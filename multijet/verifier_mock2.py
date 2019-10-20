import json
from multiprocessing import Process, Queue

from netaddr import IPSet
from utils import log
from .ecs_mgr import FloodECSMgr
from .ecs_mgr import PushPullECSMgr
from .topo import Topology
from .transceiver import Transceiver

DATADIR = 'configs/common'
# DATADIR = 'ignored/common'


class MockTransceiver(Transceiver):
    def __init__(self, node_id, qs, topo):
        super(MockTransceiver, self).__init__()
        self.qs = qs
        self.topo = topo # type: Topology
        self.node_id = node_id

    def send(self, obj, target):
        # target ('unicast', port)   ('flood_neighbor', )
        if target[0]=='unicast':
            sn, sp = self.topo.get_nextport(self.node_id, target[1])
            self.qs[sn].put({
                'type': 'mock_trans',
                'data': obj,
                'source': ('unicast', sp)
            })
        elif target[0]=='flood_neighbor':
            nodes = self.topo.get_neighbor(self.node_id)
            for n in nodes:
                self.qs[n].put({
                    'type': 'mock_trans',
                    'data': obj,
                    'source': ('flood_neighbor',)
                })
        elif target[0]=='flood':
            nodes = self.topo.nodes
            for n in nodes:
                if n==self.node_id:
                    continue
                self.qs[n].put({
                    'type': 'mock_trans',
                    'data': obj,
                    'source': ('flood',)
                })
        else:
            log("error send message")

    def on_recv(self, data, source):
        self._recv_callback(data, source)


class MockPushPullECSMgr(PushPullECSMgr):
    def run(self):
        log('start run')
        while True:
            try:
                msg = self.queue.get(timeout=20)
                # debug(msg)
            except Exception:
                log(self.dump_ecs())
                self.check()
                break
            if msg['type'] == 'mock_trans':
                self.transceiver.on_recv(msg['data'], msg['source'])
            elif msg['type'] == 'local_update':
                self._update_local_rules(msg['rules'])
            elif msg['type'] == 'unicast':
                self._on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type'] == 'flood_neighbor':
                self._on_recv_flood_neighbor(msg['data']['ecs'])
            else:
                log("error message type")


class MockFloodECSMgr(FloodECSMgr):
    def run(self):
        log('start run')
        while True:
            try:
                msg = self.queue.get(timeout=5)
                log(msg)
            except Exception:
                log(self.dump_ecs())
                self.check()
                break
            if msg['type'] == 'mock_trans':
                self.transceiver.on_recv(msg['data'], msg['source'])
            elif msg['type'] == 'local_update':
                self.update_local_rules(msg['rules'])
            elif msg['type'] == 'unicast':
                self._on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type'] == 'flood':
                self._on_recv_ecs_flood_all(msg['data'])
            else:
                log('error queue message type')


def load_rules(n):
    rules = {}
    with open(DATADIR+'/ospf%s.json'%str(n)) as f:
        obj = json.load(f)
        log('parse len = %d'%len(obj))
        for flow in obj:
            ip, mask = flow['match']['ipv4_dst']
            output = int(flow['action']['output'])
            space = str(ip)+'/24'
            rules.setdefault(output, [])
            rules[output].append(space)
    return [(IPSet(space), port) for port,space in rules.items()]


def main():
    topo = Topology()
    topo.load(DATADIR + '/topo.json')
    qs = {n: Queue() for n in topo.nodes.keys()}
    mocks = {}
    for n in topo.nodes:
        t = MockTransceiver(n, qs, topo)
        # mock = MockPushPullECSMgr(n, qs[n], topo, t)
        mock = MockFloodECSMgr(n, qs[n], topo, t)
        mocks[n] = mock
    processes = []
    for t in mocks.values():
        proc = Process(target=t.run)
        proc.start()
        processes.append(proc)

    all_rules = {n: load_rules(n) for n in topo.nodes}

    for n in topo.nodes.keys():
        rules = all_rules[n]
        log(rules)
        qs[n].put({
            'type': 'local_update',
            'rules': rules
        })

    for t in processes:
        t.join()


if __name__=='__main__':
    main()
