# Known bugs

Appended by the tester subagent. One entry per bug; don't delete entries, mark them fixed.

<!-- Template:
## YYYY-MM-DD — short title
- **Status:** open | fixed (commit)
- **Found by:** tester
- **How to reproduce:** command / action
- **Error:** traceback or visual difference
- **File:** path:line
-->

## 2026-11-14 — simulation_4200 pointless f-string (F541)
- **Status:** fixed (removed unused f-prefix, simulation_4200.py:670)
- **Found by:** tester
- **How to reproduce:** `.venv\Scripts\python.exe -m ruff check --isolated --select E,F,W,I --ignore E501 Equipment/SMU_AND_PMU/keithley4200/simulation_4200.py`
- **Error:** F541 f-string without any placeholders
- **File:** Equipment/SMU_AND_PMU/keithley4200/simulation_4200.py:670
