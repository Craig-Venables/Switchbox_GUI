# Building your executable — short explanation

## What is the spec file?

The repository-root **`build_exe.spec`** file is **only** the PyInstaller recipe. It is **not** shipped inside the application; it tells PyInstaller how to assemble the build.

## What gets included?

**Python code and dependencies**  
Discovered from **`main.py`** plus explicit **`hiddenimports`** and submodule collection defined in **`build_exe.spec`**. A full checklist of packages and edge cases lives in **[BUILD_MODULES.md](BUILD_MODULES.md)**.

**Bundled next to the runtime (under `sys._MEIPASS` when frozen)**  

- **`Json_Files/`** — mapping, pin map, custom sweeps, system configs (editable if you ship the onedir folder).  
- **`Documents/`** — documentation tree (`guides/`, `reference/`, `build/`, `ai/`, `development/`, …).

**Typically excluded unless you change the entry script**  

- **`Helpers/`**, **`tools/`**, **`archive/`**, **`tests/`** — not part of the main `main.py` application.

## How to build

1. Install PyInstaller: `pip install pyinstaller`  
2. From the **repository root**: `python build_exe.py`  
3. Run: `dist/Switchbox_GUI/Switchbox_GUI.exe`

## After building (onedir)

The `dist/Switchbox_GUI/` directory contains the `.exe`, an `_internal` dependency folder, and copies of **`Json_Files`** and **`Documents`** as configured in the spec. Distribute **the entire folder**, not only the `.exe`.

## Distribution

Zip **`dist/Switchbox_GUI/`**, extract on the target PC, run **`Switchbox_GUI.exe`**. Users can edit JSON under **`Json_Files`** without rebuilding.
