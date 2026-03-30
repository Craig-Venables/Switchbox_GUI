#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test specific files that are showing Unknown classification"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Helpers.Analysis import SweepAnalyzer
from Helpers.Analysis.core.sweep_analyzer import read_data_file

def test_file(filepath):
    """Test a single file and show detailed diagnostics."""
    print(f"\n{'='*80}")
    print(f"Testing: {Path(filepath).name}")
    print(f"{'='*80}\n")
    
    try:
        result = read_data_file(filepath)
        if len(result) == 3:
            voltage, current, time = result
        else:
            voltage, current = result
            time = None
        
        print(f"✓ Data loaded: {len(voltage)} points")
        print(f"  Voltage range: {voltage.min():.3f} to {voltage.max():.3f} V")
        print(f"  Current range: {current.min():.3e} to {current.max():.3e} A\n")
        
    except Exception as e:
        print(f"✗ ERROR reading file: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Analyze with diagnostics
    try:
        analyzer = SweepAnalyzer(
            voltage=voltage,
            current=current,
            time=time,
            measurement_type='iv_sweep',
            analysis_level='classification'
        )
        
        print(f"\n{'='*80}")
        print(f"FINAL RESULTS:")
        print(f"{'='*80}")
        print(f"Device Type: {analyzer.device_type}")
        print(f"Confidence: {analyzer.classification_confidence:.1%}")
        
    except Exception as e:
        print(f"\n✗ ERROR during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dir = Path(__file__).parent / "files_for_testing"
    
    # Test the specific files the user mentioned
    test_files = [
        "31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5.txt",
        "31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5-2.txt",
        "37-FS-3.0v-0.05sv-0.05sd-Py-St_v1-10.02.txt"
    ]
    
    for filename in test_files:
        filepath = test_dir / filename
        if filepath.exists():
            test_file(str(filepath))
        else:
            print(f"\n✗ File not found: {filename}")
