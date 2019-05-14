# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'LD_cms.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_LD_cms(object):
    def setupUi(self, LD_cms):
        LD_cms.setObjectName("LD_cms")
        LD_cms.resize(984, 850)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("C:/Users/23584/Pictures/lovewallpaper/PK2.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        LD_cms.setWindowIcon(icon)
        self.label = QtWidgets.QLabel(LD_cms)
        self.label.setGeometry(QtCore.QRect(400, 0, 251, 91))
        self.label.setStyleSheet("font: 22pt \"楷体\";")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(LD_cms)
        self.label_2.setGeometry(QtCore.QRect(110, 100, 72, 15))
        self.label_2.setObjectName("label_2")
        self.lineEdit = QtWidgets.QLineEdit(LD_cms)
        self.lineEdit.setGeometry(QtCore.QRect(230, 90, 521, 31))
        self.lineEdit.setObjectName("lineEdit")
        self.pushButton = QtWidgets.QPushButton(LD_cms)
        self.pushButton.setGeometry(QtCore.QRect(780, 100, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.comboBox = QtWidgets.QComboBox(LD_cms)
        self.comboBox.setGeometry(QtCore.QRect(430, 140, 131, 22))
        self.comboBox.setObjectName("comboBox")
        self.textBrowser = QtWidgets.QTextBrowser(LD_cms)
        self.textBrowser.setGeometry(QtCore.QRect(10, 190, 961, 641))
        self.textBrowser.setObjectName("textBrowser")

        self.retranslateUi(LD_cms)
        QtCore.QMetaObject.connectSlotsByName(LD_cms)

    def retranslateUi(self, LD_cms):
        _translate = QtCore.QCoreApplication.translate
        LD_cms.setWindowTitle(_translate("LD_cms", "LD-cms"))
        self.label.setText(_translate("LD_cms", "CMS漏洞检测"))
        self.label_2.setText(_translate("LD_cms", "网站URL："))
        self.pushButton.setText(_translate("LD_cms", "开始"))

