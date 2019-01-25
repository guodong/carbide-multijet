import json
import os
from Queue import Queue

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.lib.packet import packet, ipv4
from ryu.ofproto import ofproto_v1_3

from trigger_server import TriggerServer
from verifier import Verifier
from utils import log

MULTIJET_IP_PROTO = 143


class Multijet(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Multijet, self).__init__(*args, **kwargs)
        self.dp = None
        '''
        the verifiers is a thread dict of cpid=>verify_thread
        '''
        self.verifiers = {}
        # f = FlowServer()
        # f.start()
        t = TriggerServer(self.on_trigger)
        t.start()

        '''
        add more cps here to start multi verify threads
        '''
        cps = [100]

        self.queue = Queue()
        for cp in cps:
            verifier = Verifier(int(cp), queue=self.queue)
            self.verifiers[int(cp)] = verifier
            verifier.start()

    def on_trigger(self, type='get_rules'):
        if type == 'get_rules':
            parser = self.dp.ofproto_parser
            self.dp.send_msg(parser.OFPFlowStatsRequest(datapath=self.dp))
        elif type == 'verify':
            msg = {'type': 'verify'}
            self.queue.put(msg)

    def get_dp(self, dp):
        for d in self.dps:
            if dp == d.dp:
                return d
        return None

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def switch_in_handler(self, ev):
        dp = ev.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.dp = dp
        # self.dps.append(Datapath(dp))

        for v in self.verifiers.values():
            v.dp = dp

        # init verify msg rules
        ofmatch = parser.OFPMatch(eth_type=2048, ip_proto=MULTIJET_IP_PROTO)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        msg = parser.OFPFlowMod(datapath=dp, priority=44444, match=ofmatch,
                                command=ofp.OFPFC_ADD,
                                flags=ofp.OFPFF_SEND_FLOW_REM,
                                instructions=inst)
        dp.send_msg(msg)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        # print (ev.msg.to_jsondict())
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

            msg = {
                'type': 'add_rule',
                'cpid': stat.table_id,
                'rule': {
                    'match': match,
                    'action': action
                }
            }
            self.queue.put(msg)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
        pkt_ip = pkt.get_protocol(ipv4.ipv4)
        if not pkt_ip.proto == MULTIJET_IP_PROTO:
            return
        payload = pkt.protocols[-1]
        log('received from ' + str(in_port) + ': ' + payload)
        msg = json.loads(payload)
        if msg['route'][-1] == self.dp.id:
            return
        m = {
            'type': 'ec',
            'in_port': in_port,
            'route': msg['route'],
            'space': msg['space']
        }
        self.queue.put(m)
