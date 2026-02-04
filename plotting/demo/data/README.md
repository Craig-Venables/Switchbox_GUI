# Demo data (optional)

The demo uses **synthetic data** from `synthetic_data.py` by default, so no files are required here.

If you want to use your own data for the demo later:

- **IV / device:** CSV or text with columns: voltage, current, and optionally time. Same length arrays.
- **Endurance:** CSV or table with cycle index and columns like `Current_Forward_(OFF)_1V`, `Current_Reverse_(ON)_1V`, `Current_Forward_(ON)_-1V`, `Current_Reverse_(OFF)_-1V` for each voltage.

You can extend `synthetic_data.py` (or add a small `data_loader.py`) to check for files in this directory and load them instead of generating synthetic data when present.
