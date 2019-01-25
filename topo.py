import docker
import os, errno, shutil, signal, time

routers = {}

links = []
client = docker.from_env()

containers = {}


class Router:
    def __init__(self, id):
        self.id = id
        self.neighbors = []
        self.ips = []
        self.internal_ports = []
        self.external_ports = []
        self.port_offset = 0


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def gen_config():
    shutil.rmtree('configs')
    for r in routers.values():
        mkdir_p('configs/' + r.id)
        with open('configs/' + r.id + '/zebra.conf', 'a') as f:
            f.write('hostname Router\npassword zebra\nenable password zebra')

        with open('configs/' + r.id + '/ospfd.conf', 'a') as f:
            f.write('hostname ospfd\npassword zebra\nlog stdout\nrouter ospf\n')

    i = 0
    j = 0
    for l in links:
        k = 1
        for r in l:
            ip = '1.' + str(j) + '.' + str(i) + '.' + str(k) + '/24'
            r.ips.append(ip)
            with open('configs/' + r.id + '/ospfd.conf', 'a') as f:
                f.write(' network ' + ip + ' area 0\n')

            k = k + 1
        if i == 254:
            j = 1
            i = 0
        i = i + 1


def nsenter_run(pid, cmd):
    c = 'nsenter -t ' + str(pid) + ' -n -m -p ' + cmd
    os.system(c)


def start():
    for r in routers.values():
        print 'starting ' + r.id
        container = client.containers.run('snlab/dovs-quagga', detach=True, name=r.id, privileged=True, tty=True,
                                          hostname=r.id,
                                          volumes={os.getcwd() + '/configs/' + r.id: {'bind': '/etc/quagga'},
                                                   os.getcwd() + '/bootstrap': {'bind': '/bootstrap'},
                                                   os.getcwd() + '/fpmserver': {'bind': '/fpmserver'}},
                                          command='/bootstrap/start.sh')
        containers[r.id] = container

    time.sleep(3)

    print 'setup links'
    i = 0
    j = 0
    count = 0
    for l in links:
        srcPid = client.containers.get(l[0].id).attrs['State']['Pid']
        dstPid = client.containers.get(l[1].id).attrs['State']['Pid']
        cmd = 'nsenter -t ' + str(srcPid) + ' -n ip link add e' + str(
            l[0].port_offset) + ' type veth peer name e' + str(l[
                                                                   1].port_offset) + ' netns ' + str(dstPid)
        os.system(cmd)

        print 'setup links for ' + str(l[0].id)
        # set peer 1
        c = containers[l[0].id]
        print l[0].id
        nsenter_run(srcPid, 'ovs-vsctl add-port s e' + str(l[0].port_offset))
        # c.exec_run('ovs-vsctl add-port s e' + str(l[0].port_offset))
        nsenter_run(srcPid, 'ovs-vsctl add-port s i' + str(l[0].port_offset) + ' -- set interface i' + str(
            l[0].port_offset) + ' type=internal')
        # c.exec_run(
        #     'ovs-vsctl add-port s i' + str(l[0].port_offset) + ' -- set interface i' + str(
        #         l[0].port_offset) + ' type=internal')
        ip = '1.' + str(j) + '.' + str(i) + '.1/24'
        nsenter_run(srcPid, 'ifconfig i' + str(l[0].port_offset) + ' ' + ip)
        nsenter_run(srcPid, 'ifconfig e' + str(l[0].port_offset) + ' 0.0.0.0')
        # c.exec_run('ifconfig i' + str(l[0].port_offset) + ' ' + ip)
        # c.exec_run('ifconfig e' + str(l[0].port_offset) + ' 0.0.0.0')

        # cmd = 'ovs-ofctl add-flow s in_port=' + str(l[0].port_offset * 2 + 2) + ',actions=output:' + str(l[0].port_offset * 2 + 1)
        # c.exec_run(cmd, detach=True)
        #
        # cmd = 'ovs-ofctl add-flow s ip,ip_proto=89,in_port=' + str(l[0].port_offset * 2 + 1) + ',actions=output:' + str(l[0].port_offset * 2 + 2)
        # c.exec_run(cmd, detach=True)
        #
        # cmd = 'ovs-ofctl add-flow s arp,arp_tpa=' + ip[:-3] + ',actions=output:' + str(l[0].port_offset * 2 + 2)
        # c.exec_run(cmd, detach=True)
        # cmd = 'ovs-ofctl add-flow s ip,nw_dst=' + ip[:-3] + ',actions=output:' + str(l[0].port_offset * 2 + 2)
        # c.exec_run(cmd, detach=True)

        print 'setup links for ' + str(l[1].id)
        # set peer 2
        c = containers[l[0].id]
        print l[1].id
        nsenter_run(dstPid, 'ovs-vsctl add-port s e' + str(l[1].port_offset))
        nsenter_run(dstPid,
                    'ovs-vsctl add-port s i' + str(l[1].port_offset) + ' -- set interface i' + str(
                        l[1].port_offset) + ' type=internal')
        ip = '1.' + str(j) + '.' + str(i) + '.2/24'
        nsenter_run(dstPid, 'ifconfig i' + str(l[1].port_offset) + ' ' + ip)
        nsenter_run(dstPid, 'ifconfig e' + str(l[1].port_offset) + ' 0.0.0.0')

        # cmd = 'ovs-ofctl add-flow s in_port=' + str(l[1].port_offset * 2 + 2) + ',actions=output:' + str(
        #     l[1].port_offset * 2 + 1)
        # c.exec_run(cmd, detach=True)
        #
        # cmd = 'ovs-ofctl add-flow s ip,ip_proto=89,in_port=' + str(l[1].port_offset * 2 + 2) + ',actions=output:' + str(
        #     l[1].port_offset * 2 + 1)
        # c.exec_run(cmd, detach=True)
        #
        # cmd = 'ovs-ofctl add-flow s arp,arp_tpa=' + ip[:-3] + ',actions=output:' + str(l[1].port_offset * 2 + 2)
        # c.exec_run(cmd, detach=True)
        # cmd = 'ovs-ofctl add-flow s ip,nw_dst=' + ip[:-3] + ',actions=output:' + str(l[1].port_offset * 2 + 2)
        # c.exec_run(cmd, detach=True)

        l[0].port_offset = l[0].port_offset + 1
        l[1].port_offset = l[1].port_offset + 1

        if i == 254:
            j = 1
            i = 0
        i = i + 1

    # configure ospf rules
    for id in routers:
        print 'configure ospf rule of ' + id
        c = containers[id]
        c.exec_run('/bootstrap/start.py', detach=True)

    # configure ovs
    # count = 0
    # for r in routers.values():
    #     print 'completed: ' + str(count)
    #     count = count + 1
    #     c = client.containers.get(r.id)
    #     # c.exec_run('/bootstrap/start.sh')
    #     # c.exec_run('service openvswitch-switch start')
    #     # c.exec_run('ovs-vsctl add-br s')
    #     # c.exec_run('ovs-vsctl set-controller s tcp:172.17.0.1:6633')
    #     # c.exec_run('ovs-vsctl set-fail-mode s secure')
    #     for i in range(r.port_offset):
    #         c.exec_run('ovs-vsctl add-port s e' + str(i), detach=True)
    #         c.exec_run(
    #             'ovs-vsctl add-port s i' + str(i) + ' -- set interface i' + str(i) + ' type=internal')
    # setup ip
    # for r in routers.values():
    #     print 'setup ip for ' + r.id
    #     c = containers[r.id]
    #     i = 0
    #     for ip in r.ips:
    #         c.exec_run('ifconfig i' + str(i) + ' ' + ip, detach=True)
    #         c.exec_run('ifconfig e' + str(i) + ' 0.0.0.0', detach=True)
    #         i = i + 1

    # set rules for ospf:
    # for r in routers.values():  # this takes much time, should use multi thread
    #     print 'set rules for ospf for ' + r.id
    #     c = containers[r.id]
    #     c.exec_run('ovs-ofctl del-flows s')  # clear flows before setting
    #     i = 1
    #     for ip in r.ips:
    #         # if not internal_port == 'i1':
    #         cmd = 'ovs-ofctl add-flow s in_port=' + str(i + 1) + ',actions=output:' + str(i)
    #         c.exec_run(cmd, detach=True)
    #
    #         cmd = 'ovs-ofctl add-flow s ip,ip_proto=89,in_port=' + str(i) + ',actions=output:' + str(i + 1)
    #         c.exec_run(cmd, detach=True)
    #
    #         cmd = 'ovs-ofctl add-flow s arp,arp_tpa=' + ip[:-3] + ',actions=output:' + str(i * 2)
    #         c.exec_run(cmd, detach=True)
    #         cmd = 'ovs-ofctl add-flow s ip,nw_dst=' + ip[:-3] + ',actions=output:' + str(i * 2)
    #         c.exec_run(cmd, detach=True)
    #         i = i + 2

    for r in routers.values():
        print 'start ospf for ' + r.id
        c = containers[r.id]
        c.exec_run('zebra -d -f /etc/quagga/zebra.conf --fpm_format protobuf')
        c.exec_run('ospfd -d -f /etc/quagga/ospfd.conf')
        # c.exec_run('python /fpmserver/fpm/main.py >> logs &', detach=True)
    for r in routers.values():
        print 'start ospf for ' + r.id
        c = containers[r.id]
        c.exec_run('python /fpmserver/fpm/main.py &', detach=True)

    print 'finished'


def signal_handler(sig, frame):
    print 'cleaning containers...'

    for name in containers:
        client.containers.get(name).remove(force=True)

    exit(0)


signal.signal(signal.SIGINT, signal_handler)

with open('1755.r0.cch', 'r') as f:
    for line in f:
        arr = line.split()
        routers[arr[0]] = Router(arr[0])

    f.seek(0)

    for line in f:
        arr = line.split('->')
        arr = arr[1].split('=')
        nei_str = arr[0].replace(' ', '')
        nei_ids = nei_str[1:-1].split('><')
        print nei_ids
        t = line.split()
        router = routers[t[0]]
        for nei in nei_ids:
            router.neighbors.append(routers[nei])

    for r in routers.values():
        for n in r.neighbors:
            exists = False
            for l in links:
                if n in l and r in l:
                    exists = True
            if not exists:
                links.append([r, n])

    print len(links)
    gen_config()
    start()

while True:
    time.sleep(1)
