import tkinter as tk
from Sample_GUI import SampleGUI

# record data when checking for connection to see if the current increases over times
# maybe cut off after a sharp increase is seen!
#todo add non multiplexer device so that people can use it for just one device

""" Classes for the Gui"""

if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
