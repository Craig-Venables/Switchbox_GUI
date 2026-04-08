"""
Test Definitions - GUI metadata for pulse tests
================================================

Single source of truth for display names, parameters, descriptions, and plot types.
Which tests are *supported* per system is in test_capabilities.py; this module
only defines what each test looks like in the GUI.

Use get_test_definitions_for_gui(system_name) to get definitions filtered by
current system so only available tests appear.
"""

from typing import Dict, List, Any, Optional

# Optional: import for filtering by system (avoids circular import by lazy use)
def _get_supported_tests(system_name: str) -> List[str]:
    from .test_capabilities import get_supported_tests
    return get_supported_tests(system_name)


# Display name -> { function, description, params, plot_type, optional only_for_systems }
TEST_FUNCTIONS: Dict[str, Dict[str, Any]] = {
    "Pulse-Read-Repeat": {
        "function": "pulse_read_repeat",
        "description": "Pattern: Initial Read → (Pulse → Read → Delay) × N\nBasic pulse response with immediate read after each pulse",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_delay": {"default": 1.0, "label": "Read Delay (µs) [4200A only]", "type": "float", "4200a_only": True},
            "read_rise_time": {"default": 0.1, "label": "Read Rise Time (µs) [4200A only]", "type": "float", "4200a_only": True},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
        "plot_type": "time_series",
    },
    "Laser and Read": {
        "function": "laser_and_read",
        "description": "⚠️ IMPORTANT: You MUST reconfigure coax cables before running this test!\nPattern: CH1 continuous reads, CH2 independent laser pulse\nPhoto-induced effects, laser-assisted switching, time-resolved photoconductivity",
        "params": {
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
            "current_measure_rng": {"default": 0.00001, "label": "Current Range (A) [0=auto]", "type": "float"},
            "sample_rate": {"default": 200e6, "label": "Sample Rate (Sa/s)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Multi-Pulse-Then-Read": {
        "function": "multi_pulse_then_read",
        "description": "Pattern: Initial Read → (Pulse×N → Read×M) × Cycles\nMultiple pulses then multiple reads per cycle",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses_per_read": {"default": 10, "label": "Pulses Per Cycle", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 1, "label": "Reads Per Cycle", "type": "int"},
            "delay_between_reads": {"default": 10.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "num_cycles": {"default": 20, "label": "Number of Cycles", "type": "int"},
            "delay_between_cycles": {"default": 10.0, "label": "Delay Between Cycles (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
        "plot_type": "time_series",
    },
    "Width Sweep": {
        "function": "width_sweep_with_reads",
        "description": "Pattern: Initial Read, (Pulse→Read)×N, Reset (per width)\nFind optimal pulse timing, measure speed dependence",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3,50e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1e-3, "label": "Reset Width (s)", "type": "float"},
            "delay_between_widths": {"default": 5.0, "label": "Relaxation Delay Between Width Blocks (s)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "width_vs_resistance",
    },
    "Width Sweep (Full)": {
        "function": "width_sweep_with_all_measurements",
        "description": "Pattern: Initial Read, (Pulse(measured)→Read)×N, Reset (per width)\nFull characterization including pulse peak currents",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1e-3, "label": "Reset Width (s)", "type": "float"},
            "delay_between_widths": {"default": 5.0, "label": "Relaxation Delay Between Width Blocks (s)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "width_vs_resistance",
    },
    "Potentiation-Depression Cycle": {
        "function": "potentiation_depression_cycle",
        "description": "Pattern: Initial Read → (Gradual SET → Gradual RESET) × N cycles\nSynaptic weight update, neuromorphic applications",
        "params": {
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
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "pot_dep_cycle",
    },
    "Potentiation Only": {
        "function": "potentiation_only",
        "description": "Pattern: Initial Read → Repeated SET pulses with reads\nOptional post-pulse reads to observe relaxation",
        "params": {
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
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
        "plot_type": "time_series",
    },
    "Depression Only": {
        "function": "depression_only",
        "description": "Pattern: Initial Read → Repeated RESET pulses with reads\nOptional post-pulse reads to observe relaxation",
        "params": {
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
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output (Print data after each pulse) [4200A only]", "type": "bool", "4200a_only": True},
        },
        "plot_type": "time_series",
    },
    "Endurance Test": {
        "function": "endurance_test",
        "description": "Pattern: Initial Read → (SET → Read → RESET → Read) × N\nDevice lifetime, cycling endurance monitoring",
        "params": {
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_cycles": {"default": 100, "label": "Number of Cycles", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "endurance",
    },
    "Pulse-Multi-Read": {
        "function": "pulse_multi_read",
        "description": "Pattern: Initial Read → (Pulse × M) → Read × N\nMonitor state relaxation/drift after pulses",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "num_pulses": {"default": 1, "label": "Number of Pulses", "type": "int"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 50, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 100.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Multi-Read Only": {
        "function": "multi_read_only",
        "description": "Pattern: Just reads, no pulses\nBaseline noise, read disturb characterization",
        "params": {
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 100, "label": "Number of Reads", "type": "int"},
            "delay_between": {"default": 100.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Current Range Finder": {
        "function": "current_range_finder",
        "description": "Find optimal current measurement range\nTests multiple ranges and recommends best for your device",
        "params": {
            "test_voltage": {"default": 0.2, "label": "Test Voltage (V)", "type": "float"},
            "num_reads_per_range": {"default": 10, "label": "Reads Per Range", "type": "int"},
            "delay_between_reads": {"default": 10.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "current_ranges": {"default": "0.001,0.0001,0.00001,0.000001", "label": "Ranges to Test (comma-separated, A)", "type": "list"},
        },
        "plot_type": "range_finder",
    },
    "Relaxation After Multi-Pulse": {
        "function": "relaxation_after_multi_pulse",
        "description": "Pattern: 1×Read → N×Pulse → N×Read\nFind how device relaxes after cumulative pulsing",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses": {"default": 10, "label": "Number of Pulses", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 0.1, "label": "Delay Between Reads (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "relaxation_reads",
    },
    "Relaxation After Multi-Pulse With Pulse Measurement": {
        "function": "relaxation_after_multi_pulse_with_pulse_measurement",
        "description": "Pattern: 1×Read → N×Pulse(measured) → N×Read\nFull relaxation with pulse peak currents",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses": {"default": 10, "label": "Number of Pulses", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 0.1, "label": "Delay Between Reads (ms)", "type": "float"},
            "read_width": {"default": 0.5, "label": "Read Width (µs) [4200A only]", "type": "float", "4200a_only": True},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "relaxation_all",
    },
    "⚠️ SMU Slow Pulse Measure": {
        "function": "smu_slow_pulse_measure",
        "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: Single pulse → Measure resistance during pulse\nUse for very slow pulses (milliseconds to seconds), relaxation studies\nLimits: Pulse width 40ns to 480s (vs microseconds for PMU)\nWhen NOT to use: Fast pulses (< 1ms) - use PMU functions instead",
        "params": {
            "pulse_voltage": {"default": 1.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 0.1, "label": "Pulse Width (s) ⚠️ SECONDS (not ms/µs)", "type": "float"},
            "i_range": {"default": 10e-3, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
        "plot_type": "time_series",
        "only_for_systems": ["keithley4200_smu"],
    },
    "⚠️ SMU Endurance": {
        "function": "smu_endurance",
        "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: (SET pulse → Read → RESET pulse → Read) × N cycles\nUse for endurance cycling with slow pulses (milliseconds to seconds)\nLimits: Pulse widths 40ns to 480s (vs microseconds for PMU)\nWhen NOT to use: Fast pulses (< 1ms) - use PMU functions instead",
        "params": {
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "set_duration": {"default": 0.1, "label": "SET Duration (s) ⚠️ SECONDS", "type": "float"},
            "reset_duration": {"default": 0.1, "label": "RESET Duration (s) ⚠️ SECONDS", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "repeat_delay": {"default": 1.0, "label": "Repeat Delay (s) ⚠️ SECONDS", "type": "float"},
            "probe_voltage": {"default": 0.2, "label": "Probe Voltage (V)", "type": "float"},
            "probe_duration": {"default": 0.01, "label": "Probe Duration (s) ⚠️ SECONDS", "type": "float"},
            "i_range": {"default": 10e-3, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
        "plot_type": "time_series",
        "only_for_systems": ["keithley4200_smu"],
    },
    "⚠️ SMU Retention": {
        "function": "smu_retention",
        "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: Initial Read → Pulse → Read @ t1 → Read @ t2 → Read @ t3... (retention over time)\nMeasures initial state, then how resistance changes over time after a single pulse\nUse for retention studies with slow pulses (milliseconds to seconds)\nLimits: Pulse widths 40ns to 480s (vs microseconds for PMU)\nWhen NOT to use: Fast pulses (< 1ms) - use PMU functions instead",
        "params": {
            "pulse_voltage": {"default": 2.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_duration": {"default": 0.1, "label": "Pulse Duration (s) ⚠️ SECONDS", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "read_duration": {"default": 0.01, "label": "Read Duration (s) ⚠️ SECONDS", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 1.0, "label": "Delay Between Reads (s) ⚠️ SECONDS", "type": "float"},
            "i_range": {"default": 10e-3, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
        "plot_type": "time_series",
        "only_for_systems": ["keithley4200_smu"],
    },
    "⚠️ SMU Retention (Pulse Measured)": {
        "function": "smu_retention_with_pulse_measurement",
        "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: (SET pulse+measure → Read → RESET pulse+measure → Read) × N cycles\nMeasures resistance DURING SET/RESET pulses (not just after)\nUse for retention studies with slow pulses (milliseconds to seconds)\nLimits: Pulse widths 40ns to 480s (vs microseconds for PMU)\nWhen NOT to use: Fast pulses (< 1ms) - use PMU functions instead",
        "params": {
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "set_duration": {"default": 0.1, "label": "SET Duration (s) ⚠️ SECONDS", "type": "float"},
            "reset_duration": {"default": 0.1, "label": "RESET Duration (s) ⚠️ SECONDS", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "repeat_delay": {"default": 1.0, "label": "Repeat Delay (s) ⚠️ SECONDS", "type": "float"},
            "probe_voltage": {"default": 0.2, "label": "Probe Voltage (V)", "type": "float"},
            "probe_duration": {"default": 0.01, "label": "Probe Duration (s) ⚠️ SECONDS", "type": "float"},
            "i_range": {"default": 10e-3, "label": "Current Range (A) [0=auto]", "type": "float"},
            "i_compliance": {"default": 0.0, "label": "Current Compliance (A, 0=disabled)", "type": "float"},
            "initialize": {"default": True, "label": "Initialize SMU", "type": "bool"},
            "log_messages": {"default": True, "label": "Log Messages", "type": "bool"},
            "enable_debug_output": {"default": True, "label": "Enable Debug Output", "type": "bool"},
        },
        "plot_type": "time_series",
        "only_for_systems": ["keithley4200_smu"],
    },
    "⚡ Electrical Pulse Train (Memristor Programming)": {
        "function": "pulse_train_varying_amplitudes",
        "description": "⚡ SMU ELECTRICAL SET/RESET pulses (NO laser, NO continuous read): Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N\nSends electrical voltage pulses for memristor programming. Pattern: 1=send pulse voltage, 0=skip (0V).\n\n🚫 For OPTICAL tests with laser + continuous SMU read, use 'Optical Pulse Train with Pattern + Read' below.",
        "params": {
            "num_pulses": {"default": 5, "label": "Number of pulses (slots)", "type": "int"},
            "pulse_pattern": {"default": "11111", "label": "Pattern (1=on, 0=off, e.g. 11010)", "type": "str"},
            "pulse_voltage": {"default": 1.5, "label": "Pulse voltage when on (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_repeats": {"default": 1, "label": "Number of Repeats", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "pulse_train",
    },
    "🔦 Optical Read (Pulsed Light)": {
        "function": "optical_read_pulsed_light",
        "description": "SMU at constant voltage; laser pulses periodically. Set current measurement range correctly or you will get few points at low currents and may miss the pulse.",
        "params": {
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "total_time_s": {"default": 10.0, "label": "Time to measure (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 1e-3, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 0.0, "label": "Fire delay (s)", "type": "float", "section": "laser"},
            "optical_pulse_duration_s": {"default": 0.5, "label": "Optical pulse duration (s)", "type": "float", "section": "laser"},
            "optical_pulse_period_s": {"default": 1.0, "label": "Optical pulse period (s)", "type": "float", "section": "laser"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
        "plot_type": "time_series",
    },
    "🔦 Optical Pulse Train + Read": {
        "function": "optical_pulse_train_read",
        "description": "SMU at constant voltage; laser fires N pulses (on/off times). Set current measurement range correctly or you will get few points at low currents and may miss the pulse.",
        "params": {
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Time to measure (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 1e-3, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 0.0, "label": "Fire delay (s)", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "n_optical_pulses": {"default": 5, "label": "Number of pulses", "type": "int", "section": "laser"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
        "plot_type": "time_series",
    },
    "🔦 Continuous Read with Laser Pulse Pattern": {
        "function": "optical_pulse_train_pattern_read",
        "description": "SMU at constant voltage; continuously reads while laser fires per pattern (1=fire, 0=skip). This is optical pulsing + continuous read. Set current measurement range correctly or you will get few points at low currents and may miss the pulse.",
        "params": {
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Time to measure (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 1e-3, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_pattern": {"default": "1011", "label": "Pattern (1=fire, 0=skip)", "type": "str", "section": "laser"},
            "laser_delay_s": {"default": 0.0, "label": "Fire delay (s)", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "pattern_repeats": {"default": 1, "label": "Repeat pattern N times (e.g. 3 → 1011 wait 1011 wait 1011)", "type": "int", "section": "laser"},
            "time_between_patterns_s": {"default": 0.0, "label": "Time between pattern repeats (s) [0 = one period]", "type": "float", "section": "laser"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced – change only if needed]", "type": "float", "section": "advanced"},
        },
        "plot_type": "time_series",
    },
    "🔦 Binary Pattern Sweep": {
        "function": "optical_binary_sweep",
        "description": (
            "Iterates all 2^N binary laser patterns (0000 through 1111 for N=4).\n"
            "Each pattern runs as a separate measurement; results saved per-run as individual files\n"
            "(txt + png) inside a timestamped session folder, plus a combined wide CSV at the end.\n"
            "0000 runs as a dark/baseline measurement (laser never fires).\n"
            "SMU is turned off between runs for the configured inter-run delay."
        ),
        "params": {
            "num_bits": {"default": 4, "label": "Number of bits (N) — 2^N runs total", "type": "int", "section": "sweep"},
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Measurement duration per run (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 1e-3, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 1.0, "label": "Pre-pulse baseline time (s) [SMU reads before first laser pulse]", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "delay_between_runs_s": {"default": 2.0, "label": "Delay between runs (s) [SMU off]", "type": "float", "section": "sweep"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
        "plot_type": "time_series",
    },
    "🔦 Pattern Repeat": {
        "function": "optical_pattern_repeat",
        "description": (
            "Runs one fixed binary laser pattern N times as separate measurement runs.\n"
            "Each repeat is saved as its own file (txt + png) inside a timestamped session folder,\n"
            "plus a combined wide CSV at the end.\n"
            "SMU is turned off between runs for the configured inter-run delay."
        ),
        "params": {
            "laser_pattern": {"default": "0101", "label": "Pattern (1=fire, 0=skip)", "type": "str", "section": "laser"},
            "n_repeats": {"default": 5, "label": "Number of repeats", "type": "int", "section": "sweep"},
            "read_voltage": {"default": 0.5, "label": "Voltage (V)", "type": "float", "section": "read"},
            "duration_s": {"default": 5.0, "label": "Measurement duration per run (s)", "type": "float", "section": "read"},
            "sample_interval_s": {"default": 0.02, "label": "Sample interval (s)", "type": "float", "section": "read"},
            "current_range_a": {"default": 0.0, "label": "Current Range (A) [0=auto]", "type": "float", "section": "read"},
            "clim": {"default": 1e-3, "label": "Current limit (A)", "type": "float", "section": "read"},
            "optical_laser_power_mw": {"default": 1.0, "label": "Laser power (mW)", "type": "float", "section": "laser"},
            "laser_delay_s": {"default": 1.0, "label": "Pre-pulse baseline time (s) [SMU reads before first laser pulse]", "type": "float", "section": "laser"},
            "optical_on_ms": {"default": 500.0, "label": "Optical on (ms)", "type": "float", "section": "laser"},
            "optical_off_ms": {"default": 500.0, "label": "Optical off (ms)", "type": "float", "section": "laser"},
            "delay_between_runs_s": {"default": 2.0, "label": "Delay between runs (s) [SMU off]", "type": "float", "section": "sweep"},
            "measurement_init_time_s": {"default": 1.0, "label": "Calibration/init time (s) [advanced]", "type": "float", "section": "advanced"},
        },
        "plot_type": "time_series",
    },
}


def get_test_definitions_for_gui(
    system_name: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Return test definitions for the GUI, optionally filtered by current system.

    If system_name is given, only tests that are supported for that system
    (and pass only_for_systems if set) are included. If system_name is None,
    all defined tests are returned (e.g. before any system is connected).

    Args:
        system_name: Current system (e.g. 'keithley2450', 'keithley4200_pmu', 'keithley4200_smu', 'keithley2400')
                    or None to return all definitions.

    Returns:
        Dict mapping display name -> { function, description, params, plot_type, ... }
    """
    if system_name is None:
        return dict(TEST_FUNCTIONS)

    supported = set(_get_supported_tests(system_name))
    out = {}
    for display_name, defn in TEST_FUNCTIONS.items():
        func_key = defn.get("function")
        if func_key not in supported:
            continue
        only_for = defn.get("only_for_systems")
        if only_for is not None and system_name not in only_for:
            continue
        out[display_name] = defn
    return out


def get_display_name_for_function(function_key: str) -> Optional[str]:
    """Return the display name for a test function key, or None if not found."""
    for display_name, defn in TEST_FUNCTIONS.items():
        if defn.get("function") == function_key:
            return display_name
    return None
