# Pulse Testing Backend

Multi-system pulse testing: one interface, multiple instruments (Keithley 2450, 4200-SCS, 2400). The GUI filters tests by connected system; support is defined here.

## Unified script locations

All instrument **controllers and scripts** live under **Equipment/SMU_AND_PMU/** per instrument. **Pulse_Testing/systems/** contains only **adapters** that implement `BaseMeasurementSystem` and delegate to those scripts.

| System | Adapter (this repo) | Scripts & controller (Equipment) |
|--------|---------------------|-----------------------------------|
| **Keithley 2400** | `Pulse_Testing/systems/keithley2400.py` | `Equipment/SMU_AND_PMU/keithley2400/scpi_scripts.py`, `controller.py` |
| **Keithley 2450** | `Pulse_Testing/systems/keithley2450.py` | `Equipment/SMU_AND_PMU/keithley2450/tsp_scripts.py`, `tsp_controller.py` (and `tsp_sim_scripts.py` for sim) |
| **Keithley 4200 PMU** | `Pulse_Testing/systems/keithley4200_pmu.py` → `keithley4200_core.py` | Same KXCI stack as below |
| **Keithley 4200 SMU** | `Pulse_Testing/systems/keithley4200_smu.py` → `keithley4200_core.py` | Same KXCI stack as below |
| **Keithley 4200 custom** | `Pulse_Testing/systems/keithley4200_custom.py` → `keithley4200_core.py` | Connect + setup notes; no tests in GUI |
| **Keithley 4200A (legacy id)** | `Pulse_Testing/systems/keithley4200a.py` (subclasses PMU) | Same as PMU row |

**Equipment for all 4200 profiles:** `Equipment/SMU_AND_PMU/keithley4200/kxci_scripts.py`, `kxci_controller.py`; C code under `4200A/C_Code_with_python_scripts/`.

Each thin adapter file points at **`keithley4200_core.py`**, where **all** 4200 test methods are implemented once. To add or change low-level KXCI behavior, edit **Equipment** scripts; the core adapter only converts units and delegates.

### Keithley 4200 profiles (PMU vs SMU vs custom)

The three dropdown entries (`keithley4200_pmu`, `keithley4200_smu`, `keithley4200_custom`) use the **same** Python class stack and GPIB connection. They differ only in:

- **`test_capabilities.py`** — which tests appear for that profile (fast interleaved PMU vs SMU/optical vs none).
- **Pulse GUI timing** — µs defaults for PMU/legacy ids (`Pulse_Testing/keithley4200_constants.py`: `KEITHLEY4200_PMU_TIMING_SYSTEMS`).
- **Optical + read on 4200** — uses the SMU bias-timed read path; select **`keithley4200_smu`** (`KEITHLEY4200_SMU_OPTICAL_SYSTEMS`).

**`keithley4200a`** remains a **legacy** system id with the **same capability row as PMU** (saved configs / scripts). Prefer the explicit PMU/SMU names for new work.

## Layout

| File / folder | Purpose |
|---------------|--------|
| `system_wrapper.py` | Routes test calls to the right system; detects system from address. |
| `keithley4200_constants.py` | Shared frozensets: PMU timing ids, SMU optical ids, all 4200 ids (for GUIs). |
| `test_registry.py` | **Single source**: one `TestSpec` per test (systems, label, params, plot, order). |
| `test_capabilities.py` | `SYSTEM_CAPABILITIES`, generated from the registry. |
| `test_definitions.py` | `TEST_FUNCTIONS` / `TEST_DISPLAY_ORDER` for the GUI, generated from the registry. |
| `systems/base_system.py` | Abstract interface all systems implement. |
| `systems/keithley4200_core.py` | Shared Keithley 4200-SCS KXCI implementation (`Keithley4200KXCICommon`). |
| `systems/keithley2450.py`, `keithley2400.py`, `keithley4200_*.py` | Thin adapters; 4200 variants only override `get_system_name()`. |
| `utils/data_formatter.py` | Normalize and validate returned data. |

## How to add a new test

See **[ADDING_A_TEST.md](ADDING_A_TEST.md)** for the full walkthrough. In short:

1. Add a `TestSpec` to `TESTS` in `test_registry.py` (systems, label, params, plot_type).
2. Add a `NotImplementedError` default in `systems/base_system.py` and the method on each adapter
   (4200: once in `keithley4200_core.py`, converting µs → s there).
3. Add the script method on each instrument's scripts class, naming every GUI parameter.
4. Run `py -m pytest Pulse_Testing/tests -q`; it dry-runs every test on every claimed system.

## How to add a new measurement system

1. **System class** – In `systems/` add a new file (e.g. `my_instrument.py`). Implement `BaseMeasurementSystem`: `get_system_name`, `get_hardware_limits`, `connect`, `disconnect`, `is_connected`, `get_idn`, and every required test method (or `NotImplementedError` for unsupported ones).

2. **Registration** – In `system_wrapper.py`:
   - Add the class to `SYSTEM_CLASSES` (e.g. `'my_instrument': MyInstrumentSystem`).
   - In `detect_system_from_address`, add rules so your address format returns `'my_instrument'`.
   - If the system has a default address, implement `get_default_address()` on the class.

3. **Registry** – In `test_registry.py` add the system id to `ALL_SYSTEMS` (or a group) and to the `systems` of each test it supports.

4. **Dry-run test** – Add the system's scripts class to `SCRIPT_SLOTS` in `tests/test_registry.py` so the parameter checks cover it.

## Future: shared pattern layer (2400 / 2450)

2400 and 2450 use different backends (SCPI vs TSP) but similar patterns. To avoid duplicating pattern logic, you can later add a shared “pattern spec” (e.g. in `patterns/`) that defines each test as a sequence; each system then has a small runner that turns that spec into hardware commands. The refactor leaves the current per-system implementations as-is; this is an optional next step.
