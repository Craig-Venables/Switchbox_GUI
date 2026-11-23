# 02 — Lab agent on the 4200

The lab agent is a small Python program on the 4200. It is not an AI and
makes no decisions. It performs a short list of fixed actions when the MCP
server on the main PC asks. Safety rules: [00_safety.md](00_safety.md).
Network: [01_network_link.md](01_network_link.md).

If you choose the Remote-SSH option ([09](09_remote_ssh_option.md)), the lab
agent is still useful for the fixed build/restart actions and for screen
control, but its shell endpoint is not needed.

## Offline install

The 4200 has no internet, so download everything on the main PC and copy it
over the cable (shared folder) or by USB stick.

1. On the main PC, download the Windows x64 Python installer. Pin one version
   (for example 3.11) and use it everywhere.
2. On the main PC, download wheels for that version (PowerShell, one line):

```powershell
pip download fastapi uvicorn pydantic tomli --platform win_amd64 --python-version 3.11 --only-binary=:all: -d wheels
```

   Tier 3 also needs: `mss pillow pyautogui pywinauto`. Download those only
   when you plan to enable tier 3.

3. Copy the installer, the `wheels` folder and the `lab_agent` folder to the 4200.
4. Install Python for the `labagent` user ("Add to PATH" ticked).
5. Install packages without internet:

```powershell
pip install --no-index --find-links wheels fastapi uvicorn pydantic tomli
```

Python is independent of Clarius. Install nothing else.

## Layout on the 4200

```text
C:\lab_agent\
  lab_agent.py          FastAPI app
  config.toml           bind address, port, token hash, usrlib_root, KXCI path
  allowlist.txt         tier-2 command allowlist (empty by default)
  logs\                 audit log (append-only)
  start_lab_agent.bat   started by Task Scheduler
```

`usrlib_root` must be the real user-library folder on your unit (often under
`C:\s4200\kiuser\usrlib`; confirm during phase 0). The agent refuses any path
that does not resolve inside `usrlib_root\V2_*`, after resolving `..` and
symbolic links.

## Tier-1 API

Every request needs `Authorization: Bearer <token>`. The agent binds to
`192.168.50.2:8765` only.

| Method | Path | Does |
|---|---|---|
| `GET` | `/status` | Agent version, enabled tiers, KXCI running or not, last build result, build method in use |
| `POST` | `/deploy` | Write uploaded `.c`/`.h` files into `usrlib_root\V2_<Lib>\src\` |
| `POST` | `/build` | Build library `V2_<Lib>` with KULT; return the parsed log |
| `POST` | `/kxci/stop` | Stop KXCI |
| `POST` | `/kxci/start` | Start KXCI |
| `POST` | `/abort` | Stop an in-progress build |

### Checks on `/deploy` and `/build`

- Library name matches `^V2_[A-Za-z0-9_]+$`.
- File names match `^[A-Za-z0-9_]+\.(c|h)$`; no paths.
- Payload at most 2 MB.
- Every `.c` file must contain the V2 safety-constant block (see
  [05_build_pipeline.md](05_build_pipeline.md)); otherwise reject.
- The previous version of each file is kept in `V2_<Lib>\history\<timestamp>\`
  so a bad deploy can be rolled back.

### Build and restart sequence

KXCI and Clarius/KULT may not be able to use the instrument at the same time,
and a rebuilt library may not be picked up until KXCI restarts. Until tested
otherwise, assume both are true:

1. Main PC takes the instrument lock and sends `DE`.
2. `/kxci/stop`.
3. `/build` (KULT command line if available; otherwise the GUI through tier 3).
4. `/kxci/start`.
5. Main PC connects over GPIB, sends `DE`, then `*IDN?` (the same sequence as
   `KXCIClient.connect`). A healthy reply ends the sequence.
6. Main PC re-runs the fixture interlock, then releases the lock.

If any step fails, the main PC runs `hw_abort` and reports the step that
failed.

## Autostart

KULT and KXCI are desktop programs, so the agent runs in the logged-in
session, not as a Windows service.

1. Create a non-admin Windows user `labagent`.
2. Permissions: write only to `usrlib_root\V2_*` and `C:\lab_agent\logs`;
   read-only on everything else in `usrlib_root`.
3. Turn on auto-login for that user, and turn off screen lock and screensaver.
4. Task Scheduler task:
   - Trigger: at log on of `labagent`.
   - Action: `C:\lab_agent\start_lab_agent.bat` (runs `pythonw.exe lab_agent.py`).
   - "Run only when user is logged on".
   - Restart on failure: every 1 minute, up to 3 times.

Check whether Clarius and KXCI run correctly under a non-admin user. If they
need admin rights, record that in [08_rollout_checklist.md](08_rollout_checklist.md)
and keep the agent itself non-admin, starting KXCI through a narrowly scoped
scheduled task instead.

## Audit log

One JSON line per request, for example:

```json
{"ts": "2026-11-23T12:00:00Z", "path": "/build", "lib": "V2_Readtrain", "ok": true, "ms": 41230}
```

Logs rotate by size. The agent never deletes logs; the main PC copies them
off.

## Tiers 2 and 3

Shell and screen endpoints are described in
[03_remote_control.md](03_remote_control.md). They are not loaded unless
enabled in `config.toml`.
