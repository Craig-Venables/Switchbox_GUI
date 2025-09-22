# config.py

# Motor serial numbers
MOTOR_X_SERIAL = "27601562"
MOTOR_Y_SERIAL = "27601620"

# Motor scale
MOTOR_SCALE = 34304

# Motor settings
MAX_VELOCITY = 2.4  # mm/s
MAX_ACCELERATION = 4.5  # mm/s^2

# Software travel limits (in mm)
# Set these according to your stage's physical range. Example: 0 to 50 mm.
TRAVEL_MIN_MM = 0.0
TRAVEL_MAX_MM = 50.0

# Laser settings
LASER_USB = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"