import pickle
import zlib

from netaddr import IPSet, IPNetwork
from .topo import Topology


class EC:
    def __init__(self, route, space):  # type: (tuple, IPSet) -> None
        self.route = route  # (("sw1",2), ("sw1", 3))
        self.space = space  # IPSet("1.0.1.0/24")

    @classmethod
    def empty(cls, route):
        return EC(route, IPSet())


class ECSMgr:
    def __init__(self, node_id, topo):
        self._ecs = {}  # type: {tuple: EC}
        self.node_id = node_id
        self._topo = topo  # type: Topology
        # self._local_rules = {}
        self._ecs_request_seq = 0
        self._ecs_requests = {}

    def do_ecs_flood_all(self, ec_list): # type: ([EC]) ->None
        raise NotImplementedError

    def do_ecs_request(self, seq, space, fwd_port):  # type: (int, IPSet, object)->None
        raise NotImplementedError

    def do_ecs_reply(self, seq, ec_list, fwd_port):
        raise NotImplementedError

    def on_recv_ecs_request(self, seq, space, recv_port):
        ec_list = []
        for r, ec in self._ecs.items():
            intersection = ec.space & space
            if len(intersection)>0:
                ec_list.append(EC(r, intersection))
        self.do_ecs_reply(seq, ec_list, recv_port)

    def on_recv_ecs_reply(self, seq, ec_list):  # type: (int, [EC]) ->None
        assert seq in self._ecs_requests
        space, fwd_port = self._ecs_requests[seq]
        self._ecs_requests.pop(seq)
        flood_ecs = {}

        # end host
        port_network = self._topo.get_network(self.node_id, fwd_port)  # 1.0.0.1/24
        port_network = IPSet(IPNetwork(port_network).cidr)
        host_route_space = space & port_network
        if len(host_route_space)>0:
            host_route = ((self.node_id, fwd_port, "host"),)
            self._update_ecs(host_route, host_route_space)
            flood_ecs[host_route] = EC(host_route, host_route_space)
            space -= host_route_space

        for recv_ec in ec_list:  # type: EC
            space -= recv_ec.space
            assert self._topo.get_nexthop(self.node_id, fwd_port) == recv_ec.route[0][0], "error receive route"
            recv_route = ((self.node_id, fwd_port),) + recv_ec.route
            recv_space = recv_ec.space
            self._update_ecs(recv_route, recv_space)
            if recv_route in flood_ecs:
                flood_ecs[recv_route].space |= recv_space
            else:
                flood_ecs[recv_route] = EC(recv_route, recv_space)
            # ur, us = self._update_ecs(recv_route, recv_space)
            # flood_ecs.setdefault(ur, EC(ur, us))
            # flood_ecs[ur].space |= us

        if len(space)>0:
            unknown_route = ((self.node_id, fwd_port),)
            assert unknown_route not in flood_ecs
            flood_ecs[unknown_route] = EC(unknown_route, space)
            self._update_ecs(unknown_route, space)
        self.do_ecs_flood_all(list(flood_ecs.values()))

    def on_recv_ecs_flood_all(self, ec_list):  # type: ([EC]) ->None
        for recv_ec in ec_list:
            self._update_ecs(recv_ec.route, recv_ec.space)

    def _update_ecs(self, route, space):
        # route:  ((self.node_id, None),  )  or None  ->   delete route space
        #           (xxx, yyy)  -> update route space
        assert len(route)>0
        if route[0][0] == self.node_id:
            self._update_local(route, space)
        else:
            self._update_remote(route, space)

    def _update_local(self, route, space):
        if route[0][1] is None:
            # deleted_space = IPSet()
            for r, ec in list(self._ecs.items()):
                # intersection = ec.space & space
                # deleted_space |= intersection
                ec.space -= space
                if len(ec.space) == 0:
                    self._ecs.pop(r)
            # return ((self.node_id, None), ), deleted_space
        else:
            self._ecs.setdefault(route, EC(route, IPSet()))
            self._ecs[route].space |= space
            for r, ec in list(self._ecs.items()):
                if r!= route:
                    ec.space -= space
                    if len(ec.space) == 0:
                        self._ecs.pop(r)
            # return route, space

    def _update_remote(self, route, space):
        for r, ec in list(self._ecs.items()):
            r12 = self._route_combine(r, route)
            if r12 is not None:
                changed_space = ec.space & space
                if len(changed_space)>0:
                    ec.space-=changed_space
                    if len(ec.space)==0:
                        self._ecs.pop(r)
                    ec = self._ecs.setdefault(r12, EC.empty(r12))
                    ec.space |= changed_space

    def _route_combine(self, r1, r2):
        assert len(r1) > 0 and len(r2) > 0 and r1[0][0] != r2[0][0], "format error"
        r2_n = r2[0][0]
        i = 1
        while i<len(r1):
            if r1[i][0]==r2_n:
                break
            i+=1
        if i<len(r1):
            if r2[0][1] is None:
                return r1[:i]
            return r1[:i] + r2
        r1_last = r1[-1]
        if len(r1_last)==2 and self._topo.get_nexthop(r1_last[0], r1_last[1])==r2_n:
            return r1 + r2
        return None

    def update_local_rules(self, rules):
        # IPSet("1.0.1.0/24"), 1
        for dst_match, fwd_port in rules:  # type: IPSet, str
            tmp_route = ((self.node_id, fwd_port),)
            if fwd_port is None:
                # for route, ec in self._ecs:
                #     ec.space -= dst_match
                # self.do_ecs_flood_all([EC(tmp_route, dst_match)])
                self._update_ecs(tmp_route, dst_match)
                self.do_ecs_flood_all([EC(tmp_route, dst_match)])
            else:
                self._ecs_request_hold(dst_match, fwd_port)

    def _ecs_request_hold(self, space, fwd_port):
        self._ecs_request_seq += 1
        self._ecs_requests[self._ecs_request_seq] = (space, fwd_port)
        self.do_ecs_request(self._ecs_request_seq, space, fwd_port)

    def dump_ecs(self):
        s = "============%s==============\n"%self.node_id
        for ec in self._ecs.values():
            s += "%s <----> %s\n"%(str(ec.space), str(ec.route))
        s += "============%s==============\n" % self.node_id
        return s


class ECSMgrPickle(ECSMgr):
    def do_ecs_flood_all(self, ec_list):
        pickled = pickle.dumps(ec_list, protocol=-1)
        data = zlib.compress(pickled)
        self.flood(data)

    def do_ecs_request(self, seq, space, fwd_port):
        obj = {
            'type': 'REQUEST',
            'seq': seq,
            'space': space
        }
        pickled = pickle.dumps(obj, protocol=-1)
        data = zlib.compress(pickled)
        self.unicast(data, fwd_port)

    def do_ecs_reply(self, seq, ec_list, fwd_port):
        obj = {
            'type': 'REPLY',
            'seq': seq,
            'ecs': ec_list
        }
        pickled = pickle.dumps(obj, protocol=-1)
        data = zlib.compress(pickled)
        self.unicast(data, fwd_port)

    def on_recv_unicast(self, data, recv_port):
        pickled = zlib.decompress(data)
        obj = pickle.loads(pickled)
        if obj['type'] == 'REQUEST':
            self.on_recv_ecs_request(obj['seq'], obj['space'], recv_port)
        elif obj['type'] == 'REPLY':
            self.on_recv_ecs_reply(obj['seq'], obj['ecs'])
        else:
            print('unparsed unicast message')

    def on_recv_flood(self, data):
        pickled = zlib.decompress(data)
        obj = pickle.loads(pickled)
        self.on_recv_ecs_flood_all(obj)

    def unicast(self, msg, port):
        raise NotImplementedError

    def flood(self, msg):
        raise NotImplementedError
