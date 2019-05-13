fr = open('端口与漏洞.txt','r')
for line in fr:
    v = line.strip().split(':')
    if v[0] == '80':
        print(v[1])
        break
    else:
        continue