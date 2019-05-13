# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Baogao.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Baogao(object):
    def setupUi(self, Baogao):
        Baogao.setObjectName("Baogao")
        Baogao.resize(464, 511)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        Baogao.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(Baogao)
        self.label.setGeometry(QtCore.QRect(160, 20, 151, 111))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.pushButton = QtWidgets.QPushButton(Baogao)
        self.pushButton.setGeometry(QtCore.QRect(190, 160, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.pushButton_2 = QtWidgets.QPushButton(Baogao)
        self.pushButton_2.setGeometry(QtCore.QRect(190, 250, 93, 28))
        self.pushButton_2.setObjectName("pushButton_2")

        self.retranslateUi(Baogao)
        QtCore.QMetaObject.connectSlotsByName(Baogao)

    def retranslateUi(self, Baogao):
        _translate = QtCore.QCoreApplication.translate
        Baogao.setWindowTitle(_translate("Baogao", "Baogao"))
        self.label.setText(_translate("Baogao", "报告输出"))
        self.pushButton.setText(_translate("Baogao", "输出报告"))
        self.pushButton_2.setText(_translate("Baogao", "查看报告"))

