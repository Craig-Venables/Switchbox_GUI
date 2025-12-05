import json
import os
from typing import Dict, Any

class ConfigManager:
    """
    Manages loading and saving of configuration settings for the Oscilloscope Pulse GUI.
    Persists settings to a JSON file in the same directory.
    """
    
    def __init__(self, config_file: str = "pulse_gui_config.json"):
        # Store in the same directory as this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(current_dir, config_file)
        self.default_config = {
            "pulse_voltage": 1.0,
            "pulse_duration": 0.001,
            "compliance": 0.1,
            "pre_pulse_delay": 0.1,
            "post_pulse_hold": 0.1,
            "scope_address": None,
            "scope_type": "Tektronix TBS1000C",
            "scope_channel": 1,
            "trigger_level": 0.5,
            "trigger_slope": "RISING",
            "timebase_scale": 0.0005,
            "volts_per_div": 0.5,
            "shunt_resistance": 50.0,
            "measurement_method": "Shunt Resistor",
            "simulation_mode": False
        }

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file, falling back to defaults."""
        if not os.path.exists(self.config_path):
            return self.default_config.copy()
            
        try:
            with open(self.config_path, 'r') as f:
                saved_config = json.load(f)
                # Merge with defaults to ensure all keys exist (handle upgrades)
                config = self.default_config.copy()
                config.update(saved_config)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config.copy()

    def save_config(self, config: Dict[str, Any]):
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
