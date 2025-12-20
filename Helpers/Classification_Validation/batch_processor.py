"""
Batch Processor - Process multiple IV files and run classification.
"""

import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Callable
import re

# Import analysis function
try:
    from Helpers.IV_Analysis import quick_analyze
    from Helpers.IV_Analysis.single_file_metrics import read_data_file
except ImportError:
    print("[BATCH] Warning: Could not import analysis functions")
    quick_analyze = None
    read_data_file = None


class BatchProcessor:
    """Process multiple IV files and run classification analysis."""
    
    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        """
        Initialize batch processor.
        
        Args:
            custom_weights: Optional custom scoring weights to use
        """
        self.custom_weights = custom_weights
        self.processed_files: List[Dict] = []
    
    def process_directory(
        self, 
        directory: str, 
        recursive: bool = True,
        pattern: str = "*.txt",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict]:
        """
        Process all matching files in a directory.
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories
            pattern: File pattern to match (default: "*.txt")
            progress_callback: Optional callback(processed, total, current_file)
            
        Returns:
            List of analysis results, each with keys:
            - 'file_path': str
            - 'device_id': str
            - 'analysis': dict (from quick_analyze)
            - 'error': str (if processing failed)
        """
        directory = Path(directory)
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        # Find all matching files
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))
        
        # Filter out analysis files (they're not raw IV data)
        files = [f for f in files if not f.name.endswith('_analysis.txt')]
        
        if not files:
            print(f"[BATCH] No files found matching {pattern} in {directory}")
            return []
        
        print(f"[BATCH] Found {len(files)} files to process")
        
        results = []
        for idx, file_path in enumerate(files, 1):
            if progress_callback:
                progress_callback(idx, len(files), str(file_path))
            
            try:
                result = self.process_file(str(file_path))
                if result:
                    results.append(result)
            except Exception as e:
                print(f"[BATCH] Error processing {file_path}: {e}")
                # Still add result with error
                device_id = self._extract_device_id(str(file_path))
                results.append({
                    'file_path': str(file_path),
                    'device_id': device_id,
                    'analysis': None,
                    'error': str(e)
                })
        
        self.processed_files = results
        print(f"[BATCH] Processed {len(results)} files ({len([r for r in results if r.get('analysis')])} successful)")
        return results
    
    def process_file(self, filepath: str) -> Optional[Dict]:
        """
        Process a single IV file.
        
        Args:
            filepath: Path to IV data file
            
        Returns:
            Dictionary with:
            - 'file_path': str
            - 'device_id': str
            - 'analysis': dict (from quick_analyze)
            - 'error': str (if failed)
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Extract device ID from filename
        device_id = self._extract_device_id(filepath)
        
        # Print which file we're processing
        print(f"\n{'='*80}")
        print(f"[BATCH] Processing: {os.path.basename(filepath)}")
        print(f"[BATCH] Device ID: {device_id}")
        print(f"{'='*80}")
        
        # Read data from file
        try:
            if read_data_file:
                result = read_data_file(filepath)
                if len(result) == 3:
                    voltage, current, time = result
                else:
                    voltage, current = result
                    time = None
            else:
                # Fallback: use numpy directly
                data = np.loadtxt(filepath, skiprows=1)
                voltage = data[:, 0]
                current = data[:, 1]
                time = data[:, 2] if data.shape[1] > 2 else None
        except Exception as e:
            return {
                'file_path': filepath,
                'device_id': device_id,
                'analysis': None,
                'error': f"Failed to read file: {e}"
            }
        
        # Validate data
        if len(voltage) == 0 or len(current) == 0:
            return {
                'file_path': filepath,
                'device_id': device_id,
                'analysis': None,
                'error': "Empty data arrays"
            }
        
        if len(voltage) != len(current):
            return {
                'file_path': filepath,
                'device_id': device_id,
                'analysis': None,
                'error': f"Array length mismatch: V={len(voltage)}, I={len(current)}"
            }
        
        # Run analysis
        try:
            if quick_analyze is None:
                return {
                    'file_path': filepath,
                    'device_id': device_id,
                    'analysis': None,
                    'error': "Analysis function not available"
                }
            
            # Build metadata
            metadata = {
                'device_name': device_id,
                'file_path': filepath
            }
            
            # Run analysis with custom weights if provided
            analysis_result = quick_analyze(
                voltage=voltage,
                current=current,
                time=time,
                metadata=metadata,
                analysis_level='classification',  # Use classification level for speed
                custom_weights=self.custom_weights,  # Pass custom weights directly
                device_name=device_id  # Pass device_name for diagnostic output
            )
            
            return {
                'file_path': filepath,
                'device_id': device_id,
                'analysis': analysis_result,
                'error': None
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'file_path': filepath,
                'device_id': device_id,
                'analysis': None,
                'error': f"Analysis failed: {e}"
            }
    
    def _extract_device_id(self, filepath: str) -> str:
        """
        Extract device ID from filepath.
        
        Tries patterns like:
        - {sample}_{section}_{device}-*.txt
        - {sample}_{section}_{device}.txt
        - Uses filename without extension as fallback
        """
        filename = Path(filepath).stem  # Without extension
        
        # Try to match pattern: sample_letter_number or sample_letter-number
        # e.g., "test_sample_A_1-sweep" -> "test_sample_A_1"
        patterns = [
            r'^(.+_[A-Z]_\d+)',  # sample_A_1
            r'^(.+_[A-Z]-\d+)',  # sample_A-1
            r'^(.+?)_([A-Z])_?(\d+)',  # flexible
        ]
        
        for pattern in patterns:
            match = re.match(pattern, filename)
            if match:
                if len(match.groups()) == 1:
                    return match.group(1)
                else:
                    # Reconstruct: sample_letter_number
                    parts = match.groups()
                    if len(parts) >= 3:
                        return f"{parts[0]}_{parts[1]}_{parts[2]}"
                    return "_".join(parts)
        
        # Fallback: use filename
        return filename
    
    def _apply_custom_weights(self, analysis_result: Dict, custom_weights: Dict[str, float]) -> Dict:
        """
        Apply custom weights to recalculate memristivity score.
        
        This is a post-processing step that recalculates the score using custom weights.
        """
        if 'classification' not in analysis_result:
            return analysis_result
        
        classification = analysis_result['classification']
        breakdown = classification.get('memristivity_breakdown', {})
        
        if not breakdown:
            return analysis_result
        
        # Recalculate score with custom weights
        # Scale each component by the ratio of new_weight / old_weight
        default_weights = {
            'pinched_hysteresis': 30.0,
            'hysteresis_quality': 20.0,
            'switching_behavior': 20.0,
            'memory_window': 15.0,  # Note: breakdown uses 'memory_window'
            'nonlinearity': 10.0,
            'polarity_dependence': 5.0
        }
        
        new_score = 0.0
        new_breakdown = {}
        
        for feature, old_weight in default_weights.items():
            old_score = breakdown.get(feature, 0.0)
            new_weight = custom_weights.get(feature, old_weight)
            
            # Scale the score proportionally
            if old_weight > 0:
                scaled_score = old_score * (new_weight / old_weight)
            else:
                scaled_score = 0.0
            
            new_breakdown[feature] = scaled_score
            new_score += scaled_score
        
        # Update classification
        classification['memristivity_score'] = round(new_score, 1)
        classification['memristivity_breakdown'] = new_breakdown
        
        # Re-determine device type based on new score and thresholds
        # (This would ideally use custom thresholds too, but for now use default logic)
        if new_score >= 60:
            classification['device_type'] = 'memristive'
        elif new_score < 20:
            classification['device_type'] = 'ohmic'
        else:
            # Keep existing classification or use score-based logic
            pass
        
        return analysis_result
    
    def get_processed_files(self) -> List[Dict]:
        """Get list of all processed files."""
        return self.processed_files.copy()
    
    def clear(self) -> None:
        """Clear processed files list."""
        self.processed_files = []
