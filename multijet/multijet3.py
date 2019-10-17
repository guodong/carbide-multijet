import json
import struct
import platform

from eventlet import Queue
from netaddr import IPSet
from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import WSGIApplication
from ryu.app.wsgi import route
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.lib.hub import spawn
from ryu.lib.packet import packet, ethernet, ipv4
from ryu.ofproto import ofproto_v1_3

from utils import log, debug
from transceiver import Transceiver, build_transceiver
from ecs_mgr import PushPullECSMgr
from topo import Topology


def load_rules(n):
    rules = {}
    with open('/common/ospf%s.json'%str(n)) as f:
        obj = json.load(f)
        for flow in obj:
            ip, mask = flow['match']['ipv4_dst']
            output = int(flow['action']['output'])
            space = IPSet([ip+'/24'])
            rules.setdefault(output, IPSet())
            rules[output] |= space
    return [(space, port) for port,space in rules.items()]


class MultijetServer(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(MultijetServer, self).__init__(req, link, data, **config)
        self._app = data['app']

    @route('test', '/hello', methods=['GET'])
    def hello(self, req, **kwargs):
        return 'hello'

    @route('test', '/test', methods=['GET'])
    def test(self, req, **kwargs):
        self._app.on_trigger('test')
        return 'ok'


class PacketTransceiver(Transceiver):
    UNICAST = 144
    FLOOD_NEIGHBOR = 143
    FLOOD = 145

    def __init__(self, dp, flood_ports):
        super(PacketTransceiver, self).__init__()
        self._dp = dp
        self._flood_ports = flood_ports

    def send(self, data, target):
        ofp = self._dp.ofproto
        parser = self._dp.ofproto_parser
        if target[0]=='unicast':
            port = target[0]
            actions = [parser.OFPActionOutput(port)]
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.UNICAST)
            ip_header.serialize(data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(data)
            p.serialize()
            data = p.data
            out = parser.OFPPacketOut(datapath=self._dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions, data=data)
            self._dp.send_msg(out)
        elif target[0]=='flood_neighbor':
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.FLOOD_NEIGHBOR)
            ip_header.serialize(data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(data)
            p.serialize()
            data = p.data
            actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
            out = parser.OFPPacketOut(datapath=self._dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions, data=data)
            self._dp.send_msg(out)
        elif target[0]=='flood':
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.FLOOD_NEIGHBOR)
            ip_header.serialize(data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(data)
            p.serialize()
            data = p.data
            actions = [parser.OFPActionOutput(int(port)) for port in self._flood_ports]
            out = parser.OFPPacketOut(datapath=self._dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions, data=data)
            self._dp.send_msg(out)
        else:
            log('error send packet')

    def on_recv(self, pkt, in_port):
        pkt_ip = pkt.get_protocol(ipv4.ipv4)
        if not pkt_ip:
            return
        if pkt_ip.proto == self.UNICAST:
            in_port = ('unicast', in_port)
        elif pkt_ip.proto == self.FLOOD_NEIGHBOR:
            in_port = ('flood_neighbor',)
        elif pkt_ip.proto == self.FLOOD:
            in_port = ('flood',)
        else:
            return
        payload = pkt.protocols[-1]
        self._recv_callback(payload, in_port)


class Multijet3(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        'wsgi': WSGIApplication,
    }

    def __init__(self, *args, **kwargs):
        super(Multijet3, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(MultijetServer, {'app': self})
        self._dp = None
        self._verifiers = {}
        self._qs = {}
        self._cps = [100]
        self._node_id = platform.node()
        topo = Topology()
        topo.load('/common/topo.json')
        self._topo = topo
        self._pkt_trans = None

        with open('/common/spanningtree.json') as f:
            _spanning_tree = json.load(f)
            self._flood_ports = _spanning_tree[self._node_id]

    def on_trigger(self, cmd):
        if cmd == 'test':
            log('test start')
            rules = load_rules(self._node_id)
            self._qs[100].put({
                'type': 'local_update',
                'rules': rules
            })

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def switch_in_handler(self, ev):
        if self._dp is not None:
            return  # TODO
        log('comming switch')
        dp = ev.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self._dp = dp
        pkt_trans = PacketTransceiver(dp, self._flood_ports)
        demux, trans = build_transceiver(self._cps, pkt_trans)
        for cpid in self._cps:
            q = Queue()
            self._qs[cpid] = q
            v = PushPullECSMgr(self._node_id, q, self._topo, trans[cpid])
            spawn(v.run)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        # print (ev.msg.to_jsondict())
        rules = {}  # cpid => rules
        for stat in ev.msg.body:
            if stat.table_id < 10:  # cp tables id larger than 10
                continue
            match = {}
            action = {}
            for k, v in stat.match.items():
                if k == 'in_port':  # ignore in_port field currently
                    continue
                match[k] = v

            for inst in stat.instructions:
                for act in inst.actions:
                    if act.type == 0:
                        action['output'] = act.port

            if action['output'] > 999:  # to controller rule
                continue

            if not rules.has_key(stat.table_id):
                rules[stat.table_id] = []

            rules[stat.table_id].append({'match': match, 'action': action})

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        debug("recv packet")
        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
        self._pkt_trans.on_recv(pkt, in_port)