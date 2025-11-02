"""
Data Format Utilities
=====================

Functions for validating and normalizing measurement data to ensure
consistent format across all measurement systems.
"""

from typing import Dict, List, Any, Optional
import numpy as np


REQUIRED_FIELDS = ['timestamps', 'voltages', 'currents', 'resistances']


def validate_data_format(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate that data dictionary has required fields and correct types.
    
    Args:
        data: Data dictionary to validate
    
    Returns:
        Tuple of (is_valid, error_message)
        If valid, returns (True, None)
        If invalid, returns (False, error_message_string)
    """
    # Check all required fields exist
    for field in REQUIRED_FIELDS:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Check all required fields are lists
    for field in REQUIRED_FIELDS:
        if not isinstance(data[field], list):
            return False, f"Field '{field}' must be a list, got {type(data[field])}"
    
    # Check all lists have same length
    lengths = [len(data[field]) for field in REQUIRED_FIELDS]
    if len(set(lengths)) > 1:
        return False, f"Field lengths don't match: {dict(zip(REQUIRED_FIELDS, lengths))}"
    
    # Check all values are numeric
    for field in REQUIRED_FIELDS:
        for idx, value in enumerate(data[field]):
            try:
                float(value)
            except (ValueError, TypeError):
                return False, f"Non-numeric value in '{field}' at index {idx}: {value}"
    
    return True, None


def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize data to ensure consistent format.
    
    Converts all numeric lists to numpy arrays for consistency,
    ensures resistances are calculated if missing, and validates format.
    
    Args:
        data: Input data dictionary
    
    Returns:
        Normalized data dictionary with numpy arrays
    
    Raises:
        ValueError: If data format is invalid
    """
    # Validate format first
    is_valid, error_msg = validate_data_format(data)
    if not is_valid:
        raise ValueError(f"Invalid data format: {error_msg}")
    
    # Create normalized copy
    normalized = {}
    
    # Convert required fields to numpy arrays
    for field in REQUIRED_FIELDS:
        normalized[field] = np.array(data[field], dtype=float)
    
    # Recalculate resistances if needed (handle division by zero)
    voltages = normalized['voltages']
    currents = normalized['currents']
    
    # Calculate resistances: R = V/I, handle division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        resistances = np.where(
            np.abs(currents) > 1e-12,
            voltages / currents,
            1e12  # Large resistance for open circuit / zero current
        )
    
    normalized['resistances'] = resistances
    
    # Copy any extra fields (phase, pulse_widths, etc.)
    for key, value in data.items():
        if key not in REQUIRED_FIELDS:
            normalized[key] = value
    
    return normalized


def ensure_list_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert numpy arrays back to lists for JSON serialization.
    
    Some systems may return numpy arrays, but GUI expects lists.
    
    Args:
        data: Data dictionary (may contain numpy arrays)
    
    Returns:
        Data dictionary with all arrays converted to lists
    """
    converted = {}
    for key, value in data.items():
        if isinstance(value, np.ndarray):
            converted[key] = value.tolist()
        elif isinstance(value, (list, tuple)):
            converted[key] = list(value)
        else:
            converted[key] = value
    
    return converted

