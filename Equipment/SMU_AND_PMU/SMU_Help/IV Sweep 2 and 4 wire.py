#IV Sweep
import instruments
import time
import numpy as np
from tkinter import filedialog as dialog
import matplotlib.pyplot as plt

sb = instruments.SwitchBox()
sm = instruments.K2461()

sb.connect(5)
sm.connect()

meas_4Wire = {"I+": "H", "I-": "G", "V1+": "F", "V1-": "E"}
meas_2Wire = {"I+": "H", "I-": "G"}

#Current perams
Imax = 0.1e-3
Imin = 0.1e-3
steps = 0.001e-3

nplc = 2

Zero_Imax = np.arange(0, Imax , steps)
Imax_Zero = np.arange(Imax, 0, -steps)
Zero_Imin = np.arange(0, Imin , steps)
Imin_Zero = np.arange(Imin, 0, -steps)

Isweep = np.append(Zero_Imax,[Imax_Zero, Zero_Imin, Imin_Zero])

Current_arr = []
Voltage_arr = []

sb.switch(meas_4Wire)

for i, n in enumerate(Isweep):
    
    sm.prepare_measure_one(n, nplc, four_wire=True)
    plt.pause(0.001)
    sm.trigger()
    plt.pause(0.001)
    t, v, c = sm.read_buffer(1)
    
    Current_arr.append(c)
    Voltage_arr.append(v)
    
    plt.plot(v,c)
    



    
    
    




































