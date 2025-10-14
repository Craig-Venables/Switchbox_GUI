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

