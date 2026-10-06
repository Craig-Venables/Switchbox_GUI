# Loop trend

Finds measurement files that contain many repeated IV loops, and shows how the positive and negative sides change from the first loop to the last.

This is separate from the device variation viewer. It does not use the jump-finder session.

## Run

From the Switchbox_GUI repository root:

```powershell
python -m tools.loop_trend
```

## What it does

**Add folders…** then **Scan**. A file is kept when `split_loops` finds at least **Min loops** cycles inside that one file (default 20). Endurance, retention, and pulse files are skipped.

The list is sorted by the change between the first loop and the last, largest first. Click a row. The left graph is the normalised positive side of every loop. The right graph is the normalised negative side. Early loops are blue and later loops are red.

**Save all loops…** writes twelve Origin files for every measurement in the list, in a folder named after that file:

- `voltage, abs current.txt` and `voltage, current.txt`
- the same two with `(normalised)` — current divided by that sweep's maximum absolute current
- the same four again with `(ps only)` — only `V ≥ 0`
- the same four again with `(ng only)` — only `V ≤ 0`

Each sweep is two columns, `Voltage Sweep 1 (V)` beside `Absolute Current Sweep 1 (A)` or `Current Sweep 1 (A)`. Sweep numbers start at 1. Import one file as tab-delimited text and plot each pair.

Files go in `<common parent of the folders>\origin data\<name you typed>\<measurement>\`.
