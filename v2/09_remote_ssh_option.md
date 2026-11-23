# 09 — Option: Cursor Remote-SSH into the 4200

An alternative way for the AI to work directly on the 4200: Cursor on the main
PC connects to the 4200 over SSH, so the AI's file edits and terminal commands
happen on the 4200. The model itself still runs in the cloud and is reached
from the main PC. Safety rules: [00_safety.md](00_safety.md).

This option is **unproven offline**. Test it in phase 6
([08_rollout_checklist.md](08_rollout_checklist.md)) before relying on it.

## What it replaces and what it does not

| Need | Remote-SSH covers it? |
|---|---|
| Editing `V2_*` source on the 4200 | Yes |
| Running KULT builds from a terminal (if a command line exists) | Yes |
| Tier-2 shell | Yes; replaces the lab-agent `/shell` |
| Screen control for KULT/Clarius dialogs | No; still tier 3 of the lab agent |
| Safety gate for instrument `EX` commands | No; `EX` still goes through the MCP server over GPIB |
| Library protection | Only through Windows permissions on the SSH account |

Because Remote-SSH gives a full shell, treat enabling it like enabling tier 2
with free shell: human approval and fixture-only wiring.

## Setup

### On the 4200

1. On the main PC, download the Win32-OpenSSH MSI (64-bit) from the
   PowerShell/Win32-OpenSSH releases on GitHub. Copy it to the 4200 and
   install it. Windows' built-in "optional feature" install needs internet,
   so it will not work here.
2. Configure `C:\ProgramData\ssh\sshd_config`:

```text
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers labagent
ListenAddress 192.168.50.2
```

3. Put the main PC's public key in `C:\Users\labagent\.ssh\authorized_keys`.
4. Firewall: TCP 22 inbound from `192.168.50.1` only.
5. Set the `sshd` service to start automatically.

### On the main PC

1. Create an SSH key pair for this purpose only; keep the private key out of
   the repo.
2. `~/.ssh/config`:

```text
Host lab4200
  HostName 192.168.50.2
  User labagent
  IdentityFile ~/.ssh/lab4200_ed25519
```

3. Test: `ssh lab4200 whoami` returns `labagent`.
4. In Cursor, connect with Remote-SSH to `lab4200`.

### Offline server install (the uncertain part)

Remote-SSH normally downloads a server component onto the remote machine.
The 4200 cannot download, so:

- Find the exact server build that matches your Cursor version (the commit ID
  shown in Cursor's About dialog).
- Download that server package on the main PC and place it in the location
  Cursor expects under `labagent`'s home folder on the 4200.
- Check Cursor's documentation for the current offline procedure; it changes
  between versions.

If this cannot be made to work reliably, stay with the lab agent
([02](02_lab_agent_4200.md), [03](03_remote_control.md)).

## Questions to confirm

- Are all of Cursor's model requests made from the main PC when connected
  over Remote-SSH? If the remote side tries to reach the internet, it simply
  fails because there is no gateway; nothing leaks, but the feature would not
  work.
- Does Cursor's server component run on this Windows version under a
  non-admin account?
- Does it interfere with Clarius or KXCI (CPU, memory, file locks)? Watch
  during a long PMU run.

## Risks

| Risk | Mitigation |
|---|---|
| Full shell bypasses the lab agent's allowlist | Non-admin account; write access only to `V2_*`; fixture-only wiring; enable only with approval |
| AI runs a direct KXCI call that skips the gate | Safety constants inside every `V2_*` module; GPIB held by the MCP server |
| Cursor updates break the offline server | Pin the Cursor version used for this; re-test after updates |
| SSH key leaked | Key used only for this link; the 4200 is reachable only from the main PC anyway |

## Tests

1. `ssh lab4200 whoami` works; password login is refused.
2. From another IP (if you can arrange one), SSH is refused.
3. Cursor Remote-SSH opens a `V2_*` folder and can edit a file.
4. Writing a file in a non-`V2_*` library is refused by Windows permissions.
5. A long PMU run with Cursor connected completes normally.
