# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Zhujiemian.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Zhujiemian(object):
    def setupUi(self, Zhujiemian):
        Zhujiemian.setObjectName("Zhujiemian")
        Zhujiemian.resize(545, 737)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        Zhujiemian.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(Zhujiemian)
        self.label.setGeometry(QtCore.QRect(100, 30, 391, 101))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.pushButton = QtWidgets.QPushButton(Zhujiemian)
        self.pushButton.setGeometry(QtCore.QRect(200, 200, 161, 51))
        self.pushButton.setObjectName("pushButton")
        self.pushButton_2 = QtWidgets.QPushButton(Zhujiemian)
        self.pushButton_2.setGeometry(QtCore.QRect(200, 320, 161, 51))
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_3 = QtWidgets.QPushButton(Zhujiemian)
        self.pushButton_3.setGeometry(QtCore.QRect(200, 440, 161, 51))
        self.pushButton_3.setObjectName("pushButton_3")

        self.retranslateUi(Zhujiemian)
        QtCore.QMetaObject.connectSlotsByName(Zhujiemian)

    def retranslateUi(self, Zhujiemian):
        _translate = QtCore.QCoreApplication.translate
        Zhujiemian.setWindowTitle(_translate("Zhujiemian", "Zhujiemiam"))
        self.label.setText(_translate("Zhujiemian", "轻量级WEB漏洞扫描器"))
        self.pushButton.setText(_translate("Zhujiemian", "信息收集"))
        self.pushButton_2.setText(_translate("Zhujiemian", "漏洞检测"))
        self.pushButton_3.setText(_translate("Zhujiemian", "报告查看"))

