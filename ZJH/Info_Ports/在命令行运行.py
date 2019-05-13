#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
Mingling = 'python 端口扫描-2.py -u http://www.kibing-glass.com -t p'
output = os.popen(Mingling)
x = output.read()
print(x)