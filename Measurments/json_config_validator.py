"""
JSON Configuration Validator for Automated Testing

This module validates sweep configuration parameters to ensure they are
compatible with the measurement system before execution.

Author: AI Assistant
Purpose: Unified JSON configuration system for automated testing
"""

from typing import Dict, Any, Tuple, List


def validate_sweep_config(params: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate sweep configuration parameters
    
    Args:
        params: Dictionary containing sweep parameters
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    # Handle backward compatibility: check old "mode" and "excitation" fields first
    measurement_type = "IV"  # default
    
    if "mode" in params:
        measurement_type = params["mode"]  # Endurance, Retention
    elif "excitation" in params:
        # Map old excitation names to measurement_type
        excitation_map = {
            "DC Triangle IV": "IV",
            "SMU Pulsed IV": "PulsedIV",
            "SMU Fast Pulses": "FastPulses",
            "SMU Fast Hold": "Hold"
        }
        measurement_type = excitation_map.get(params["excitation"], "IV")
    elif "measurement_type" in params:
        measurement_type = params["measurement_type"]
    
    valid_types = ["IV", "Endurance", "Retention", "PulsedIV", "FastPulses", "Hold"]
    
    if measurement_type not in valid_types:
        return False, f"Invalid measurement_type: {measurement_type}. Must be one of {valid_types}"
    
    # Type-specific validation
    if measurement_type == "IV":
        required = ["start_v", "stop_v"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for IV: {field}"
        
        # Validate voltage range
        try:
            start_v = float(params["start_v"])
            stop_v = float(params["stop_v"])
            # Check for reasonable range based on source mode
            source_mode = params.get("source_mode", "voltage")
            if source_mode == "current":
                # Current source mode - much smaller ranges (microamps)
                min_diff = 1e-9  # 1 nA
            else:
                # Voltage source mode - typical voltage ranges
                min_diff = 0.001  # 1 mV
            
            if abs(stop_v - start_v) < min_diff:
                return False, f"IV sweep: start_v and stop_v must differ by at least {min_diff}"
        except (ValueError, TypeError):
            return False, "IV sweep: start_v and stop_v must be numeric"
    
    elif measurement_type == "Endurance":
        required = ["set_v", "reset_v", "cycles"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for Endurance: {field}"
        
        # Validate endurance parameters
        try:
            set_v = float(params["set_v"])
            reset_v = float(params["reset_v"])
            cycles = int(params["cycles"])
            if cycles <= 0:
                return False, "Endurance: cycles must be positive integer"
            if abs(set_v - reset_v) < 0.001:
                return False, "Endurance: set_v and reset_v must differ by at least 0.001V"
        except (ValueError, TypeError):
            return False, "Endurance: set_v, reset_v must be numeric; cycles must be integer"
    
    elif measurement_type == "Retention":
        required = ["set_v", "read_v"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for Retention: {field}"
        
        # Validate retention parameters
        try:
            set_v = float(params["set_v"])
            read_v = float(params["read_v"])
            if abs(set_v - read_v) < 0.001:
                return False, "Retention: set_v and read_v must differ by at least 0.001V"
        except (ValueError, TypeError):
            return False, "Retention: set_v and read_v must be numeric"
    
    elif measurement_type == "PulsedIV":
        required = ["start_v", "stop_v", "pulse_ms"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for PulsedIV: {field}"
        
        try:
            pulse_ms = float(params["pulse_ms"])
            if pulse_ms <= 0:
                return False, "PulsedIV: pulse_ms must be positive"
        except (ValueError, TypeError):
            return False, "PulsedIV: pulse_ms must be numeric"
    
    elif measurement_type == "FastPulses":
        required = ["pulse_v", "num"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for FastPulses: {field}"
        
        try:
            num = int(params["num"])
            if num <= 0:
                return False, "FastPulses: num must be positive integer"
        except (ValueError, TypeError):
            return False, "FastPulses: num must be integer"
    
    elif measurement_type == "Hold":
        required = ["hold_v", "duration_s"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for Hold: {field}"
        
        try:
            duration_s = float(params["duration_s"])
            if duration_s <= 0:
                return False, "Hold: duration_s must be positive"
        except (ValueError, TypeError):
            return False, "Hold: duration_s must be numeric"
    
    # Validate optional parameters
    if "source_mode" in params:
        valid_source_modes = ["voltage", "current"]
        if params["source_mode"] not in valid_source_modes:
            return False, f"Invalid source_mode: {params['source_mode']}. Must be one of {valid_source_modes}"
    
    if "temperature_C" in params:
        try:
            temp = float(params["temperature_C"])
            if temp < -200 or temp > 500:
                return False, "temperature_C must be between -200 and 500"
        except (ValueError, TypeError):
            return False, "temperature_C must be numeric"
    
    if "LED_ON" in params:
        led_val = params["LED_ON"]
        if led_val not in [0, 1, "0", "1", False, True]:
            return False, "LED_ON must be 0, 1, False, or True"
    
    if "power" in params:
        try:
            power = float(params["power"])
            if power < 0:
                return False, "power must be non-negative"
        except (ValueError, TypeError):
            return False, "power must be numeric"
    
    return True, "Valid"


def validate_full_config(config: Dict[str, Any]) -> Tuple[bool, str, List[str]]:
    """
    Validate entire JSON configuration file
    
    Args:
        config: Full configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_message, warnings_list)
    """
    warnings = []
    
    if not isinstance(config, dict):
        return False, "Configuration must be a dictionary", []
    
    for test_name, test_config in config.items():
        if not isinstance(test_config, dict):
            return False, f"Test '{test_name}' configuration must be a dictionary", []
        
        if "sweeps" not in test_config:
            return False, f"Test '{test_name}' missing 'sweeps' section", []
        
        if not isinstance(test_config["sweeps"], dict):
            return False, f"Test '{test_name}' sweeps must be a dictionary", []
        
        # Validate each sweep
        for sweep_key, sweep_params in test_config["sweeps"].items():
            is_valid, error_msg = validate_sweep_config(sweep_params)
            if not is_valid:
                return False, f"Test '{test_name}', Sweep '{sweep_key}': {error_msg}", []
            
            # Check for deprecated fields
            if "mode" in sweep_params and "measurement_type" not in sweep_params:
                warnings.append(f"Test '{test_name}', Sweep '{sweep_key}': 'mode' field is deprecated, use 'measurement_type'")
            
            if "excitation" in sweep_params and "measurement_type" not in sweep_params:
                warnings.append(f"Test '{test_name}', Sweep '{sweep_key}': 'excitation' field is deprecated, use 'measurement_type'")
    
    return True, "Valid", warnings


if __name__ == "__main__":
    # Test the validator
    print("Testing JSON config validator...")
    
    # Test valid IV config
    valid_iv = {
        "measurement_type": "IV",
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.1,
        "source_mode": "voltage"
    }
    is_valid, msg = validate_sweep_config(valid_iv)
    print(f"Valid IV config: {is_valid}, {msg}")
    
    # Test invalid config
    invalid_config = {
        "measurement_type": "InvalidType",
        "start_v": 0
    }
    is_valid, msg = validate_sweep_config(invalid_config)
    print(f"Invalid config: {is_valid}, {msg}")
    
    # Test full config
    full_config = {
        "Test1": {
            "sweeps": {
                "1": valid_iv
            }
        }
    }
    is_valid, msg, warnings = validate_full_config(full_config)
    print(f"Full config: {is_valid}, {msg}, warnings: {warnings}")
    
    print("Validator tests complete!")
