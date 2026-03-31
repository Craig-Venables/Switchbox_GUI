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
| `test_capabilities.py` | **Single source** for “which system supports which test” (`SYSTEM_CAPABILITIES`). |
| `test_definitions.py` | GUI metadata: display name, params, description, plot_type; optional `only_for_systems`. |
| `systems/base_system.py` | Abstract interface all systems implement. |
| `systems/keithley4200_core.py` | Shared Keithley 4200-SCS KXCI implementation (`Keithley4200KXCICommon`). |
| `systems/keithley2450.py`, `keithley2400.py`, `keithley4200_*.py` | Thin adapters; 4200 variants only override `get_system_name()`. |
| `utils/data_formatter.py` | Normalize and validate returned data. |

## How to add a new test

1. **Capabilities** – In `test_capabilities.py`:
   - Add the function name to `ALL_TEST_FUNCTIONS`.
   - For each system that supports it, set `SYSTEM_CAPABILITIES[system_name][function_name] = True`.

2. **Definitions** – In `test_definitions.py`:
   - Add an entry to `TEST_FUNCTIONS`: display name → `function`, `description`, `params`, `plot_type`.
   - If the test should only appear for specific systems, set `only_for_systems` (e.g. `["keithley4200_smu"]` for SMU-only GUI rows).

3. **Implementation** – In `systems/base_system.py`:
   - Either add an `@abstractmethod` (all systems must implement) or a default that raises `NotImplementedError`.
   - Implement the method on each adapter that supports it.

The GUI uses `get_test_definitions_for_gui(system_name)` so only supported tests appear; no duplicate “who supports what” in the GUI.

### Adding a new test on Keithley 4200 only

Implement **once** on `Keithley4200KXCICommon` in `systems/keithley4200_core.py` (delegate to `Keithley4200_KXCI_Scripts` / C modules as today). Do **not** duplicate code in `keithley4200_pmu.py` or `keithley4200_smu.py`.

Then:

1. Add the function name to `ALL_TEST_FUNCTIONS` if it is new.
2. Set `SYSTEM_CAPABILITIES['keithley4200_pmu'][name]` and/or `SYSTEM_CAPABILITIES['keithley4200_smu'][name]` to `True` for whichever bench configuration should expose the test (often only one of them).
3. Add the `TEST_FUNCTIONS` row in `test_definitions.py`; use `only_for_systems` when the test must not appear on 2450/2400.
4. For interleaved PMU timing, keep using the existing param flag **`4200a_only`** in definitions; the pulse GUI treats it as “PMU µs timing” via `KEITHLEY4200_PMU_TIMING_SYSTEMS` in `keithley4200_constants.py`.

If both PMU and SMU profiles should list the same new test, set both capability entries to `True`.

## How to add a new measurement system

1. **System class** – In `systems/` add a new file (e.g. `my_instrument.py`). Implement `BaseMeasurementSystem`: `get_system_name`, `get_hardware_limits`, `connect`, `disconnect`, `is_connected`, `get_idn`, and every required test method (or `NotImplementedError` for unsupported ones).

2. **Registration** – In `system_wrapper.py`:
   - Add the class to `SYSTEM_CLASSES` (e.g. `'my_instrument': MyInstrumentSystem`).
   - In `detect_system_from_address`, add rules so your address format returns `'my_instrument'`.
   - If the system has a default address, implement `get_default_address()` on the class.

3. **Capabilities** – In `test_capabilities.py` add a new key to `SYSTEM_CAPABILITIES` for your system and set `True`/`False` for each test.

4. **Optional** – If some tests are only for this system, set `only_for_systems` in `test_definitions.py` for those entries.

## Future: shared pattern layer (2400 / 2450)

2400 and 2450 use different backends (SCPI vs TSP) but similar patterns. To avoid duplicating pattern logic, you can later add a shared “pattern spec” (e.g. in `patterns/`) that defines each test as a sequence; each system then has a small runner that turns that spec into hardware commands. The refactor leaves the current per-system implementations as-is; this is an optional next step.
