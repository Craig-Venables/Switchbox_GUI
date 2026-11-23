# 03 — Remote control (tiers 2 and 3)

These tiers let the AI do on the 4200 what a person at the keyboard could do.
They are **off by default**, need per-session human approval, and expire.
Read [00_safety.md](00_safety.md) first.

While either tier is on, only the 10 kOhm fixture may be connected.

For an alternative to the tier-2 shell, see
[09_remote_ssh_option.md](09_remote_ssh_option.md).

## Tier 2 — Remote shell

### Primary: lab-agent `/shell`

`POST /shell` with `{"cmd": "...", "timeout_s": 30}`.

- Runs in the logged-in desktop session, so programs it starts appear on
  screen.
- **Allowlist mode (default):** the command must match an entry in
  `allowlist.txt`. Start with read-only commands, for example:
  - listing `usrlib_root\V2_*`
  - reading KULT/Clarius build logs
  - `tasklist` to see whether KXCI is running
- **Free mode:** only with the extra human flag `ALLOW_FREE_SHELL=1` for the
  session. Logged as high risk.
- Output is capped (for example 200 KB) and returned with the exit code.

### Recovery: PowerShell Remoting (WinRM)

Used only when the lab agent itself has crashed. One-time setup on the 4200
(as admin, works offline):

```powershell
Enable-PSRemoting -Force
```

On the main PC:

```powershell
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "192.168.50.2"
```

Firewall: TCP 5985 from `192.168.50.1` only. Remoting sessions are not the
desktop session, so they are for restarting the agent or reading files, not
for starting Clarius or KXCI.

## Tier 3 — Screen control

Lab-agent endpoints:

| Method | Path | Does |
|---|---|---|
| `GET` | `/screenshot` | PNG of the desktop |
| `GET` | `/windows` | Open windows and their controls (`pywinauto`) |
| `POST` | `/window/click` | Click a named control in a named window |
| `POST` | `/click` | Click at `{x, y}` |
| `POST` | `/type` | Type `{text}` |
| `POST` | `/key` | Press `{keys}`, for example `enter` |

Rules:

- Prefer `/window/click` with control names over raw coordinates.
- `/type` refuses text longer than 2 000 characters.
- Every call saves a screenshot after the action to the audit folder on the
  main PC.

### Requirements

- The desktop stays logged in and unlocked.
- **No Remote Desktop.** RDP takes over the console and locks it when you
  disconnect, which breaks automation and can upset Clarius.
- To watch the screen yourself, install a VNC server (TightVNC or UltraVNC)
  offline, password protected, firewall limited to the main PC. VNC shares the
  real desktop without locking it.

### Main use: KULT without a command line

If KULT on your Clarius version cannot build from the command line, the
`/build` endpoint drives the KULT window with `pywinauto`. Record the working
click sequence once, by hand, then store it in the agent config so it is
repeated identically every time.

## MCP tools

Only available while the tier is enabled and approved:

| Tier | Tools |
|---|---|
| 2 | `remote_shell(cmd, timeout_s)` |
| 3 | `remote_screenshot()`, `remote_list_windows()`, `remote_window_click(title, control)`, `remote_click(x, y)`, `remote_type(text)`, `remote_key(keys)` |

## Approval flow

1. A human sets `tier2_enabled` or `tier3_enabled` with an expiry in the MCP
   server's session overlay (not in the committed config).
2. The server records who approved it and when.
3. On expiry or kill switch, the tools disappear and calls are refused.

## Risks

| Risk | Mitigation |
|---|---|
| AI bypasses the `EX` envelope with a direct KXCI call | Fixture-only wiring; limits inside the C template; free shell off by default |
| AI changes or deletes production libraries | Account has write access to `V2_*` only |
| AI changes Windows settings or drivers | Non-admin account |
| A dialog box blocks a build | Screenshot and click tools; VNC for a human to clear it |
| Desktop locked after RDP | RDP not used |

## When to use which

- Normal loop: tiers 0 and 1.
- A build needs a click, or a one-off diagnosis: enable tier 3 for that
  session, then let it expire.
- Lab agent not responding: WinRM to restart it, then back to tier 1.
