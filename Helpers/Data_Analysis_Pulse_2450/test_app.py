"""
Test script to verify application components work correctly.
Run this before launching the full GUI.
"""

import sys
from pathlib import Path

print("=" * 60)
print("TSP Data Analysis Tool - Component Tests")
print("=" * 60)

# Test 1: Core imports
print("\n1. Testing core imports...")
try:
    from core.data_parser import parse_tsp_file, TSPData
    from core.test_type_registry import get_registry
    print("   [OK] Core modules imported successfully")
except Exception as e:
    print(f"   [ERROR] Core import failed: {e}")
    sys.exit(1)

# Test 2: Utils imports
print("\n2. Testing utils imports...")
try:
    from utils.settings import get_settings
    print("   [OK] Utils modules imported successfully")
except Exception as e:
    print(f"   [ERROR] Utils import failed: {e}")
    sys.exit(1)

# Test 3: Test type registry
print("\n3. Testing test type registry...")
try:
    registry = get_registry()
    test_types = registry.get_all_test_types()
    print(f"   [OK] Registry loaded with {len(test_types)} test types")
    print(f"   Test types: {', '.join(test_types[:3])}...")
except Exception as e:
    print(f"   [ERROR] Registry test failed: {e}")
    sys.exit(1)

# Test 4: Settings
print("\n4. Testing settings...")
try:
    settings = get_settings()
    window_width = settings.get('window.width')
    print(f"   [OK] Settings loaded (window width: {window_width})")
except Exception as e:
    print(f"   [ERROR] Settings test failed: {e}")
    sys.exit(1)

# Test 5: GUI imports (without creating widgets)
print("\n5. Testing GUI imports...")
try:
    from PyQt6.QtWidgets import QApplication
    from gui.main_window import MainWindow
    from gui.file_browser_tab import FileBrowserTab
    print("   [OK] GUI modules imported successfully")
except Exception as e:
    print(f"   [ERROR] GUI import failed: {e}")
    print(f"   Note: Make sure PyQt6 is installed (pip install PyQt6)")
    sys.exit(1)

# Test 6: Data parser (if test file exists)
print("\n6. Testing data parser...")
test_data_dir = Path("../../Data_save_loc")
if test_data_dir.exists():
    txt_files = list(test_data_dir.rglob("*.txt"))
    txt_files = [f for f in txt_files if not f.name.startswith("tsp_test_log")][:1]
    
    if txt_files:
        try:
            data = parse_tsp_file(txt_files[0])
            if data:
                print(f"   [OK] Successfully parsed: {data.filename}")
                print(f"     Test: {data.test_name}")
                print(f"     Points: {len(data.timestamps)}")
            else:
                print("   [WARN] Parsing returned None")
        except Exception as e:
            print(f"   [WARN] Parser test failed: {e}")
    else:
        print("   [WARN] No test files found to parse")
else:
    print("   [WARN] Test data directory not found")

print("\n" + "=" * 60)
print("[SUCCESS] All critical tests passed!")
print("=" * 60)
print("\nYou can now run the application with:")
print("  python main.py")
print()

