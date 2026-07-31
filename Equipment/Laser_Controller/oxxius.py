import serial
import time

# True rated max optical power of the LBX unit normally used with the
# TTL/ACC (current-%) workflow (tools/pmu_laser_smu_read). PM is an
# absolute power CEILING enforced by the firmware in ALL modes (APC *and*
# ACC) — if it's left at a lower leftover value (e.g. the 100 mW used for
# manual/analog-wheel control elsewhere in this driver), CM (current %)
# gets silently clamped once the resulting power would exceed that
# ceiling, so "100% current" does NOT mean "100% of the laser's rated
# output". Set this to your unit's actual rated power (see its label/
# datasheet) if it's not a 330 mW model.
TTL_FULL_POWER_MW = 330

class OxxiusLaser:
    def __init__(self, port="COM3", baud=38400, timeout=1.0, safe_power_mw=10, verbose=True):
        """
        Initialise connection to Oxxius laser.
        Adjust 'port' and 'baud' depending on your hardware.

        After power loss, many Oxxius units restore or default to maximum power
        (e.g. 320 mW). To avoid the laser coming on at full power when the
        system is turned back on, we set a safe power level as soon as we
        connect. Pass safe_power_mw=10 (default) to set 10 mW on connect, or
        None to leave the hardware power unchanged.

        verbose: If True (default), print every serial command and reply.
        """
        self.verbose = verbose
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
        if self.verbose:
            print(f"[LASER] >> {cmd}", flush=True)
        self.ser.write((cmd + "\n").encode("ascii"))
        reply = self.ser.read_until(b"\r\n")
        text = reply.decode("ascii", errors="ignore").strip()
        if self.verbose:
            print(f"[LASER] << {text!r}", flush=True)
        return text

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
        """Query measured output power in mW (?P)."""
        return self.send_command("?P")

    def get_power_setpoint(self):
        """Query power setpoint / ceiling in mW (?SP)."""
        return self.send_command("?SP")

    def set_current(self, value):
        """Set diode current as % of nominal (0–125). Uses CM (not saved to EEPROM).

        CM = Automatic Current Control setpoint as a *percent of the laser's
        nominal diode current* (not mA, and not optical power %). In ACC
        mode (APC 0) this is what sets how bright the beam is when TTL
        gates the emission on. Typical range 0–100 (up to 125 on some
        firmwares). Distinct from PM/SP, which are absolute power in mW.
        """
        # Firmware expects an integer percent; "I …" is not a valid LBX command.
        pct = int(round(float(value)))
        return self.send_command(f"CM {pct}")

    def get_current(self):
        """Query diode current setpoint in mA (?SC)."""
        return self.send_command("?SC")

    def get_current_percent(self):
        """Query diode current setpoint as % of nominal (?CM)."""
        return self.send_command("?CM")

    def query_levels(self):
        """Snapshot of current-% / current-mA / measured power / power setpoint.

        Used when logging a pulse fire so the terminal shows what the laser
        was actually set to (CM / ?SC) and what power it reported (?P / ?SP).
        Returns a dict of raw reply strings (never raises — missing queries
        become None).
        """
        out = {
            "cm_pct": None,
            "current_ma": None,
            "power_mw": None,
            "power_setpoint_mw": None,
        }
        try:
            out["cm_pct"] = self.get_current_percent()
        except Exception:
            pass
        try:
            out["current_ma"] = self.get_current()
        except Exception:
            pass
        try:
            out["power_mw"] = self.get_power()
        except Exception:
            pass
        try:
            out["power_setpoint_mw"] = self.get_power_setpoint()
        except Exception:
            pass
        return out

    def digital_modulation_on(self):
        """Enable TTL digital modulation (TTL 1). Alias CW 0 on some firmwares."""
        return self.send_command("TTL 1")

    def digital_modulation_off(self):
        """Disable TTL digital modulation / CW beam (TTL 0). Alias CW 1 on some firmwares."""
        return self.send_command("TTL 0")

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
        results['TTL'] = self.digital_modulation_off()
        time.sleep(0.1)
        return results

    def prepare_for_ttl_modulation(self, full_power_mw=TTL_FULL_POWER_MW):
        """
        Arm the laser for external TTL gating via the digital modulation input.

        Sequence: set power ceiling (PM <full_power_mw>) → analog modulation
        OFF (AM 0) → digital modulation ON (TTL 1) → emission ON (DL 1).
        Emission must be ON for the TTL input to gate light; LOW TTL = off,
        HIGH TTL = on at the current/power setpoint.

        Why set PM here: PM is an absolute power CEILING enforced by the
        firmware in ALL modes, including ACC (current-%, what this method
        arms). If PM was left at a lower leftover value from a previous
        session (e.g. 100 mW, the standard manual/analog-wheel default),
        CM (current %) silently clamps once the resulting power would
        exceed that ceiling — so "100% current" would NOT mean "100% of
        the laser's rated output". Setting PM to the unit's true rated max
        power here ensures the full CM range (0-100%, or up to 125% of
        nominal) maps to genuine 0-100%+ of rated output, uncapped.

        Note: LBX firmware uses ``TTL``, not ``DM`` (``DM`` returns ``????``).

        Args:
            full_power_mw: Power ceiling to set (mW) — default is this
                unit's rated max (see TTL_FULL_POWER_MW at module level;
                change that constant, or pass a value here, if your laser
                is not a 330 mW model).

        Returns:
            dict: Results of each command.
        """
        results = {}
        if self.verbose:
            print(
                f"[LASER] === prepare_for_ttl_modulation (PM {full_power_mw}, "
                "TTL 1, ACC, emission ON) ===",
                flush=True,
            )
        # Emission must be OFF to change APC; then arm TTL and turn emission
        # back ON — required for the TTL input to gate light.
        results['emission_off'] = self.emission_off()
        time.sleep(0.05)
        # Raise the power ceiling BEFORE arming ACC/TTL so CM% is never
        # silently clamped by a lower leftover PM value.
        results['power'] = self.set_power(full_power_mw)
        time.sleep(0.1)
        results['AM'] = self.send_command("AM 0")
        time.sleep(0.1)
        results['APC'] = self.send_command("APC 0")
        time.sleep(0.1)
        results['TTL'] = self.digital_modulation_on()
        time.sleep(0.1)
        results['emission_on'] = self.emission_on()
        time.sleep(0.1)
        return results

    def set_current_percent_for_ttl(self, percent):
        """
        Set diode current percent (``CM``) while leaving AM/TTL/emission alone.

        Call after prepare_for_ttl_modulation() (which puts the unit in ACC /
        APC 0). Do **not** re-send APC here — while emission is ON the firmware
        returns ``Not authorized`` and a DL0/DL1 dance would interrupt TTL.

        Args:
            percent: Current setpoint in percent (typically 0–100).

        Returns:
            dict: Results of each command.
        """
        results = {}
        pct = int(round(float(percent)))
        if self.verbose:
            print(f"[LASER] set current → {pct}% (CM, leave emission/TTL as-is)", flush=True)
        results['current'] = self.set_current(pct)
        time.sleep(0.1)
        return results

    def enter_alignment_mode(self, percent=5):
        """
        Continuous low-power beam for optical alignment (no TTL gating).

        LBX command set (Annex A):
          AM 0 → TTL 0 (CW) → APC 0 (ACC) → CM <percent> → DL 1

        ``DM`` / ``I`` are not valid on this firmware (they return ``????``).

        Call prepare_for_ttl_modulation() afterwards to return to experiment
        mode (TTL 1 with emission ON).

        Args:
            percent: Alignment current setpoint in percent (default 5).

        Returns:
            dict: Results of each command.
        """
        results = {}
        pct = int(round(float(percent)))
        if self.verbose:
            print(f"[LASER] === Align ON @ {pct}% ===", flush=True)
        # Change APC / TTL only with emission off (avoids "Not authorized")
        results['emission_off'] = self.emission_off()
        time.sleep(0.05)
        results['AM'] = self.send_command("AM 0")
        time.sleep(0.1)
        results['TTL'] = self.digital_modulation_off()
        time.sleep(0.1)
        results['APC'] = self.send_command("APC 0")
        time.sleep(0.1)
        results['current'] = self.set_current(pct)
        time.sleep(0.1)
        results['emission_on'] = self.emission_on()
        time.sleep(0.1)
        if self.verbose:
            print(f"[LASER] === Align ON done (replies: {results}) ===", flush=True)
        return results

    def set_to_analog_modulation_mode(self, power_mw=100):
        """
        Set laser to analog modulation mode for manual control.
        
        This is the standard state the laser should be left in:
        - Analog modulation ON (AM 1) - allows front panel wheel control
        - Digital modulation OFF (TTL 0)
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
            # APC changes require emission off on this firmware
            results['emission_off'] = self.emission_off()
            time.sleep(0.05)

            results['APC'] = self.send_command("APC 1")
            time.sleep(0.1)
            
            results['AM'] = self.send_command("AM 1")
            time.sleep(0.1)
            
            results['TTL'] = self.digital_modulation_off()
            time.sleep(0.1)
            
            results['power'] = self.set_power(power_mw)
            time.sleep(0.1)

            results['emission_on'] = self.emission_on()
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
        - Digital modulation: OFF (TTL 0)
        - Power control: ON (APC 1)
        - Power: 100 mW (front panel wheel controls 0-100% of this)
        
        Args:
            restore_to_manual_control: If True, restore to analog modulation
                mode before closing (default: True)
        """
        if restore_to_manual_control:
            try:
                # set_to_analog_modulation_mode handles emission off→APC→on
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
        print("   Disabling digital modulation (TTL 0)...")
        result = laser.digital_modulation_off()
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
4. SET to digital control: AM 0, TTL 0
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
- Digital modulation: OFF (TTL 0)
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

COMMAND REFERENCE (LBX Annex A)
-----------------
- DL 1 / DL 0: Emission ON / OFF
- APC 1 / APC 0: Power mode / Current mode (ACC)
- AM 1 / AM 0: Analog modulation ON / OFF
- TTL 1 / TTL 0: Digital (TTL) modulation ON / OFF  (NOT "DM" — returns ????)
- CW 1 / CW 0: Alternate aliases (CW 1 = digital mod OFF, CW 0 = ON)
- PM <mW>: Set power without EEPROM wear
- CM <%>: Set diode current percent of nominal (0–125)  (NOT "I" — returns ????)
- C <%>: Same as CM but saves to EEPROM
- ?P / ?SC / ?SP: Query measured power / current setpoint (mA) / power setpoint
- ???? reply: command not understood
- "Not authorized": often means APC was changed while emission was ON

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
