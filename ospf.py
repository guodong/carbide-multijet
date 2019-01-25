from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, udp, ethernet, ipv4
import json

from core.Space import Space

MULTIJET_IP_PROTO = 33



class Ospf(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Multijet, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def switch_in_handler(self, ev):
        dp = ev.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.dps.append(Datapath(dp))

        # init ospf rules
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
        dp = self.get_dp(ev.msg.datapath)
        # print (ev.msg.to_jsondict())
        rules = []
        for stat in ev.msg.body:
            match = {}
            action = {}
            for k, v in stat.match.items():
                if k == 'in_port':  # ignore in_port currently
                    continue
                match[k] = v

            for inst in stat.instructions:
                for act in inst.actions:
                    if act.type == 0:
                        action['output'] = act.port

            if action['output'] > 999:  # to controller rule
                continue
            rules.append({'match': match, 'action': action})

        dp.set_rules(rules)
        dp.init_ec()

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        dp = self.get_dp(ev.msg.datapath)
        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
        pkt_ip = pkt.get_protocol(ipv4.ipv4)
        if not pkt_ip.proto == MULTIJET_IP_PROTO:
            return
        payload = pkt.protocols[-1]
        print 'received in: ' + str(dp.dp.id)
        print payload
        msg = json.loads(payload)
        if msg['route'][-1] == dp.dp.id:
            return
        dp.calc_ec(in_port, msg['route'], msg['space'])


