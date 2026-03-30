#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to diagnose the classification issue with 31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5.txt
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Helpers.Analysis import SweepAnalyzer
from Helpers.Analysis.core.sweep_analyzer import read_data_file

def test_file(filepath):
    """Test a single file and show detailed diagnostics."""
    print(f"="*80)
    print(f"Testing file: {filepath}")
    print(f"="*80)
    
    # Read the data
    try:
        result = read_data_file(filepath)
        if len(result) == 3:
            voltage, current, time = result
        else:
            voltage, current = result
            time = None
        
        print(f"Data loaded: {len(voltage)} points")
        print(f"Voltage range: {voltage.min():.3f} to {voltage.max():.3f} V")
        print(f"Current range: {current.min():.3e} to {current.max():.3e} A")
        print()
        
    except Exception as e:
        print(f"ERROR reading file: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Analyze with full diagnostics
    try:
        analyzer = SweepAnalyzer(
            voltage=voltage,
            current=current,
            time=time,
            measurement_type='iv_sweep',
            analysis_level='classification'
        )
        
        print()
        print(f"="*80)
        print(f"ANALYSIS RESULTS:")
        print(f"="*80)
        print(f"Device Type: {analyzer.device_type}")
        print(f"Confidence: {analyzer.classification_confidence:.1%}")
        print(f"Number of loops: {analyzer.num_loops}")
        
        print(f"\nScoring Breakdown:")
        if hasattr(analyzer, 'classification_breakdown'):
            for dtype, score in analyzer.classification_breakdown.items():
                print(f"  {dtype}: {score:.1f}")
        
        print(f"\nFeatures:")
        if hasattr(analyzer, 'classification_features'):
            for feature, value in analyzer.classification_features.items():
                print(f"  {feature}: {value}")
        
    except Exception as e:
        print(f"ERROR during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test the problematic file
    target_file = Path(__file__).parent / "files_for_testing" / "31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5.txt"
    
    if not target_file.exists():
        # Try the -2 variant
        target_file = Path(__file__).parent / "files_for_testing" / "31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5-2.txt"
    
    if target_file.exists():
        test_file(str(target_file))
    else:
        print(f"File not found: {target_file}")
        print("Available files in directory:")
        for f in (Path(__file__).parent / "files_for_testing").glob("*.txt"):
            print(f"  - {f.name}")
