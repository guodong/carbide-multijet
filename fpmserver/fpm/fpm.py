#!/usr/bin/python
import netifaces
import socket
import struct
import time

from python_arptable import ARPTABLE

import fpm_pb2 as fpm

ifaces = netifaces.interfaces()
if 'eth0' in ifaces:
    ifaces.remove('eth0')  # remove eth0 for easier handling


# fpm nexthop interface id to ovs port id, eg: 9 -> 0 means #9 is i0, i0 -> eth0, eth0 -> of port 1
def ifIdtoPortId(ifId):
    if ifId > 100:  # it's docker bridge
        return None

    for iface in ifaces:
        with open('/sys/class/net/' + iface + '/ifindex') as f:
            ifindex = f.read()
            if int(ifindex) == ifId:
                idx = iface[1:]
                if idx == 'o':
                    return None
                if idx == '1':
                    return 1
                if 'e1' in ifaces:
                    return 2 * (int(idx) - 3) - 1
                else:
                    return 2 * (int(idx) - 4) - 1
    return None


def getMacByIp(ip):
    for entry in ARPTABLE:
        if entry['IP address'] == ip:
            return entry['HW address']

    return None


def bytes2Ip(bts):
    for i in range(len(bts), 4):
        bts += '\0'

    return '.'.join("{:d}".format(ord(x)) for x in bts)


# table 1 is pvv, pvv table should be controlled by controller
# cmd = 'ovs-ofctl add-flow s table=0,priority=0,actions=resubmit\(,1\)'
# os.system(cmd)


class Fpm:
    def __init__(self):
        self.on_add_route = None

    def add_flow(self, dst, output):
        if dst == '10.0.0.0/24':
            actions = {'mod_dl_dst': '00:00:00:00:00:01', 'output': output}
        elif dst == '10.0.1.0/24':
            # dl_dst = getMacByIp('10.0.1.1')
            actions = {'mod_dl_dst': '00:00:00:00:00:02', 'output': output}
        else:
            actions = {'output': output}

        self.on_add_route({"eth_type": 2048, "ipv4_dst": (dst[:-3], '255.255.255.0')}, actions)  # TODO: rewrite mask

    def start(self):
        addr = ('127.0.0.1', 2620)
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(10)
        while True:
            conn, addr = s.accept()
            print("new conn\n")

            while True:
                data = conn.recv(4)
                d = bytearray(data)
                x, y, size = struct.unpack(">ccH", d)
                body = conn.recv(size - 4)
                m = fpm.Message()
                m.ParseFromString(body)
                if m.add_route:
                    dst = bytes2Ip(m.add_route.key.prefix.bytes) + '/' + str(m.add_route.key.prefix.length)
                    output = ifIdtoPortId(m.add_route.nexthops[0].if_id.index)
                    if output is not None:
                        self.add_flow(dst, str(output))
                        end = time.time()
                        with open('/tmp/result', 'a') as f:
                            f.write("%f\n" % end)
