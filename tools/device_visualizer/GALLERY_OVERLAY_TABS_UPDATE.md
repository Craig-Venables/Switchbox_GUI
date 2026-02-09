# Device Visualizer: Gallery and Overlay Tabs Update

## Summary

Added two new tabs to the Device Analysis Visualizer for viewing plot images from device folders:
1. **Gallery Tab** - Scrollable grid view of all plot images
2. **Overlay Tab** - Stacked view of plots with transparency control

## Files Added

### 1. `widgets/gallery_tab.py`
**Purpose:** Display all plot images in a scrollable 3-column grid

**Key Features:**
- Automatic discovery of PNG/JPG/JPEG images in device folder
- Responsive grid layout (3 columns)
- Image thumbnails (max 400x300px)
- Displays filename and relative path
- Refresh button to reload plots
- Sorts by modification time (newest first)

**Main Methods:**
- `update_device(device)` - Load and display plots for selected device
- `_discover_plot_images(device)` - Recursively find image files
- `_display_plots()` - Render grid of plot thumbnails
- `_create_plot_widget(plot_path)` - Create individual plot display widget

---

### 2. `widgets/overlay_tab.py`
**Purpose:** Display multiple plot images overlaid on top of one another

**Key Features:**
- Overlay multiple plots with adjustable transparency
- Opacity slider (10%-100%)
- Individual layer toggle controls
- Show All / Hide All buttons
- Centered alignment for different sized plots
- Composite rendering using QPainter

**Main Methods:**
- `update_device(device)` - Load and overlay plots for selected device
- `_discover_plot_images(device)` - Find all plot images
- `_load_pixmaps()` - Load images as QPixmaps
- `_render_overlay()` - Composite multiple images with transparency
- `_on_opacity_changed(value)` - Update opacity and re-render
- `_on_layer_selection_changed(index)` - Toggle individual layers

---

## Files Modified

### 3. `widgets/main_window.py`
**Changes:**
- Imported `GalleryTab` and `OverlayTab`
- Created instances of both tabs (lines 128-129)
- Added tabs to tab widget with emoji icons (lines 136-137)
- Added keyboard shortcuts Ctrl+5 and Ctrl+6 (lines 204-212)
- Updated device selection handler to update new tabs (lines 353-354)
- Updated keyboard shortcuts help dialog (lines 415-418)

**Keyboard Shortcuts Added:**
- `Ctrl+5` - Navigate to Gallery tab
- `Ctrl+6` - Navigate to Overlay tab

---

### 4. `widgets/__init__.py`
**Changes:**
- Imported `GalleryTab` and `OverlayTab`
- Added to `__all__` export list
- Updated module docstring

---

## Files Created (Documentation)

### 5. `README.md`
Comprehensive documentation including:
- Overview of all tabs
- Detailed Gallery tab documentation
- Detailed Overlay tab documentation
- Keyboard shortcuts reference
- File discovery strategy
- Technical implementation details
- Usage examples
- Version history

---

## Usage

### Gallery Tab (Ctrl+5)

1. Select a device from the device list
2. Navigate to Gallery tab
3. Scroll through plot images in grid layout
4. Click Refresh to reload if new plots are generated

**Perfect for:**
- Browsing all plots for a device
- Quick overview of available visualizations
- Identifying specific plots by filename

### Overlay Tab (Ctrl+6)

1. Select a device from the device list
2. Navigate to Overlay tab
3. Adjust opacity slider (30-70% recommended for multiple plots)
4. Click layer names in dropdown to toggle individual plots
5. Use Show All / Hide All for quick control

**Perfect for:**
- Comparing multiple measurements
- Identifying patterns across different sweeps
- Overlaying before/after plots
- Visual alignment and comparison

---

## Technical Implementation

### Image Discovery Strategy
Both tabs use the same discovery strategy:
1. Determine device folder from `DeviceData.measurements[0].file_path.parent`
2. Fallback to `DeviceData.raw_data_files[0].parent`
3. Recursively search for image files using `Path.rglob()`
4. Support extensions: `*.png`, `*.PNG`, `*.jpg`, `*.JPG`, `*.jpeg`, `*.JPEG`
5. Sort by modification time (newest first)

### Gallery Tab Implementation
- **Layout:** `QGridLayout` with 3 columns
- **Scrolling:** `QScrollArea` with `widgetResizable=True`
- **Thumbnails:** Scaled to max 400x300px maintaining aspect ratio
- **Display:** Shows filename and relative path below each image

### Overlay Tab Implementation
- **Compositing:** Uses `QPainter` with `CompositionMode_SourceOver`
- **Image Format:** ARGB32 for proper alpha blending
- **Opacity:** Applied per-layer using `painter.setOpacity()`
- **Alignment:** Centers images of different sizes on white background
- **Max Size:** Scales composite to 1200x900px if larger

---

## Integration Points

### Device Selection
When a device is selected in `main_window._on_device_selected()`:
```python
self.gallery_tab.update_device(device)
self.overlay_tab.update_device(device)
```

### Tab Navigation
Tab indices (for keyboard shortcuts):
- 0: Overview
- 1: Plots
- 2: Metrics
- 3: Classification
- 4: Gallery (Ctrl+5)
- 5: Overlay (Ctrl+6)

---

## Testing Recommendations

1. **Test with no plot images**
   - Both tabs should show appropriate "no images found" message

2. **Test with single plot**
   - Gallery: Should display single image centered
   - Overlay: Should display at 100% opacity

3. **Test with multiple plots**
   - Gallery: Should display in 3-column grid
   - Overlay: Should composite with adjustable opacity

4. **Test with different image sizes**
   - Gallery: Thumbnails should maintain aspect ratio
   - Overlay: Images should be centered on white background

5. **Test layer toggling in Overlay**
   - Individual layers should toggle on/off
   - Show All / Hide All should work correctly

6. **Test keyboard shortcuts**
   - Ctrl+5 should navigate to Gallery
   - Ctrl+6 should navigate to Overlay

---

## Future Enhancements

### Gallery Tab
- [ ] Click to enlarge image in popup/dialog
- [ ] Export selected images
- [ ] Filter by image type or folder
- [ ] Sort options (name, date, size)
- [ ] Adjustable thumbnail size
- [ ] Image metadata display (dimensions, file size)

### Overlay Tab
- [ ] Individual opacity control per layer
- [ ] Blend mode options (multiply, screen, etc.)
- [ ] Layer reordering
- [ ] Export composited image
- [ ] Pan and zoom controls
- [ ] Alignment tools (auto-align by features)
- [ ] Difference mode to highlight changes

---

## Known Limitations

1. **Large Image Count:** Performance may degrade with 50+ images (both tabs)
2. **Memory Usage:** All images loaded into memory simultaneously
3. **File Size:** Very large images (>10MB) may be slow to load
4. **Image Formats:** Only PNG, JPG, JPEG supported (no GIF, BMP, SVG)

---

## Version

**Version:** 1.1.0  
**Date:** 2026-02-09  
**Author:** Switchbox GUI Team

---

## Related Files

- `widgets/overview_tab.py` - Original overview tab with heatmap
- `widgets/plots_tab.py` - Original plots tab with matplotlib
- `data/device_data_model.py` - Device data structure
- `data/data_discovery.py` - File discovery utilities
- `utils/plot_utils.py` - Matplotlib plotting utilities
