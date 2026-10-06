swithin # Device variation viewer

PyQt tool that shows how a device's IV sweeps change before and after filament forming, how devices in one sample differ from each other, and how two samples (for example a 2% film and a 3% film) compare.

It does not decide which current steps are real jumps. Load a session saved from **filament jump finder**. Accepted jumps set the forming file. Rejected jumps do not.

## Run

From the Switchbox_GUI repository root:

```powershell
python -m tools.device_variation
python -m tools.device_variation --session "C:\path\to\filament_jump_session.json"
```

Requires Python 3.9+ with PyQt5, matplotlib, and numpy (same as the jump finder).

## What you need first

In the jump finder, review the candidates and use **Save Session…**. That JSON stores:

- the sample folders
- each Jump / Rejected decision (`file path::step index`)
- the ratio and voltage-window settings that were on screen

**Load jump session…** reads that file, loads the curves, and applies the same filter. A step counts only when it still passes those settings and you left it as a Jump. Steps you never marked stay accepted, which is the same rule the jump finder uses.

The forming file is the earliest included sweep that still has an accepted jump. Sweeps before it are pre. That file and later sweeps are post. A device with no accepted jump is unformed.

**Add folders…** can load extra samples. Those folders are not split until they are part of a jump session. The tool does not invent a threshold of its own.

Decision keys are absolute paths. If a sample folder has moved, the session will not match, same as reloading it in the jump finder.

## Normalization

One control applies to every tab:

| Mode | What it does |
|------|----------------|
| Divide by max \|I\| | Default. Compares shape. A high-current device does not hide the rest. |
| Raw current | Keeps magnitude. |
| log10(\|I\|) | Log magnitude. |
| Divide by \|I\| at read voltage | Shape relative to a fixed bias. Default read voltage is 0.5 V. |

## Tabs

**Device.** One device. **Lifetime** draws every included sweep on one plot, coloured from early (cool) to late (warm). Click a file to draw that sweep in pink. Uncheck a file to drop it; the device plot updates immediately. **Pre / post** is the other plot mode. **Split before file** overrides the first accepted jump for that device only.

**Sample.** One sample. Each line is one real sweep, the same loop you see on the Device tab. Uncheck a device in the list to leave it off this plot. With **All devices**, **Pre sweep** and **Post sweep** pick the same kind of file on every checked device (last sweep before forming, the forming sweep, and so on). **Also show raw current** keeps that plot and adds a second row in amperes, so the devices can differ in size as well as shape. **Positive trend** and **Negative trend** use one measurement file. **Min loops** (default 20) is the number of repeated cycles inside that file. Click the file in the sweep list. Each line is one voltage side of one loop, scaled by that side's maximum current, coloured from the first loop (blue) to the last (red). **Save loops…** writes twelve Origin files for the clicked measurement. Sweep numbers start at 1. Column names are long, with units, for example `Voltage Sweep 1 (V)` and `Absolute Current Sweep 1 (A)`.

**Compare.** The **Figure** menu switches the plot. **Medians** is one device lifetime under the sample bands; pick that device in the table (highest memristive score first) and edit the label to something like `2%`. **Yield** is formed, unformed, and memristive counts for every device in each folder. **Read current** is `|I|` at the read voltage on the sweep chosen by the Sample tab's Pre and Post menus, one point per checked device. **Sweep overlay** draws those same real sweeps, one colour per sample. Unchecked devices stay off the read-current and overlay figures.

## Save session and Origin

**Save session…** / **Load session…** stores the jump-session path, folders, unchecked files, unchecked devices, split overrides, sample labels, chosen compare devices, the Compare figure, the Pre/Post sweep choice, and the other plot settings.

**Save for Origin…** writes tab-separated files under `origin data/<name>/` next to the sample folders. Each lifetime file is paired columns, `V_…` and `Y_…`, one pair per sweep, in sweep order. Import as tab-delimited text and plot each pair as voltage against normalised current. A matching `_index.txt` names the sweeps. `sample_*_band.txt` holds the median and quartile curves. **Save loops…** writes twelve tab-separated files in a folder named after the measurement. Each file is one plot: voltage against absolute current, voltage against current, and the same two with current divided by that sweep's maximum absolute current. Those four are repeated for the full loop, the positive side only (`ps only`, `V ≥ 0`), and the negative side only (`ng only`, `V ≤ 0`). Import a file as tab-delimited text and plot each voltage column against the current column beside it.

## Layout

```text
device_variation/
  __init__.py
  __main__.py
  core.py          # session apply, split, normalize, voltage bins, distance
  gui.py
  README.md
```
