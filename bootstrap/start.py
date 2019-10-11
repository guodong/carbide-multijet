#!/usr/bin/python
import netifaces
import os

ifaces = netifaces.interfaces()

my_ifaces = []


for i in ifaces:
    if i[0] == 'i':
        my_ifaces.append(i)

for i in my_ifaces:
    idx = int(i[1:])
    cmd = 'ovs-ofctl add-flow s in_port=' + str(idx * 2 + 2) + ',actions=output:' + str(idx * 2 + 1)
    os.system(cmd)

    cmd = 'ovs-ofctl add-flow s ip,ip_proto=89,in_port=' + str(idx * 2 + 1) + ',actions=output:' + str(idx * 2 + 2)
    os.system(cmd)

    info = netifaces.ifaddresses(i)
    ip = info[2][0]['addr']

    cmd = 'ovs-ofctl add-flow s arp,arp_tpa=' + ip + ',actions=output:' + str(idx * 2 + 2)
    os.system(cmd)
    cmd = 'ovs-ofctl add-flow s ip,nw_dst=' + ip + ',actions=output:' + str(idx * 2 + 2)
    os.system(cmd)

cmd = 'ovs-ofctl add-flow s -OOpenFlow13 priority=0,action=goto_table:100'
os.system(cmd)
