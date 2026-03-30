"""
Test script to verify ohmic device classification fixes.

This script tests:
1. Ohmic device (linear I-V through origin) is classified as ohmic, not memristive
2. Pinched hysteresis detection doesn't trigger false positives on ohmic devices
3. Classification weights correctly prioritize ohmic classification

Usage:
    python test_ohmic_classification.py
"""

import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from IV_Analysis import IVSweepAnalyzer

def create_ideal_ohmic_device(resistance=1e6, v_max=1.0, num_points=100):
    """Create synthetic ideal ohmic device data (linear I-V through origin)."""
    # Single sweep: 0 → +V → 0 → -V → 0
    voltage = np.concatenate([
        np.linspace(0, v_max, num_points//4),
        np.linspace(v_max, 0, num_points//4),
        np.linspace(0, -v_max, num_points//4),
        np.linspace(-v_max, 0, num_points//4)
    ])
    
    # Perfect ohmic: I = V/R, plus tiny noise
    current = voltage / resistance
    noise = np.random.normal(0, np.max(np.abs(current)) * 0.001, len(current))
    current = current + noise
    
    return voltage, current

def create_noisy_ohmic_device(resistance=1e6, v_max=1.0, num_points=100, noise_level=0.02):
    """Create ohmic device with realistic measurement noise."""
    voltage, current = create_ideal_ohmic_device(resistance, v_max, num_points)
    
    # Add realistic noise (2% of max current)
    noise = np.random.normal(0, np.max(np.abs(current)) * noise_level, len(current))
    current = current + noise
    
    return voltage, current

def test_ohmic_classification():
    """Test that ohmic devices are correctly classified."""
    print("=" * 70)
    print("OHMIC CLASSIFICATION FIX - TEST SUITE")
    print("=" * 70)
    
    # Test 1: Ideal ohmic device
    print("\n[TEST 1] Ideal Ohmic Device (R=1MΩ, minimal noise)")
    print("-" * 70)
    v1, i1 = create_ideal_ohmic_device(resistance=1e6, v_max=1.0)
    
    analyzer1 = IVSweepAnalyzer(analysis_level='full')
    result1 = analyzer1.analyze_sweep(voltage=v1, current=i1, device_name="Ideal_Ohmic")
    
    print(f"\nClassification: {result1['classification']['device_type']}")
    print(f"Confidence: {result1['classification']['confidence']:.2%}")
    print(f"Conduction Mechanism: {result1['classification']['conduction_mechanism']}")
    print(f"\nScoring Breakdown:")
    for device_type, score in result1['classification']['breakdown'].items():
        print(f"  {device_type:15s}: {score:6.1f}")
    
    print(f"\nKey Features:")
    features1 = result1['classification']['features']
    print(f"  linear_iv:           {features1.get('linear_iv')}")
    print(f"  ohmic_behavior:      {features1.get('ohmic_behavior')}")
    print(f"  has_hysteresis:      {features1.get('has_hysteresis')}")
    print(f"  pinched_hysteresis:  {features1.get('pinched_hysteresis')}")
    print(f"  switching_behavior:  {features1.get('switching_behavior')}")
    
    test1_pass = result1['classification']['device_type'] == 'ohmic'
    print(f"\n✓ TEST 1 PASSED" if test1_pass else f"\n✗ TEST 1 FAILED")
    
    # Test 2: Noisy ohmic device (realistic)
    print("\n" + "=" * 70)
    print("[TEST 2] Noisy Ohmic Device (R=1MΩ, 2% noise)")
    print("-" * 70)
    v2, i2 = create_noisy_ohmic_device(resistance=1e6, v_max=1.0, noise_level=0.02)
    
    analyzer2 = IVSweepAnalyzer(analysis_level='full')
    result2 = analyzer2.analyze_sweep(voltage=v2, current=i2, device_name="Noisy_Ohmic")
    
    print(f"\nClassification: {result2['classification']['device_type']}")
    print(f"Confidence: {result2['classification']['confidence']:.2%}")
    print(f"Conduction Mechanism: {result2['classification']['conduction_mechanism']}")
    print(f"\nScoring Breakdown:")
    for device_type, score in result2['classification']['breakdown'].items():
        print(f"  {device_type:15s}: {score:6.1f}")
    
    print(f"\nKey Features:")
    features2 = result2['classification']['features']
    print(f"  linear_iv:           {features2.get('linear_iv')}")
    print(f"  ohmic_behavior:      {features2.get('ohmic_behavior')}")
    print(f"  has_hysteresis:      {features2.get('has_hysteresis')}")
    print(f"  pinched_hysteresis:  {features2.get('pinched_hysteresis')}")
    print(f"  switching_behavior:  {features2.get('switching_behavior')}")
    
    test2_pass = result2['classification']['device_type'] == 'ohmic'
    print(f"\n✓ TEST 2 PASSED" if test2_pass else f"\n✗ TEST 2 FAILED")
    
    # Test 3: High noise ohmic device
    print("\n" + "=" * 70)
    print("[TEST 3] High Noise Ohmic Device (R=1MΩ, 5% noise)")
    print("-" * 70)
    v3, i3 = create_noisy_ohmic_device(resistance=1e6, v_max=1.0, noise_level=0.05)
    
    analyzer3 = IVSweepAnalyzer(analysis_level='full')
    result3 = analyzer3.analyze_sweep(voltage=v3, current=i3, device_name="HighNoise_Ohmic")
    
    print(f"\nClassification: {result3['classification']['device_type']}")
    print(f"Confidence: {result3['classification']['confidence']:.2%}")
    print(f"Conduction Mechanism: {result3['classification']['conduction_mechanism']}")
    print(f"\nScoring Breakdown:")
    for device_type, score in result3['classification']['breakdown'].items():
        print(f"  {device_type:15s}: {score:6.1f}")
    
    print(f"\nKey Features:")
    features3 = result3['classification']['features']
    print(f"  linear_iv:           {features3.get('linear_iv')}")
    print(f"  ohmic_behavior:      {features3.get('ohmic_behavior')}")
    print(f"  has_hysteresis:      {features3.get('has_hysteresis')}")
    print(f"  pinched_hysteresis:  {features3.get('pinched_hysteresis')}")
    print(f"  switching_behavior:  {features3.get('switching_behavior')}")
    
    test3_pass = result3['classification']['device_type'] in ['ohmic', 'uncertain']
    print(f"\n✓ TEST 3 PASSED (ohmic or uncertain accepted)" if test3_pass else f"\n✗ TEST 3 FAILED")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Test 1 (Ideal Ohmic):      {'PASS ✓' if test1_pass else 'FAIL ✗'}")
    print(f"Test 2 (Noisy Ohmic):      {'PASS ✓' if test2_pass else 'FAIL ✗'}")
    print(f"Test 3 (High Noise Ohmic): {'PASS ✓' if test3_pass else 'FAIL ✗'}")
    
    all_passed = test1_pass and test2_pass and test3_pass
    print(f"\nOverall: {'ALL TESTS PASSED ✓✓✓' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 70)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_ohmic_classification()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

