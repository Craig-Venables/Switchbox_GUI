"""
Test script for CameraManager class

This script tests the CameraManager class to ensure it properly initializes
and manages camera instances according to the Equipment module pattern.

Purpose:
    Verify that the camera manager works correctly with configuration dictionaries
    and provides a stable interface for camera operations.

Usage:
    Run this script to test camera manager functionality.
"""

from __future__ import annotations

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Equipment.camera_manager import CameraManager


def test_manager_initialization():
    """Test basic manager initialization."""
    print("Testing manager initialization...")
    
    try:
        mgr = CameraManager(
            camera_type='Thorlabs',
            mode='server',
            camera_index=0,
            port=8491
        )
        
        assert mgr.camera_type == 'Thorlabs', "Camera type should be 'Thorlabs'"
        assert mgr.mode == 'server', "Mode should be 'server'"
        assert mgr.instrument is not None, "Instrument should be initialized"
        
        print("✓ Manager initialization successful")
        mgr.close()
        return True
        
    except Exception as e:
        print(f"✗ Manager initialization failed: {e}")
        return False


def test_from_config_server():
    """Test creating manager from config (server mode)."""
    print("Testing from_config (server mode)...")
    
    try:
        config = {
            'camera_type': 'Thorlabs',
            'mode': 'server',
            'camera_index': 0,
            'port': 8492,
            'resolution': [640, 480],
            'fps': 30
        }
        
        mgr = CameraManager.from_config(config, auto_connect=False)
        
        assert mgr.camera_type == 'Thorlabs', "Camera type should match config"
        assert mgr.mode == 'server', "Mode should be 'server'"
        assert mgr.port == 8492, "Port should match config"
        
        print("✓ from_config (server) successful")
        mgr.close()
        return True
        
    except Exception as e:
        print(f"✗ from_config (server) failed: {e}")
        return False


def test_from_config_client():
    """Test creating manager from config (client mode)."""
    print("Testing from_config (client mode)...")
    
    try:
        config = {
            'camera_type': 'Thorlabs',
            'mode': 'client',
            'server_ip': '192.168.1.100',
            'port': 8493
        }
        
        mgr = CameraManager.from_config(config, auto_connect=False)
        
        assert mgr.camera_type == 'Thorlabs', "Camera type should match config"
        assert mgr.mode == 'client', "Mode should be 'client'"
        assert mgr.port == 8493, "Port should match config"
        
        print("✓ from_config (client) successful")
        mgr.close()
        return True
        
    except Exception as e:
        print(f"✗ from_config (client) failed: {e}")
        return False


def test_create_server():
    """Test convenience method for creating server."""
    print("Testing create_server convenience method...")
    
    try:
        mgr = CameraManager.create_server(
            camera_index=0,
            port=8494,
            resolution=(640, 480),
            fps=30,
            auto_start=False
        )
        
        assert mgr.mode == 'server', "Mode should be 'server'"
        assert mgr.camera_type == 'Thorlabs', "Camera type should be 'Thorlabs'"
        assert mgr.port == 8494, "Port should match"
        
        print("✓ create_server successful")
        mgr.close()
        return True
        
    except Exception as e:
        print(f"✗ create_server failed: {e}")
        return False


def test_create_client():
    """Test convenience method for creating client."""
    print("Testing create_client convenience method...")
    
    try:
        mgr = CameraManager.create_client(
            server_ip='192.168.1.100',
            port=8495,
            auto_connect=False
        )
        
        assert mgr.mode == 'client', "Mode should be 'client'"
        assert mgr.camera_type == 'Thorlabs', "Camera type should be 'Thorlabs'"
        assert mgr.port == 8495, "Port should match"
        
        print("✓ create_client successful")
        mgr.close()
        return True
        
    except Exception as e:
        print(f"✗ create_client failed: {e}")
        return False


def test_get_camera_info():
    """Test getting camera information."""
    print("Testing get_camera_info...")
    
    try:
        mgr = CameraManager(mode='server', camera_index=0, port=8496)
        info = mgr.get_camera_info()
        
        assert 'camera_type' in info, "Info should contain 'camera_type'"
        assert 'mode' in info, "Info should contain 'mode'"
        assert info['camera_type'] == 'Thorlabs', "Camera type should match"
        assert info['mode'] == 'server', "Mode should match"
        
        print("✓ get_camera_info successful")
        print(f"  Info: {info}")
        mgr.close()
        return True
        
    except Exception as e:
        print(f"✗ get_camera_info failed: {e}")
        return False


def test_type_normalization():
    """Test camera type normalization."""
    print("Testing type normalization...")
    
    try:
        # Test lowercase
        mgr1 = CameraManager(camera_type='thorlabs', mode='server', port=8497)
        assert mgr1.camera_type == 'Thorlabs', "Should normalize to 'Thorlabs'"
        mgr1.close()
        
        print("✓ Type normalization successful")
        return True
        
    except Exception as e:
        print(f"✗ Type normalization failed: {e}")
        return False


def test_unsupported_type():
    """Test error handling for unsupported camera type."""
    print("Testing unsupported camera type error...")
    
    try:
        mgr = CameraManager(camera_type='UnknownCamera', mode='server', port=8498)
        print("✗ Should have raised ValueError for unsupported type")
        mgr.close()
        return False
        
    except ValueError:
        print("✓ Correctly raised ValueError for unsupported type")
        return True
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("CameraManager Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_manager_initialization,
        test_from_config_server,
        test_from_config_client,
        test_create_server,
        test_create_client,
        test_get_camera_info,
        test_type_normalization,
        test_unsupported_type,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"✗ Test {test.__name__} raised exception: {e}")
            results.append(False)
            print()
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    """
    Run tests when executed directly.
    
    Note: Tests that require a physical camera or network connections
    may have limited functionality, but should still test the interface
    and configuration handling.
    """
    exit_code = run_all_tests()
    sys.exit(exit_code)

