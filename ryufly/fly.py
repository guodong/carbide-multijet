import json
import struct
import os
import logging
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, MAIN_DISPATCHER
from ryu.lib.hub import spawn, sleep
from ryu.lib.packet import packet, ethernet, ipv4
from ryu.ofproto import ofproto_v1_3, ofproto_v1_3_parser

from multijet.topo import Topology, topo_port_set_network, shortest_path_fwd_rules


def port_is_down(ofpport, ofproto):
    return (ofpport.state & ofproto.OFPPS_LINK_DOWN) > 0 \
           or (ofpport.config & ofproto.OFPPC_PORT_DOWN) > 0


logger = logging.getLogger("ryufly.fly")


def debug(*msg):
    logger.debug(str(msg))


def info(*msg):
    logger.info(str(msg))


def error(*msg):
    logger.error(str(msg))


class FlyApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FlyApp, self).__init__(*args, **kwargs)

        self.topo = Topology()
        self.topo.load('configs/common/topo.json')
        topo_port_set_network(self.topo)

        self.up_links = dict(self.topo.links)  # up status links
        self.port_status = {}     # all external port status
        for p1, p2 in self.up_links.items():
            self.port_status[p1] = 'up'

        self.internal_to_external = {}
        for node_id, ports in self.topo.nodes.items():
            for port_num, attrs in ports.items():
                name1 = attrs['name']
                if name1.startswith('i'):
                    for p2, a2 in ports.items():
                        name2 = a2['name']
                        if name2.startswith('e') and name1[1:] == name2[1:]:
                            self.internal_to_external[(node_id, port_num)] = (node_id, p2)

        self.container_addr_to_node_id = {}
        with open('configs/common/container.json') as f:
            self.container_info = json.load(f)
            for n, info in self.container_info.items():
                eth0_ip = info['eth0']
                self.container_addr_to_node_id[str(eth0_ip)] = str(n)

        self.node_id_to_dp = {}
        self.rules = {}

        self._build_cached()

    def _dp_to_node_id(self, dp):
        return self.container_addr_to_node_id[str(dp.address[0])]

    def _delete_rule(self, match, node):
        debug('delete_rule', match, node)
        match = ofproto_v1_3_parser.OFPMatch(eth_type=0x0800, ipv4_dst=match)
        self._update_rule(ofproto_v1_3.OFPFC_DELETE_STRICT, match, node, None)

    def _add_rule(self, match, node, output):
        debug('add_rule', match, node, output)
        match = ofproto_v1_3_parser.OFPMatch(eth_type=0x0800, ipv4_dst=match)
        self._update_rule(ofproto_v1_3.OFPFC_ADD, match, node, output)

    def _mod_rule(self, match, node, output):
        debug('mod_rule', match, node, output)
        match = ofproto_v1_3_parser.OFPMatch(eth_type=0x0800, ipv4_dst=match)
        self._update_rule(ofproto_v1_3.OFPFC_MODIFY, match, node, output)

    def _delete_talbe(self, node):
        debug('delete table 100 on node', node)
        match = ofproto_v1_3_parser.OFPMatch()
        self._update_rule(ofproto_v1_3.OFPFC_DELETE, match, node, None)

    def _update_rule(self, op, match, node, output):
        of = ofproto_v1_3
        ofp = ofproto_v1_3_parser

        dp = self.node_id_to_dp.get(node)
        if dp is None:
            error("error dp is None")
            return

        if op == of.OFPFC_DELETE_STRICT or op == of.OFPFC_DELETE:
            insts = []
        else:
            action = [ofp.OFPActionOutput(output)]
            insts = [ofp.OFPInstructionActions(of.OFPIT_APPLY_ACTIONS, action)]

        msg = ofp.OFPFlowMod(
            datapath=dp,
            table_id=100,
            command=op,
            priority=2333,
            match=match,
            instructions=insts,
            out_port=of.OFPP_ANY,
            out_group=of.OFPG_ANY
        )

        dp.send_msg(msg)

    def _cached_key(self, links):
        return tuple(sorted(links.items()))

    def _build_cached(self):
        info("build cached")
        self._cached = {}
        ds = [self.up_links]

        computed=set()
        for p1, p2 in self.up_links.items():
            if p1 in computed:
                continue
            computed.add(p1)
            computed.add(p2)
            links = dict(self.up_links)
            links.pop(p1)
            links.pop(p2)
            ds.append(links)
        
        info("prepare done!")

        for links in ds:
            topo = Topology()
            topo.nodes = self.topo.nodes
            topo.links = links
            # info(links)
            rules2 = shortest_path_fwd_rules(topo)
            key = self._cached_key(links)
            self._cached[key] = rules2
        
        info("build cached done!")

    def cached_shortest_path_fwd_rules(self, topo):
        key = self._cached_key(topo.links)
        value = self._cached.get(key)
        if value is not None:
            info("got in cache")
            return value
        else:
            info("not in cache")
            rules2 = shortest_path_fwd_rules(topo)
            self._cached[key] = rules
            return key

    def _update(self):
        info("update start", time.time())
        topo = Topology()
        topo.nodes = self.topo.nodes
        topo.links = self.up_links
        info("before sp", time.time())
        rules2 = self.cached_shortest_path_fwd_rules(topo)
        info("after sp", time.time())
        for match, fwds2 in rules2.items():
            fwds = self.rules.get(match)
            if fwds is None:
                for n, p2 in fwds2.items():
                    self._add_rule(match, n, p2[1])
            else:
                for n, p in fwds.items():
                    p2 = fwds2.get(n)
                    if p2 is None:
                        self._delete_rule(match, n)
                    elif p2 != p:
                        self._mod_rule(match, n, p2[1])
                for n, p2 in fwds2.items():
                    if n not in fwds:
                        self._add_rule(match, n, p2[1])

        for match, fwds in self.rules.items():
            if match not in rules2:
                for n, p in fwds.items():
                    self._delete_rule(match, n)

        self.rules = rules2
        info("update finish", time.time())

    def _port_status_change(self, node_id, port_num, status): # status: 'down' / 'up'
        p = (node_id, port_num)
        p2 = self.internal_to_external.get(p)
        if p2 is not None:
            p = p2
        status1 = self.port_status.get(p)
        if status1 is not None and status1!=status: # status changed
            self.port_status[p] = status
            if status == 'up':  # 'down' -> 'up'
                p2 = self.topo.links[p]
                assert p not in self.up_links
                assert p2 not in self.up_links
                if self.port_status[p2] == 'up':
                    self.up_links[p] = p2
                    self.up_links[p2] = p
                    self._update()
            else:      # 'up' -> 'down'
                p2 = self.topo.links[p]
                if p not in self.up_links:
                    assert p2 not in self.up_links
                else:
                    self.up_links.pop(p)
                    self.up_links.pop(p2)
                    self._update()

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def switch_in_handler(self, ev):
        info('comming switch')
        dp = ev.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        n = self._dp_to_node_id(dp)
        self.node_id_to_dp[n] = dp
        # print(self.node_id_to_dp)
        self._delete_talbe(n)
        if len(self.node_id_to_dp) == len(self.topo.nodes):
            sleep(1)
            info('start update......')
            self._update()

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_event_handler(self, ev):
        # print("recv Port Event")
        msg = ev.msg
        reason = msg.reason
        dp = msg.datapath
        ofp = dp.ofproto
        ofpport = msg.desc
        port_no = ofpport.port_no
        if reason == dp.ofproto.OFPPR_ADD:
            pass
        elif reason == dp.ofproto.OFPPR_DELETE:
            pass
        elif reason == dp.ofproto.OFPPR_MODIFY:
            node_id = self._dp_to_node_id(dp)
            if port_is_down(ofpport, ofp):
                self._port_status_change(node_id, port_no, 'down')
            else:
                self._port_status_change(node_id, port_no, 'up')
        else:
            print("error")

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        print("recv FlowStatsReplay")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        print("recv PacketIn")
        in_port = ev.msg.match['in_port']
        pkt = packet.Packet(data=ev.msg.data)
