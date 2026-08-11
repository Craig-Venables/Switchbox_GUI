# AGENTS.md

## Cursor Cloud specific instructions

Switchbox_GUI is a **Python 3 Tkinter desktop application** for semiconductor/memristor device
characterization in a physics lab. There is **no web server, database, or authentication** — it is a
local GUI that talks to lab instruments over VISA/serial. When no hardware is present, the app and its
measurements fall back to built-in **simulation**, so it can run fully end-to-end in this VM.

### Environment layout
- Dependencies are installed into a virtualenv at `.venv` (gitignored). Activate with
  `source .venv/bin/activate`, or call binaries directly via `.venv/bin/python`.
- The repo pins Python 3.10/3.11 (see `SETUP.md`), but only **Python 3.12** is available here. The
  pinned `numpy`/`matplotlib`/`pandas` install fine on 3.12; `scipy`/`seaborn`/`pytest` are `>=`
  pinned and resolve to newer versions. This is expected and does not affect the app or tests.
- System packages required (already provisioned in the VM snapshot, not in the update script):
  `python3.12-venv`, `python3-tk` (Tkinter — required for the GUI), and `xvfb`.

### Running the app (GUI)
- A virtual X display is already running at `DISPLAY=:1` (XFCE desktop). Launch the app with:
  `DISPLAY=:1 python main.py` (from an activated venv). The window is titled
  "Device Selection & Quick Scan".
- Hello-world / smoke flow: open the **Quick Scan Results** tab, set a non-`Manual` Multiplexer
  (e.g. `Electronic_Mpx`) so the multiplexer manager initializes, then click **Run Scan**. With no
  hardware, it logs simulated per-device current readings (e.g. `A3: 4.978e-07 A`) and finishes at
  "Complete". Standalone tool launchers are listed in `SETUP.md` §8.

### Tests / lint / build
- Tests: `python -m pytest tests -q` (no hardware or extra setup needed).
- **Pre-existing test failures unrelated to environment setup** (do not treat as env breakage):
  - `tests/test_check_connection_stream.py` — collection `ImportError` (imports
    `latest_sample_from_buffers`, removed from `run_check_connection_stream.py`).
  - `tests/test_sample_gui_quick_scan.py` — references `gui.sample_gui.BASE_DIR`, but `BASE_DIR`
    now lives in `gui/sample_gui/config.py`.
  - `tests/test_plot_updaters.py::test_plot_updaters_populate_live_plots` — timing-sensitive
    threading assertion on the log-log plot line.
- No linter is configured (no ruff/flake8/pylint/pyproject). For a syntax check use
  `python -m compileall main.py gui Measurements analysis plotting`. Note: some non-core hardware
  scripts under `Equipment/` (e.g. `Equipment/Moku/test scripts/`, folders prefixed `Ignore---`)
  contain intentional/broken syntax and are not part of the app import path.
- Build (optional, Windows-focused): PyInstaller specs (`build_exe.py`, `build_pulse_testing_gui.py`);
  not needed for development.
