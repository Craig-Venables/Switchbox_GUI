"""
Camera Viewer Test Script

This script provides a simple GUI application to test and view the camera feed.
It supports USB mode for local camera viewing and can be extended for network streaming.

Purpose:
    Test camera functionality and provide a visual interface for camera feeds,
    useful for verifying camera connections and settings before integration with motor control.

Usage:
    python view_camera.py [camera_index]
    
    Press 'q' to quit the viewer.
    Press 's' to save a screenshot.
    Press 'r' to show camera resolution info.
"""

from __future__ import annotations

import sys
import os
import cv2
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Equipment.camera_manager import CameraManager


def main():
    """Main function to run the camera viewer."""
    # Get camera index from command line or use default
    camera_index = 0
    if len(sys.argv) > 1:
        try:
            camera_index = int(sys.argv[1])
        except ValueError:
            print(f"Invalid camera index: {sys.argv[1]}. Using default (0)")
    
    print("=" * 60)
    print("Camera Viewer - USB Mode")
    print("=" * 60)
    print(f"Opening camera {camera_index}...")
    print("\nControls:")
    print("  'q' - Quit")
    print("  's' - Save screenshot")
    print("  'r' - Show resolution info")
    print("  'f' - Show FPS")
    print("=" * 60)
    
    try:
        # Create camera manager in USB mode
        camera = CameraManager.create_usb(
            camera_index=camera_index,
            resolution=(1280, 720),  # Higher resolution for better viewing
            fps=30
        )
        
        if not camera.is_connected():
            print(f"ERROR: Failed to open camera {camera_index}")
            print("Please check:")
            print("  1. Camera is connected")
            print("  2. Camera is not being used by another application")
            print("  3. Camera index is correct (try 0, 1, 2, etc.)")
            return 1
        
        print(f"\n✓ Camera {camera_index} opened successfully")
        info = camera.get_camera_info()
        print(f"Mode: {info.get('mode', 'unknown')}")
        print(f"Resolution: {info.get('resolution', 'unknown')}")
        print(f"FPS: {info.get('fps', 'unknown')}")
        print("\nStarting video feed...")
        print("(Press 'q' to quit)\n")
        
        # Frame rate calculation
        frame_count = 0
        fps_start_time = time.time()
        current_fps = 0.0
        
        screenshot_count = 0
        
        while True:
            # Get frame
            frame = camera.get_frame()
            
            if frame is None:
                print("Warning: No frame received")
                time.sleep(0.1)
                continue
            
            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - fps_start_time
            if elapsed >= 1.0:
                current_fps = frame_count / elapsed
                frame_count = 0
                fps_start_time = time.time()
            
            # Add FPS text to frame
            frame_with_info = frame.copy()
            cv2.putText(
                frame_with_info,
                f"FPS: {current_fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )
            cv2.putText(
                frame_with_info,
                f"Resolution: {frame.shape[1]}x{frame.shape[0]}",
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            cv2.putText(
                frame_with_info,
                f"Camera: {camera_index}",
                (10, 110),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            cv2.putText(
                frame_with_info,
                "Press 'q' to quit, 's' to save, 'r' for info",
                (10, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            
            # Display frame
            cv2.imshow('Camera Viewer - USB Mode', frame_with_info)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord('s'):
                # Save screenshot
                screenshot_count += 1
                filename = f"camera_screenshot_{screenshot_count:04d}.jpg"
                cv2.imwrite(filename, frame)
                print(f"\nScreenshot saved: {filename}")
            elif key == ord('r'):
                # Show resolution info
                print(f"\nCamera Information:")
                print(f"  Resolution: {frame.shape[1]} x {frame.shape[0]}")
                print(f"  Channels: {frame.shape[2] if len(frame.shape) > 2 else 1}")
                print(f"  Data type: {frame.dtype}")
                print(f"  FPS: {current_fps:.2f}")
            elif key == ord('f'):
                # Show FPS only
                print(f"Current FPS: {current_fps:.2f}")
        
        # Cleanup
        camera.close()
        cv2.destroyAllWindows()
        
        print("\n✓ Camera closed successfully")
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if 'camera' in locals():
            camera.close()
        cv2.destroyAllWindows()
        return 0
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        if 'camera' in locals():
            try:
                camera.close()
            except:
                pass
        cv2.destroyAllWindows()
        return 1


if __name__ == "__main__":
    """
    Run the camera viewer when executed directly.
    """
    exit_code = main()
    sys.exit(exit_code)








