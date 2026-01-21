import tkinter as tk
from gui.sample_gui import SampleGUI



# change pulse with laser c program update on 4200


#build specific laser gui, this homes the laser you then just select the device and it will go to said device,we need to 
# find a way to make sure its in the correct position for this 
#temp gui

# make the current value when plotting red so you can see it when tracing


# Some forming set up, allowing you to choose a current limit and we send pulses until the device "forms" form read form read etc
# post form then runs measurmetns 

#add into the anlaysis tab a way too run theough all the data and reclassify with new weights of whats memristive capacative etc... 

# conditional testing dosnt work propperly seemigly dosnt save the data! but dies run the measurment 
# if and when the switchbox is used, devices c and f 1-5 need too be not routed too as theres no auto pins for this location!

# something to view the "memristive newss" od the samples and quick look 

#the quick view organge aboive the grpoahds needs updating wiuth the current devices voltage and loop number 



""" Classes for the Gui"""

if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
