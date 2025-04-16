import serial
import time

class ITC4Controller:
    def __init__(self, port='COM5', baudrate=9600, timeout=1):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)

        # set into remote mode unlocked
        self.send_command("C3")

        # Can unlock but cannot controll or read yet

        print("set_temp",self.send_command("R0"))

        print(self.get_temperature("3"))
        print(self.get_temperature(3))

        time.sleep(2)  # Let the serial connection settle

    def send_command(self, command):
        """Send a command to the controller."""
        full_command = f"{command}\r"
        self.ser.write(full_command.encode('ascii'))
        time.sleep(0.1)
        response = self.ser.read_all().decode('ascii', errors='ignore').strip()
        return response,self.ser.read_all()

    def get_temperature(self, sensor):
        return self.send_command(f'R{sensor}')

    def set_temperature(self, temp):
        return self.send_command(f'T{temp}')

    def close(self):
        self.ser.close()

# Example usage
if __name__ == "__main__":
    itc = ITC4Controller(port='COM5')  # Change this to your detected port


