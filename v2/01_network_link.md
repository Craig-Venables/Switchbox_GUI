# 01 — Private network link

A direct Ethernet cable between the main PC and the 4200. The 4200 never
reaches the internet or the lab LAN. Safety rules: [00_safety.md](00_safety.md).

## Hardware

1. Add a second network port to the main PC (a USB-to-Ethernet adapter is
   fine). Keep the existing port for the normal network.
2. Connect a straight Ethernet cable from that port to the 4200's LAN port.
   Current network cards auto-detect, so a crossover cable is not needed.
3. Do not connect the 4200 to any switch that has other machines or an uplink.

GPIB stays connected as it is now. The cable is an extra link, not a
replacement.

## Addressing

| Host | IPv4 | Mask | Gateway | DNS |
|---|---|---|---|---|
| Main PC (second port) | `192.168.50.1` | `255.255.255.0` | blank | blank |
| 4200 | `192.168.50.2` | `255.255.255.0` | blank | blank |

Steps on each machine: Control Panel → Network and Sharing Center → Change
adapter settings → right-click the adapter → Properties → Internet Protocol
Version 4 → "Use the following IP address".

On the main PC, also check:

- Internet Connection Sharing is off on both adapters.
- The two adapters are not bridged.

## Firewall on the 4200

Inbound rules, each limited to remote address `192.168.50.1`:

| Port | Use | Enable when |
|---|---|---|
| TCP 8765 | Lab agent | Phase 2 onwards |
| TCP 22 | OpenSSH | Only for the Remote-SSH option ([09](09_remote_ssh_option.md)) |
| TCP 5985 | WinRM | Only if tier-2 recovery is wanted ([03](03_remote_control.md)) |
| TCP 5900 | VNC | Only if you want to watch the screen |

Block all other inbound traffic. Outbound can stay at the default; with no
gateway it cannot leave the cable.

## Tests (phase 1 gate)

From the main PC:

```powershell
ping 192.168.50.2
```

On the 4200, confirm there is no outside route (both should fail):

```powershell
ping 8.8.8.8
Resolve-DnsName example.com
```

After the lab agent is installed (phase 2):

```powershell
curl.exe -H "Authorization: Bearer <token>" http://192.168.50.2:8765/status
```

## Instrument connection

- Keep **GPIB** for KXCI in the first rollout. `KXCIClient` already uses it;
  the default address in the repo is `GPIB0::17::INSTR` (confirm on your
  unit).
- Later option: switch KXCI to Ethernet in KConfig and point the MCP server
  at a `TCPIP::192.168.50.2::<port>::SOCKET` resource. Only after the GPIB
  setup has been stable.

## Do not

- Enable DHCP on this link.
- Give the 4200 a gateway "just in case".
- Use Remote Desktop to the 4200 (see [03_remote_control.md](03_remote_control.md)).
- Expose the lab-agent port on the main PC's internet-facing adapter.
