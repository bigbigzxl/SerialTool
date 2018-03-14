#! /usr/bin/env python
# -*- coding: utf-8 -*-

#用来解这个bug的：ERROR 'QString' object has no attribute 'upper'
#https://stackoverflow.com/questions/37263086/attributeerror-qstring-object-has-no-attribute-rfind
#QtCore.QString("demo text")不用这个新的aapi的话就得用这个做字符串映射。
import sip
sip.setapi('QString', 2)



import usb4site
import sys
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import *


# serial part
from Utils.SerialHelper import SerialHelper
import platform
import logging
import threading
import time,datetime
import re
import csv
import os
# 根据系统 引用不同的库
if platform.system() == "Windows":
	from serial.tools import list_ports
else:
	import glob
	import os
	import re

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S')
# 结束符（16进制）CR 13; NL(LF) 10
END_HEX = "16"
CURR_ERROR = -10

# usb part

class  serial_part(QObject):
	# 创建一个信号，用来在子线程里面发送信号来改变主线程里面的界面的
	signal_ser = pyqtSignal(dict)
	
	def __init__(self, port='', channel=1, parent=None):
		super(serial_part, self).__init__(parent)
		'''
		我的预期是：界面程序中每增加一个串口部分，我就直接调用这个类就好了；
		在信号发射后，槽函数接收到信号就创建一个串口实例，不能打开则直接报错并弹框显示错误，能打开则自动连接；
		'''
		self.current_system = "Android7.x"
		self.channel = channel
		self.port = port
		self.receive_data_zxl = ''
		self.Item_testtime = 0
		self.TIME_OUT = 60
		self.mem_runtime = 0
		#       0: Testting...
		#       1: TestFail/Ready
		# 第一个测试项检测到STOP=1则表示ready，其余项则表示FAIL;
		self.STOP = True
		self.FailLog_folderPath, self.database_path = self.Init_TestData()
		# self.FailLog_folderPath,self.database_path = self.Init_TestData()
		self._Data_Lock = threading.Lock()
		self.OpenSerial()
		
	def change_curSystem(self, cur_system):
		if cur_system == self.current_system:
			pass
		else:
			self.current_system = cur_system
			
	# Serial part.
	def OpenSerial(self):
		w = QWidget()
		if self.port == '':
			QMessageBox.warning(w, "Message", u"没有串口号啊！")
		elif "COM" not in self.port and len(self.port) > 6:
			QMessageBox.warning(w, "Message", u"串口字符有问题啊！")
		else:
			self._open_serial()
	
	def _open_serial(self):
		'''
        打开串口设备
        '''
		try:
			self.baudrate = 115200
			self.parity = 'N'
			self.databit = 8
			self.stopbit = 1
			self.ser = SerialHelper(Port=self.port,
			                   BaudRate=self.baudrate,
			                   ByteSize=self.databit,
			                   Parity=self.parity,
			                   Stopbits=self.stopbit)
			self.ser.connect()
			if self.ser.is_connected:
				self.ser.write("poweroff\r\n")
				#开了个线程，只要串口线连接着就不断地去取数据，取满一行就调用上层的这个处理函数来处理；
				self.ser.on_data_received(self.serial_on_data_received)
			else:
				w = QWidget()
				QMessageBox.warning(w, "Message", u"是不是已经被打开了呢？检查下吧！")
				print "cant open [{0}] !".format(self.port)
				
		except Exception as e:
			logging.error(e)
			logging.error("Open [{0}] Failed!".format(self.port))
	
	def Ser_close(self):
		self.ser.disconnect()
		
	def serial_on_data_received(self, data_line):
			"""
	        串口接收数据回调函数:只有在串口接收线程里面判断接收到了1行之后才会调用这个函数
	        """
			#这里会不会冲突的？底层往receive_data_zxl里写数据，别的地方又读又擦除的！
			#这里装把锁，可以保证线程安全，数据不会乱，当测试函数在处理这个字符段的时候，acqure就会阻塞等待（这里有假设inwating的buffer足够大哈！）；
			with self._Data_Lock:
				data_line = data_line.strip().replace("\b", "")
				# print data_line
				self.receive_data_zxl += data_line
				#数据量太大会怎么样？我要限制一下大小;
				# if len(self.receive_data_zxl) > 3000:
				# 	print "outside"
				# 	pass
				# else:
				# 	print data_line
				# 	self.receive_data_zxl += data_line
				
	#########################################################
	# 测试函数：
	#    Test pattern  support part.
	#########################################################
	def check_before_test(self):
		# 安检而已啦！
		if self.ser and self.ser.is_connected:
			print("serial is opened.\r\n")
		else:
			w = QWidget()
			QMessageBox.warning(w, "Message", u"串口，你去哪儿了？！")
			return False
		# 重复点击按钮的判别，放到槽函数里面去识别。
		return True
	
	def check_luncher(self):
		# 仅检测主界面是否存在！
		# waitting for system lunch.
		timeout = 3
		lunched = False
		cmd = "dumpsys activity | grep Focus"
		
		self.ser.write("TestItem9" + "\r\n")
		time.sleep(0.5)
		
		for i in range(10):
			self.ser.write("TestItem8" + "\r\n")
			start_time = time.time()
			while (time.time() - start_time) < timeout:
				if self.STOP:
					return False
				
				if self.receive_data_zxl == '':
					time.sleep(0.5)
					continue
					#com.softwinner.firelauncher ===> Android4.4
					#"com.android.tv.launcher"  ===> Android7.X
				elif ("com.android.tv.launcher" in self.receive_data_zxl) or ("com.softwinner.firelauncher" in self.receive_data_zxl):
					lunched = True
					break
				else:
					# 这里是有安全隐患的，假如在上面判断期间就有数据进来，那么我可能是检测不到的；
					with self._Data_Lock:
						self.receive_data_zxl = ''
			if lunched == True:
				break
		if lunched == False:
			print ("luncher failed.\r\n")
			return False
		
		print ("luncher success.\r\n")
		return True
	
	def check_sleep_H6(self):
		# 无论你是处于什么状态，我都会把你整成休眠状态，至死方休！！！吼~
		# return:
		#   True: enter sleeping.
		#   false: enter sleepMode failed with timeout
		check_sleep_sting = "PM: Entering mem sleep"  # "PM: suspend entry"
		self.ser.write("TestItem9" + "\n")
		time.sleep(0.1)
		self.ser.write("TestItem0#echo 8 >/proc/sysrq-trigger\r\n")
		time.sleep(1)
		
		
		self.ser.write("TestItem5" + "\n")
		start_time = time.time()
		while (time.time() - start_time) < 5:
			if self.STOP:
				return False
			if self.receive_data_zxl == '':
				time.sleep(0.2)
				continue
			elif check_sleep_sting in self.receive_data_zxl:
				return True
			else:
				# 这里是有安全隐患的，假如在上面判断期间就有数据进来，那么我可能是检测不到的；
				with self._Data_Lock:
					self.receive_data_zxl = ''
		return False
	
	def check_wakeup_H6(self):
		# return:
		#   True: wakeup ok.
		#   false: wakeup fail.
		check_wakeup_string = "HDMI"  # 这个才是屏幕亮了 #"PM: Finishing wakeup"这个屏幕还不一定亮了，只是PMU起来了
		time.sleep(1)
		self.ser.write("TestItem5" + "\r\n")
		start_time = time.time()
		while (time.time() - start_time) < 20:
			if self.STOP:
				return False
			if self.receive_data_zxl == '':
				time.sleep(0.2)
				continue
			elif check_wakeup_string in self.receive_data_zxl:
				return True
			else:
				# 这里是有安全隐患的，假如在上面判断期间就有数据进来，那么我可能是检测不到的；
				with self._Data_Lock:
					self.receive_data_zxl = ''
		return False
	
	def checkStop_Poweroff(self):
		# 只在autotesting里面的步骤之间用，因为这会直接把系统关机的；
		# 比如我在每个子测试项里面运行的时候，检测到了STOP（即你手动点的），我就直接返回一个False，然后在
		# autotestting这个主干线里面进行退出操作；
		if self.STOP:
			self.TestData_line[1] = "Fail"
			self.record_TestData(self.TestData_line)
			# step7: system down and power off
			self.TestItem_SysPoweroff()
			return True
		else:
			return False
		
	def writeCMD_check(self, cmd="", check_string="", timeout=30):
		
		Timeout = timeout
		# Cmd = cmd
		# Check_string = check_string
		StartTime = time.time()
		EndTime = time.time()
		
		# check parameter
		if cmd == "" or check_string == "":
			print("\r\nwrong cmd or check_string in writeCMD_check()\r\n")
			return False
		
		# start check
		self.ser.write(cmd + "\n")
		while EndTime - StartTime < Timeout:
			if self.STOP:
				return False
			if self.receive_data_zxl == '':
				time.sleep(0.2)
				continue
			elif check_string in self.receive_data_zxl:
				break
			else:
				# 这里是有安全隐患的，假如在上面判断期间就有数据进来，那么我可能是检测不到的；
				with self._Data_Lock:
					self.receive_data_zxl = ''
			
			EndTime = time.time()
		
		# return check outcome.
		if EndTime - StartTime + 0.5 < Timeout:
			return True
		
		return False
	
	def run_memtester(self, size="128M", circle="1000"):
		
		if self.current_system == "Android7.x":
			cmd = "TestItem0#/data/memtester {} {} 0 &".format(size, circle)
		elif self.current_system == "Android4.4":
			cmd = "TestItem0#/data/memtester {} {} 0 &".format("20M", 1000)
		else:
			return False
		
		self.ser.write(cmd + "\n")
		print(cmd)
		# 开四核
		# for i in range(4):
		# 	self.ser.write(cmd + "\n")
		END_string = "8-bit Writes"
		START_sting = "memtester version"
		start_pattern = re.compile(START_sting)
		end_pattern = re.compile(END_string)
		StartTime = time.time()
		while True:
			# 数据量太大的时候会导致搜索很费时间
			# if len(self.receive_data_zxl) > 100:
			# 	continue
			# if START_sting in self.receive_data_zxl:
			if self.STOP:
				return False
			if self.receive_data_zxl == '':
				time.sleep(0.2)
				continue
			elif start_pattern.search(self.receive_data_zxl):
				break
			else:
				# 这里是有安全隐患的，假如在上面判断期间就有数据进来，那么我可能是检测不到的；
				with self._Data_Lock:
					self.receive_data_zxl = ''
		Spend_Time = time.time() - StartTime
		self.mem_runtime = float('%.1f' % Spend_Time)
	
	def get_current(self, channel="", timeout=10):
		#############channel number###############
		# *1: SleepMode: VDD12 Current test
		# *2: RunningMode: VDD12 Current test
		# *3: SleepMode: VDD18 Current test
		# *4: RunningMode: VDD18 Current test
		##########################################
		
		# parameter check
		if channel == "":
			return -10
		self.ser.write(channel + "\r\n")
		
		start_time = time.time()
		end_time = time.time()
		while end_time - start_time < timeout:
			if self.STOP:
				return False
			if self.receive_data_zxl == '':
				time.sleep(0.5)
				continue
			else:
				# print self.receive_data_zxl
				search_outcome = re.search(r"\[\d+\.\d+\] mA", self.receive_data_zxl)  # self.receive_data_zxl
			# l = "petrel-p1:/ # running mode: VDD12 Current test,The Current is [143.00] mA;"
				# "[123.34] mA"
				# "[123.34]"
				if search_outcome:
					current_block = search_outcome.group().split(' ')[0]
					# "123.34"
					# print search_outcome,search_outcome.group(),current_block
					current_str = re.search(r"\d+\.\d+", current_block).group()
					return current_str
				else:
					with self._Data_Lock:
						self.receive_data_zxl = ''
			
			end_time = time.time()
			
		# timeout return error value
		return -10
	
	def start_thread_target(self, func='', name=''):
		print("Tread name is {}".format(name))
		tDataReceived = threading.Thread(target=func, name=name)
		tDataReceived.setDaemon(True)
		tDataReceived.start()
	
	##################DataBase part#########################
	#   功能描述：
	#           记录log的。
	########################################################
	def Init_TestData(self):
		# 检测文件或者文件夹是否存在,不存在就创建一下！
		# 最后是要返回一个文件地址的！
		# pwd = os.getcwd()
		folder_path = os.path.join(os.getcwd(), "TestData")
		if not os.path.exists(folder_path):
			# 创建文件夹
			os.makedirs(folder_path)
		
		# 存在的话，我们看下今天的测试文件有木有？
		#channel+COM+date.csv
		today_str = time.strftime('%Y%m%d', time.localtime(time.time()))
		file_path = os.path.join(folder_path, "CH"+str(self.channel)+self.port+"-"+today_str + ".csv")
		
		# 今天还没存过，那么我就创建一个。
		if not os.path.exists(file_path):
			with open(file_path, 'wb') as csvfile:
				# datetime,TestResult,InitTime,SceneVdd12,SceneVdd18,SleepVdd12,SleepVdd18,MEM+4K
				Item_names = ["datetime", "TestResult", "InitTime", "SceneVdd12", "SceneVdd18", "SleepVdd12",
				              "SleepVdd18", "MEM+4K"]
				spamwriter = csv.writer(csvfile, dialect='excel')
				spamwriter.writerow(Item_names)
		
		return folder_path, file_path
	
	def record_TestData(self, data):
		with open(self.database_path, 'ab') as csvfile:
			spamwriter = csv.writer(csvfile, dialect='excel')
			spamwriter.writerow(data)
	
	def record_FailLog(self, data):
		# 文件夹在软件打开的时候就初始化过了
		FailLog_FilePath = os.path.join(self.FailLog_folderPath, "CH"+str(self.channel)+self.port+"-"+"FailLog{}.txt".format(
			time.strftime('%Y%m%d', time.localtime(time.time()))))
		
		# 今天还没存过，那么我就创建一个。
		if not os.path.exists(FailLog_FilePath):
			with open(FailLog_FilePath, 'wb') as f0:
				f0.writelines("=============" + time.strftime('[%Y-%m-%d %H:%M:%S] ', time.localtime(
					time.time())) + " start to record" + "\r\n\r\n")
		
		# 直接写进去，没有的话就新建咯！
		with open(FailLog_FilePath, "ab") as f:
			f.writelines(time.strftime('[%Y-%m-%d %H:%M:%S] ', time.localtime(time.time())) + "\r\n\r\n" + data + "\r\n\r\n")
	
	def record_memtesterLOG(self, data):
		today_str = time.strftime('%Y%m%d', time.localtime(time.time()))
		logfile = os.path.join(self.FailLog_folderPath, "CH"+str(self.channel)+self.port+"-"+today_str + ".txt")
		with open(logfile, "ab") as f:
			f.writelines(time.strftime('[%Y-%m-%d %H:%M:%S] ', time.localtime(time.time())) + "\r\n" + data + "\r\n")
			
	#########################################################
	# 测试函数：
	#  功能测试pattern。
	#########################################################
	def TestItem_AutoTesting_caller(self):
		# 为什么把检查串口放到这里？
		# 因为：第一我的操作步骤里面有sleep操作，因此放到按键回调函数这里会使得界面一卡一卡的；
		# 其次，check_serial_open里面的tkMessageBox函数是不能在线程里面执行的，因此从线程里面提出来，
		# 虽然破坏了一定的简洁性，但是效果还是很不错的嘛！
		if self.check_before_test():
			pass
		else:
			return False
		
		self.start_thread_target(self.TestItem_AutoTesting, "Auto Testting.")
	def TestItem_AutoTesting(self):
		print("start to run AutoTesting...\r\n")
		self.TestStep = 0
		# 这个总的按钮是不闪的
		# ["TestResult", "InitTime", "MainsceenCurrVDD12", "MainsceenCurrVDD18", "SleepCurrVDD12", "SleepCurrVDD18", "RunappTime" ]
		self.TestData_line = ["", "", "", "", "", "", "", ""]

		# step0: record timestamp
		self.TestData_line[1] = time.strftime('[%m/%d %H:%M]', time.localtime(time.time()))
		
		# step1: init test
		init_time_str = self.TestItem_Init()
		if init_time_str is not False:
			self.TestData_line[2] = init_time_str
		# print TestData_line
		else:
			# 表示测试异常了
			self.STOP = True
			
		if self.checkStop_Poweroff():
			# 异常了，上面这个函数就把数据保存了，并且还帮你关机了，停电了，真贴心！
			# 同时还要告诉主线程，你测试异常了哈！
			self.signal_ser.emit({"fail_item": ["Init_T"]})
			return False
		self.TestStep = 1
		self.signal_ser.emit(
			{"test_step": 1, "Init_T": self.TestData_line[2]})
		
		# step2: mainscreen current test
		mainscreen_curr_str = self.TestItem_mainscreen()
		if mainscreen_curr_str[0] is not False:
			self.TestData_line[3], self.TestData_line[4] = mainscreen_curr_str
		else:
			# 表示测试异常了
			self.STOP = True
		
		
		if self.checkStop_Poweroff():
			# 异常了，上面这个函数就把数据保存了，并且还帮你关机了，停电了，真贴心！
			# 同时还要告诉主线程，你测试异常了哈！
			self.signal_ser.emit({"fail_item": ["MCur_VDD12", "MCur_VDD18"]})
			return False
		self.TestStep = 2
		self.signal_ser.emit(
			{"test_step": 2, "MCur_VDD12": self.TestData_line[3], "MCur_VDD18": self.TestData_line[4]})
		
		
		# step3: sleep current test
		sleepcurrent_str = self.TestItem_SleepTest()
		if sleepcurrent_str[0] is not False:
			self.TestData_line[5], self.TestData_line[6] = sleepcurrent_str
		else:
			# 表示测试异常了
			self.STOP = True
		
		
		if self.checkStop_Poweroff():
			# 异常了，上面这个函数就把数据保存了，并且还帮你关机了，停电了，真贴心！
			# 同时还要告诉主线程，你测试异常了哈！
			self.signal_ser.emit({"fail_item": ["SCur_VDD12", "SCur_VDD18"]})
			return False
		self.TestStep = 3
		self.signal_ser.emit(
			{"test_step": 3, "SCur_VDD12": self.TestData_line[5], "SCur_VDD18": self.TestData_line[6]})
		
		# step4: runapp test
		runapp_time_str = self.TestItem_RunTest()
		if runapp_time_str is not False:
			self.TestData_line[7] = runapp_time_str
		else:
			# 表示测试异常了
			self.STOP = True
		
		
		if self.checkStop_Poweroff():
			# 异常了，上面这个函数就把数据保存了，并且还帮你关机了，停电了，真贴心！
			# 同时还要告诉主线程，你测试异常了哈！
			self.signal_ser.emit({"fail_item": ["MEM_T"]})
			return False
		self.TestStep = 4
		self.signal_ser.emit({"test_step": 4, "MEM_T": self.TestData_line[7]})
		
		
		for i in self.TestData_line:
			print i
		# step5: check Item outcome again
		for i in range(len(self.TestData_line)):
			if i == 0:
				pass
			else:
				if self.TestData_line[i] == "":
					# fail
					self.STOP = True
					self.TestData_line[1] = "fail"
					self.record_TestData(self.TestData_line)
					self.TestItem_SysPoweroff()
					return False

		# step6: write test date to database
		self.TestData_line[1] = "pass"
		self.record_TestData(self.TestData_line)
		# step7: system down and power off
		self.TestItem_SysPoweroff()
		
		self.TestStep = 5
		self.signal_ser.emit({"test_step": 5, "SaveFILE": "PASS"})
		return True
	
	def TestItem_Init_caller(self):
		# 界面函数里面不能用延时，因此单独开一个线程来做有延时的操作；
		# 界面回调函数是在toplevel层运行的，因此只要有延时就会使得界面卡住；
		# 注意此时之前的测试项还是在跑的，但是我们直接跑初始化，即重启，了！但是被打断的线程还在继续，因此这里是有bug的，我暂时不加这个功能。
		# is serials open ?
		if self.check_before_test():
			pass
		else:
			return False
		self.start_thread_target(self.TestItem_Init, name="TestItem_Init_caller")
	def TestItem_Init(self):
		# change True(ready, only in the front of the test pattern.) to False(Testting...)
		self.STOP = False
		
		# record test time.
		self.Item_testtime = time.time()
		# 初始化：先断电再上电，并检测是否正常开机
		# print("$LPDDR3$: start to Init...\r\n")

		# power off
		# print("$LPDDR3$: start power off.\r\n")
		self.ser.write("poweroff" + "\n")
		time.sleep(1)
		
		# power on
		# print("$LPDDR3$: start power on.\r\n")
		self.ser.write("poweron" + "\n")
		
		timeout = 40
		StartTime = time.time()
		EndTime = time.time()
		while EndTime - StartTime < timeout:
			# 插的哨子
			if self.STOP:
				return False
				
			if self.receive_data_zxl == '':
				time.sleep(0.4)
			elif ("psci: CPU1 killed" in self.receive_data_zxl) or ("Starting kernel" in self.receive_data_zxl):
				break
			else:
				# 这里是有安全隐患的，假如在上面判断期间就有数据进来，那么我可能是检测不到的；
				with self._Data_Lock:
					self.receive_data_zxl = ''
					
			# print("waitting for system on.\r\n")
			EndTime = time.time()
		
		if EndTime - StartTime + 0.5 < timeout:
			print("$LPDDR3$: system booting success.\r\n")
		else:
			print("$LPDDR3$: system booting fail.\r\n")
			return False
		# init state, send "su" to H6
		StartTime = time.time()
		EndTime = time.time()
		while EndTime - StartTime < timeout:
			# 在耗时的部分加入全局停止检测
			if self.STOP:
				return False
			
			self.ser.write("TestItem9" + "\n")
			
			#轮训速度太快了
			if self.receive_data_zxl == '':
				time.sleep(0.2)
			elif ("petrel-p1:/ #" in self.receive_data_zxl) or ("root@petrel-p1:/ #" in self.receive_data_zxl):
				break
			else:
				with self._Data_Lock:
					self.receive_data_zxl = ''
			EndTime = time.time()
			
		if EndTime - StartTime + 0.5 < timeout:
			print("$LPDDR3$: system on success.\r\n")
		else:
			print("$LPDDR3$: system on fail.\r\n")
			return False
		
		if self.check_luncher():
			print("$LPDDR3$: Init test PASS.\r\n")
			self.Item_testtime = time.time() - self.Item_testtime
			return str(float("%.1f" % self.Item_testtime))
		else:
			print("$LPDDR3$: check luncher fail.\r\n")
			return False
	
	def TestItem_mainscreen_caller(self):
		# is serials open ?
		if self.check_before_test():
			pass
		else:
			return False
		
		self.start_thread_target(self.TestItem_mainscreen, name="TestItem_mainscrren_caller")
	def TestItem_mainscreen(self):
		# 主界面下的电流测试
		# record test time.
		self.Item_testtime = time.time()
		
		print("$LPDDR3$: start to mainscreen...\r\n")

		# flush serial buffer
		with self._Data_Lock:
			self.receive_data_zxl = ""
			
		# 是使得H6在开机状态下回到主界面；
		# 测试主界面下的电流值
		# print("$LPDDR3$: start to back to mainscreen.\r\n")
		# self.ser.write("TestItem6" + "\n")
		#
		# StartTime = time.time()
		# EndTime = time.time()
		# while EndTime - StartTime < self.TIME_OUT:
		# 	if self.check_luncher():
		# 		break
		# 	else:
		# 		pass
		# 	# print("waitting for system on.\r\n")
		# 	EndTime = time.time()
		#
		# if EndTime - StartTime + 0.5 < self.TIME_OUT:
		# 	print("$LPDDR3$: back to mainscreen success.\r\n")
		# else:
		# 	print("$LPDDR3$: back to mainscreen fail.\r\n")
		# 	# stop falsh button
		# 	self.stop_button_flash()
		# 	time.sleep(0.3)
		# 	self.serial_frm.frm_right_TestItem_btn_mainscreen["bg"] = "#DC143C"  # deep red
		# 	return False
		
		
		
		
		# VDD1.8 current test @running mode ===> TestItem4
		current_VDD18_str = self.get_current(channel="TestItem4")
		
		if type(current_VDD18_str) is int and current_VDD18_str < 0:
			print("cant get current value, please check error.\r\n")
			time.sleep(0.3)
			return False, False
		
		# flush serial buffer
		with self._Data_Lock:
			self.receive_data_zxl = ""
		
		##########################################################################
		# VDD1.2V running mode
		currentVDD12_str = self.get_current(channel="TestItem2")
		
		if type(currentVDD12_str) is int and currentVDD12_str < 0:
			print("cant get current value, please check error.\r\n")
			return False, False
		else:
			print("$LPDDR3$: Init test PASS.\r\n")
			self.Item_testtime = time.time() - self.Item_testtime
			return currentVDD12_str, current_VDD18_str
	
	def TestItem_SleepTest_caller(self):
		# is serials open ?
		if self.check_before_test():
			pass
		else:
			return False
		
		self.start_thread_target(self.TestItem_SleepTest, name="TestItem_SleepTest_caller")
	def TestItem_SleepTest(self):
		
		# 休眠的电流测试
		# record test time.
		self.Item_testtime = time.time()
		print("$LPDDR3$: start  sleeptest...\r\n")
		# do slep and check
		# 有时一次是抓不到的，我把一次检测的时间由原来的15s减为5s，这里外面再多检查几次，从而增强鲁棒性
		sleep_state = False
		for i in range(3):
			if self.check_sleep_H6() is True:
				sleep_state = True
				break
			else:
				continue
		if sleep_state is False:
			self.Item_testtime = time.time() - self.Item_testtime
			return False, False
		
		time.sleep(2)
		
		# flush
		with self._Data_Lock:
			self.receive_data_zxl = ""
			
		# VDD1.8V running mode
		current_VDD18_str = self.get_current(channel="TestItem3")
		# print("current_VDD18_str=", current_VDD18_str)
		if type(current_VDD18_str) is int and current_VDD18_str < 0:
			# 整醒~
			self.check_wakeup_H6()
			self.Item_testtime = time.time() - self.Item_testtime
			return False, False  # -10 means fail
		
		# flush handly
		# flush buffer
		with self._Data_Lock:
			self.receive_data_zxl = ""
		time.sleep(2)
		
		# VDD1.2V running mode
		currentVDD12_str = self.get_current(channel="TestItem1")
		
		# 先保证能起来
		if self.check_wakeup_H6() is False:
			self.Item_testtime = time.time() - self.Item_testtime
			return False, False
		
		if type(currentVDD12_str) is int and currentVDD12_str < 0:
			print("cant get current value, please check error.\r\n")
			self.Item_testtime = time.time() - self.Item_testtime
			return False, False
		else:
			print("$LPDDR3$: sleep current test PASS.\r\n")
			self.Item_testtime = time.time() - self.Item_testtime
			return currentVDD12_str, current_VDD18_str
	
	def TestItem_RunTest_caller(self):
		# 界面函数里面不能用延时，因此单独开一个线程来做有延时的操作；
		# 界面回调函数是在toplevel层运行的，因此只要有延时就会使得界面卡住；
		
		# is serials open ?
		if self.check_before_test():
			pass
		else:
			return False
		
		self.start_thread_target(self.TestItem_RunTest, name="TestItem_RunTest_caller")
	def TestItem_RunTest(self):
		
		# record test time.
		self.Item_testtime = time.time()
		
		# 0 初始化：先断电再上电，并检测是否正常开机
		print("$LPDDR3$: start to RunTest...\r\n")
		
		# 3 发送指令并检测
		# 3.1 for sure: get root authority;
		self.ser.write("TestItem9" + "\n")
		
		time.sleep(0.1)
		self.ser.write("TestItem0#echo 0 >/proc/sysrq-trigger\r\n")
		
		# 3.2 run memtester
		# Mode：blocked
		# self.start_thread_target(self.run_memtester, name="TestItem_run_memtester_caller")
		time.sleep(0.1)
		# just send am instryction instead.

		if self.current_system == "Android7.x":
			self.ser.write(
				"TestItem0#am start -n com.softwinner.TvdVideo/.TvdVideoActivity -d /sdcard/Movies/4K-super_car2.mp4\r\n")
		elif self.current_system == "Android4.4":
			self.ser.write("TestItem0#am start -n org.cocos2dx.FishingJoy2/.FishingJoy2\r\n")
			time.sleep(10)
			self.ser.write("TestItem0#input tap 640 700\r\n")
			time.sleep(2)
			self.ser.write("TestItem0#input tap 640 700\r\n")
		else:
			return False
		
		time.sleep(3)
		
		self.run_memtester(size="128M", circle="1000")
		# 191.8s
		
		
		# 3.3 start uiautomator and check
		# print("$LPDDR3$: start to run Uiautomator.\r\n")
		# key_string = "cpufreq max to 1800000 min to 816000"
		
		# run uiautomator success
		# if self.writeCMD_check(cmd="TestItem7", check_string=key_string, timeout=30):
		# 	# 6s检测到
		# 	print("runapp startup time:%ds" % (time.time() - self.Item_testtime))
		# else:
		# 	# 由于系统压力很大，这个不一定检测的到
		# 	# self.stop_button_flash()
		# 	# self.serial_frm.frm_right_TestItem_btn_RunTest["bg"] = "#DC143C"  # deep red
		# 	print("$LPDDR3$: run test app fail.\r\n")
		
		
		
		# during test: check everithing ok?
		#
		# 在memtester和视频播放起来后，是可以让他一直播放的，
		# 我们要做的是检测其中memtester是否会报错，以及系统是否卡死
		#########################################
		test_time = 200
		start_time = time.time()
		systemdown_starttime = time.time()
		test_status = ""
		# print start_time,systemdown_starttime
		############## test block########
		# while not self.STOP:
		# 	if self.receive_data_zxl:
		# 		print self.receive_data_zxl
		# 		with self._Data_Lock:
		# 			self.receive_data_zxl = ''
		# 	else:
		# 		time.sleep(0.1)
		# return False
		############## test block########
		
		# flush
		
		with self._Data_Lock:
			self.receive_data_zxl = ''
			
		while time.time() - start_time < test_time:
			if self.STOP == True:
				return False
			if self.receive_data_zxl == "":
				if time.time() - systemdown_starttime > 30:
					print time.time() - systemdown_starttime
					# 系统死机
					test_status = "systemdown"
					break
				else:
					time.sleep(0.1)
					continue
			else:
				if "FAILURE:" in self.receive_data_zxl:
					self.record_FailLog(self.receive_data_zxl)
					# 这里可能会有问题，公共资源我强制占用可能会导致界面那显示不出来
					# 这里想解决的问题是：假如我写完之后不清空，那么很有可能就是重复写进log文件了，存在的问题是清空了就不能在界面显示了
					test_status = "mem_failure"
					break
			
				#这里要做个log存储的函数；
				
				with self._Data_Lock:
					self.receive_data_zxl = ""
				
				systemdown_starttime = time.time()
		
		if (test_status == "systemdown") or (test_status == "mem_failure"):
			print("$LPDDR3$: run test app fail@"+test_status+".\r\n")
			return False
		else:
			self.Item_testtime = time.time() - self.Item_testtime
			return str(float("%.1f" % self.Item_testtime))
		
		# #一定得等4K视频播放完，否则会延迟执行
		# #back to mainscreen
		# self.ser.write("TestItem6" + "\n")
		# #wait to back to mainscreen:
		# # 因为播放4K视频加跑memtester会产生很大压力，从而通过串口发送的指令很可能无法马上被检测到并执行，因此等一会吧！
		#
		# if self.check_luncher():
		# 	self.stop_button_flash()
		# 	self.serial_frm.frm_right_TestItem_btn_RunTest["bg"] = "#006400"  # deep green
		# 	print("$LPDDR3$: Init test PASS.\r\n")
		# 	self.Item_testtime = time.time() - self.Item_testtime
		# 	self.serial_frm.frm_right_TestItem_btn_RunTest["text"] = "Runapp\n Time={}s".format(float("%.1f" % self.Item_testtime))
		# 	return str(float("%.1f" % self.Item_testtime))
		# else:
		# 	self.stop_button_flash()
		# 	self.serial_frm.frm_right_TestItem_btn_RunTest["bg"] = "#DC143C"  # deep red
		# 	self.serial_frm.frm_right_TestItem_btn_RunTest["text"] = "Runapp+mem\n Fail!!!"
		# 	print("$LPDDR3$: run test app fail.\r\n")
		# 	return False
	
	def TestItem_SysPoweroff_caller(self):
		# is serials open ? NO!!!最高权限
		# if self.check_before_test():
		# 	pass
		# else:
		# 	return False
		self.start_thread_target(self.TestItem_SysPoweroff, name="TestItem_SysPoweroff_caller")
	def TestItem_SysPoweroff(self):
		# 初始化界面
		# 全局停止标志
		self.STOP = True
		self.ser.write("TestItem0#reboot -p\r\n")
		time.sleep(2)
		self.ser.write("poweroff\r\n")

class Ui(QtGui.QMainWindow, usb4site.Ui_MainWindow):  #
	# 注意上面继承这里，整了我半天，按照网上的代码是继承自QWidget，但是我的qt designer是新建的一个MainWindow啊！所以改一下就好了！。
	def __init__(self, parent=None):
		super(Ui, self).__init__(parent=parent)
		self.setupUi(self)
		self.system = "Android4.4"
		###########cfg##########
		self.LogPath = ""
	
		###########serial##########
		self.serial1 = ''
		self.serial2 = ''
		self.serial3 = ''
		self.serial4 = ''
		self.SerialPort1 = ''
		self.SerialPort2 = ''
		self.SerialPort3 = ''
		self.SerialPort4 = ''
		self.TestItem = ["Init_T", "MCur_VDD12", "MCur_VDD18","SCur_VDD12","SCur_VDD18","MEM_T", "SaveFILE"]
		self.temp_serial = list()
		self.AutoDetect_SerialDevices()
		#自动更新串口至combox里面
		# temp_thread = threading.Thread(target=self.deamon_flushCOMlist,
		#                                args=(self.comboBox, self.comboBox_2,self.comboBox_3,self.comboBox_4,))
		# temp_thread.setDaemon(True)
		# temp_thread.start()
	###################################################################
	###################Function Support Part###########################
	###################################################################
	# find serial uart (period = 1s)
	
	#直接继承自QtGui.QWidget，所以我这里直接重载就好了
	def keyPressEvent(self, event):
		key = event.key()
		# 按下D
		if key == QtCore.Qt.Key_1:
			self.serial1_startTest()
		elif key == QtCore.Qt.Key_2 and self.SerialPort2 != '':
			self.serial2_startTest()
		elif key == QtCore.Qt.Key_3 and self.SerialPort3 != '':
			self.serial3_startTest()
		elif key == QtCore.Qt.Key_4 and self.SerialPort4 != '':
			self.serial4_startTest()
		# 按ESC键，则退出程序
		elif key == QtCore.Qt.Key_Escape:
			sys.exit()
		else:
			pass
	
	def AutoDetect_SerialDevices(self):
		'''
        线程检测连接设备的状态
        '''
		self.find_all_serial_devices()

		temp_thread = threading.Timer(0.1, self.AutoDetect_SerialDevices)
		temp_thread.setDaemon(True)
		temp_thread.start()
	def find_all_serial_devices(self):
		'''
        检查串口设备
        '''
		try:
			if platform.system() == "Windows":
				self.temp_serial = list()
				for com in list(list_ports.comports()):
					try:
						strCom = com[0].encode("utf-8") #+ ": " + com[1][:6].encode("utf-8")
					except:
						strCom = com[0] #+ ": " + com[1][:6].decode("gbk").encode("utf-8")
					self.temp_serial.append(strCom)
					
			elif platform.system() == "Linux":
				self.temp_serial = list()
				self.temp_serial = self.find_usb_tty()
		except Exception as e:
			logging.error(e)
	def find_usb_tty(self, vendor_id=None, product_id=None):
				'''
				查找Linux下的串口设备
				'''
				tty_devs = list()
				for dn in glob.glob('/sys/bus/usb/devices/*'):
					try:
						vid = int(open(os.path.join(dn, "idVendor")).read().strip(), 16)
						pid = int(open(os.path.join(dn, "idProduct")).read().strip(), 16)
						if ((vendor_id is None) or (vid == vendor_id)) and (
							(product_id is None) or (pid == product_id)):
							dns = glob.glob(os.path.join(
								dn, os.path.basename(dn) + "*"))
							for sdn in dns:
								for fn in glob.glob(os.path.join(sdn, "*")):
									if re.search(r"\/ttyUSB[0-9]+$", fn):
										tty_devs.append(os.path.join(
											"/dev", os.path.basename(fn)))
					except Exception as ex:
						pass
				return tty_devs
	
	###################################################################
	###################Function Part###################################
	###################################################################
	def ReadCfg_FreshCombox(self):
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file',
		                                          '/home')
		with open(fname, 'r') as f:
			Cfgs = f.readlines()
			for line in Cfgs:
				if "Datalog" in line:
					#别忘了用strip来去掉头尾换行符空白符呀！
					self.LogPath = line.split('=')[1].strip()
	
	def init_table(self, table):
		table.clearContents()
		for item in self.TestItem:
			newItem = QTableWidgetItem(item)
			#items 是一个list，index方法是从0开始计数的。
			table.setItem(self.TestItem.index(item), 0, newItem)
			
	def deamon_flushCOMlist(self, *comboxs):
		
		time.sleep(1)
		COMList = []
		while True:
			# 串口连接的个数没变，但是串口号也没变动了于是一切正常，我就休息一会。
			if len(self.temp_serial) == len(COMList) and len(list(set(self.temp_serial).difference(set(COMList)))) == 0:
				time.sleep(1)
			#明显有串口线插拔,或者串口号变动了！
			else:
				COMList = self.temp_serial
				for combox in comboxs:
					# print combox
					combox.clear()
					combox.addItems(COMList)


	def serial1_connect(self):
		#创建信号槽的时候，信号选择highlight，这样子就是只要点击combox就会触发；
		# 而你想点击commbox里面的串口号啥的，这样子才触发的话，你得选择activate信号；
		#self.comboBox.setItemText(0, "zxl")#只有存在的才行，比如combox里面就一个元素，那么我位置参数写2那就不对了，系统会没反应的咯。
		#用highlight的方式会连续触发，采用activate的方式要点击里面的内容才会触发这里，
		port = self.comboBox.currentText()
		
		if port == "Refresh":
			self.comboBox.clear()
			self.comboBox.addItems(["Refresh"]+self.temp_serial)
			#close serial connected.
			if self.serial1:
				self.serial1.STOP = True

		else:
			# 这里是处理你在下拉表里面随便乱点的情况；
			# first time come in
			if self.SerialPort1 == '':
				self.SerialPort1 = port
				self.serial1 = serial_part(self.SerialPort1, channel=1)
				# 绑定信号槽
				self.serial1.signal_ser.connect(self.Ser1ShowOutcome)
				print port + " connect ok!!!"
			elif self.SerialPort1 == port:
				pass
			elif self.SerialPort1 != port:
				# close the old test process.
				self.serial1.STOP= True
				time.sleep(0.1)
				# close the old serial
				self.serial1.Ser_close()
				#open the new serial
				self.serial1 = serial_part(port, channel=1)
				# 绑定信号槽
				self.serial1.signal_ser.connect(self.Ser1ShowOutcome)
				# update the
				self.SerialPort1 = port
				print port + " connect ok!!!"

	def serial1_startTest(self):
		# is testting...
		# self.tableWidget.insertRow(self.tableWidget.rowCount())
		self.init_table(self.tableWidget)
		self.serial1.change_curSystem(self.system)
		if self.serial1.STOP == False:
			#强行停止
			self.serial1.STOP = True
			self.pushButton_2.setText(u'已停止测试')
		else:
			self.pushButton_2.setText(u'已开始测试')
			self.progressBar_1.setValue(0)
			# 本来这个地方调用测试函数后，该测试函数开启了一个线程进行测试，紧接着该函数退出，并且这个原始函数serial1_startTest也退出了，
			# 本来的话附线程都退出了，那么子线程势必会退出的，由于这里是UI界面，所以父线程是不会退出的，因此，我们这里的子线程必须特别注意，
			#要留主动退出的窗口，不然就是一个后台的死循环线程啊！
			
			#UI里面尽量不要做逻辑控制，而只做显示，逻辑（耗时的，如轮训等待）全部放到线程里面去做，子线程发信号给主线成的
			#槽函数就好了，槽用来做界面显示控制的。
			self.serial1.TestItem_AutoTesting_caller()
			
	def Ser1ShowOutcome(self, value_dict):
		# 接收一个字典,直接送去显示
		for key, value in value_dict.items():
			if key == "test_step":
					#进度条self.progressBar.setValue(int(100.0 * (self.TestStep / 5.0)))
					self.progressBar_1.setValue(int(100.0 * (value / 5.0)))
			elif key == "fail_item":
				for failitem in value:
					item = self.tableWidget.findItems(failitem, QtCore.Qt.MatchExactly)
					# 获取其行号
					fail_row = item[0].row()
					fail_item = QTableWidgetItem("FAIL")
					fail_item.setBackgroundColor(Qt.red)
					self.tableWidget.setItem(fail_row, 1, fail_item)
			else:
				#贴结果
				# 遍历表查找对应的item
				item = self.tableWidget.findItems(key, QtCore.Qt.MatchExactly)
				# 获取其行号
				row = item[0].row()
				# 滚轮定位过去，搞定
				# self.tableWidget.verticalScrollBar().setSliderPosition(row)
				# print key, value
				newItem = QTableWidgetItem(str(value))
				newItem.setBackgroundColor(Qt.green)
				self.tableWidget.setItem(row, 1, newItem)
				
	
	def serial2_connect(self):
		# 创建信号槽的时候，信号选择highlight，这样子就是只要点击combox就会触发；
		# 而你想点击commbox里面的串口号啥的，这样子才触发的话，你得选择activate信号；
		# self.comboBox.setItemText(0, "zxl")#只有存在的才行，比如combox里面就一个元素，那么我位置参数写2那就不对了，系统会没反应的咯。
		# 用highlight的方式会连续触发，采用activate的方式要点击里面的内容才会触发这里，
		port = self.comboBox_2.currentText()
		if port == "Refresh":
			self.comboBox_2.clear()
			self.comboBox_2.addItems(["Refresh"] + self.temp_serial)
			# close serial connected.
			if self.serial1:
				self.serial1.STOP = True
		else:
			# 这里是处理你在下拉表里面随便乱点的情况；
			# first time come in
			if self.SerialPort2 == '':
				self.SerialPort2 = port
				self.serial2 = serial_part(self.SerialPort2, channel=2)
				# 绑定信号槽
				self.serial2.signal_ser.connect(self.Ser2ShowOutcome)
				print port + " connect ok!!!"
			elif self.SerialPort2 == port:
				pass
			elif self.SerialPort2 != port:
				# close the old test process.
				self.serial2.STOP = True
				time.sleep(0.1)
				# close the old serial
				self.serial2.Ser_close()
				# open the new serial
				self.serial2 = serial_part(port, channel=2)
				# 绑定信号槽
				self.serial2.signal_ser.connect(self.Ser2ShowOutcome)
				# update the
				self.SerialPort2 = port
				print port + " connect ok!!!"
	
	def serial2_startTest(self):
		# is testting...
		# self.tableWidget.insertRow(self.tableWidget.rowCount())
		self.init_table(self.tableWidget_2)
		self.serial2.change_curSystem(self.system)
		if self.serial2.STOP == False:
			# 强行停止
			self.serial2.STOP = True
			self.pushButton_3.setText(u'已停止测试')
		else:
			self.pushButton_3.setText(u'已开始测试')
			self.progressBar_2.setValue(0)
			# 本来这个地方调用测试函数后，该测试函数开启了一个线程进行测试，紧接着该函数退出，并且这个原始函数serial1_startTest也退出了，
			# 本来的话附线程都退出了，那么子线程势必会退出的，由于这里是UI界面，所以父线程是不会退出的，因此，我们这里的子线程必须特别注意，
			# 要留主动退出的窗口，不然就是一个后台的死循环线程啊！
			
			# UI里面尽量不要做逻辑控制，而只做显示，逻辑（耗时的，如轮训等待）全部放到线程里面去做，子线程发信号给主线成的
			# 槽函数就好了，槽用来做界面显示控制的。
			self.serial2.TestItem_AutoTesting_caller()
	
	def Ser2ShowOutcome(self, value_dict):
		# 接收一个字典,直接送去显示
		for key, value in value_dict.items():
			if key == "test_step":
				if value > 0:
					# 进度条self.progressBar.setValue(int(100.0 * (self.TestStep / 5.0)))
					self.progressBar_2.setValue(int(100.0 * (value / 5.0)))
			elif key == "fail_item":
				for failitem in value:
					item = self.tableWidget_2.findItems(failitem, QtCore.Qt.MatchExactly)
					# 获取其行号
					fail_row = item[0].row()
					fail_item = QTableWidgetItem("FAIL")
					fail_item.setBackgroundColor(Qt.red)
					self.tableWidget_2.setItem(fail_row, 1, fail_item)
			else:
				# 贴结果
				# 遍历表查找对应的item
				item = self.tableWidget_2.findItems(key, QtCore.Qt.MatchExactly)
				# 获取其行号
				row = item[0].row()
				# 滚轮定位过去，搞定
				# self.tableWidget.verticalScrollBar().setSliderPosition(row)
				# print key, value
				newItem = QTableWidgetItem(str(value))
				newItem.setBackgroundColor(Qt.green)
				self.tableWidget_2.setItem(row, 1, newItem)
				
				
	def serial3_connect(self):
		# 创建信号槽的时候，信号选择highlight，这样子就是只要点击combox就会触发；
		# 而你想点击commbox里面的串口号啥的，这样子才触发的话，你得选择activate信号；
		# self.comboBox.setItemText(0, "zxl")#只有存在的才行，比如combox里面就一个元素，那么我位置参数写2那就不对了，系统会没反应的咯。
		# 用highlight的方式会连续触发，采用activate的方式要点击里面的内容才会触发这里，
		port = self.comboBox_3.currentText()
		if port == "Refresh":
			self.comboBox_3.clear()
			self.comboBox_3.addItems(["Refresh"] + self.temp_serial)
			# close serial connected.
			if self.serial1:
				self.serial1.STOP = True
		else:
			# 这里是处理你在下拉表里面随便乱点的情况；
			# first time come in
			if self.SerialPort3 == '':
				self.SerialPort3 = port
				self.serial3 = serial_part(self.SerialPort3, channel=3)
				# 绑定信号槽
				self.serial3.signal_ser.connect(self.Ser3ShowOutcome)
				print port + " connect ok!!!"
			elif self.SerialPort3 == port:
				pass
			elif self.SerialPort3 != port:
				# close the old test process.
				self.serial3.STOP = True
				time.sleep(0.1)
				# close the old serial
				self.serial3.Ser_close()
				# open the new serial
				self.serial3 = serial_part(port, channel=3)
				# 绑定信号槽
				self.serial3.signal_ser.connect(self.Ser3ShowOutcome)
				# update the
				self.SerialPort3 = port
				print port + " connect ok!!!"
	
	def serial3_startTest(self):
		# is testting...
		# self.tableWidget.insertRow(self.tableWidget.rowCount())
		self.init_table(self.tableWidget_3)
		self.serial3.change_curSystem(self.system)
		if self.serial3.STOP == False:
			# 强行停止
			self.serial3.STOP = True
			self.pushButton_4.setText(u'已停止测试')
		else:
			self.pushButton_4.setText(u'已开始测试')
			self.progressBar_3.setValue(0)
			# 本来这个地方调用测试函数后，该测试函数开启了一个线程进行测试，紧接着该函数退出，并且这个原始函数serial1_startTest也退出了，
			# 本来的话附线程都退出了，那么子线程势必会退出的，由于这里是UI界面，所以父线程是不会退出的，因此，我们这里的子线程必须特别注意，
			# 要留主动退出的窗口，不然就是一个后台的死循环线程啊！
			
			# UI里面尽量不要做逻辑控制，而只做显示，逻辑（耗时的，如轮训等待）全部放到线程里面去做，子线程发信号给主线成的
			# 槽函数就好了，槽用来做界面显示控制的。
			self.serial3.TestItem_AutoTesting_caller()
	
	def Ser3ShowOutcome(self, value_dict):
		# 接收一个字典,直接送去显示
		for key, value in value_dict.items():
			if key == "test_step":
				if value > 0:
					# 进度条self.progressBar.setValue(int(100.0 * (self.TestStep / 5.0)))
					self.progressBar_3.setValue(int(100.0 * (value / 5.0)))
			elif key == "fail_item":
				for failitem in value:
					item = self.tableWidget_3.findItems(failitem, QtCore.Qt.MatchExactly)
					# 获取其行号
					fail_row = item[0].row()
					fail_item = QTableWidgetItem("FAIL")
					fail_item.setBackgroundColor(Qt.red)
					self.tableWidget_3.setItem(fail_row, 1, fail_item)
			else:
				# 贴结果
				# 遍历表查找对应的item
				item = self.tableWidget_3.findItems(key, QtCore.Qt.MatchExactly)
				# 获取其行号
				row = item[0].row()
				# 滚轮定位过去，搞定
				# self.tableWidget.verticalScrollBar().setSliderPosition(row)
				# print key, value
				newItem = QTableWidgetItem(str(value))
				newItem.setBackgroundColor(Qt.green)
				self.tableWidget_3.setItem(row, 1, newItem)
	

	def serial4_connect(self):
		# 创建信号槽的时候，信号选择highlight，这样子就是只要点击combox就会触发；
		# 而你想点击commbox里面的串口号啥的，这样子才触发的话，你得选择activate信号；
		# self.comboBox.setItemText(0, "zxl")#只有存在的才行，比如combox里面就一个元素，那么我位置参数写2那就不对了，系统会没反应的咯。
		# 用highlight的方式会连续触发，采用activate的方式要点击里面的内容才会触发这里，
		port = self.comboBox_4.currentText()
		if port == "Refresh":
			self.comboBox_4.clear()
			self.comboBox_4.addItems(["Refresh"] + self.temp_serial)
			# close serial connected.
			if self.serial1:
				self.serial1.STOP = True
		else:
			# 这里是处理你在下拉表里面随便乱点的情况；
			# first time come in
			if self.SerialPort4 == '':
				self.SerialPort4 = port
				self.serial4 = serial_part(self.SerialPort4, channel=4)
				# 绑定信号槽
				self.serial4.signal_ser.connect(self.Ser4ShowOutcome)
				print port + " connect ok!!!"
			elif self.SerialPort4 == port:
				pass
			elif self.SerialPort4 != port:
				# close the old test process.
				self.serial4.STOP = True
				time.sleep(0.1)
				# close the old serial
				self.serial4.Ser_close()
				# open the new serial
				self.serial4 = serial_part(port, channel=4)
				# 绑定信号槽
				self.serial4.signal_ser.connect(self.Ser4ShowOutcome)
				# update the
				self.SerialPort4 = port
				print port + " connect ok!!!"
	
	def serial4_startTest(self):
		# is testting...
		# self.tableWidget.insertRow(self.tableWidget.rowCount())
		self.init_table(self.tableWidget_4)
		self.serial4.change_curSystem(self.system)
		if self.serial4.STOP == False:
			# 强行停止
			self.serial4.STOP = True
			self.pushButton_5.setText(u'已停止测试')
		else:
			self.pushButton_5.setText(u'已开始测试')
			self.progressBar_4.setValue(0)
			# 本来这个地方调用测试函数后，该测试函数开启了一个线程进行测试，紧接着该函数退出，并且这个原始函数serial1_startTest也退出了，
			# 本来的话附线程都退出了，那么子线程势必会退出的，由于这里是UI界面，所以父线程是不会退出的，因此，我们这里的子线程必须特别注意，
			# 要留主动退出的窗口，不然就是一个后台的死循环线程啊！
			
			# UI里面尽量不要做逻辑控制，而只做显示，逻辑（耗时的，如轮训等待）全部放到线程里面去做，子线程发信号给主线成的
			# 槽函数就好了，槽用来做界面显示控制的。
			self.serial4.TestItem_AutoTesting_caller()
	
	def Ser4ShowOutcome(self, value_dict):
		# 接收一个字典,直接送去显示
		for key, value in value_dict.items():
			if key == "test_step":
				if value > 0:
					# 进度条self.progressBar.setValue(int(100.0 * (self.TestStep / 5.0)))
					self.progressBar_4.setValue(int(100.0 * (value / 5.0)))
			elif key == "fail_item":
				for failitem in value:
					item = self.tableWidget_4.findItems(failitem, QtCore.Qt.MatchExactly)
					# 获取其行号
					fail_row = item[0].row()
					fail_item = QTableWidgetItem("FAIL")
					fail_item.setBackgroundColor(Qt.red)
					self.tableWidget_4.setItem(fail_row, 1, fail_item)
			else:
				# 贴结果
				# 遍历表查找对应的item
				item = self.tableWidget_4.findItems(key, QtCore.Qt.MatchExactly)
				# 获取其行号
				row = item[0].row()
				# 滚轮定位过去，搞定
				# self.tableWidget.verticalScrollBar().setSliderPosition(row)
				# print key, value
				newItem = QTableWidgetItem(str(value))
				newItem.setBackgroundColor(Qt.green)
				self.tableWidget_4.setItem(row, 1, newItem)
	
	def QA_SystemSelect(self):
		self.system = self.comboBox_6.currentText()
	
	def connnect_usb(self):
		pass

if __name__ == "__main__":
	# 给系统注册一下：我要在最小化时也显示图标。
	import ctypes
	myappid = 'mycompany.myproduct.subproduct.version'  # arbitrary string
	ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
	
	#加上软件图标
	app = QApplication(sys.argv)
	app_icon = QtGui.QIcon('sourcefile/app1.ico')#icons8-webhook-528.png
	app.setWindowIcon(app_icon)
	
	ui = Ui()
	ui.show()
	app.exec_()