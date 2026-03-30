"""
Data loading module for parsing and aggregating device analysis data.

This module loads data from various sources (JSON files, TXT measurements, logs)
and combines them into unified DeviceData objects.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging
import re

from .device_data_model import (
    DeviceData,
    MeasurementData,
    ClassificationResult,
    MetricsData
)
from .data_discovery import DataDiscovery

# Set up logging
logger = logging.getLogger(__name__)


class DataLoader:
    """
    Load and parse device analysis data from various file formats.
    
    Handles:
    - Device tracking JSON files (_history.json)
    - Research JSON files (_research.json)
    - Classification log files (classification_log.txt)
    - Raw measurement TXT files (voltage, current data)
    """
    
    @staticmethod
    def load_sample(sample_path: Path) -> Dict[str, DeviceData]:
        """
        Load all devices from a sample directory.
        
        Args:
            sample_path: Path to sample directory
            
        Returns:
            Dictionary mapping device_id to DeviceData object
        """
        devices = {}
        sample_name = DataDiscovery.get_sample_name(sample_path)
        
        logger.info(f"Loading sample: {sample_name}")
        
        # Discover all device folders
        device_folders = DataDiscovery.find_device_folders(sample_path)
        
        for device_id, device_path in device_folders:
            try:
                device_data = DataLoader.load_device(
                    device_id, device_path, sample_name, sample_path
                )
                if device_data.has_valid_data():
                    devices[device_id] = device_data
                else:
                    logger.debug(f"Skipping device {device_id} (no valid data)")
            except Exception as e:
                logger.error(f"Error loading device {device_id}: {e}")
        
        logger.info(f"Loaded {len(devices)} devices from sample {sample_name}")
        return devices
    
    @staticmethod
    def load_device(device_id: str, device_path: Path, 
                   sample_name: str, sample_path: Path) -> DeviceData:
        """
        Load data for a single device from all available sources.
        
        Args:
            device_id: Device identifier (e.g., 'G_1')
            device_path: Path to device directory
            sample_name: Sample name
            sample_path: Path to sample directory
            
        Returns:
            DeviceData object with aggregated data
        """
        # Parse device_id to extract section and device number
        section, device_num = DataLoader._parse_device_id(device_id)
        
        # Create base DeviceData object
        device = DeviceData(
            device_id=device_id,
            sample_name=sample_name,
            section=section,
            device_number=device_num
        )
        
        # Load classification data from log
        classification_log = DataDiscovery.find_classification_logs(device_path)
        if classification_log:
            classification = DataLoader.parse_classification_log(classification_log)
            device.current_classification = classification
            device.memristivity_score = classification.score
            device.classification_log = classification_log.read_text(encoding='utf-8', errors='ignore')
        
        # Load raw measurement files
        raw_files = DataDiscovery.find_raw_data_files(device_path)
        device.raw_data_files = raw_files
        
        # Load measurements from raw files
        for raw_file in raw_files[:10]:  # Limit to first 10 files to avoid overload
            try:
                measurement = DataLoader.load_measurement_from_txt(raw_file)
                if measurement:
                    device.measurements.append(measurement)
            except Exception as e:
                logger.debug(f"Error loading measurement {raw_file.name}: {e}")
        
        # Load research JSON files
        research_files = DataDiscovery.find_research_files(device_path)
        if research_files:
            for research_file in research_files[:5]:  # Limit to first 5
                try:
                    research_data = DataLoader.load_research_json(research_file)
                    device.research_data.update(research_data)
                except Exception as e:
                    logger.debug(f"Error loading research file {research_file.name}: {e}")
        
        # Load device tracking data
        tracking_files = DataDiscovery.find_device_tracking_files(sample_path, device_id)
        if tracking_files:
            try:
                tracking = DataLoader.load_device_tracking(tracking_files[0])
                device.tracking_history = tracking
            except Exception as e:
                logger.debug(f"Error loading tracking file: {e}")
        
        # Extract metrics from classification and measurements
        device.metrics = DataLoader._extract_metrics(device)
        
        # Identify best and worst measurements
        DataLoader._identify_best_worst_measurements(device)
        
        return device
    
    @staticmethod
    def load_device_tracking(file_path: Path) -> Dict[str, Any]:
        """
        Parse device tracking JSON file.
        
        Args:
            file_path: Path to _history.json file
            
        Returns:
            Dictionary containing tracking data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Error loading tracking file {file_path}: {e}")
            return {}
    
    @staticmethod
    def parse_classification_log(log_path: Path) -> ClassificationResult:
        """
        Parse classification log file to extract classification results.
        
        Args:
            log_path: Path to classification_log.txt
            
        Returns:
            ClassificationResult object
        """
        result = ClassificationResult()
        
        try:
            content = log_path.read_text(encoding='utf-8', errors='ignore')
            
            # Extract device type (look for "Classification: <type>")
            type_match = re.search(r'Classification:\s*(\w+)', content, re.IGNORECASE)
            if type_match:
                result.device_type = type_match.group(1).capitalize()
            
            # Extract score (look for "Score: <number>" or "Memristivity Score: <number>")
            score_patterns = [
                r'Memristivity Score:\s*([\d.]+)',
                r'Score:\s*([\d.]+)',
                r'(\d+\.?\d*)\s*(?:pts|points)'
            ]
            for pattern in score_patterns:
                score_match = re.search(pattern, content, re.IGNORECASE)
                if score_match:
                    result.score = float(score_match.group(1))
                    break
            
            # Extract confidence (look for "Confidence: <number>")
            conf_match = re.search(r'Confidence:\s*([\d.]+)', content, re.IGNORECASE)
            if conf_match:
                result.confidence = float(conf_match.group(1))
            else:
                # Default confidence based on score
                if result.score > 70:
                    result.confidence = 80.0
                elif result.score > 40:
                    result.confidence = 60.0
                else:
                    result.confidence = 40.0
            
            # Extract warnings (look for "Warning:" or "⚠")
            warning_matches = re.findall(r'(?:Warning|⚠)[:\s]+(.*?)(?:\n|$)', content, re.IGNORECASE)
            result.warnings = warning_matches
            
        except Exception as e:
            logger.error(f"Error parsing classification log {log_path}: {e}")
        
        return result
    
    @staticmethod
    def load_research_json(file_path: Path) -> Dict[str, Any]:
        """
        Parse research JSON file from sweep analysis.
        
        Args:
            file_path: Path to _research.json file
            
        Returns:
            Dictionary containing research data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Error loading research JSON {file_path}: {e}")
            return {}
    
    @staticmethod
    def load_raw_measurement(txt_path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """
        Parse raw measurement TXT file to extract voltage and current arrays.
        
        Handles multiple formats:
        - Tab-delimited or space-delimited
        - With or without headers
        - 2 columns (voltage, current) or 3+ columns (time, voltage, current)
        
        Args:
            txt_path: Path to measurement TXT file
            
        Returns:
            Tuple of (voltage_array, current_array)
        """
        try:
            # Try to load data with skiprows=1 to handle header
            try:
                data = np.loadtxt(txt_path, skiprows=1)
            except (ValueError, IndexError):
                # If that fails, try without skipping
                data = np.loadtxt(txt_path, skiprows=0)
            
            # Handle different column formats
            if data.ndim == 1:
                # Single column - not useful for I-V
                logger.debug(f"Single column data in {txt_path.name}")
                return np.array([]), np.array([])
            
            if data.shape[1] == 2:
                # Two columns: voltage, current
                voltage = data[:, 0]
                current = data[:, 1]
            elif data.shape[1] >= 3:
                # Three+ columns: likely time, voltage, current
                voltage = data[:, 1]
                current = data[:, 2]
            else:
                logger.debug(f"Unexpected column count in {txt_path.name}: {data.shape[1]}")
                return np.array([]), np.array([])
            
            # Validate data
            if len(voltage) == 0 or len(current) == 0:
                return np.array([]), np.array([])
            
            # Check for invalid values
            if not np.all(np.isfinite(voltage)) or not np.all(np.isfinite(current)):
                # Filter out non-finite values
                valid_mask = np.isfinite(voltage) & np.isfinite(current)
                voltage = voltage[valid_mask]
                current = current[valid_mask]
            
            logger.debug(f"Successfully loaded {len(voltage)} points from {txt_path.name}")
            return voltage, current
            
        except Exception as e:
            logger.warning(f"Error loading raw measurement {txt_path.name}: {e}")
            return np.array([]), np.array([])
    
    @staticmethod
    def load_measurement_from_txt(txt_path: Path) -> Optional[MeasurementData]:
        """
        Create MeasurementData object from TXT file.
        
        Args:
            txt_path: Path to measurement TXT file
            
        Returns:
            MeasurementData object or None if loading fails
        """
        voltage, current = DataLoader.load_raw_measurement(txt_path)
        
        if len(voltage) == 0 or len(current) == 0:
            return None
        
        # Detect measurement type from filename
        filename_lower = txt_path.stem.lower()
        if any(x in filename_lower for x in ['pulse', 'ps', 'ns']):
            meas_type = 'pulse'
        elif any(x in filename_lower for x in ['retention', 'ret']):
            meas_type = 'retention'
        elif any(x in filename_lower for x in ['endurance', 'cycle']):
            meas_type = 'endurance'
        else:
            meas_type = 'iv_sweep'
        
        measurement = MeasurementData(
            file_path=txt_path,
            measurement_type=meas_type,
            voltage=voltage.tolist(),
            current=current.tolist(),
            cycles=1  # TODO: detect cycles
        )
        
        return measurement
    
    @staticmethod
    def _parse_device_id(device_id: str) -> Tuple[str, int]:
        """
        Parse device ID to extract section and device number.
        
        Args:
            device_id: Device ID string (e.g., 'G_1', 'Section_A_5')
            
        Returns:
            Tuple of (section_name, device_number)
        """
        # Split by underscore and extract last part as number
        parts = device_id.split('_')
        
        if len(parts) >= 2:
            try:
                device_num = int(parts[-1])
                section = '_'.join(parts[:-1])
                return section, device_num
            except ValueError:
                pass
        
        # Fallback: use entire string as section, number as 0
        return device_id, 0
    
    @staticmethod
    def _extract_metrics(device: DeviceData) -> MetricsData:
        """
        Extract metrics from device classification and measurement data.
        
        Args:
            device: DeviceData object
            
        Returns:
            MetricsData object with extracted metrics
        """
        metrics = MetricsData()
        
        # Try to get metrics from classification data
        if device.current_classification.feature_scores:
            scores = device.current_classification.feature_scores
            
            # Look for Ron/Roff in feature scores or research data
            if 'ron' in scores:
                metrics.ron = scores['ron']
            if 'roff' in scores:
                metrics.roff = scores['roff']
            if 'on_off_ratio' in scores:
                metrics.on_off_ratio = scores['on_off_ratio']
        
        # Try to get metrics from research data
        if device.research_data:
            research = device.research_data
            metrics.ron = research.get('ron', metrics.ron)
            metrics.roff = research.get('roff', metrics.roff)
            metrics.on_off_ratio = research.get('on_off_ratio', metrics.on_off_ratio)
            metrics.switching_voltage = research.get('switching_voltage', metrics.switching_voltage)
            metrics.hysteresis_area = research.get('hysteresis_area', metrics.hysteresis_area)
        
        # Calculate on_off_ratio if we have ron and roff
        if metrics.ron and metrics.roff and not metrics.on_off_ratio:
            metrics.on_off_ratio = metrics.roff / metrics.ron
        
        return metrics
    
    @staticmethod
    def _identify_best_worst_measurements(device: DeviceData) -> None:
        """
        Identify best and worst performing measurements based on available metrics.
        
        Modifies device in place to set best_measurement and worst_measurement indices.
        
        Args:
            device: DeviceData object
        """
        if len(device.measurements) == 0:
            return
        
        # For now, simply use first and last measurements
        # TODO: Implement proper scoring based on metrics
        device.best_measurement = 0
        device.worst_measurement = len(device.measurements) - 1 if len(device.measurements) > 1 else 0
