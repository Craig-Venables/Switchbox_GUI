import instruments
import time
import numpy as np
from tkinter import filedialog as dialog
import matplotlib.pyplot as plt


sb = instruments.SwitchBox()
sm = instruments.K2461()

sb.connect(5)
sm.connect()

meas = {"I+": "H", "I-": "G", "V1+": "F", "V1-": "H"}
puls1 = {"I+": "H", "I-": "G"}
puls2 =  {"I+": "H", "I-": "G"}

# Pulse
pulse_current = 0.01e-3                                              
pulse_width = 1e-3
number_of_pulses = 5

# Probe
probe_current = 10e-6
nplc = 2
number_of_measurments = 10


# Pre set matrix and arrays
n_pulses = np.arange(number_of_pulses)
pulse_data = []
voltage_matrix = np.zeros((number_of_measurments,number_of_pulses))
time_arr_matrix = np.zeros((number_of_measurments,number_of_pulses))
time_arr_av = np.zeros((number_of_measurments,1))
time_arr_std = np.zeros((number_of_measurments,1))
print("About to start pulses")

Failed = "No"

try:
    
    for n in n_pulses:
    
        sb.switch(puls1)
        plt.pause(1)
        sm.prepare_pulsing_current(pulse_current,pulse_width)
        sm.send_pulse()
        plt.pause(200e-3)
        sb.switch(meas)
        plt.pause(1)
        sm.prepare_measure_n(probe_current,number_of_measurments, nplc)
        print(n,0)
        sm.trigger()
        print(n,1)
        plt.pause(0.0001)
        print(n,2)
        time_arr, v, c = sm.read_buffer(number_of_measurments)
        
        P = np.array([time_arr, v, c])
        pulse_data.append(P)
        
        # V = np.array([v])
        # voltage_matrix.append(V)
        
        #pulse_data[n] = P
        
        new_time_arr = time_arr + n*time_arr[-1]*1.2
        
        plt.plot(new_time_arr,v/c)
        
        print("Pulse #",n+1)

except:
    
    print("There was an Error and had to close loop")
    
    sm.BEEP(311, 0.25)
    plt.pause(0.15)
    sm.BEEP(294, 0.25)
    plt.pause(0.15)
    sm.BEEP(262, 0.5)
    plt.pause(0.15)
    
    sb.close()
    sm.close()
    
    Failed = "Yes"


if Failed == "No":
    
    sm.BEEP(440, 0.6)
    plt.pause(0.1)
    sm.BEEP(466, 0.6)
    plt.pause(0.1)
    sm.BEEP(494, 0.6)
    plt.pause(0.1)
    sm.BEEP(523, 0.6)
    plt.pause(0.1)
    sm.BEEP(784, 1.2)
    plt.pause(0.1)



time_arr_0 = pulse_data[0][0]


for n in n_pulses:
    
    time_n = pulse_data[n][0]
    time_arr_matrix[:,n] = time_n
    
    v = pulse_data[n][1]
    voltage_matrix[:, n] = v 

for n in np.arange(number_of_measurments):
    
    t_n = time_arr_matrix[n,:]
    t_std = np.std(t_n)
    t_av = np.average(t_n)
    
    time_arr_av[n,:] = t_av
    time_arr_std[n,:] = t_std
    
    
    
final_data = np.column_stack((time_arr_av, time_arr_std, voltage_matrix))

print(final_data.shape)
print(final_data[:10])  # preview first 5 rows

# np.savetxt(r"C:\Users\ppyak4\OneDrive - The University of Nottingham\PhD\Exported Data sets from Python\Test.txt", current_resistance_data)

sb.close()
sm.close()