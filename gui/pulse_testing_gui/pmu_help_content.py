"""
Text content for the Pulse Testing GUI help guide (4200 PMU focus).

Kept in a separate module so help text can be updated without touching UI layout code.
"""

from __future__ import annotations

from typing import List, Tuple

HelpSection = Tuple[str, str]

# Discrete RPM/PMU ranges (must match kxci_scripts.PMU_DISCRETE_I_RANGES).
PMU_I_RANGES_DISPLAY = "100 nA, 1 uA, 10 uA, 100 uA, 1 mA, ..."

GENERAL_HELP_SECTIONS: List[HelpSection] = [
    (
        "Overview",
        "Pulse Testing runs memristor / pulse tests on Keithley 2450 (TSP) or "
        "4200A-SCS (KXCI + PMU). Results plot in real time; data saves under "
        "Documents/Data_folder/Pulse_Testing/.\n\n"
        "2450: uses Current Limit (clim) on the SMU.\n"
        "4200 PMU: uses PMU Current Range (IRange) on each EX command — see the "
        "'4200 PMU' tab in this guide.",
    ),
    (
        "Getting started",
        "1. Select system (e.g. keithley4200_pmu) and connect.\n"
        "2. Manual Testing tab: pick a test and load a preset if available.\n"
        "3. Set pulse / read parameters (units are us for 4200 timing fields).\n"
        "4. Run Test — watch the log for [KXCI] diagnostics after PMU runs.\n"
        "5. Use presets (Save/Load) once you find settings that work on your DUT.",
    ),
    (
        "Test types (PMU)",
        "• Read -> Write -> Read — single switching pulse between reads.\n"
        "• Endurance — Initial read, then (SET, read, RESET, read) x N.\n"
        "• Endurance Burst Test — same pattern; long runs batched in one EX.\n"
        "• Retention — baseline reads, program pulses, retention reads.\n"
        "• Pulse train / width sweep — see test description in the dropdown.",
    ),
    (
        "Presets",
        "Presets live in Json_Files/tsp_test_presets.json. For speed sweeps on "
        "Endurance, try: DUT 10cyc @ 1us, @ 100ns, @ 20ns (HW min). For retention "
        "with minimum gaps: DUT min gaps 20ns.",
    ),
]

PMU_HELP_SECTIONS: List[HelpSection] = [
    (
        "Hardware: PMU + RPM (required)",
        "Fast pulses use the 4225-PMU with two RPMs in PULSE mode (configured "
        "automatically by the C driver).\n\n"
        "Wiring:\n"
        "  CH1 (force) — DUT high side: SET/RESET/read voltage.\n"
        "  CH2 (measure) — DUT low side: current measurement (0 V bias).\n\n"
        "Use short leads. Stay on the 10 V range for fastest timing (40 V range "
        "raises minimum period).",
    ),
    (
        "Timing units (important)",
        "In this GUI, 4200 pulse/read widths and rise times are in MICROSECONDS (us).\n\n"
        "  1.0  = 1 us\n"
        "  0.1  = 100 ns\n"
        "  0.02 = 20 ns (hardware segment minimum)\n\n"
        "Firmware minimum segment time: 20 ns. Practical fast writes: 100 ns "
        "with 100 ns edges (scope-check). Aggressive floor: 20 ns width + 20 ns rise.",
    ),
    (
        "Fast pulses vs good reads",
        "Writes (SET/RESET) can be very fast; reads need a flat voltage plateau "
        "to measure resistance.\n\n"
        "Recommended split:\n"
        "  Write pulse width / rise: 0.1 us (100 ns) or lower if scope validates.\n"
        "  Read width: 0.2–2 us (wider = more averaging, stabler R).\n"
        "  Read rise: 0.1 us (100 ns) unless read width is sub-200 ns.\n"
        "  Delay between: 0.02 us (20 ns) minimum gap between segments.\n\n"
        "Endurance pattern = many segments per cycle (write + read + write + read). "
        "Cycle time is the sum of all segments, not just write width.",
    ),
    (
        "PMU current range (IRange)",
        "On 4200 PMU tests, resistance uses the APPLIED read voltage (Read V) "
        "divided by measured current. Set PMU Current Range (A) in Test Parameters "
        "(and/or load a preset). It is sent as IRange on the EX command.\n\n"
        "This is NOT the same as 'Current Limit (clim)' on 2450 tests. clim is "
        "ignored for PMU interleaved/endurance timing tests.\n\n"
        "Valid hardware ranges (nearest is chosen automatically):\n"
        f"  {PMU_I_RANGES_DISPLAY}\n\n"
        "Rule of thumb: pick the smallest range where your largest read current "
        "uses roughly 10–80% of full scale.\n\n"
        "Examples:\n"
        "  ~100 nA reads (high R) -> try 1e-6 (1 uA) or 1e-7 (100 nA).\n"
        "  ~5 uA after SET (low R) -> need at least 1e-5 (10 uA).\n"
        "  Device spans both HRS and LRS: one range cannot perfect both — prefer "
        "10 uA if post-SET reads clip, or 1 uA if you only care about high-R states.\n\n"
        "Firmware caps reported R at 1e4/IRange (e.g. 100 MOhm at 100 uA range).",
    ),
    (
        "Finding the right range (step by step)",
        "1. Run a short test (10 cycles) with IRange = 1e-4 (100 uA) default.\n"
        "2. After the run, read the log section:\n"
        "     [KXCI] PMU current range: ...\n"
        "   It shows min/median/max read current and % of full scale.\n"
        "3. If weak reads are <5% of range or nearly identical nA values, lower IRange.\n"
        "4. If peak read exceeds range or R looks clipped on LRS, raise IRange.\n"
        "5. Re-run until the log says 'Current range looks reasonable' or you accept "
        "the LRS/HRS trade-off.\n\n"
        "Quick estimate: I_expected = Read_V / R_guess. Pick range >= I_expected/0.5.",
    ),
    (
        "What the results table means",
        "Read V (V) — programmed read pulse amplitude on CH1 (e.g. 0.2 or 0.3 V).\n"
        "Current (A) — measured on CH2 during the read window.\n"
        "Resistance (ohm) — Read_V / |I|, capped by firmware.\n\n"
        "Do not expect CH2 terminal voltage to equal Read V; low-side measure "
        "stays near 0 V.",
    ),
    (
        "Presets for speed",
        "Endurance presets (load from preset dropdown):\n"
        "  DUT 10cyc @ 1us      — scope-validated everyday speed.\n"
        "  DUT 10cyc @ 100ns    — fast writes/reads.\n"
        "  DUT 10cyc @ 20ns (HW min) — aggressive; verify on scope.\n"
        "  DUT min gaps 20ns    — retention with 20 ns gaps.\n\n"
        "Always confirm CH1 on a scope: flat top at pulse voltage, edges not rounded "
        "by excessive DUT capacitance.",
    ),
    (
        "Endurance Burst Test (100+ cycles)",
        "One Python/EX call; the 4200 runs several INTERNAL sub-bursts (~19 cycles each, "
        "~350 seg-arb segments per sub-burst). Pulses inside a sub-burst are continuous; "
        "there is a short hardware gap while the PMU reloads the next sub-burst waveform "
        "(not a 1 s Python delay; typically tens to hundreds of ms after re-arm tuning).\n\n"
        "Sub-burst 2+ skips the initial read and keeps RPM/PMU armed (not_init path) to "
        "minimize the gap. Scope: gaps are between sub-bursts, not between every cycle.\n\n"
        "To reduce gaps further: fewer/larger sub-bursts only if your USRLIB tolerates "
        "more segments (raise PMU_MAX_SEG_PER_BURST cautiously); or use classic Endurance "
        "with fewer cycles per EX from Python.",
    ),
    (
        "Troubleshooting",
        "• Identical nA on every read — IRange too high; lower PMU current range.\n"
        "• R too low / flat after SET — range too low (clipping); raise IRange.\n"
        "• EX error -122 — segment time < 20 ns or waveform illegal; widen times.\n"
        "• Scope shows long pulses but log shows short — old waveform config; "
        "reload DUT 1us write preset.\n"
        "• Burst / cycle limits — see test description; endurance burst batches "
        "inside one EX on the 4200.",
    ),
]
