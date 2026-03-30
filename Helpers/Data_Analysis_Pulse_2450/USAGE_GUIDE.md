# TSP Data Analysis Tool - Complete Usage Guide

A comprehensive guide to using all features of the TSP Data Analysis Tool for analyzing Keithley 2450 pulse test data.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [File Browser Tab](#file-browser-tab)
3. [Plotting Tab](#plotting-tab)
4. [Multi-Panel Layouts](#multi-panel-layouts)
5. [Combined Plots](#combined-plots)
6. [Data Processing](#data-processing)
7. [Annotations](#annotations)
8. [Exporting Data](#exporting-data)
9. [Keyboard Shortcuts](#keyboard-shortcuts)
10. [Tips & Best Practices](#tips--best-practices)

---

## Getting Started

### Launching the Application

1. Navigate to the `Helpers/Data_Analysis_Pulse_2450` directory
2. Run: `python main.py`
3. The application opens with three main tabs:
   - **📁 File Browser**: Browse and select data files
   - **📊 Plotting**: View and analyze your data
   - **⚙️ Batch Processing**: Process multiple files (advanced)

---

## File Browser Tab

### Loading Data Files

**Method 1: Browse Folder**
1. Click the **"📁 Browse..."** button
2. Navigate to your data folder
3. All `.txt` files are automatically loaded

**Method 2: Recent Folders**
- Use the dropdown to quickly access recently opened folders
- Folders are saved automatically for convenience

### Selecting Files

- **Single Selection**: Click a file to select it
- **Multiple Selection**: 
  - **Ctrl+Click**: Add individual files
  - **Shift+Click**: Select a range
- **Select All**: Right-click menu → "Select All"

### File Preview

When you select a file, the right panel shows:
- **Metadata**: Test name, sample, device, parameters, timestamp
- **Test Parameters**: Voltage, pulse width, delays, etc.
- **Thumbnail Plot**: Quick preview of the data
- **Notes**: Any notes saved with the measurement

### Filtering Files

Use the **"Filter by Test Type"** dropdown to show only:
- Specific test types (e.g., "Endurance Test", "Relaxation")
- All files (default)

### Auto-Refresh

Enable **"🔄 Auto-refresh"** to automatically detect new or modified files:
- Checks every 2 seconds
- Updates the file list automatically
- Useful when data is being collected in real-time

### Sending Files to Plotting

**Standard Mode:**
1. Select files (one or multiple)
2. Click **"📊 Plot Selected Files"**
3. Files are loaded into the **currently active plotting tab**

**Append Mode:**
1. Check **"Append to existing plot"**
2. Select files and click **"📊 Plot Selected Files"**
3. Files are added to the current plot without replacing existing data

**💡 Tip**: If you're viewing "Plotting 2" tab, files will go there. If you're on the File Browser tab, they go to the most recently active plotting tab.

---

## Plotting Tab

### Creating Multiple Plotting Tabs

**Method 1: Menu**
- **View → New Plotting Tab** (or **Ctrl+T**)
- Each tab is independent and can hold different datasets

**Method 2: Automatic**
- When you send files from the file browser, they go to the active tab
- If no tab is active, a new one is created automatically

### Managing Datasets

**Dataset List:**
- Shows all loaded datasets with color indicators (●)
- **Double-click** a dataset to toggle visibility (● becomes ○)
- Invisible datasets are grayed out

**Dataset Controls:**
- **Edit Label**: Double-click dataset name to edit
- **Edit Sample**: Change sample name for better organization
- **Remove**: Remove a dataset from the plot
- **Clear All**: Remove all datasets

### Plot Customization

**Plot Settings:**
- **Line Width**: 0.5-5.0 (adjust for clarity)
- **Marker Size**: 0-12 (0 = no markers)
- **Grid**: Toggle grid lines
- **Legend**: Show/hide legend
- **Log Scale**: Use logarithmic Y-axis

**Background Color:**
- Click the color button to change plot background
- Useful for presentations or matching your style

**Axis Configuration:**
- **X-Axis**: Time, Measurement Number, Voltage, etc.
- **Y-Axis (Left)**: Resistance, Current, Voltage, etc.
- **Y-Axis (Right)**: Optional second Y-axis for dual measurements
- **Enable Right Y**: Check to activate dual-axis plotting

**Axis Ranges:**
- **Auto-scale**: Automatically fits data (default)
- **Manual**: Set custom min/max values
- Use spin boxes to adjust ranges precisely

### Interactive Plot Navigation

**Toolbar Controls:**
- **Home**: Reset zoom to original view
- **Back/Forward**: Navigate zoom history
- **Pan**: Click and drag to pan
- **Zoom**: Click and drag to zoom to rectangle
- **Configure**: Adjust subplot spacing
- **Save**: Quick save dialog

**Zoom Tips:**
- **Mouse Wheel**: Zoom in/out at cursor position
- **Right-click + Drag**: Pan the plot
- **Middle-click**: Reset view

---

## Multi-Panel Layouts

### Single Panel Mode (Default)

- **All datasets overlaid** on the same graph
- Best for comparing multiple measurements directly
- Default layout: **"Single Panel (1×1) - All Overlaid"**

### Multi-Panel Mode

**Selecting Layout:**
1. Open **"📐 Multi-Panel Layout"** section
2. Choose from:
   - **2 Panels (2×1)**: Two panels stacked vertically
   - **2 Panels (1×2)**: Two panels side-by-side
   - **4 Panels (2×2)**: 2×2 grid
   - **6 Panels (3×2)**: 3 rows × 2 columns
   - **9 Panels (3×3)**: 3×3 grid

**Assigning Datasets to Panels:**
1. Select a multi-panel layout
2. Click **"📋 Assign Datasets to Panels"**
3. Check the boxes to assign datasets to specific panels
4. Each dataset can go to multiple panels if needed
5. Click **"Auto-Assign (Sequential)"** for automatic assignment
6. Click **OK** to apply

**Shared Axes:**
- Check **"Share Axes Between Panels"** to use the same axis ranges
- Useful for direct comparison across panels

**💡 Tips:**
- Start with single panel to overlay all data
- Use multi-panel when you need to separate datasets for clarity
- Shared axes help compare magnitude across panels

---

## Combined Plots

### Creating Combined Plots

**Purpose:** Combine multiple plotting tabs into one multi-panel view

**Steps:**
1. Create multiple plotting tabs with different data (Plotting 1, Plotting 2, etc.)
2. Go to **View → Create Combined Plot** (or **Ctrl+Shift+C**)
3. In the dialog, **select which plotting tabs** to include
4. Each selected tab becomes a **panel** in the combined plot
5. Click **OK** to create

### Combined Plot Features

**Layout Selection:**
- **Auto**: Automatically arranges panels (recommended)
- **Manual**: Choose 1×1, 1×2, 2×1, 2×2, 2×3, 3×2, or 3×3
- Change layout anytime using the dropdown

**Panel Reordering:**
- Use the **Panel Order** list to see current order
- Click **⬆ Up** or **⬇ Down** buttons to reorder panels
- Panels are reordered immediately

**Read-Only Mode:**
- Data in combined plots is **locked** (cannot be edited)
- This preserves the original plots from source tabs
- Panels automatically update when you switch to the combined plot tab

**Live Updates:**
- Combined plots refresh automatically when you view them
- Shows the **current state** of source tabs
- Source tabs can be modified independently

**Annotations:**
- Annotations work on combined plots!
- Click on any panel to set annotation position
- Annotations are added to the clicked panel
- Use the annotation toolbar as normal

**💡 Best Practices:**
- Create separate plotting tabs for different experiments
- Use combined plots for publication-ready figures
- Rearrange panels to match your preferred layout
- Annotate panels to highlight important features

---

## Data Processing

### Cropping Data

**Purpose:** Focus on a specific time range or measurement range

**Steps:**
1. Open **"🔧 Data Processing"** section
2. Set **Crop Start** (first point to include)
3. Set **Crop End** (last point to include)
4. Click **"Apply Crop"** or the plot updates automatically
5. Click **"Reset Crop"** to restore full range

**Example:** Crop to points 100-500 to focus on a specific region

### Normalization

**Purpose:** Scale all datasets to 0-1 range for shape comparison

**How it works:**
- Each dataset is scaled: `(value - min) / (max - min)`
- Useful for comparing curves with different magnitudes
- Check **"Normalize"** to enable

### Y-Axis Offset

**Purpose:** Vertically separate overlapping curves

**Steps:**
1. Set **Y Offset** value (e.g., 1000, 5000, etc.)
2. Each dataset is shifted up by this amount
3. Useful for comparing similar curves

### Data Smoothing

**Purpose:** Reduce noise in your data

**Available Methods:**
- **None**: No smoothing (original data)
- **Moving Average**: Simple rolling average
  - **Window Size**: Number of points to average (3-101)
  - Better edge handling with reflection mode
- **Savitzky-Golay**: Preserves features while smoothing
  - **Window Size**: Must be odd (5, 7, 9, etc.)
  - **Polynomial Order**: 1-5 (higher = preserves more features)
- **Gaussian Filter**: Smooth Gaussian convolution
  - **Sigma**: Smoothing strength (0.1-10.0)

**💡 Tips:**
- Start with Moving Average for quick smoothing
- Use Savitzky-Golay for preserving peaks/valleys
- Gaussian filter for gentle smoothing
- Adjust window size based on data density

---

## Annotations

### Adding Annotations

**Available Types:**
1. **Text Box**: Add text labels
2. **Arrow**: Point to specific features
3. **Circle**: Highlight regions
4. **Rectangle**: Mark areas of interest

**Steps:**
1. Open **"✏️ Annotations"** section
2. Select annotation type
3. **Click on the plot** to set position
4. Adjust parameters (color, size, style)
5. Click **"Add Annotation"**

### Arrow Annotations

**Two-Step Process:**
1. Click on plot to set **start point**
2. Click again to set **end point**
3. Or manually enter x2, y2 coordinates

### Annotation Controls

- **Color Picker**: Choose annotation color
- **Font Size** (text): 8-24 pt
- **Line Width** (arrows/shapes): 0.5-5.0
- **Fill** (circles/rectangles): Fill with color or outline only
- **Style** (arrows): →, ←, ↔, ↕

### Managing Annotations

- **Remove Last**: Undo last annotation
- **Clear All**: Remove all annotations (with confirmation)
- **Help**: Detailed instructions dialog

**💡 Tips:**
- Use arrows to point out switching events
- Circles to highlight regions of interest
- Text boxes for labels and explanations
- Different colors for different annotation types

---

## Exporting Data

### Exporting Plots

**PNG Export:**
- **📷 PNG**: Standard PNG (300 DPI)
- **PNG (Trans)**: Transparent background (300 DPI)
- Saves to source file directory by default

**PDF Export:**
- **📄 PDF**: Standard PDF (150 DPI)
- **PDF (Trans)**: Transparent background
- Vector format, scalable

**SVG Export:**
- **🖼️ SVG**: Vector format for publications
- Scalable without quality loss
- Best for figures in papers

**💡 Default Save Location:**
- All exports default to the **source file's directory**
- Filenames are automatically generated from dataset names

### Exporting Data

**TXT Format:**
- Click **"📊 Export Data (TXT)"**
- Exports processed data (with cropping, normalization, etc.)
- Includes headers, units, and metadata comments
- Defaults to source file directory

**CSV Format (Statistics):**
- Calculate statistics first
- Click **"📊 Export Statistics (CSV)"**
- Exports all calculated statistics

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+O** | Open folder dialog |
| **Ctrl+T** | New plotting tab |
| **Ctrl+Shift+C** | Create combined plot |
| **Ctrl+B** | Batch processing dialog |
| **F5** | Refresh files |
| **Ctrl+Q** | Exit application |

---

## Tips & Best Practices

### Workflow Recommendations

1. **Organize Your Data:**
   - Use consistent folder structure
   - Name files descriptively
   - Use the "Append" mode to build comparisons gradually

2. **Creating Publication Figures:**
   - Use single panel for direct comparisons
   - Use multi-panel for separate datasets
   - Use combined plots for multi-experiment figures
   - Add annotations to highlight key features
   - Export as SVG or high-DPI PNG

3. **Comparing Datasets:**
   - Start with all datasets visible (single panel)
   - Use different colors (automatic)
   - Toggle visibility to focus on specific datasets
   - Use Y-offset if curves overlap too much

4. **Smoothing Noisy Data:**
   - Try Moving Average first (simple and fast)
   - Use Savitzky-Golay for preserving features
   - Adjust window size: larger = smoother, smaller = more detail
   - Check both smoothed and original data

5. **Multi-Tab Workflow:**
   - Create separate tabs for different experiments
   - Use combined plots to create summary figures
   - Keep source tabs for detailed analysis
   - Reorder panels in combined plots for best presentation

6. **Data Analysis:**
   - Crop to relevant regions first
   - Calculate statistics for quantitative analysis
   - Use annotations to mark important events
   - Export both plots and data for records

### Common Tasks

**Comparing Two Measurements:**
1. Load both files into the same plotting tab
2. Use single panel mode (default)
3. Both datasets overlay automatically
4. Toggle visibility if needed

**Creating a 4-Panel Figure:**
1. Load 4 datasets
2. Select "4 Panels (2×2)" layout
3. Assign datasets to panels (or use auto-assign)
4. Adjust layout if needed
5. Export as PNG/PDF

**Combining Multiple Experiments:**
1. Create separate plotting tabs (Plotting 1, Plotting 2, etc.)
2. Load different experiments into each
3. Create combined plot (Ctrl+Shift+C)
4. Select tabs to include
5. Rearrange panels as needed
6. Add annotations to highlight features

**Smoothing Noisy Relaxation Data:**
1. Load relaxation measurement
2. Go to Data Processing → Smoothing
3. Select "Savitzky-Golay"
4. Window Size: 5-9 (odd number)
5. Polynomial: 2-3
6. Compare smoothed vs. original

---

## Troubleshooting

**Files not loading:**
- Check file format matches TSP specification
- Ensure files are `.txt` format
- Check file isn't corrupted

**Plot not updating:**
- Check if datasets are visible (not grayed out)
- Verify data processing settings
- Try clicking "Update Plot" or refreshing

**Annotations not working:**
- Click on the plot canvas (not outside)
- Ensure annotation type is selected
- Check that plot has data loaded

**Combined plot not updating:**
- Switch away and back to the combined plot tab
- Source tabs should have data loaded
- Check that source tabs are still open

**Export not working:**
- Check file permissions in target directory
- Ensure sufficient disk space
- Try a different file format

---

## Advanced Features

### Batch Processing

Access via **File → Batch Processing** or **Ctrl+B**

- Process multiple files automatically
- Apply same settings to all files
- Export results in batch
- See Batch Processing tab for details

### Auto-Refresh

Enable in File Browser tab:
- Automatically detects new files
- Updates file list every 2 seconds
- Useful during data collection
- Shows status: "🔄 Auto-refresh active"

### Custom Labels

- Double-click dataset name to edit
- Use descriptive names for clarity
- Labels appear in legend and exports
- Preserved when saving/loading

---

## Support

For issues or questions:
1. Check this guide first
2. Review the README.md for technical details
3. Check file format specification if data won't load
4. Review statistics guide for analysis questions

---

**Version:** 2.0  
**Last Updated:** 2025-01-29  
**Status:** Production Ready ✅




