import serial
import time

class OxxiusLaser:
    def __init__(self, port="COM3", baud=38400, timeout=1.0):
        """
        Initialise connection to Oxxius laser.
        Adjust 'port' and 'baud' depending on your hardware.
        """
        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout
        )
        time.sleep(0.2)  # settle interface

    def send_command(self, cmd):
        """Send a command string and return the reply as text."""
        self.ser.write((cmd + "\n").encode("ascii"))
        reply = self.ser.read_until(b"\r\n")
        return reply.decode("ascii", errors="ignore").strip()

    # =======================
    # Basic info & control
    # =======================

    def idn(self):
        """Query identity string."""
        return self.send_command("?ID")

    def emission_on(self):
        """Turn emission on (DL 1 or EM 1 depending on firmware)."""
        return self.send_command("DL 1")

    def emission_off(self):
        """Turn emission off (DL 0 or EM 0)."""
        return self.send_command("DL 0")

    def set_power(self, value):
        """
        Set target power.
        Usually 'P <mW>' (e.g. 'P 100').
        Some firmwares use 'PW <percent>'.
        """
        return self.send_command(f"PM {value}")

    def get_power(self):
        """Query power setpoint/reading (?P)."""
        return self.send_command("?P")

    def set_current(self, value):
        """Set diode current (if in current mode)."""
        return self.send_command(f"I {value}")

    def get_current(self):
        """Query diode current (?I)."""
        return self.send_command("?I")

    # =======================
    # Status & errors
    # =======================

    def get_status(self):
        """
        Query laser status (?S).
        Returns a status string or bitmask depending on model.
        """
        return self.send_command("?S")

    def get_error(self):
        """
        Query error messages (?E).
        Returns last error or '0' if none.
        """
        return self.send_command("?E")

    def reset_error(self):
        """
        Reset/clear error state.
        Some firmwares use 'E 0'.
        """
        return self.send_command("E 0")

    def get_temperature(self):
        """
        Query internal temperature (?T).
        Not all models support this.
        """
        return self.send_command("?T")

    def interlock_status(self):
        """
        Query interlock status.
        Often included in ?S reply, but some firmwares
        have dedicated ?IL query.
        """
        return self.send_command("?IL")

    # =======================
    # Housekeeping
    # =======================

    def close(self):
        """Close the serial connection."""
        self.ser.close()


# =======================
# Example usage
# =======================
if __name__ == "__main__":
    laser = OxxiusLaser(port="COM4", baud=19200)

    try:
        print("ID:", laser.idn())

        print("Status:", laser.get_status())
        print("Errors:", laser.get_error())
        print("set laser to power control")
        print(laser.send_command("APC 1"))

        print("Turning emission ON...")
        print(laser.emission_on())
        time.sleep(6)  # safety delay

        

        print("changing powers")
        print(laser.send_command("AM 0"))
        print(laser.send_command("DM 0"))

        # print("########################")

        # print("Setting power to 10 mW...")
        # print(laser.set_power(10))
        # print("Power:", laser.get_power())

        # time.sleep(2)
        
        # print("Setting power to 100 mW...")
        # print(laser.set_power(100))
        # print("Power:", laser.get_power())
        # time.sleep(2)

        # print("Power:", laser.get_power())
        # print("Temperature:", laser.get_temperature())

        # print(laser.set_power(1))

        # print("Turning emission OFF...")
        # print(laser.emission_off())


        print(laser.send_command("APC 0"))

        laser.send_command("RST")

    finally:
        laser.close()


"""
What you need to change for different controllers

SERIAL_PORT

Windows: "COMx"

Linux/Mac: "/dev/ttyUSBx"

Check in Device Manager (Windows) or dmesg (Linux) to find which COM port the laser appears on.

BAUD_RATE

LCX / LBX LaserBoxx: 19200 or 38400 (check manual / try both).

L1C compact lasers: 115200.

Commands

DL 1 / DL 0 are common for LCX and LaserBoxx.

Some older LBX units use EM 1 / EM 0.

Power query is usually ?P, but can vary.

Always check the “RS-232 command list” in your model’s manual.

Safety delay

The first ON after enabling emission typically takes 5 s before light appears. Don’t shorten that wait.
"""
