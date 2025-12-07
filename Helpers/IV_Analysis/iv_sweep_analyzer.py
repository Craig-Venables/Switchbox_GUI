"""
IV Sweep Analyzer - Fast Data Extraction
==========================================

This module provides fast, comprehensive data extraction from IV sweep measurements.
It extracts all relevant metrics without LLM processing, making it ideal for
quick analysis of single sweeps or batch processing.

Purpose:
- Extract comprehensive metrics from IV sweeps (fast, no LLM)
- Support IV sweeps, pulse, endurance, and retention measurements
- Include metadata (LED state, temperature, etc.)
- Return structured data dictionaries

Example Usage:
    # Analyze a file
    from Helpers.IV_Analysis import IVSweepAnalyzer
    
    analyzer = IVSweepAnalyzer(analysis_level='full')
    data = analyzer.analyze_sweep(file_path="device_sweep.txt")
    
    print(f"Device Type: {data['classification']['device_type']}")
    print(f"Switching Ratio: {data['resistance_metrics']['switching_ratio_mean']:.1f}")
    
    # Analyze with metadata
    metadata = {'led_on': True, 'led_type': 'UV', 'temperature': 25.0}
    data = analyzer.analyze_sweep(
        file_path="sweep.txt",
        metadata=metadata
    )
    
    # Analyze direct data (no file)
    import numpy as np
    voltage = np.array([...])
    current = np.array([...])
    data = analyzer.analyze_sweep(voltage=voltage, current=current)
"""

import json
import numpy as np
from typing import Dict, List, Optional, Union, Any

from .sing_file_analyser import analyze_single_file, read_data_file


class IVSweepAnalyzer:
    """
    Fast analyzer for extracting comprehensive data from IV sweep measurements.
    
    This class focuses on data extraction without LLM processing, making it
    efficient for single sweeps and batch processing. All metrics are extracted
    and returned in a structured dictionary.
    
    Example:
        >>> analyzer = IVSweepAnalyzer(analysis_level='full')
        >>> data = analyzer.analyze_sweep(file_path="sweep.txt")
        >>> print(data['classification']['device_type'])
        memristive
        >>> print(data['resistance_metrics']['switching_ratio_mean'])
        45.2
    """
    
    def __init__(self, analysis_level: str = 'full'):
        """
        Initialize the IV Sweep Analyzer.
        
        Parameters:
        -----------
        analysis_level : str, default='full'
            Analysis depth. Options:
            - 'basic': Fast, core metrics only (Ron, Roff, areas)
            - 'classification': Adds device classification
            - 'full': Adds conduction models and advanced metrics
            - 'research': Maximum detail with extra diagnostics
        
        Example:
            >>> # Fast basic analysis
            >>> analyzer = IVSweepAnalyzer(analysis_level='basic')
            >>> 
            >>> # Comprehensive analysis
            >>> analyzer = IVSweepAnalyzer(analysis_level='full')
        """
        self.analysis_level = analysis_level
        self.analyzer = None
        self.extracted_data = None
        self.metadata = {}
    
    def analyze_sweep(self, 
                     voltage: Optional[np.ndarray] = None,
                     current: Optional[np.ndarray] = None,
                     time: Optional[np.ndarray] = None,
                     file_path: Optional[str] = None,
                     measurement_type: Optional[str] = None,
                     device_name: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze an IV sweep and extract all relevant information.
        
        Can accept either file_path OR voltage/current data directly. This is
        the main method for data extraction - fast and comprehensive.
        
        Parameters:
        -----------
        voltage : array-like, optional
            Voltage data (required if file_path not provided)
        current : array-like, optional
            Current data (required if file_path not provided)
        time : array-like, optional
            Time data for pulse/retention measurements
        file_path : str, optional
            Path to data file (alternative to providing voltage/current directly)
        measurement_type : str, optional
            Type of measurement: 'iv_sweep', 'pulse', 'endurance', 'retention'
            If None, will be auto-detected from data
        device_name : str, optional
            Name/identifier for the device (extracted from filename if file_path provided)
        metadata : dict, optional
            Additional metadata about the measurement:
            - 'led_on': bool - Whether LED was on during measurement
            - 'led_type': str - Type of LED used (e.g., 'red', 'blue', 'UV')
            - 'led_wavelength': float - LED wavelength in nm
            - 'temperature': float - Measurement temperature in °C
            - 'humidity': float - Measurement humidity in %
            - 'bias_voltage': float - DC bias voltage if applicable
            - 'sweep_rate': float - Voltage sweep rate in V/s
            - 'notes': str - Any additional notes
            - Any other custom fields
        
        Returns:
        --------
        dict : Complete analysis results with all extracted metrics
        
        Example:
            >>> # Analyze from file
            >>> analyzer = IVSweepAnalyzer()
            >>> data = analyzer.analyze_sweep(file_path="device_1.txt")
            >>> print(data['classification']['device_type'])
            memristive
            >>> 
            >>> # Analyze with metadata
            >>> metadata = {
            ...     'led_on': True,
            ...     'led_type': 'UV',
            ...     'led_wavelength': 365,
            ...     'temperature': 25.0
            ... }
            >>> data = analyzer.analyze_sweep(
            ...     file_path="sweep.txt",
            ...     metadata=metadata
            ... )
            >>> 
            >>> # Analyze direct data
            >>> import numpy as np
            >>> v = np.array([0, 1, 2, 1, 0, -1, -2, -1, 0])
            >>> i = np.array([0, 1e-6, 2e-6, 1.5e-6, 0, -1e-6, -2e-6, -1.5e-6, 0])
            >>> data = analyzer.analyze_sweep(voltage=v, current=i)
        """
        # Handle file_path or direct data
        if file_path is not None:
            # Read from file
            result = read_data_file(file_path)
            if len(result) == 3:
                voltage, current, time = result
            else:
                voltage, current = result
                time = None
            
            # Extract device name from filename if not provided
            if device_name is None:
                import os
                device_name = os.path.splitext(os.path.basename(file_path))[0]
        
        elif voltage is None or current is None:
            raise ValueError("Must provide either file_path OR both voltage and current data")
        
        # Store metadata
        self.metadata = metadata or {}
        
        # Auto-detect measurement type if not provided
        if measurement_type is None:
            if time is not None:
                # Check if it looks like retention (long constant periods)
                if len(np.unique(voltage)) < len(voltage) / 10:
                    measurement_type = 'retention'
                # Check if it looks like pulse (step changes)
                elif np.max(np.abs(np.diff(voltage))) > 10 * np.median(np.abs(np.diff(voltage))):
                    measurement_type = 'pulse'
                else:
                    measurement_type = 'iv_sweep'
            else:
                # Check for multiple cycles (endurance)
                zero_crossings = np.where(np.diff(np.signbit(voltage)))[0]
                if len(zero_crossings) > 8:  # Multiple cycles
                    measurement_type = 'endurance'
                else:
                    measurement_type = 'iv_sweep'
        
        # Run the technical analysis
        self.analyzer = analyze_single_file(
            voltage, current, time, 
            measurement_type=measurement_type,
            analysis_level=self.analysis_level
        )
        
        # Extract comprehensive information
        self.extracted_data = self._extract_all_information(device_name)
        
        return self.extracted_data
    
    def _extract_all_information(self, device_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract all available information from the analyzer.
        
        Internal method that compiles all metrics into a structured dictionary.
        Called automatically by analyze_sweep().
        
        Returns:
        --------
        dict : Comprehensive extracted information
        """
        if self.analyzer is None:
            raise ValueError("No analysis has been performed yet. Call analyze_sweep() first.")
        
        # Get all results based on analysis level
        results = self.analyzer.get_results(level=self.analysis_level)
        
        # Build comprehensive data structure
        extracted = {
            'device_info': {
                'name': device_name,
                'analysis_level': self.analysis_level,
                'measurement_type': self.analyzer.measurement_type,
                'num_loops': self.analyzer.num_loops,
                'metadata': self.metadata.copy() if self.metadata else {},
            },
            'classification': {
                'device_type': self.analyzer.device_type,
                'confidence': float(self.analyzer.classification_confidence),
                'conduction_mechanism': self.analyzer.conduction_mechanism,
                'model_r2': float(self.analyzer.model_parameters.get('R2', 0)) if isinstance(self.analyzer.model_parameters, dict) else 0.0,
                'features': self.analyzer.classification_features if hasattr(self.analyzer, 'classification_features') else {},
                'explanation': self.analyzer.classification_explanation if hasattr(self.analyzer, 'classification_explanation') else {},
            },
            'resistance_metrics': {
                'ron_mean': float(np.mean(self.analyzer.ron)) if self.analyzer.ron else 0.0,
                'ron_std': float(np.std(self.analyzer.ron)) if self.analyzer.ron else 0.0,
                'roff_mean': float(np.mean(self.analyzer.roff)) if self.analyzer.roff else 0.0,
                'roff_std': float(np.std(self.analyzer.roff)) if self.analyzer.roff else 0.0,
                'switching_ratio_mean': float(np.mean(self.analyzer.switching_ratio)) if self.analyzer.switching_ratio else 0.0,
                'switching_ratio_std': float(np.std(self.analyzer.switching_ratio)) if self.analyzer.switching_ratio else 0.0,
                'on_off_ratio_mean': float(np.mean(self.analyzer.on_off)) if self.analyzer.on_off else 0.0,
                'window_margin_mean': float(np.mean(self.analyzer.window_margin)) if self.analyzer.window_margin else 0.0,
            },
            'voltage_metrics': {
                'von_mean': float(np.mean(self.analyzer.von)) if self.analyzer.von else 0.0,
                'voff_mean': float(np.mean(self.analyzer.voff)) if self.analyzer.voff else 0.0,
                'max_voltage': float(np.max(np.abs(self.analyzer.voltage))),
                'min_voltage': float(np.min(np.abs(self.analyzer.voltage))),
            },
            'hysteresis_metrics': {
                'normalized_area_mean': float(np.mean(self.analyzer.normalized_areas)) if self.analyzer.normalized_areas else 0.0,
                'normalized_area_std': float(np.std(self.analyzer.normalized_areas)) if self.analyzer.normalized_areas else 0.0,
                'total_area': float(np.sum(self.analyzer.areas)) if self.analyzer.areas else 0.0,
                'has_hysteresis': self.analyzer.classification_features.get('has_hysteresis', False) if hasattr(self.analyzer, 'classification_features') else False,
                'pinched_hysteresis': self.analyzer.classification_features.get('pinched_hysteresis', False) if hasattr(self.analyzer, 'classification_features') else False,
            },
            'performance_metrics': {
                'retention_score': float(self.analyzer.retention_score),
                'endurance_score': float(self.analyzer.endurance_score),
                'rectification_ratio_mean': float(np.mean(self.analyzer.rectification_ratio)) if self.analyzer.rectification_ratio else 1.0,
                'nonlinearity_mean': float(np.mean(self.analyzer.nonlinearity_factor)) if self.analyzer.nonlinearity_factor else 0.0,
                'asymmetry_mean': float(np.mean(self.analyzer.asymmetry_factor)) if self.analyzer.asymmetry_factor else 0.0,
                'power_consumption_mean': float(np.mean(self.analyzer.power_consumption)) if self.analyzer.power_consumption else 0.0,
                'energy_per_switch_mean': float(np.mean(self.analyzer.energy_per_switch)) if self.analyzer.energy_per_switch else 0.0,
                'compliance_current': float(self.analyzer.compliance_current * 1e6) if self.analyzer.compliance_current else None,
            },
            'summary_stats': self.analyzer.get_summary_stats(),
        }
        
        # Add research-level diagnostics if available
        if self.analysis_level == 'research' and hasattr(self.analyzer, 'switching_polarity'):
            extracted['research_diagnostics'] = {
                'switching_polarity': self.analyzer.switching_polarity,
                'ndr_index': float(self.analyzer.ndr_index) if self.analyzer.ndr_index is not None else None,
                'hysteresis_direction': self.analyzer.hysteresis_direction,
                'kink_voltage': float(self.analyzer.kink_voltage) if self.analyzer.kink_voltage is not None else None,
                'loop_similarity_score': float(self.analyzer.loop_similarity_score) if self.analyzer.loop_similarity_score is not None else None,
                'pinch_offset': float(self.analyzer.pinch_offset) if self.analyzer.pinch_offset is not None else None,
                'noise_floor': float(self.analyzer.noise_floor) if self.analyzer.noise_floor is not None else None,
            }
        
        # Add validation results if available
        if 'validation' in results:
            extracted['validation'] = results['validation']
        
        # Add performance metrics if available
        if 'performance' in results:
            extracted['detailed_performance'] = results['performance']
        
        return extracted
    
    def save_analysis(self, output_path: str, analysis_result: Optional[Dict] = None):
        """
        Save complete analysis results to a JSON file.
        
        Parameters:
        -----------
        output_path : str
            Path to save the JSON file
        analysis_result : dict, optional
            Analysis result to save (uses last analysis if not provided)
        
        Example:
            >>> analyzer = IVSweepAnalyzer()
            >>> data = analyzer.analyze_sweep(file_path="sweep.txt")
            >>> analyzer.save_analysis("results.json")
        """
        if analysis_result is None:
            analysis_result = self.extracted_data
        
        if analysis_result is None:
            raise ValueError("No analysis result to save. Run analyze_sweep() first.")
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(item) for item in obj]
            return obj
        
        serializable_result = convert_types(analysis_result)
        
        with open(output_path, 'w') as f:
            json.dump(serializable_result, f, indent=2)
        
        print(f"Analysis saved to {output_path}")


def analyze_sweep(file_path: Optional[str] = None,
                  voltage: Optional[np.ndarray] = None,
                  current: Optional[np.ndarray] = None,
                  time: Optional[np.ndarray] = None,
                  metadata: Optional[Dict[str, Any]] = None,
                  analysis_level: str = 'full',
                  save_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function for quick single-sweep analysis.
    
    Simple one-line function to analyze a sweep and get all data back.
    Fast - no LLM processing.
    
    Parameters:
    -----------
    file_path : str, optional
        Path to data file (alternative to voltage/current)
    voltage : array-like, optional
        Voltage data (required if file_path not provided)
    current : array-like, optional
        Current data (required if file_path not provided)
    time : array-like, optional
        Time data for pulse/retention measurements
    metadata : dict, optional
        Measurement metadata (LED state, temperature, etc.)
    analysis_level : str, default='full'
        Analysis depth: 'basic', 'classification', 'full', 'research'
    save_path : str, optional
        Path to save JSON results
    
    Returns:
    --------
    dict : Complete analysis results
    
    Example:
        >>> # Quick file analysis
        >>> from Helpers.IV_Analysis import analyze_sweep
        >>> data = analyze_sweep(file_path="device.txt")
        >>> print(data['classification']['device_type'])
        memristive
        >>> 
        >>> # With metadata
        >>> data = analyze_sweep(
        ...     file_path="sweep.txt",
        ...     metadata={'led_on': True, 'led_type': 'UV'}
        ... )
    """
    analyzer = IVSweepAnalyzer(analysis_level=analysis_level)
    result = analyzer.analyze_sweep(
        file_path=file_path,
        voltage=voltage,
        current=current,
        time=time,
        metadata=metadata
    )
    
    if save_path:
        analyzer.save_analysis(save_path, result)
    
    return result


def quick_analyze(voltage, current, time=None, metadata=None, **kwargs) -> Dict[str, Any]:
    """
    Ultra-simple function to analyze sweep data immediately after measurement.
    
    Just pass your voltage and current arrays - that's it! Perfect for
    calling right after a sweep completes.
    
    Parameters:
    -----------
    voltage : array-like
        Voltage data from sweep (required)
    current : array-like
        Current data from sweep (required)
    time : array-like, optional
        Time data (for pulse/retention measurements)
    metadata : dict, optional
        Quick metadata dict. Common keys:
        - 'led_on': bool
        - 'led_type': str (e.g., 'UV', 'red', 'blue')
        - 'temperature': float
        - 'device_name': str
    **kwargs : optional
        Additional args passed to analyze_sweep (e.g., analysis_level='full')
    
    Returns:
    --------
    dict : Complete analysis results
    
    Example:
        >>> # After a sweep, just pass the data:
        >>> from Helpers.IV_Analysis import quick_analyze
        >>> 
        >>> # Your sweep returns: voltages, currents
        >>> voltages, currents = run_sweep()
        >>> 
        >>> # One line analysis:
        >>> results = quick_analyze(voltages, currents)
        >>> print(results['classification']['device_type'])
        >>> 
        >>> # With metadata:
        >>> results = quick_analyze(
        ...     voltages, currents,
        ...     metadata={'led_on': True, 'led_type': 'UV', 'temperature': 25.0}
        ... )
        >>> 
        >>> # Access results:
        >>> print(f"Device: {results['classification']['device_type']}")
        >>> print(f"Switching Ratio: {results['resistance_metrics']['switching_ratio_mean']:.1f}")
        >>> print(f"Ron: {results['resistance_metrics']['ron_mean']:.2e} Ω")
    """
    return analyze_sweep(
        voltage=voltage,
        current=current,
        time=time,
        metadata=metadata,
        **kwargs
    )

