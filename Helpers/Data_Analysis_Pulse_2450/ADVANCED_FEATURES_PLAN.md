# Advanced Features Implementation Plan

## ✅ Completed
1. **Parser fix** - Silently skip empty/incomplete files
2. **Scrollable UI** - Control panel now scrolls for smaller screens
3. **Label editor dialog** - Created (needs integration)

## 🚧 In Progress - Critical Features

### 1. Custom Labels Integration (HIGH PRIORITY)
- [x] Create label editor dialog
- [ ] Add "Edit Labels" button to dataset controls
- [ ] Store custom labels per dataset
- [ ] Use custom labels in legend
- [ ] Use custom sample names in displays

### 2. Statistics Panel (HIGH PRIORITY)
- [ ] Calculate basic stats (mean, median, std dev, min, max)
- [ ] Calculate HRS/LRS values
- [ ] Calculate switching window
- [ ] Calculate relaxation time (exponential fit)
- [ ] Display in table widget
- [ ] Export stats to CSV

### 3. Initial Read Reference (HIGH PRIORITY)
- [ ] Detect initial read value
- [ ] Calculate change from initial (ΔR, ΔR/R₀)
- [ ] Option to plot relative to initial
- [ ] Show initial read in stats

### 4. Multi-Axis Plotting (MEDIUM PRIORITY)
- [ ] Checkbox to enable dual Y-axis
- [ ] Plot Resistance on left Y, Current on right Y
- [ ] Different colors for each axis
- [ ] Synchronized X-axis

### 5. Multi-Panel Layout Creator (MEDIUM PRIORITY)
- [ ] New tab: "Multi-Panel"
- [ ] Select grid size (2x1, 2x2, 3x2, etc.)
- [ ] Drag/drop datasets to panels
- [ ] Shared or independent axes option
- [ ] Export entire figure

### 6. Batch Processing (MEDIUM PRIORITY)
- [ ] Select folder
- [ ] Choose output settings
- [ ] Process all files automatically
- [ ] Generate summary report
- [ ] Save all plots

## 📋 Implementation Priority

**Phase 1** (Now):
1. Custom labels integration
2. Statistics panel
3. Initial read reference

**Phase 2** (Next):
4. Multi-axis plotting
5. Relaxation time calculation

**Phase 3** (Future):
6. Multi-panel layout
7. Batch processing

## 🎯 Quick Summary for User

The most immediately useful features being implemented:
- ✅ Fixed empty file warnings
- ✅ Scrollable UI for smaller screens  
- 🚧 Edit dataset labels and sample names
- 🚧 View statistics (including relaxation times)
- 🚧 Use initial read as reference

Coming soon:
- Plot R and I together (dual axis)
- Create multi-panel figures
- Batch process folders



