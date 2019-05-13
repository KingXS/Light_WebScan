import time
import socket
from gevent import monkey
monkey.patch_all()
import gevent
import gevent.pool
import sys
import getopt


def TCP_connect(ip,port):
    """模拟TCP连接"""
    TCP_sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    TCP_sock.settimeout(0.5)  #设置连接超时
    try:
        result = TCP_sock.connect_ex((ip,int(port)))
        if result == 0:
            print("[*]%s 端口 开启\t"%port)
        else:
            # print("[!]%s端口 关闭"%port)
            pass
        TCP_sock.close()
    except socket.error as e:
        print("[!]错误:",e)


def scan_web(argv):
    #获取命令行参数
    try:
        opts, args = getopt.getopt(argv,"hu:",["url="])
    except getopt.GetoptError:
      print('端口扫描.py -u <url>')
      sys.exit(2)

    for opt,arg in opts:
        if opt in ('-u','--url'):
            web = arg

    global web_addr

    """扫描目标网址"""
    web_addr = web
    if "http://" in web or "https://" in web:
        web = web[web.find('://')+3:]
        print(web)
        print("[*]正在分析网站服务器IP")
    try:
        server_ip = socket.gethostbyname(str(web))
        print("[*]服务器IP为%s"%server_ip)
        scan_port(server_ip)
    except Exception as e:
        print("[!]服务器IP获取失败")
        pass


def scan_port(ip):
    """扫描端口"""
    print("[*]开始扫描目标端口")
    start = time.time()
    g = gevent.pool.Pool(20) #设置线程数
    run_list = []
    for port in range(1,65535):
        run_list.append(g.spawn(TCP_connect,ip,port))
    gevent.joinall(run_list)
    end = time.time()
    print("[*]总耗时%s"%time.strftime("%H:%M:%S",time.gmtime(end-start)))


if __name__ == "__main__":
   scan_web(sys.argv[1:])
