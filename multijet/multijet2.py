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
from ryu.lib.packet import packet, ipv4
from ryu.ofproto import ofproto_v1_3

from verifier2 import Verifier2
from utils import log, debug


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


class Multijet2(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        'wsgi': WSGIApplication,
    }

    def __init__(self, *args, **kwargs):
        super(Multijet2, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(MultijetServer, {'app': self})
        self._dp = None
        self._verifiers = {}
        self._qs = {}
        self._cps = [100]

    def on_trigger(self, cmd):
        if cmd == 'test':
            log('test start')
            rules = load_rules(platform.node())
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
        for cpid in self._cps:
            q = Queue()
            self._qs[cpid] = q
            v = self._verifiers[cpid] = Verifier2(cpid, dp, q)
            spawn(v.run)

        # init verify msg rules
        # ofmatch = parser.OFPMatch(eth_type=2048, ip_proto=MULTIJET_IP_PROTO)
        # actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        # inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        # msg = parser.OFPFlowMod(datapath=dp, priority=44444, match=ofmatch,
        #                         command=ofp.OFPFC_ADD,
        #                         flags=ofp.OFPFF_SEND_FLOW_REM,
        #                         instructions=inst)
        # dp.send_msg(msg)

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

        # for cpid, rlist in rules.items():
        #     msg = {
        #         'cpid': cpid,
        #         'data': {
        #             'type': 'add_rules',
        #             'rules': rlist
        #         }
        #     }
        #     if cpid == 100:
        #         with open('/common/ospf'+str(platform.node())+'.json', 'w') as f:
        #             json.dump(rlist, f, indent=2)
        #     self.queue.put(msg)
        #
        # log('finish fetch rules')

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        debug("recv packet")
        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
        pkt_ip = pkt.get_protocol(ipv4.ipv4)
        if not pkt_ip:
            return
        if pkt_ip.proto == Verifier2.MULTIJET_IP_UNICAST_PROTO \
                or pkt_ip.proto == Verifier2.MULTIJET_IP_FLOOD_PROTO:
            payload = pkt.protocols[-1]
            cpid = struct.unpack_from("I", payload)[0]
            debug(cpid)
            verifier = self._verifiers.get(cpid)
            if verifier:
                debug('reassemble')
                verifier.reassemble(in_port, pkt_ip.proto, payload)