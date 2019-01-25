import json, threading, time, socket, platform

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.ofproto import ofproto_v1_3

from core.control_plane import ControlPlane
from fpm.fpm import Fpm
from server import Server
from ryu.lib.packet import packet, udp, ethernet, ipv4

lock = threading.Lock()

initializer = False

class Multijet(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Multijet, self).__init__(*args, **kwargs)
        self.dp = None
        self.cps = {
            10: ControlPlane(10),  # sdn
            100: ControlPlane(100)  # ospf
        }

        self.ecs = []

        # start trigger server
        t = threading.Thread(target=self.trigger_server)
        t.setDaemon(True)
        t.start()

    # called when ospf fpm add route
    def on_add_route(self, match, acts):
        global lock
        ofp = self.dp.ofproto
        parser = self.dp.ofproto_parser
        ofmatch = self.dp.ofproto_parser.OFPMatch(**match)
        actions = []
        for k, v in acts.items():
            if k == 'mod_dl_dst':
                actions.append(parser.OFPActionSetField(eth_dst=v))

        actions.append(parser.OFPActionOutput(int(acts['output'])))

        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        # add ospf rule to table 100
        msg = self.dp.ofproto_parser.OFPFlowMod(datapath=self.dp, table_id=100, match=ofmatch, cookie=0,
                                                command=ofp.OFPFC_ADD,
                                                idle_timeout=0, hard_timeout=0, flags=ofp.OFPFF_SEND_FLOW_REM,
                                                instructions=inst)

        lock.acquire()
        self.dp.send_msg(msg)
        time.sleep(0.2)  # seems lost msg without sleep
        lock.release()

        self.cps[100].add_rule(match, {'output': int(acts['output'])})

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def switch_in_handler(self, ev):
        dp = ev.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        self.dp = dp

        dp.send_msg(parser.OFPFlowStatsRequest(datapath=dp))

        # init fly server pkt rules
        ofmatch = parser.OFPMatch(eth_type=2048, ip_proto=17, udp_dst=9999)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        msg = self.dp.ofproto_parser.OFPFlowMod(datapath=self.dp, priority=44444, match=ofmatch,
                                                command=ofp.OFPFC_ADD,
                                                flags=ofp.OFPFF_SEND_FLOW_REM,
                                                instructions=inst)
        dp.send_msg(msg)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        # start fpm server
        print 'starting fpm server'
        fpm = Fpm()
        fpm.on_add_route = self.on_add_route
        t = threading.Thread(target=fpm.start)
        t.setDaemon(True)
        t.start()

        print json.dumps(ev.msg.to_jsondict())

        for stat in ev.msg.body:
            if stat.table_id < 10:  # cp tables id larger than 10
                continue

            if self.cps.has_key(stat.table_id):
                match = {}
                action = {}
                for k, v in stat.match.items():
                    match[k] = v

                for inst in stat.instructions:
                    for act in inst.actions:
                        if act.type == 0:
                            action['output'] = act.port

                print match, action

                self.cps[stat.table_id].add_rule(match, action)


    def fly(self):
        server = Server()
        # server.on_peer_notify = self.on_peer_notify
        server.start()

    # def on_peer_notify(self, cp, property, space):
    #     self.cps[int(cp)].calc_property_space(property, space)

    def trigger_server(self):
        ip_port = ('0.0.0.0', 8888)
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(ip_port)
        while True:
            data, client = server.recvfrom(4096)
            print 'trigger: %d' % int(time.time() * 1000000)
            print('recv: ', len(data), client[0], data)
            data = data.replace('\n', '')  # remove the last \n
            action = data.split(':')[0]
            if action == 't':  # trigger verify
                initializer = True
                msg_to_send = {
                    'type': 'pm',
                    'protocol': 100,
                    'property': 'reach:h2',
                    'space': self.cps[100].frules[1].areas
                    # 'space': [''.rjust(336, '*')]
                }
                p = packet.Packet()
                p.add_protocol(ethernet.ethernet())
                ipheader = ipv4.ipv4(proto=17)
                p.add_protocol(ipheader)
                u = udp.udp(dst_port=9999)
                u.serialize(json.dumps(msg_to_send), ipheader)
                p.add_protocol(u)
                p.add_protocol(json.dumps(msg_to_send))

                ofp = self.dp.ofproto
                parser = self.dp.ofproto_parser
                p.serialize()
                data = p.data
                actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
                out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                          actions=actions, data=data)
                self.dp.send_msg(out)
            elif action == 'e':  # ec calc
                # initializer = True
                msg_to_send = {
                    'type': 'ec',
                    'node': platform.node(),
                    'ecs': [{
                        'space': [''.rjust(336, '*')],
                        'route': [platform.node()]
                    }]
                }
                p = packet.Packet()
                p.add_protocol(ethernet.ethernet())
                ipheader = ipv4.ipv4(proto=17)
                p.add_protocol(ipheader)
                u = udp.udp(dst_port=9999)
                u.serialize(json.dumps(msg_to_send), ipheader)
                p.add_protocol(u)
                p.add_protocol(json.dumps(msg_to_send))

                ofp = self.dp.ofproto
                parser = self.dp.ofproto_parser
                p.serialize()
                data = p.data
                actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
                out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                          actions=actions, data=data)
                self.dp.send_msg(out)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        '''
        This event handler is used to handle fly messages
        '''
        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
        pkt_udp = pkt.get_protocol(udp.udp)
        if not pkt_udp or pkt_udp.dst_port != 9999:
            return
        payload = pkt.protocols[-1]
        print payload
        if initializer:
            return
        try:
            msg = json.loads(payload)
            if msg['type'] == 'pm':
                changed = self.cps[int(msg['protocol'])].calc_property_space(in_port, msg['property'], msg['space'])
                if changed:
                    msg_to_send = {
                        'type': msg['type'],
                        'protocol': msg['protocol'],
                        'property': msg['property'],
                        'space': self.cps[int(msg['protocol'])].get_property_areas(msg['property'])
                    }
                    print 'flooding'
                    p = packet.Packet()
                    p.add_protocol(ethernet.ethernet())
                    ipheader = ipv4.ipv4(proto=17)
                    p.add_protocol(ipheader)
                    u = udp.udp(dst_port=9999)
                    u.serialize(json.dumps(msg_to_send), ipheader)
                    p.add_protocol(u)
                    p.add_protocol(json.dumps(msg_to_send))

                    ofp = self.dp.ofproto
                    parser = self.dp.ofproto_parser
                    p.serialize()
                    data = p.data
                    actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
                    # out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER, actions=actions, data=data)
                    out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=in_port, actions=actions, data=data)
                    self.dp.send_msg(out)
            elif msg['type'] == 'ec':
                changed = self.cps[100].calc_ecs(in_port, msg['ecs'])
                if changed:
                    data = []
                    for route, space in self.cps[100].ecs.items():
                        data.append({'space': space.areas, 'route': json.loads(route)})

                    msg_to_send = {
                        'type': msg['type'],
                        'ecs': data
                    }
                    print 'flooding ecs'
                    p = packet.Packet()
                    p.add_protocol(ethernet.ethernet())
                    ipheader = ipv4.ipv4(proto=17)
                    p.add_protocol(ipheader)
                    u = udp.udp(dst_port=9999)
                    u.serialize(json.dumps(msg_to_send), ipheader)
                    p.add_protocol(u)
                    p.add_protocol(json.dumps(msg_to_send))

                    ofp = self.dp.ofproto
                    parser = self.dp.ofproto_parser
                    p.serialize()
                    data = p.data
                    actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
                    # out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER, actions=actions, data=data)
                    out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=in_port, actions=actions, data=data)
                    self.dp.send_msg(out)

        except Exception as e:
            print e

