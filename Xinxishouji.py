# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Xinxishouji.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Xinxishouji(object):
    def setupUi(self, Xinxishouji):
        Xinxishouji.setObjectName("Xinxishouji")
        Xinxishouji.resize(461, 473)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        Xinxishouji.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(Xinxishouji)
        self.label.setGeometry(QtCore.QRect(160, 10, 151, 91))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.pushButton = QtWidgets.QPushButton(Xinxishouji)
        self.pushButton.setGeometry(QtCore.QRect(160, 140, 141, 41))
        self.pushButton.setObjectName("pushButton")
        self.pushButton_2 = QtWidgets.QPushButton(Xinxishouji)
        self.pushButton_2.setGeometry(QtCore.QRect(160, 220, 141, 41))
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_3 = QtWidgets.QPushButton(Xinxishouji)
        self.pushButton_3.setGeometry(QtCore.QRect(140, 300, 191, 51))
        self.pushButton_3.setObjectName("pushButton_3")

        self.retranslateUi(Xinxishouji)
        QtCore.QMetaObject.connectSlotsByName(Xinxishouji)

    def retranslateUi(self, Xinxishouji):
        _translate = QtCore.QCoreApplication.translate
        Xinxishouji.setWindowTitle(_translate("Xinxishouji", "Xinxishouji"))
        self.label.setText(_translate("Xinxishouji", "信息收集"))
        self.pushButton.setText(_translate("Xinxishouji", "网站基本信息"))
        self.pushButton_2.setText(_translate("Xinxishouji", "子域名"))
        self.pushButton_3.setText(_translate("Xinxishouji", "端口扫描与服务识别"))

