# Cursor usage cap (unofficial)

Cursor has no setting to stop at a percentage of included usage, and no official usage API for individual plans (the Admin API at `api.cursor.com/teams/*` is team-admin only). This documents an **unofficial** workaround.

## 1. Endpoint
`GET https://cursor.com/api/usage-summary`

The same endpoint the dashboard Usage page uses. As observed by community tools (e.g. CursorMeter), it returns the membership/plan type, billing cycle start and end, and a `plan` object with used, limit, remaining and percentage fields including `totalPercentUsed`, plus on-demand status. Field names are observed, not documented, so check the real response first.

## 2. Authentication
Requires your browser session cookie **`WorkosCursorSessionToken`**:
1. Log in at https://cursor.com/dashboard in your browser.
2. Open developer tools (F12) > Application > Cookies > `https://cursor.com`.
3. Copy the value of `WorkosCursorSessionToken`.
4. Put it in an environment variable for the current shell only: `export CURSOR_SESSION_TOKEN='...'`

## 3. ⚠️ Warning
This cookie is effectively your **full Cursor login**: anyone or anything holding it can act as your account. **Never commit it to this repo**, never paste it into code, chat, AGENTS.md or a config file that is tracked. Keep it in an environment variable only. The cookie expires; grab a fresh one when requests start returning 401/403.

## 4. Example script (`check_usage.py`, keep outside or untracked)
```python
"""Poll Cursor usage-summary; exit non-zero once total percent used reaches the cap."""
import json, os, sys, time, urllib.request

CAP = float(os.environ.get("CURSOR_USAGE_CAP", "75"))
POLL_SECONDS = 300
token = os.environ.get("CURSOR_SESSION_TOKEN")
if not token:
    sys.exit("Set CURSOR_SESSION_TOKEN first (see USAGE_CAP.md).")

def percent_used() -> float:
    req = urllib.request.Request(
        "https://cursor.com/api/usage-summary",
        headers={"Cookie": f"WorkosCursorSessionToken={token}",
                 "Accept": "application/json", "Origin": "https://cursor.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    plan = data.get("plan") or data.get("individualUsage", {}).get("plan") or {}
    pct = plan.get("totalPercentUsed")
    if pct is None:
        raise RuntimeError(f"No totalPercentUsed in response; keys: {list(data)}")
    return float(pct)

while True:
    pct = percent_used()
    print(f"Cursor usage: {pct:.1f}% (cap {CAP:.0f}%)")
    if pct >= CAP:
        print(f"ALERT: usage cap reached ({pct:.1f}% >= {CAP:.0f}%). Stop agent work.")
        sys.exit(2)
    if "--once" in sys.argv:
        break
    time.sleep(POLL_SECONDS)
```
Run once: `python check_usage.py --once` (exit code 2 means the cap is reached). Run continuously without `--once`.

## 5. Caveats
- These endpoints are **unofficial** and reverse-engineered from the dashboard; they can change or break without notice.
- Some older endpoints (e.g. `/api/usage/summary`, request-count fields in `/api/usage`) stopped working after Cursor's **August 2026** pricing change.
- Enforcement is yours: the script only alerts/exits, it doesn't stop Cursor itself.
