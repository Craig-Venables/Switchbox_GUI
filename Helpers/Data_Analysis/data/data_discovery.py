"""
Data discovery module for locating device files across various folder structures.

This module implements a hybrid discovery strategy:
1. Try standard locations first (fast)
2. Fall back to pattern-based scanning if standard locations fail (comprehensive)

This ensures the application works even if folder structures change.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

# Set up logging
logger = logging.getLogger(__name__)


class DataDiscovery:
    """
    Hybrid data discovery for device analysis files.
    
    Combines standard location attempts with pattern-based fallback scanning
    to flexibly locate device tracking files, research JSONs, classification logs,
    and raw measurement data.
    """
    
    @staticmethod
    def discover_sample_structure(sample_path: Path) -> Dict[str, List[Path]]:
        """
        Discover the structure of a sample directory.
        
        Scans the sample folder to find all sections and devices.
        
        Args:
            sample_path: Path to sample directory
            
        Returns:
            Dictionary with keys:
                - 'sections': List of section folder paths
                - 'devices': List of device folder paths
                - 'tracking_files': List of device tracking JSON files
                - 'research_files': List of research JSON files
                - 'classification_logs': List of classification log files
        """
        result = {
            'sections': [],
            'devices': [],
            'tracking_files': [],
            'research_files': [],
            'classification_logs': []
        }
        
        if not sample_path.exists():
            logger.warning(f"Sample path does not exist: {sample_path}")
            return result
        
        # Look for section folders (commonly named 'G', 'Section_A', etc.)
        # Try common patterns
        for item in sample_path.iterdir():
            if item.is_dir():
                # Check if this looks like a section folder (contains numbered device folders)
                device_folders = [d for d in item.iterdir() if d.is_dir() and d.name.isdigit()]
                if device_folders:
                    result['sections'].append(item)
                    result['devices'].extend(device_folders)
        
        # Discover tracking files (in sample_analysis/analysis/device_tracking/)
        tracking_dir = sample_path / 'sample_analysis' / 'analysis' / 'device_tracking'
        if tracking_dir.exists():
            result['tracking_files'] = list(tracking_dir.glob('*_history.json'))
        
        # Discover research files and classification logs in device folders
        for device_folder in result['devices']:
            # Research JSONs in sweep_analysis subfolder
            sweep_analysis_dir = device_folder / 'sweep_analysis'
            if sweep_analysis_dir.exists():
                result['research_files'].extend(sweep_analysis_dir.glob('*_research.json'))
            
            # Classification logs in device folder root
            class_log = device_folder / 'classification_log.txt'
            if class_log.exists():
                result['classification_logs'].append(class_log)
        
        logger.info(f"Discovered sample structure: {len(result['sections'])} sections, "
                   f"{len(result['devices'])} devices, {len(result['tracking_files'])} tracking files")
        
        return result
    
    @staticmethod
    def find_device_tracking_files(sample_path: Path, device_id: Optional[str] = None) -> List[Path]:
        """
        Find device tracking JSON files.
        
        Standard location: {sample}/sample_analysis/analysis/device_tracking/{device_id}_history.json
        Fallback: Recursive scan for *_history.json files
        
        Args:
            sample_path: Path to sample directory
            device_id: Optional device ID to filter (e.g., 'G_1')
            
        Returns:
            List of paths to tracking files
        """
        tracking_files = []
        
        # Try standard location first
        tracking_dir = sample_path / 'sample_analysis' / 'analysis' / 'device_tracking'
        if tracking_dir.exists():
            if device_id:
                specific_file = tracking_dir / f"{device_id}_history.json"
                if specific_file.exists():
                    tracking_files.append(specific_file)
            else:
                tracking_files = list(tracking_dir.glob('*_history.json'))
        
        # Fallback: Pattern-based scan
        if len(tracking_files) == 0:
            tracking_files = DataDiscovery.find_files_by_pattern(
                sample_path, '*_history.json'
            )
            
            # Filter by device_id if specified
            if device_id:
                tracking_files = [f for f in tracking_files if device_id in f.stem]
        
        return tracking_files
    
    @staticmethod
    def find_research_files(device_path: Path) -> List[Path]:
        """
        Find research JSON files for a device.
        
        Standard location: {device_path}/sweep_analysis/*_research.json
        Fallback: Recursive scan in device folder
        
        Args:
            device_path: Path to device directory
            
        Returns:
            List of paths to research JSON files
        """
        research_files = []
        
        # Try standard location
        sweep_analysis_dir = device_path / 'sweep_analysis'
        if sweep_analysis_dir.exists():
            research_files = list(sweep_analysis_dir.glob('*_research.json'))
        
        # Fallback: Scan device folder
        if len(research_files) == 0 and device_path.exists():
            research_files = list(device_path.rglob('*_research.json'))
        
        return research_files
    
    @staticmethod
    def find_classification_logs(device_path: Path) -> Optional[Path]:
        """
        Find classification log file for a device.
        
        Standard location: {device_path}/classification_log.txt
        Also checks: {device_path}/classification_summary.txt
        
        Args:
            device_path: Path to device directory
            
        Returns:
            Path to classification log file, or None if not found
        """
        # Try standard locations
        log_files = [
            device_path / 'classification_log.txt',
            device_path / 'classification_summary.txt'
        ]
        
        for log_file in log_files:
            if log_file.exists():
                return log_file
        
        # Fallback: Search recursively
        found_logs = list(device_path.glob('**/classification*.txt'))
        if found_logs:
            return found_logs[0]
        
        return None
    
    @staticmethod
    def find_raw_data_files(device_path: Path) -> List[Path]:
        """
        Find raw measurement TXT files for a device.
        
        Standard location: {device_path}/*.txt
        Excludes classification logs.
        
        Args:
            device_path: Path to device directory
            
        Returns:
            List of paths to raw measurement TXT files
        """
        if not device_path.exists():
            return []
        
        # Find all TXT files in device folder
        txt_files = list(device_path.glob('*.txt'))
        
        # Exclude classification logs and other non-measurement files
        exclude_patterns = ['classification', 'summary', 'log', 'readme']
        raw_files = [
            f for f in txt_files 
            if not any(pattern in f.stem.lower() for pattern in exclude_patterns)
        ]
        
        return raw_files
    
    @staticmethod
    def find_files_by_pattern(root_path: Path, pattern: str, max_depth: int = 5) -> List[Path]:
        """
        Generic pattern-based file finder with depth limit.
        
        Args:
            root_path: Root directory to search from
            pattern: Glob pattern (e.g., '*.json', '*_history.json')
            max_depth: Maximum recursion depth
            
        Returns:
            List of matching file paths
        """
        matching_files = []
        
        try:
            # Use rglob for recursive search
            # Note: Python's rglob doesn't support depth limit natively,
            # so we filter by path depth
            for file_path in root_path.rglob(pattern):
                # Calculate depth
                try:
                    depth = len(file_path.relative_to(root_path).parts)
                    if depth <= max_depth:
                        matching_files.append(file_path)
                except ValueError:
                    # Skip if path is not relative to root_path
                    continue
        except Exception as e:
            logger.error(f"Error scanning with pattern '{pattern}': {e}")
        
        return matching_files
    
    @staticmethod
    def find_device_folders(sample_path: Path) -> List[Tuple[str, Path]]:
        """
        Find all device folders in a sample and extract device IDs.
        
        Common patterns:
        - {sample}/G/{device_num}/
        - {sample}/Section_{X}/{device_num}/
        
        Args:
            sample_path: Path to sample directory
            
        Returns:
            List of (device_id, device_path) tuples
        """
        devices = []
        
        if not sample_path.exists():
            return devices
        
        # Look for section folders
        for section_folder in sample_path.iterdir():
            if not section_folder.is_dir():
                continue
            
            section_name = section_folder.name
            
            # Look for numbered device folders within sections
            for device_folder in section_folder.iterdir():
                if device_folder.is_dir() and device_folder.name.isdigit():
                    device_num = device_folder.name
                    device_id = f"{section_name}_{device_num}"
                    devices.append((device_id, device_folder))
        
        logger.info(f"Found {len(devices)} device folders in {sample_path.name}")
        return devices
    
    @staticmethod
    def get_sample_name(sample_path: Path) -> str:
        """
        Extract sample name from path.
        
        Args:
            sample_path: Path to sample directory
            
        Returns:
            Sample name (directory basename)
        """
        return sample_path.name
