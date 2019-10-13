import json
import os, platform
from Queue import Queue

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.lib.packet import packet, ipv4
from ryu.ofproto import ofproto_v1_3

from trigger_server import TriggerServer
from verifier import Verifier
from utils import log


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

        self.msg_buf = {}

        '''
        add more cps here to start multi verify threads
        '''
        self.cps = [100]

        self.queue = Queue()
        for cp in self.cps:
            verifier = Verifier(int(cp), queue=self.queue)
            self.verifiers[int(cp)] = verifier
            verifier.start()

    def on_trigger(self, type='get_rules', comps=None):
        if type == 'get_rules':
            parser = self.dp.ofproto_parser
            log('start fetch rules')
            self.dp.send_msg(parser.OFPFlowStatsRequest(datapath=self.dp))
        elif type == 'verify':
            for cp in self.cps:
                msg = {
                    'cpid': cp,
                    'data': {
                        'type': 'verify'
                    }
                }
            self.queue.put(msg)
        elif type == 'add_rule':
            cp = int(comps['cp'][0])
            rule = json.loads(comps['rule'][0])
            msg = {
                'cpid': cp,
                'data': {
                    'type': 'update_add_rule',
                    'rule': rule
                }
            }
            print msg
            self.queue.put(msg)

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def switch_in_handler(self, ev):
        print 'comming switch'
        dp = ev.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.dp = dp
        # self.dps.append(Datapath(dp))

        for v in self.verifiers.values():
            v.dp = dp

        # init verify msg rules
        ofmatch = parser.OFPMatch(eth_type=2048, ip_proto=Verifier.MULTIJET_IP_PROTO)
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

        for cpid, rlist in rules.items():
            msg = {
                'cpid': cpid,
                'data': {
                    'type': 'add_rules',
                    'rules': rlist
                }
            }
            if cpid == 100:
                with open('/common/ospf'+str(platform.node())+'.json', 'w') as f:
                    json.dump(rlist, f, indent=2)
            self.queue.put(msg)

        log('finish fetch rules')

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
        pkt_ip = pkt.get_protocol(ipv4.ipv4)
        if not pkt_ip.proto == Verifier.MULTIJET_IP_PROTO:
            return
        payload = pkt.protocols[-1]
        msg = json.loads(payload)
        if not self.msg_buf.has_key(msg['seq']):
            self.msg_buf[msg['seq']] = []

        self.msg_buf[msg['seq']].append(msg['data'])

        if len(self.msg_buf[msg['seq']]) == msg['count']:
            payload = ''.join(self.msg_buf[msg['seq']])
            log('received from ' + str(in_port) + ': ' + payload[:100])

            parsed = json.loads(payload)
            parsed['in_port'] = in_port

            self.queue.put(parsed)
