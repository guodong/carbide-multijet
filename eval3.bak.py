#!/usr/bin/env python2

import os
import shutil
import signal
import sys
import time
import urllib
import urllib2
import re
import json
import argparse
from cmd import Cmd
import random
import threading

import docker
import grequests

import utils

from multijet.topo import Topology
from scripts.dumpdata import get_fpm_history, get_nodes

client = docker.from_env()


class Router:
    def __init__(self, id):
        self.id = id
        self.neighbors = []
        self.port_offset = 0


class RocketFuel(Cmd):
    intro = 'Welcome to the Multijet eval shell.   Type help or ? to list commands.\n'
    prompt = 'multijet> '

    def __init__(self, filename='1755.r0.cch'):
        Cmd.__init__(self)
        self.current = time.time()
        self.routers = {}
        self.links = []
        self.containers = {}
        self.filename = filename

        self.port_status = {}

        if filename.endswith(".json"):
            self._load_json_topology(filename)
        else:
            self._load_cch_topology(filename)

    def _load_cch_topology(self, filename):
        with open(filename, 'r') as f:
            for line in f:
                arr = line.split()
                self.routers[arr[0]] = Router(arr[0])

            f.seek(0)

            # generate links
            for line in f:
                arr = line.split('->')
                arr = arr[1].split('=')
                nei_str = arr[0].replace(' ', '')
                nei_ids = nei_str[1:-1].split('><')
                t = line.split()
                router = self.routers[t[0]]
                for nei in nei_ids:
                    router.neighbors.append(self.routers[nei])

            for r in self.routers.values():
                for n in r.neighbors:
                    exists = False
                    for l in self.links:
                        if n in l and r in l:
                            exists = True
                    if not exists:
                        self.links.append([r, n])

    def _load_json_topology(self, filename):
        with open(filename) as f:
            switches = json.load(f)

            for n in switches:
                n = str(n)
                self.routers[n] = Router(n)

            for n,v in switches.items():
                r = self.routers[str(n)]
                for en in v['neighbor']:
                    r.neighbors.append(self.routers[str(en)])

            for r in self.routers.values():
                for n in r.neighbors:
                    exists = False
                    for l in self.links:
                        if n in l and r in l:
                            exists = True
                    if not exists:
                        self.links.append([r, n])

    def attach(self):
        for r in self.routers.values():
            print 'get container ' + r.id
            container = client.containers.get(r.id)
            self.containers[r.id] = container

        self.topo = Topology()
        self.topo.load('configs/common/topo.json')

    def start(self):
        # generate ospf config file
        self._make_configs_directory()

        for r in self.routers.values():
            print 'starting ' + r.id
            container = client.containers.run('snlab/dovs-quagga', detach=True, name=r.id, privileged=True, tty=True,
                                              hostname=r.id,
                                              volumes={os.getcwd() + '/configs/' + r.id: {'bind': '/etc/quagga'},
                                                       os.getcwd() + '/bootstrap': {'bind': '/bootstrap'},
                                                       os.getcwd() + '/fpm': {'bind': '/fpm'},
                                                       os.getcwd() + '/multijet': {'bind': '/multijet'},
                                                       os.getcwd() + '/configs/common': {'bind': '/common'}},
                                              command='/bootstrap/start.sh')

        time.sleep(3)

        for r in self.routers.values():
            container = client.containers.get(r.id)
            self.containers[r.id] = container

        topo = Topology()
        topo.nodes = {r.id: {} for r in self.routers.values()}

        print 'setup links'
        i = 0
        j = 0
        for l in self.links:
            srcPid = client.containers.get(l[0].id).attrs['State']['Pid']
            dstPid = client.containers.get(l[1].id).attrs['State']['Pid']
            cmd = 'nsenter -t ' + str(srcPid) + ' -n ip link add e' + str(
                l[0].port_offset) + ' type veth peer name e' + str(l[1].port_offset) + ' netns ' + str(dstPid)
            os.system(cmd)

            print 'setup links for ' + str(l[0].id)
            # set peer 1
            utils.nsenter_run(srcPid, 'ovs-vsctl add-port s e' + str(l[0].port_offset))
            utils.nsenter_run(srcPid, 'ovs-vsctl add-port s i' + str(l[0].port_offset) + ' -- set interface i' + str(
                l[0].port_offset) + ' type=internal')

            ip1 = '1.' + str(j) + '.' + str(i) + '.1/24'
            utils.nsenter_run(srcPid, 'ifconfig i' + str(l[0].port_offset) + ' ' + ip1 + ' hw ether 76:00:00:00:00:01')
            utils.nsenter_run(srcPid, 'ifconfig e' + str(l[0].port_offset) + ' 0.0.0.0')

            print 'setup links for ' + str(l[1].id)
            # set peer 2
            utils.nsenter_run(dstPid, 'ovs-vsctl add-port s e' + str(l[1].port_offset))
            utils.nsenter_run(dstPid,
                              'ovs-vsctl add-port s i' + str(l[1].port_offset) + ' -- set interface i' + str(
                                  l[1].port_offset) + ' type=internal')
            ip2 = '1.' + str(j) + '.' + str(i) + '.2/24'
            utils.nsenter_run(dstPid, 'ifconfig i' + str(l[1].port_offset) + ' ' + ip2 + ' hw ether 76:00:00:00:00:01')
            utils.nsenter_run(dstPid, 'ifconfig e' + str(l[1].port_offset) + ' 0.0.0.0')

            topo.nodes[l[0].id][l[0].port_offset * 2 + 1] = {'name': 'e' + str(l[0].port_offset),
                                                             'type': 'veth', 'fip': ip1}
            topo.nodes[l[0].id][l[0].port_offset * 2 + 2] = {'name': 'i' + str(l[0].port_offset),
                                                             'type': 'internal', 'ip': ip1}
            topo.nodes[l[1].id][l[1].port_offset * 2 + 1] = {'name': 'e' + str(l[1].port_offset),
                                                             'type': 'veth', 'fip': ip2}
            topo.nodes[l[1].id][l[1].port_offset * 2 + 2] = {'name': 'i' + str(l[1].port_offset),
                                                             'type': 'internal', 'ip': ip2}
            topo.links[(l[0].id, l[0].port_offset * 2 + 1)] = (l[1].id, l[1].port_offset * 2 + 1)
            topo.links[(l[1].id, l[1].port_offset * 2 + 1)] = (l[0].id, l[0].port_offset * 2 + 1)

            l[0].port_offset = l[0].port_offset + 1
            l[1].port_offset = l[1].port_offset + 1

            if i == 254:
                j += 1
                i = 0
            i = i + 1

        topo.save('configs/common/topo.json')

        self.topo = topo

        self._write_quagga_configs()

        ports = topo.spanning_tree()
        print(ports)
        with open("configs/common/spanningtree.json", 'w') as f:
            json.dump(ports, f, indent=2)

        container_info = {}
        for n,c in self.containers.items():
            ipaddr = c.attrs['NetworkSettings']['IPAddress']
            container_info[n] = {'eth0': ipaddr}
        print(container_info)
        with open("configs/common/container.json", 'w') as f:
            json.dump(container_info, f)

        for id in self.routers:
            print 'configure to_controller rules ' + id
            c = self.containers[id]
            cmd1 = 'ovs-ofctl add-flow -OOpenFlow13 s priority=53333,ip,ip_proto=144,actions=output:controller'
            c.exec_run(cmd1)
            cmd1 = 'ovs-ofctl add-flow -OOpenFlow13 s priority=53333,ip,ip_proto=143,actions=output:controller'
            c.exec_run(cmd1)
            ps = [str(p) for p in ports[id]]
            ps.append('controller')
            pss = ','.join(ps)
            cmd2 = 'ovs-ofctl add-flow -OOpenFlow13 s priority=53333,ip,ip_proto=145,actions=output:%s' % pss
            c.exec_run(cmd2)

        # configure ospf rules
        for id in self.routers:
            print 'configure ospf rule of ' + id
            c = self.containers[id]
            c.exec_run('/bootstrap/start.py', detach=True)

    def _make_configs_directory(self):
        if os.path.exists('configs'):
            shutil.rmtree('configs')
        utils.mkdir_p('configs/common')
        # os.system('cp ignored/preset/%s/* configs/common/' % (self.filename))
        for r in self.routers.values():
            utils.mkdir_p('configs/' + r.id)

    def _write_quagga_configs(self):
        for node_id, ports in self.topo.nodes.items():
            print('write quagga configs', node_id)
            with open('configs/' + node_id + '/zebra.conf', 'w') as f:
                f.write('hostname Router\npassword zebra\nenable password zebra')

            with open('configs/' + node_id + '/ospfd.conf', 'w') as f:
                f.write('hostname ospfd\npassword zebra\nlog stdout\n')

                # for port_id, port in ports.items():
                #     if port['type'] == 'internal':
                #         f.write(
                #             '!\ninterface %s\n  ip ospf hello-interval 4\n  ip ospf dead-interval 10\n' % port['name'])

                f.write('!\nrouter ospf\n')

                for port_id, port in ports.items():
                    if port['type'] == 'internal':
                        f.write(' network ' + port['ip'] + ' area 0\n')

    def node_nsenter_exec(self, n, cmd):
        pid = client.containers.get(n).attrs['State']['Pid']
        utils.nsenter_run(pid, cmd)

    def stop(self):
        print 'cleaning containers...'

        for name in self.containers:
            print("clean container %s" % name)
            client.containers.get(name).remove(force=True)

        exit(0)

    def emptyline(self):
        return ""

    def do_write_quagga_configs(self, line):
        self._write_quagga_configs()

    def do_start_iperf_server(self, line):
        def inner_trd(c):
            c.exec_run('nohup iperf -s -u &')

        for r in self.routers.values():
            c = self.containers[r.id]
            t = threading.Thread(target=inner_trd, args=(c,))
            print 'start iperf server for ' + r.id
            t.setDaemon(True)
            t.start()

    def do_start_iperf_client(self, line):
        self.iperf_run = True
        self.topo = Topology()
        self.topo.load('configs/common/topo.json')

        def inner_trd(c):
            while self.iperf_run:
                time.sleep(random.randint(0, 2))
                print 'start iperf client for ' + r.id
                random_remote_info = random.choice(list(self.topo.nodes.values()))
                print random_remote_info
                c.exec_run('iperf -c' + random_remote_info[1]['fip'][:-3] + ' -u -b 64k -n 128000')

        for r in self.routers.values():
            c = self.containers[r.id]
            t = threading.Thread(target=inner_trd, args=(c,))
            t.setDaemon(True)
            t.start()
            
    def do_stop_iperf_client(self, line):
        self.iperf_run = False

    def do_start_ospf(self, line):
        """ start ospf process"""
        for r in self.routers.values():
            print 'start ospf for ' + r.id
            c = self.containers[r.id]
            c.exec_run('zebra -d -f /etc/quagga/zebra.conf --fpm_format protobuf')
            c.exec_run('ospfd -d -f /etc/quagga/ospfd.conf')

    def do_start_fpm_server(self, line):
        """ start fpm server process"""
        for r in self.routers.values():
            print 'start fpm for ' + r.id
            c = self.containers[r.id]
            c.exec_run('python /fpm/main.py &', detach=True)

    def do_kill_ospf_and_server(self, line):
        """ kill ospf and fpm server process"""
        os.system('pkill -f -e "^python /fpm/main.py"')
        os.system('pkill -f -e "^zebra"')
        os.system('pkill -f -e "^ospfd"')

    def do_start_ospf_and_server(self, line):
        """ start ospf and fpm server prcocess"""
        os.system("rm -f configs/common/fpm-history-*.json")
        os.system("rm -f configs/common/fpm-server-*.log")
        self.do_start_fpm_server(None)
        self.do_start_ospf(None)

    def do_start_ryufly(self, line):
        name = 'ryufly'
        cwd = os.getcwd()
        client.containers.run('snlab/ryufly', detach=True, name=name, privileged=False, tty=True,
                            hostname=name,
                            volumes={cwd : {'bind': cwd}},
                            command=cwd + '/ryufly/run.sh')
        c = client.containers.get(name)
        if c is None:
            print("error start container")
        else:
            print("start ryufly successfully")

    def do_kill_ryufly(self, line):
        name = 'ryufly'
        c = client.containers.get(name)
        if c is not None:
            c.remove(force=True)
            print("removed")
        else:
            print("not exists")

    def do_set_ovs_controller_to_ryufly(self, line):
        name = 'ryufly'
        c = client.containers.get(name)
        if c is None:
            print("error get container")
            return
        ipaddr = c.attrs['NetworkSettings']['IPAddress']
        if len(ipaddr)<1:
            print("error ip address", ipaddr)
            return
        self.do_set_ovs_controller("tcp:%s:6653" % ipaddr)

    def do_set_ovs_controller(self, line):
        args = line.split()
        controller_addr = 'tcp:127.0.0.1:6633'
        if len(args)<1:
            print("default controller address", controller_addr)
        else:
            controller_addr = args[0]
        
        for n,c in self.containers.items():
            cmd = "ovs-vsctl set-controller s %s" % controller_addr
            print(cmd)
            c.exec_run(cmd)

    def do_eval(self, line):

        test_total_time = 8 # int

        for i in range(1,8):
            freq = 0.125* 2**i

            result_dir = "ignored/data/eval/result-%d-%f/" % (test_total_time, freq)
            os.system("rm -rf " + result_dir)
            os.system("mkdir -p " + result_dir)

            link_down_log = "%slink-down-up.log" % (result_dir,)

#            self.do_start_ryufly(None)
#            self.do_set_ovs_controller_to_ryufly(None)
            for j in range(10):
#                time.sleep(1)
                print(j)

            #self.do_dump_netstat_ns_config()
#            self.do_start_netstat_ns(None)
            time.sleep(3)

            pair = None
            self.current = time.time()
            if freq == 0.125:
                links_list = list(sorted(self.topo.links.items()))
                ri = random.randint(0, len(links_list) - 1)
                pair = links_list[ri]
                self._link_down(pair)
                history = []
                history.append({
                    'pair': pair,
                    'op': 'down',
                    'time': time.time()
                })
                with open(link_down_log, 'w') as f:
                    json.dump(history, f, indent=2)
            else:
                self.do_link_down_test("%s %d %f" % (link_down_log, test_total_time, freq))
            time.sleep(35)
            self._gather(freq)

            self.do_kill_netstat_ns(None)
            time.sleep(1)
#           self.do_kill_ryufly(None)

        #    os.system("mv result.dat %snetstat-ns-result.dat" % (result_dir, ))
#            os.system("mv configs/common/ryufly.log %sryufly.log" % (result_dir, ))

            if pair is not None:
                self._link_up(pair)
            time.sleep(30)

    def _gather(self, fq):
        nodes = get_nodes('configs')
        history = get_fpm_history(nodes)
        data = {}
        for id, time_list in history.items():
            data[id] = []
            for t in time_list:
                if t > self.current:
                    delta = t - self.current
                    data[id].append(delta)
        with open('result/raw/output.%s.dat' % (fq), 'w') as f:
            f.write(json.dumps(data))

    def do_setup_latency(self, line):
        for l in self.topo.links.items():
            self._link_set_bw_latency(l, 64, None)
        for n in self.topo.nodes:
            self._port_set_bw_latency(n, 'eth0', 64, None)
    
    def do_setup_latency_ryufly_eth0(self, line):
        name = 'ryufly'
        c = client.containers.get(name)
        if c is None:
            print("not exists")
        else:
            self._port_set_bw_latency(name, 'eth0', 64, None)

    def do_link_down_test(self, line):
        """link down test"""
        self.current = time.time()
        args = line.split()
        if len(args) < 1:
            print('link_down_test file.name')
            return

        history_file_name = args[0]
        history = []
        links_list = list(sorted(self.topo.links.items()))
        random.seed(0)
        total_time = int(args[1]) # second
        frequency = float(args[2]) # HZ

        for index in range(int(total_time * frequency / 2)):
            ri = random.randint(0, len(links_list) - 1)
            pair = links_list[ri]

            history.append({
                'pair': pair,
                'op': 'down',
                'time': time.time()
            })
            self._link_down(pair)
            time.sleep((1.0/frequency))
            print('link', pair, 'down')

            history.append({
                'pair': pair,
                'op': 'up',
                'time': time.time()
            })
            self._link_up(pair)
            time.sleep((1.0/frequency))
            print('link', pair, 'up')

        with open(history_file_name, 'w') as f:
            json.dump(history, f, indent=2)


    def do_gather_update_time(self, line):
        nodes = get_nodes('configs')
        history = get_fpm_history(nodes)
        for id, time_list in history.items():
            print id, time_list[-1] - self.current

    def do_link(self, line):
        """link down/up  host1 host2"""
        args = line.split()
        if len(args) < 3:
            print("error args")
            return
        op, n1, n2 = args[0], args[1], args[2]
        if n1 not in self.topo.nodes or n2 not in self.topo.nodes:
            print("error args")
            return
        for start, end in self.topo.links.items():
            self.current = time.time()
            if start[0] == n1 and end[0] == n2:
                if op == 'down':
                    self._link_down((start, end))
                elif op == 'up':
                    self._link_up((start, end))
                break
        else:
            print("not find link")

    def _link_down(self, pair):  # ((n1, p1), (n2, p2))
        for n, p in pair:
            ename = self.topo.nodes[n][p]['name']
            iname = 'i' + ename[1:]
            self.node_nsenter_exec(n, "ifconfig %s down" % iname)
            print('down', n, iname)

    def _link_up(self, pair):  # ((n1, p1), (n2, p2))
        for n, p in pair:
            ename = self.topo.nodes[n][p]['name']
            iname = 'i' + ename[1:]
            self.node_nsenter_exec(n, "ifconfig %s up" % iname)
            print('up', n, iname)

    def do_set_bw_latency(self, line):
        """set_bw_latency n1 n2 bw(kbps) latency(ms)"""
        args = line.split()
        if len(args) < 4:
            print("error args")
            return
        n1, n2, bw, latency = args[0], args[1], args[2], args[3]
        bw = int(bw)
        latency = int(latency)
        if n1 not in self.topo.nodes or n2 not in self.topo.nodes:
            print("error args")
            return
        for start, end in self.topo.links.items():
            if start[0] == n1 and end[0] == n2:
                self._link_set_bw_latency((start, end), bw, latency)
                break
        else:
            print("not find link")

    def _link_set_bw_latency(self, pair, bw, latency):  # ((n1, p1), (n2, p2))
        for n, p in pair:
            name = self.topo.nodes[n][p]['name']
            self._port_set_bw_latency(n, name, bw, latency)
        
    def _port_set_bw_latency(self, node, port_name, bw, latency): #  '11' 'e0'
            status = self.port_status.setdefault((node, port_name), {})
            pre_bw = status.setdefault('bw', None)
            pre_latency = status.setdefault('latency', None)
            cmds = []
            if pre_bw is None and pre_latency is None:
                cmds.append('tc qdisc del dev %s root'  % (port_name, ))
                cmds.append('tc qdisc add dev %s root handle 5:0 htb default 1'  % (port_name, ))
            if pre_bw != bw:
                if bw is None:
                    cmds.append('tc class del dev %s parent 5:0 classid 5:1' % (port_name, ))
                elif pre_bw is None:
                    cmds.append('tc class add dev %s parent 5:0 classid 5:1 htb rate %dkbit burst 1b' % (port_name, bw))
                else:
                    cmds.append('tc class change dev %s parent 5:0 classid 5:1 htb rate %dkbit burst 1b peakrate 1bit' % (port_name, bw, bw))
            if pre_latency != latency:
                if latency is None:
                    cmds.append('tc qdisc del dev %s parent 5:1 handle 10:' % (port_name,))
                elif pre_latency is None:
                    cmds.append('tc qdisc add dev %s parent 5:1 handle 10: netem delay %dms' % (port_name, latency))
                else:
                    cmds.append('tc qdisc change dev %s parent 5:1 handle 10: netem delay %dms' % (port_name, latency))
            status['bw'] = bw
            status['latency'] = latency
            for cmd in cmds:
                print(node, cmd)
                self.node_nsenter_exec(node, cmd)

    def do_start_ryu(self, line):
        """deprecated"""
        for r in self.routers.values():
            print 'start multijet for ' + r.id
            c = self.containers[r.id]
            c.exec_run('ryu-manager /multijet/multijet.py', detach=True)

    def do_start_ryu2(self, line):
        """start multijet main process"""
        self.do_remove_log(None)

        for r in self.routers.values():
            print 'start multijet2 for ' + r.id
            c = self.containers[r.id]
            code, output = c.exec_run('ryu-manager multijet.multijet2', detach=True, environment=['PYTHONPATH=/'],
                                      workdir='/')
            print(output)

    def do_remove_log(self, line):
        """remove multijet log file"""
        for n in self.routers:
            log_file_path = 'configs/%s/multijet2.log' % n
            if os.path.exists(log_file_path):
                os.remove(log_file_path)

    def do_kill_ryu(self, line):
        """kill all ryu process"""
        os.system('pkill -f -e "^/usr/bin/python /usr/local/bin/ryu-manager"')
        # for r in self.routers.values():
        #     print 'kill multijet2 for ' + r.id
        #     c = self.containers[r.id]
        #     code, output = c.exec_run('pkill ryu')
        #     print(output)

    def do_ps(self, line):
        for r in self.routers.values():
            print 'ps cmd for ' + r.id
            c = self.containers[r.id]
            code, output = c.exec_run('ps')
            print(output)

    def do_exec(self, line):
        for r in self.routers.values():
            print('exec cmd %s for %s' % (line, str(r.id)))
            c = self.containers[r.id]
            code, output = c.exec_run(line)
            print(output)

    def do_test(self, line):
        print(line)
        urls = []
        for c in self.containers:
            ip = str(client.containers.get(c).attrs['NetworkSettings']['Networks']['bridge']['IPAddress'])
            urls.append('http://' + ip + ':8080/test')
        rs = (grequests.get(u) for u in urls)
        resps = grequests.map(rs)
        print(resps)

    def do_restart(self, line):
        print(line)
        urls = []
        for c in self.containers:
            ip = str(client.containers.get(c).attrs['NetworkSettings']['Networks']['bridge']['IPAddress'])
            urls.append('http://' + ip + ':8080/restart')
        rs = (grequests.get(u) for u in urls)
        resps = grequests.map(rs)
        print(resps)

    def do_test_ready(self, line):
        for n in self.routers:
            with open('configs/%s/multijet2.log' % n) as f:
                s = f.read()
                # print(s)
                if 'start run' not in s:
                    print('node %s not ready' % n)
        print('test ready done!')

    def do_dump_netstat_ns_config(self, line):
        args = line.split()

        if len(args)>=1 and args[0]=='all':
            dumpall = True
        else:
            dumpall = False

        lines = []
        for n, ports in self.topo.nodes.items():
            pid = client.containers.get(n).attrs['State']['Pid']
            names = []
            for p in ports.values():
                if p['type'] == 'veth':
                    names.append(p['name'])
            if dumpall:
                names.append('eth0')
            lines.append("%s %d %d %s\n" % (n, pid, len(names), ' '.join(names)))

        if dumpall:
            c = client.containers.get('ryufly')
            if c is None:
                print("warning: no ryufly container")
            else:
                pid = c.attrs['State']['Pid']
                lines.append("ryufly %d 1 eth0" % (pid, ))

        with open('configs/common/netstat_ns.conf', 'w') as f:
            for l in lines:
                f.write(l)
        print(lines)
    
    def do_start_netstat_ns(self, line):
        os.system("./ignored/netstat-ns/netstat-ns 100 configs/common/netstat_ns.conf &")
    
    def do_kill_netstat_ns(self, line):
        os.system("pkill -e netstat-ns")

    def _read_config_path(self, i):
        with open('configs/common/random_path.json') as f:
            data = json.load(f)
        return [(str(n), int(output)) for n, output in data[i]]

    def _get_config_path_length(self):
        with open('configs/common/random_path.json') as f:
            data = json.load(f)
        return len(data)

    def do_dump_random_path(self, line):
        """random generate test path and write configuration file"""
        paths = []
        try:
            num, a, b = line.split()
            num = int(num)
            start = int(a)
            end = int(b)
        except:
            print('error argument')
            return

        while len(paths) < num:
            select_len = random.randint(start, end)
            nodes = list(self.topo.nodes.keys())
            r1 = random.randint(0, len(nodes) - 1)
            sn = nodes[r1]
            path = []
            flags = {n: False for n in nodes}
            print('select_len', select_len)
            while len(path) < select_len:
                flags[sn] = True
                nsn = [(p1, p2[0]) for p1, p2 in self.topo.links.items() if p1[0] == sn and flags[p2[0]] == False]
                if len(nsn) == 0:
                    break
                r2 = random.randint(0, len(nsn) - 1)
                ns = nsn[r2]
                path.append(ns[0])
                sn = ns[1]
            print('path', path)

            if len(path) >= start:
                paths.append(path)
            print('len(paths)', len(paths))
        with open('configs/common/random_path.json', 'w') as f:
            json.dump(paths, f, indent=2)

    def do_exit(self, line):
        """exit all container"""
        print('shell exit')
        return True

    def do_just_exit(self, line):
        """just exit this shell, but keep container running"""
        print('just exit')
        exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="eval2")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-a", "--attach", action="store_true")
    parser.add_argument("topo", type=str, help="topology file")
    args = parser.parse_args()
    topo = RocketFuel(args.topo)
    if args.attach:
        topo.attach()
    else:
        topo.start()
    topo.cmdloop()
    topo.stop()
