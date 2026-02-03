# Device Map Creator

A user-friendly tool for creating and checking device maps. No coding knowledge required!

## Quick Start

### Option 1: Use the GUI Tool (Recommended)

**Easiest way for non-programmers!**

1. Double-click or run:
   ```bash
   python device_map_tool.py
   ```

2. Follow the on-screen instructions:
   - Select your device image
   - Click and drag to map each device
   - Save when finished

### Option 2: Use the Command-Line Checker

Check and fix existing mapping files:

```bash
python check_mapping.py
```

Or specify a file:

```bash
python check_mapping.py path/to/your/mapping.json
```

## What Are Device Maps?

Device maps tell the measurement system where each device is located on your sample image. This allows you to:
- Click on devices in the GUI to select them
- Visualize device layouts
- Organize measurements by device location

## How to Create a New Map

### Step 1: Prepare Your Image

1. Take a clear photo of your device layout
2. Save it as a PNG or JPG file
3. Note the location of the file

### Step 2: Run the Map Creator

1. **Launch the tool:**
   ```bash
   python device_map_tool.py
   ```

2. **Select your image:**
   - Click "Browse..." next to "Image File"
   - Find and select your device image
   - Click "Open"

3. **Configure your sample:**
   - Enter a **Sample Type** (e.g., "Cross_bar", "Device_Array_10")
   - Enter a **Section** name (e.g., "A", "B", "1")

4. **Load the image:**
   - Click "Load Image"
   - A new window will open showing your image

### Step 3: Map Your Devices

**Important:** Always drag from **top-left** to **bottom-right**!

1. **For each device:**
   - Position your mouse at the **top-left corner** of the device
   - **Click and hold** the left mouse button
   - **Drag** to the **bottom-right corner**
   - **Release** the mouse button
   - A green rectangle will appear with a device label

2. **Continue mapping:**
   - Repeat for each device you want to measure
   - Devices are automatically numbered (device_1, device_2, etc.)

3. **Keyboard shortcuts** (in the image window):
   - Press **'S'** to save current progress
   - Press **'Q'** to quit (auto-saves)
   - Press **'R'** to reset current device
   - Press **'U'** to undo last device

### Step 4: Check Your Mapping

1. Click **"Check Mapping"** button
2. Review any warnings or errors
3. Fix issues if needed

### Step 5: Save

1. Click **"Save Mapping"** button
2. Your mapping will be saved to the JSON file
3. The file will be automatically updated with your new devices

## File Locations

### Default File Paths

- **Mapping JSON:** `Json_Files/mapping.json`
- **Sample Images:** `Helpers/Sample_Information/`

### Mapping File Structure

The mapping file is organized by sample type:

```json
{
  "Sample_Type_Name": {
    "device_1": {
      "x_min": 121,
      "y_min": 214,
      "x_max": 208,
      "y_max": 293,
      "sample": "Sample_Type_Name",
      "section": "A"
    },
    "device_2": {
      ...
    }
  },
  "Another_Sample_Type": {
    ...
  }
}
```

## Checking Existing Maps

### Using the GUI Tool

1. Open `device_map_tool.py`
2. Load your existing mapping JSON file
3. Click **"Check Mapping"**
4. Review results and fix any issues

### Using the Command-Line Tool

```bash
python check_mapping.py
```

This will:
- ✅ Validate all device rectangles
- ✅ Auto-fix swapped min/max values
- ✅ Report errors and warnings
- ✅ Save fixes automatically

## Troubleshooting

### Problem: "Could not load image"

**Solution:**
- Make sure the image file exists
- Check that the file is a supported format (PNG, JPG, BMP)
- Try opening the image in another program to verify it's not corrupted

### Problem: "Rectangle is too small"

**Solution:**
- Draw a larger rectangle around the device
- Make sure you're dragging from top-left to bottom-right
- The rectangle should be at least 5 pixels wide and tall

### Problem: Devices don't appear in the main GUI

**Solution:**
- Make sure you saved the mapping file
- Check that the sample type name matches
- Verify the JSON file is in the correct location
- Run the checker tool to find errors:
  ```bash
  python check_mapping.py
  ```

### Problem: "Invalid rectangle" error

**Solution:**
- Run the checker tool - it will auto-fix swapped min/max values:
  ```bash
  python check_mapping.py
  ```
- Or manually ensure:
  - `x_min` < `x_max`
  - `y_min` < `y_max`

## Tips for Best Results

1. **Use clear images:** High-resolution photos work best
2. **Consistent orientation:** Keep the sample oriented the same way in all images
3. **Map systematically:** Go left-to-right, top-to-bottom
4. **Check your work:** Always run the checker after creating a map
5. **Backup your file:** Keep a copy of your mapping file before major changes

## Advanced Usage

### Loading Existing Maps

To continue working on an existing map:

1. Set the JSON file path to your existing file
2. Click **"Load Existing Mapping"**
3. Select the sample type from the dropdown
4. Continue mapping or make edits

### Multiple Sample Types

The mapping file can contain multiple sample types. To add a new one:

1. Enter a new **Sample Type** name
2. Start mapping devices
3. All devices will be saved under that sample type

### Batch Checking

Check multiple files at once:

```bash
python check_mapping.py file1.json
python check_mapping.py file2.json
python check_mapping.py file3.json
```

## Tools Included

### device_map_tool.py
- **Purpose:** Main GUI tool for creating and editing maps
- **Best for:** Creating new maps or editing existing ones
- **User Level:** Anyone (no coding needed)

### check_mapping.py
- **Purpose:** Command-line tool to validate and fix mapping files
- **Best for:** Checking existing maps, batch validation
- **User Level:** Basic command-line familiarity helpful

### Legacy Tools
- `Map_device.py` - Old mapping tool (use `device_map_tool.py` instead)
- `show_boxes.py` - Old visualization tool (integrated into GUI)
- `jason_check.py` - Old checker (use `check_mapping.py` instead)

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run the checker tool to find specific errors
3. Verify your image file is valid
4. Check that file paths are correct

## Examples

### Example 1: Creating a Map for a New Sample

```bash
# 1. Start the tool
python device_map_tool.py

# 2. In the GUI:
#    - Browse for: "my_device_image.png"
#    - Sample Type: "My_New_Sample"
#    - Section: "A"
#    - Click "Load Image"
#    - Map devices by clicking and dragging
#    - Click "Save Mapping"
```

### Example 2: Checking an Existing Map

```bash
# Quick check with default file
python check_mapping.py

# Check a specific file
python check_mapping.py Json_Files/my_custom_mapping.json
```

## File Format Reference

Each device entry contains:

- **x_min, y_min:** Top-left corner coordinates
- **x_max, y_max:** Bottom-right corner coordinates
- **sample:** Sample type name (must match the key in JSON)
- **section:** Section identifier (e.g., "A", "B", "1")

All coordinates are in pixels relative to the original image size.

