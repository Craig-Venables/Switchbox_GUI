# Building Switchbox_GUI executable

This guide explains how to build a standalone **Windows** executable from the Switchbox_GUI repository.

**Before you change imports or packages**, read **[BUILD_MODULES.md](BUILD_MODULES.md)** and update **`build_exe.spec`** (repository root) in the same commit.

## Prerequisites

- **Python 3.10.11+ or 3.11+** recommended for packaging. **Python 3.10.0** has been observed to hit `IndexError: tuple index out of range` inside `dis.get_instructions` while PyInstaller scans dependencies (after hooks such as `pygments` / `anyio`). If you see that traceback during **Analysis**, upgrade the **patch** version of Python and rebuild.
- Install project dependencies you need inside the exe (at minimum what `main.py` touches). For analysis features, ensure **`scipy`** and **`pandas`** are installed so PyInstaller can trace their imports from `analysis/` and `plotting/`.  
- From the **repository root** (where `main.py` and `build_exe.spec` live):

  ```bash
  pip install pyinstaller
  ```

## Quick start

1. **Build**

   ```bash
   python build_exe.py
   ```

   Or:

   ```bash
   pyinstaller build_exe.spec
   ```

2. **Output (onedir layout)**  
   - Executable: `dist/Switchbox_GUI/Switchbox_GUI.exe`  
   - The **entire** `dist/Switchbox_GUI/` directory must be copied when distributing (internal `_internal` folder and bundled `Json_Files`, `Documents`, etc.).

## Why PyInstaller (not only auto-py-to-exe)?

This project has hardware-related code, many subpackages, JSON-driven behaviour, and lazy imports. A checked-in **`build_exe.spec`** gives repeatable builds and a place to record **`datas`** and **`hiddenimports`**. See also **[BUILD_EXPLANATION.md](BUILD_EXPLANATION.md)**.

## What the spec bundles as data

The root **`build_exe.spec`** copies:

- **`Json_Files/`** → editable configuration next to the executable (same as historical behaviour).  
- **`Documents/`** → this documentation tree (including `guides/`, `reference/`, `build/`, `ai/`, etc.).

If you add new **runtime assets** (icons, templates, extra JSON trees), add them to the `datas` list in **`build_exe.spec`** and document them in **[BUILD_MODULES.md](BUILD_MODULES.md)**.

## Customization

### Hidden imports

If the app raises **`ModuleNotFoundError`** for a library that is only loaded via `importlib` or a rare code path, add the dotted module name to **`hiddenimports`** in **`build_exe.spec`**. **[BUILD_MODULES.md](BUILD_MODULES.md)** lists known lazy edges (e.g. 4200A step sweep module).

### DLLs / drivers

Add tuples to **`binaries`** in the spec when a vendor DLL must sit next to the executable. Match **32-bit vs 64-bit** to your Python build.

### Icon

Set `icon='path/to/icon.ico'` on the **`EXE(...)`** call in **`build_exe.spec`** (path relative to the spec file or absolute).

## Troubleshooting

| Symptom | What to check |
|--------|----------------|
| Missing module at runtime | **`hiddenimports`** in **`build_exe.spec`**; see **[BUILD_MODULES.md](BUILD_MODULES.md)** |
| JSON / config not found | **`datas`** includes **`Json_Files`**; frozen code uses **`sys._MEIPASS`** (see `gui/sample_gui/config.py`) |
| Huge executable | Trim optional **`collect_submodules`** packages only if unused; prefer virtualenv with fewer site-packages |
| Analysis / plots fail inside exe | Ensure **`scipy`**, **`pandas`**, **`matplotlib`** were installed **on the build machine** so analysis can be analyzed and bundled |

## Testing and distribution

1. Run `dist/Switchbox_GUI/Switchbox_GUI.exe` on the build PC.  
2. Copy the **whole** `dist/Switchbox_GUI/` folder to a PC **without** Python and repeat.  
3. Zip that folder for distribution.

**Note:** Built executables are **platform-specific** (Windows build → Windows exe).

## Advanced layouts

The default spec uses a **onedir** build (recommended for large scientific stacks). Switching to **onefile** is possible but increases startup time and complicates shipping `Json_Files`; follow [PyInstaller documentation](https://pyinstaller.org/) if you need that layout.
