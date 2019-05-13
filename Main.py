#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
import sys
import os
#引用相关的界面模块
from Zhujiemian import  Ui_Zhujiemian

#信息收集界面
from Xinxishouji import Ui_Xinxishouji
from Info_submain import Ui_Info_submain
from Info_ports import Ui_Info_ports
from Info_basic import  Ui_Info_basic

#漏洞检测界面
from loudongjiance import Ui_loudongjiance
from LD_cms import Ui_LD_cms
from LD_SQL import Ui_LD_SQL
from LD_XSS import Ui_LD_XSS

#报告输出界面
from Baogao import Ui_Baogao


########################################################################################################################
###############主界面模块


class new_Zhujiemian(QtWidgets.QWidget, Ui_Zhujiemian):
    def __init__(self):
        super(new_Zhujiemian,self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.Xinxishouji_show)
        self.pushButton_2.clicked.connect(self.loudongjiance_show)
        self.pushButton_3.clicked.connect(self.Baogao_show)

#显示信息收集界面
    def Xinxishouji_show(self):
        Xinxishouji.show()

#显示漏洞检测模块
    def loudongjiance_show(self):
        loudongjiance.show()

#显示报告查看界面
    def Baogao_show(self):
        Baogao.show()





########################################################################################################################
###############信息收集模块
class new_Xinxishouji(QtWidgets.QWidget, Ui_Xinxishouji):
    def __init__(self):
        super(new_Xinxishouji,self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.Info_basic_show)
        self.pushButton_2.clicked.connect(self.Info_submain_show)
        self.pushButton_3.clicked.connect(self.Info_ports_show)

    def Info_basic_show(self):
        Info_basic.show()

    def Info_submain_show(self):
        Info_submain.show()

    def Info_ports_show(self):
        Info_ports.show()

#基本信息收集
class new_Info_basic(QtWidgets.QWidget, Ui_Info_basic):
    def __init__(self):
        super(new_Info_basic,self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.Start_Info_basic)

    #开始基本信息采集
    def Start_Info_basic(self):
        os.chdir('E:\BYSJ\ZJH\Info_Basic\WebEye-master')
        #获取网站URL
        url = self.lineEdit.text()
        Mingling1 = "python2 E:\BYSJ\ZJH\Info_Basic\WebEye-master/WebEye.py -u "+url
        output = os.popen(Mingling1)
        print(output)
        x = output.read()
        self.textEdit.setText(x)






#子域名采集
class new_Info_submain(QtWidgets.QWidget, Ui_Info_submain):
    def __init__(self):
        super(new_Info_submain,self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.Start_Info_basic)


    # 开始子域名采集
    def Start_Info_basic(self):
        # 获取网站URL
        os.chdir('E:\BYSJ\ZJH\Info_Submain')
        url = self.lineEdit.text()
        Mingling2 = "python2 subDomainsBrute.py "+url
        Mingling2 = str(Mingling2)
        print(Mingling2)
        output = os.popen(Mingling2)
        x = output.read()
        print(x)

        self.textEdit.setText(x)


#端口扫描
class new_Info_ports(QtWidgets.QWidget, Ui_Info_ports):
    def __init__(self):
        super(new_Info_ports,self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.Start_Info_ports)

# 开始端口扫描
    def Start_Info_ports(self):
        # 获取网站URL
        url = self.lineEdit.text()
        if (self.radioButton.isChecked()):
            type = 'p'
        elif (self.radioButton_2.isChecked()):
            type = 'f'
        Mingling3 = "python E:/BYSJ/ZJH/Info_Ports/PortScan.py -u "+url+" -t "+type
        Mingling3 = str(Mingling3)
        print(Mingling3)
        output = os.system(Mingling3)

        self.textEdit.setText(output)


########################################################################################################################
################漏洞检测模块
class new_loudongjiance(QtWidgets.QWidget, Ui_loudongjiance):
    def __init__(self):
        super(new_loudongjiance,self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.LD_cms_show)
        self.pushButton_2.clicked.connect(self.LD_SQL_show)
        self.pushButton_3.clicked.connect(self.LD_XSS_show)

    def LD_cms_show(self):
        LD_cms.show()

    def LD_SQL_show(self):
        LD_SQL.show()

    def LD_XSS_show(self):
        LD_XSS.show()


#cms漏洞检测
class new_LD_cms(QtWidgets.QWidget, Ui_LD_cms):
    def __init__(self):
        super(new_LD_cms,self).__init__()
        self.setupUi(self)
#SQL注入
class new_LD_SQL(QtWidgets.QWidget, Ui_LD_SQL):
    def __init__(self):
        super(new_LD_SQL,self).__init__()
        self.setupUi(self)
#XSS检测
class new_LD_XSS(QtWidgets.QWidget, Ui_LD_XSS):
    def __init__(self):
        super(new_LD_XSS,self).__init__()
        self.setupUi(self)






########################################################################################################################
#######展示报告模块
class new_Baogao(QtWidgets.QWidget, Ui_Baogao):
    def __init__(self):
        super(new_Baogao,self).__init__()
        self.setupUi(self)










########################################################################################################################
#主函数
if __name__=='__main__':
    app = QtWidgets.QApplication(sys.argv)
    Zhujiemian=new_Zhujiemian()     #定义主界面对象
    Zhujiemian.show()
########################################################################################################################
    #信息收集界面
    Xinxishouji = new_Xinxishouji()

    #基本信息采集界面
    Info_basic = new_Info_basic()
    #子域名采集
    Info_submain = new_Info_submain()
    #端口扫描
    Info_ports = new_Info_ports()

################################################
    #漏洞检测界面
    loudongjiance = new_loudongjiance()

    #cms漏洞检测
    LD_cms = new_LD_cms()
    #SQL注入
    LD_SQL = new_LD_SQL()
    #XSS检测
    LD_XSS = new_LD_XSS()

################################################
    #漏洞报告界面
    Baogao = new_Baogao()

    sys.exit(app.exec_())







