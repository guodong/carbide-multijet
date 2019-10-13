import json
from Queue import Queue
from threading import Thread

from netaddr import IPSet
from utils import log
from .ecs_mgr import ECSMgrPickle
from .topo import Topology

# DATADIR = 'configs/common'
DATADIR = 'results/common'

class MockVerifierThread(Thread, ECSMgrPickle):

    def __init__(self, node_id, queue):
        topo = Topology()
        topo.load(DATADIR+'/topo.json')
        ECSMgrPickle.__init__(self, node_id, topo)
        Thread.__init__(self)
        self.all_queue = None
        self.queue = queue

    def run(self):
        while True:
            msg = self.queue.get()
            # log(msg)
            if msg['type']=='local_update':
                self.update_local_rules(msg['rules'])
            elif msg['type']=='unicast':
                self.on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type']=='flood':
                self.on_recv_flood(msg['data'])
            self.dump_ecs()

    def unicast(self, msg, port):
        n, p = self._topo.get_nextport(self.node_id, port)
        self.all_queue[n].put({
            'type': 'unicast',
            'data': msg,
            'recv_port': p
        })
        log('unicast finished')

    def flood(self, msg):
        for n,q in self.all_queue.items():
            if n!= self.node_id:
                q.put({
                    'type': 'flood',
                    'data': msg
                })
        log('flood finished')


def load_rules(n):
    rules = {}
    with open(DATADIR+'/ospf%s.json'%str(n)) as f:
        obj = json.load(f)
        for flow in obj:
            ip, mask = flow['match']['ipv4_dst']
            output = int(flow['action']['output'])
            space = IPSet([ip+'/24'])
            rules.setdefault(output, IPSet())
            rules[output] |= space
    return [(space, port) for port,space in rules.items()]

def main():
    topo = Topology()
    topo.load(DATADIR+'/topo.json')
    qs = {n : Queue() for n in topo.nodes.keys()}
    ts = {n : MockVerifierThread(n, qs[n]) for n in topo.nodes.keys()}
    for t in ts.values():
        t.all_queue = qs
        t.start()
    for n in topo.nodes.keys():
        rules = load_rules(n)
        log(rules)
        qs[n].put({
            'type': 'local_update',
            'rules': rules
        })
    
    for t in ts.values():
        t.join()


if __name__=='__main__':
    main()
