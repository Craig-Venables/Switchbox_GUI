import serial
import time

class OxxiusLaser:
    def __init__(self, port="COM3", baud=38400, timeout=1.0, safe_power_mw=10):
        """
        Initialise connection to Oxxius laser.
        Adjust 'port' and 'baud' depending on your hardware.

        After power loss, many Oxxius units restore or default to maximum power
        (e.g. 320 mW). To avoid the laser coming on at full power when the
        system is turned back on, we set a safe power level as soon as we
        connect. Pass safe_power_mw=10 (default) to set 10 mW on connect, or
        None to leave the hardware power unchanged.
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
        if safe_power_mw is not None:
            try:
                self.emission_off()
                time.sleep(0.05)
                self.set_power(safe_power_mw)
            except Exception:
                pass  # don't fail init if laser doesn't respond yet

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
        """
        Turn emission on (DL 1 or EM 1 depending on firmware).
        Note: Switching speed via serial is limited (~10–50 Hz). For faster modulation use TTL input.
        """
        return self.send_command("DL 1")

    def emission_off(self):
        """
        Turn emission off (DL 0 or EM 0).
        Note: Switching speed via serial is limited (~10–50 Hz). For faster modulation use TTL input.
        """
        return self.send_command("DL 0")

    # =======================
    # Ms-scale pulsing (serial; TTL can be added later for faster)
    # =======================

    def pulse_on_ms(self, duration_ms):
        """
        Turn emission on for the given duration (ms), then off.
        Uses serial commands; suitable for ms-scale pulses (~10–50 Hz max).
        For faster repetition use the laser TTL input with external hardware.

        Args:
            duration_ms: Time to keep emission on, in milliseconds (float or int).

        Returns:
            str: Reply from the final emission_off command.
        """
        self.emission_on()
        time.sleep(duration_ms / 1000.0)
        return self.emission_off()

    def pulse_train(self, n_pulses, on_ms, off_ms, power_mw=None):
        """
        Run a train of n_pulses: each pulse is on for on_ms and off for off_ms (between pulses).
        Uses serial on/off; suitable for ms-scale timing. Optional power set once before train.

        Args:
            n_pulses: Number of pulses (int, >= 1).
            on_ms: Emission on time per pulse, in milliseconds.
            off_ms: Time between pulses (emission off), in milliseconds.
            power_mw: If set, set power to this value (mW) once before the train.

        Returns:
            list: Replies from emission_off for each pulse (for debugging).
        """
        if n_pulses < 1:
            return []
        if power_mw is not None:
            self.set_power(power_mw)
            time.sleep(0.05)
        replies = []
        for i in range(n_pulses):
            self.emission_on()
            time.sleep(on_ms / 1000.0)
            r = self.emission_off()
            replies.append(r)
            if i < n_pulses - 1:
                time.sleep(off_ms / 1000.0)
        return replies

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

    def set_to_digital_power_control(self, power_mw):
        """
        Set laser to digital/software power control so set_power() is used.
        Use this when you want to control power in mW from software (e.g. for pulses).
        When done, call set_to_analog_modulation_mode() or close(restore_to_manual_control=True)
        to return to manual front-panel control.

        Emission is turned OFF first and power is set before switching to digital mode
        to avoid a brief power spike when AM 0 is applied.

        Args:
            power_mw: Power level in mW.

        Returns:
            dict: Results of each command.
        """
        results = {}
        results['emission_off'] = self.emission_off()
        time.sleep(0.05)
        results['power'] = self.set_power(power_mw)
        time.sleep(0.1)
        results['APC'] = self.send_command("APC 1")
        time.sleep(0.1)
        results['AM'] = self.send_command("AM 0")
        time.sleep(0.1)
        results['DM'] = self.send_command("DM 0")
        time.sleep(0.1)
        return results

    def set_to_analog_modulation_mode(self, power_mw=100):
        """
        Set laser to analog modulation mode for manual control.
        
        This is the standard state the laser should be left in:
        - Analog modulation ON (AM 1) - allows front panel wheel control
        - Digital modulation OFF (DM 0)
        - Power control mode ON (APC 1)
        - Power set to specified value (default 100 mW)
        - Emission should remain ON
        
        The analog modulation controls a percentage of the set power value.
        Setting power to 100 mW means the front panel wheel can control
        0-100% of 100 mW (0-100 mW range).
        
        Args:
            power_mw: Power level in mW (default: 100 mW)
        
        Returns:
            dict: Results of each command
        """
        results = {}
        try:
            # Set to power control mode
            results['APC'] = self.send_command("APC 1")
            time.sleep(0.1)
            
            # Enable analog modulation (allows front panel wheel control)
            results['AM'] = self.send_command("AM 1")
            time.sleep(0.1)
            
            # Disable digital modulation
            results['DM'] = self.send_command("DM 0")
            time.sleep(0.1)
            
            # Set power level
            results['power'] = self.set_power(power_mw)
            time.sleep(0.1)
            
        except Exception as e:
            results['error'] = str(e)
        return results

    def close(self, restore_to_manual_control=True):
        """
        Close the serial connection.
        
        IMPORTANT: By default, this will restore the laser to analog modulation
        mode before closing. This ensures the laser is left in a state where
        it can be controlled manually via the front panel wheel.
        
        Standard final state:
        - Emission: ON
        - Analog modulation: ON (AM 1)
        - Digital modulation: OFF (DM 0)
        - Power control: ON (APC 1)
        - Power: 100 mW (front panel wheel controls 0-100% of this)
        
        Args:
            restore_to_manual_control: If True, restore to analog modulation
                mode before closing (default: True)
        """
        if restore_to_manual_control:
            try:
                # Ensure emission is ON
                self.emission_on()
                time.sleep(0.1)
                
                # Set to analog modulation mode with 100 mW power
                self.set_to_analog_modulation_mode(power_mw=100)
                
            except Exception:
                # If restoration fails, still close the connection
                pass
        
        self.ser.close()


# =======================
# Example usage
# =======================
if __name__ == "__main__":
    print("=" * 50)
    print("Oxxius Laser Controller Test")
    print("=" * 50)
    
    # Connect to laser
    print("\n1. Connecting to laser...")
    laser = OxxiusLaser(port="COM4", baud=19200)
    print("   ✓ Connected")

    try:
        # Get laser identity
        print("\n2. Querying laser identity...")
        idn = laser.idn()
        print(f"   ID: {idn}")
        
        # Check status and errors
        print("\n3. Checking status and errors...")
        status = laser.get_status()
        errors = laser.get_error()
        print(f"   Status: {status}")
        print(f"   Errors: {errors}")
        
        # Set to power control mode
        print("\n4. Setting to power control mode...")
        result = laser.send_command("APC 1")
        print(f"   Result: {result}")
        
        # Set to digital control (analog modulation OFF)
        print("\n5. Setting to digital control (AM 0)...")
        result = laser.send_command("AM 0")
        print(f"   Result: {result}")
        
        # Disable digital modulation
        print("   Disabling digital modulation (DM 0)...")
        result = laser.send_command("DM 0")
        print(f"   Result: {result}")
        
        # Set power to 5 mW
        print("\n6. Setting power to 5 mW...")
        result = laser.set_power(5)
        print(f"   Result: {result}")
        
        # Verify power setting
        power = laser.get_power()
        print(f"   Current power: {power}")
        
        # Turn laser on
        print("\n7. Turning laser emission ON...")
        result = laser.emission_on()
        print(f"   Result: {result}")
        
        # Wait 2 seconds
        print("\n8. Waiting 2 seconds...")
        time.sleep(2)
        print("   ✓ Wait complete")
        
        # Enable analog modulation (AM 1)
        # Note: Analog modulation is a % of the power setting
        print("\n9. Enabling analog modulation (AM 1)...")
        result = laser.send_command("AM 1")
        print(f"   Result: {result}")
        print("   ✓ Analog modulation enabled (front panel wheel controls % of set power)")
        
        # Set power to 100 mW (this becomes the maximum when analog modulation is enabled)
        print("\n10. Setting power to 100 mW (max for analog modulation)...")
        result = laser.set_power(100)
        print(f"   Result: {result}")
        
        # Verify power setting
        power = laser.get_power()
        print(f"   Current power: {power}")
        print("   ✓ Power set to 100 mW - analog wheel now controls % of this value")
        
        # Keep emission ON (don't disable as it causes issues)
        print("\n11. Keeping emission ON (not disabling to avoid issues)...")
        print("   ✓ Laser remains ON with analog modulation enabled")
        
        print("\n" + "=" * 50)
        print("Test completed successfully!")
        print("=" * 50)
        print("Laser is now in analog modulation mode:")
        print("  - Power set to 100 mW (maximum)")
        print("  - Front panel wheel controls percentage of 100 mW")
        print("  - Emission remains ON")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n11. Closing connection and restoring to manual control mode...")
        # close() automatically restores to analog modulation mode with 100 mW
        # Emission will be kept ON, analog modulation ON, power at 100 mW
        laser.close(restore_to_manual_control=True)
        print("   ✓ Connection closed")
        print("   ✓ Laser restored to manual control mode (emission ON, AM ON, 100 mW)")


"""
================================================================================
LASER OPERATION PROTOCOL AND DOCUMENTATION
================================================================================

STANDARD OPERATION SEQUENCE
----------------------------
When operating the laser, ALWAYS follow this sequence to ensure proper operation
and leave the system in a good state for the next user:

1. CONNECT to laser (COM4, 19200 baud)
2. QUERY identity, status, and errors
3. SET to power control mode: APC 1
4. SET to digital control: AM 0, DM 0
5. SET power level (e.g., 5 mW for testing)
6. TURN laser ON: DL 1
7. WAIT 2 seconds (safety delay)
8. ENABLE analog modulation: AM 1
9. SET power to desired level (typically 100 mW for manual control)
10. KEEP emission ON (do NOT disable - causes issues)
11. CLOSE connection (automatically restores to manual control mode)

IMPORTANT: Never disable emission (DL 0) after enabling analog modulation,
as this causes the laser to not work properly later.

POWER LEVEL SETTINGS
--------------------
- When analog modulation is OFF (AM 0): Power setting is absolute (e.g., 5 mW = 5 mW)
- When analog modulation is ON (AM 1): Power setting is the MAXIMUM
  - Front panel wheel controls 0-100% of the set power
  - Example: Power set to 100 mW with AM 1 means wheel controls 0-100 mW

STANDARD FINAL STATE (for manual control)
------------------------------------------
The laser should ALWAYS be left in this state when closing/disconnecting:

- Emission: ON (DL 1)
- Analog modulation: ON (AM 1)
- Digital modulation: OFF (DM 0)
- Power control: ON (APC 1)
- Power: 100 mW

This allows the next user to control the laser manually via the front panel
wheel, which will adjust the power from 0-100% of 100 mW (0-100 mW range).

The close() method automatically restores the laser to this state by default.

SETTING POWER LEVELS
--------------------
When setting power levels:

1. If using digital control (AM 0):
   - Set power directly: set_power(desired_mw)
   - Power will be exactly what you set

2. If using analog modulation (AM 1):
   - Set power to maximum desired: set_power(max_mw)
   - Front panel wheel controls 0-100% of this maximum
   - Example: set_power(100) with AM 1 allows 0-100 mW via wheel

3. Always set power BEFORE enabling analog modulation if you want a specific
   maximum value.

COMMAND REFERENCE
-----------------
- DL 1: Turn emission ON
- DL 0: Turn emission OFF (avoid after enabling analog modulation)
- APC 1: Enable automatic power control
- APC 0: Disable automatic power control
- AM 1: Enable analog modulation (front panel wheel control)
- AM 0: Disable analog modulation (digital/software control)
- DM 1: Enable digital modulation
- DM 0: Disable digital modulation
- PM <value>: Set power in mW
- ?P: Query current power setting

SERIAL PULSE TIMING (MINIMUM PULSE WIDTH)
------------------------------------------
Pulsing via serial (DL 1 / DL 0) is limited by command round-trip time, not by
the laser hardware. Measured on this system (COM4, 19200 baud):

  - Serial overhead (one on + one off with no delay): ~10 ms per cycle.
  - Shortest full cycle (on then off) is therefore ~10 ms.
  - For reliable pulse length (requested on-time is accurate), use on-time >= 20 ms.
  - Example: at 20 ms requested, total elapsed ≈ 25 ms (overhead ≈ 5 ms).

Typical requested vs total elapsed:
  Requested on-time (ms)  |  Total elapsed (ms)  |  Overhead (ms)
  -----------------------|---------------------|------------------
  50                     |  ~71                 |  ~21
  20                     |  ~25                 |  ~5
  10                     |  ~25                 |  ~15
  5, 2, 1                |  ~15–25              |  overhead dominates

Recommendation:
  - Use pulse_on_ms() and pulse_train() with on_time >= 20 ms for predictable pulses.
  - For shorter pulses (sub-millisecond or high repetition), use the laser TTL
    modulation input with external hardware; serial cannot achieve those rates.

To re-measure on your setup, run:
  python test_oxxius_pulse.py --timing [COM_PORT] [BAUD] [POWER_MW]

CONNECTION SETTINGS
-------------------
SERIAL_PORT:
  Windows: "COMx" (e.g., "COM4")
  Linux/Mac: "/dev/ttyUSBx"
  Check Device Manager (Windows) or dmesg (Linux) to find COM port

BAUD_RATE:
  LCX / LBX LaserBoxx: 19200 or 38400 (check manual / try both)
  L1C compact lasers: 115200

Default for this system: COM4, 19200 baud

SAFETY NOTES
------------
- First ON after enabling emission typically takes 5 s before light appears
- Don't shorten the safety delay
- Always verify laser status and errors before operations
- Never disable emission after enabling analog modulation
- Always restore to analog modulation mode before closing

================================================================================
"""
