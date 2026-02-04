from __future__ import annotations


class VoltageRangeMode:
    FIXED_STEP = "fixed_step"  # Default: use explicit step size
    FIXED_SWEEP_RATE = "fixed_sweep_rate"  # Placeholder for future
    FIXED_VOLTAGE_TIME = "fixed_voltage_time"  # Placeholder for future


class SMULimits:
    """Configuration for different SMU types and their timing limits."""

    def __init__(self) -> None:
        self.limits = {
            "Keithley 2400": {
                "min_timing_us": 200,
                "max_update_rate": 2000,
                "rise_fall_time_us": 50,
                "min_pulse_width_ms": 1.0,
                "voltage_range_V": (-200, 200),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-6,
                "defaults": {
                    "read_v": 0.2,
                    "vbase": 0.2,
                    "pulse_ms": 1.0,
                    "triangle": {
                        "vmin": 0.0,
                        "vmax": 1.0,
                        "step": 0.05,
                        "delay_s": 0.05,
                    },
                },
            },
            "Keithley 2401": {
                "min_timing_us": 250,
                "max_update_rate": 2000,
                "rise_fall_time_us": 30,
                "min_pulse_width_ms": 1.0,
                "voltage_range_V": (-20, 20),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-6,
                "defaults": {
                    "read_v": 0.2,
                    "vbase": 0.2,
                    "pulse_ms": 1.0,
                    "triangle": {
                        "vmin": 0.0,
                        "vmax": 1.0,
                        "step": 0.05,
                        "delay_s": 0.05,
                    },
                },
            },
            "Keithley 4200A_smu": {
                "min_timing_us": 100,
                "max_update_rate": 5000,
                "rise_fall_time_us": 20,
                "min_pulse_width_ms": 0.5,
                "voltage_range_V": (-210, 210),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-9,
                "defaults": {
                    "read_v": 0.2,
                    "vbase": 0.2,
                    "pulse_ms": 0.5,
                    "triangle": {
                        "vmin": 0.0,
                        "vmax": 1.0,
                        "step": 0.05,
                        "delay_s": 0.02,
                    },
                },
            },
            "Keithley 4200A_pmu": {
                "min_timing_us": 10,
                "max_update_rate": 10000,
                "rise_fall_time_us": 0.01,
                "min_pulse_width_ms": 0.00005,  # 50 µs
                "voltage_range_V": (-10, 10),
                "current_range_A": (-0.1, 0.1),  # ±100 mA
                "compliance_resolution": 1e-6,
                "bandwidth_MHz": 5,
            },
            "HP4140B": {
                "min_timing_ms": 5,
                "max_update_rate": 20,
                "voltage_range_V": (-100, 100),
                "current_range_A": (1e-14, 1e-2),
                "pulse_capability": None,
                "integration_modes": ["short", "medium", "long"],
            },
        }

    def get_limits(self, smu_type: str) -> dict:
        """Get timing limits for the specified SMU type."""
        return self.limits.get(smu_type, self.limits["Keithley 2401"])

    def update_limits(self, smu_type: str, **kwargs) -> None:
        """Update timing limits for a specific SMU type."""
        if smu_type not in self.limits:
            self.limits[smu_type] = {}
        self.limits[smu_type].update(kwargs)

    def get_defaults(self, smu_type: str) -> dict:
        """Return sensible per-model defaults (read_v, vbase, pulse_ms, triangle)."""
        lim = self.get_limits(smu_type)
        return lim.get("defaults", self.limits["Keithley 2401"].get("defaults", {}))


__all__ = ["SMULimits", "VoltageRangeMode"]
