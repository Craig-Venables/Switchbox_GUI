import time
import numpy as np
from ProxyClass import Proxy

# -----------------------------
# User settings
# -----------------------------
tcp_ip   = "192.168.0.10"   # IP of 4200A-SCS PC
tcp_port = 8888            # Port defined in 4200-Server.ini
smu_name = "SMU1"          # Which SMU to use (e.g. SMU1, SMU2)

start_v     = 0.0          # Sweep start voltage (V)
stop_v      = 1.0          # Sweep stop voltage (V)
step_v      = 0.1          # Step size (V)
step_delay  = 0.1          # Delay per step (s)
compliance  = 1e-3         # Compliance current (A)

# -----------------------------
# Connect to server
# -----------------------------
lpt   = Proxy(tcp_ip, tcp_port, "lpt")
param = Proxy(tcp_ip, tcp_port, "param")

# Initialize LPT interface
lpt.initialize()
lpt.devint()

# Get instrument ID
smu_id = lpt.getinstid(smu_name)

# -----------------------------
# Configure compliance (limit)
# -----------------------------
lpt.limiti(smu_id, compliance)

# -----------------------------
# Build voltage sweep array
# -----------------------------
# Forward sweep: start → stop
forward = np.arange(start_v, stop_v + step_v, step_v)
# Reverse sweep: stop → start
reverse = np.arange(stop_v, start_v - step_v, -step_v)

voltages = np.concatenate([forward, reverse])

# -----------------------------
# Run the sweep
# -----------------------------
data = []

for v in voltages:
    # Apply voltage
    lpt.forcev(smu_id, float(v))

    # Wait to settle
    time.sleep(step_delay)

    # Measure current
    current = lpt.intgi(smu_id)  # intgi = measure current

    print(f"V = {v:.3f} V, I = {current:.3e} A")

    data.append((v, current))

# -----------------------------
# Turn off source (force 0 V)
# -----------------------------
lpt.forcev(smu_id, 0.0)

# Save results to file
with open("iv_sweep.csv", "w") as f:
    f.write("Voltage (V), Current (A)\n")
    for v, i in data:
        f.write(f"{v:.6f},{i:.6e}\n")

print("Sweep complete. Data saved to iv_sweep.csv")
