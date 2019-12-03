#!/usr/bin/python
import socket
import struct
import os
import netifaces
import fpm_pb2 as fpm
import time
import logging
import platform
import json
import requests
import fcntl, termios, array

logger = logging.getLogger(__name__)
logger.setLevel(level = logging.INFO)
handler = logging.FileHandler('/tmp/fpmlog')
if os.path.exists('/common'):
    handler = logging.FileHandler('/common/fpm-server-%s.log'%str(platform.node()))
else:
    handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

ifaces = netifaces.interfaces()
ifaces.remove('eth0')
ifaces.remove('lo')

if os.path.exists('/common'):
    history_file = '/common/fpm-history-%s.json'%str(platform.node())
else:
    history_file = '/tmp/fpm-history-%s.json'%str(platform.node())

history_list = []

global_flows = {}
global_new_flows = {}


def history_list_append_and_dump(obj):
    history_list.append(obj)
    with open(history_file, 'w') as f:
        json.dump(history_list, f, indent=2)


# fpm nexthop interface id to ovs port id, eg: 9 -> 2 means #9 is i0, ofport is e0 id = 1
def ifIdtoPortId(ifId):
    if ifId > 100:  # it's docker bridge
        return None

    for iface in ifaces:
        with open('/sys/class/net/' + iface + '/ifindex') as f:
            ifindex = f.read()
            if int(ifindex) == ifId:
                idx = iface[1:]
                return 2 * int(idx) + 1

    return None


def add_flow(dst, output):
    # if dst == '10.0.0.0/24':
    #     actions = 'mod_dl_dst:00:00:00:00:00:01' + ',output:' + output
    # elif dst == '10.0.1.0/24':
    #     actions = 'mod_dl_dst:00:00:00:00:00:02' + ',output:' + output
    # else:
    #     actions = 'output:' + output

    actions = 'output:' + output
    cmd = 'ovs-ofctl add-flow s table=100,ip,nw_dst=' + dst + ',actions=' + actions
    logger.info('add-flow dst=%s output=%s' % (str(dst), str(output)))
    os.system(cmd)
    global_new_flows[dst] = int(output)


def delete_flow(dst):
    logger.info('delete route %s' % dst)
    cmd = 'ovs-ofctl del-flow s table=100,ip,nw_dst=' + dst
    os.system(cmd)
    if dst in global_flows:
        global_new_flows[dst] = None


def request_update():
    diff_flows = {}
    for dst,output in global_new_flows.items():
        if dst not in global_flows or global_flows[dst]!=output:
            global_flows[dst] = output
            diff_flows[dst] = output
    if len(diff_flows)==0:
        logger.info('empty diff')
        return
    logger.info("request_update %s" % str(diff_flows))
    url = 'http://localhost:8080/install'
    # requests.post(url, json=diff_flows)
    history_list_append_and_dump({
        'type': 'request_update',
        'time': time.time(),
        'diff_flows': diff_flows
    })


def bytes2Ip(bts):
    for i in range(len(bts), 4):
        bts += '\0'

    return '.'.join('{:d}'.format(ord(x)) for x in bts)


# table 1 is pvv, pvv table should be controlled by controller
# cmd = 'ovs-ofctl add-flow s table=0,priority=0,actions=resubmit\(,1\)'
# os.system(cmd)

def main():

    addr = ('127.0.0.1', 2620)
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(10)
    flow_count = 1

    sock_size_buf = array.array('i', [0])

    while True:
        conn, addr = s.accept()
        logger.info('new conn')

        while True:
            try:
                data = conn.recv(4)
                d = bytearray(data)
                x, y, size = struct.unpack('>ccH', d)
                body = conn.recv(size - 4)
                if m.HasField('add_route') or m.HasField('delete_route'):
                    log_time()

                continue
                m = fpm.Message()
                m.ParseFromString(body)
                logger.info(m)
                if m.HasField('add_route'):
                    dst = bytes2Ip(m.add_route.key.prefix.bytes) + '/' + str(m.add_route.key.prefix.length)
                    output = ifIdtoPortId(m.add_route.nexthops[0].if_id.index)
                    if output is not None:
                        add_flow(dst, str(output))
                        logger.info(str(flow_count))
                        flow_count = flow_count + 1
                elif m.HasField('delete_route'):
                    dst = bytes2Ip(m.delete_route.key.prefix.bytes) + '/' + str(m.delete_route.key.prefix.length)
                    delete_flow(dst)
                else:
                    logger.info('UNKNOWN message type')

                # time.sleep(0.000001)
                # fcntl.ioctl(conn, termios.FIONREAD, sock_size_buf)
                # if sock_size_buf[0] == 0:
                #     logger.info('empty sock read')
                request_update()

            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception:
                logger.error('Faild', exc_info=True)


if __name__=='__main__':
    main()
