"""
Test Type Registry

Manages known test types and their plotting characteristics.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TestTypeInfo:
    """Information about a test type"""
    name: str
    description: str
    plot_type: str  # 'time_series', 'width_vs_resistance', 'pot_dep_cycle', etc.
    expected_columns: List[str]
    key_parameters: List[str]


class TestTypeRegistry:
    """Registry of known test types"""
    
    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = registry_file or Path(__file__).parent.parent / "resources" / "test_types.json"
        self.test_types: Dict[str, TestTypeInfo] = {}
        self.load_registry()
    
    def load_registry(self):
        """Load test types from JSON file"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for name, info in data.items():
                    self.test_types[name] = TestTypeInfo(
                        name=name,
                        description=info.get('description', ''),
                        plot_type=info.get('plot_type', 'time_series'),
                        expected_columns=info.get('expected_columns', []),
                        key_parameters=info.get('key_parameters', [])
                    )
            except Exception as e:
                print(f"Error loading test type registry: {e}")
                self._create_default_registry()
        else:
            self._create_default_registry()
    
    def _create_default_registry(self):
        """Create default registry with known test types"""
        default_types = {
            "Pulse-Read-Repeat": {
                "description": "Pattern: Initial Read → (Pulse → Read → Delay) × N",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "pulse_width", "read_voltage", "num_cycles"]
            },
            "Multi-Pulse-Then-Read": {
                "description": "Pattern: Initial Read → (Pulse×N → Read×M) × Cycles",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "num_pulses_per_read", "pulse_width", "num_cycles"]
            },
            "Width Sweep": {
                "description": "Pattern: Initial Read, (Pulse→Read)×N, Reset (per width)",
                "plot_type": "width_vs_resistance",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)", "Pulse Widths"],
                "key_parameters": ["pulse_voltage", "pulse_widths", "read_voltage", "num_pulses_per_width"]
            },
            "Width Sweep (Full)": {
                "description": "Pattern: Initial Read, (Pulse(measured)→Read)×N, Reset (per width)",
                "plot_type": "width_vs_resistance",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)", "Pulse Widths"],
                "key_parameters": ["pulse_voltage", "pulse_widths", "read_voltage", "num_pulses_per_width"]
            },
            "Potentiation-Depression Cycle": {
                "description": "Pattern: Initial Read → Gradual SET (LRS) → Gradual RESET (HRS)",
                "plot_type": "pot_dep_cycle",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)", "Phase"],
                "key_parameters": ["set_voltage", "reset_voltage", "pulse_width", "steps"]
            },
            "Potentiation Only": {
                "description": "Pattern: Initial Read → Repeated SET pulses with reads",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["set_voltage", "pulse_width", "read_voltage", "num_pulses"]
            },
            "Depression Only": {
                "description": "Pattern: Initial Read → Repeated RESET pulses with reads",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["reset_voltage", "pulse_width", "read_voltage", "num_pulses"]
            },
            "Endurance Test": {
                "description": "Pattern: Initial Read → (SET → Read → RESET → Read) × N",
                "plot_type": "endurance",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)", "Cycle Number"],
                "key_parameters": ["set_voltage", "reset_voltage", "pulse_width", "num_cycles"]
            },
            "Pulse-Multi-Read": {
                "description": "Pattern: Initial Read → (Pulse × M) → Read × N",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "pulse_width", "num_pulses", "read_voltage", "num_reads"]
            },
            "Multi-Read Only": {
                "description": "Pattern: Just reads, no pulses",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["read_voltage", "num_reads"]
            },
            "Relaxation After Multi-Pulse": {
                "description": "Pattern: 1×Read → N×Pulse → N×Read",
                "plot_type": "relaxation_reads",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "num_pulses", "read_voltage", "num_reads"]
            },
            "Relaxation After Multi-Pulse With Pulse Measurement": {
                "description": "Pattern: 1×Read → N×Pulse(measured) → N×Read",
                "plot_type": "relaxation_all",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "num_pulses", "read_voltage", "num_reads"]
            },
            "Current Range Finder": {
                "description": "Find optimal current measurement range",
                "plot_type": "range_finder",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["test_voltage", "num_reads_per_range", "current_ranges"]
            },
            "IV Sweep (Hysteresis)": {
                "description": "Voltage-Current hysteresis loop",
                "plot_type": "iv_sweep",
                "expected_columns": ["Voltage", "Current", "Time"],
                "key_parameters": ["voltage", "sweep_rate"]
            },
            "PMU Pulse-Read": {
                "description": "Pulse measurement with reads",
                "plot_type": "time_series",
                "expected_columns": ["Time", "Voltage", "Current", "Resistance"],
                "key_parameters": ["set_voltage", "read_voltage"]
            },
            "Laser and Read": {
                "description": "Pattern: CH1 continuous reads, CH2 independent laser pulse\nPhoto-induced effects, laser-assisted switching, time-resolved photoconductivity",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["read_voltage", "read_width", "laser_voltage_high", "laser_width", "num_reads"]
            },
            "⚠️ SMU Slow Pulse Measure": {
                "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: Single pulse → Measure resistance during pulse\nUse for very slow pulses (milliseconds to seconds), relaxation studies",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "pulse_width", "i_range"]
            },
            "⚠️ SMU Endurance": {
                "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: (SET pulse → Read → RESET pulse → Read) × N cycles\nUse for endurance cycling with slow pulses (milliseconds to seconds)",
                "plot_type": "endurance",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)", "Cycle Number"],
                "key_parameters": ["set_voltage", "reset_voltage", "set_duration", "reset_duration", "num_cycles"]
            },
            "⚠️ SMU Retention": {
                "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: Initial Read → Pulse → Read @ t1 → Read @ t2 → Read @ t3... (retention over time)\nMeasures initial state, then how resistance changes over time after a single pulse",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["pulse_voltage", "pulse_duration", "read_voltage", "num_reads", "delay_between_reads"]
            },
            "⚠️ SMU Retention (Pulse Measured)": {
                "description": "⚠️ IMPORTANT: Uses SMU (not PMU) - Much slower but supports longer pulses\nPattern: (SET pulse+measure → Read → RESET pulse+measure → Read) × N cycles\nMeasures resistance DURING SET/RESET pulses (not just after)",
                "plot_type": "time_series",
                "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
                "key_parameters": ["set_voltage", "reset_voltage", "set_duration", "reset_duration", "num_cycles"]
            }
        }
        
        # Convert to TestTypeInfo objects
        for name, info in default_types.items():
            self.test_types[name] = TestTypeInfo(
                name=name,
                description=info['description'],
                plot_type=info['plot_type'],
                expected_columns=info['expected_columns'],
                key_parameters=info['key_parameters']
            )
        
        # Save to file
        self.save_registry()
    
    def save_registry(self):
        """Save test types to JSON file"""
        try:
            # Ensure directory exists
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict
            data = {}
            for name, info in self.test_types.items():
                data[name] = {
                    'description': info.description,
                    'plot_type': info.plot_type,
                    'expected_columns': info.expected_columns,
                    'key_parameters': info.key_parameters
                }
            
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving test type registry: {e}")
    
    def get_test_type(self, name: str) -> Optional[TestTypeInfo]:
        """Get test type info by name (case-insensitive)"""
        for key, info in self.test_types.items():
            if key.lower() == name.lower():
                return info
        return None
    
    def get_all_test_types(self) -> List[str]:
        """Get list of all known test type names"""
        return list(self.test_types.keys())
    
    def get_plot_type(self, test_name: str) -> str:
        """Get plot type for a test name"""
        info = self.get_test_type(test_name)
        return info.plot_type if info else 'time_series'


# Global registry instance
_registry = None

def get_registry() -> TestTypeRegistry:
    """Get the global test type registry instance"""
    global _registry
    if _registry is None:
        _registry = TestTypeRegistry()
    return _registry


# Module test
if __name__ == "__main__":
    print("Test Type Registry - Module Test")
    print("=" * 60)
    
    registry = get_registry()
    
    print(f"\nLoaded {len(registry.test_types)} test types:")
    for name in registry.get_all_test_types():
        info = registry.get_test_type(name)
        print(f"\n  • {name}")
        print(f"    Plot type: {info.plot_type}")
        print(f"    Description: {info.description}")
    
    print(f"\n✓ Registry file: {registry.registry_file}")

