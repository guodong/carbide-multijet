import json
import pickle
import zlib
import platform
from threading import Thread

from ryu.lib.packet import packet, ethernet, ipv4

from utils import log
from .ecs_mgr import ECSMgrPickle
from .topo import Topology


class VerifierThread(Thread, ECSMgrPickle):
    MULTIJET_IP_UNICAST_PROTO = 143
    MULTIJET_IP_FLOOD_PROTO = 144

    def __init__(self, cpid, queue):
        '''
        One cp one verifier thread
        :param cpid: control plane id, we use it as table offset currently, cpid=100 meas flows should be installed to table 100
        '''
        # super(VerifierThread, self).__init__()
        topo = Topology()
        topo.load("/common/topology.json")
        ECSMgrPickle.__init__(self, str(platform.node()), topo)
        Thread.__init__(self)
        self.dp = None
        self.cpid = cpid
        self.queue = queue

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
