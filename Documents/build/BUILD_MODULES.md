# Switchbox_GUI — modules and PyInstaller checklist

This file lists **Python packages and data** the main application (`main.py` → `gui.sample_gui`) can reach, so a frozen build stays complete. When you add a **new top-level package**, **dynamic import**, or **runtime data path**, update **`build_exe.spec`** (and this table) in the same change.

**Build entry:** repository root `main.py`  
**Spec:** `build_exe.spec` (root)  
**Runtime project root:** `gui/sample_gui/config.py` uses `sys._MEIPASS` when frozen, so **`Json_Files/`** and bundled **`Documents/`** must appear as **`datas`** in the spec (see `build_exe.spec`).

---

## 1. Core application packages (always include)

By default, **`build_exe.spec`** relies on PyInstaller’s import graph starting at **`main.py`** for **`gui/`**, **`Equipment/`**, **`Pulse_Testing/`**, **`Notifications/`**, **`analysis/`**, **`plotting/`**, etc. Optional **`collect_submodules('gui')`** / **`Measurements`** (commented in the spec) pulls every submodule eagerly if a frozen build misses a lazy import.

The spec also defines **`_modules_from_pkg_path()`** so you can uncomment two lines to register **all** `analysis.*` and `plotting.*` modules without running `import analysis` at spec time (useful when lazy paths skip analysis entirely).

| Package / tree | Role | If build misses something |
|----------------|------|-----------------------------|
| **`gui/`** | All Tk front ends: `sample_gui`, `measurement_gui`, `pulse_testing_gui`, `connection_check_gui`, `oscilloscope_pulse_gui`, `motor_control_gui` | Uncomment `collect_submodules` in the spec and/or add the missing submodule to **`hiddenimports`**. |
| **`Measurements/`** | Runners, data saver, SMU/PMU services, Telegram coordinator, optical helpers | Same. |
| **`Equipment/`** | Multiplexers, SMU/PMU drivers, IV managers, optical hardware glue | Same. Optional: exclude unfinished drivers only if nothing imports them. |
| **`analysis/`** | IV classification and aggregators (lazy-imported from measurement GUI) | Uncomment **`_modules_from_pkg_path`** lines in the spec, or add explicit **`hiddenimports`**. |
| **`plotting/`** | Sample/section/device plots used by `analysis` aggregators | Same as `analysis/`. |
| **`Pulse_Testing/`** | Pulse test definitions, 4200 constants, `system_wrapper` (used by `gui/pulse_testing_gui`) | Same. |
| **`Notifications/`** | `TelegramBot` (lazy-imported from sample GUI / Telegram coordinator) | Same. |

---

## 2. Entry script and config on disk

| Path | Purpose | PyInstaller |
|------|---------|-------------|
| **`main.py`** | Application entry | Listed as `Analysis(... scripts=[main.py])`. |
| **`Json_Files/`** | `mapping.json`, `pin_mapping.json`, `Custom_Sweeps.json`, system configs, etc. | **`datas`**: copy tree to `Json_Files` inside the bundle. |
| **`Documents/`** | User-facing and AI-oriented docs (this tree) | **`datas`**: copy whole tree so help text and zips stay complete. |

If you add **new static assets** (icons, images, templates) loaded by path from `BASE_DIR`, add them under **`datas`** with the correct destination folder name.

---

## 3. Dynamic / easy-to-miss imports

Add explicit **`hiddenimports`** strings in `build_exe.spec` when PyInstaller omits them.

| Module string | Why |
|---------------|-----|
| `Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep` | Loaded via `importlib` in `gui/measurement_gui/main.py` (numeric folder name). |
| `matplotlib.backends.backend_tkagg` | TkAgg for embedded plots in the measurement GUI. |
| `PIL._tkinter_finder` | Pillow + Tk image paths in sample GUI device map. |

Optional third-party stacks (only if you use the feature in a build):

- **VISA:** `pyvisa`, `pyvisa_py` (and related backends).
- **Telegram:** `telegram`, `telegram.ext` (and what `python-telegram-bot` requires for your version).

---

## 4. Optional root-level GUIs (try/except in measurement GUI)

`gui/measurement_gui/main.py` may import **`PMU_Testing_GUI`**, **`Advanced_tests_GUI`**, **`Automated_tester_GUI`**, **`Measurement_Plotter`**, **`automated_tests.framework`**. If those packages exist **next to** `main.py` in your tree and you need them inside the exe, add them to **`hiddenimports`** or **`collect_submodules`**. If they are absent, the GUI already tolerates `None`.

---

## 5. Explicitly *not* part of the main app (unless you import them)

| Tree | Note |
|------|------|
| **`Helpers/`** | Legacy / parallel copies; main app does not depend on it for `main.py`. |
| **`tools/`**, **`archive/`**, **`Other/`** | Standalone or historical; do not bundle unless you change the entry script. |
| **`tests/`** | Not required at runtime. |

---

## 6. Maintenance workflow

1. Add or rename a package under the core list → extend **`collect_submodules`** list in `build_exe.spec` if it is a new **top-level** name.
2. Add `importlib.import_module("...")` → add the full dotted path to **`hiddenimports`**.
3. Add files read from disk relative to project root → add **`datas`** entries.
4. Run **`python build_exe.py`**, then launch **`dist/Switchbox_GUI/Switchbox_GUI.exe`** and hit the code path you changed.

For operator-facing build steps, see **[BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md)**. For what the spec file is conceptually, see **[BUILD_EXPLANATION.md](BUILD_EXPLANATION.md)**.

---

## 7. PyInstaller crashes during “Analyzing main.py”

If the build fails with **`IndexError: tuple index out of range`** in **`dis.py`** / **`modulegraph.util.iterate_instructions`**, that is almost always the **Python interpreter** (early **3.10.0** is a known bad case), not your application source. **Upgrade Python** to the latest **3.10.x** or **3.11+**, recreate the venv, reinstall dependencies, and rebuild.

The stock **`build_exe.spec`** keeps aggressive **`collect_submodules('gui')`** / **`Measurements`** **commented out** by default to shorten analysis time; uncomment those lines if the frozen app misses lazy-loaded GUI submodules.
