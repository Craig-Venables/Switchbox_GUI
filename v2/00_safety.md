# 00 — Safety model

Every other V2 document refers back here. If anything conflicts with this
file, this file wins. The aim is to limit what the AI can do as much as
possible while still letting it build, test and iterate.

## Principles

1. **Default deny.** Every capability is off until a human turns it on.
2. **Reject, never clip.** Out-of-range requests fail with an explanation;
   the gate never silently changes values.
3. **The fixture is the last line of defence.** While the AI has hardware
   access, only the 10 kOhm resistor is connected. Software limits can be
   bypassed if tier 2 is on; the physical setup cannot.
4. **Least privilege.** Non-admin Windows account; writes only to `V2_*`
   libraries.
5. **Recoverable.** Full backup before go-live; kill switch always available.
6. **Auditable.** Every action that reaches the 4200 is logged on the main PC.

## Capability tiers

| Tier | Name | What it allows | Default |
|---|---|---|---|
| 0 | Simulator and local checks | Simulator tools, `c_precheck`, status | On |
| 1 | Fixed lab actions | Deploy to `V2_*`, KULT build, KXCI restart; gated `EX`/`GP` on hardware | Off until phases 0 to 4 pass |
| 2 | Remote shell | Allowlisted commands; free shell only with an extra flag | Off |
| 3 | Screen control | Screenshot, click, type, window list | Off |

- Tiers 2 and 3 need a **per-session human approval** that expires
  (default 2 hours). Expiry or the kill switch drops back to tier 1.
- Hardware `EX` additionally requires the fixture interlock to have passed in
  the current session.
- A tier only works if all lower tiers are healthy.

## Hardware envelope

The MCP server parses every `EX` string before it reaches KXCI. Each allowed
module has a registered parameter parser with limits. Modules that are not
registered are rejected.

### SMU

| Parameter | Limit | Why |
|---|---|---|
| Force voltage | \|V\| ≤ 1.0 V | 1 V / 10 kΩ = 100 µA |
| Current limit / compliance | ≤ 200 µA | 2x headroom over expected current |
| Points per sweep | ≤ 200 | Short runs |
| Total run time | ≤ 30 s | Timeout companion |

### PMU (PMU1, dual channel through the RPMs)

| Parameter | Limit | Why |
|---|---|---|
| Any force or bias level | \|V\| ≤ 1.0 V | Same bound as SMU |
| I-range | one of 10 µA, 100 µA, 1 mA (from `PMU_DISCRETE_I_RANGES`) | Avoids high-current ranges |
| Current limit | ≤ 1 mA | Soft protection |
| Pulse / segment width | ≥ 1 µs (hardware minimum is 20 ns) | Stays well clear of edge cases |
| `max_points` | ≤ 30 000 | Memory and transfer time |
| Estimated seg-arb segments per burst | ≤ 350 (`_PMU_OBSERVED_SINGLE_BURST_SEGMENTS`) | Practical ceiling seen on this setup; hardware max is 2048 |
| Estimated burst duration | ≤ 10 s | Timeout companion |

The existing script limits in `kxci_scripts.py` are much wider
(±20 V, 20 ns, 0.8 A). V2 must not rely on them.

The same limits go into the `V2_*` C module template as constants, checked at
the top of the module function. A direct KXCI call that skips the gate still
hits those checks.

## Fixture interlock

Before the first hardware `EX` in a session, and after every rebuild or KXCI
restart:

1. Run one fixed SMU check using the existing
   `EX A_Check_Connection smu_check_connection(...)` with
   bias 0.1 V and current limit 100 µA (expected current 10 µA).
2. Compute R from the returned V and I.
3. Require 9.5 kΩ ≤ R ≤ 10.5 kΩ.
4. On failure, lock all hardware tools until a human re-checks the wiring and
   clears the lock.

This catches a real sample left on the station, an open lead, or a missing
resistor before any AI-built module runs. Running `A_Check_Connection` is the
only use of a non-`V2_*` library the gate allows, and only with these fixed
parameters.

## Instrument lock, timeouts, abort

- One instrument lock: only one `EX`, build, or KXCI restart at a time.
- Timeouts: 60 s for SMU `EX`, 120 s for PMU `EX`, 300 s for a build.
- On timeout, error, or MCP client disconnect, run `hw_abort`: send `DE`,
  device clear, return outputs to 0 V, release the lock.
- `hw_abort` and the kill switch are available at every tier.

## Library protection

- The AI may create, edit, build and delete only libraries whose name matches
  `^V2_[A-Za-z0-9_]+$`.
- Everything else is read-only to the lab-agent account. Libraries currently
  used by this repo include `A_Read_Train`, `A_Retention`,
  `A_pulse_read_grouped_multi`, `A_Poteniation_Depression` (that spelling is
  in the code), `A_Iv_Sweep`, `A_Check_Connection`,
  `A_Ch1Read_Ch2Laser_Pulse`, `A_pmu_laser_smu_read`, `ACraig5`, `ACraig12`,
  `ACraig13`, `Labview_Controlled_Programs_Kemp` and
  `Python_Controlled_PMU_Craig`.
- New `V2_*` modules must use module names that do not clash with existing
  ones, so Clarius `proto.h` stays unambiguous (the same issue noted in
  `pmu_ttl_laser_ch1/README.md`).

## Approvals

| Event | Needs |
|---|---|
| First hardware `EX` of a newly built module version | Human approval in the MCP client |
| Enabling tier 2 or 3 | Human flag with expiry |
| Free (non-allowlisted) shell | Extra human flag, logged as high risk |
| Clearing a failed fixture interlock | Human confirmation after checking wiring |
| Changing the envelope in `v2/config.toml` | Human edit only; the AI has no tool for it |
| Anything outside `V2_*` | Not possible; no tool exists |

## Backups (phase 0, before anything is installed)

1. Full Windows system image of the 4200 on external media.
2. Copy of the Keithley user-library tree (typically under `C:\s4200\kiuser`;
   confirm the real path) onto the main PC and a second medium.
3. A one-page restore procedure kept with the image.
4. After installing V2 pieces, confirm that an existing library still builds
   and a known-good `EX` still returns data before enabling hardware tools.

## Accounts and secrets

- The lab agent runs as a dedicated non-admin user (for example `labagent`).
- That user can write only to `usrlib\V2_*` and its own log folder.
- The lab-agent token lives only on the main PC and in a protected config
  file on the 4200. It is never committed to this repo.
- SSH keys for the Remote-SSH option follow the same rule.

## Audit log

The main PC writes one JSON line per action: timestamp, tool, tier, arguments
summary, result, duration. Tier-3 screenshots go into a dated folder. The lab
agent keeps its own matching log. Logs are never deleted by any AI tool.

## Kill switch

1. MCP tool `hw_kill_switch()`: stops the lab agent, runs `hw_abort`, closes
   KXCI if reachable, drops all tiers to 0.
2. A desktop shortcut on the main PC that does the same without the MCP
   server.
3. Physical fallback: the 4200's own front-panel / Clarius stop, and
   disconnecting the fixture.

After a kill, a human must re-enable tiers.

## Network isolation

Details in [01_network_link.md](01_network_link.md). Hard rules:

- No default gateway and no DNS on the 4200.
- Internet Connection Sharing off on the main PC.
- 4200 firewall allows inbound only from `192.168.50.1`, only on the ports
  in use.
- The 4200 is never connected to the lab LAN or the internet, including
  through a proxy.
