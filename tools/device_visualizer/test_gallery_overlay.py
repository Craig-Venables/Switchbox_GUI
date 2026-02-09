"""
Test script for Gallery and Overlay tabs.

This script helps verify the new Gallery and Overlay tabs work correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt5.QtWidgets import QApplication
from tools.device_visualizer.widgets import GalleryTab, OverlayTab
from tools.device_visualizer.data.device_data_model import DeviceData, MeasurementData


def create_test_device_data():
    """
    Create a test DeviceData object for testing.
    
    Note: This requires actual measurement files to exist for plot discovery to work.
    """
    # Create a minimal test device
    device = DeviceData(
        device_id="TEST_1",
        sample_name="TestSample",
        section="TEST",
        device_number=1
    )
    
    # You would need to add actual measurement files here
    # Example:
    # test_file = Path("path/to/test/measurement.txt")
    # if test_file.exists():
    #     measurement = MeasurementData(
    #         file_path=test_file,
    #         measurement_type="iv_sweep"
    #     )
    #     device.measurements.append(measurement)
    
    return device


def test_gallery_tab():
    """Test Gallery tab standalone."""
    print("Testing Gallery Tab...")
    
    app = QApplication(sys.argv)
    
    gallery = GalleryTab()
    gallery.setWindowTitle("Gallery Tab Test")
    gallery.resize(800, 600)
    gallery.show()
    
    # For actual testing, you would load a real device:
    # device = create_test_device_data()
    # gallery.update_device(device)
    
    print("Gallery tab window opened. Close window to continue.")
    app.exec_()
    print("Gallery tab test complete.\n")


def test_overlay_tab():
    """Test Overlay tab standalone."""
    print("Testing Overlay Tab...")
    
    app = QApplication(sys.argv)
    
    overlay = OverlayTab()
    overlay.setWindowTitle("Overlay Tab Test")
    overlay.resize(800, 600)
    overlay.show()
    
    # For actual testing, you would load a real device:
    # device = create_test_device_data()
    # overlay.update_device(device)
    
    print("Overlay tab window opened. Close window to continue.")
    app.exec_()
    print("Overlay tab test complete.\n")


def test_discovery():
    """
    Test plot image discovery without GUI.
    
    Provide a path to a device folder to test discovery.
    """
    print("Testing Plot Discovery...")
    
    # Example: Provide a path to test
    test_path = Path("path/to/device/folder")  # Replace with actual path
    
    if not test_path.exists():
        print(f"Test path does not exist: {test_path}")
        print("Please edit test_gallery_overlay.py and provide a valid device folder path.")
        return
    
    # Search for images
    image_extensions = ['*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']
    found_images = []
    
    for ext in image_extensions:
        found = list(test_path.rglob(ext))
        found_images.extend(found)
    
    print(f"Found {len(found_images)} plot images in {test_path}")
    for img in found_images[:10]:  # Show first 10
        print(f"  - {img.name} ({img.relative_to(test_path)})")
    
    if len(found_images) > 10:
        print(f"  ... and {len(found_images) - 10} more")
    
    print()


def print_usage():
    """Print usage instructions."""
    print("=" * 60)
    print("Gallery and Overlay Tabs Test Script")
    print("=" * 60)
    print()
    print("This script tests the new Gallery and Overlay tabs.")
    print()
    print("Test Options:")
    print("  1. Test Gallery tab (standalone)")
    print("  2. Test Overlay tab (standalone)")
    print("  3. Test plot discovery")
    print("  4. Launch full visualizer")
    print("  5. Exit")
    print()


def launch_full_visualizer():
    """Launch the full device visualizer application."""
    print("Launching full Device Analysis Visualizer...")
    
    try:
        from tools.device_visualizer import launch_visualizer
        launch_visualizer()
    except Exception as e:
        print(f"Error launching visualizer: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main test menu."""
    print_usage()
    
    while True:
        choice = input("Select test option (1-5): ").strip()
        
        if choice == '1':
            test_gallery_tab()
            print_usage()
        elif choice == '2':
            test_overlay_tab()
            print_usage()
        elif choice == '3':
            test_discovery()
            print_usage()
        elif choice == '4':
            launch_full_visualizer()
            break
        elif choice == '5':
            print("Exiting test script.")
            break
        else:
            print("Invalid choice. Please select 1-5.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest script interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
