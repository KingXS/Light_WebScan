# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'LD-XSS.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_LD_XSS(object):
    def setupUi(self, LD_XSS):
        LD_XSS.setObjectName("LD_XSS")
        LD_XSS.resize(757, 431)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        LD_XSS.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(LD_XSS)
        self.label.setGeometry(QtCore.QRect(290, 20, 221, 41))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(LD_XSS)
        self.label_2.setGeometry(QtCore.QRect(80, 100, 91, 16))
        self.label_2.setObjectName("label_2")
        self.lineEdit = QtWidgets.QLineEdit(LD_XSS)
        self.lineEdit.setGeometry(QtCore.QRect(220, 90, 321, 31))
        self.lineEdit.setObjectName("lineEdit")
        self.pushButton = QtWidgets.QPushButton(LD_XSS)
        self.pushButton.setGeometry(QtCore.QRect(620, 90, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.textEdit = QtWidgets.QTextEdit(LD_XSS)
        self.textEdit.setGeometry(QtCore.QRect(130, 160, 511, 191))
        self.textEdit.setObjectName("textEdit")

        self.retranslateUi(LD_XSS)
        QtCore.QMetaObject.connectSlotsByName(LD_XSS)

    def retranslateUi(self, LD_XSS):
        _translate = QtCore.QCoreApplication.translate
        LD_XSS.setWindowTitle(_translate("LD_XSS", "LD-XSS"))
        self.label.setText(_translate("LD_XSS", "XSS漏洞检测"))
        self.label_2.setText(_translate("LD_XSS", "疑似漏洞点："))
        self.pushButton.setText(_translate("LD_XSS", "开始"))

