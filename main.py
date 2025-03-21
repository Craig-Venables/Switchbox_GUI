import tkinter as tk
from Sample_GUI import SampleGUI

# import pySwitchbox


# record data when checking for connection to see if the current increases over time
# maybe cut off after a sharp increase is seen!

# todo give updates on gui of the current sweep
# todo add code where telegram bot gives you updates hen you prompt it.
# todo when it sends tne start it sends an estimated time of completion


# todo Led code?
# todo worth adding uv led?

# TODO can i add a time to this so i can do endurance and retention
# todo is there a way to find the optimal settings for each device, some kind of test?

""" Classes for the Gui"""


if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
