import tkinter as tk
from gui.sample_gui import SampleGUI


#todo add non multiplexer device so that people can use it for just one device

# TODO: Test Read_With_Laser_Pulse_SegArb buffer limit change (2025-01-XX)
# - Changed buffer limit from 100,000 to 1,000,000 samples (hardware limit)
# - File: Equipment/SMU_AND_PMU/4200_C_Code/Read_with_laser_pulse/Pull from 4200 this is wrong.c (line 1001)
# - This allows up to 5 ms measurements at 200 MSa/s (was limited to 0.5 ms)
# - For longer measurements, reduce sample rate (e.g., 10 MSa/s for 100 ms)
# - NEEDS TESTING: Verify measurements work correctly with 1M sample buffer
# - Memory usage: ~24 MB for waveform buffers (3 arrays × 1M samples × 8 bytes)


# change pulse with laser c program update on 4200


#build specific laser gui, this homes the laser you then just select the device and it will go to said device,we need to 
# find a way to make sure its in the correct position for this 
#temp gui

# make the current value when plotting red so you can see it when tracing
# cannot change sample mid way though testing 

""" Classes for the Gui"""

if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
