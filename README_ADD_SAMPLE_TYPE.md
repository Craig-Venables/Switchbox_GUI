# How to Add a New Sample Type

This guide walks you through the process of adding a new sample type to the Switchbox GUI application.

## Overview

Adding a new sample type involves four main steps:
1. Prepare the sample image
2. Define the sample configuration
3. Create the device mapping with coordinates
4. Add image loading logic

## Prerequisites

- Sample image file (PNG or JPG format)
- Knowledge of device locations on the sample (pixel coordinates)
- Understanding of sample sections and device numbering scheme

---

## Step 1: Add Sample Image

### 1.1 Prepare Your Image

Place your sample image in the following directory:
```
Helpers/Sample_Infomation/
```

**Image Requirements:**
- Format: PNG or JPG
- Recommended size: At least 400x400 pixels (will be resized to 400x400)
- Clear visibility of device locations
- Good contrast for device identification

**Example:**
```
Helpers/Sample_Infomation/My_New_Sample.jpg
```

---

## Step 2: Configure Sample Settings

### 2.1 Edit Sample_GUI.py

Open `Sample_GUI.py` and locate the `sample_config` dictionary (around line 48).

Add your new sample configuration:

```python
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, ...},
        "devices": [str(i) for i in range(1, 11)]
    },
    "Multiplexer_10_OUT": {
        "sections": {"A": True},
        "devices": [str(i) for i in range(1, 11)]
    },
    "My_New_Sample": {  # Add your new sample here
        "sections": {
            "A": True,   # True = enabled, False = disabled
            "B": True,
            "C": False   # Disabled sections won't show in UI
        },
        "devices": [str(i) for i in range(1, 21)]  # Device numbers
    }
}
```

**Configuration Parameters:**

- **sections**: Dictionary of section names (A, B, C, etc.)
  - `True` = Section is enabled and selectable
  - `False` = Section is disabled but visible in dropdown
  
- **devices**: List of device identifiers
  - Usually sequential numbers as strings: `["1", "2", "3", ...]`
  - Can use any naming scheme: `["D1", "D2", "D3", ...]`

---

## Step 3: Create Device Mapping

### 3.1 Determine Device Coordinates

You need to find the pixel coordinates for each device on your sample image. Use an image editor or the helper script to identify coordinates.

**Helper Script Location:**
```
Helpers/Maps_Create/show_boxes.py
```

This script can help you visualize and test device locations.

### 3.2 Edit mapping.json

Open `Json_Files/mapping.json` and add your device mapping:

```json
{
  "Cross_bar": { ... },
  "Multiplexer_10_OUT": { ... },
  "My_New_Sample": {
    "device_1": {
      "x_min": 100,
      "y_min": 150,
      "x_max": 200,
      "y_max": 250,
      "sample": "My_New_Sample",
      "section": "A"
    },
    "device_2": {
      "x_min": 220,
      "y_min": 150,
      "x_max": 320,
      "y_max": 250,
      "sample": "My_New_Sample",
      "section": "A"
    },
    ... (add all devices)
  }
}
```

**Mapping Parameters:**

- **device_X**: Unique device identifier (must match device list from Step 2)
- **x_min, y_min**: Top-left corner coordinates (in pixels)
- **x_max, y_max**: Bottom-right corner coordinates (in pixels)
- **sample**: Must match your sample name exactly
- **section**: Section identifier (A, B, C, etc.)

**Tips for Mapping:**
1. Use an image editor with pixel coordinate display
2. Start from top-left of the image (0,0)
3. Create rectangular boundaries around each device
4. Ensure no overlapping regions between devices
5. Test with the helper scripts to verify accuracy

---

## Step 4: Add Image Loading Logic

### 4.1 Edit load_image Function

In `Sample_GUI.py`, locate the `load_image` function (around line 365).

Add your image loading logic:

```python
def load_image(self, sample: str) -> None:
    """ Load image into canvas set up to add others later simply """
    
    if sample == 'Cross_bar':
        sample = BASE_DIR / "Helpers" / "Sample_Infomation" / "memristor.png"
        self.original_image = Image.open(sample)
        img = self.original_image.resize((400, 400))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

    if sample == 'Multiplexer_10_OUT':
        sample = BASE_DIR / "Helpers" / "Sample_Infomation" / "Multiplexer_10_OUT.jpg"
        self.original_image = Image.open(sample)
        img = self.original_image.resize((400, 400))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
    
    # Add your new sample here
    if sample == 'My_New_Sample':
        sample = BASE_DIR / "Helpers" / "Sample_Infomation" / "My_New_Sample.jpg"
        self.original_image = Image.open(sample)
        img = self.original_image.resize((400, 400))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

    # Redraw selection highlights
    self.update_canvas_selection_highlights()
```

**Important Notes:**
- Use the exact same name in all configurations
- Include "Helpers" / "Sample_Infomation" in the path
- The image will be automatically resized to 400x400 pixels
- Make sure file extension matches your actual file (.jpg or .png)

---

## Step 5: Testing Your New Sample

### 5.1 Run the Application

```bash
python main.py
```

### 5.2 Verification Checklist

- [ ] New sample appears in the sample type dropdown
- [ ] Sample image loads correctly
- [ ] Sections appear in section dropdown with correct enabled/disabled states
- [ ] Device numbers appear in device dropdown
- [ ] Device selection highlights appear at correct locations on image
- [ ] Multiple device selection works correctly
- [ ] Device info displays correctly when selected

### 5.3 Common Issues and Solutions

**Issue: Sample doesn't appear in dropdown**
- Check `sample_config` key name matches exactly
- Verify JSON syntax is correct

**Issue: Image not found error**
- Verify image file exists in `Helpers/Sample_Infomation/`
- Check file extension (.jpg vs .png)
- Ensure path in `load_image` function is correct

**Issue: Devices don't highlight correctly**
- Verify coordinates in `mapping.json`
- Check that device names match between `sample_config` and `mapping.json`
- Use `show_boxes.py` helper to visualize coordinates

**Issue: Wrong devices highlighted**
- Scale your coordinates if image was resized
- Remember image is displayed at 400x400, so scale accordingly
- If original image is 1200x1200, divide all coordinates by 3

---

## Quick Reference Checklist

When adding a new sample type named "MySample":

1. **Add image:** `Helpers/Sample_Infomation/MySample.jpg`

2. **Update `Sample_GUI.py` - sample_config:**
   ```python
   "MySample": {
       "sections": {"A": True, ...},
       "devices": [str(i) for i in range(1, 11)]
   }
   ```

3. **Update `Json_Files/mapping.json`:**
   ```json
   "MySample": {
       "device_1": {coordinates, "sample": "MySample", "section": "A"},
       ...
   }
   ```

4. **Update `Sample_GUI.py` - load_image function:**
   ```python
   if sample == 'MySample':
       sample = BASE_DIR / "Helpers" / "Sample_Infomation" / "MySample.jpg"
       self.original_image = Image.open(sample)
       img = self.original_image.resize((400, 400))
       self.tk_img = ImageTk.PhotoImage(img)
       self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
   ```

5. **Test thoroughly!**

---

## Advanced: Coordinate Mapping Helper

To help map coordinates, you can use this Python snippet:

```python
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Load your image
img = Image.open("Helpers/Sample_Infomation/MySample.jpg")

# Display with matplotlib
fig, ax = plt.subplots(1)
ax.imshow(img)

# Click to get coordinates
def onclick(event):
    if event.xdata is not None and event.ydata is not None:
        print(f"x={int(event.xdata)}, y={int(event.ydata)}")

cid = fig.canvas.mpl_connect('button_press_event', onclick)
plt.show()
```

This will help you identify pixel coordinates by clicking on the image.

---

## Additional Resources

- **Device mapping tool:** `Helpers/Maps_Create/Map_device.py`
- **Coordinate verification:** `Helpers/Maps_Create/show_boxes.py`
- **JSON validation:** `Helpers/Maps_Create/jason_check.py`

---

## Example: Complete Sample Addition

Here's a complete example of adding a sample called "TestChip":

### Files to modify:

**1. Add image:** `Helpers/Sample_Infomation/TestChip.png`

**2. `Sample_GUI.py` (sample_config):**
```python
"TestChip": {
    "sections": {"Section1": True, "Section2": True},
    "devices": [str(i) for i in range(1, 5)]
}
```

**3. `Json_Files/mapping.json`:**
```json
"TestChip": {
  "device_1": {"x_min": 50, "y_min": 50, "x_max": 150, "y_max": 150, "sample": "TestChip", "section": "Section1"},
  "device_2": {"x_min": 200, "y_min": 50, "x_max": 300, "y_max": 150, "sample": "TestChip", "section": "Section1"},
  "device_3": {"x_min": 50, "y_min": 200, "x_max": 150, "y_max": 300, "sample": "TestChip", "section": "Section2"},
  "device_4": {"x_min": 200, "y_min": 200, "x_max": 300, "y_max": 300, "sample": "TestChip", "section": "Section2"}
}
```

**4. `Sample_GUI.py` (load_image function):**
```python
if sample == 'TestChip':
    sample = BASE_DIR / "Helpers" / "Sample_Infomation" / "TestChip.png"
    self.original_image = Image.open(sample)
    img = self.original_image.resize((400, 400))
    self.tk_img = ImageTk.PhotoImage(img)
    self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
```

---

## Notes

- **Naming Convention:** Use consistent naming across all files (case-sensitive)
- **Coordinate Scaling:** If your image is resized, ensure coordinates are scaled appropriately
- **Section Naming:** Can use any string for section names (A, B, C or Section1, Section2, etc.)
- **Device Naming:** Must be unique within the sample, typically "device_1", "device_2", etc.
- **JSON Validation:** Use a JSON validator to ensure proper syntax before running

---

## Support

If you encounter issues:
1. Check the console output for error messages
2. Verify JSON syntax using `Helpers/Maps_Create/jason_check.py`
3. Test coordinates using `Helpers/Maps_Create/show_boxes.py`
4. Review existing sample configurations as templates

---

Last Updated: October 2025

