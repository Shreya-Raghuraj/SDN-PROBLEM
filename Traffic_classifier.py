"""
SDN Traffic Classification System — POX Controller
File: ~/pox/ext/traffic_classifier.py

Run with:
    cd ~/pox
    python3 pox.py traffic_classifier
"""

from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.packet import ethernet, ipv4, tcp, udp, icmp, arp
import pox.openflow.libopenflow_01 as of
from collections import defaultdict
import time

log = core.getLogger()


class TrafficClassifier:

    def __init__(self):
        # MAC learning table: {dpid: {mac: port}}
        self.mac_to_port = {}

        # Traffic stats: {dpid: {protocol: count}}
        self.stats = defaultdict(lambda: defaultdict(int))

        self.start_time = time.time()

        # Listen for switch connections
        core.openflow.addListeners(self)

        log.info("=" * 55)
        log.info("  SDN Traffic Classification System - POX")
        log.info("=" * 55)
        log.info("  Classifying: TCP | UDP | ICMP | ARP | Other")
        log.info("=" * 55)

    # ------------------------------------------------------------------ #
    #  Switch connects - install table-miss rule                          #
    # ------------------------------------------------------------------ #
    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        self.mac_to_port[event.dpid] = {}
        log.info("[Switch %s] Connected", dpid)

        # Table-miss: send all unmatched packets to controller
        msg = of.ofp_flow_mod()
        msg.priority = 0
        msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        event.connection.send(msg)
        log.info("[Switch %s] Table-miss rule installed", dpid)

    def _handle_ConnectionDown(self, event):
        dpid = dpid_to_str(event.dpid)
        log.info("[Switch %s] Disconnected", dpid)

    # ------------------------------------------------------------------ #
    #  PacketIn - main classification logic                               #
    # ------------------------------------------------------------------ #
    def _handle_PacketIn(self, event):
        pkt     = event.parsed
        dpid    = event.dpid
        in_port = event.port

        if not pkt.parsed:
            return

        src_mac = str(pkt.src)
        dst_mac = str(pkt.dst)

        # MAC learning
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port

        out_port = self.mac_to_port[dpid].get(dst_mac, of.OFPP_FLOOD)

        # Classify
        proto = self._classify(pkt)
        self.stats[dpid][proto] += 1
        self._log_packet(dpid, src_mac, dst_mac, in_port, out_port, proto)

        # Install flow rule if output port is known
        if out_port != of.OFPP_FLOOD:
            self._install_flow(event, pkt, in_port, out_port)

        # Send packet out now
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.in_port = in_port
        msg.actions.append(of.ofp_action_output(port=out_port))
        event.connection.send(msg)

        # Print summary every 15 packets
        total = sum(self.stats[dpid].values())
        if total % 15 == 0:
            self._print_summary(dpid)

    # ------------------------------------------------------------------ #
    #  Classify packet - return protocol label string                     #
    # ------------------------------------------------------------------ #
    def _classify(self, pkt):
        if pkt.type == ethernet.ARP_TYPE:
            return "ARP"

        ip = pkt.find("ipv4")
        if ip is None:
            return "Non-IP"

        if pkt.find("icmp") is not None:
            return "ICMP"

        tcp_pkt = pkt.find("tcp")
        if tcp_pkt is not None:
            dport = tcp_pkt.dstport
            sport = tcp_pkt.srcport
            if 80  in (dport, sport): return "TCP/HTTP"
            if 443 in (dport, sport): return "TCP/HTTPS"
            if 22  in (dport, sport): return "TCP/SSH"
            if 21  in (dport, sport): return "TCP/FTP"
            return "TCP"

        udp_pkt = pkt.find("udp")
        if udp_pkt is not None:
            dport = udp_pkt.dstport
            sport = udp_pkt.srcport
            if 53 in (dport, sport): return "UDP/DNS"
            return "UDP"

        return "IP/Other"

    # ------------------------------------------------------------------ #
    #  Push a flow rule into the switch                                   #
    # ------------------------------------------------------------------ #
    def _install_flow(self, event, pkt, in_port, out_port):
        msg = of.ofp_flow_mod()
        msg.idle_timeout = 10
        msg.hard_timeout = 30
        msg.priority     = 10
        msg.actions.append(of.ofp_action_output(port=out_port))

        ip     = pkt.find("ipv4")
        tcp_p  = pkt.find("tcp")
        udp_p  = pkt.find("udp")
        icmp_p = pkt.find("icmp")

        if tcp_p and ip:
            msg.match.dl_type  = ethernet.IP_TYPE
            msg.match.nw_proto = ipv4.TCP_PROTOCOL
            msg.match.nw_src   = ip.srcip
            msg.match.nw_dst   = ip.dstip
            msg.match.tp_src   = tcp_p.srcport
            msg.match.tp_dst   = tcp_p.dstport
        elif udp_p and ip:
            msg.match.dl_type  = ethernet.IP_TYPE
            msg.match.nw_proto = ipv4.UDP_PROTOCOL
            msg.match.nw_src   = ip.srcip
            msg.match.nw_dst   = ip.dstip
        elif icmp_p and ip:
            msg.match.dl_type  = ethernet.IP_TYPE
            msg.match.nw_proto = ipv4.ICMP_PROTOCOL
            msg.match.nw_src   = ip.srcip
            msg.match.nw_dst   = ip.dstip
        else:
            msg.match.dl_src = pkt.src
            msg.match.dl_dst = pkt.dst

        msg.match.in_port = in_port
        event.connection.send(msg)

    # ------------------------------------------------------------------ #
    #  Colored log line                                                   #
    # ------------------------------------------------------------------ #
    def _log_packet(self, dpid, src, dst, in_p, out_p, proto):
        elapsed = int(time.time() - self.start_time)
        colors = {
            "TCP": "\033[94m", "TCP/HTTP": "\033[94m",
            "TCP/HTTPS": "\033[94m", "TCP/SSH": "\033[94m",
            "UDP": "\033[92m", "UDP/DNS": "\033[92m",
            "ICMP": "\033[93m", "ARP": "\033[95m",
            "IP/Other": "\033[96m", "Non-IP": "\033[37m",
        }
        reset = "\033[0m"
        color = colors.get(proto, "\033[37m")
        log.info("[+%3ds][SW %s]  %-13s  %s -> %s   port %s -> %s",
                 elapsed, dpid_to_str(dpid),
                 f"{color}{proto}{reset}",
                 src[-5:], dst[-5:], in_p, out_p)

    def _print_summary(self, dpid):
        total = sum(self.stats[dpid].values())
        log.info("")
        log.info("  -- Traffic Summary (Switch %s) --", dpid_to_str(dpid))
        for proto, count in sorted(self.stats[dpid].items(),
                                   key=lambda x: -x[1]):
            bar = "#" * int(count / max(total, 1) * 20)
            pct = count / max(total, 1) * 100
            log.info("  %-14s %4d  %5.1f%%  %s", proto, count, pct, bar)
        log.info("  Total: %d packets", total)
        log.info("")


# POX entry point
def launch():
    core.registerNew(TrafficClassifier)