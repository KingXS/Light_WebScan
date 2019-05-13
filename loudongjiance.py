# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'loudongjiance.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_loudongjiance(object):
    def setupUi(self, loudongjiance):
        loudongjiance.setObjectName("loudongjiance")
        loudongjiance.resize(510, 490)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        loudongjiance.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(loudongjiance)
        self.label.setGeometry(QtCore.QRect(190, 0, 161, 101))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.pushButton = QtWidgets.QPushButton(loudongjiance)
        self.pushButton.setGeometry(QtCore.QRect(210, 130, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.pushButton_2 = QtWidgets.QPushButton(loudongjiance)
        self.pushButton_2.setGeometry(QtCore.QRect(210, 200, 93, 28))
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_3 = QtWidgets.QPushButton(loudongjiance)
        self.pushButton_3.setGeometry(QtCore.QRect(210, 270, 93, 28))
        self.pushButton_3.setObjectName("pushButton_3")

        self.retranslateUi(loudongjiance)
        QtCore.QMetaObject.connectSlotsByName(loudongjiance)

    def retranslateUi(self, loudongjiance):
        _translate = QtCore.QCoreApplication.translate
        loudongjiance.setWindowTitle(_translate("loudongjiance", "loudongjiance"))
        self.label.setText(_translate("loudongjiance", "漏洞检测"))
        self.pushButton.setText(_translate("loudongjiance", "CMS漏洞"))
        self.pushButton_2.setText(_translate("loudongjiance", "SQL注入"))
        self.pushButton_3.setText(_translate("loudongjiance", "XSS漏洞"))

