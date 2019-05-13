import os
Mingling = 'python E:/BYSJ/ZJH/Info_Ports/PortScan.py -u http://www.kibing-glass.com -t p'
output = os.popen(Mingling)
x = output.read()
print(x)