Install the following dependancies 

pip install opencv-python
pip install matplotlib

https://nodejs.org/en


# Create a custom sweep 

To create custom sweeps use Custom_sweeps.jason build the sweeps you want and then within the code add it too the ddown list within the code

The following options are along with the defaults: 
"start_v": 0,
"stop_v": 0.1,
"sweeps": 3,
"step_v": 0.01,
"step_delay":0.05
"Sweep_type": "FS" 
(FS = Full sweep (default),Ps=PositiveHalf-sweep +ve, Ns=NegativeHalf-sweep)

"LED": "OFF"      (colour of the led,options - blue,red,green,white,OFF)
"LED_TIME": "10" Time led is on before measurements taking place
"LED_SWEEPS": "2" (Number of sweep the led is on for)




# Common Problems
1. Mapping not correct?\
1.i. Check the scaling factor or use show box's python code\
1.ii. check x_max and x_min are the correct way around this causes issues if not!
2. 



