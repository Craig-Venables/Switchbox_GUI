"""
Data models for device analysis visualization.

This module defines dataclasses for representing device data, measurements,
classifications, and metrics in a unified structure.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class MetricsData:
    """
    Container for device metrics.
    
    Attributes:
        ron: ON-state resistance (Ohms)
        roff: OFF-state resistance (Ohms)
        on_off_ratio: Switching ratio (Roff/Ron)
        switching_voltage: Voltage required for switching (V)
        set_voltage: SET operation voltage (V)
        reset_voltage: RESET operation voltage (V)
        retention_time: State retention time (seconds)
        endurance_cycles: Number of reliable switching cycles
        nonlinearity: Degree of I-V nonlinearity
        hysteresis_area: Area of hysteresis loop
        switching_energy: Energy per switching event (J)
    """
    ron: Optional[float] = None
    roff: Optional[float] = None
    on_off_ratio: Optional[float] = None
    switching_voltage: Optional[float] = None
    set_voltage: Optional[float] = None
    reset_voltage: Optional[float] = None
    retention_time: Optional[float] = None
    endurance_cycles: Optional[int] = None
    nonlinearity: Optional[float] = None
    hysteresis_area: Optional[float] = None
    switching_energy: Optional[float] = None


@dataclass
class ClassificationResult:
    """
    Device classification result details.
    
    Attributes:
        device_type: Primary classification (e.g., 'memristive', 'ohmic')
        score: Overall classification score (0-100)
        confidence: Confidence level (0-100)
        feature_scores: Dict of individual feature contributions
        warnings: List of warning messages from classification
        decision_path: List of classification decision steps
        raw_scores: Raw scores for all device types
    """
    device_type: str = "Unknown"
    score: float = 0.0
    confidence: float = 0.0
    feature_scores: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    decision_path: List[str] = field(default_factory=list)
    raw_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class MeasurementData:
    """
    Individual measurement file information.
    
    Attributes:
        file_path: Path to measurement file
        measurement_type: Type of measurement (e.g., 'iv_sweep', 'pulse', 'retention')
        timestamp: Measurement timestamp
        voltage: Voltage data array
        current: Current data array
        time: Time data array (optional)
        cycles: Number of measurement cycles
        analysis_results: Dict containing analysis results from sweep_analyzer
    """
    file_path: Path
    measurement_type: str = "iv_sweep"
    timestamp: Optional[str] = None
    voltage: Optional[List[float]] = None
    current: Optional[List[float]] = None
    time: Optional[List[float]] = None
    cycles: int = 1
    analysis_results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceData:
    """
    Unified device representation aggregating all data sources.
    
    This class combines data from device tracking files, research JSONs,
    classification logs, and raw measurement files into a single unified object.
    
    Attributes:
        device_id: Unique device identifier (e.g., 'G_1', 'Device_001')
        sample_name: Name of the sample this device belongs to
        section: Section identifier (e.g., 'G', 'Section_A')
        device_number: Device number within section
        
        # Classification data
        current_classification: Current device classification result
        memristivity_score: Overall memristivity score (0-100)
        
        # Measurement data
        measurements: List of all measurements for this device
        raw_data_files: List of paths to raw measurement TXT files
        best_measurement: Index of best performing measurement
        worst_measurement: Index of worst performing measurement
        
        # Metrics
        metrics: Device metrics (Ron, Roff, switching, etc.)
        
        # Additional data
        research_data: Dict containing research JSON data
        tracking_history: Dict containing device history from tracking files
        classification_log: Raw classification log text
    """
    # Basic identification
    device_id: str
    sample_name: str = ""
    section: str = ""
    device_number: int = 0
    
    # Classification
    current_classification: ClassificationResult = field(default_factory=ClassificationResult)
    memristivity_score: float = 0.0
    
    # Measurements
    measurements: List[MeasurementData] = field(default_factory=list)
    raw_data_files: List[Path] = field(default_factory=list)
    best_measurement: Optional[int] = None
    worst_measurement: Optional[int] = None
    
    # Metrics
    metrics: MetricsData = field(default_factory=MetricsData)
    
    # Additional data
    research_data: Dict[str, Any] = field(default_factory=dict)
    tracking_history: Dict[str, Any] = field(default_factory=dict)
    classification_log: str = ""
    
    def get_score_for_display(self) -> str:
        """
        Get formatted score string for display.
        
        Returns:
            Formatted score string (e.g., "87.3" or "Unknown")
        """
        if self.memristivity_score > 0:
            return f"{self.memristivity_score:.1f}"
        return "N/A"
    
    def get_status_icon(self) -> str:
        """
        Get status icon based on score and confidence.
        
        Returns:
            Unicode status icon (✓, ⚠, or ✗)
        """
        if self.memristivity_score >= 70 and self.current_classification.confidence >= 70:
            return "✓"  # Good
        elif self.memristivity_score >= 40 or self.current_classification.confidence >= 50:
            return "⚠"  # Uncertain
        else:
            return "✗"  # Poor
    
    def has_valid_data(self) -> bool:
        """
        Check if device has valid measurement data.
        
        Returns:
            True if device has at least one measurement with data
        """
        return len(self.measurements) > 0 or len(self.raw_data_files) > 0
