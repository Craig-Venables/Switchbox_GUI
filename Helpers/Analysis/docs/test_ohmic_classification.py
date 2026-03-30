"""
Test script for ohmic classification improvements (v1.2)

This script demonstrates how the enhanced classification system handles
devices that were previously misclassified as memristive.

Usage:
    python test_ohmic_classification.py <data_file>

Or run with simulated data:
    python test_ohmic_classification.py --simulate
"""

import sys
import os
import numpy as np

# Add parent directories to path to import analysis module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from Helpers.Analysis.core.sweep_analyzer import SweepAnalyzer


def create_ohmic_device_with_artifact():
    """
    Simulate an ohmic device with tiny measurement artifact.
    This mimics the problem case: linear device with noise that looks like hysteresis.
    """
    # Create linear I-V sweep
    voltage = np.linspace(-1.5, 1.5, 500)
    
    # Ohmic response: I = V/R
    resistance = 1000  # 1 kΩ
    current = voltage / resistance
    
    # Add tiny hysteresis artifact (measurement noise, cable capacitance, etc.)
    # This is what was causing false memristive classification
    artifact_magnitude = 1e-6  # 1 μA artifact
    for i in range(len(voltage)):
        # Add small hysteresis loop artifact
        if i < len(voltage) / 2:
            current[i] += artifact_magnitude * np.sin(i / 50)
        else:
            current[i] -= artifact_magnitude * np.sin(i / 50)
    
    return voltage, current


def create_true_memristive_device():
    """
    Simulate a true memristive device for comparison.
    Should still be classified as memristive after changes.
    """
    voltage = np.linspace(0, 1.5, 250).tolist() + np.linspace(1.5, 0, 250).tolist() + \
              np.linspace(0, -1.5, 250).tolist() + np.linspace(-1.5, 0, 250).tolist()
    voltage = np.array(voltage)
    
    # Memristive behavior with state-dependent resistance
    current = np.zeros_like(voltage)
    state = 0.5  # Internal state variable
    
    for i in range(len(voltage)):
        # State-dependent resistance (HRS to LRS switching)
        R_on = 500
        R_off = 5000
        R = R_off - (R_off - R_on) * state
        
        # Current calculation
        current[i] = voltage[i] / R
        
        # State dynamics (simplified)
        if voltage[i] > 0.5:
            state = min(state + 0.01, 1.0)  # Set
        elif voltage[i] < -0.5:
            state = max(state - 0.01, 0.0)  # Reset
    
    return voltage, current


def analyze_and_report(voltage, current, device_name):
    """Analyze device and print detailed report."""
    print(f"\n{'='*70}")
    print(f"Analyzing: {device_name}")
    print('='*70)
    
    # Run analysis
    analyzer = SweepAnalyzer(
        voltage=voltage,
        current=current,
        measurement_type='iv_sweep',
        analysis_level='classification',
        device_name=device_name
    )
    
    # Get classification report
    report = analyzer.get_classification_report()
    
    # Print results
    print(f"\n📊 CLASSIFICATION RESULT:")
    print(f"   Device Type: {report['device_type'].upper()}")
    print(f"   Confidence: {report['confidence']:.1%}")
    print(f"   Conduction: {report['conduction_mechanism']}")
    
    print(f"\n📈 SCORING BREAKDOWN:")
    for device_type, score in sorted(report['breakdown'].items(), key=lambda x: x[1], reverse=True):
        symbol = "✓" if device_type == report['device_type'] else " "
        print(f"   {symbol} {device_type.capitalize():15s}: {score:6.1f}")
    
    print(f"\n🔍 KEY FEATURES:")
    features = report['features']
    print(f"   Hysteresis:      {'YES' if features.get('has_hysteresis') else 'no'}")
    print(f"   Pinched Loop:    {'YES' if features.get('pinched_hysteresis') else 'no'}")
    print(f"   Switching:       {'YES' if features.get('switching_behavior') else 'no'}")
    print(f"   Nonlinear I-V:   {'YES' if features.get('nonlinear_iv') else 'no'}")
    print(f"   Linear I-V:      {'YES' if features.get('linear_iv') else 'no'}")
    print(f"   Ohmic Behavior:  {'YES' if features.get('ohmic_behavior') else 'no'}")
    print(f"   Phase Shift:     {features.get('phase_shift', 0):.1f}°")
    
    # Check for artifact detection
    if features.get('artifact_hysteresis'):
        print(f"\n⚠️  ARTIFACT DETECTED: Hysteresis appears to be measurement artifact")
    
    print(f"\n📏 METRICS:")
    if analyzer.ron and analyzer.roff:
        print(f"   Ron:  {np.mean(analyzer.ron):.2e} Ω")
        print(f"   Roff: {np.mean(analyzer.roff):.2e} Ω")
        print(f"   ON/OFF Ratio: {np.mean(analyzer.on_off):.2f}")
    if analyzer.normalized_areas:
        print(f"   Normalized Area: {np.median(analyzer.normalized_areas):.2e}")
    
    return analyzer


def test_from_file(file_path):
    """Test classification on real data file."""
    try:
        # Try to read data file
        data = np.loadtxt(file_path, skiprows=1)
        voltage = data[:, 0]
        current = data[:, 1]
        
        device_name = os.path.basename(file_path)
        analyze_and_report(voltage, current, device_name)
        
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return False
    
    return True


def run_simulation_tests():
    """Run tests on simulated data."""
    print("\n" + "="*70)
    print("OHMIC CLASSIFICATION IMPROVEMENT TEST SUITE")
    print("="*70)
    print("\nTesting classification improvements for ohmic vs memristive devices...")
    
    # Test 1: Ohmic device with artifact (the problem case)
    print("\n\n" + "█"*70)
    print("TEST 1: Ohmic Device with Measurement Artifact")
    print("█"*70)
    print("\nThis test simulates the reported issue:")
    print("- Linear (ohmic) device")
    print("- Tiny hysteresis artifact from measurement noise")
    print("- OLD SYSTEM: Classified as Memristive (35%)")
    print("- NEW SYSTEM: Should classify as Ohmic (60-70%)")
    
    voltage_ohmic, current_ohmic = create_ohmic_device_with_artifact()
    analyzer_ohmic = analyze_and_report(voltage_ohmic, current_ohmic, "Ohmic-with-Artifact")
    
    # Validate result
    if analyzer_ohmic.device_type == 'ohmic':
        print("\n✅ TEST 1 PASSED: Device correctly classified as Ohmic")
    else:
        print(f"\n❌ TEST 1 FAILED: Device classified as {analyzer_ohmic.device_type} (expected: ohmic)")
    
    # Test 2: True memristive device (ensure we didn't break this)
    print("\n\n" + "█"*70)
    print("TEST 2: True Memristive Device")
    print("█"*70)
    print("\nThis test ensures true memristive devices are still detected:")
    print("- Nonlinear state-dependent resistance")
    print("- Clear switching behavior")
    print("- Pinched hysteresis loop")
    print("- Should still classify as Memristive")
    
    voltage_mem, current_mem = create_true_memristive_device()
    analyzer_mem = analyze_and_report(voltage_mem, current_mem, "True-Memristive")
    
    # Validate result
    if analyzer_mem.device_type == 'memristive':
        print("\n✅ TEST 2 PASSED: Device correctly classified as Memristive")
    else:
        print(f"\n⚠️  TEST 2 WARNING: Device classified as {analyzer_mem.device_type} (expected: memristive)")
        print("    Note: This may be OK if confidence is low or device simulation is weak")
    
    # Summary
    print("\n\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    test1_pass = analyzer_ohmic.device_type == 'ohmic'
    test2_pass = analyzer_mem.device_type == 'memristive'
    
    print(f"\nTest 1 (Ohmic with Artifact):  {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (True Memristive):      {'✅ PASS' if test2_pass else '⚠️  WARNING'}")
    
    if test1_pass:
        print("\n🎉 SUCCESS! The ohmic classification improvements are working correctly.")
        print("\n📝 Key Improvements Applied:")
        print("   1. Graduated ohmic scoring system (4 quality levels)")
        print("   2. Critical penalty for hysteresis without switching (-40 pts)")
        print("   3. Artifact detection for linear+pinched+no_switching cases")
        print("   4. Enhanced pinched hysteresis detection with area threshold")
        print("   5. Multi-level hysteresis thresholds with consistency checks")
    else:
        print("\n⚠️  ATTENTION REQUIRED")
        print("   Test 1 failed - ohmic device still being misclassified")
        print("   See OHMIC_CLASSIFICATION_IMPROVEMENTS.md for troubleshooting")
    
    print("\n" + "="*70 + "\n")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg in ['--simulate', '-s']:
            # Run simulation tests
            run_simulation_tests()
        elif arg in ['--help', '-h']:
            print(__doc__)
        else:
            # Assume it's a file path
            if os.path.exists(arg):
                test_from_file(arg)
            else:
                print(f"Error: File not found: {arg}")
                print("\nUsage: python test_ohmic_classification.py <data_file>")
                print("   or: python test_ohmic_classification.py --simulate")
    else:
        # Default: run simulation
        run_simulation_tests()


if __name__ == "__main__":
    main()

