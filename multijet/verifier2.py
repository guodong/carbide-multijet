import json
import platform
import struct

from ryu.lib.packet import packet, ethernet, ipv4
from eventlet import Queue

from utils import log, debug
from .ecs_mgr import ECSMgrPickle
from .topo import Topology


class _Buffer:
    def __init__(self, length):
        self.buf = bytearray(length)
        self.pad_size = 0
        self.pad_set = set()

    def pad(self, start, end, fragment):
        self.buf[start: end] = fragment
        self.pad_size += end-start

    def get_if_full(self):
        debug("pad_size=%d len=%d"%(self.pad_size, len(self.buf)))
        if self.pad_size==len(self.buf):
            return str(self.buf)
        return None


class Verifier2(ECSMgrPickle):
    MULTIJET_IP_UNICAST_PROTO = 144
    MULTIJET_IP_FLOOD_PROTO = 145

    def __init__(self, cpid, dp, queue):
        topo = Topology()
        topo.load('/common/topo.json')
        ECSMgrPickle.__init__(self, str(platform.node()), topo)

        self._dp = dp
        self._queue = queue  # type: Queue
        self._cpid = cpid
        self._unicast_seq_num = 0
        self._flood_seq_num = 0
        self._reassemble_buf = {
            self.MULTIJET_IP_FLOOD_PROTO: {},
            self.MULTIJET_IP_UNICAST_PROTO: {}
        }

        with open('/common/spanningtree.json') as f:
            self._spanning_tree = json.load(f)

    def run(self):
        log('start run')
        while True:
            try:
                msg = self._queue.get(timeout=5)
                # debug(msg)
            except Exception:
                log(self.dump_ecs())
                continue
            if msg['type'] == 'local_update':
                self.update_local_rules(msg['rules'])
            elif msg['type'] == 'unicast':
                self.on_recv_unicast(msg['data'], msg['recv_port'])
            elif msg['type'] == 'flood':
                self.on_recv_flood(msg['data'])
            # debug(self.dump_ecs())

    HEADER_FORMAT = "I8sIIII"
    HEADER_LENGTH = struct.calcsize(HEADER_FORMAT)

    def _split_msg(self, msg, seq_num):
        # cpid seq_num  total_size start_offset end_offset  fragment
        total_size = len(msg)
        buf_size = 1200
        offset = 0
        while offset<total_size:
            frag = msg[offset:offset + buf_size]
            start_offset = offset
            offset = offset + len(frag)
            end_offset = offset
            header = struct.pack(self.HEADER_FORMAT, self._cpid, self.node_id, seq_num, total_size, start_offset, end_offset)
            yield header+frag

    def reassemble(self, in_port, proto, fragment):
        bufs = self._reassemble_buf.get(proto)
        if bufs is None:
            return
        cpid, node_id, seq_num, ts, so, eo = struct.unpack_from(self.HEADER_FORMAT, fragment)
        node_id = node_id.strip('\x00')
        debug("recv %d %s %d %d %d %d"%(cpid, node_id, seq_num, ts, so, eo))
        node_bufs = bufs.setdefault(node_id, {})
        buf = node_bufs.setdefault(seq_num, _Buffer(ts))
        data = fragment[self.HEADER_LENGTH:]
        if len(data) != eo-so:
            debug("error data length")
        buf.pad(so, eo, data)
        msg = buf.get_if_full()
        if msg:
            node_bufs.pop(seq_num)
            if proto == self.MULTIJET_IP_UNICAST_PROTO:
                debug("put queue")
                self._queue.put({
                    'type': 'unicast',
                    'data': msg,
                    'recv_port': in_port  # TODO
                })
            elif proto == self.MULTIJET_IP_FLOOD_PROTO:
                debug("put queue")
                self._queue.put({
                    'type': 'flood',
                    'data': msg
                })

    def unicast(self, msg, port):
        ofp = self._dp.ofproto
        parser = self._dp.ofproto_parser
        actions = [parser.OFPActionOutput(port)]

        self._unicast_seq_num += 1
        for pkt_data in self._split_msg(msg, self._unicast_seq_num):
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.MULTIJET_IP_UNICAST_PROTO)
            ip_header.serialize(pkt_data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(pkt_data)
            p.serialize()
            data = p.data
            out = parser.OFPPacketOut(datapath=self._dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions, data=data)
            self._dp.send_msg(out)
        log('unicast finished')

    def flood(self, msg):
        ofp = self._dp.ofproto
        parser = self._dp.ofproto_parser
        actions = [parser.OFPActionOutput(int(port)) for port in self._spanning_tree[self.node_id]]

        self._flood_seq_num += 1
        for pkt_data in self._split_msg(msg, self._flood_seq_num):
            p = packet.Packet()
            eth_header = ethernet.ethernet()
            ip_header = ipv4.ipv4(proto=self.MULTIJET_IP_FLOOD_PROTO)
            ip_header.serialize(pkt_data, eth_header)
            p.add_protocol(eth_header)
            p.add_protocol(ip_header)
            p.add_protocol(pkt_data)
            p.serialize()
            data = p.data
            out = parser.OFPPacketOut(datapath=self._dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions, data=data)
            self._dp.send_msg(out)
        log('flood finished')
