# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Info_ports.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Info_ports(object):
    def setupUi(self, Info_ports):
        Info_ports.setObjectName("Info_ports")
        Info_ports.resize(806, 558)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        Info_ports.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(Info_ports)
        self.label.setGeometry(QtCore.QRect(250, 10, 351, 91))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(Info_ports)
        self.label_2.setGeometry(QtCore.QRect(70, 130, 72, 15))
        self.label_2.setObjectName("label_2")
        self.lineEdit = QtWidgets.QLineEdit(Info_ports)
        self.lineEdit.setGeometry(QtCore.QRect(220, 120, 351, 31))
        self.lineEdit.setObjectName("lineEdit")
        self.pushButton = QtWidgets.QPushButton(Info_ports)
        self.pushButton.setGeometry(QtCore.QRect(630, 120, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.textEdit = QtWidgets.QTextEdit(Info_ports)
        self.textEdit.setGeometry(QtCore.QRect(120, 230, 571, 271))
        self.textEdit.setObjectName("textEdit")
        self.radioButton = QtWidgets.QRadioButton(Info_ports)
        self.radioButton.setGeometry(QtCore.QRect(240, 180, 115, 19))
        self.radioButton.setObjectName("radioButton")
        self.radioButton_2 = QtWidgets.QRadioButton(Info_ports)
        self.radioButton_2.setGeometry(QtCore.QRect(460, 180, 115, 19))
        self.radioButton_2.setObjectName("radioButton_2")

        self.retranslateUi(Info_ports)
        QtCore.QMetaObject.connectSlotsByName(Info_ports)

    def retranslateUi(self, Info_ports):
        _translate = QtCore.QCoreApplication.translate
        Info_ports.setWindowTitle(_translate("Info_ports", "Info-ports"))
        self.label.setText(_translate("Info_ports", "端口扫描与服务识别"))
        self.label_2.setText(_translate("Info_ports", "网站URL："))
        self.pushButton.setText(_translate("Info_ports", "开始"))
        self.radioButton.setText(_translate("Info_ports", "快速扫描"))
        self.radioButton_2.setText(_translate("Info_ports", "全面扫描"))

