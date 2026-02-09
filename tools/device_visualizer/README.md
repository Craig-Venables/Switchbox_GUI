# Device Analysis Visualizer

A comprehensive Qt5 application for visualizing device analysis data with dynamic data discovery and interactive visualizations.

## Features

### Core Tabs

1. **📊 Overview** - Yield heatmap and high-level device summary
2. **📈 Plots** - I-V curves, hysteresis, and resistance visualization
3. **📉 Metrics** - Device metrics analysis and comparison
4. **🔬 Classification** - Classification breakdown and feature scores

### New Plot Gallery Tabs

#### 🖼️ Gallery Tab (Ctrl+5)

The Gallery tab provides a scrollable grid view of all plot images found in the device folder.

**Features:**
- Automatically discovers PNG, JPG, and JPEG images in device folder and subfolders
- Displays plots in a 3-column responsive grid layout
- Shows filename and relative path for each plot
- Refresh button to reload plots
- Scrollable for easy navigation through many plots

**Usage:**
1. Select a device from the device list
2. Navigate to the Gallery tab (Ctrl+5)
3. Scroll through all available plot images
4. Click Refresh to reload if new plots are generated

**Supported Formats:**
- PNG (.png)
- JPEG (.jpg, .jpeg)

---

#### 📚 Overlay Tab (Ctrl+6)

The Overlay tab displays all plot images stacked on top of one another, useful for comparing multiple plots or seeing patterns across different measurements.

**Features:**
- Overlays multiple plots with adjustable transparency
- Opacity slider (10%-100%) to control layer visibility
- Individual layer toggle controls
- Show All / Hide All buttons for quick control
- Centered alignment for plots of different sizes

**Usage:**
1. Select a device from the device list
2. Navigate to the Overlay tab (Ctrl+6)
3. Adjust opacity slider to control transparency of overlaid plots
4. Click on layer names in the dropdown to toggle individual plots on/off
5. Use "Show All" or "Hide All" buttons to quickly control all layers

**Tips:**
- Lower opacity (30-50%) works best for comparing multiple plots
- Higher opacity (70-100%) is better for viewing 2-3 plots
- Toggle individual layers to focus on specific comparisons

---

## Keyboard Shortcuts

### Navigation
- **↑/↓** - Navigate through device list
- **Page Up/Down** - Jump up/down in device list
- **Home/End** - Go to first/last device
- **Enter** - Select device (when list has focus)

### Tabs
- **Ctrl+1** - Overview tab
- **Ctrl+2** - Plots tab
- **Ctrl+3** - Metrics tab
- **Ctrl+4** - Classification tab
- **Ctrl+5** - Gallery tab
- **Ctrl+6** - Overlay tab
- **Ctrl+Tab** - Cycle through tabs

### File Operations
- **Ctrl+O** - Open sample
- **F5** - Refresh current sample
- **Ctrl+Q** - Exit application

---

## File Discovery

The Gallery and Overlay tabs automatically discover plot images using the following search strategy:

1. Determines device folder from measurement files
2. Recursively searches for image files (*.png, *.jpg, *.jpeg)
3. Sorts by modification time (newest first)
4. Loads and displays all found images

**Example folder structure:**
```
Sample_Name/
├── G/
│   ├── 1/
│   │   ├── measurement_001.txt
│   │   ├── measurement_002.txt
│   │   └── sweep_analysis/
│   │       ├── iv_curve_plot.png
│   │       ├── hysteresis_plot.png
│   │       └── resistance_plot.png
│   └── 2/
│       └── ...
```

In this example, the Gallery and Overlay tabs would display all three PNG files from the `sweep_analysis` folder.

---

## Technical Details

### Gallery Tab Implementation
- Uses QGridLayout with 3 columns for responsive grid
- Images scaled to max 400x300 pixels while maintaining aspect ratio
- QScrollArea for smooth scrolling through large collections

### Overlay Tab Implementation
- Uses QPainter to composite multiple images
- ARGB32 format for proper alpha blending
- Centered alignment for images of different dimensions
- Maximum display size: 1200x900 pixels (scaled with aspect ratio)

---

## Usage Example

```python
from tools.device_visualizer import launch_visualizer

# Launch with auto-loaded sample
launch_visualizer('/path/to/sample')
```

Or from command line:
```bash
python device_visualizer_app.py --sample /path/to/sample
```

---

## Requirements

- PyQt5
- matplotlib
- numpy
- pathlib (standard library)

---

## Version History

### v1.1.0 (2026-02-09)
- Added Gallery tab for viewing all plot images in a grid
- Added Overlay tab for comparing plots with transparency
- Enhanced keyboard shortcuts (Ctrl+5, Ctrl+6)
- Improved file discovery for plot images

### v1.0.0
- Initial release with Overview, Plots, Metrics, and Classification tabs

---

## Contributing

When adding new tabs or features:
1. Create tab widget in `widgets/` folder
2. Import and instantiate in `main_window.py`
3. Add to `_on_device_selected()` to receive device updates
4. Update keyboard shortcuts and help documentation
5. Export from `widgets/__init__.py`

---

## License

© 2026 Switchbox GUI Team
