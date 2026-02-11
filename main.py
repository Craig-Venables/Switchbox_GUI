"""
Switchbox GUI – Main Entry Point
================================

Application launcher for the Switchbox measurement and device characterization system.
Creates the root Tkinter window and starts the Sample GUI, which provides:

- Device selection and sample management
- Visual device map with click-to-select
- Multiplexer routing control
- Launch point for measurement interfaces (IV sweeps, pulse testing, etc.)

Usage:
------
    python main.py

Or import and run programmatically:

    import tkinter as tk
    from gui.sample_gui import SampleGUI

    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()

See Also:
---------
- gui.sample_gui: Device selection and sample management
- gui.measurement_gui: Main measurement interface
- TODO.md: Tracked feature requests and known issues

# idea - log time of each measurment into the log file to keep track of when each measurment was taken
# time and data on each measurment on the sample header 
"""

import tkinter as tk
from gui.sample_gui import SampleGUI


if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
