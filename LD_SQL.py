# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'LD_SQL.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_LD_SQL(object):
    def setupUi(self, LD_SQL):
        LD_SQL.setObjectName("LD_SQL")
        LD_SQL.resize(788, 506)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        LD_SQL.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(LD_SQL)
        self.label.setGeometry(QtCore.QRect(300, 30, 231, 51))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(LD_SQL)
        self.label_2.setGeometry(QtCore.QRect(70, 120, 91, 16))
        self.label_2.setObjectName("label_2")
        self.lineEdit = QtWidgets.QLineEdit(LD_SQL)
        self.lineEdit.setGeometry(QtCore.QRect(210, 110, 361, 31))
        self.lineEdit.setObjectName("lineEdit")
        self.pushButton = QtWidgets.QPushButton(LD_SQL)
        self.pushButton.setGeometry(QtCore.QRect(620, 110, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.textBrowser = QtWidgets.QTextBrowser(LD_SQL)
        self.textBrowser.setGeometry(QtCore.QRect(30, 170, 731, 301))
        self.textBrowser.setObjectName("textBrowser")

        self.retranslateUi(LD_SQL)
        QtCore.QMetaObject.connectSlotsByName(LD_SQL)

    def retranslateUi(self, LD_SQL):
        _translate = QtCore.QCoreApplication.translate
        LD_SQL.setWindowTitle(_translate("LD_SQL", "LD-SQL"))
        self.label.setText(_translate("LD_SQL", "SQL注入检测"))
        self.label_2.setText(_translate("LD_SQL", "疑似注入点："))
        self.pushButton.setText(_translate("LD_SQL", "开始检测"))

