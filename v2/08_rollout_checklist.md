# 08 — Rollout checklist

Phases are in order. Do not start a phase until the previous one's gate has
passed. A human ticks each box. Safety rules: [00_safety.md](00_safety.md).

## Phase 0 — Backups and facts

- [ ] Full Windows system image of the 4200 on external media.
- [ ] Copy of the user-library tree (find the real path; often under `C:\s4200\kiuser`).
- [ ] One-page restore procedure written and stored with the image.
- [ ] Record: Clarius version, Windows version, GPIB address, user-library path.
- [ ] Record which existing libraries are loaded (list in [00_safety.md](00_safety.md)).

**Gate:** you could restore the 4200 to today's state if needed.

## Phase 1 — Network

- [ ] Second adapter on the main PC, direct cable, static IPs, no gateway ([01](01_network_link.md)).
- [ ] Internet Connection Sharing off.
- [ ] 4200 firewall: inbound only from `192.168.50.1`.
- [ ] `ping 192.168.50.2` works from the main PC.
- [ ] `ping 8.8.8.8` and DNS lookups fail from the 4200.

**Gate:** both machines see each other; the 4200 sees nothing else.

## Phase 2 — Lab agent tier 1 and build facts

- [ ] Python and wheels installed offline ([02](02_lab_agent_4200.md)).
- [ ] `labagent` user created; write access only to `usrlib\V2_*` and logs.
- [ ] Autostart at login works after a reboot.
- [ ] `/status` reachable from the main PC with the token; refused without it.
- [ ] `/deploy` refuses a non-`V2_*` library name and a path with `..`.
- [ ] **Find out:** does KULT have a command-line build on this Clarius version? Test by hand on a throwaway `V2_Test` library.
- [ ] **Find out:** does KXCI need a restart to pick up a rebuilt library?
- [ ] **Find out:** can Clarius, KULT and KXCI run under the non-admin user?
- [ ] An existing library still builds and an existing `EX` still works afterwards.

**Gate:** a trivial `V2_Test` module deploys, builds, and is callable over GPIB, all started from the main PC.

## Phase 3 — MCP server, simulator only

- [ ] MCP server with tier-0 tools only ([04](04_mcp_server.md)).
- [ ] `c_precheck` with stub headers and header/constant checks ([05](05_build_pipeline.md)).
- [ ] Gate unit tests: values just inside and just outside every limit.
- [ ] Hardware tools refuse `SIM*` addresses and the reverse.
- [ ] PMU simulator handler for a pure resistor ([07](07_pmu.md)).
- [ ] AI completes one full loop (edit, precheck, simulate) on a `V2_*` copy without hardware.

**Gate:** all tests pass; no GPIB connection was opened during this phase.

## Phase 4 — SMU on the fixture

- [ ] Fixture built, measured with a multimeter, value recorded in `config.toml` ([06](06_validation_fixture.md)).
- [ ] Only the fixture connected; no sample on the station.
- [ ] Fixture interlock passes; then disconnect one lead and confirm it fails and locks.
- [ ] `hw_abort` and the kill switch tested while an `EX` is running.
- [ ] Tier 1 enabled.
- [ ] One SMU `V2_*` module: first run approved by a human, `validate_resistor` passes.

**Gate:** SMU loop works end to end, abort and kill switch proven.

## Phase 5 — PMU on the fixture

- [ ] PMU fixture wiring (CH1 to 10 kOhm to CH2) ([06](06_validation_fixture.md)).
- [ ] `V2_Readtrain` passes in simulation, then on hardware with human approval of the first run.
- [ ] Gate rejects 1 V on the 100 µA range and a burst over 350 segments.
- [ ] `V2_Retention`, then `V2_PulseReadInterleaved`, each passing in turn ([07](07_pmu.md)).

**Gate:** three PMU modules validated against 10 kOhm.

## Phase 6 — Optional remote control

Only if needed (for example KULT has no command line).

- [ ] Tier 3 endpoints installed; screenshot works; VNC installed for human viewing ([03](03_remote_control.md)).
- [ ] KULT GUI build sequence recorded and repeatable.
- [ ] Tier 2 allowlist written; free shell left off.
- [ ] Approval expiry tested (tools disappear after expiry).
- [ ] Optional: Remote-SSH tested ([09](09_remote_ssh_option.md)).

**Gate:** each enabled tier switches on with approval and off on expiry or kill switch.

## Open questions to answer on the instrument

| Question | Found in phase | Affects |
|---|---|---|
| Does KULT have a command-line build? | 2 | Whether tier 3 is required |
| Does KXCI need a restart after a rebuild? | 2 | Build sequence time |
| Real user-library path | 0 | Lab agent config |
| Clarius and Windows versions | 0 | Stub headers, Python compatibility |
| GPIB address | 0 | MCP config |
| Do Clarius/KXCI work under a non-admin user? | 2 | Account model |
| Can Cursor's remote server be installed offline on this Windows version? | 6 | Remote-SSH option |
| Are Cursor's model requests made from the main PC when using Remote-SSH? | 6 | Whether Remote-SSH works without internet on the 4200 |

## Ongoing rules after go-live

- Re-run the fixture interlock after every rebuild, KXCI restart and reboot.
- Review the audit log weekly.
- Refresh the system image after any Clarius update.
- Never connect a real sample while tier 1 or above is enabled.
