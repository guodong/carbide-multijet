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

import docker
import grequests

import utils

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
        self.routers = {}
        self.links = []
        self.containers = {}
        self.filename = filename
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

    def attach(self):
        for r in self.routers.values():
            print 'get container ' + r.id
            container = client.containers.get(r.id)
            self.containers[r.id] = container

    def start(self):
        # generate ospf config file
        self.gen_config()

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
            self.containers[r.id] = container

        time.sleep(3)

        from multijet.topo import Topology
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
        ports = topo.spanning_tree()
        print(ports)
        with open("configs/common/spanningtree.json", 'w') as f:
            json.dump(ports, f, indent=2)

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
            cmd2 = 'ovs-ofctl add-flow -OOpenFlow13 s priority=53333,ip,ip_proto=145,actions=output:%s'%pss
            c.exec_run(cmd2)

        # configure ospf rules
        for id in self.routers:
            print 'configure ospf rule of ' + id
            c = self.containers[id]
            c.exec_run('/bootstrap/start.py', detach=True)

    def gen_config(self):
        if os.path.exists('configs'):
            shutil.rmtree('configs')
        utils.mkdir_p('configs/common')
        os.system('cp ignored/preset/%s/* configs/common/'%(self.filename))
        for r in self.routers.values():
            utils.mkdir_p('configs/' + r.id)
            with open('configs/' + r.id + '/zebra.conf', 'a') as f:
                f.write('hostname Router\npassword zebra\nenable password zebra')

            with open('configs/' + r.id + '/ospfd.conf', 'a') as f:
                f.write('hostname ospfd\npassword zebra\nlog stdout\nrouter ospf\n')

        i = 0
        j = 0
        for l in self.links:
            k = 1
            for r in l:
                ip = '1.' + str(j) + '.' + str(i) + '.' + str(k) + '/24'
                with open('configs/' + r.id + '/ospfd.conf', 'a') as f:
                    f.write(' network ' + ip + ' area 0\n')

                k = k + 1
            if i == 254:
                j += 1
                i = 0
            i = i + 1

    def stop(self):
        print 'cleaning containers...'

        for name in self.containers:
            print("clean container %s"%name)
            client.containers.get(name).remove(force=True)

        exit(0)

    def emptyline(self):
        return ""

    def do_start_ospf(self, line):
        for r in self.routers.values():
            print 'start ospf for ' + r.id
            c = self.containers[r.id]
            c.exec_run('zebra -d -f /etc/quagga/zebra.conf --fpm_format protobuf')
            c.exec_run('ospfd -d -f /etc/quagga/ospfd.conf')

        for r in self.routers.values():
            print 'start fpm for ' + r.id
            c = self.containers[r.id]
            c.exec_run('python /fpm/main.py &', detach=True)

    def do_start_ryu(self, line):
        for r in self.routers.values():
            print 'start multijet for ' + r.id
            c = self.containers[r.id]
            c.exec_run('ryu-manager /multijet/multijet.py', detach=True)

    def do_start_ryu2(self, line):
        self.do_remove_log(None)

        for r in self.routers.values():
            print 'start multijet2 for ' + r.id
            c = self.containers[r.id]
            code, output = c.exec_run('ryu-manager multijet.multijet2', detach=True, environment=['PYTHONPATH=/'], workdir='/')
            print(output)

    def do_remove_log(self, line):
        for n in self.routers:
            os.remove('configs/%s/multijet2.log'%n)

    def do_kill_ryu(self, line):
        for r in self.routers.values():
            print 'kill multijet2 for ' + r.id
            c = self.containers[r.id]
            code, output = c.exec_run('pkill ryu')
            print(output)

    def do_ps(self, line):
        for r in self.routers.values():
            print 'ps cmd for ' + r.id
            c = self.containers[r.id]
            code, output = c.exec_run('ps')
            print(output)

    def do_exec(self, line):
        for r in self.routers.values():
            print('exec cmd %s for %s'%(line, str(r.id)))
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

    def do_eval(self, line):
        rules = {}
        for n in self.routers:
            with open('configs/common/ospf%s.json' % str(n)) as f:
                obj = json.load(f)
                for flow in obj:
                    ip, mask = flow['match']['ipv4_dst']
                    output = int(flow['action']['output'])
                    k = ip + '/24'
                    ks = rules.setdefault(k, {})
                    ks[n] = output

        self.container_ip = {n: str(client.containers.get(n).attrs['NetworkSettings']['Networks']['bridge']['IPAddress'])
                        for n in self.routers}
        self.watch_pos = {}
        for n in self.routers:
            with open('configs/%s/multijet2.log' % n) as f:
                f.seek(0, 2)
                self.watch_pos[n] = f.tell()

        results = []
        for k, ks in rules.items():
            rules_once = {n: {k: output} for n, output in ks.items()}
            print('eval once')
            print(rules_once)
            self._eval_once(rules_once)
            time.sleep(5)
            t1_mn = float('inf')
            t2_mx = 0
            for n in ks.keys():
                t2, t1 = self._watch_install_and_finish(n)
                if t2_mx<t2: t2_mx = t2
                if t1_mn>t1: t1_mn = t1
                delta_t = t2 - t1
                print('node %s update time %f'%(n, delta_t))
            print('converge time %f'%(t2_mx - t1_mn))

    def _watch_install_and_finish(self, n):
        _, t1 = self._watch_wait_read(n, ('install',))
        last_t2 = None
        while True:
            words = ('handle one message', '=======dumpecs')
            w, t2 = self._watch_wait_read(n, words)
            if w == words[0]:
                last_t2 = t2
            else:
                break
        return last_t2,  t1

    def _watch_wait_read(self, n, words):
        while True:
            t = self._watch_for(n, words)
            if t is None:
                time.sleep(1)
            else:
                break
        return t

    def _watch_for(self, n, words):
        with open('configs/%s/multijet2.log' % n) as f:
            pos = self.watch_pos[n]
            f.seek(pos)
            while True:
                line = f.readline()
                self.watch_pos[n] = f.tell()
                if line == "":
                    self.watch_pos[n] = f.tell()
                    return None
                for word in words:
                    if word in line:
                        return word, self._parse_log_time(line)

    def _parse_log_time(self, line):
        b = next(re.finditer(' (\d+\.\d+) ', line))
        t_str = b.groups()[0]
        return float(t_str)

    def _eval_once(self, rules):
        reqs = []
        for n, rs in rules.items():
            ip = self.container_ip[n]
            url = 'http://' + ip + ':8080/install'
            d = rs
            req = grequests.post(url, json=d)
            reqs.append(req)
        resps = grequests.map(reqs)
        print(resps)

    def do_exit(self, line):
        print('shell exit')
        return True

    def do_just_exit(self, line):
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
