import json
from multiprocessing import Process, Queue

from netaddr import IPSet
from utils import log
from .ecs_mgr import ECSMgrPickle
from .ecs_mgr import PushPullECSMgr
from .topo import Topology
from .transceiver import Transceiver

DATADIR = 'configs/common'
# DATADIR = 'ignored/common'


class MockVerifierThread(ECSMgrPickle):

    def __init__(self, node_id, qs):
        topo = Topology()
        topo.load(DATADIR+'/topo.json')
        ECSMgrPickle.__init__(self, node_id, topo)
        self.all_queue = qs
        self.queue = qs[node_id]

    def run(self):
        while True:
            try:
                msg = self.queue.get(timeout=10)
            except Exception:
                log(self.dump_ecs())
                self.check()
                return
            if msg['type']=='local_update':
                self.update_local_rules(msg['rules'])
            elif msg['type']=='unicast':
                self.on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type']=='flood':
                self.on_recv_flood(msg['data'])
            # self.dump_ecs()

    def check(self):
        if len(self._ecs_requests)>0:
            log("error  %s %s"%(self.node_id, str(self._ecs_requests)))

    def unicast(self, msg, port):
        n, p = self._topo.get_nextport(self.node_id, port)
        self.all_queue[n].put({
            'type': 'unicast',
            'data': msg,
            'recv_port': p
        })
        # log('unicast finished')

    def flood(self, msg):
        for n,q in self.all_queue.items():
            if n!= self.node_id:
                q.put({
                    'type': 'flood',
                    'data': msg
                })
        # log('flood finished')


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
                # log(self.dump_assemble())
                break
            if msg['type'] == 'mock_trans':
                self.transceiver.on_recv(msg['data'], msg['source'])
            elif msg['type'] == 'local_update':
                self._update_local_rules(msg['rules'])
            elif msg['type'] == 'unicast':
                self._on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type'] == 'flood_neighbor':
                self._on_recv_flood_neighbor(msg['data'])



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



def main1():
    topo = Topology()
    topo.load(DATADIR + '/topo.json')
    qs = {n: Queue() for n in topo.nodes.keys()}
    mocks = {}
    for n in topo.nodes:
        t = MockTransceiver(n, qs, topo)
        mock = MockPushPullECSMgr(n, qs[n], topo, t)
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


def main():
    topo = Topology()
    topo.load(DATADIR+'/topo.json')
    qs = {n : Queue() for n in topo.nodes.keys()}
    ts = {n : MockVerifierThread(n, qs) for n in topo.nodes.keys()}
    processes = []
    for t in ts.values():
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
    main1()
