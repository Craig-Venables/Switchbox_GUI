"""
TSP Data File Parser

Parses TSP measurement files according to the format specification.
Extracts metadata, column headers, and data arrays.
"""

from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import re


class TSPData:
    """Container for parsed TSP measurement data"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.filename = filepath.name
        
        # Metadata
        self.test_name: str = ""
        self.timestamp: str = ""
        self.sample: str = ""
        self.device: str = ""
        self.instrument: str = ""
        self.address: str = ""
        self.parameters: Dict[str, str] = {}
        self.hardware_limits: Dict[str, str] = {}
        self.data_points: int = 0
        self.duration: float = 0.0
        self.notes: str = ""
        
        # Data
        self.headers: List[str] = []
        self.data: np.ndarray = np.array([])
        
        # Convenience accessors for standard columns
        self.measurement_numbers: np.ndarray = np.array([])
        self.timestamps: np.ndarray = np.array([])
        self.voltages: np.ndarray = np.array([])
        self.currents: np.ndarray = np.array([])
        self.resistances: np.ndarray = np.array([])
        
        # Additional columns (varies by test type)
        self.additional_data: Dict[str, np.ndarray] = {}
    
    def get_column(self, name: str) -> Optional[np.ndarray]:
        """Get data column by name"""
        # Check standard columns first
        if 'measurement' in name.lower() and 'number' in name.lower():
            return self.measurement_numbers
        elif 'timestamp' in name.lower():
            return self.timestamps
        elif 'voltage' in name.lower():
            return self.voltages
        elif 'current' in name.lower():
            return self.currents
        elif 'resistance' in name.lower():
            return self.resistances
        
        # Check additional data
        for key, data in self.additional_data.items():
            if name.lower() in key.lower():
                return data
        
        return None
    
    def get_display_name(self) -> str:
        """Get a human-readable display name for this dataset"""
        parts = []
        if self.sample and self.sample != "Unknown":
            parts.append(self.sample)
        if self.device and self.device != "UnknownDevice":
            parts.append(self.device)
        if parts:
            return f"{' - '.join(parts)} ({self.test_name})"
        return f"{self.test_name} ({self.filename})"
    
    def get_key_parameters(self) -> str:
        """Get key parameters as a formatted string"""
        key_params = []
        
        # Look for common important parameters
        for key in ['pulse_voltage', 'pulse_width', 'read_voltage', 'set_voltage', 'reset_voltage']:
            if key in self.parameters:
                value = self.parameters[key]
                # Format nicely
                if 'voltage' in key:
                    key_params.append(f"{value}V")
                elif 'width' in key:
                    try:
                        val_float = float(value)
                        if val_float < 0.001:
                            key_params.append(f"{val_float*1e6:.0f}µs")
                        else:
                            key_params.append(f"{val_float*1e3:.1f}ms")
                    except:
                        key_params.append(value)
        
        return ", ".join(key_params) if key_params else ""


def detect_file_format(lines: List[str], filename: str) -> str:
    """
    Detect file format from first few lines and filename.
    
    Returns: 'tsp', 'pmu_simple', 'endurance', 'iv_sweep', or 'unknown'
    """
    # Check for TSP format (has # Keithley header)
    for line in lines[:10]:
        if '# Keithley' in line or '# ================================================================' in line:
            return 'tsp'
    
    # Check for Endurance format
    if 'endurance' in filename.lower():
        for line in lines[:5]:
            if 'Iteration' in line and 'Resistance (Reset)' in line:
                return 'endurance'
    
    # Check first line for headers
    if len(lines) > 0:
        first_line = lines[0].strip().lower()
        
        # PMU Simple: Time, Voltage, Current, Resistance
        if 'time' in first_line and 'voltage' in first_line and 'current' in first_line and 'resistance' in first_line:
            return 'pmu_simple'
        
        # IV Sweep: Voltage, Current (with or without Time)
        if 'voltage' in first_line and 'current' in first_line:
            if 'fs-' in filename.lower() or 'hysteresis' in filename.lower():
                return 'iv_sweep'
            return 'iv_sweep'
        
        # Endurance: Iteration, Time, Resistance (Reset), Resistance (Set)
        if 'iteration' in first_line and 'resistance' in first_line and ('reset' in first_line or 'set' in first_line):
            return 'endurance'
    
    return 'unknown'


def extract_params_from_filename(filename: str) -> Dict[str, str]:
    """Extract parameters from filename patterns"""
    params = {}
    
    # Example: 12-set_-2.5v_100e-6-read_0.3v_5e-6.txt
    # Extract voltages and currents
    import re
    
    # Voltage patterns: -2.5v, 0.3v, 1.5v, 2.8v
    voltages = re.findall(r'([+-]?\d+\.?\d*)[vV]', filename)
    if voltages:
        if 'set' in filename.lower():
            params['set_voltage'] = voltages[0]
        if 'read' in filename.lower():
            params['read_voltage'] = voltages[-1] if len(voltages) > 1 else voltages[0]
        if len(voltages) == 1:
            params['voltage'] = voltages[0]
    
    # Current patterns: 100e-6, 5e-6, 100E-6
    currents = re.findall(r'(\d+\.?\d*)[eE][+-](\d+)', filename)
    if currents:
        # Convert to readable format
        for base, exp in currents:
            value = float(base) * (10 ** -int(exp))
            if 'read' in filename.lower():
                params['read_current'] = f"{value:.2e}"
            else:
                params['current'] = f"{value:.2e}"
    
    # Time/delay patterns: 0.05sv, 0.01sd, 100E-6x30
    if 'x' in filename.lower():
        cycles = re.findall(r'x(\d+)', filename)
        if cycles:
            params['num_cycles'] = cycles[0]
    
    # Extract sample/device from path if available
    if 's2' in filename.lower():
        params['sample'] = filename.split('-')[0] if '-' in filename else 'Unknown'
    
    return params


def parse_tsp_file(filepath: Path) -> Optional[TSPData]:
    """
    Parse a TSP measurement file (supports multiple formats).
    
    Args:
        filepath: Path to the .txt file
    
    Returns:
        TSPData object or None if parsing fails
    """
    try:
        data = TSPData(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return None
        
        # Detect file format
        file_format = detect_file_format(lines, data.filename)
        
        # Route to appropriate parser
        if file_format == 'tsp':
            return parse_tsp_format(data, lines)
        elif file_format == 'pmu_simple':
            return parse_pmu_simple_format(data, lines)
        elif file_format == 'endurance':
            return parse_endurance_format(data, lines)
        elif file_format == 'iv_sweep':
            return parse_iv_sweep_format(data, lines)
        else:
            # Try generic parser as fallback
            return parse_tsp_format(data, lines)
            
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_tsp_format(data: TSPData, lines: List[str]) -> Optional[TSPData]:
    """Parse standard TSP format with metadata headers"""
    try:
        # Parse header section
        header_end = None
        in_parameters = False
        in_hardware_limits = False
        in_notes = False
        
        for i, line in enumerate(lines):
            line = line.rstrip('\n')
            
            # Skip separator lines
            if line.startswith('# ================================================================'):
                continue
            
            # Main metadata fields
            if line.startswith('# Keithley 2450 TSP Pulse Test:'):
                data.test_name = line.split(':', 1)[1].strip()
            elif line.startswith('# Timestamp:'):
                data.timestamp = line.split(':', 1)[1].strip()
            elif line.startswith('# Sample:'):
                data.sample = line.split(':', 1)[1].strip()
            elif line.startswith('# Device:'):
                data.device = line.split(':', 1)[1].strip()
            elif line.startswith('# Instrument:'):
                data.instrument = line.split(':', 1)[1].strip()
            elif line.startswith('# Address:'):
                data.address = line.split(':', 1)[1].strip()
            
            # Section markers
            elif line.startswith('# Test Parameters:'):
                in_parameters = True
                in_hardware_limits = False
                in_notes = False
            elif line.startswith('# Hardware Limits:'):
                in_parameters = False
                in_hardware_limits = True
                in_notes = False
            elif line.startswith('# User Notes:'):
                in_parameters = False
                in_hardware_limits = False
                in_notes = True
            elif line.startswith('# Data Points:'):
                data.data_points = int(line.split(':')[1].strip())
                in_parameters = False
                in_hardware_limits = False
                in_notes = False
            elif line.startswith('# Duration:'):
                duration_str = line.split(':')[1].strip()
                try:
                    data.duration = float(duration_str.split()[0])
                except:
                    data.duration = 0.0
            
            # Parse parameter/limit/note lines
            elif line.startswith('#   ') and ':' in line:
                key_value = line[4:]  # Remove '#   '
                if ':' in key_value:
                    key, value = key_value.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if in_parameters:
                        data.parameters[key] = value
                    elif in_hardware_limits:
                        data.hardware_limits[key] = value
                    elif in_notes:
                        if data.notes:
                            data.notes += '\n' + value
                        else:
                            data.notes = value
            
            # Column headers (tab-delimited line starting with #)
            elif line.startswith('# ') and '\t' in line:
                header_line = line[2:].strip()  # Remove '# '
                data.headers = [h.strip() for h in header_line.split('\t')]
                header_end = i
                break
        
        if header_end is None:
            # Silently skip files with no data (incomplete measurements)
            return None
        
        # Parse data section
        data_rows = []
        for line in lines[header_end + 1:]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Split by tab
            values = line.split('\t')
            if len(values) != len(data.headers):
                # Skip malformed lines
                continue
            
            # Convert to appropriate types
            row = []
            for i, val in enumerate(values):
                try:
                    # First column is always int (Measurement_Number)
                    if i == 0:
                        row.append(int(val))
                    else:
                        # Try float, handle NaN
                        if val.upper() == 'NAN':
                            row.append(np.nan)
                        else:
                            row.append(float(val))
                except ValueError:
                    # String column
                    row.append(val)
            
            data_rows.append(row)
        
        if not data_rows:
            # Silently skip files with no data rows (incomplete measurements)
            return None
        
        # Convert to numpy array
        data.data = np.array(data_rows, dtype=object)
        
        # Extract standard columns
        if len(data.headers) >= 5:
            data.measurement_numbers = np.array([row[0] for row in data_rows], dtype=int)
            data.timestamps = np.array([row[1] for row in data_rows], dtype=float)
            data.voltages = np.array([row[2] for row in data_rows], dtype=float)
            data.currents = np.array([row[3] for row in data_rows], dtype=float)
            data.resistances = np.array([row[4] for row in data_rows], dtype=float)
            
            # Extract additional columns (beyond standard 5)
            for i in range(5, len(data.headers)):
                col_name = data.headers[i]
                col_data = [row[i] for row in data_rows]
                
                # Try to convert to numeric
                try:
                    data.additional_data[col_name] = np.array(col_data, dtype=float)
                except (ValueError, TypeError):
                    # Keep as object array (strings)
                    data.additional_data[col_name] = np.array(col_data, dtype=object)
        
        return data
    except Exception as e:
        print(f"Error parsing TSP format: {e}")
        return None


def parse_pmu_simple_format(data: TSPData, lines: List[str]) -> Optional[TSPData]:
    """Parse PMU simple format: Time, Voltage, Current, Resistance (no metadata)"""
    try:
        # First line is headers
        if len(lines) < 2:
            return None
        
        header_line = lines[0].strip()
        # Split by tab or space
        if '\t' in header_line:
            data.headers = [h.strip() for h in header_line.split('\t')]
            delimiter = '\t'
        else:
            data.headers = [h.strip() for h in header_line.split()]
            delimiter = None
        
        # Extract parameters from filename
        data.parameters = extract_params_from_filename(data.filename)
        
        # Set test name
        if 'set' in data.filename.lower() and 'read' in data.filename.lower():
            data.test_name = "PMU Pulse-Read"
        else:
            data.test_name = "PMU Measurement"
        
        # Parse data rows
        data_rows = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            # Split by delimiter
            if delimiter:
                values = line.split(delimiter)
            else:
                values = line.split()
            
            if len(values) < len(data.headers):
                continue
            
            # Convert to floats
            try:
                row = [float(v) for v in values[:len(data.headers)]]
                data_rows.append(row)
            except ValueError:
                continue
        
        if not data_rows:
            return None
        
        # Map to standard columns
        time_idx = next((i for i, h in enumerate(data.headers) if 'time' in h.lower()), 0)
        volt_idx = next((i for i, h in enumerate(data.headers) if 'voltage' in h.lower()), 1)
        curr_idx = next((i for i, h in enumerate(data.headers) if 'current' in h.lower()), 2)
        res_idx = next((i for i, h in enumerate(data.headers) if 'resistance' in h.lower()), 3)
        
        # Extract data
        data.timestamps = np.array([row[time_idx] for row in data_rows], dtype=float)
        data.voltages = np.array([row[volt_idx] for row in data_rows], dtype=float)
        data.currents = np.array([row[curr_idx] for row in data_rows], dtype=float)
        data.resistances = np.array([row[res_idx] for row in data_rows], dtype=float)
        
        # Create measurement numbers
        data.measurement_numbers = np.arange(len(data_rows), dtype=int)
        
        # Duration
        if len(data.timestamps) > 1:
            data.duration = float(data.timestamps[-1] - data.timestamps[0])
        
        data.data_points = len(data_rows)
        data.data = np.array(data_rows, dtype=object)
        
        return data
    except Exception as e:
        print(f"Error parsing PMU simple format: {e}")
        return None


def parse_endurance_format(data: TSPData, lines: List[str]) -> Optional[TSPData]:
    """Parse Endurance format: Iteration #, Time (s), Resistance (Reset), Resistance (Set)"""
    try:
        # First line is headers
        if len(lines) < 2:
            return None
        
        header_line = lines[0].strip()
        if '\t' in header_line:
            data.headers = [h.strip() for h in header_line.split('\t')]
            delimiter = '\t'
        else:
            data.headers = [h.strip() for h in header_line.split()]
            delimiter = None
        
        data.test_name = "Endurance Test"
        data.parameters = extract_params_from_filename(data.filename)
        
        # Find column indices
        iter_idx = next((i for i, h in enumerate(data.headers) if 'iteration' in h.lower()), 0)
        time_idx = next((i for i, h in enumerate(data.headers) if 'time' in h.lower()), 1)
        reset_idx = next((i for i, h in enumerate(data.headers) if 'reset' in h.lower()), 2)
        set_idx = next((i for i, h in enumerate(data.headers) if 'set' in h.lower()), 3)
        
        # Parse data
        data_rows = []
        cycles = []
        times = []
        r_reset = []
        r_set = []
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            if delimiter:
                values = line.split(delimiter)
            else:
                values = line.split()
            
            if len(values) < max(iter_idx, time_idx, reset_idx, set_idx) + 1:
                continue
            
            try:
                cycle = int(float(values[iter_idx]))
                time = float(values[time_idx])
                r_r = float(values[reset_idx])
                r_s = float(values[set_idx])
                
                cycles.append(cycle)
                times.append(time)
                r_reset.append(r_r)
                r_set.append(r_s)
                
                data_rows.append([cycle, time, r_r, r_s])
            except (ValueError, IndexError):
                continue
        
        if not data_rows:
            return None
        
        # Store data
        data.measurement_numbers = np.array(cycles, dtype=int)
        data.timestamps = np.array(times, dtype=float)
        data.resistances = np.array(r_reset, dtype=float)  # Use Reset as primary
        
        # Store both states in additional_data
        data.additional_data['Resistance (Reset)'] = np.array(r_reset, dtype=float)
        data.additional_data['Resistance (Set)'] = np.array(r_set, dtype=float)
        data.additional_data['Cycle Number'] = np.array(cycles, dtype=int)
        
        # Create voltages/currents arrays (empty, but required)
        data.voltages = np.zeros(len(data_rows))
        data.currents = np.zeros(len(data_rows))
        
        data.data_points = len(data_rows)
        if len(data.timestamps) > 1:
            data.duration = float(data.timestamps[-1] - data.timestamps[0])
        
        data.data = np.array(data_rows, dtype=object)
        
        return data
    except Exception as e:
        print(f"Error parsing Endurance format: {e}")
        return None


def parse_iv_sweep_format(data: TSPData, lines: List[str]) -> Optional[TSPData]:
    """Parse IV sweep format: Voltage, Current, Time (optional)"""
    try:
        if len(lines) < 2:
            return None
        
        header_line = lines[0].strip()
        if '\t' in header_line:
            data.headers = [h.strip() for h in header_line.split('\t')]
            delimiter = '\t'
        else:
            data.headers = [h.strip() for h in header_line.split()]
            delimiter = None
        
        data.test_name = "IV Sweep (Hysteresis)"
        data.parameters = extract_params_from_filename(data.filename)
        
        # Find column indices
        volt_idx = next((i for i, h in enumerate(data.headers) if 'voltage' in h.lower()), 0)
        curr_idx = next((i for i, h in enumerate(data.headers) if 'current' in h.lower()), 1)
        time_idx = next((i for i, h in enumerate(data.headers) if 'time' in h.lower()), None)
        
        # Parse data
        data_rows = []
        voltages = []
        currents = []
        times = []
        resistances = []
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            if delimiter:
                values = line.split(delimiter)
            else:
                values = line.split()
            
            if len(values) < max(volt_idx, curr_idx) + 1:
                continue
            
            try:
                v = float(values[volt_idx])
                i = float(values[curr_idx])
                t = float(values[time_idx]) if time_idx is not None and time_idx < len(values) else len(voltages) * 0.1
                
                voltages.append(v)
                currents.append(i)
                times.append(t)
                
                # Calculate resistance (avoid division by zero)
                if abs(i) > 1e-12:
                    resistances.append(abs(v / i))
                else:
                    resistances.append(np.nan)
                
                data_rows.append([v, i, t])
            except (ValueError, IndexError, ZeroDivisionError):
                continue
        
        if not data_rows:
            return None
        
        # Store data
        data.voltages = np.array(voltages, dtype=float)
        data.currents = np.array(currents, dtype=float)
        data.timestamps = np.array(times, dtype=float)
        data.resistances = np.array(resistances, dtype=float)
        data.measurement_numbers = np.arange(len(data_rows), dtype=int)
        
        data.data_points = len(data_rows)
        if len(data.timestamps) > 1:
            data.duration = float(data.timestamps[-1] - data.timestamps[0])
        
        data.data = np.array(data_rows, dtype=object)
        
        return data
    except Exception as e:
        print(f"Error parsing IV sweep format: {e}")
        return None


def detect_test_type(data: TSPData) -> str:
    """
    Detect test type from data.
    
    Returns test_name from metadata, or tries to infer from filename if missing.
    """
    if data.test_name:
        return data.test_name
    
    # Try to extract from filename
    # Example: "Pulse-Read-Repeat-001_1.5V_1ms-20251031_143022.txt"
    filename = data.filename.lower()
    
    # New format patterns (check first)
    if 'endurance' in filename:
        return "Endurance Test"
    if 'fs-' in filename or 'hysteresis' in filename:
        return "IV Sweep (Hysteresis)"
    if 'set' in filename and 'read' in filename:
        return "PMU Pulse-Read"
    
    # Common TSP patterns
    test_patterns = [
        'Pulse-Read-Repeat',
        'Multi-Pulse-Then-Read',
        'Width Sweep',
        'Potentiation-Depression Cycle',
        'Relaxation',
        'Pulse-Multi-Read',
        'Multi-Read Only',
    ]
    
    for pattern in test_patterns:
        if pattern.lower().replace('-', '_').replace(' ', '_') in filename:
            return pattern
    
    return "Unknown"


# Module test
if __name__ == "__main__":
    print("TSP Data Parser - Module Test")
    print("=" * 60)
    
    # Test with example file (if available)
    test_file = Path("example_data.txt")
    if test_file.exists():
        print(f"\nParsing: {test_file}")
        data = parse_tsp_file(test_file)
        
        if data:
            print(f"✓ Parsed successfully")
            print(f"  Test: {data.test_name}")
            print(f"  Sample: {data.sample}")
            print(f"  Device: {data.device}")
            print(f"  Points: {len(data.timestamps)}")
            print(f"  Duration: {data.duration:.2f}s")
            print(f"  Columns: {', '.join(data.headers)}")
            print(f"  Parameters: {data.parameters}")
    else:
        print("No test file found. Place example_data.txt in this directory to test.")

