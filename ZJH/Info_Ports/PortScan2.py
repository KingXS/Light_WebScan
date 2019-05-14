#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import socket
from gevent import monkey

monkey.patch_all()
import gevent
import gevent.pool
import sys
import getopt

port_service = {'21': 'ftp', '22': 'SSH', '23': 'Telnet', '80': 'web----Http.sys远程代码执行漏洞', '161': 'SNMP', '389': 'LDAP',
                '443': 'SSL心脏滴血以及一些web漏洞测试', '445': 'SMB', '512': 'Rexec', '513': 'Rexec', '514': 'Rexec',
                '873': 'Rsync未授权', '1025': 'NFS', '111': 'NFS', '1433': 'MSSQL', '1521': 'Oracle(iSqlPlus)',
                '2082': 'cpanel主机管理系统登陆', '2083': 'cpanel主机管理系统登陆', '2222': 'DA虚拟主机管理系统登陆（国外用较多）',
                '2601': 'zebra路由，默认密码zebra', '2604': 'zebra 路由，默认密码zebra', '3128': 'squid代理默认端口，如果没设置口令很可能就直接漫游内网了',
                '3306': 'MySQL', '3312': 'kangle主机管理系统登陆', '3311': 'kangle主机管理系统登陆', '3389': '远程桌面----RDP漏洞',
                '4440': 'rundeck', '5432': 'PostgreSQL', '5672': 'rabbitMQ（guest/guest）',
                '15672': 'rabbitMQ（guest/guest）', '5900': 'vnc--使用realVNCviewer连接被测ip', '5984': 'CouchDB',
                '6082': 'varnish,Varnish,HTTP,accelerator,CLI,未授权访问易导致网站被直接篡改或者作为代理进入内网', '6379': 'redis未授权',
                '7001': 'WebLogic默认弱口令，反序列', '7002': 'WebLogic默认弱口令，反序列', '7008': 'SSRF漏洞', '7778': 'Kloxo主机控制面板登录',
                '8080': 'JBOSS', '8089': 'JBOSS', '9090': 'JBOSS', '8083': 'Vestacp主机管理系统（国外用较多）', '8649': 'ganglia',
                '8808': 'web应用', '8888': 'amh/LuManager主机管理系统默认端口', '9200': 'elasticsearch', '9300': 'elasticsearch',
                '10000': 'Virtualmin/Webmin服务器虚拟主机管理系统', '11211': 'memcache未授权访问', '27017': 'Mongodb未授权访问',
                '27018': 'Mongodb未授权访问', '28017': 'mongodb统计页面', '50000': 'SAP命令执行', '50070': 'hadoop默认端口 未授权访问',
                '50030': 'hadoop默认端口未授权访问'}


def TCP_connect(ip, port):
    """模拟TCP连接"""
    TCP_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    TCP_sock.settimeout(0.5)  # 设置连接超时
    try:
        result = TCP_sock.connect_ex((ip, int(port)))
        if result == 0:
            if port in port_service.keys():
                print("[*]%s 端口 开启" % port, "服务是", port_service[port], "\t")
            else:
                print("[*]%s 端口 开启" % port, "服务需手动确认", "\t")
        else:
            # print("[!]%s端口 关闭"%port)
            pass
        TCP_sock.close()
    except socket.error as e:
        print("[!]错误:", e)


def scan_web(argv):
    # 获取命令行参数
    try:
        opts, args = getopt.getopt(argv, "hu:t:", ["url=", "types="])
    except getopt.GetoptError:
        print('端口扫描.py -u <url> -t <types>')
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-u', '--url'):
            web = arg
            # print(web)
        # 判断要进行何种扫描
        elif opt in ('-t', '--types'):
            types = arg
            # print(arg)

    global web_addr
    if types == 'f':
        """扫描目标网址"""
        web_addr = web
        if "http://" in web or "https://" in web:
            web = web[web.find('://') + 3:]
            # print(web)
            print("[*]正在分析网站服务器IP")
        try:
            server_ip = socket.gethostbyname(str(web))
            print("[*]服务器IP为%s" % server_ip)
            scan_port_full(server_ip)
        except Exception as e:
            print("[!]服务器IP获取失败")
            pass

    elif types == 'p':
        """扫描目标网址"""
        web_addr = web
        if "http://" in web or "https://" in web:
            web = web[web.find('://') + 3:]
            print(web)
            print("[*]正在分析网站服务器IP")
        try:
            server_ip = socket.gethostbyname(str(web))
            print("[*]服务器IP为%s" % server_ip)
            scan_port_part(server_ip)
        except Exception as e:
            print("[!]服务器IP获取失败")
            pass


def scan_port_part(ip):
    """扫描端口"""
    print("[*]开始扫描目标端口")
    start = time.time()
    g = gevent.pool.Pool(20)  # 设置线程数
    run_list = []
    port_list = ['21', '22', '23', '80', '161', '389', '443', '445', '512', '513', '514', '873', '1025', '111', '1433',
                 '1521', '2082', '2083', '2222', '2601', '2604', '3128', '3306', '3312', '3311', '3389', '4440', '5432',
                 '5672', '15672', '5900', '5984', '6082', '6379', '7001', '7002', '7008', '7778', '8080', '8080',
                 '8089', '9090', '8083', '8649', '8808', '8888', '9200', '9300', '10000', '11211', '27017', '27018',
                 '28017', '50000', '50070', '50030']
    for port in port_list:
        run_list.append(g.spawn(TCP_connect, ip, port))
    gevent.joinall(run_list)
    end = time.time()
    print("[*]总耗时%s" % time.strftime("%H:%M:%S", time.gmtime(end - start)))


def scan_port_full(ip):
    """扫描端口"""
    print("[*]开始扫描目标端口")
    start = time.time()
    g = gevent.pool.Pool(20)  # 设置线程数
    run_list = []
    for port in range(1, 65535):
        run_list.append(g.spawn(TCP_connect, ip, port))
    gevent.joinall(run_list)
    end = time.time()
    print("[*]总耗时%s" % time.strftime("%H:%M:%S", time.gmtime(end - start)))


if __name__ == "__main__":
    scan_web(sys.argv[1:])

