import os
import unittest
import time
import threading
from read_writeyaml import MyYaml
from myloging import Loging
from models.myunit import mytest
from models.myunit_per import ReadYaml
from models.MyRedis import Myredis as redis
from configpath import getpath


log = Loging()
redis = redis()
path = getpath()

class myThread(threading.Thread):   #继承父类threading.Thread
    def __init__(self, threadID, name, module, times):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.module = module
        self.time = times

    def run(self):
        time.sleep(self.time)
        log.info('开启线程:{}'.format(self.name))
        RunAllClass().run_module(self.module)  #把要执行的代码写到run函数里面 线程在创建后会直接运行run函数

    def __del__(self):
        log.info('{}线程结束！'.format(self.name))

class RunAllClass(object):
    def __init__(self):
        pass

    def run_module(self, moudleName):
        """
        运行单个模块
        :param moduleName:
        :return:
        """
        suite = unittest.TestSuite()
        suite.addTest(mytest.parametrize(moudleName, param=None))
        runner = unittest.TextTestRunner(verbosity=1)   #执行测试用例集 ,,verbosity 有 0 1 2 三个级别，verbosity=2 的输出最详细
        result = runner.run(suite)
        if result.failures:                   #错误用例
            failures_list = []                #错误用例列表
            for i in result.failures:
                case_id = str(i[0]).split('(')[0]
                case_info = str(i[1])
                failures_list.append([case_id, case_info])
            redis.case_failures(failures_list)
        if result.errors:
            errors_list = []
            for i in result.errors:
                case_id = str(i[0]).split('(')[0]
                case_info = str(i[1])
                errors_list.append([case_id, case_info])
            redis.case_errors(errors_list)
        if result.skipped:
            skipped_list = []
            for i in result.skipped:
                case_id = str(i[0]).split('(')[0]
                case_info = str(i[1])
                skipped_list.append([case_id, case_info])
            redis.case_skipped(skipped_list)

class AllResult(object):
    """所有执行结果"""

    def __init__(self):
        redis.remove_redis([                         #新一轮测试前删除redis缓存数据
            'all_module',
            'case_data',
            'case_failures',
            'case_errors',               #删除数据
            'case_skipped',
        ])
        self.timeout = MyYaml().config('timeout')
        self.projectName = MyYaml().config('projectName')
        self.EnvName = MyYaml().config('EnvName')    #测试环境
        self.moudleName = MyYaml().config('moudleName')    # all
        if self.moudleName is None:
            self.moudleName = ''
        self.matching = MyYaml().config('matching')        #正则
        # self.ip = MyYaml().config('ip')
        # self.domain = MyYaml().config('domain')     #本地测试环境
        # self.app_config = MyYaml().interface_data
        # if self.domain is None:
        #     self.get_url = 'http://{}/polls/get_report/'.format(self.ip)
        # else:
        #     self.get_url = 'http://{}/polls/get_report/'.format(self.domain)
        # self.message = MyYaml().config('message')

        def moudle_name():
            """
            获取可运行模块
            :return: moudle list
            """
            moudleName = MyYaml().config('moudleName')
            project_names = os.path.join(path, '{}'.format(self.projectName))
            dir_list = os.listdir(project_names)     #os.listdir(project_names):列出paoject_names下的目录和文件
            moudle_list = []    #一级目录
            all_import_class = []    #所有要导入的测试类
            all_moudle = []
            if moudleName is None:
                for i in dir_list:
                    if '.' not in i and '__' not in i:
                        if os.path.exists(project_names + '/{}/__init__.py'.format(i)):
                            moudle_list.append(i)
            else:
                if os.path.exists(project_names + '/{}/__init__.py'.format(moudleName)):
                    moudle_list.append(moudleName)
            for a in moudle_list:
                dir_name = project_names + '\\' + a
                dir_list = os.listdir(dir_name)
                for b in dir_list:
                    if self.matching.split('_')[1] in b:
                        import_name = '{}_{}'.format(b.split('_')[0], a)
                        all_import_class.append('from.{}.{} import {}'.format(a, b.split('.')[0], import_name))
                        all_import_class.append('\n')
                        all_moudle.append(import_name)
            init_file_py = project_names + '/__init__.py'
            if os.path.exists(init_file_py):        #os.path.exists(init_file_py):判断是否存在文件或目录init_file_py
                os.remove(init_file_py)        #os.remove(file):删除一个文件
            all_moudle = str(all_moudle)
            import re
            all_moudle = re.sub("'", '', all_moudle)    #sub()：替换
            with open(init_file_py, 'w') as f:
                f.writelines(all_import_class)
                f.write('moudle_list = {}'.format(all_moudle))
                f.write('\n')
                f.close()
            return all_moudle, moudle_list   #all_moudle=所有类名（模块），moudle_list=case包下的所有包
        self.all_moudle, self.moudle_list = moudle_name()

    def run_class(self):
        from case import moudle_list
        redis.all_module(moudle_list)     #存进redis
        #创建新线程
        count = 0
        numbers = 0
        if len(redis.read_moudle('all_module')) != 0:    #计算长度，len长度
            while True:       #循环
                log.info('共计{}个测试类'.format(len(redis.read_moudle('all_module'))))
                if len(redis.read_moudle('all_module')) != 0:
                    threads = []
                    log.info('添加线程')
                    try:
                        moudle = redis.rpop('all_module', MyYaml().config('thread_count'))
                        moudle_per = ReadYaml().return_module(moudle_list, moudle)
                        for i in moudle_per:
                            threads.append(myThread(count, "Thread-{}".format(count), i, 0))
                            count += 1
                    except Exception:
                        pass
                    #开启新线程
                    for i in threads:
                        try:
                            i.start()   #start开启线程
                        except Exception:
                            pass
                    #等待所有线程完成
                    for t in threads:
                        try:
                            t.join()    #等待线程、子线程完毕后关闭主线程
                        except Exception:
                            pass
                    log.info('主进行{}结束'.format(numbers))
                    numbers += 1
                else:
                    log.info('所有主进程结束！')
                    break
        else:
            log.info('测试集为空')


    def run_all_case(self):
        now_time = time.strftime('%Y-%m-%d %H:%M:%S')
        log.debug('now_time:{}'.format(now_time))
        self.run_class()  # 运行所有模块


if __name__ == '__main__':
    AllResult().run_all_case()























































