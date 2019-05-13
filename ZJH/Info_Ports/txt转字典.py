fr = open('端口与漏洞.txt','r')
dic = {}
port_list = []
keys = [] #用来存储读取的顺序
for line in fr:
    v = line.strip().split(':')
    dic[v[0]] = v[1]
    port_list.append(v[0])
    keys.append(v[0])
fr.close()
print(port_list)
#写入文件代码 通过keys的顺序写入
fw = open('wdic.txt','w')
for k in keys:
    fw.write(k+':'+dic[k]+'\n')
 
fw.close()
#print(dic)


