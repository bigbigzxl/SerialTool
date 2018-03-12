#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys

from PyQt4 import QtGui
from PyQt4.QtGui import *

from pyusb.pyqt4UI.ForTest import untitled


class Ui(QtGui.QMainWindow, untitled.Ui_MainWindow):#
	#注意上面继承这里，整了我半天，按照网上的代码是继承自QWidget，但是我的qt designer是新建的一个MainWindow啊！所以改一下就好了！。
	def __init__(self, parent=None):
		super(Ui, self).__init__(parent=parent)
		self.setupUi(self)

# class Ui(QtGui.QMainWindow, usb4site.Ui_MainWindow):#,untitled.Ui_MainWindow
# 	def __init__(self, parent=None):
# 		super(Ui, self).__init__(parent=parent)
# 		self.setupUi(self)
		
app = QApplication(sys.argv)
ui = Ui()
ui.show()
app.exec_()