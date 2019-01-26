import json, platform
from threading import Thread
from core.Space import Space
from ryu.lib.packet import packet, ethernet, ipv4
from utils import log


class Verifier(Thread):
    MULTIJET_IP_PROTO = 143

    def __init__(self, cpid, queue):
        """
        One cp one verifier thread
        :param cpid: control plane id, we use it as table offset currently, cpid=100 meas flows should be installed to table 100
        """
        super(Verifier, self).__init__()
        self.dp = None
        self.cpid = cpid
        self.queue = queue
        self.rules = []
        self.forward_rules = {}
        self.ecs = []
        self.seq = 0
        self.received_seqs = []  # forbid update msg loop

    def run(self):
        while True:
            msg = self.queue.get()
            if msg['cpid'] == self.cpid:
                data = msg['data']
                if data['type'] == 'add_rules':
                    log('add_rules')
                    self.rules = []
                    self.ecs = []
                    self.rules.extend(data['rules'])
                    self.build_space()
                elif data['type'] == 'verify':
                    log('verify')
                    self.init_ec()
                elif data['type'] == 'ec':
                    log('ec')
                    self.calc_ec(msg['in_port'], data['route'], data['space'])
                elif data['type'] == 'update_add_rule':
                    log('update_add_rule')
                    self.update_space(data['rule'])
                elif data['type'] == 'update_request':
                    log('update_request')
                    for ec in self.ecs:
                        s = Space(areas=data['space'])
                        s.multiply(ec['space'])
                        if len(s.areas) > 0:
                            seq = self.gen_seq()
                            self.received_seqs.append(seq)
                            m = {
                                'cpid': self.cpid,
                                'src': platform.node(),
                                'data': {
                                    'seq': seq,
                                    'type': 'update',
                                    'from': data['from'],
                                    'route': ec['route'],
                                    'space': s.areas
                                }
                            }
                            self.flood(json.dumps(m))
                elif data['type'] == 'update':
                    log('update')
                    if data['seq'] in self.received_seqs:
                        continue
                    # 1. flood out
                    self.received_seqs.append(data['seq'])
                    m = {
                        'cpid': self.cpid,
                        'src': platform.node(),
                        'data': data
                    }
                    self.flood(json.dumps(m), msg['in_port'])

                    # 2. do local update
                    self.do_update(data['from'], data['route'], data['space'])

    def build_space(self):
        self.forward_rules = {}
        for rule in self.rules:
            if not self.forward_rules.has_key(rule['action']['output']):
                self.forward_rules[rule['action']['output']] = Space()
            self.forward_rules[rule['action']['output']].plus(Space(match=rule['match']))

        self.add_ec([platform.node()], Space(areas=[''.ljust(336, '*')]))
        log('finish build ec')

    def add_ec(self, route, space):
        for ec in self.ecs:
            if ec['route'] == route:
                ec['space'].plus(space)
                return
        self.ecs.append({'route': route, 'space': space})

    def update_space(self, rule):
        self.rules.append(rule)
        self.build_space()
        space = Space(match=rule['match'])
        msg = {
            'cpid': self.cpid,
            'src': platform.node(),
            'data': {
                'type': 'update_request',
                'from': platform.node(),
                'space': space.areas
            }
        }

        self.unicast(json.dumps(msg), rule['action']['output'])

    def do_update(self, from_, route, space):
        for ec in self.ecs:
            if ec['route'][-1] == from_:
                ec['route'].extend(route)
                ec['space'].plus(Space(areas=space))
        log('updated')
        self.dump_ecs()

    def get_init_ec_space(self):

        for ec in self.ecs:
            print ec['route']
            if ec['route'][0] == platform.node():
                print 'return'
                return ec['space']

        result = Space()
        for s in self.forward_rules.values():
            result.plus(s)
        return result.notme()

    def init_ec(self):
        msg = {
            'cpid': self.cpid,
            'src': platform.node(),
            'data': {
                'type': 'ec',
                'route': [platform.node()],
                'space': [''.ljust(336, '*')]  # self.get_init_ec_space().areas
            }
        }
        self.flood(json.dumps(msg))

    def calc_ec(self, in_port, route, areas):
        if not self.forward_rules.has_key(in_port):
            return
        space = Space(areas=areas)
        space.multiply(self.forward_rules[in_port])
        if len(space.areas) == 0:
            return
        route.insert(0, platform.node())
        self.add_ec(route, space)
        msg = {
            'cpid': self.cpid,
            'src': platform.node(),
            'data': {
                'type': 'ec',
                'route': route,
                'space': space.areas
            }
        }
        if len(space.areas) > 0:
            self.flood(json.dumps(msg), in_port)

        self.dump_ecs()

    def gen_seq(self):
        seq = str(self.dp.id) + str(self.cpid) + str(self.seq)
        self.seq = self.seq + 1
        return seq

    def unicast(self, msg, port):
        size = len(msg)
        buf_size = 1200
        offset = 0
        count = size / buf_size + 1
        seq = self.gen_seq()
        while size > 0:
            frag = msg[offset:offset + buf_size]
            offset = offset + buf_size
            size = size - buf_size
            pkt_data = json.dumps({
                'seq': seq,
                'count': count,
                'data': frag
            })
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.MULTIJET_IP_PROTO)
            ip_header.serialize(pkt_data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(pkt_data)

            ofp = self.dp.ofproto
            parser = self.dp.ofproto_parser
            p.serialize()
            data = p.data
            actions = [parser.OFPActionOutput(port)]
            out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions, data=data)
            self.dp.send_msg(out)
        log('unicast finished')

    def flood(self, msg, except_port=None):
        size = len(msg)
        buf_size = 1200
        offset = 0
        count = size / buf_size + 1
        seq = self.gen_seq()
        while size > 0:
            frag = msg[offset:offset + buf_size]
            offset = offset + buf_size
            size = size - buf_size
            pkt_data = json.dumps({
                'seq': seq,
                'count': count,
                'data': frag
            })
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.MULTIJET_IP_PROTO)
            ip_header.serialize(pkt_data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(pkt_data)

            ofp = self.dp.ofproto
            parser = self.dp.ofproto_parser
            p.serialize()
            data = p.data
            actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
            if except_port is None:
                except_port = ofp.OFPP_CONTROLLER
            out = parser.OFPPacketOut(datapath=self.dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=except_port,
                                      actions=actions, data=data)
            self.dp.send_msg(out)
        log('flood finished')

    def dump_ecs(self):
        log('ecs count: ' + str(len(self.ecs)))
        # for ec in self.ecs:
        #     log(ec['route'])
            # for a in ec['space'].areas:
            #     log(a)
        # log('count: ' + str(len(self.ecs)))
