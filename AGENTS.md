# AGENTS.md — Switchbox_GUI ground rules

> REMINDER: Ask Craig to grab his WorkosCursorSessionToken cookie from browser dev tools before using the usage cap script (see USAGE_CAP.md). Never store the cookie value anywhere in this repo.

> Follow TOKEN_LIMITS.md to keep token usage low across all agents.

## What Switchbox is
Switchbox_GUI is a Python (3.10+) Tkinter desktop app that automates electrical characterisation of resistive-switching (memristor) devices on multi-device samples. A sample/device-selector window picks devices; a measurement window runs IV sweeps, pulsed IV, endurance and retention tests, plots live, and saves data.

## Definitions
- **SMU** — source-measure unit (Keithley 2400/2450/4200A-SCS, HP4140B). Sources voltage, measures current, enforces compliance. Accessed via the adapter layer (`IVControllerManager`) so all SMUs share `set_voltage` / `measure_current`.
- **Device map** — the sample layout (JSON config in `Json_Files/`) shown in the sample window; maps device names to positions and relay channels.
- **Multiplexer / switchbox** — Arduino-driven relay matrix that routes the SMU to one device at a time. Accessed via `MultiplexerManager`.
- **Simulator** — drop-in simulated SMUs (e.g. `Equipment/SMU_AND_PMU/keithley2400/simulation_2400.py`) with the same interface as real drivers.

## Hard rules
1. **Never touch real hardware.** Do not open GPIB/VISA/serial connections or drive relays. No agent runs code against real instruments.
2. **Always use the simulator for tests and manual runs.**
3. Never commit secrets, cookies, or tokens.
4. Don't break the GUI layout without saying so; the tester compares element positions against the layout notes below.

## Coding style
- Python 3.10+, follow `ruff.toml`; run `ruff check` before finishing.
- Keep GUI updates on the Tk main thread (use `after()` / queues from worker threads); don't add new widget calls from worker threads.
- Small, focused changes; add or update pytest tests in `tests/` for behaviour changes.
- Put new instruments behind the existing adapter/factory pattern, not in GUI code.

## GUI layout notes (for the tester's screenshot comparison)
- TODO (Craig): describe the expected positions of the main elements in the sample window and measurement window here.

## Delegation rule (main agent)
You are the coordinator. Do not write large changes yourself.
1. Hand each implementation task to the **implementer** subagent, one task at a time, with full context in the prompt (subagents don't see this conversation).
2. After any implementation, **always run the tester subagent** before saying anything is done.
3. Optionally run the **reviewer** subagent on the diff.
4. Only report "done" when the tester reports no new failures; otherwise send failures back to the implementer.
