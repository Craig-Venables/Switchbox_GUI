"""
Test script for oscilloscope control and waveform acquisition.

This script verifies the functionality of the Tektronix TBS1000C oscilloscope
controller and manager classes.

Tests include:
- Connection establishment
- Channel configuration
- Trigger setup
- Waveform acquisition
- Automatic measurements
- Error handling

Run this script with: python tests/test_oscilloscope.py

Author: Generated for Switchbox_GUI project
"""

import sys
import os
import time

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C
from Equipment.oscilloscope_manager import OscilloscopeManager


def test_connection():
    """Test basic connection to oscilloscope."""
    print("\n" + "="*60)
    print("TEST 1: Connection Test")
    print("="*60)
    
    # Try to find any Tektronix oscilloscope
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        print(f"Found {len(resources)} VISA resources:")
        for res in resources:
            print(f"  - {res}")
        
        # Look for Tektronix devices
        tek_resources = [r for r in resources if 'TEKTRONIX' in r.upper() or 
                        '0x0699' in r.upper()]
        
        if not tek_resources:
            usb_resources = [r for r in resources if 'USB' in r]
            if usb_resources:
                tek_resources = usb_resources
        
        if not tek_resources:
            print("No Tektronix or USB resources found. Cannot test connection.")
            return False
        
        test_resource = tek_resources[0]
        print(f"\nUsing resource: {test_resource}")
        
        # Test direct connection
        scope = TektronixTBS1000C(resource=test_resource)
        if scope.connect():
            print(f"✓ Successfully connected!")
            print(f"  ID: {scope.idn()}")
            scope.disconnect()
            print("✓ Successfully disconnected!")
            return True
        else:
            print("✗ Connection failed")
            return False
        
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False


def test_oscilloscope_manager():
    """Test OscilloscopeManager auto-detection."""
    print("\n" + "="*60)
    print("TEST 2: Oscilloscope Manager Test")
    print("="*60)
    
    try:
        scope_mgr = OscilloscopeManager(auto_detect=True)
        
        if scope_mgr.is_connected():
            print("✓ Manager successfully connected to oscilloscope")
            info = scope_mgr.get_scope_info()
            print(f"  Type: {info.get('type', 'Unknown')}")
            print(f"  Address: {info.get('address', 'Unknown')}")
            scope_mgr.close()
            return True
        else:
            print("✗ Manager could not connect (no oscilloscope detected)")
            return False
            
    except Exception as e:
        print(f"✗ Manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_channel_configuration():
    """Test channel configuration commands."""
    print("\n" + "="*60)
    print("TEST 3: Channel Configuration Test")
    print("="*60)
    
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        tek_resources = [r for r in resources if 'TEKTRONIX' in r.upper() or 
                        '0x0699' in r.upper()]
        if not tek_resources:
            usb_resources = [r for r in resources if 'USB' in r]
            if usb_resources:
                tek_resources = usb_resources
        
        if not tek_resources:
            print("No oscilloscope found. Skipping configuration test.")
            return False
        
        scope = TektronixTBS1000C(resource=tek_resources[0])
        if not scope.connect():
            print("✗ Could not connect for configuration test")
            return False
        
        print("✓ Connected for configuration test")
        
        # Test channel enable
        scope.channel_display(1, True)
        scope.channel_display(2, False)
        print("✓ Set channel display")
        
        # Test scale settings
        scope.set_channel_scale(1, 1.0)  # 1V/div
        scale = scope.get_channel_scale(1)
        print(f"✓ Set channel scale: {scale:.3f} V/div")
        
        # Test coupling
        scope.set_channel_coupling(1, 'DC')
        print("✓ Set channel coupling to DC")
        
        # Test offset
        scope.set_channel_offset(1, 0.0)
        offset = scope.get_channel_offset(1)
        print(f"✓ Set channel offset: {offset:.3f} V")
        
        scope.disconnect()
        print("✓ Configuration test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_timebase_configuration():
    """Test timebase configuration."""
    print("\n" + "="*60)
    print("TEST 4: Timebase Configuration Test")
    print("="*60)
    
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        tek_resources = [r for r in resources if 'TEKTRONIX' in r.upper() or 
                        '0x0699' in r.upper()]
        if not tek_resources:
            usb_resources = [r for r in resources if 'USB' in r]
            if usb_resources:
                tek_resources = usb_resources
        
        if not tek_resources:
            print("No oscilloscope found. Skipping timebase test.")
            return False
        
        scope = TektronixTBS1000C(resource=tek_resources[0])
        if not scope.connect():
            print("✗ Could not connect for timebase test")
            return False
        
        # Test timebase scale
        scope.set_timebase_scale(1e-3)  # 1 ms/div
        scale = scope.get_timebase_scale()
        print(f"✓ Set timebase scale: {scale:.6f} s/div")
        
        # Test timebase position
        scope.set_timebase_position(0.0)
        pos = scope.get_timebase_position()
        print(f"✓ Set timebase position: {pos:.6f} s")
        
        scope.disconnect()
        print("✓ Timebase test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Timebase test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trigger_configuration():
    """Test trigger configuration."""
    print("\n" + "="*60)
    print("TEST 5: Trigger Configuration Test")
    print("="*60)
    
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        tek_resources = [r for r in resources if 'TEKTRONIX' in r.upper() or 
                        '0x0699' in r.upper()]
        if not tek_resources:
            usb_resources = [r for r in resources if 'USB' in r]
            if usb_resources:
                tek_resources = usb_resources
        
        if not tek_resources:
            print("No oscilloscope found. Skipping trigger test.")
            return False
        
        scope = TektronixTBS1000C(resource=tek_resources[0])
        if not scope.connect():
            print("✗ Could not connect for trigger test")
            return False
        
        # Test trigger mode
        scope.set_trigger_mode('AUTO')
        mode = scope.get_trigger_mode()
        print(f"✓ Set trigger mode: {mode}")
        
        # Test trigger source
        scope.set_trigger_source('CH1')
        print("✓ Set trigger source to CH1")
        
        # Test trigger level
        scope.set_trigger_level(0.0)
        level = scope.get_trigger_level()
        print(f"✓ Set trigger level: {level:.3f} V")
        
        # Test trigger slope
        scope.set_trigger_slope('RISING')
        print("✓ Set trigger slope to RISING")
        
        scope.disconnect()
        print("✓ Trigger test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Trigger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_waveform_acquisition():
    """Test waveform data acquisition."""
    print("\n" + "="*60)
    print("TEST 6: Waveform Acquisition Test")
    print("="*60)
    
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        tek_resources = [r for r in resources if 'TEKTRONIX' in r.upper() or 
                        '0x0699' in r.upper()]
        if not tek_resources:
            usb_resources = [r for r in resources if 'USB' in r]
            if usb_resources:
                tek_resources = usb_resources
        
        if not tek_resources:
            print("No oscilloscope found. Skipping acquisition test.")
            return False
        
        scope = TektronixTBS1000C(resource=tek_resources[0])
        if not scope.connect():
            print("✗ Could not connect for acquisition test")
            return False
        
        # Configure for acquisition
        scope.channel_display(1, True)
        scope.set_channel_coupling(1, 'DC')
        scope.set_trigger_mode('AUTO')
        scope.set_trigger_source('CH1')
        
        # Run autoscale to get a good signal
        print("Running autoscale...")
        scope.autoscale()
        time.sleep(2)
        
        # Acquire waveform
        print("Acquiring waveform...")
        time_array, voltage_array = scope.acquire_waveform(1, format='ASCII')
        
        if len(voltage_array) > 0:
            print(f"✓ Successfully acquired {len(voltage_array)} data points")
            print(f"  Time range: {time_array.min():.6f} to {time_array.max():.6f} s")
            print(f"  Voltage range: {voltage_array.min():.3f} to {voltage_array.max():.3f} V")
            print(f"  Mean voltage: {voltage_array.mean():.3f} V")
            print(f"  Std deviation: {voltage_array.std():.3f} V")
        else:
            print("⚠ Acquired waveform but got 0 data points")
        
        scope.disconnect()
        print("✓ Acquisition test completed")
        return True
        
    except Exception as e:
        print(f"✗ Acquisition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_measurements():
    """Test automatic measurements."""
    print("\n" + "="*60)
    print("TEST 7: Automatic Measurements Test")
    print("="*60)
    
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        tek_resources = [r for r in resources if 'TEKTRONIX' in r.upper() or 
                        '0x0699' in r.upper()]
        if not tek_resources:
            usb_resources = [r for r in resources if 'USB' in r]
            if usb_resources:
                tek_resources = usb_resources
        
        if not tek_resources:
            print("No oscilloscope found. Skipping measurements test.")
            return False
        
        scope = TektronixTBS1000C(resource=tek_resources[0])
        if not scope.connect():
            print("✗ Could not connect for measurements test")
            return False
        
        # Configure
        scope.channel_display(1, True)
        scope.set_channel_coupling(1, 'DC')
        scope.set_trigger_mode('AUTO')
        scope.set_trigger_source('CH1')
        scope.autoscale()
        time.sleep(2)
        
        # Configure measurements
        print("Configuring measurements...")
        scope.configure_measurement('AMPL', channel=1, measurement_number=1)
        scope.configure_measurement('FREQ', channel=1, measurement_number=2)
        
        time.sleep(1)
        
        # Read measurements
        try:
            amplitude = scope.read_measurement(1)
            print(f"✓ Amplitude: {amplitude:.3f} V")
        except Exception as e:
            print(f"⚠ Could not read amplitude: {e}")
        
        try:
            frequency = scope.read_measurement(2)
            print(f"✓ Frequency: {frequency:.3f} Hz")
        except Exception as e:
            print(f"⚠ Could not read frequency: {e}")
        
        scope.disconnect()
        print("✓ Measurements test completed")
        return True
        
    except Exception as e:
        print(f"✗ Measurements test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling for invalid operations."""
    print("\n" + "="*60)
    print("TEST 8: Error Handling Test")
    print("="*60)
    
    try:
        # Test without connection
        scope = TektronixTBS1000C()
        try:
            scope.write("*IDN?")
            print("✗ Should have raised RuntimeError for unconnected scope")
            return False
        except RuntimeError:
            print("✓ Correctly raises RuntimeError when not connected")
        
        # Test invalid channel
        try:
            scope.channel_display(3, True)
            print("✗ Should have raised ValueError for invalid channel")
            return False
        except ValueError:
            print("✓ Correctly raises ValueError for invalid channel")
        
        # Test invalid coupling
        try:
            scope.set_channel_coupling(1, 'INVALID')
            print("✗ Should have raised ValueError for invalid coupling")
            return False
        except ValueError:
            print("✓ Correctly raises ValueError for invalid coupling")
        
        print("✓ Error handling test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("OSCILLOSCOPE TEST SUITE")
    print("="*60)
    print("\nThis script tests the Tektronix TBS1000C oscilloscope controller.")
    print("Make sure an oscilloscope is connected via USB before running.\n")
    
    results = {}
    
    # Run tests
    results['connection'] = test_connection()
    results['manager'] = test_oscilloscope_manager()
    results['error_handling'] = test_error_handling()
    
    # Only run hardware tests if connection works
    if results['connection']:
        results['channel_config'] = test_channel_configuration()
        results['timebase'] = test_timebase_configuration()
        results['trigger'] = test_trigger_configuration()
        results['waveform'] = test_waveform_acquisition()
        results['measurements'] = test_measurements()
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<50} {status}")
    
    print("="*60)
    print(f"Total: {passed}/{total} tests passed")
    print("="*60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

