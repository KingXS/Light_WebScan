import os 

#文件的路径
path = "c:\报告输出"

#判断文件夹是否已经创建
ifexist = os.path.exists(path)

print(ifexist)

# 判断结果
if not ifexist:
    # 如果不存在则创建目录
    # 创建目录操作函数
    os.makedirs(path) 
 
    print(path+' 创建成功')
else:
    # 如果目录存在则不创建，并提示目录已存在
    print(path+' 目录已存在')