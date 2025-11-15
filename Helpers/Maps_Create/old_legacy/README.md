# Old Legacy Tools

This folder contains the original mapping tools that have been replaced by the new, user-friendly GUI tools.

## Legacy Files

### Map_device.py
- **Original mapping tool** using OpenCV
- Replaced by: `device_map_tool.py`
- **Use case:** Command-line mapping tool
- **How to use:** 
  ```bash
  python Map_device.py
  ```
  - Click and drag on image to map devices
  - Press 'S' to save
  - Press 'Q' to quit

### show_boxes.py
- **Original visualization tool** using matplotlib
- Replaced by: Integrated into `device_map_tool.py` (Check Mapping feature)
- **Use case:** View device mappings on scaled image
- **How to use:**
  ```bash
  python show_boxes.py
  ```
  - Shows green boxes for valid mappings
  - Shows red boxes for invalid mappings

### jason_check.py
- **Original checker tool** (note: typo in filename - "jason" instead of "json")
- Replaced by: `check_mapping.py`
- **Use case:** Check and fix mapping JSON files
- **How to use:**
  ```bash
  python jason_check.py
  ```
  - Auto-fixes swapped min/max values
  - Validates mapping file

## Why Use Legacy Tools?

Use these old tools if:
- You're familiar with the old workflow
- You need command-line only tools
- You have existing scripts that depend on these files
- You prefer the original simple interface

## Recommendation

**For new users:** Use the new tools:
- `device_map_tool.py` - Full-featured GUI tool
- `check_mapping.py` - Improved command-line checker

**For existing users:** You can continue using these legacy tools if you prefer.

## Notes

- The old tools still work but may not have all the new features
- The new tools are more user-friendly and have better error handling
- All tools use the same JSON file format, so mappings are compatible

