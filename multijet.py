from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, udp, ethernet, ipv4
import json

from core.Space import Space

MULTIJET_IP_PROTO = 143


class Datapath:
    def __init__(self, dp):
        self.dp = dp
        self.rules = []
        self.forward_rules = {}
        self.ecs = []

    def set_rules(self, rules):
        self.rules = rules
        self.build_space()

    def build_space(self):
        for rule in self.rules:
            if not self.forward_rules.has_key(rule['action']['output']):
                self.forward_rules[rule['action']['output']] = Space()
            self.forward_rules[rule['action']['output']].plus(Space(match=rule['match']))

        # for port, fr in self.forward_rules.items():
        #     print port
        #     print json.dumps(fr.areas)

    def init_ec(self):
        msg = {
            'type': 'init',
            'route': [self.dp.id],
            'space': [''.ljust(336, '*')]
        }
        self.flood(json.dumps(msg))

    def calc_ec(self, in_port, route, areas):
        if not self.forward_rules.has_key(in_port):
            return
        space = Space(areas=areas)
        space.multiply(self.forward_rules[in_port])
        if len(space.areas) == 0:
            return
        route.insert(0, self.dp.id)
        self.ecs.append({'route': route, 'space': space})
        msg = {
            'type': 'flood',
            'route': route,
            'space': space.areas
        }
        if len(space.areas) > 0:
            self.flood(json.dumps(msg), in_port)

        self.dump_ecs()

    def flood(self, msg, except_port=None):
        p = packet.Packet()
        eth_header = ethernet.ethernet()
        p.add_protocol(eth_header)
        ip_header = ipv4.ipv4(proto=MULTIJET_IP_PROTO)
        ip_header.serialize(msg, eth_header)
        p.add_protocol(ip_header)
        p.add_protocol(msg)

        ofp = self.dp.ofproto
        parser = self.dp.ofproto_parser
        print ip_header.dst
        p.serialize()
        data = p.data
        actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        if except_port is None:
            except_port = ofp.OFPP_CONTROLLER
        out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=except_port,
                                  actions=actions, data=data)
        self.dp.send_msg(out)

    def dump_ecs(self):
        print 'ecs of: ' + str(self.dp.id)
        for ec in self.ecs:
            print ec['route']
            ec['space'].dump()
        print 'count: ' + str(len(self.ecs))

    def add_flow(self, priority, match, actions, buffer_id=None):
        ofproto = self.dp.ofproto
        parser = self.dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=self.dp, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=self.dp, priority=priority,
                                    match=match, instructions=inst)
        self.dp.send_msg(mod)


class Multijet(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Multijet, self).__init__(*args, **kwargs)
        self.dps = []

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
        self.dps.append(Datapath(dp))

        dp.send_msg(parser.OFPFlowStatsRequest(datapath=dp))

        # init fly server pkt rules
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
            if stat.table_id < 10:  # cp tables id larger than 10
                continue
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
