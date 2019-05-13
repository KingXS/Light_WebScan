# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Info_submain.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Info_submain(object):
    def setupUi(self, Info_submain):
        Info_submain.setObjectName("Info_submain")
        Info_submain.resize(711, 490)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        Info_submain.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(Info_submain)
        self.label.setGeometry(QtCore.QRect(270, 0, 201, 91))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(Info_submain)
        self.label_2.setGeometry(QtCore.QRect(80, 110, 81, 21))
        self.label_2.setObjectName("label_2")
        self.lineEdit = QtWidgets.QLineEdit(Info_submain)
        self.lineEdit.setGeometry(QtCore.QRect(190, 100, 321, 31))
        self.lineEdit.setObjectName("lineEdit")
        self.pushButton = QtWidgets.QPushButton(Info_submain)
        self.pushButton.setGeometry(QtCore.QRect(560, 100, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.textEdit = QtWidgets.QTextEdit(Info_submain)
        self.textEdit.setGeometry(QtCore.QRect(80, 160, 561, 281))
        self.textEdit.setObjectName("textEdit")

        self.retranslateUi(Info_submain)
        QtCore.QMetaObject.connectSlotsByName(Info_submain)

    def retranslateUi(self, Info_submain):
        _translate = QtCore.QCoreApplication.translate
        Info_submain.setWindowTitle(_translate("Info_submain", "Info-submain"))
        self.label.setText(_translate("Info_submain", "子域名采集"))
        self.label_2.setText(_translate("Info_submain", "网站URL："))
        self.pushButton.setText(_translate("Info_submain", "开始采集"))

