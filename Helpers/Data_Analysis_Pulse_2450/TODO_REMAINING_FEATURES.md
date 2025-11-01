# TODO: Remaining Features for TSP Data Analysis Tool

## 🎯 HIGH PRIORITY (Requested by User)

### 1. Multi-Format File Support
- [ ] **PMU Simple Format** (Time, Voltage, Current, Resistance)
  - Example: `12-set_-2.5v_100e-6-read_0.3v_5e-6.txt`
  - 4 columns: Time, Voltage, Current, Resistance
  - No metadata header
  - Extract parameters from filename
  
- [ ] **Endurance Format** (Iteration, Time, R_Reset, R_Set)
  - Example: `15-Endurance-2.5v_100E-6x30_.txt`
  - Columns: Iteration #, Time (s), Resistance (Reset), Resistance (Set)
  - Plot HRS/LRS separately
  - Calculate switching window
  
- [ ] **IV Sweep Format** (Voltage, Current, Time)
  - Example: `26-FS-1.5v-0.05sv-0.01sd-Py-St_v1-5.txt`
  - 3 columns: Voltage, Current, Time
  - Hysteresis plotting
  - Forward/reverse sweep detection

### 2. Statistics Panel
- [ ] Create statistics tab/panel
- [ ] Basic stats (mean, median, std dev, min, max)
- [ ] HRS/LRS detection and values
- [ ] Switching window calculation
- [ ] **Relaxation time calculation** (exponential fit)
- [ ] Initial read reference value
- [ ] Export stats to CSV

### 3. Initial Read Reference
- [ ] Detect first measurement as initial read
- [ ] Calculate ΔR = R - R₀
- [ ] Calculate ΔR/R₀ (percentage change)
- [ ] Option to plot relative to initial
- [ ] Show R₀ in stats panel

### 4. Multi-Axis Plotting (R + I together)
- [ ] Add checkbox "Show Current (dual axis)"
- [ ] Plot Resistance on left Y-axis
- [ ] Plot Current on right Y-axis
- [ ] Different colors/styles for each
- [ ] Synchronized X-axis zoom/pan
- [ ] Legend shows both

---

## 📊 MEDIUM PRIORITY (Nice to Have)

### 5. Multi-Panel Layout Creator
- [ ] New tab: "Multi-Panel Layout"
- [ ] Grid selector (1x1, 2x1, 1x2, 2x2, 3x2, 3x3)
- [ ] Drag-drop datasets to panels
- [ ] Shared axes option
- [ ] Independent axes option
- [ ] Export entire multi-panel figure
- [ ] Save/load layout presets

### 6. Batch Processing
- [ ] "Batch Process" dialog
- [ ] Select folder recursively
- [ ] Apply same plot settings to all
- [ ] Auto-generate plots for all files
- [ ] Create summary report (CSV with stats)
- [ ] Progress bar for large batches
- [ ] Log file of processed files

### 7. Enhanced Data Analysis
- [ ] Moving average filter
- [ ] Savitzky-Golay smoothing
- [ ] Data binning/resampling
- [ ] Peak detection
- [ ] Baseline subtraction
- [ ] Rate of change (dR/dt)

### 8. Advanced Visualization
- [ ] Colormap for cycle number
- [ ] 3D plots (for parameter sweeps)
- [ ] Heatmaps (endurance over time)
- [ ] Histogram of resistance values
- [ ] Box plots for distributions

---

## 🔧 LOW PRIORITY (Future Enhancements)

### 9. Origin Export
- [ ] Research Origin file format (.opj)
- [ ] Export data in Origin-compatible format
- [ ] Preserve metadata and labels
- [ ] Multi-sheet export

### 10. Plot Templates
- [ ] Save current plot settings as template
- [ ] Load template to apply settings
- [ ] Share templates between users
- [ ] Built-in templates for common cases

### 11. Automated Reporting
- [ ] Generate PDF report with plots
- [ ] Include statistics tables
- [ ] Customizable report template
- [ ] Batch generate reports

### 12. Data Filtering
- [ ] Remove outliers (IQR method)
- [ ] Manual point selection/removal
- [ ] Filter by time range
- [ ] Filter by value threshold

### 13. Comparison Tools
- [ ] Side-by-side plot comparison
- [ ] Difference plots (A - B)
- [ ] Ratio plots (A / B)
- [ ] Overlay with transparency

### 14. Annotations
- [ ] Add text labels to plot
- [ ] Add arrows/lines
- [ ] Highlight regions
- [ ] Save annotations with plot

---

## 🐛 BUG FIXES COMPLETED

- [x] Fixed empty file warnings
- [x] Fixed QTableWidgetItem placeholder error
- [x] Fixed recursion in settings save
- [x] Made UI scrollable for small screens

## ⚠️ KNOWN ISSUES / BUGS

### Annotation System
- [ ] **Annotations not working correctly** - Needs debugging and fixes
  - Issue: Annotations may not be adding/displaying properly
  - Status: Needs investigation
  - Priority: Medium (feature exists but needs fixing)

---

## ✅ COMPLETED FEATURES

- [x] TSP file parsing
- [x] File browser with filtering
- [x] Multi-select files
- [x] Real-time preview
- [x] Custom label editor
- [x] Custom sample names
- [x] Interactive plotting
- [x] Dataset visibility toggle
- [x] Plot customization (line width, markers, grid, legend)
- [x] Background color picker
- [x] Transparent export
- [x] Data cropping
- [x] Data normalization
- [x] Y-axis offset
- [x] Manual axis ranges
- [x] Export PNG/PDF/TXT
- [x] Log scale
- [x] Dark theme

---

## 📝 IMPLEMENTATION NOTES

### File Format Parsers Needed

1. **PMU Simple**: 
   - No header, start reading from line 1
   - Tab or space delimited
   - Auto-detect from column count and headers

2. **Endurance**:
   - Header row with column names
   - Extract cycles and resistance states
   - Need special plotting for HRS/LRS

3. **IV Sweep**:
   - Voltage-Current data
   - Detect hysteresis from forward/reverse
   - Calculate parameters (Vset, Vreset, etc.)

### Statistics Calculations

- Use `numpy` for basic stats
- Use `scipy.optimize.curve_fit` for exponential fits
- Relaxation time: fit R(t) = R∞ + (R₀ - R∞)e^(-t/τ)

### Multi-Axis Implementation

- Use matplotlib's `twinx()` for dual Y-axis
- Keep separate line collections
- Handle zoom/pan synchronization

---

## 🎯 SUGGESTED NEXT SESSION

**Phase 1** (1-2 hours):
1. Fix label editor error ✅
2. Add multi-format file support
3. Basic statistics panel

**Phase 2** (1-2 hours):
4. Initial read reference
5. Multi-axis plotting
6. Relaxation time fitting

**Phase 3** (2-3 hours):
7. Multi-panel layout
8. Batch processing

---

## 💡 QUICK WINS (Can do in <30 min each)

- [ ] Add keyboard shortcuts (Ctrl+S for save, etc.)
- [ ] Remember window size/position
- [ ] Add "Recent files" list
- [ ] Export settings to JSON
- [ ] Import settings from JSON
- [ ] Add status bar progress for long operations
- [ ] Add "About" dialog with version info
- [ ] Add tooltips to all controls
- [ ] Add context menu (right-click) on datasets
- [ ] Add "Copy values" for statistics

---

**Last Updated**: 2025-10-31 23:50  
**Version**: 1.0 with Phase 1 Complete  
**Total Remaining**: ~20-25 features  
**Estimated Time**: 15-20 hours for all features

---

## 🚀 TO RESUME DEVELOPMENT

1. Fix label editor (DONE - fixed placeholder issue)
2. Add multi-format parsers (priority)
3. Implement statistics panel
4. Continue with user's priority list

Save this file and continue when ready!

