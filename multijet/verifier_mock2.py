import json
from multiprocessing import Process, Queue

from netaddr import IPSet
from utils import log
from .ecs_mgr import ECSMgrPickle
from .topo import Topology

DATADIR = 'configs/common'
# DATADIR = 'results/common'


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
                return
            if msg['type']=='local_update':
                self.update_local_rules(msg['rules'])
            elif msg['type']=='unicast':
                self.on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type']=='flood':
                self.on_recv_flood(msg['data'])
            # self.dump_ecs()

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
    ts = {n : MockVerifierThread(n, qs) for n in topo.nodes.keys()}
    processes = []
    for t in ts.values():
        proc = Process(target=t.run)
        proc.start()
        processes.append(proc)
    for n in topo.nodes.keys():
        rules = load_rules(n)
        log(rules)
        qs[n].put({
            'type': 'local_update',
            'rules': rules
        })
    
    for t in processes:
        t.join()


if __name__=='__main__':
    main()
