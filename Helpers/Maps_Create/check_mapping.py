"""
Mapping Checker - Standalone Tool
==================================

A simple tool to check and fix device mapping files.
Run this to validate and auto-fix any issues in your mapping JSON files.

Usage:
    python check_mapping.py [path_to_mapping.json]
"""

import json
import sys
from pathlib import Path

# Get project root for default path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_and_fix_mapping(json_path):
    """Check and fix a mapping JSON file."""
    print(f"\n{'='*60}")
    print(f"Checking: {json_path}")
    print(f"{'='*60}\n")
    
    if not Path(json_path).exists():
        print(f"❌ ERROR: File not found: {json_path}")
        return False
        
    try:
        # Load the mapping file
        with open(json_path, 'r', encoding='utf-8') as f:
            device_mapping = json.load(f)
            
        print(f"✓ File loaded successfully\n")
        
        # Track issues
        fixed = 0
        errors = []
        warnings = []
        
        # Process each sample type
        for sample_type, devices in device_mapping.items():
            print(f"Sample Type: {sample_type}")
            print(f"  Devices: {len(devices)}")
            
            if not isinstance(devices, dict):
                errors.append(f"{sample_type}: Invalid format (expected dict)")
                continue
                
            # Check each device
            for device_name, bounds in devices.items():
                if not isinstance(bounds, dict):
                    errors.append(f"{sample_type}.{device_name}: Invalid format (expected dict)")
                    continue
                    
                # Fix min/max values if swapped
                if "x_min" in bounds and "x_max" in bounds:
                    if bounds["x_min"] > bounds["x_max"]:
                        bounds["x_min"], bounds["x_max"] = bounds["x_max"], bounds["x_min"]
                        fixed += 1
                        print(f"    ✓ Fixed {device_name}: swapped x_min/x_max")
                        
                if "y_min" in bounds and "y_max" in bounds:
                    if bounds["y_min"] > bounds["y_max"]:
                        bounds["y_min"], bounds["y_max"] = bounds["y_max"], bounds["y_min"]
                        fixed += 1
                        print(f"    ✓ Fixed {device_name}: swapped y_min/y_max")
                        
                # Validate required fields
                required = ["x_min", "y_min", "x_max", "y_max"]
                missing = [key for key in required if key not in bounds]
                if missing:
                    errors.append(f"{sample_type}.{device_name}: Missing fields {missing}")
                    
                # Check rectangle validity
                if all(key in bounds for key in required):
                    x_min, y_min = bounds["x_min"], bounds["y_min"]
                    x_max, y_max = bounds["x_max"], bounds["y_max"]
                    
                    if x_min >= x_max or y_min >= y_max:
                        errors.append(f"{sample_type}.{device_name}: Invalid rectangle")
                        
                    width = x_max - x_min
                    height = y_max - y_min
                    if width < 5 or height < 5:
                        warnings.append(f"{sample_type}.{device_name}: Very small rectangle ({width}x{height})")
                        
            print()
            
        # Save if fixes were made
        if fixed > 0:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(device_mapping, f, indent=2, separators=(",", ": "))
            print(f"✓ Saved fixes to file\n")
            
        # Report summary
        print(f"{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"✓ Auto-fixed issues: {fixed}")
        print(f"⚠ Warnings: {len(warnings)}")
        print(f"❌ Errors: {len(errors)}")
        
        if warnings:
            print(f"\nWarnings:")
            for w in warnings[:10]:
                print(f"  - {w}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")
                
        if errors:
            print(f"\nErrors:")
            for e in errors[:10]:
                print(f"  - {e}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
                
        if not errors and not warnings:
            print("\n✓ All mappings are valid!")
            return True
        else:
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON format: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        # Default to project mapping.json
        json_path = _PROJECT_ROOT / "Json_Files" / "mapping.json"
        
    success = check_and_fix_mapping(json_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

