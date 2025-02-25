from unittest.mock import MagicMock

class SimulatedKeithley:
    def write(self, command):
        print(f"Command received: {command}")

    def query(self, command):
        responses = {
            "*IDN?": "Keithley Instruments Inc., Model 2400, SN123456, 1.0",
            "MEAS:VOLT?": "2.500E+00",
            "MEAS:CURR?": "1.000E-03",
        }
        return responses.get(command, "0.000E+00")

# Replace actual instrument with simulation
# sim_inst = SimulatedKeithley()
# print(sim_inst.query("*IDN?"))