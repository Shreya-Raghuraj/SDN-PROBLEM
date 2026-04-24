# SDN Traffic Classification System

**Name:** Shreya Raghuraj
**SRN:** PES2UG24AM154

**Controller:** POX (OpenFlow 1.0)
**Simulator:** Mininet
**Language:** Python 3

---

## Project Overview

This project implements an SDN-based Traffic Classification System using the POX controller and Mininet network simulator. The controller classifies network traffic into categories — TCP, UDP, ICMP, ARP — by inspecting packets at the controller level and dynamically installing flow rules into OVS switches.

---

## Topology

```
h1 (10.0.0.1) ─┐
h2 (10.0.0.2) ─┤── s1 ──── s2 ──┬── h4 (10.0.0.4)
h3 (10.0.0.3) ─┘                └── h5 (10.0.0.5)
                      ↕ OpenFlow 1.0
                  POX Controller
```

- 2 OVS Switches (s1, s2) connected in a linear topology
- 5 Hosts (h1–h5) with IPs 10.0.0.1 to 10.0.0.5
- 1 POX Controller listening on port 6633

---

## Files

| File | Description |
|------|-------------|
| `traffic_classifier.py` | POX controller — classifies traffic and installs flow rules |
| `topology.py` | Mininet topology — creates switches, hosts and links |

---

## Installation

```bash
# Install Mininet
sudo apt-get update
sudo apt-get install -y mininet iperf

# Install POX (no pip needed)
cd ~
git clone https://github.com/noxrepo/pox.git

# Copy controller into POX
cp traffic_classifier.py ~/pox/ext/
```

---

## How to Run

### Terminal 1 — Start POX Controller
```bash
cd ~/pox
python3 pox.py traffic_classifier
```

Expected output:
```
SDN Traffic Classification System - POX
Classifying: TCP | UDP | ICMP | ARP | Other
INFO:core:POX is up.
```

### Terminal 2 — Start Mininet Topology
```bash
sudo python3 ~/topology.py
```

---

## Demo Commands (inside Mininet CLI)

```bash
# Generate ICMP traffic (ping)
mininet> h1 ping -c5 h4

# Generate TCP traffic (iperf)
mininet> iperf h1 h4

# Generate UDP traffic
mininet> h5 iperf -s -u &
mininet> h2 iperf -c 10.0.0.5 -u -t3

# Show installed flow rules
mininet> sh ovs-ofctl -O OpenFlow10 dump-flows s1

# Test all host connectivity
mininet> pingall
```

---

## How It Works

1. Mininet starts a virtual network with 2 switches and 5 hosts
2. POX controller connects to both switches via OpenFlow
3. Controller installs a table-miss rule — all unmatched packets go to controller
4. When h1 pings h4, the switch has no rule → sends `packet_in` to controller
5. Controller classifies the packet (ICMP, TCP, UDP, ARP)
6. Controller installs a specific flow rule back into the switch
7. All future packets of that flow are forwarded directly by the switch

---

## Traffic Classification Logic

| Protocol | How Detected | Example |
|----------|-------------|---------|
| ARP | `pkt.type == ARP_TYPE` | Host discovery |
| ICMP | `pkt.find("icmp")` | ping |
| TCP | `pkt.find("tcp")` | iperf |
| TCP/HTTP | TCP port 80 | Web traffic |
| TCP/SSH | TCP port 22 | SSH |
| UDP | `pkt.find("udp")` | iperf -u |
| UDP/DNS | UDP port 53 | DNS queries |

---

## Sample Output

**Controller Terminal:**
```
[+ 10s][SW 00-00-00-00-00-01]  ARP    00:01 -> ff:ff   port 1 -> 65531
[+ 10s][SW 00-00-00-00-00-01]  ICMP   00:01 -> 00:04   port 1 -> 4
[+ 15s][SW 00-00-00-00-00-01]  TCP    00:01 -> 00:04   port 1 -> 4
```

**Flow Rules (dump-flows):**
```
priority=10, icmp, nw_src=10.0.0.1, nw_dst=10.0.0.4  actions=output:s1-eth4
priority=10, tcp,  nw_src=10.0.0.1, nw_dst=10.0.0.4  actions=output:s1-eth4
priority=0                                             actions=CONTROLLER:65535
```

---

**What is SDN?**
Software Defined Networking separates the control plane (controller) from the data plane (switch). The controller has a global view and programs switches remotely using OpenFlow.

**What is packet_in?**
When a switch receives a packet with no matching flow rule, it sends it to the controller. This triggers the `_handle_PacketIn` function in my controller.

**What is a flow rule?**
A flow rule has a match (identifies the packet by IP, protocol, port) and an action (what to do — forward, drop, flood).

**Difference between match and action?**
Match is the condition (e.g. `nw_proto=1` means ICMP). Action is the result (e.g. `output port 4`).

**How are flow rules installed?**
My controller sends an `ofp_flow_mod` message to the switch after classifying the packet. The switch stores this rule and uses it for future packets of the same flow.

**What happens without the controller?**
The switch cannot forward packets — it has no rules. All packets get dropped or flooded.

**What topology did you use?**
Linear/tree topology — 2 switches connected in a line, with hosts branching off each switch.

**How does your logic affect network behavior?**
The controller classifies every new flow, installs a specific rule, and future packets bypass the controller entirely — making forwarding faster over time.
