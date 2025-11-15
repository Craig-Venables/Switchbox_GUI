import tkinter as tk
from gui.sample_gui import SampleGUI

# record data when checking for connection to see if the current increases over times
# maybe cut off after a sharp increase is seen!
#todo add non multiplexer device so that people can use it for just one device

# TODO: Test Read_With_Laser_Pulse_SegArb buffer limit change (2025-01-XX)
# - Changed buffer limit from 100,000 to 1,000,000 samples (hardware limit)
# - File: Equipment/SMU_AND_PMU/4200_C_Code/Read_with_laser_pulse/Pull from 4200 this is wrong.c (line 1001)
# - This allows up to 5 ms measurements at 200 MSa/s (was limited to 0.5 ms)
# - For longer measurements, reduce sample rate (e.g., 10 MSa/s for 100 ms)
# - NEEDS TESTING: Verify measurements work correctly with 1M sample buffer
# - Memory usage: ~24 MB for waveform buffers (3 arrays × 1M samples × 8 bytes)


#ideas


# move the plots around a little bgger specific ones 
# clean up led and laser intergration 




#build specific laser gui, this homes the laser you then just select the device and it will go to said device,we need to find a way to make sure its in the correct position for this 
#

# upon testing with the switchbox you can save the heat map and load it in such that it knows which deivces dont work so you can skip them or apply high voltage too them 
# this will be saved somewhere and you can choose the device when you load the system, if this is done samplename and additional save location should be greyed out as we know know the sample
# but additonal info will still be there and added onto the end of the file name.
# specific testing for a new device to create the heat map, this heat map will then show when loaded onto the initial gui.

#temp gui

###
# IMPORTANT:make look nicer,the graphs look hideousREA
###

# consider moving this into qt6

""" Classes for the Gui"""

if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
