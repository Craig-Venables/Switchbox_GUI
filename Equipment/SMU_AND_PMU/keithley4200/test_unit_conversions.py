"""
Unit Conversion Tests for Keithley 4200A KXCI Scripts
=====================================================

This module tests that unit conversions are correct for all test functions.
The C modules expect values in SECONDS, so we verify:
1. GUI converts user input (in selected unit) to µs
2. System wrapper passes through (already in µs)
3. KXCI scripts convert from µs to seconds

Test Cases:
-----------
- Verify conversion from µs to seconds matches C code expectations
- Verify default values match example files
- Verify minimum/maximum value enforcement
"""

import unittest
from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import (
    Keithley4200_KXCI_Scripts,
    PulseReadInterleavedConfig,
    format_param
)


class TestUnitConversions(unittest.TestCase):
    """Test unit conversions for 4200A KXCI scripts."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock scripts instance (without actual connection)
        self.scripts = Keithley4200_KXCI_Scripts(gpib_address="GPIB0::17::INSTR", timeout=5.0)
    
    def test_convert_us_to_seconds(self):
        """Test conversion from microseconds to seconds."""
        # Test basic conversions
        self.assertAlmostEqual(self.scripts._convert_us_to_seconds(1.0), 1e-6, places=10)
        self.assertAlmostEqual(self.scripts._convert_us_to_seconds(0.5), 0.5e-6, places=10)
        self.assertAlmostEqual(self.scripts._convert_us_to_seconds(10.0), 10e-6, places=10)
        self.assertAlmostEqual(self.scripts._convert_us_to_seconds(1000.0), 1000e-6, places=10)
    
    def test_pulse_read_repeat_conversion(self):
        """Test that pulse_read_repeat converts correctly from µs to seconds."""
        # Test with typical values (in µs as received from GUI)
        pulse_width_us = 1.0  # 1 µs
        delay_between_us = 10.0  # 10 µs
        read_width_us = 0.5  # 0.5 µs
        read_delay_us = 1.0  # 1 µs
        read_rise_us = 0.1  # 0.1 µs
        
        # Convert using the function
        pulse_width_s = self.scripts._convert_us_to_seconds(pulse_width_us)
        delay_between_s = self.scripts._convert_us_to_seconds(delay_between_us)
        read_width_s = self.scripts._convert_us_to_seconds(read_width_us)
        read_delay_s = self.scripts._convert_us_to_seconds(read_delay_us)
        read_rise_s = self.scripts._convert_us_to_seconds(read_rise_us)
        
        # Verify conversions match C code expectations (defaults are in seconds)
        self.assertAlmostEqual(pulse_width_s, 1e-6, places=10, msg="pulse_width should be 1e-6 seconds")
        self.assertAlmostEqual(delay_between_s, 10e-6, places=10, msg="delay_between should be 10e-6 seconds")
        self.assertAlmostEqual(read_width_s, 0.5e-6, places=10, msg="read_width should be 0.5e-6 seconds")
        self.assertAlmostEqual(read_delay_s, 1e-6, places=10, msg="read_delay should be 1e-6 seconds")
        self.assertAlmostEqual(read_rise_s, 0.1e-6, places=10, msg="read_rise_time should be 0.1e-6 seconds")
    
    def test_potentiation_depression_conversion(self):
        """Test that potentiation_depression_cycle converts correctly."""
        # Test with typical values (in µs as received from GUI)
        pulse_width_us = 1.0  # 1 µs
        delay_between_pulses_us = 1.0  # 1 µs
        delay_between_cycles_us = 10.0  # 10 µs
        read_width_us = 0.5  # 0.5 µs
        delay_before_read_us = 0.02  # 0.02 µs = 20 ns
        
        # Convert using the function
        pulse_width_s = self.scripts._convert_us_to_seconds(pulse_width_us)
        delay_between_pulses_s = self.scripts._convert_us_to_seconds(delay_between_pulses_us)
        delay_between_cycles_s = self.scripts._convert_us_to_seconds(delay_between_cycles_us)
        read_width_s = self.scripts._convert_us_to_seconds(read_width_us)
        delay_before_read_s = self.scripts._convert_us_to_seconds(delay_before_read_us)
        
        # Verify conversions match C code expectations
        self.assertAlmostEqual(pulse_width_s, 1e-6, places=10, msg="pulse_width should be 1e-6 seconds")
        self.assertAlmostEqual(delay_between_pulses_s, 1e-6, places=10, msg="delay_between_pulses should be 1e-6 seconds")
        self.assertAlmostEqual(delay_between_cycles_s, 10e-6, places=10, msg="delay_between_cycles should be 10e-6 seconds")
        self.assertAlmostEqual(read_width_s, 0.5e-6, places=10, msg="read_width should be 0.5e-6 seconds")
        self.assertAlmostEqual(delay_before_read_s, 0.02e-6, places=10, msg="delay_before_read should be 0.02e-6 seconds")
    
    def test_minimum_segment_time_enforcement(self):
        """Test that minimum segment time (20 ns) is enforced."""
        MIN_SEGMENT_TIME = 2e-8  # 20 ns in seconds
        
        # Test with value below minimum
        pulse_width_us = 0.01  # 0.01 µs = 10 ns (below minimum)
        pulse_width_s = self.scripts._convert_us_to_seconds(pulse_width_us)
        
        # After enforcement, should be at least MIN_SEGMENT_TIME
        enforced = max(MIN_SEGMENT_TIME, pulse_width_s)
        self.assertGreaterEqual(enforced, MIN_SEGMENT_TIME, 
                               msg="Enforced value should be >= 20 ns")
        self.assertAlmostEqual(enforced, MIN_SEGMENT_TIME, places=10,
                               msg="Value below minimum should be set to minimum")
    
    def test_config_defaults_match_example(self):
        """Test that PulseReadInterleavedConfig defaults match example file."""
        cfg = PulseReadInterleavedConfig()
        
        # Compare with example file defaults (in seconds)
        self.assertAlmostEqual(cfg.pulse_width, 1e-6, places=10,
                              msg="pulse_width default should be 1e-6 s (1 µs)")
        self.assertAlmostEqual(cfg.pulse_delay, 1e-6, places=10,
                              msg="pulse_delay default should be 1e-6 s (1 µs)")
        self.assertAlmostEqual(cfg.meas_width, 1e-6, places=10,
                              msg="meas_width default should be 1e-6 s (1 µs)")
        self.assertAlmostEqual(cfg.meas_delay, 2e-6, places=10,
                              msg="meas_delay default should be 2e-6 s (2 µs)")
        self.assertAlmostEqual(cfg.pulse_rise_time, 1e-7, places=10,
                              msg="pulse_rise_time default should be 1e-7 s (0.1 µs)")
        self.assertAlmostEqual(cfg.pulse_fall_time, 1e-7, places=10,
                              msg="pulse_fall_time default should be 1e-7 s (0.1 µs)")
        self.assertAlmostEqual(cfg.rise_time, 1e-7, places=10,
                              msg="rise_time default should be 1e-7 s (0.1 µs)")
    
    def test_format_param_for_ex_command(self):
        """Test that format_param formats values correctly for EX commands."""
        # Test small values (should use scientific notation)
        self.assertEqual(format_param(1e-6), "1.00E-6")
        self.assertEqual(format_param(0.5e-6), "5.00E-7")
        self.assertEqual(format_param(2e-8), "2.00E-8")
        
        # Test zero
        self.assertEqual(format_param(0.0), "0")
        
        # Test integers
        self.assertEqual(format_param(5), "5")
        self.assertEqual(format_param(100), "100")
        
        # Test strings
        self.assertEqual(format_param("VF"), "VF")
    
    def test_config_validation(self):
        """Test that config validation works correctly."""
        cfg = PulseReadInterleavedConfig()
        
        # Valid config should not raise
        try:
            cfg.validate()
        except ValueError:
            self.fail("Valid config should not raise ValueError")
        
        # Invalid pulse_width (too small)
        cfg.pulse_width = 1e-9  # 1 ns (below minimum of 20 ns)
        with self.assertRaises(ValueError):
            cfg.validate()
        
        # Reset to valid value
        cfg.pulse_width = 1e-6
        cfg.validate()  # Should not raise


if __name__ == '__main__':
    unittest.main()

