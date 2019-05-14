# -*- coding: utf-8 -*-
import subprocess
import os
import time
#sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding = 'gb180030')
Mingling = 'python2 E:\BYSJ\ZJH\Vul_det\SQL_Vul/sqlmap.py -u http://www.symotor.com/news.php?id=31 --risk 3 --level 3 --dbs'
#output = subprocess.check_output(Mingling)
#x = output.readlines()
#print(output.decode("utf-8"))

#x = output.read().decode("gbk")
popen = subprocess.Popen(Mingling,  # 需要执行的文件路径
                         stdout = subprocess.PIPE,
                         stderr = subprocess.PIPE,
                         bufsize=1)

# 重定向标准输出
while popen.poll() is None:                      # None表示正在执行中
    r = popen.stdout.read().decode("utf-8")
    print(r)                                # 可修改输出方式，比如控制台、文件等

# 重定向错误输出
if popen.poll() != 0:                                   # 不为0表示执行错误
    err = popen.stderr.read().decode("utf-8")
    print(err)                             # 可修改输出方式，比如控制台、文件等