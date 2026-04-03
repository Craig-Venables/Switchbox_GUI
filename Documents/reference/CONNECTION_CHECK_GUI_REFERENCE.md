# Connection Check GUI — Architecture Reference

> **Documentation accuracy:** These notes are a snapshot of the repository at the time they were written. Thresholds, timing, and instrument APIs evolve. Use this for **orientation**; verify against `gui/connection_check_gui/main.py` for exact behavior.

---

## 1. General overview

### 1.1 Purpose

The **Connection Check GUI** (`gui/connection_check_gui/`) is a **small `tk.Toplevel`** tool for **probe contact verification**. It:

1. Applies a **fixed small DC bias** (legacy path: **0.2 V**, compliance **0.1 A**) and enables SMU output.  
2. Runs a **background thread** that repeatedly measures **current**.  
3. Plots **|I| vs time** on a **log Y-axis** with a **threshold line**.  
4. Optionally plays **alerts** when **|I| ≥ threshold** (default **1 nA**): instrument **`beep()`** when available, else **Windows `winsound`** (or terminal bell).

It is optimized for **lowering probes** onto devices and seeing current appear without starting a full measurement.

### 1.2 Entry points

- **From Measurement GUI:** User clicks **Check Connection**; implementation passes **`master=self.master`** and **`keithley=self.keithley`** (the connected SMU adapter or manager—whatever object exposes the methods below).  
- **Standalone / tests:** `CheckConnection(tk.Tk(), mock_or_real_keithley)` — see `if __name__ == "__main__"` block with `MagicMock`.

Exported symbol: **`CheckConnection`** from `gui.connection_check_gui`.

### 1.3 Package layout

```
gui/connection_check_gui/
├── __init__.py       # exports CheckConnection
├── main.py           # entire implementation (~580 lines)
└── README.md
```

There is **no** separate `layout` or `logic` module; everything lives in **`main.py`**.

---

## 2. Main class: `CheckConnection`

### 2.1 Construction

```text
CheckConnection(master: tk.Misc, keithley: Any)
```

- Creates **`self.top = tk.Toplevel(master)`**, title **Connection Check - Pin Lowering Assistant**, geometry **800×750**.  
- Detects **4200A** via `str(getattr(keithley, "smu_type", "")).lower()` containing **`"4200a"`** → sets **`self._is_4200a`** (used for beep fallback: 4200A often has **no hardware beep**).  
- Initializes **`current_threshold_a`**, **`time_data` / `current_data`**, flags **`check_connection_window`**, **`noise_already`** (single-beep latch).  
- **`create_ui()`** then **`start_measurement_loop()`**.

### 2.2 Two measurement backends (automatic)

The worker thread chooses a path at startup:

1. **Helper path (4200A-style):** If **`keithley.connection_check_sample`** is callable, or the same on **`keithley.instrument`**, each loop calls **`helper()`** and reads **`sample["current"]`** and wall-clock elapsed time.  
2. **Legacy path:** **`set_voltage(0.2, 0.1)`**, **`enable_output(True)`**, then **`measure_current()`**. Tuple/list returns use **index `[1]`** as current (4200-style); scalar → `float`.

If the helper throws, the code **disables the helper** and **falls back** to the legacy path (with re-init).

**Loop interval:** **`time.sleep(0.05)`** between samples in the success path (~20 Hz); errors may backoff to **0.5 s**.

### 2.3 UI sections

- **Top bar** — title + **Help / Guide** (`_show_help` scrollable instructions).  
- **Plot** — matplotlib `Figure` embedded via `FigureCanvasTkAgg`; updated in **`update_plot`** (full redraw: `ax.clear()` each time).  
- **Controls** — sound on/off, continuous vs single beep, **Reset Alert**, threshold entry + **Update**, status label, **Save Graph**, **Close**.

### 2.4 Alert logic

- **Single mode:** When **`|I| ≥ threshold`** and **`noise_already`** is false → **`on_spike_detected(continuous=False)`** sets **`noise_already = True`** after success.  
- **Continuous mode:** Beep on **every** reading above threshold.  
- **`on_spike_detected`:** Tries **`keithley.beep(freq, duration)`**; if 4200A or beep failed → **`_play_system_beep`** (`winsound.Beep` or `\a`).

### 2.5 Shutdown

- **`close_window`:** sets **`check_connection_window = False`** (stops loop), disables output **only if not using connection helper** (`_connection_helper_active`), destroys **`self.top`**.  
- **Legacy path end:** when loop exits, may call **`keithley.shutdown()`** (not used for helper path—verify current file if instrument state matters).

---

## 3. Instrument contract (expected methods)

The `keithley` object should support (depending on path):

| Method / attribute | Used when |
|--------------------|-----------|
| `connection_check_sample()` → dict with `"current"` | Helper path |
| `set_voltage(v, icc)`, `enable_output(bool)`, `measure_current()` | Legacy path |
| `beep(freq, duration)` | Alerts (optional) |
| `shutdown()` | Legacy cleanup after loop |
| `instrument.connection_check_sample` | Fallback lookup for nested instrument |

Actual types are often **`SMUAdapter`** or **`IVControllerManager`** wrappers from the measurement stack—behavior is normalized in the measurement layer where possible.

---

## 4. Defaults (verify in code)

| Setting | Typical value in implementation |
|---------|--------------------------------|
| Bias (legacy) | 0.2 V, 0.1 A compliance |
| Sample period | ~50 ms |
| Default threshold | 1e-9 A |
| Plot Y scale | log10 of \|I\| |

---

## 5. Relationships

```
MeasurementGUI.check_connection()  [or equivalent button handler]
        │
        ▼
CheckConnection(master, keithley)
        │
        └─► Background thread → plot + optional beeps
```

---

## 6. Related documentation

- **`gui/connection_check_gui/README.md`** — operator-focused summary  
- **`Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md`** — parent GUI  

---

*Other GUI references in `Documents/reference/`: `MOTOR_CONTROL_GUI_REFERENCE.md`, `PULSE_TESTING_GUI_REFERENCE.md`, `OSCILLOSCOPE_PULSE_GUI_REFERENCE.md`.*
