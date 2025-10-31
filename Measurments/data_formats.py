"""
Data Formatting Utilities

Provides centralized data formatting for consistent file output across all measurements.

Eliminates ~10 duplicate data formatting patterns across the codebase.

Author: AI Refactoring - October 2025
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from pathlib import Path
import time


@dataclass
class DataColumn:
    """
    Definition of a data column.
    
    Attributes:
        name: Column name
        unit: Unit of measurement
        format_spec: Format specification for output (e.g., "%0.3E")
    """
    name: str
    unit: str
    format_spec: str = "%0.3E"
    
    def get_header(self) -> str:
        """Get formatted header string."""
        if self.unit:
            return f"{self.name}({self.unit})"
        return self.name


class StandardColumns:
    """Standard column definitions for common measurements."""
    
    TIME = DataColumn("Time", "s", "%0.3E")
    TEMPERATURE = DataColumn("Temperature", "C", "%0.3E")
    VOLTAGE = DataColumn("Voltage", "V", "%0.3E")
    CURRENT = DataColumn("Current", "A", "%0.3E")
    RESISTANCE = DataColumn("Resistance", "Ohm", "%0.3E")
    CONDUCTANCE = DataColumn("Conductance", "S", "%0.3E")
    CONDUCTANCE_NORM = DataColumn("Conductance_Normalized", "", "%0.3E")
    POWER = DataColumn("Power", "W", "%0.3E")
    STD_ERROR = DataColumn("Std_Error", "A", "%0.3E")


class DataFormatter:
    """
    Centralized data formatting for measurement files.
    
    Examples:
        >>> # Basic IV data
        >>> formatter = DataFormatter()
        >>> data, header, fmt = formatter.format_iv_data(
        ...     timestamps=np.array([0, 1, 2]),
        ...     voltages=np.array([0, 0.5, 1.0]),
        ...     currents=np.array([0, 1e-3, 2e-3])
        ... )
        
        >>> # IV data with temperature
        >>> data, header, fmt = formatter.format_iv_data(
        ...     timestamps=np.array([0, 1, 2]),
        ...     voltages=np.array([0, 0.5, 1.0]),
        ...     currents=np.array([0, 1e-3, 2e-3]),
        ...     temperatures=np.array([25.0, 25.1, 25.2])
        ... )
    """
    
    def __init__(self, delimiter: str = "\t"):
        """
        Initialize data formatter.
        
        Args:
            delimiter: Column delimiter (default: tab)
        """
        self.delimiter = delimiter
    
    def format_iv_data(
        self,
        timestamps: np.ndarray,
        voltages: np.ndarray,
        currents: np.ndarray,
        temperatures: Optional[np.ndarray] = None,
        std_errors: Optional[np.ndarray] = None,
        include_resistance: bool = True,
        include_conductance: bool = True
    ) -> Tuple[np.ndarray, str, str]:
        """
        Format IV measurement data for file output.
        
        Args:
            timestamps: Time values
            voltages: Voltage values
            currents: Current values
            temperatures: Optional temperature values
            std_errors: Optional standard error values
            include_resistance: Include resistance column
            include_conductance: Include conductance columns
        
        Returns:
            Tuple[np.ndarray, str, str]: (data_array, header, format_string)
        """
        columns = []
        headers = []
        formats = []
        
        # Time column
        columns.append(timestamps)
        headers.append(StandardColumns.TIME.get_header())
        formats.append(StandardColumns.TIME.format_spec)
        
        # Temperature column (if provided)
        if temperatures is not None:
            columns.append(temperatures)
            headers.append(StandardColumns.TEMPERATURE.get_header())
            formats.append(StandardColumns.TEMPERATURE.format_spec)
        
        # Voltage column
        columns.append(voltages)
        headers.append(StandardColumns.VOLTAGE.get_header())
        formats.append(StandardColumns.VOLTAGE.format_spec)
        
        # Current column
        columns.append(currents)
        headers.append(StandardColumns.CURRENT.get_header())
        formats.append(StandardColumns.CURRENT.format_spec)
        
        # Standard error (if provided)
        if std_errors is not None:
            columns.append(std_errors)
            headers.append(StandardColumns.STD_ERROR.get_header())
            formats.append(StandardColumns.STD_ERROR.format_spec)
        
        # Resistance column
        if include_resistance:
            resistance = self._calculate_resistance(voltages, currents)
            columns.append(resistance)
            headers.append(StandardColumns.RESISTANCE.get_header())
            formats.append(StandardColumns.RESISTANCE.format_spec)
        
        # Conductance columns
        if include_conductance:
            conductance = self._calculate_conductance(voltages, currents)
            columns.append(conductance)
            headers.append(StandardColumns.CONDUCTANCE.get_header())
            formats.append(StandardColumns.CONDUCTANCE.format_spec)
            
            # Normalized conductance
            conductance_norm = self._normalize_conductance(conductance)
            columns.append(conductance_norm)
            headers.append(StandardColumns.CONDUCTANCE_NORM.get_header())
            formats.append(StandardColumns.CONDUCTANCE_NORM.format_spec)
        
        # Combine into final arrays
        data = np.column_stack(columns)
        header = self.delimiter.join(headers)
        fmt = self.delimiter.join(formats)
        
        return data, header, fmt
    
    def format_pmu_data(
        self,
        voltages: np.ndarray,
        currents: np.ndarray,
        timestamps: np.ndarray
    ) -> Tuple[np.ndarray, str, str]:
        """
        Format PMU measurement data.
        
        Args:
            voltages: Voltage values
            currents: Current values
            timestamps: Time values
        
        Returns:
            Tuple[np.ndarray, str, str]: (data_array, header, format_string)
        """
        data = np.column_stack([voltages, currents, timestamps])
        header = f"{StandardColumns.VOLTAGE.get_header()}{self.delimiter}" \
                f"{StandardColumns.CURRENT.get_header()}{self.delimiter}" \
                f"{StandardColumns.TIME.get_header()}"
        fmt = self.delimiter.join([
            StandardColumns.VOLTAGE.format_spec,
            StandardColumns.CURRENT.format_spec,
            StandardColumns.TIME.format_spec
        ])
        
        return data, header, fmt
    
    def format_retention_data(
        self,
        timestamps: np.ndarray,
        voltages: np.ndarray,
        currents: np.ndarray,
        temperatures: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, str, str]:
        """
        Format retention measurement data.
        
        Similar to IV data but optimized for retention measurements.
        """
        return self.format_iv_data(
            timestamps=timestamps,
            voltages=voltages,
            currents=currents,
            temperatures=temperatures,
            include_resistance=True,
            include_conductance=True
        )
    
    def _calculate_resistance(
        self, 
        voltages: np.ndarray, 
        currents: np.ndarray
    ) -> np.ndarray:
        """Calculate resistance, handling division by zero."""
        with np.errstate(divide='ignore', invalid='ignore'):
            resistance = voltages / currents
            resistance[~np.isfinite(resistance)] = np.nan
        return resistance
    
    def _calculate_conductance(
        self, 
        voltages: np.ndarray, 
        currents: np.ndarray
    ) -> np.ndarray:
        """Calculate conductance, handling division by zero."""
        with np.errstate(divide='ignore', invalid='ignore'):
            conductance = currents / voltages
            conductance[~np.isfinite(conductance)] = np.nan
        return conductance
    
    def _normalize_conductance(self, conductance: np.ndarray) -> np.ndarray:
        """Normalize conductance to first non-zero value."""
        # Find first valid (non-zero, non-NaN) conductance value
        valid_mask = np.isfinite(conductance) & (conductance != 0)
        if np.any(valid_mask):
            first_valid = conductance[valid_mask][0]
            return conductance / first_valid
        else:
            return np.full_like(conductance, np.nan)


class TSPDataFormatter:
    """
    Specialized formatter for TSP pulse testing data.
    
    Handles the unique requirements of TSP tests:
    - Variable number of measurement types (timestamps, voltages, currents, resistances, phases, etc.)
    - Comprehensive metadata including test parameters and hardware limits
    - Tab-delimited format matching SMU measurements
    """
    
    def __init__(self, delimiter: str = "\t"):
        self.delimiter = delimiter
    
    def format_tsp_data(
        self,
        data_dict: Dict[str, List[float]],
        test_name: str,
        params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, str, str, Dict[str, Any]]:
        """
        Format TSP test data for file output.
        
        Args:
            data_dict: Dictionary with 'timestamps', 'voltages', 'currents', 'resistances' 
                      and any additional columns (e.g., 'phase', 'pulse_widths', 'cycle_number')
            test_name: Name of the test performed
            params: Test parameters used
            metadata: Additional metadata (instrument info, sample, device, etc.)
        
        Returns:
            Tuple[np.ndarray, str, str, Dict]: (data_array, header, format_string, full_metadata)
        """
        # Required base columns (always present)
        base_cols = ['timestamps', 'voltages', 'currents', 'resistances']
        
        # Build column list
        columns = []
        headers = []
        formats = []
        
        # Measurement/Pulse number FIRST (most useful for analysis)
        num_points = len(data_dict.get('timestamps', []))
        measurement_numbers = np.arange(num_points)
        columns.append(measurement_numbers)
        headers.append('Measurement_Number')
        formats.append('%d')
        
        # Timestamp second
        if 'timestamps' in data_dict:
            columns.append(np.array(data_dict['timestamps']))
            headers.append('Timestamp(s)')
            formats.append('%0.6E')
        
        # Voltage, Current, Resistance
        for col in ['voltages', 'currents', 'resistances']:
            if col in data_dict:
                columns.append(np.array(data_dict[col]))
                unit_map = {'voltages': 'V', 'currents': 'A', 'resistances': 'Ohm'}
                headers.append(f'{col.replace("s", "").capitalize()}({unit_map[col]})')
                formats.append('%0.6E')
        
        # Add any extra columns (e.g., phase, cycle_number, operation, pulse_widths)
        # Exclude metadata fields that are not data columns
        metadata_fields = ['test_name', 'params', 'plot_type']
        extra_cols = [k for k in data_dict.keys() if k not in base_cols and k not in metadata_fields]
        
        # Get expected length from timestamps
        expected_length = len(data_dict.get('timestamps', []))
        
        for col in extra_cols:
            col_data = data_dict[col]
            
            # Skip empty or non-sequence data
            try:
                # Skip if not a proper sequence type
                if isinstance(col_data, (dict, str)):
                    continue
                if not hasattr(col_data, '__len__'):
                    continue
                if len(col_data) == 0:
                    continue
                
                # Convert to numpy array
                col_array = np.array(col_data)
                
                # Must be 1D and match expected length
                if col_array.ndim != 1:
                    print(f"Warning: Skipping column '{col}' - not 1D (shape: {col_array.shape})")
                    continue
                if col_array.size != expected_length:
                    print(f"Warning: Skipping column '{col}' - length mismatch ({col_array.size} vs {expected_length})")
                    continue
                    
                columns.append(col_array)
                
                # Try to format nicely
                col_display = col.replace('_', ' ').title()
                headers.append(col_display)
                
                # Check if numeric or string
                first_val = col_data[0]
                if isinstance(first_val, (int, float, np.number)):
                    formats.append('%0.6E')
                else:
                    formats.append('%s')
                    
            except Exception as e:
                # If anything goes wrong, skip this column
                print(f"Warning: Skipping column '{col}' due to error: {e}")
                continue
        
        # Stack into array
        if not columns:
            raise ValueError("No data columns found to save")
        data = np.column_stack(columns)
        header = self.delimiter.join(headers)
        fmt = self.delimiter.join(formats)
        
        # Build comprehensive metadata
        full_metadata = {
            'test_name': test_name,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': params,
        }
        if metadata:
            full_metadata.update(metadata)
        
        return data, header, fmt, full_metadata


class FileNamer:
    """
    Utilities for generating consistent measurement filenames.
    
    Examples:
        >>> namer = FileNamer()
        >>> filename = namer.create_iv_filename(
        ...     device="A1",
        ...     voltage=1.0,
        ...     measurement_type="sweep"
        ... )
        >>> # "Device_1_A1_1.0V_sweep_20251014_123045.txt"
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize file namer.
        
        Args:
            base_dir: Base directory for saving files
        """
        self.base_dir = base_dir or Path("Data_save_loc")
    
    def create_iv_filename(
        self,
        device: str,
        voltage: float,
        measurement_type: str = "IV",
        status: str = "complete",
        num_measurements: Optional[int] = None
    ) -> str:
        """
        Create standardized IV measurement filename.
        
        Args:
            device: Device identifier
            voltage: Voltage value
            measurement_type: Type of measurement
            status: Measurement status (complete/interrupted)
            num_measurements: Number of measurements
        
        Returns:
            str: Formatted filename
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Extract device number if available
        device_number = "".join(filter(str.isdigit, device)) or "0"
        
        parts = [
            f"Device_{device_number}",
            device,
            f"{voltage}V",
            measurement_type
        ]
        
        if num_measurements is not None:
            parts.append(f"{num_measurements}measurements")
        
        parts.extend([status, timestamp])
        
        return "_".join(parts) + ".txt"
    
    def create_pmu_filename(
        self,
        device: str,
        mode: str,
        index: int = 0
    ) -> str:
        """
        Create standardized PMU measurement filename.
        
        Args:
            device: Device identifier
            mode: Measurement mode
            index: Sequential index
        
        Returns:
            str: Formatted filename
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        mode_clean = mode.replace(' ', '_')
        return f"{index}-{mode_clean}-{timestamp}.txt"
    
    def get_device_folder(
        self,
        sample_name: str,
        device: str,
        subfolder: Optional[str] = None
    ) -> Path:
        """
        Get the folder path for a device's data.
        
        Args:
            sample_name: Sample name
            device: Device identifier (e.g., "A1")
            subfolder: Optional subfolder name
        
        Returns:
            Path: Full path to device folder
        """
        # Extract letter and number from device
        if len(device) >= 2:
            letter = device[0]
            number = device[1:]
        else:
            letter = "X"
            number = "0"
        
        folder = self.base_dir / sample_name / letter / number
        
        if subfolder:
            folder = folder / subfolder
        
        return folder
    
    def create_tsp_filename(
        self,
        test_name: str,
        index: int,
        extension: str = "txt",
        test_details: str = ""
    ) -> str:
        """
        Create standardized TSP test filename with sequential numbering.
        
        Args:
            test_name: Name of test (e.g., "Pulse-Read-Repeat")
            index: Sequential index number
            extension: File extension (default: "txt")
            test_details: Optional test details to append (e.g., "1.5V_100us")
        
        Returns:
            str: Formatted filename like "0-Pulse_Read_Repeat-1.5V_100us-20251029_143022.txt"
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        test_clean = test_name.replace(" ", "_").replace("-", "_")
        
        if test_details:
            return f"{index}-{test_clean}-{test_details}-{timestamp}.{extension}"
        else:
            return f"{index}-{test_clean}-{timestamp}.{extension}"
    
    def get_next_index(self, folder: Path) -> int:
        """
        Get next sequential index for a folder.
        
        Args:
            folder: Folder to check
        
        Returns:
            int: Next available index
        """
        if not folder.exists():
            return 0
        
        # Find all numbered files
        max_idx = -1
        for f in folder.glob("*-*"):
            try:
                idx = int(f.stem.split('-')[0])
                max_idx = max(max_idx, idx)
            except (ValueError, IndexError):
                continue
        
        return max_idx + 1


def save_measurement_data(
    filepath: Path,
    data: np.ndarray,
    header: str,
    fmt: str,
    comments: str = "# "
) -> bool:
    """
    Save measurement data to file.
    
    Args:
        filepath: Path to save file
        data: Data array
        header: Header string
        fmt: Format string
        comments: Comment prefix for header
    
    Returns:
        bool: True if successful
    
    Example:
        >>> data, header, fmt = formatter.format_iv_data(t, v, i)
        >>> save_measurement_data(Path("data.txt"), data, header, fmt)
    """
    try:
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save data
        np.savetxt(filepath, data, fmt=fmt, header=header, comments=comments)
        
        return True
    except Exception as e:
        print(f"Error saving data to {filepath}: {e}")
        return False


def save_tsp_measurement(
    filepath: Path,
    data: np.ndarray,
    header: str,
    fmt: str,
    metadata: Dict[str, Any],
    save_plot: Optional[Any] = None
) -> bool:
    """
    Save TSP measurement data with comprehensive metadata.
    
    Saves two files:
    1. .txt file with data and metadata header
    2. .png file with plot (if provided)
    
    Args:
        filepath: Path to save main .txt file
        data: Data array
        header: Column header string
        fmt: Format string for data
        metadata: Complete metadata dictionary
        save_plot: Matplotlib figure to save (optional)
    
    Returns:
        bool: True if successful
    
    Example:
        >>> save_tsp_measurement(path, data, header, fmt, metadata, fig)
    """
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 1. Save main data file with metadata header
        with open(filepath, 'w', encoding='utf-8') as f:
            # Write comprehensive header
            f.write("# ================================================================\n")
            f.write(f"# Keithley 2450 TSP Pulse Test: {metadata.get('test_name', 'Unknown')}\n")
            f.write("# ================================================================\n")
            f.write(f"# Timestamp: {metadata.get('timestamp', 'N/A')}\n")
            f.write(f"# Sample: {metadata.get('sample', 'Unknown')}\n")
            f.write(f"# Device: {metadata.get('device', 'Unknown')}\n")
            f.write(f"# Instrument: {metadata.get('instrument', 'Keithley 2450')}\n")
            f.write(f"# Address: {metadata.get('address', 'N/A')}\n")
            f.write("#\n")
            
            # Write test parameters
            f.write("# Test Parameters:\n")
            params = metadata.get('parameters', {})
            for key, value in params.items():
                f.write(f"#   {key}: {value}\n")
            f.write("#\n")
            
            # Write hardware limits if present
            if 'hardware_limits' in metadata:
                f.write("# Hardware Limits:\n")
                limits = metadata['hardware_limits']
                for key, value in limits.items():
                    f.write(f"#   {key}: {value}\n")
                f.write("#\n")
            
            # Write data statistics
            f.write(f"# Data Points: {len(data)}\n")
            f.write(f"# Duration: {data[-1][0]:.3f} s\n" if len(data) > 0 else "# Duration: N/A\n")
            
            # Write notes if present
            if 'notes' in metadata and metadata['notes']:
                f.write("#\n")
                f.write("# User Notes:\n")
                for line in metadata['notes'].split('\n'):
                    f.write(f"#   {line}\n")
            
            f.write("#\n")
            f.write("# ================================================================\n")
            f.write(f"# {header}\n")
            
        # Append data to file
        with open(filepath, 'ab') as f:
            np.savetxt(f, data, fmt=fmt, delimiter='', comments='')
        
        # 2. Save plot if provided
        if save_plot is not None:
            plot_path = filepath.with_suffix('.png')
            save_plot.savefig(plot_path, dpi=200, bbox_inches='tight')
        
        # 3. Append to combined log
        log_path = filepath.parent / "tsp_test_log.txt"
        with open(log_path, 'a') as f:
            f.write(f"{metadata.get('timestamp', '')}, {metadata.get('test_name', '')}, "
                   f"{filepath.name}, points={len(data)}\n")
        
        return True
        
    except Exception as e:
        print(f"Error saving TSP data to {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return False


# Module-level test
if __name__ == "__main__":
    print("Testing data_formats module...")
    
    # Test data formatter
    print("\n1. Testing IV data formatting:")
    formatter = DataFormatter()
    
    t = np.array([0, 1, 2, 3])
    v = np.array([0, 0.5, 1.0, 0.5])
    i = np.array([0, 1e-3, 2e-3, 1e-3])
    temp = np.array([25.0, 25.1, 25.2, 25.1])
    
    data, header, fmt = formatter.format_iv_data(t, v, i, temperatures=temp)
    print(f"  Header: {header}")
    print(f"  Format: {fmt}")
    print(f"  Data shape: {data.shape}")
    
    # Test PMU formatting
    print("\n2. Testing PMU data formatting:")
    data_pmu, header_pmu, fmt_pmu = formatter.format_pmu_data(v, i, t)
    print(f"  Header: {header_pmu}")
    
    # Test file namer
    print("\n3. Testing file naming:")
    namer = FileNamer()
    filename = namer.create_iv_filename("A1", 1.5, "sweep", num_measurements=100)
    print(f"  Filename: {filename}")
    
    folder = namer.get_device_folder("MySample", "A1", "IV_sweeps")
    print(f"  Folder: {folder}")
    
    print("\nAll tests passed!")

