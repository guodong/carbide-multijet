import time
import collections

from netaddr import IPSet, IPNetwork
from .topo import Topology
from .transceiver import Transceiver
from .utils import log, debug
# from eventlet import Queue


class EC:
    """  Equivalence Class Item
    currently,  only consider about dst IP prefix, use IPSet class to maintain space
    """
    def __init__(self, route, space):  # type: (tuple, IPSet) -> None
        self.route = route  # (("sw1",2), ("sw1", 3))
        self.space = space  # IPSet("1.0.1.0/24")

    @classmethod
    def empty(cls, route):
        return EC(route, IPSet())

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "{%s <---> %s}"%(str(self.route), str(self.space))


class BaseECSMgr(object):
    """ECS Manager base class
    """
    def __init__(self, node_id, queue, topo, transceiver):
        self._ecs = {}  # type: {tuple: EC}
        self.node_id = node_id  # type: str
        self.queue = queue
        self.topo = topo  # type: Topology
        self.transceiver = transceiver  # type: Transceiver
        transceiver.set_recv_callback(self.on_recv)

    def run(self): raise NotImplementedError

    def on_recv(self, data, source): raise NotImplementedError

    def dump_ecs(self):
        s = "=======dumpecs===%s==============\n"%self.node_id
        for ec in self._ecs.values():
            s += "%s <----> %s\n"%(str(ec.space), str(ec.route))
        s += "============%s==============\n" % self.node_id
        return s


class PushPullECSMgr(BaseECSMgr):
    """ECS Mananger
    """
    def __init__(self, node_id, queue, topo, transceiver):
        super(PushPullECSMgr, self).__init__(node_id, queue, topo, transceiver)
        self._ecs_request_seq = 0
        self._ecs_requests = {}
        self._ecs_changed = False

    def run(self):
        log('start run')
        while True:
            self._ecs_changed = False
            try:
                msg = self.queue.get(timeout=5)
                log('handle one message, start')
                # debug(msg)
            except Exception:
                log(self.dump_ecs())
                log("self.transceiver.dump: %s" % str(self.transceiver.dump()))
                self.check()
                continue
            if msg['type'] == 'local_update':
                self._update_local_rules(msg['rules'])
            elif msg['type'] == 'unicast':
                self._on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type'] == 'flood_neighbor':
                self._on_recv_flood_neighbor(msg['data']['ecs'])
            elif msg['type'] == 'exit':
                return
            else:
                log('error queue message type')
            # debug(self.dump_ecs())
            log('handle one message, end, %s'%('ecs_changed' if self._ecs_changed else 'no_ecs_change'))

    def check(self):
        if len(self._ecs_requests)>0:
            log('error len(self._ecs_requests)=%d'%(len(self._ecs_requests)))
        # for ec in self._ecs.values():
        #     if len(ec.route[-1])==2:
        #         log('error unreachable route %s'%(str(ec)))

    def on_recv(self, obj, source):
        # source  ('unicast', recv_port)   ('flood', )
        if source[0]=='unicast':
            self.queue.put({
                'type': 'unicast',
                'data': obj,
                'recv_port': source[1]
            })
        elif source[0]=='flood_neighbor':
            self.queue.put({
                'type': 'flood_neighbor',
                'data': obj
            })

    def _on_recv_unicast(self, obj, recv_port):
        if obj['type'] == 'REQUEST':
            self._on_recv_ecs_request(obj['seq'], obj['space'], recv_port)
        elif obj['type'] == 'REPLY':
            self._on_recv_ecs_reply(obj['seq'], obj['ecs'])
        else:
            print('unparsed unicast message')

    def _on_recv_ecs_request(self, seq, space, recv_port):
        ec_list = []
        for r, ec in self._ecs.items():
            intersection = ec.space & space
            if len(intersection) > 0:
                ec_list.append(EC(r, intersection))
        self._do_ecs_reply(seq, ec_list, recv_port)

    def _on_recv_ecs_reply(self, seq, ec_list):  # type: (int, [EC]) ->None
        assert seq in self._ecs_requests
        space, fwd_port = self._ecs_requests[seq]
        self._ecs_requests.pop(seq)
        flood_ecs = {}

        for recv_ec in ec_list:  # type: EC
            space -= recv_ec.space
            assert self.topo.get_nexthop(self.node_id, fwd_port) == recv_ec.route[0][0], "error receive route"
            recv_route = ((self.node_id, fwd_port),) + recv_ec.route
            recv_space = recv_ec.space
            self._update_local(recv_route, recv_space)
            t = flood_ecs.setdefault(recv_route, EC.empty(recv_route))
            t.space |= recv_space

        if len(space)>0:
            unknown_route = ((self.node_id, fwd_port),)
            assert unknown_route not in flood_ecs
            flood_ecs[unknown_route] = EC(unknown_route, space)
            self._update_local(unknown_route, space)
        self._do_push_neighbor(list(flood_ecs.values()))

    def _on_recv_flood_neighbor(self, ec_list):
        updated_ecs = {}
        for ec in ec_list:
            l = self._update_remote(ec.route, ec.space)
            for r,s in l:
                ec = updated_ecs.setdefault(r, EC.empty(r))
                ec.space |= s
        if len(updated_ecs)>0:
            self._do_push_neighbor(list(updated_ecs.values()))

    def _do_ecs_reply(self, seq, ec_list, port):
        obj = {
            'type': 'REPLY',
            'seq': seq,
            'ecs': ec_list
        }
        self.transceiver.send(obj, ('unicast', port))

    def _do_pull_request(self, space, fwd_port):  # type: (IPSet, object)->None
        self._ecs_request_seq += 1
        self._ecs_requests[self._ecs_request_seq] = (space, fwd_port)
        obj = {
            'type':'REQUEST',
            'seq': self._ecs_request_seq,
            'space': space
        }
        self.transceiver.send(obj, ('unicast', fwd_port))

    def _do_push_neighbor(self, ec_list):
        obj = {
            'type': 'FLOOD',
            'ecs': ec_list
        }
        self.transceiver.send(obj, ('flood_neighbor', ))

    def _update_local_rules(self, rules):
        # IPSet("1.0.1.0/24"), 1
        flood_ecs = []
        for dst_match, fwd_port in rules:  # type: IPSet, str
            tmp_route = ((self.node_id, fwd_port),)
            if fwd_port is None:
                self._update_local(tmp_route, dst_match)
                flood_ecs.append(EC(tmp_route, dst_match))
            else:
                port_network = self.topo.get_network(self.node_id, fwd_port)
                port_network = IPSet(IPNetwork(port_network).cidr)
                host_route_space = dst_match & port_network
                if len(host_route_space) > 0:
                    host_route = ((self.node_id, fwd_port, "host"),)
                    self._update_local(host_route, host_route_space)
                    flood_ecs.append(EC(host_route, host_route_space))
                    dst_match -= host_route_space
                if len(dst_match)>0:
                    self._do_pull_request(dst_match, fwd_port)
        if len(flood_ecs) > 0:
            self._do_push_neighbor(flood_ecs)

    def _update_local(self, route, space):
        if route[0][1] is None:
            for r, ec in list(self._ecs.items()):
                if len(space & ec.space) > 0:    # NOTE:
                    self._ecs_changed = True

                ec.space -= space
                if len(ec.space) == 0:
                    self._ecs.pop(r)
        else:
            if route not in self._ecs:  # NOTE:
                self._ecs[route] = EC(route, space)
                self._ecs_changed = True
            else:
                ec = self._ecs[route]
                if not space.issubset(ec.space):
                    ec.space.update(space)
                    self._ecs_changed = True

            # self._ecs.setdefault(route, EC(route, IPSet()))
            # self._ecs[route].space |= space
            for r, ec in list(self._ecs.items()):
                if r != route:
                    if len(space & ec.space) > 0:  # NOTE:
                        self._ecs_changed = True

                    ec.space -= space
                    if len(ec.space) == 0:
                        self._ecs.pop(r)

    def _update_remote(self, route, space):
        ret = []
        for r, ec in list(self._ecs.items()):
            r12 = self._route_combine(r, route)
            if r12 is not None:
                changed_space = ec.space & space
                if len(changed_space) > 0:

                    self._ecs_changed = True  # NOTE:

                    ec.space -= changed_space
                    if len(ec.space) == 0:
                        self._ecs.pop(r)
                    ec = self._ecs.setdefault(r12, EC.empty(r12))
                    ec.space |= changed_space
                    ret.append((r12, changed_space))
        return ret

    def _route_combine(self, r1, r2):
        print('r1', r1, 'r2', r2)
        assert len(r1) > 0 and len(r2) > 0 and r1[0][0] != r2[0][0], "format error"
        r2_n = r2[0][0]
        i = 1
        while i < len(r1):
            if r1[i][0] == r2_n:
                break
            i += 1
        if i < len(r1):
            # assert i==1, "format error" TODO:
            if i!=1:
                return None
            if r2[0][1] is None:
                return r1[:i]
            return r1[:i] + r2
        r1_last = r1[-1]
        if len(r1_last) == 2 and self.topo.get_nexthop(r1_last[0], r1_last[1]) == r2_n and r2[0][1] is not None:
            return r1 + r2
        return None


class FloodECSMgr(BaseECSMgr):
    def __init__(self, node_id, queue, topo, transceiver):
        super(FloodECSMgr, self).__init__(node_id, queue, topo, transceiver)
        self._ecs_request_seq = 0
        self._ecs_requests = {}
        self._tmp_save_flood_ecs = {}
        self._last_updated_unknown_next_hosts = set()
        self._fix_last_updated_count = 0
        self._ecs_changed = False

    def run(self):
        log('start run')
        msg = None
        while True:
            self._ecs_changed = False

            if msg is None:
                try:
                    msg = self.queue.get(timeout=5)  # timeout above 1 seconds
                except Exception:
                    log(self.dump_ecs())
                    log("self.transceiver.dump: %s" % str(self.transceiver.dump()))
                    self.check()

                    self._reset_tmp_save_flood_ecs()  # clear _tmp_save_flood_ecs
                    continue

            log('handle one message, start')

            if msg['type'] == 'local_update':
                self.update_local_rules(msg['rules'])
            elif msg['type'] == 'unicast':
                self._on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type'] == 'flood':
                self._on_recv_ecs_flood_all(msg['data'])
            elif msg['type'] == 'exit':
                return
            else:
                log('error queue message type')
            try:
                msg = self.queue.get(timeout=0.00001) # using timeout but not empty-method is to switch to packet receiving thread first
            except Exception:
                self._fix_last_updated_unknown_next_hosts()  # fix ECS with self._tmp_save_flood_ecs, putting it here is to make queue empty first
                msg = None

            log('handle one message, end, %s'%('ecs_changed' if self._ecs_changed else 'no_ecs_change'))

    def _reset_tmp_save_flood_ecs(self):
        self._tmp_save_flood_ecs = {}
        log('reset self._tmp_save_flood_ecs')

    def check(self):
        if len(self._ecs_requests)>0:
            log('error len(self._ecs_requests)=%d' % (len(self._ecs_requests)))
        # for ec in self._ecs.values():
        #     if len(ec.route[-1])==2:
        #         log('error unreachable route %s'%(str(ec)))
        log('self._fix_last_updated_count=%d'%self._fix_last_updated_count)

    def on_recv(self, obj, source):
        # source  ('unicast', recv_port)   ('flood', )
        if source[0]=='unicast':
            self.queue.put({
                'type': 'unicast',
                'data': obj,
                'recv_port': source[1]
            })
        elif source[0]=='flood':
            self.queue.put({
                'type': 'flood',
                'data': obj
            })
        else:
            log('error on_recv message type')

    def _do_ecs_flood_all(self, ec_list): # type: ([EC]) ->None
        obj = {
            'ecs': ec_list,
            'source': self.node_id
        }
        self.transceiver.send(obj, ('flood', ))

    def _do_ecs_request(self, seq, space, fwd_port):  # type: (int, IPSet, object)->None
        obj = {
            'type': 'REQUEST',
            'seq': seq,
            'space': space
        }
        self.transceiver.send(obj, ('unicast', fwd_port))

    def _do_ecs_reply(self, seq, ec_list, fwd_port):
        obj = {
            'type': 'REPLY',
            'seq': seq,
            'ecs': ec_list
        }
        self.transceiver.send(obj, ('unicast', fwd_port))

    def _on_recv_unicast(self, obj, recv_port):
        if obj['type'] == 'REQUEST':
            self._on_recv_ecs_request(obj['seq'], obj['space'], recv_port)
        elif obj['type'] == 'REPLY':
            self._on_recv_ecs_reply(obj['seq'], obj['ecs'])
        else:
            print('unparsed unicast message')

    def _on_recv_ecs_request(self, seq, space, recv_port):
        ec_list = []
        for r, ec in self._ecs.items():
            intersection = ec.space & space
            if len(intersection)>0:
                ec_list.append(EC(r, intersection))
        self._do_ecs_reply(seq, ec_list, recv_port)

    def _on_recv_ecs_reply(self, seq, ec_list):  # type: (int, [EC]) ->None
        assert seq in self._ecs_requests
        space, fwd_port = self._ecs_requests[seq]
        self._ecs_requests.pop(seq)
        flood_ecs = {}

        # end host
        # port_network = self.topo.get_network(self.node_id, fwd_port)  # 1.0.0.1/24
        # port_network = IPSet(IPNetwork(port_network).cidr)
        # host_route_space = space & port_network
        # if len(host_route_space)>0:
        #     host_route = ((self.node_id, fwd_port, "host"),)
        #     self._update_local(host_route, host_route_space)
        #     flood_ecs[host_route] = EC(host_route, host_route_space)
        #     space -= host_route_space

        for recv_ec in ec_list:  # type: EC
            space -= recv_ec.space
            assert self.topo.get_nexthop(self.node_id, fwd_port) == recv_ec.route[0][0], "error receive route"
            recv_route = ((self.node_id, fwd_port),) + recv_ec.route
            recv_space = recv_ec.space
            self._update_local(recv_route, recv_space)
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
            self._update_local(unknown_route, space)
        self._do_ecs_flood_all(list(flood_ecs.values()))

        # self._fix_last_updated_unknown_next_hosts()

    def _fix_last_updated_unknown_next_hosts(self):
        self._fix_last_updated_count += 1
        while len(self._last_updated_unknown_next_hosts) > 0:
            s = self._last_updated_unknown_next_hosts
            self._last_updated_unknown_next_hosts = set()
            for n in s:
                sn_save_dict = self._tmp_save_flood_ecs.get(n)
                if sn_save_dict:
                    now = time.time()
                    for t, ec_list in list(sn_save_dict.items()):
                        if now-t > 500:
                            sn_save_dict.pop(t)
                            log("unexpected timeout")
                        else:
                            ec_list_copy = self._consume_ec_list(ec_list)
                            if len(ec_list_copy)>0:
                                sn_save_dict[t] = ec_list_copy
                            else:
                                sn_save_dict.pop(t)

    def _consume_ec_list(self, ec_list):
        ec_list_copy = list(ec_list)

        for recv_ec in ec_list:
            remained_space = self._update_remote(recv_ec.route, recv_ec.space)
            if len(remained_space) > 0:
                recv_ec.space = remained_space
            else:
                ec_list_copy.remove(recv_ec)

        return ec_list_copy

    def _on_recv_ecs_flood_all(self, obj):  # type: ([EC]) ->None
        ec_list = obj['ecs']

        ec_list_copy = self._consume_ec_list(ec_list)

        if len(ec_list_copy)>0:
            source_node = obj['source']
            sn_save = self._tmp_save_flood_ecs.setdefault(source_node, collections.OrderedDict())
            now = time.time()
            sn_save[now] = ec_list_copy

        # self._fix_last_updated_unknown_next_hosts()

    def _update_local(self, route, space):
        if route[0][1] is None:
            for r, ec in list(self._ecs.items()):
                if len(space & ec.space) > 0:    # NOTE:
                    self._ecs_changed = True

                ec.space -= space
                if len(ec.space) == 0:
                    self._ecs.pop(r)
        else:
            if route not in self._ecs:  # NOTE:
                self._ecs[route] = EC(route, space)
                self._ecs_changed = True
            else:
                ec = self._ecs[route]
                if not space.issubset(ec.space):
                    ec.space.update(space)
                    self._ecs_changed = True

            # self._ecs.setdefault(route, EC(route, IPSet()))
            # self._ecs[route].space |= space
            for r, ec in list(self._ecs.items()):
                if r!= route:
                    if len(space & ec.space) > 0:  # NOTE:
                        self._ecs_changed = True

                    ec.space -= space
                    if len(ec.space) == 0:
                        self._ecs.pop(r)

            if len(route[-1]) == 2:
                n = self.topo.get_nexthop(route[-1][0], route[-1][1])
                self._last_updated_unknown_next_hosts.add(n)

    def _update_remote(self, route, space):

        for r, ec in list(self._ecs.items()):
            r12 = self._route_combine(r, route)
            if r12 is not None and r12 != r:
                # if r12[-1][1] is None:
                #     log('route=%s space=%s  r=%s r12=%s'%(str(route), str(space), str(r), str(r12)))
                changed_space = ec.space & space
                if len(changed_space) > 0:

                    self._ecs_changed = True # NOTE:

                    space -= changed_space

                    ec.space -= changed_space

                    if len(ec.space)==0:
                        self._ecs.pop(r)
                    ec = self._ecs.setdefault(r12, EC.empty(r12))
                    ec.space |= changed_space

                    if len(r12[-1]) == 2:
                        n = self.topo.get_nexthop(r12[-1][0], r12[-1][1])
                        self._last_updated_unknown_next_hosts.add(n)

        return space

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
        # assert self._topo.get_nexthop(r1_last[0], r1_last[1]) is not None
        if len(r1_last)==2 and self.topo.get_nexthop(r1_last[0], r1_last[1])==r2_n and r2[0][1] is not None:
            return r1 + r2
        return None

    def update_local_rules(self, rules):
        # IPSet("1.0.1.0/24"), 1

        # v1 code
        # for dst_match, fwd_port in rules:  # type: IPSet, str
        #     tmp_route = ((self.node_id, fwd_port),)
        #     if fwd_port is None:
        #         # for route, ec in self._ecs:
        #         #     ec.space -= dst_match
        #         # self.do_ecs_flood_all([EC(tmp_route, dst_match)])
        #         self._update_local(tmp_route, dst_match)
        #         self._do_ecs_flood_all([EC(tmp_route, dst_match)])
        #     else:
        #         self._ecs_request_hold(dst_match, fwd_port)

        # v2 code
        flood_ecs = []
        for dst_match, fwd_port in rules:  # type: IPSet, str
            tmp_route = ((self.node_id, fwd_port),)
            if fwd_port is None:
                self._update_local(tmp_route, dst_match)
                flood_ecs.append(EC(tmp_route, dst_match))
            else:
                port_network = self.topo.get_network(self.node_id, fwd_port)
                # if(port_network is None):
                print(self.node_id, fwd_port)
                print('port_network',port_network)
                port_network = IPSet(IPNetwork(port_network).cidr)
                host_route_space = dst_match & port_network
                if len(host_route_space) > 0:
                    host_route = ((self.node_id, fwd_port, "host"),)
                    self._update_local(host_route, host_route_space)
                    flood_ecs.append(EC(host_route, host_route_space))
                    dst_match -= host_route_space
                if len(dst_match) > 0:
                    self._ecs_request_hold(dst_match, fwd_port)
        if len(flood_ecs) > 0:
            self._do_ecs_flood_all(flood_ecs)

    def _ecs_request_hold(self, space, fwd_port):
        self._ecs_request_seq += 1
        self._ecs_requests[self._ecs_request_seq] = (space, fwd_port)
        self._do_ecs_request(self._ecs_request_seq, space, fwd_port)