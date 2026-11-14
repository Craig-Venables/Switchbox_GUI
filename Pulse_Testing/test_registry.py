"""
Pulse Test Registry - the single place to register a pulse test
================================================================

Every pulse test is ONE ``TestSpec`` entry in ``TESTS`` below. That entry decides:

- which systems list the test (``systems``) - replaces the old capability matrix
- the dropdown label, description, parameters and defaults - replaces TEST_FUNCTIONS
- the dropdown order (list order) - replaces TEST_DISPLAY_ORDER
- the plot handler (``plot_type``), how the GUI runs it (``runner``) and live updates (``progress``)

``test_capabilities.py`` and ``test_definitions.py`` are now built from this file and keep
their old public names, so the GUI and SystemWrapper did not have to change.

Adding a test: see ``Pulse_Testing/ADDING_A_TEST.md``. Run
``py -m pytest Pulse_Testing/tests/test_registry.py`` afterwards; it checks every system
you listed really implements the test and accepts every parameter you defined.

Parameter dict keys
-------------------
``default``, ``label``, ``type`` (float | int | bool | str | list | choice) are required.
Optional: ``choices`` (for choice), ``4200a_only`` (only shown on PMU timing systems, values in µs),
``gui_only`` (display option, never sent to the instrument), ``section`` (optical layout grouping).
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional

# ---------------------------------------------------------------------------
# System groups (system ids as used by SystemWrapper / the Connection dropdown)
# ---------------------------------------------------------------------------
SMU_2450: FrozenSet[str] = frozenset({"keithley2450", "keithley2450_sim"})
SMU_2400: FrozenSet[str] = frozenset({"keithley2400"})  # Keithley 2400 and 2401 (SCPI)
SMU_24XX: FrozenSet[str] = SMU_2450 | SMU_2400
PMU_4200: FrozenSet[str] = frozenset({"keithley4200_pmu", "keithley4200a"})  # 4200a = legacy id of PMU profile
SMU_4200: FrozenSet[str] = frozenset({"keithley4200_smu", "keithley4200_smu_sim"})
CUSTOM_4200: FrozenSet[str] = frozenset({"keithley4200_custom"})  # connect/setup only, no tests

ALL_SYSTEMS: FrozenSet[str] = SMU_24XX | PMU_4200 | SMU_4200 | CUSTOM_4200

# Time parameters entered in the GUI's ns/µs/ms/s unit selector.
TIME_PARAMS: tuple = (
    "pulse_width", "delay_between", "delay_between_pulses", "delay_between_reads",
    "delay_before_read", "delay_between_cycles", "post_read_interval", "reset_width",
    "delay_between_voltages", "delay_between_levels",
)
# PMU edge/read-window parameters: always entered in µs on PMU systems (not affected by the unit selector).
PMU_EDGE_PARAMS: tuple = ("read_width", "read_delay", "read_rise_time", "pulse_rise_time", "pulse_fall_time")

RUNNERS = ("system", "optical", "optical_sweep")


@dataclass(frozen=True)
class TestSpec:
    """One pulse test as it appears in the GUI.

    function:     method name on the system adapters (and usually on the Equipment scripts)
    systems:      system ids that list and run this test (use the groups above)
    display_name: dropdown label; None for hidden tests that are runnable but not listed
    runner:       "system" (SystemWrapper.run_test), "optical" or "optical_sweep" (optical_runner, laser-synced)
    progress:     pass a progress_callback so the plot updates while the test runs
    hidden:       supported by the backend but not shown in the dropdown yet
    """

    function: str
    systems: FrozenSet[str]
    display_name: Optional[str] = None
    description: str = ""
    params: Mapping[str, Dict[str, Any]] = field(default_factory=dict)
    plot_type: str = "time_series"
    runner: str = "system"
    progress: bool = False
    hidden: bool = False


# Dropdown order = list order.
TESTS: List[TestSpec] = [
    TestSpec(
        function="endurance_test",
        display_name="Endurance",
        systems=SMU_24XX | PMU_4200,
        plot_type="endurance",
        description=(
            "Pattern: Initial Read → (SET → Read → RESET → Read) × N\n"
            "PMU timing (µs): firmware min 0.02 (20 ns) flat-top; scope-validated ~0.1 (100 ns).\n"
            "2-ch PMU required: CH1 force / CH2 measure (same as Read→Write→Read).\n"
            "Use DUT 10cyc @ 20ns → 10us presets to sweep speed. Limit = voltage / cycle-count stress."
        ),
        params={
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (µs) [PMU] / (ms) [SMU]", "type": "float"},
            "read_voltage": {"default": 0.3, "label": "Read Voltage (V)", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "delay_between": {"default": 1.0, "label": "Delay Between (µs) [PMU] / (ms) [SMU]", "type": "float"},
            "clim": {"default": 0.001, "label": "Current Limit (A)", "type": "float"},
            "read_width": {"default": 2.0, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_rise_time": {"default": 0.1, "label": "Read Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "pulse_rise_time": {"default": 0.1, "label": "Write Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "plot_y_axis": {"default": "resistance", "label": "Plot Y-Axis", "type": "choice", "choices": ["resistance", "current"], "gui_only": True},
        },
    ),
    TestSpec(
        function="endurance_burst_test",
        display_name="Endurance Burst Test",
        systems=PMU_4200,
        plot_type="endurance",
        description=(
            "EXPERIMENTAL — validates instrument-side burst batching (pmu_endurance_burst_test).\n"
            "Same pattern as Endurance but one EX command; C batches internally (~20 cycles/burst).\n"
            "Requires redeploy: add pmu_endurance_burst_test.c to A_pulse_read_grouped_multi.\n"
            "Use this to prove 100+ cycles before changing the main Endurance test."
        ),
        params={
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (µs)", "type": "float"},
            "read_voltage": {"default": 0.3, "label": "Read Voltage (V)", "type": "float"},
            "num_cycles": {"default": 100, "label": "Total Cycles (batched on 4200)", "type": "int"},
            "delay_between": {"default": 1.0, "label": "Delay Between (µs)", "type": "float"},
            "clim": {"default": 0.001, "label": "Current Limit (A)", "type": "float"},
            "read_width": {"default": 2.0, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_rise_time": {"default": 0.1, "label": "Read Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "pulse_rise_time": {"default": 0.1, "label": "Write Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "plot_y_axis": {"default": "resistance", "label": "Plot Y-Axis", "type": "choice", "choices": ["resistance", "current"], "gui_only": True},
        },
    ),
    TestSpec(
        function="retention_test",
        display_name="Retention",
        systems=PMU_4200,
        plot_type="retention",
        description=(
            "PMU fast retention (A_Retention / pmu_retention_dual_channel).\n"
            "Pattern: Baseline reads → program pulse train → retention reads (min 8, max 1000).\n"
            "2-ch PMU required: CH1 force / CH2 measure (same wiring as Endurance).\n"
            "Presets: Smoke → DUT (more reads/pulses) → Limit (100ns, 20ns gaps, 200 reads)."
        ),
        params={
            "pulse_voltage": {"default": 2.0, "label": "Program Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Program Pulse Width (µs)", "type": "float"},
            "num_program_pulses": {"default": 5, "label": "Program Pulses (count)", "type": "int"},
            "num_initial_reads": {"default": 2, "label": "Baseline Reads (count)", "type": "int"},
            "read_voltage": {"default": 0.3, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 8, "label": "Retention Reads (count, min 8)", "type": "int"},
            "delay_between_reads": {"default": 2.0, "label": "Delay Between Reads (µs)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Program Pulses (µs)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
            "read_width": {"default": 2.0, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_rise_time": {"default": 0.1, "label": "Read Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "pulse_rise_time": {"default": 0.1, "label": "Program Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "pulse_fall_time": {"default": 0.1, "label": "Program Fall Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "plot_y_axis": {"default": "resistance", "label": "Plot Y-Axis", "type": "choice", "choices": ["resistance", "current"], "gui_only": True},
        },
    ),
    TestSpec(
        function="retention_test",
        display_name="Timed Retention",
        systems=SMU_24XX,
        plot_type="time_series",
        description=(
            "SMU/TSP timed retention (2450 / 2400).\n"
            "Pattern: Initial state read → program pulse → post-pulse read → reads every N seconds until duration.\n"
            "Default: every 60 s (1 min) for 10000 s (~2.8 h). Lower duration or raise interval for smoke tests.\n"
            "Read Every / Duration are absolute seconds after the pulse (not affected by ns/µs/ms unit)."
        ),
        params={
            "pulse_voltage": {"default": 2.0, "label": "Program Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 0.1, "label": "Program Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "read_every_s": {"default": 60.0, "label": "Read Every (s) — 60 = every minute", "type": "float"},
            "retention_duration_s": {"default": 10000.0, "label": "Retention Duration (s) (~2.8 h)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="log_retention_test",
        display_name="Log Retention",
        systems=SMU_24XX,
        plot_type="log_retention",
        description=(
            "Publication-quality log-spaced retention (2450 / 2400).\n"
            "Pattern: Initial read → program pulse → post-pulse read → log-spaced reads from t_min to t_max.\n"
            "Optional early burst (0.05–1 s) when t_min < 1 s for fast initial relaxation.\n"
            "Fits R(t) = R₀(1 + α·log(1+t)) after the run.\n"
            "t_min / t_max / num_reads are absolute seconds (not affected by ns/µs/ms unit)."
        ),
        params={
            "pulse_voltage": {"default": 2.0, "label": "Program Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 0.1, "label": "Program Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "t_min_s": {"default": 0.1, "label": "First Read After Pulse (s)", "type": "float"},
            "t_max_s": {"default": 86400.0, "label": "Last Read After Pulse (s)", "type": "float"},
            "num_reads": {"default": 80, "label": "Log-Spaced Read Count", "type": "int"},
            "include_early_burst": {"default": True, "label": "Early Burst (0.05–1 s before log segment)", "type": "bool"},
            "read_intervals": {"default": "", "label": "Explicit Intervals (s, comma) — overrides schedule", "type": "str"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="volatile_screening_test",
        display_name="Volatile Screening",
        systems=SMU_24XX,
        plot_type="volatile_screening",
        description=(
            "Volatile vs non-volatile screening (2450 on-instrument burst; 2400 PC-timed).\n"
            "Phase A: baseline → pulse → post-pulse → dense reads (ms–s, 50+ points).\n"
            "Phase B (optional): slow PC tail for longer non-volatile confirmation.\n"
            "Auto verdict: VOLATILE / NON-VOLATILE / MARGINAL / INCONCLUSIVE.\n"
            "Schedule: log (default), linear, or explicit comma intervals in seconds."
        ),
        params={
            "pulse_voltage": {"default": 2.0, "label": "Program Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Program Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "schedule_mode": {"default": "log", "label": "Schedule Mode", "type": "choice", "choices": ["log", "linear", "explicit"]},
            "t_min_s": {"default": 0.001, "label": "First Read After Pulse (s)", "type": "float"},
            "burst_t_max_s": {"default": 5.0, "label": "Burst End Time (s)", "type": "float"},
            "t_max_s": {"default": 5.0, "label": "Overall End Time (s)", "type": "float"},
            "num_reads": {"default": 50, "label": "Burst Read Count", "type": "int"},
            "read_intervals": {"default": "", "label": "Explicit Intervals (s) — e.g. 0.001,0.01,0.1,1", "type": "str"},
            "include_slow_tail": {"default": False, "label": "Enable Slow Tail (Phase B)", "type": "bool"},
            "slow_tail_start_s": {"default": 10.0, "label": "Slow Tail Start (s)", "type": "float"},
            "slow_tail_num_reads": {"default": 30, "label": "Slow Tail Read Count", "type": "int"},
            "retention_threshold": {"default": 0.85, "label": "Non-Volatile Threshold (fraction retained)", "type": "float"},
            "min_switch_ratio": {"default": 0.05, "label": "Min Switch Ratio |ΔR/R_base|", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="pulse_read_repeat",
        display_name="Read → Write → Read",
        systems=SMU_24XX | PMU_4200,
        plot_type="time_series",
        description=(
            "Pattern: Initial Read → (Pulse → Read → Delay) × N\n"
            "4200 PMU: use keithley4200_pmu, ns/µs timing, CH1 force / CH2 measure.\n"
            "Validated bench: 1 µs write @ 1 V with reads either side (preset: DUT 1us write)."
        ),
        params={
            "pulse_voltage": {"default": 1.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.3, "label": "Read Voltage (V)", "type": "float"},
            "delay_between": {"default": 0.02, "label": "Delay Between (ms)", "type": "float"},
            "num_cycles": {"default": 1, "label": "Number of Cycles", "type": "int"},
            "clim": {"default": 0.001, "label": "Current Limit (A)", "type": "float"},
            "read_width": {"default": 2.0, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_delay": {"default": 0.02, "label": "Read Delay (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_rise_time": {"default": 0.1, "label": "Read Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "pulse_rise_time": {"default": 0.1, "label": "Write Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "enable_debug_output": {"default": False, "label": "Enable Debug Output [4200A only]", "type": "bool", "4200a_only": True},
        },
    ),
    TestSpec(
        function="multi_pulse_then_read",
        display_name="Pulse Train → Read",
        systems=SMU_24XX | PMU_4200,
        plot_type="time_series",
        description=(
            "Pattern: Initial Read → (Pulse×N → Read×M) × Cycles\n"
            "4200 PMU: 2-ch (CH1 force / CH2 measure). Multiple pulses then multiple reads per cycle"
        ),
        params={
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses_per_read": {"default": 10, "label": "Pulses Per Cycle", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 1, "label": "Reads Per Cycle", "type": "int"},
            "delay_between_reads": {"default": 10.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "num_cycles": {"default": 20, "label": "Number of Cycles", "type": "int"},
            "delay_between_cycles": {"default": 10.0, "label": "Delay Between Cycles (ms)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
    ),
    TestSpec(
        function="pulse_multi_read",
        display_name="Pulse → Multi-Read",
        systems=SMU_24XX | PMU_4200,
        plot_type="time_series",
        description=(
            "Pattern: Initial Read → (Pulse × M) → Read × N\n"
            "Monitor state relaxation/drift after pulses"
        ),
        params={
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "num_pulses": {"default": 1, "label": "Number of Pulses", "type": "int"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 50, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 100.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="multi_read_only",
        display_name="Read Only",
        systems=SMU_24XX | PMU_4200,
        plot_type="time_series",
        description=(
            "Pattern: Just reads, no pulses\n"
            "Baseline noise, read disturb characterization"
        ),
        params={
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 100, "label": "Number of Reads", "type": "int"},
            "delay_between": {"default": 100.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="width_sweep_with_reads",
        display_name="Pulse Width Sweep",
        systems=SMU_24XX | PMU_4200,
        plot_type="width_vs_resistance",
        description=(
            "Pattern: Initial Read, (Pulse→Read)×N, Reset (per width)\n"
            "4200 PMU: 2-ch (CH1 force / CH2 measure). Find optimal pulse timing, measure speed dependence"
        ),
        params={
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3,50e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 0.001, "label": "Reset Width (s)", "type": "float"},
            "delay_between_widths": {"default": 5.0, "label": "Relaxation Delay Between Width Blocks (s)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="width_sweep_with_all_measurements",
        display_name="Pulse Width Sweep (+ I)",
        systems=SMU_24XX,
        plot_type="width_vs_resistance",
        description=(
            "Pattern: Initial Read, (Pulse(measured)→Read)×N, Reset (per width)\n"
            "Full characterization including pulse peak currents"
        ),
        params={
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 0.001, "label": "Reset Width (s)", "type": "float"},
            "delay_between_widths": {"default": 5.0, "label": "Relaxation Delay Between Width Blocks (s)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="potentiation_depression_cycle",
        display_name="Pot / Dep Cycle",
        systems=SMU_24XX | PMU_4200,
        plot_type="pot_dep_cycle",
        description=(
            "Pattern: Initial Read → (Gradual SET → Gradual RESET) × N cycles\n"
            "4200 PMU: 2-ch (CH1 force / CH2 measure). Synaptic weight update, neuromorphic applications"
        ),
        params={
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "steps": {"default": 20, "label": "Steps (each direction)", "type": "int"},
            "num_cycles": {"default": 1, "label": "Number of Cycles", "type": "int"},
            "delay_between_cycles": {"default": 10.0, "label": "Delay Between Cycles (ms)", "type": "float"},
            "delay_between_pulses": {"default": 10.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "delay_before_read": {"default": 0.02, "label": "Delay Before Read (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="potentiation_only",
        display_name="Potentiation",
        systems=SMU_24XX | PMU_4200,
        plot_type="time_series",
        description=(
            "Pattern: Initial Read → Repeated SET pulses with reads\n"
            "Optional post-pulse reads to observe relaxation"
        ),
        params={
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses": {"default": 30, "label": "Number of Pulses", "type": "int"},
            "delay_between_cycles": {"default": 10.0, "label": "Delay Between Cycles (ms)", "type": "float"},
            "delay_between_pulses": {"default": 10.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "delay_before_read": {"default": 0.02, "label": "Delay Before Read (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "num_post_reads": {"default": 0, "label": "Post-Pulse Reads (0=disabled)", "type": "int"},
            "post_read_interval": {"default": 1.0, "label": "Post-Read Interval (ms)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
    ),
    TestSpec(
        function="depression_only",
        display_name="Depression",
        systems=SMU_24XX | PMU_4200,
        plot_type="time_series",
        description=(
            "Pattern: Initial Read → Repeated RESET pulses with reads\n"
            "Optional post-pulse reads to observe relaxation"
        ),
        params={
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses": {"default": 30, "label": "Number of Pulses", "type": "int"},
            "delay_between_cycles": {"default": 10.0, "label": "Delay Between Cycles (ms)", "type": "float"},
            "delay_between_pulses": {"default": 10.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "delay_before_read": {"default": 0.02, "label": "Delay Before Read (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "num_post_reads": {"default": 0, "label": "Post-Pulse Reads (0=disabled)", "type": "int"},
            "post_read_interval": {"default": 1.0, "label": "Post-Read Interval (ms)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
    ),
    TestSpec(
        function="relaxation_after_multi_pulse",
        display_name="Relaxation",
        systems=SMU_24XX | PMU_4200,
        plot_type="relaxation_reads",
        description=(
            "Pattern: 1×Read → N×Pulse → N×Read\n"
            "Find how device relaxes after cumulative pulsing"
        ),
        params={
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses": {"default": 10, "label": "Number of Pulses", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 0.1, "label": "Delay Between Reads (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="relaxation_after_multi_pulse_with_pulse_measurement",
        display_name="Relaxation (+ Pulse I)",
        systems=SMU_24XX,
        plot_type="relaxation_all",
        description=(
            "Pattern: 1×Read → N×Pulse(measured) → N×Read\n"
            "Full relaxation with pulse peak currents"
        ),
        params={
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses": {"default": 10, "label": "Number of Pulses", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 0.1, "label": "Delay Between Reads (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="current_range_finder",
        display_name="Current Range Finder",
        systems=SMU_24XX,
        plot_type="range_finder",
        description=(
            "Find optimal current measurement range\n"
            "Tests multiple ranges and recommends best for your device"
        ),
        params={
            "test_voltage": {"default": 0.2, "label": "Test Voltage (V)", "type": "float"},
            "num_reads_per_range": {"default": 10, "label": "Reads Per Range", "type": "int"},
            "delay_between_reads": {"default": 10.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "current_ranges": {"default": "0.001,0.0001,0.00001,0.000001", "label": "Ranges to Test (comma-separated, A)", "type": "list"},
        },
    ),
    TestSpec(
        function="laser_and_read",
        display_name="Laser + Read",
        systems=PMU_4200,
        plot_type="time_series",
        description=(
            "⚠️ IMPORTANT: You MUST reconfigure coax cables before running this test!\n"
            "Pattern: CH1 continuous reads, CH2 independent laser pulse\n"
            "Photo-induced effects, laser-assisted switching, time-resolved photoconductivity"
        ),
        params={
            "read_voltage": {"default": 0.3, "label": "CH1 Read Voltage (V)", "type": "float"},
            "read_width": {"default": 0.5, "label": "CH1 Read Width (µs)", "type": "float"},
            "read_period": {"default": 2.0, "label": "CH1 Read Period (µs)", "type": "float"},
            "num_reads": {"default": 500, "label": "Number of Reads", "type": "int"},
            "laser_voltage_high": {"default": 1.5, "label": "CH2 Laser Voltage (V) - MAX 2.0V!", "type": "float"},
            "laser_voltage_low": {"default": 0.0, "label": "CH2 Baseline Voltage (V)", "type": "float"},
            "laser_width": {"default": 10.0, "label": "CH2 Laser Width (µs)", "type": "float"},
            "laser_delay": {"default": 5.0, "label": "CH2 Laser Delay (µs)", "type": "float"},
            "laser_rise_time": {"default": 0.1, "label": "CH2 Rise Time (µs)", "type": "float"},
            "laser_fall_time": {"default": 0.1, "label": "CH2 Fall Time (µs)", "type": "float"},
            "volts_source_rng": {"default": 10.0, "label": "CH1 Voltage Range (V)", "type": "float"},
            "current_measure_rng": {"default": 1e-05, "label": "Current Range (A) [0=auto]", "type": "float"},
            "sample_rate": {"default": 200000000.0, "label": "Sample Rate (Sa/s)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="pulse_train_varying_amplitudes",
        display_name="Electrical Pulse Train",
        systems=SMU_24XX | PMU_4200,
        plot_type="pulse_train",
        description=(
            "⚡ SMU ELECTRICAL SET/RESET pulses (NO laser, NO continuous read): Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N\n"
            "Sends electrical voltage pulses for memristor programming. Pattern: 1=send pulse voltage, 0=skip (0V).\n"
            "\n"
            "🚫 For OPTICAL tests with laser + continuous SMU read, use 'Optical Pulse Train with Pattern + Read' below."
        ),
        params={
            "num_pulses": {"default": 5, "label": "Number of pulses (slots)", "type": "int"},
            "pulse_pattern": {"default": "11111", "label": "Pattern (1=on, 0=off, e.g. 11010)", "type": "str"},
            "pulse_voltage": {"default": 1.5, "label": "Pulse voltage when on (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_repeats": {"default": 1, "label": "Number of Repeats", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 0.0001, "label": "Current Limit (A)", "type": "float"},
        },
    ),
    TestSpec(
        function="smu_slow_pulse_measure",
        display_name="SMU: Slow Pulse",
        systems=SMU_4200,
        plot_type="time_series",
        description=(
            "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\n"
            "Pattern: Single pulse → Measure resistance during pulse\n"
            "Use for very slow pulses (milliseconds to seconds), relaxation studies\n"
            "Limits: Pulse width 40ns to 480s (vs microseconds for PMU)\n"
            "When NOT to use: Fast pulses (< 1ms) - use PMU functions instead"
        ),
        params={
            "pulse_voltage": {"default": 1.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 0.1, "label": "Pulse Width (s) ⚠️ SECONDS (not ms/µs)", "type": "float"},
            "i_range": {"default": 0.01, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
    ),
    TestSpec(
        function="smu_endurance",
        display_name="SMU: Endurance",
        systems=SMU_4200,
        plot_type="time_series",
        progress=True,
        description=(
            "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\n"
            "Pattern: (SET pulse → Read → RESET pulse → Read) × N cycles\n"
            "Use for endurance cycling with slow pulses (milliseconds to seconds)\n"
            "Limits: Pulse widths 40ns to 480s (vs microseconds for PMU)\n"
            "When NOT to use: Fast pulses (< 1ms) - use PMU functions instead"
        ),
        params={
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "set_duration": {"default": 0.1, "label": "SET Duration (s) ⚠️ SECONDS", "type": "float"},
            "reset_duration": {"default": 0.1, "label": "RESET Duration (s) ⚠️ SECONDS", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "repeat_delay": {"default": 1.0, "label": "Repeat Delay (s) ⚠️ SECONDS", "type": "float"},
            "probe_voltage": {"default": 0.2, "label": "Probe Voltage (V)", "type": "float"},
            "probe_duration": {"default": 0.01, "label": "Probe Duration (s) ⚠️ SECONDS", "type": "float"},
            "i_range": {"default": 0.01, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
    ),
    TestSpec(
        function="smu_retention",
        display_name="SMU: Retention",
        systems=SMU_4200,
        plot_type="time_series",
        progress=True,
        description=(
            "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\n"
            "Pattern: Initial Read → Pulse → Read @ t1 → Read @ t2 → Read @ t3... (retention over time)\n"
            "Measures initial state, then how resistance changes over time after a single pulse\n"
            "Use for retention studies with slow pulses (milliseconds to seconds)\n"
            "Limits: Pulse widths 40ns to 480s (vs microseconds for PMU)\n"
            "When NOT to use: Fast pulses (< 1ms) - use PMU functions instead"
        ),
        params={
            "pulse_voltage": {"default": 2.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_duration": {"default": 0.1, "label": "Pulse Duration (s) ⚠️ SECONDS", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "read_duration": {"default": 0.01, "label": "Read Duration (s) ⚠️ SECONDS", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 1.0, "label": "Delay Between Reads (s) ⚠️ SECONDS", "type": "float"},
            "i_range": {"default": 0.01, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
    ),
    TestSpec(
        function="smu_retention_with_pulse_measurement",
        display_name="SMU: Retention (+ Pulse I)",
        systems=SMU_4200,
        plot_type="time_series",
        progress=True,
        description=(
            "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\n"
            "Pattern: (SET pulse+measure → Read → RESET pulse+measure → Read) × N cycles\n"
            "Measures resistance DURING SET/RESET pulses (not just after)\n"
            "Use for retention studies with slow pulses (milliseconds to seconds)\n"
            "Limits: Pulse widths 40ns to 480s (vs microseconds for PMU)\n"
            "When NOT to use: Fast pulses (< 1ms) - use PMU functions instead"
        ),
        params={
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "set_duration": {"default": 0.1, "label": "SET Duration (s) ⚠️ SECONDS", "type": "float"},
            "reset_duration": {"default": 0.1, "label": "RESET Duration (s) ⚠️ SECONDS", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "repeat_delay": {"default": 1.0, "label": "Repeat Delay (s) ⚠️ SECONDS", "type": "float"},
            "probe_voltage": {"default": 0.2, "label": "Probe Voltage (V)", "type": "float"},
            "probe_duration": {"default": 0.01, "label": "Probe Duration (s) ⚠️ SECONDS", "type": "float"},
            "i_range": {"default": 0.01, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
    ),
    TestSpec(
        function="optical_read_pulsed_light",
        display_name="Optical: Pulsed Read",
        systems=SMU_24XX | SMU_4200,
        plot_type="time_series",
        runner="optical",
        description="SMU at constant voltage; laser pulses periodically. Set current measurement range correctly or you will get few points at low currents and may miss the pulse.",
        params={
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "total_time_s": {"default": 10.0, "label": "Time to measure (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 0.001, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 0.0, "label": "Fire delay (s)", "type": "float", "section": "laser"},
            "optical_pulse_duration_s": {"default": 0.5, "label": "Optical pulse duration (s)", "type": "float", "section": "laser"},
            "optical_pulse_period_s": {"default": 1.0, "label": "Optical pulse period (s)", "type": "float", "section": "laser"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
    ),
    TestSpec(
        function="optical_pulse_train_read",
        display_name="Optical: Pulse Train + Read",
        systems=SMU_24XX | SMU_4200,
        plot_type="time_series",
        runner="optical",
        description="SMU at constant voltage; laser fires N pulses (on/off times). Set current measurement range correctly or you will get few points at low currents and may miss the pulse.",
        params={
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Time to measure (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 0.001, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 0.0, "label": "Fire delay (s)", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "n_optical_pulses": {"default": 5, "label": "Number of pulses", "type": "int", "section": "laser"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
    ),
    TestSpec(
        function="optical_pulse_train_pattern_read",
        display_name="Optical: Pattern + Read",
        systems=SMU_24XX | SMU_4200,
        plot_type="time_series",
        runner="optical",
        description="SMU at constant voltage; continuously reads while laser fires per pattern (1=fire, 0=skip). This is optical pulsing + continuous read. Set current measurement range correctly or you will get few points at low currents and may miss the pulse.",
        params={
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Time to measure (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 0.001, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_pattern": {"default": "1011", "label": "Pattern (1=fire, 0=skip)", "type": "str", "section": "laser"},
            "laser_delay_s": {"default": 0.0, "label": "Fire delay (s)", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "pattern_repeats": {"default": 1, "label": "Repeat pattern N times (e.g. 3 → 1011 wait 1011 wait 1011)", "type": "int", "section": "laser"},
            "time_between_patterns_s": {"default": 0.0, "label": "Time between pattern repeats (s) [0 = one period]", "type": "float", "section": "laser"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced – change only if needed]", "type": "float", "section": "advanced"},
        },
    ),
    TestSpec(
        function="optical_binary_sweep",
        display_name="Optical: Binary Sweep",
        systems=SMU_24XX | SMU_4200,
        plot_type="time_series",
        runner="optical_sweep",
        description=(
            "Iterates all 2^N binary laser patterns (0000 through 1111 for N=4).\n"
            "Each pattern runs as a separate measurement; results saved per-run as individual files\n"
            "(txt + png) inside a timestamped session folder, plus a combined wide CSV at the end.\n"
            "0000 runs as a dark/baseline measurement (laser never fires).\n"
            "SMU is turned off between runs for the configured inter-run delay."
        ),
        params={
            "num_bits": {"default": 4, "label": "Number of bits (N) — 2^N runs total", "type": "int", "section": "sweep"},
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Measurement duration per run (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 0.001, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 1.0, "label": "Pre-pulse baseline time (s) [SMU reads before first laser pulse]", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "delay_between_runs_s": {"default": 2.0, "label": "Delay between runs (s) [SMU off]", "type": "float", "section": "sweep"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
    ),
    TestSpec(
        function="optical_pattern_repeat",
        display_name="Optical: Pattern Repeat",
        systems=SMU_24XX | SMU_4200,
        plot_type="time_series",
        runner="optical_sweep",
        description=(
            "Runs one fixed binary laser pattern N times as separate measurement runs.\n"
            "Each repeat is saved as its own file (txt + png) inside a timestamped session folder,\n"
            "plus a combined wide CSV at the end.\n"
            "SMU is turned off between runs for the configured inter-run delay."
        ),
        params={
            "laser_pattern": {"default": "0101", "label": "Pattern (1=fire, 0=skip)", "type": "str", "section": "laser"},
            "n_repeats": {"default": 5, "label": "Number of repeats", "type": "int", "section": "sweep"},
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Measurement duration per run (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 0.001, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 1.0, "label": "Pre-pulse baseline time (s) [SMU reads before first laser pulse]", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "delay_between_runs_s": {"default": 2.0, "label": "Delay between runs (s) [SMU off]", "type": "float", "section": "sweep"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
    ),
    # --- Hidden: implemented on these systems but not in the dropdown yet. Give one a
    # display_name/params and drop hidden=True to expose it. ---
    TestSpec(function="pulse_then_read", systems=SMU_24XX, hidden=True,
             description="Pattern: (Pulse → Delay → Read) × N"),
    TestSpec(function="varying_width_pulses", systems=SMU_24XX, hidden=True,
             description="Test multiple pulse widths"),
    TestSpec(function="voltage_amplitude_sweep", systems=SMU_24XX | PMU_4200, hidden=True,
             plot_type="voltage_sweep",
             description="For each voltage: Initial Read → (Pulse → Read) × N → Reset"),
    TestSpec(function="ispp_test", systems=SMU_24XX | PMU_4200, hidden=True, plot_type="ispp",
             description="Incremental step pulse programming: increase voltage each pulse"),
    TestSpec(function="switching_threshold_test", systems=SMU_24XX | PMU_4200, hidden=True,
             plot_type="threshold",
             description="Try increasing voltages, find minimum that causes switching"),
    TestSpec(function="multilevel_programming", systems=SMU_24XX | PMU_4200, hidden=True,
             plot_type="multilevel",
             description="For each level: Reset → Program with pulses → Read"),
]

# The in-memory 2450 simulator (Equipment/SMU_AND_PMU/keithley2450/tsp_sim_scripts.py) has not
# ported these, so "2450 Sim" does not list them. Remove a name here once the simulator implements it.
SIM_2450_NOT_PORTED: FrozenSet[str] = frozenset({
    "multi_pulse_then_read", "pulse_multi_read", "relaxation_after_multi_pulse",
    "relaxation_after_multi_pulse_with_pulse_measurement", "width_sweep_with_reads",
    "width_sweep_with_all_measurements", "current_range_finder",
})
TESTS = [
    replace(t, systems=t.systems - {"keithley2450_sim"}) if t.function in SIM_2450_NOT_PORTED else t
    for t in TESTS
]


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def visible_tests() -> List[TestSpec]:
    return [t for t in TESTS if not t.hidden]


def all_functions() -> List[str]:
    """Unique function names in registry order."""
    seen: Dict[str, None] = {}
    for t in TESTS:
        seen.setdefault(t.function, None)
    return list(seen)


def systems_for_function(function: str) -> FrozenSet[str]:
    """Union of systems over every spec using ``function`` (e.g. both retention rows)."""
    out: FrozenSet[str] = frozenset()
    for t in TESTS:
        if t.function == function:
            out = out | t.systems
    return out


def get_spec(display_name: str) -> Optional[TestSpec]:
    for t in TESTS:
        if t.display_name == display_name:
            return t
    return None


def functions_with_runner(runner: str) -> FrozenSet[str]:
    return frozenset(t.function for t in TESTS if t.runner == runner)


def progress_functions() -> FrozenSet[str]:
    return frozenset(t.function for t in TESTS if t.progress)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
_REQUIRED_PARAM_KEYS = ("default", "label", "type")
_PARAM_TYPES = ("float", "int", "bool", "str", "list", "choice")


def instrument_params_for(spec: TestSpec, system: str, extra_pmu_params: Iterable[str] = ()) -> List[str]:
    """Parameter names the GUI sends to ``system`` for this test (mirrors the GUI filtering)."""
    is_pmu = system in PMU_4200
    names = []
    for name, info in spec.params.items():
        if info.get("gui_only"):
            continue
        if info.get("4200a_only") and not is_pmu:
            continue
        if is_pmu and name == "clim":
            continue
        names.append(name)
    if is_pmu:
        names.extend(n for n in extra_pmu_params if n not in names)
    return names


def validate_registry(
    system_classes: Optional[Mapping[str, type]] = None,
    plot_types: Optional[Iterable[str]] = None,
) -> List[str]:
    """Return a list of problems (empty = OK).

    Static checks always run. Pass ``system_classes`` (SystemWrapper.SYSTEM_CLASSES) to also check
    that every claimed system has a real (non-stub) method, and ``plot_types`` to check plot handlers.
    """
    import inspect

    errors: List[str] = []
    names = [t.display_name for t in TESTS if t.display_name]
    for n in sorted({n for n in names if names.count(n) > 1}):
        errors.append(f"duplicate display_name {n!r}")

    for t in TESTS:
        label = t.display_name or t.function
        if not t.hidden and not t.display_name:
            errors.append(f"{t.function}: visible test needs a display_name")
        unknown = t.systems - ALL_SYSTEMS
        if unknown:
            errors.append(f"{label}: unknown systems {sorted(unknown)}")
        if t.runner not in RUNNERS:
            errors.append(f"{label}: runner {t.runner!r} not in {RUNNERS}")
        if plot_types is not None and t.plot_type not in set(plot_types):
            errors.append(f"{label}: no plot handler for plot_type {t.plot_type!r}")
        for pname, info in t.params.items():
            missing = [k for k in _REQUIRED_PARAM_KEYS if k not in info]
            if missing:
                errors.append(f"{label}.{pname}: missing {missing}")
            if info.get("type") not in _PARAM_TYPES:
                errors.append(f"{label}.{pname}: bad type {info.get('type')!r}")
            if info.get("type") == "choice" and info.get("default") not in info.get("choices", []):
                errors.append(f"{label}.{pname}: default not in choices")

        if system_classes is None or t.runner != "system":
            continue
        for system in sorted(t.systems):
            cls = system_classes.get(system)
            if cls is None:
                continue  # e.g. keithley2450_sim is created by the GUI, not SystemWrapper
            method = getattr(cls, t.function, None)
            if method is None:
                errors.append(f"{label}: {system} has no method {t.function}()")
                continue
            try:
                src = inspect.getsource(method)
            except (OSError, TypeError):
                src = ""
            if "raise NotImplementedError" in src and len(src.splitlines()) < 15:
                errors.append(f"{label}: {system}.{t.function}() is a NotImplementedError stub")
    return errors
