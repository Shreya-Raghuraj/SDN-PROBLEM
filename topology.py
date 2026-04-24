"""
Mininet Topology for SDN Traffic Classification Demo
Topology:
        h1 ──┐
        h2 ──┤── s1 ── s2 ──┬── h4
        h3 ──┘              └── h5

Run:  sudo python3 topology.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import sys


def build_network():
    net = Mininet(controller=RemoteController,
                  switch=OVSSwitch,
                  link=TCLink,
                  autoSetMacs=True)

    info("\n*** Adding Ryu controller (127.0.0.1:6633)\n")
    c0 = net.addController("c0",
                            controller=RemoteController,
                            ip="127.0.0.1",
                            port=6633)

    info("*** Adding switches\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")

    info("*** Adding hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")
    h5 = net.addHost("h5", ip="10.0.0.5/24")

    info("*** Adding links\n")
    # Hosts to switch 1
    net.addLink(h1, s1, bw=10)
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s1, bw=10)

    # Switch to switch (backbone)
    net.addLink(s1, s2, bw=100)

    # Hosts to switch 2
    net.addLink(s2, h4, bw=10)
    net.addLink(s2, h5, bw=10)

    return net, c0


def run_auto_traffic(net):
    """Send mixed traffic so the classifier has something to classify."""
    h1, h2, h3, h4, h5 = [net.get(f"h{i}") for i in range(1, 6)]

    info("\n*** Generating mixed traffic for classification demo\n")
    info("    (watch the Ryu controller terminal for output)\n\n")

    # ICMP (ping)
    info("  [1/4] ICMP  — h1 pings h4 and h5\n")
    h1.cmd("ping -c 4 10.0.0.4 &")
    h2.cmd("ping -c 4 10.0.0.5 &")
    time.sleep(2)

    # TCP — using iperf
    info("  [2/4] TCP   — iperf h1→h4\n")
    h4.cmd("iperf -s -t 10 &")
    h1.cmd("iperf -c 10.0.0.4 -t 5 &")
    time.sleep(3)

    # UDP
    info("  [3/4] UDP   — iperf UDP h2→h5\n")
    h5.cmd("iperf -s -u -t 10 &")
    h2.cmd("iperf -c 10.0.0.5 -u -b 1M -t 5 &")
    time.sleep(3)

    # More ICMP
    info("  [4/4] ICMP  — h3 pings h4\n")
    h3.cmd("ping -c 6 10.0.0.4 &")
    time.sleep(4)

    info("\n*** Traffic generation complete\n")


def show_flow_tables(net):
    info("\n" + "=" * 55 + "\n")
    info("  Flow Tables (ovs-ofctl dump-flows)\n")
    info("=" * 55 + "\n")
    for sw in ["s1", "s2"]:
        s = net.get(sw)
        info(f"\n--- Switch {sw} ---\n")
        result = s.cmd(f"ovs-ofctl -O OpenFlow13 dump-flows {sw}")
        info(result)


def show_port_stats(net):
    info("\n" + "=" * 55 + "\n")
    info("  Port Statistics\n")
    info("=" * 55 + "\n")
    for sw in ["s1", "s2"]:
        s = net.get(sw)
        info(f"\n--- Switch {sw} ---\n")
        result = s.cmd(f"ovs-ofctl -O OpenFlow13 dump-ports {sw}")
        info(result)


def main():
    setLogLevel("info")

    info("=" * 55 + "\n")
    info("  SDN Traffic Classification — Mininet Topology\n")
    info("=" * 55 + "\n")
    info("  Ensure Ryu controller is running:\n")
    info("  $ ryu-manager traffic_classifier.py\n")
    info("=" * 55 + "\n\n")

    net, c0 = build_network()

    info("*** Starting network\n")
    net.start()

    info("*** Waiting for switches to connect to controller...\n")
    time.sleep(4)

    # Verify connectivity
    info("*** Testing basic connectivity (pingAll)\n")
    net.pingAll()
    time.sleep(1)

    # Generate demo traffic
    if "--auto" in sys.argv:
        run_auto_traffic(net)
        time.sleep(2)
        show_flow_tables(net)
        show_port_stats(net)
    else:
        info("\n*** Auto traffic skipped. Run with --auto to generate it.\n")
        info("*** Inside Mininet CLI you can try:\n")
        info("    mininet> h1 ping -c5 h4\n")
        info("    mininet> iperf h1 h4\n")
        info("    mininet> h2 iperf -c 10.0.0.5 -u -b 1M -t5 &\n")
        info("    mininet> s1 ovs-ofctl -O OpenFlow13 dump-flows s1\n\n")

    info("*** Entering Mininet CLI (type 'exit' to quit)\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == "__main__":
    main()
