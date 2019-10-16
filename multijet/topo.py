import json


class Topology:
    def __init__(self):
        self.nodes = {} # id : {port_num:  {'name': ' ',  }}
        self.links = {}

    def load(self, path):
        with open(path) as f:
            topo = json.load(f)
            self.nodes = {str(n): {int(p): pa for p,pa in a.items()}  for n,a in topo['nodes'].items()}
            for np1,np2 in topo['links']:
                n1, p1 = str(np1[0]), int(np1[1])
                n2, p2 = str(np2[0]), int(np2[1])
                self.links[(n1, p1)] = (n2, p2)
                # self.links[(n2, p2)] = (n1, p1)

    def save(self, path):
        with open(path, 'w') as f:
            json.dump({'nodes': self.nodes, 'links': list(self.links.items())}, f, indent=2)
            
    def get_network(self, node_id, port_num):
        n = self.nodes.get(str(node_id))
        if not n:
            return 'ERROR NODE'
        pattr = n.get(port_num)
        if not pattr:
            return 'ERROR PORT'
        if 'fip' in pattr:
            return pattr['fip']
        if 'ip' in pattr:
            return pattr['ip']
        return 'ERROR'

    def get_nexthop(self, node_id, port_num):
        port = str(node_id), int(port_num)
        p2 = self.links.get(port)
        if p2:
            return p2[0]
        else:
            return None

    def get_nextport(self, node_id, port_num):
        port = str(node_id), int(port_num)
        p2 = self.links.get(port)
        return p2

    def get_neighbor(self, node_id):
        nodes = set()
        for src, dst in self.links.items():
            if str(src[0])==str(node_id):
                nodes.add(dst[0])
        return list(nodes)

    def spanning_tree(self):
        flags = {n: False for n in self.nodes.keys()}
        spanning_tree_ports = {n: [] for n in self.nodes.keys()}
        while True:
            selected = []
            for n,f in flags.items():
                if not f:
                    selected.append(n)
                    flags[n]=True
                    break
            if not selected:
                break
            while True:
                mn = None
                for n1_id in selected:
                    n1 = self.nodes[n1_id]
                    for p1 in n1.keys():
                        port1 = (n1_id, p1)
                        port2 = self.links.get(port1)
                        if port2 and flags[port2[0]]==False:  # no weight
                            mn = port1, port2
                            break
                    if mn is not None:
                        break
                if mn is None:
                    break
                flags[mn[1][0]]=True
                selected.append(mn[1][0])
                spanning_tree_ports[mn[0][0]].append(mn[0][1])
                spanning_tree_ports[mn[1][0]].append(mn[1][1])
        return spanning_tree_ports