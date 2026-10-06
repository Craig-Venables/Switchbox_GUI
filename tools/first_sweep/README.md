# First sweep comparison

Compare the first IV sweep of every device in a sample, and compare that sample with another.

From the Switchbox_GUI repository root:

```powershell
python -m tools.first_sweep
```

## Samples

**Add folders…** uses the same section and device layout as the jump finder. Each folder is one sample. Select it and type a short **Label**, such as `2%`. Uncheck a device to leave it off every figure and out of the Origin tables.

**Opening cutoff** defaults to 0.5 V. The opening-window figure keeps the start of a sweep until the voltage first reaches that value. **Files** defaults to 3: that many measurement files from the start of each device. **Jump ratio** defaults to 10: a step counts when the larger current is at least that many times the smaller. Steps whose smaller current is below 0.1 pA are ignored, so a sweep that passes through zero is not treated as forming.

The file list under the devices is those first files. Uncheck a file to drop that curve. Click a row to draw it in pink on top of the others; the row is shown in bold. **All** and **None** under Files apply to the files in the list.

## Figures

**Opening window** is the default. It draws the start of each checked file, out to the cutoff, with every device on the same axes. One colour is one sample. File 1 is a solid line, file 2 is dashed, and file 3 is dotted. Points with a negative current on that rise are left out, so the line between the remaining points does not go below zero. **Full first sweep** draws the whole first measurement file.

**Metric** plots one number per device, grouped by sample. Polarity and permanently ohmic are counts. The table under the plot lists every checked device. A blank cell means that event was not in the sweeps.

**Sweep evolution** draws absolute current and resistance at the cutoff against sweep number, starting at 1.

Forming is the earliest current jump in sweep order, which is often a later file than the first sweep. The first-sweep jump voltage is kept as its own column. ON/OFF resistance is taken on the first sweep after forming, at the cutoff, from the forward and return branches. Permanently ohmic means every sweep after forming stays a single log-log slope near 1, with no jump and an ON/OFF ratio below 2.

## Origin

**Save for Origin…** writes tab-separated files under `<common parent>\origin data\<name>\`. Import a curve file as tab-delimited text and plot each voltage column against the current column beside it.

- `voltage, current (first <cutoff> V).txt`, the absolute-current file, and the two normalised files. Each kept file is one pair of columns, and only the opening out to the cutoff is included. Unchecked files are left out.
- `index.txt` maps each column name to the measurement path
- `device metrics.txt`, one row per device
- `sweep evolution.txt`, sweep number then current and resistance for each device

Column names include the sample label, the device, the file number, the filename, and the unit. **Save session…** remembers the file count, the cutoff, and which files were unchecked.
