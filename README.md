# SerialTool
## discription
muti-channel Serial or USB Tool.

## 初衷
要学会使用pyqt，因此边学边做，同时也想摸索一下学习新东西新工具有没有更好的窍门。

额·····其实主要原因是任务来的。

这个工具平时是自己用的，刚写完第一版，很是粗糙，先放到git上来，慢慢优化代码，**力求做到代码简洁**！


![image](https://note.youdao.com/yws/public/resource/6fc50104df2bbc09d34c3fc42c337e0c/xmlnote/687E388221024567A80274502CC7AC07/6820)


##使用
### 工具背景
这是一个自动化测试工具，用来进行DDR的QA测试的。

测试内容就是针对DRR设计一些QA测试pattern，分两个部分，其一为安卓压力应用（比如memtester，4K 大码流视频等），其二为针对cell设计一些测试算法，最终通过安卓下的JNI来跑这些算法。

因此我们的验证系统就是分软硬件两部分，硬件板来跑安卓系统，以及验证pattern，PC上位机负责控制以及数据的收集，通信接口是USB跟串口。
### 使用方法
