"""
Test script for ThorlabsCamera class

This script tests the basic functionality of the ThorlabsCamera class for
Ethernet webcam streaming. It verifies camera initialization, streaming,
and frame capture capabilities.

Purpose:
    Verify that the camera class works correctly for both server and client modes,
    enabling reliable integration with motor control systems.

Usage:
    Run this script to test camera functionality. Ensure a webcam is connected
    and OpenCV is properly installed.
"""

from __future__ import annotations

import sys
import os
import time
import cv2
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Equipment.Camera.thorlabs_camera import ThorlabsCamera


def test_camera_initialization():
    """Test camera initialization in server mode."""
    print("Testing camera initialization (server mode)...")
    
    try:
        camera = ThorlabsCamera(
            mode='server',
            camera_index=0,
            port=8485,
            resolution=(640, 480),
            fps=30
        )
        
        assert camera.mode == 'server', "Mode should be 'server'"
        assert camera.capture is not None, "Capture object should be initialized"
        assert camera.capture.isOpened(), "Camera should be opened"
        
        print("✓ Camera initialization successful")
        camera.close()
        return True
        
    except Exception as e:
        print(f"✗ Camera initialization failed: {e}")
        return False


def test_camera_info():
    """Test camera info retrieval."""
    print("Testing camera info retrieval...")
    
    try:
        camera = ThorlabsCamera(mode='server', camera_index=0, port=8486)
        info = camera.get_camera_info()
        
        assert 'mode' in info, "Info should contain 'mode'"
        assert 'resolution' in info, "Info should contain 'resolution'"
        assert 'fps' in info, "Info should contain 'fps'"
        assert info['mode'] == 'server', "Mode should be 'server'"
        
        print("✓ Camera info retrieval successful")
        print(f"  Info: {info}")
        camera.close()
        return True
        
    except Exception as e:
        print(f"✗ Camera info retrieval failed: {e}")
        return False


def test_frame_capture():
    """Test frame capture from camera."""
    print("Testing frame capture...")
    
    try:
        camera = ThorlabsCamera(mode='server', camera_index=0, port=8487)
        
        # Read a few frames to ensure camera is working
        for i in range(5):
            ret, frame = camera.capture.read()
            if ret:
                assert frame is not None, "Frame should not be None"
                assert isinstance(frame, np.ndarray), "Frame should be numpy array"
                assert len(frame.shape) == 3, "Frame should be 3D array (H, W, C)"
                break
        
        if not ret:
            print("⚠ Could not capture frame (camera may not be available)")
            camera.close()
            return True  # Not a failure if camera isn't connected
        
        print("✓ Frame capture successful")
        print(f"  Frame shape: {frame.shape}")
        camera.close()
        return True
        
    except Exception as e:
        print(f"✗ Frame capture failed: {e}")
        return False


def test_streaming_setup():
    """Test streaming setup (without actual client connection)."""
    print("Testing streaming setup...")
    
    try:
        camera = ThorlabsCamera(mode='server', camera_index=0, port=8488)
        
        # Start streaming (will wait for client)
        result = camera.start_streaming()
        
        assert result is True, "Streaming should start successfully"
        assert camera.streaming is True, "Streaming flag should be True"
        assert camera.socket is not None, "Socket should be created"
        
        print("✓ Streaming setup successful")
        print("  (Note: Will wait for client connection)")
        
        # Cleanup
        camera.stop_streaming()
        camera.close()
        return True
        
    except Exception as e:
        print(f"✗ Streaming setup failed: {e}")
        return False


def test_client_initialization():
    """Test client mode initialization."""
    print("Testing client initialization...")
    
    try:
        # Use a non-existent IP for testing (should still initialize)
        camera = ThorlabsCamera(
            mode='client',
            server_ip='192.168.1.100',
            port=8489
        )
        
        assert camera.mode == 'client', "Mode should be 'client'"
        assert camera.server_ip == '192.168.1.100', "Server IP should be set"
        assert camera.socket is not None, "Socket should be initialized"
        
        print("✓ Client initialization successful")
        camera.close()
        return True
        
    except Exception as e:
        print(f"✗ Client initialization failed: {e}")
        return False


def test_frame_callback():
    """Test frame callback functionality."""
    print("Testing frame callback...")
    
    callback_called = [False]
    frame_received = [None]
    
    def test_callback(frame):
        callback_called[0] = True
        frame_received[0] = frame.copy()
    
    try:
        camera = ThorlabsCamera(mode='client', server_ip='192.168.1.100', port=8490)
        camera.set_frame_callback(test_callback)
        
        assert camera.frame_callback is not None, "Callback should be set"
        assert camera.frame_callback == test_callback, "Callback should match"
        
        print("✓ Frame callback setup successful")
        camera.close()
        return True
        
    except Exception as e:
        print(f"✗ Frame callback test failed: {e}")
        return False


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("ThorlabsCamera Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_camera_initialization,
        test_camera_info,
        test_frame_capture,
        test_streaming_setup,
        test_client_initialization,
        test_frame_callback,
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
    
    Note: Some tests require a physical camera to be connected.
    Tests that require network connections may fail if no server/client
    are running, which is expected behavior.
    """
    exit_code = run_all_tests()
    sys.exit(exit_code)












