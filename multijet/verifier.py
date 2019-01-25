import json
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

    def run(self):
        while True:
            msg = self.queue.get()
            if msg['type'] == 'verify':
                print 'verify'
                self.init_ec()
            elif msg['type'] == 'add_rule' and msg['cpid'] == self.cpid:
                self.rules.append(msg['rule'])
                self.build_space()
            elif msg['type'] == 'ec':
                self.calc_ec(msg['in_port'], msg['route'], msg['space'])

    def build_space(self):
        for rule in self.rules:
            if not self.forward_rules.has_key(rule['action']['output']):
                self.forward_rules[rule['action']['output']] = Space()
            self.forward_rules[rule['action']['output']].plus(Space(match=rule['match']))

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
        ip_header = ipv4.ipv4(proto=self.MULTIJET_IP_PROTO)
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
        log('ecs of: ' + str(self.dp.id))
        for ec in self.ecs:
            log(ec['route'])
            for a in ec['space'].areas:
                log(a)
        log('count: ' + str(len(self.ecs)))
