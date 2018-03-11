# SerialTool
## discription
muti-channel Serial or USB Tool.

## 初衷
要学会使用pyqt，因此边学边做，同时也想摸索一下学习新东西新工具有没有更好的窍门。

额·····其实主要原因是任务来的。

这个工具平时是自己用的，刚写完第一版，很是粗糙，先放到git上来，慢慢优化代码，**力求做到代码简洁**！


![image](https://note.youdao.com/yws/public/resource/6fc50104df2bbc09d34c3fc42c337e0c/xmlnote/687E388221024567A80274502CC7AC07/6820)


##使用
### 背景
这是一个专用工具，用来进行DDR的QA验证的。

当前国内很多公司，包括华为，都是直接买的内存die，然后去封装厂做个封装，加个丝印，测一下就是产品卖出去啦！

所以成本的关键点就在测试了，测试的准不准？测试的时间多长？这些都是直接关系到成本关系到钱的啊！

测试内容就是针对DRR设计一些QA测试pattern，分两个部分，其一为安卓压力应用（比如memtester，4K 大码流视频等），其二为针对cell设计一些测试算法，最终通过安卓下的JNI来跑这些算法。

因此我们的验证系统就是分软硬件两部分，硬件板端来跑安卓系统，以及验证pattern，PC上位机负责控制以及数据的收集，通信接口是USB跟串口（嗯，可以很负责任的告诉你，目前（2018.3）国内大部分中小企业都是这么干的，中小的定义就是有没有买几百万美金一台的ATE设备）。

关于DDR cell的测试算法介绍以及关键研究点，我会在知乎里面写个专栏的，感兴趣的到时可以去看哈！


### 目的
写这篇的目的是分享系统架构，软件界面代码，不分享的是DDR cell的测试pattern，这部分属于公司机密。


### 使用方法
1. 第一步就是从下拉菜单选择你要打开的串口（点击refresh进行串口号刷新），选择对应的串口号时就自动创建了一个串口实例；
2. 第二步就是点击开始测试，这时上位机就会发送测试pattern到下面硬件板内进行测试啦！
