# Documentation for AI assistants and tooling

Use this folder as the **entry point** when an automated assistant (Cursor, Copilot, etc.) needs repository context without spelunking the whole tree.

## Where things live

| Topic | Location |
|--------|-----------|
| **End-user guides** (usage, JSON, lab checklist) | [`../guides/`](../guides/) |
| **Architecture & GUI maps** (how Sample / Measurement / child GUIs connect) | [`../reference/`](../reference/) — start with [`../reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md`](../reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md) |
| **Build / PyInstaller** (module inventory, spec file, datas) | [`../build/`](../build/) — see [`../build/BUILD_MODULES.md`](../build/BUILD_MODULES.md) and [`../build/BUILD_INSTRUCTIONS.md`](../build/BUILD_INSTRUCTIONS.md) |
| **Refactors, summaries, internal notes** | [`../development/`](../development/) |
| **Master doc index** | [`../README.md`](../README.md) |

## Naming that trips people up

- **“Measurement GUI”** in docs means the **package** `gui/measurement_gui/`, not legacy `archive/old_code/Measurement_GUI.py`. This is stated at the top of the measurement architecture reference.
- The canonical measurement data package is **`Measurements/`** (with an **e**). A typo duplicate **`Measurments/`** exists for older tooling; the main app uses **`Measurements`**.

## When you change imports or add packages

1. Open [`../build/BUILD_MODULES.md`](../build/BUILD_MODULES.md) and align **`build_exe.spec`** (`hiddenimports`, `datas`, `binaries`) with the new code or assets.
2. Rebuild with `python build_exe.py` from the **repository root** and smoke-test the `dist/Switchbox_GUI/` folder.

## Cursor-specific

- Optional planning notes may appear under **`.cursor/plans/`** in a local workspace. They are **not** required reading for coding tasks; prefer `Documents/reference/` and source code for truth.
