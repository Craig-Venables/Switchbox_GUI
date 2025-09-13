import tkinter as tk
from Sample_GUI import SampleGUI



# record data when checking for connection to see if the current increases over times
# maybe cut off after a sharp increase is seen!


#todo add non multiplexer device so that people can use it for just one device
#todo clean up the code with the following 
#more comments explaineng each functions with variables in and out
#consolidate code, currently theres a lot of similar things, measurments for smu and pmu will be seperated due to the complexity of pmu 
# foir this smu needs to be cleaner and more consise, measurment services needs to be notable for SMU only and there needs to be one for the pmu
#advanced_test_gui needs shifting into somewhere. 

#pmu testing,-pmu_fg_orchestrator.py needs to be moved into a perminant place in the main folder called something to do with meausrment_service_pmu.py
# this function will be the wrapper for all the measurments that are available for the pmu, this can either call 4200adual...py or another wrapper then the class, 
# probably another class



# todo is there a way to find the optimal settings for each device, some kind of test?

""" Classes for the Gui"""


if __name__ == "__main__":
    import sys
    if "--pmu" in sys.argv:
        from PMU_Minimal_GUI import PMUMinimalGUI
        app = PMUMinimalGUI()
        app.mainloop()
    else:
        root = tk.Tk()
        app = SampleGUI(root)
        root.mainloop()
0