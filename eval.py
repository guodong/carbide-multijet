import argparse
import random
from cmd import Cmd
import json
import os
import shutil
import utils
import docker
import time

client = docker.from_env()


class Port:
    def __init__(self, node, id):
        self.node = node
        self.id = id
        self.ip = ''
        self.bw = None

    def set_bw(self, bw):
        cmds = []
        cmds.append('tc qdisc del dev e%s root' % (self.id))
        cmds.append('tc qdisc add dev e%s root handle 5:0 htb default 1' % (self.id,))
        if self.bw is None:
            cmds.append('tc class del dev e%s parent 5:0 classid 5:1' % (self.id,))
            cmds.append('tc class add dev e%s parent 5:0 classid 5:1 htb rate %skbit' % (self.id, bw))
        else:
            cmds.append('tc class change dev e%s parent 5:0 classid 5:1 htb rate %skbit' % (
                self.id, bw))
        self.bw = bw
        for cmd in cmds:
            print(self.node.id, cmd)
            self.node.nsenter_exec(cmd)


class Node:
    def __init__(self, id):
        self.id = id
        self.ports = []
        self.port_offset = 0
        self.container = None

    def nsenter_exec(self, cmd):
        pid = client.containers.get(self.id).attrs['State']['Pid']
        utils.nsenter_run(pid, cmd)


class Link:
    def __init__(self, lid, p0, p1):
        self.status = 1  # default 1(UP)
        self.lid = lid
        self.p0 = p0
        self.p1 = p1

    def _up(self):
        self.p0.node.nsenter_exec("ifconfig e%s up" % self.p0.id)
        self.p1.node.nsenter_exec("ifconfig e%s up" % self.p1.id)

    def _down(self):
        self.p0.node.nsenter_exec("ifconfig e%s down" % self.p0.id)
        self.p1.node.nsenter_exec("ifconfig e%s down" % self.p1.id)

    def toggle(self):
        if self.status == 1:
            self._down()
            self.status = 0
        else:
            self._up()
            self.status = 1


class Topology:
    def __init__(self):
        self.nodes = {}
        self.links = []


class Main(Cmd):
    intro = 'Welcome to the Multijet eval shell.   Type help or ? to list commands.\n'
    prompt = 'multijet> '

    def __init__(self):
        Cmd.__init__(self)
        self.topo = Topology()

    def do_load_topo(self, line):
        with open(line) as f:
            topo = json.load(f)

            for n in topo['nodes']:
                nid = 'r' + str(n)
                r = Node(nid)

                self.topo.nodes[n] = r

            for l in topo['links']:
                p0 = Port(self.topo.nodes[l[0]], self.topo.nodes[l[0]].port_offset)
                p1 = Port(self.topo.nodes[l[1]], self.topo.nodes[l[1]].port_offset)
                self.topo.nodes[l[0]].port_offset += 1
                self.topo.nodes[l[1]].port_offset += 1
                self.topo.nodes[l[0]].ports.append(p0)
                self.topo.nodes[l[1]].ports.append(p1)
                lid = str(l[0]) + '-' + str(l[1])
                link = Link(lid, p0, p1)
                self.topo.links.append(link)

    def do_start_network(self, line):
        self._make_configs_directory()
        for r in self.topo.nodes.values():
            print 'starting ' + r.id
            r.container = client.containers.run('snlab/dovs-quagga', detach=True, name=r.id, privileged=True, tty=True,
                                                hostname=r.id,
                                                volumes={os.getcwd() + '/configs/' + r.id: {'bind': '/etc/quagga'},
                                                         os.getcwd() + '/bootstrap': {'bind': '/bootstrap'},
                                                         os.getcwd() + '/fpm': {'bind': '/fpm'},
                                                         os.getcwd() + '/multijet': {'bind': '/multijet'},
                                                         os.getcwd() + '/configs/common': {'bind': '/common'}},
                                                command='/bootstrap/start.sh')

        print 'setup links'
        i = 0
        j = 0
        for l in self.topo.links:
            srcPid = client.containers.get(l.p0.node.id).attrs['State']['Pid']
            dstPid = client.containers.get(l.p1.node.id).attrs['State']['Pid']
            cmd = 'nsenter -t ' + str(srcPid) + ' -n ip link add e' + str(
                l.p0.id) + ' type veth peer name e' + str(l.p1.id) + ' netns ' + str(dstPid)
            os.system(cmd)

            print 'setup links for ' + str(l.p0.id)
            # set peer 1
            ip1 = '1.' + str(j) + '.' + str(i) + '.1/24'
            l.p0.ip = ip1
            utils.nsenter_run(srcPid, 'ifconfig e' + str(l.p0.id) + ' ' + ip1 + ' hw ether 76:00:00:00:00:01')

            print 'setup links for ' + str(l.p1.id)
            # set peer 2
            ip2 = '1.' + str(j) + '.' + str(i) + '.2/24'
            l.p1.ip = ip2
            utils.nsenter_run(dstPid, 'ifconfig e' + str(l.p1.id) + ' ' + ip2 + ' hw ether 76:00:00:00:00:01')

            if i == 254:
                j += 1
                i = 0
            i = i + 1

        self._write_quagga_configs()

        # configure ospf rules
        for node in self.topo.nodes.values():
            print 'configure ospf rule of ' + node.id
            node.container.exec_run('/bootstrap/start.py', detach=True)

    def _write_quagga_configs(self):
        for node_id, node in self.topo.nodes.items():
            print('write quagga configs', node_id)
            with open('configs/%s/zebra.conf' % node.id, 'w') as f:
                f.write('hostname Router\npassword zebra\nenable password zebra')

            with open('configs/%s/ospfd.conf' % node.id, 'w') as f:
                f.write('hostname ospfd\npassword zebra\nlog stdout\n')
                f.write('!\nrouter ospf\n')

                for port in node.ports:
                    f.write(' network ' + port.ip + ' area 0\n')

    def _make_configs_directory(self):
        if os.path.exists('configs'):
            shutil.rmtree('configs')
        utils.mkdir_p('configs/common')
        for r in self.topo.nodes.values():
            utils.mkdir_p('configs/' + r.id)

    def do_start_ospf(self, line):
        """ start ospf process"""
        for r in self.topo.nodes.values():
            print 'start ospf for ' + r.id
            c = r.container
            c.exec_run('zebra -d -f /etc/quagga/zebra.conf --fpm_format protobuf')
            c.exec_run('ospfd -d -f /etc/quagga/ospfd.conf')

    def do_start_fpm_server(self, line):
        """ start fpm server process"""
        for r in self.topo.nodes.values():
            print 'start fpm for ' + r.id
            c = r.container
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

    def do_eval(self, line):

        test_total_time = 8  # int

        for i in range(8):
            freq = 0.125 * 2 ** i

            result_dir = "ignored/data/eval/result-%d-%f/" % (test_total_time, freq)
            os.system("rm -rf " + result_dir)
            os.system("mkdir -p " + result_dir)

            self.do_link_down_test("%d %f" % (test_total_time, freq))
            time.sleep(60)
            self.do_link_up_all()
            time.sleep(60)

    def do_link_up_all(self, line):
        for l in self.topo.links:
            if l.status == 0:
                l.up()

    def do_link_down_test(self, line):
        """link down test"""
        args = line.split()

        total_time = int(args[0])  # second
        frequency = float(args[1])  # HZ

        for i in range(int(total_time * frequency)):
            ri = random.randint(0, len(self.topo.links) - 1)
            link = self.topo.links[ri]
            link.toggle()
            time.sleep((1.0 / frequency))

    def do_set_bw(self, bw):  # ((n1, p1), (n2, p2))
        for l in self.topo.links:
            l.p0.set_bw(bw)
            l.p1.set_bw(bw)

    def stop(self):
        print 'cleaning containers...'

        for node in self.topo.nodes.values():
            print("clean container %s" % node.id)
            node.container.remove(force=True)

        exit(0)

    def do_exit(self, line):
        return True

    def do_just_exit(self, line):
        """just exit this shell, but keep container running"""
        print('just exit')
        exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="eval")
    parser.add_argument("-a", "--attach", action="store_true")
    args = parser.parse_args()
    main = Main()
    main.cmdloop()
    main.stop()
