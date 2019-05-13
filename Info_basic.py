# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Info_basic.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Info_basic(object):
    def setupUi(self, Info_basic):
        Info_basic.setObjectName("Info_basic")
        Info_basic.resize(658, 548)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        Info_basic.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(Info_basic)
        self.label.setGeometry(QtCore.QRect(210, 0, 231, 91))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(Info_basic)
        self.label_2.setGeometry(QtCore.QRect(50, 110, 72, 15))
        self.label_2.setObjectName("label_2")
        self.lineEdit = QtWidgets.QLineEdit(Info_basic)
        self.lineEdit.setGeometry(QtCore.QRect(160, 100, 321, 31))
        self.lineEdit.setObjectName("lineEdit")
        self.pushButton = QtWidgets.QPushButton(Info_basic)
        self.pushButton.setGeometry(QtCore.QRect(520, 100, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.textEdit = QtWidgets.QTextEdit(Info_basic)
        self.textEdit.setGeometry(QtCore.QRect(130, 170, 391, 321))
        self.textEdit.setObjectName("textEdit")

        self.retranslateUi(Info_basic)
        QtCore.QMetaObject.connectSlotsByName(Info_basic)

    def retranslateUi(self, Info_basic):
        _translate = QtCore.QCoreApplication.translate
        Info_basic.setWindowTitle(_translate("Info_basic", "Info-basic"))
        self.label.setText(_translate("Info_basic", "网站基本信息"))
        self.label_2.setText(_translate("Info_basic", "网站URL："))
        self.pushButton.setText(_translate("Info_basic", "开始"))

