# Pulse Testing Backend

Multi-system pulse testing: one interface, multiple instruments (Keithley 2450, 4200A, 2400). The GUI filters tests by connected system; support is defined here.

## Unified script locations

All instrument **controllers and scripts** live under **Equipment/SMU_AND_PMU/** per instrument. **Pulse_Testing/systems/** contains only **adapters** that implement `BaseMeasurementSystem` and delegate to those scripts.

| System | Adapter (this repo) | Scripts & controller (Equipment) |
|--------|---------------------|-----------------------------------|
| **Keithley 2400** | `Pulse_Testing/systems/keithley2400.py` | `Equipment/SMU_AND_PMU/keithley2400/scpi_scripts.py`, `controller.py` |
| **Keithley 2450** | `Pulse_Testing/systems/keithley2450.py` | `Equipment/SMU_AND_PMU/keithley2450/tsp_scripts.py`, `tsp_controller.py` (and `tsp_sim_scripts.py` for sim) |
| **Keithley 4200A** | `Pulse_Testing/systems/keithley4200a.py` | `Equipment/SMU_AND_PMU/keithley4200/kxci_scripts.py`, `kxci_controller.py`; C code under `4200A/C_Code_with_python_scripts/` |

Each adapter file has a short docstring at the top pointing to its script and controller paths. To add or change test logic for an instrument, edit the script module in **Equipment/SMU_AND_PMU/<instrument>/**; the adapter in **Pulse_Testing/systems/** only wires that script to the common interface.

## Layout

| File / folder | Purpose |
|---------------|--------|
| `system_wrapper.py` | Routes test calls to the right system; detects system from address. |
| `test_capabilities.py` | **Single source** for “which system supports which test” (`SYSTEM_CAPABILITIES`). |
| `test_definitions.py` | GUI metadata: display name, params, description, plot_type; optional `only_for_systems`. |
| `systems/base_system.py` | Abstract interface all systems implement. |
| `systems/keithley2450.py`, `keithley4200a.py`, `keithley2400.py` | Adapters only; delegate to Equipment scripts (see table above). |
| `utils/data_formatter.py` | Normalize and validate returned data. |

## How to add a new test

1. **Capabilities** – In `test_capabilities.py`:
   - Add the function name to `ALL_TEST_FUNCTIONS`.
   - For each system that supports it, set `SYSTEM_CAPABILITIES[system_name][function_name] = True`.

2. **Definitions** – In `test_definitions.py`:
   - Add an entry to `TEST_FUNCTIONS`: display name → `function`, `description`, `params`, `plot_type`.
   - If the test should only appear for one system (e.g. 4200A), set `only_for_systems: ["keithley4200a"]`.

3. **Implementation** – In `systems/base_system.py`:
   - Either add an `@abstractmethod` (all systems must implement) or a default that raises `NotImplementedError`.
   - Implement the method in each system that supports it (e.g. `keithley2450.py`, `keithley4200a.py`).

The GUI uses `get_test_definitions_for_gui(system_name)` so only supported tests appear; no duplicate “who supports what” in the GUI.

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
