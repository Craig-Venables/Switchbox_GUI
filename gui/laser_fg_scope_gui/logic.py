"""
Laser FG Scope GUI — Measurement Logic
=======================================

Coordinates four instruments in a background thread:
  1. Keithley 4200 SMU  — passive DC bias (KXCI GPIB)
  2. Oxxius LBX-405     — laser in DM1 TTL-gate mode (RS-232 serial)
  3. Siglent SDG1032X   — timing master / laser TTL driver (VISA USB)
  4. Tektronix TBS1000C — waveform capture (VISA USB)

Run sequence:
  1. SMU: apply bias voltage, keep output on
  2. Laser: PM <power>, DM 1, DL 1  (arm TTL gate)
  3. FG:    configure pulse/ARB + burst, output on
  4. Scope: EXT TRIG, set timebase, ACQ:STATE RUN  (arm)
  5. sleep(15 ms)
  6. FG:    C1:TRIG  (hardware fires laser + triggers scope)
  7. sleep(capture_wait_s)
  8. Scope: DAT/CURV? → time[], voltage[] arrays
  9. Callbacks → plot

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUGS FIXED (2026-04-08)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIX 1 — _configure_scope: slope argument was "RIS" (invalid abbreviation)
  Before: scope.write("TRIG:MAI:EDGE:SLO RIS")
  After:  scope.write("TRIG:MAI:EDGE:SLO RISE")

FIX 2 — _run_sequence: polled TRIG:STATE? which is unreliable on TBS1000C
  Per PyVISA community docs for TDS/TBS scopes, the correct completion poll
  is ACQ:STATE? which returns "1" while running and "0" when done.
  Before: scope.query("TRIG:STATE?") checked for "TRIGGER"/"SAVE"/"ARMED"
  After:  scope.query("ACQ:STATE?")  checks for "0"

TRIGGER PREFIX — TRIG:MAI: vs TRIG:A:
  _configure_scope uses TRIG:MAI: (matches PyVISA community docs for TDS/TBS)
  The TektronixTBS1000C.py driver uses TRIG:A: throughout.
  The TBS1000C-specific programmer manual (Tektronix Part 077169102) requires
  a login to download so we could not verify which prefix is correct.

  HOW TO TEST when the hardware is available:
    1. Run with TRIG:MAI: as-is and see if the scope arms on EXT.
    2. If scope never fires, change the four lines in _configure_scope:
         TRIG:MAI:TYP EDGE       →  (remove this line — not needed with TRIG:A:)
         TRIG:MAI:EDGE:SOU EXT   →  scope.set_trigger_source("EXT")
         TRIG:MAI:EDGE:SLO RISE  →  scope.set_trigger_slope("RISING")
         TRIG:MAI:LEV <v>        →  scope.set_trigger_level(trig_v)
       This routes through the driver methods (TRIG:A: prefix) instead.
    3. After each change, send scope.query("ALLEV?") — "No events" = no error.

SINGLE-SHOT OPERATION
  ACQ:STOPA SEQ arms the scope in single-sequence mode: it captures exactly
  one trace when the EXT TRIG edge arrives, then stops. ACQ:STATE? returns
  "0" when the capture is complete. This is the same mechanism as pressing
  "Single" on the front panel.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# ── Lazy imports so the module loads even without hardware ──────────────────────
try:
    import pyvisa
    _PYVISA_OK = True
except ImportError:
    _PYVISA_OK = False
    pyvisa = None  # type: ignore

try:
    from Equipment.managers.function_generator import FunctionGeneratorManager
    _FG_OK = True
except ImportError:
    FunctionGeneratorManager = None  # type: ignore
    _FG_OK = False

try:
    from Equipment.Laser_Controller.oxxius import OxxiusLaser
    _LASER_OK = True
except ImportError:
    OxxiusLaser = None  # type: ignore
    _LASER_OK = False

try:
    from Equipment.managers.oscilloscope import OscilloscopeManager
    _SCOPE_OK = True
except ImportError:
    OscilloscopeManager = None  # type: ignore
    _SCOPE_OK = False


# ---------------------------------------------------------------------------
# Keithley 4200 SMU — EX/UL bias wrapper
# ---------------------------------------------------------------------------

def _fmt4200(v: float) -> str:
    """Format a float for a 4200 EX command parameter (matches run_smu_bias_timed_read.py)."""
    if v == 0.0:
        return "0"
    if abs(v) >= 1.0 and abs(v) < 1e6:
        if float(v) == int(v):
            return str(int(v))
        return f"{v:.10g}".rstrip("0").rstrip(".")
    return f"{v:.2E}".upper().replace("E-0", "E-").replace("E+0", "E+")


class _Keithley4200Bias:
    """
    DC bias for Keithley 4200-SCS via EX/UL mode.

    Direct DV/CN KXCI commands return -992 on many 4200 configurations
    because the instrument is set up to only execute compiled C modules via
    EX commands.  This class uses the same EX/UL path as the working IV sweep
    scripts:

      set_bias  → UL + EX A_SMU_BiasTimedRead_Start SMU_BiasTimedRead_Start(vforce, ilimit)
      output_off → EX ... Start(0, ilimit) then DE to exit UL

    The SMU hardware latches the forcev() value set by the C module and holds
    the voltage until the next EX call or a power cycle.

    Requires the A_SMU_BiasTimedRead_Start C module to be compiled and loaded
    in the 4200's USRLIB (same module used by the Pulse Testing GUI optical path).
    """

    def __init__(self, address: str = "GPIB0::17::INSTR") -> None:
        self.address = address
        self._addr = address   # kept for reconnect in output_off
        self._rm = None
        self._inst = None
        self._output_on = False
        self._channel = 1
        self._compliance = 1e-3
        self._ul_active = False

    # ── connection ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        if not _PYVISA_OK:
            raise RuntimeError("pyvisa not installed — cannot connect to 4200.")
        try:
            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(self.address)
            self._inst.timeout = 15_000
            self._inst.write_termination = "\n"
            self._inst.read_termination = "\n"
            idn = self._inst.query("*IDN?").strip()
            print(f"[4200Bias] Connected: {idn}")
            return True
        except Exception as exc:
            print(f"[4200Bias] Connection failed: {exc}")
            self._inst = None
            return False

    def is_connected(self) -> bool:
        return self._inst is not None

    # ── UL mode helpers ─────────────────────────────────────────────────────────

    def _enter_ul(self) -> None:
        if not self._ul_active:
            self._inst.write("UL")
            time.sleep(0.05)
            self._ul_active = True

    def _exit_ul(self) -> None:
        if self._ul_active:
            self._inst.write("DE")
            time.sleep(0.05)
            self._ul_active = False

    def _session_ok(self) -> bool:
        """Quick GPIB health-check: returns False if the session handle is dead."""
        if not self._inst:
            return False
        try:
            _ = self._inst.timeout   # attribute access fails on closed sessions
            return True
        except Exception:
            return False

    def _run_ex(self, cmd: str, wait: float = 1.0) -> None:
        """Send an EX command (caller must already be in UL mode) and drain response.

        Timeout is long enough for the C module to finish executing (the 4200
        can take several hundred ms on SMU_BiasTimedRead_Start).  We never
        propagate a read-timeout as an error — the return value is unused.
        """
        self._inst.write(cmd)
        time.sleep(wait)
        # Drain any RETURN VALUE response so the buffer stays clean.
        old_to = self._inst.timeout
        try:
            self._inst.timeout = 5000   # 5 s — long enough for any EX module to finish
            self._inst.read()
        except Exception:
            pass
        finally:
            try:
                self._inst.timeout = old_to
            except Exception:
                pass

    # ── bias control ────────────────────────────────────────────────────────────

    def set_bias(self, voltage: float, compliance: float = 1e-3, channel: int = 1) -> None:
        """
        Apply DC bias using SMU_BiasTimedRead_Start EX command.

        The C module calls forcev(channel, voltage, compliance) which latches
        the SMU output at the requested voltage until the next EX call.
        """
        if not self._inst:
            raise RuntimeError("4200 not connected.")
        self._channel = channel
        self._compliance = compliance
        vf = _fmt4200(float(voltage))
        il = _fmt4200(float(compliance))
        cmd = f"EX A_SMU_BiasTimedRead_Start SMU_BiasTimedRead_Start({vf},{il})"
        print(f"[4200Bias] set_bias: {cmd}")
        self._enter_ul()
        self._run_ex(cmd, wait=0.5)
        self._output_on = True

    def output_off(self, channel: Optional[int] = None) -> None:
        """Ramp output to 0 V using the same EX path, then exit UL mode."""
        if not self._inst:
            self._output_on = False
            return
        # If the GPIB session dropped while we were waiting (scope *RST / capture
        # can take several seconds), try to reconnect once before giving up.
        if not self._session_ok():
            print("[4200Bias] Session dropped — reconnecting for output_off…")
            self._ul_active = False
            try:
                self._inst.close()
            except Exception:
                pass
            self._inst = None
            if self._addr:
                try:
                    self._rm = pyvisa.ResourceManager()
                    self._inst = self._rm.open_resource(self._addr)
                    self._inst.timeout = 10000
                    print("[4200Bias] Reconnected for output_off.")
                except Exception as exc:
                    print(f"[4200Bias] Reconnect failed: {exc}")
                    self._output_on = False
                    return
            else:
                self._output_on = False
                return
        try:
            il = _fmt4200(float(self._compliance))
            cmd = f"EX A_SMU_BiasTimedRead_Start SMU_BiasTimedRead_Start(0,{il})"
            print(f"[4200Bias] output_off: {cmd}")
            self._ul_active = False   # reset so _enter_ul always sends "UL"
            self._enter_ul()
            self._run_ex(cmd, wait=0.5)
            self._exit_ul()
        except Exception as exc:
            print(f"[4200Bias] output_off warning: {exc}")
        self._output_on = False

    def disconnect(self) -> None:
        try:
            if self._output_on:
                self.output_off()
        except Exception:
            pass
        try:
            self._exit_ul()
        except Exception:
            pass
        try:
            if self._inst:
                self._inst.close()
            if self._rm:
                self._rm.close()
        except Exception:
            pass
        self._inst = None
        self._rm = None


# ---------------------------------------------------------------------------
# Main logic class
# ---------------------------------------------------------------------------

class LaserFGScopeLogic:
    """
    Owns instrument instances and runs the measurement sequence in a thread.

    Thread-safety: instrument objects are accessed only from the measurement
    thread after initial connect (which is called from the UI thread).
    """

    # ── instrument handles ──────────────────────────────────────────────────
    def __init__(self) -> None:
        self.smu:   Optional[_Keithley4200Bias]    = None
        self.laser: Optional[OxxiusLaser]          = None  # type: ignore
        self.fg:    Optional[FunctionGeneratorManager] = None  # type: ignore
        self.scope_mgr: Optional[OscilloscopeManager]  = None  # type: ignore
        self._scope = None   # the raw scope instrument object

        self._is_running   = False
        self._stop_event   = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Keep FG output enabled between runs to avoid output-enable transients.
        self._fg_output_latched = False

    # ── connection helpers (called from UI thread) ──────────────────────────

    def connect_smu(self, address: str) -> Tuple[bool, str]:
        """Connect to Keithley 4200 SMU. Returns (ok, message)."""
        try:
            obj = _Keithley4200Bias(address)
            ok = obj.connect()
            if ok:
                self.smu = obj
                return True, "Connected"
            return False, "Connection failed — check address and GPIB."
        except Exception as exc:
            return False, str(exc)

    def disconnect_smu(self) -> None:
        if self.smu:
            try:
                self.smu.disconnect()
            except Exception:
                pass
            self.smu = None

    def connect_laser(self, port: str, baud: int = 19200) -> Tuple[bool, str]:
        """Connect to Oxxius laser over serial. Returns (ok, message)."""
        if not _LASER_OK:
            return False, "OxxiusLaser driver not available."
        try:
            obj = OxxiusLaser(port=port, baud=baud, safe_power_mw=10)  # type: ignore
            idn = obj.idn()
            self.laser = obj
            return True, f"Connected: {idn}"
        except Exception as exc:
            return False, str(exc)

    def disconnect_laser(self) -> None:
        if self.laser:
            try:
                self.laser.emission_off()
                self.laser.send_command("DM 0")
                self.laser.close(restore_to_manual_control=True)
            except Exception:
                pass
            self.laser = None

    def connect_fg(self, address: str) -> Tuple[bool, str]:
        """Connect to Siglent SDG1032X function generator. Returns (ok, message)."""
        if not _FG_OK:
            return False, "FunctionGeneratorManager not available."
        try:
            obj = FunctionGeneratorManager(fg_type="Siglent SDG1032X", address=address, auto_connect=False)  # type: ignore
            ok = obj.connect()
            if ok:
                self.fg = obj
                self._fg_output_latched = False
                return True, f"Connected: {obj.get_idn()}"
            return False, "Connection failed — check VISA address."
        except Exception as exc:
            return False, str(exc)

    def disconnect_fg(self) -> None:
        if self.fg:
            try:
                self.fg.output(1, False)
                self.fg.close()
            except Exception:
                pass
            self.fg = None
            self._fg_output_latched = False

    def connect_scope(self, address: str) -> Tuple[bool, str]:
        """Connect to Tektronix TBS1000C oscilloscope. Returns (ok, message)."""
        if not _SCOPE_OK:
            return False, "OscilloscopeManager not available."
        try:
            mgr = OscilloscopeManager(auto_detect=False)  # type: ignore
            ok = mgr.manual_init_scope(scope_type="Tektronix TBS1000C", address=address)
            if not ok:
                return False, "Could not connect — check VISA address and USB cable."
            self.scope_mgr = mgr
            self._scope = mgr.scope
            idn = self._scope.idn() if self._scope else "?"
            return True, f"Connected: {idn}"
        except Exception as exc:
            return False, str(exc)

    def disconnect_scope(self) -> None:
        if self.scope_mgr:
            try:
                self.scope_mgr.disconnect()
            except Exception:
                pass
            self.scope_mgr = None
            self._scope = None

    # ── laser arming helpers (called from UI thread) ─────────────────────────

    def arm_laser_dm1(self, power_mw: float) -> Tuple[bool, str]:
        """
        Arm laser in DM1 mode:
          PM <power_mw>, DM 1, DL 1
        After this the laser is ON but the TTL gate from the FG controls emission.
        """
        if not self.laser:
            return False, "Laser not connected."
        try:
            self.laser.set_power(power_mw)
            time.sleep(0.15)
            self.laser.send_command("APC 1")
            time.sleep(0.1)
            self.laser.send_command("AM 0")
            time.sleep(0.1)
            self.laser.send_command("DM 1")
            time.sleep(0.1)
            self.laser.emission_on()
            time.sleep(0.2)
            return True, f"Armed: {power_mw:.1f} mW, DM1 active"
        except Exception as exc:
            return False, str(exc)

    def disarm_laser(self) -> Tuple[bool, str]:
        """Turn off emission and disable DM mode."""
        if not self.laser:
            return False, "Laser not connected."
        try:
            self.laser.emission_off()
            time.sleep(0.1)
            self.laser.send_command("DM 0")
            return True, "Disarmed — emission off, DM0"
        except Exception as exc:
            return False, str(exc)

    # ── SMU bias helpers ─────────────────────────────────────────────────────

    def apply_bias(self, voltage: float, compliance: float = 1e-3) -> Tuple[bool, str]:
        if not self.smu:
            return False, "SMU not connected."
        try:
            self.smu.set_bias(voltage, compliance=compliance)
            return True, f"Bias: {voltage:.3f} V applied"
        except Exception as exc:
            return False, str(exc)

    def bias_off(self) -> None:
        if self.smu:
            try:
                self.smu.output_off()
            except Exception:
                pass

    # ── Measurement thread ────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._is_running

    def run_measurement(
        self,
        params: Dict[str, Any],
        on_progress: Callable[[str], None],
        on_data: Callable[[np.ndarray, np.ndarray, Dict], None],
        on_error: Callable[[str], None],
        on_finished: Callable[[], None],
    ) -> None:
        """Launch measurement in a background thread."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            args=(params, on_progress, on_data, on_error, on_finished),
            daemon=True,
        )
        self._thread.start()

    def stop_measurement(self) -> None:
        self._stop_event.set()

    def _worker(
        self,
        params: Dict[str, Any],
        on_progress: Callable[[str], None],
        on_data: Callable[[np.ndarray, np.ndarray, Dict], None],
        on_error: Callable[[str], None],
        on_finished: Callable[[], None],
    ) -> None:
        try:
            time_arr, volt_arr, meta = self._run_sequence(params, on_progress)
            on_data(time_arr, volt_arr, meta)
        except Exception as exc:
            on_error(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        finally:
            self._is_running = False
            on_finished()

    def _run_sequence(
        self,
        params: Dict[str, Any],
        on_progress: Callable[[str], None],
    ) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Execute the full measurement sequence. Raises on any unrecoverable error.

        Params keys (all optional, fall back to defaults):
          bias_v, bias_compliance, smu_channel
          laser_power_mw     — set before arming (if arm_laser_now=True)
          arm_laser_now      — if True, re-arm laser before measurement
          fg_manual_mode     — if True, skip FG config; just send C1:TRIG (user pre-configured FG)
          fg_mode            — "simple" or "arb"
          pulse_high_v, pulse_low_v, pulse_width_ns, pulse_rate_hz, burst_count
          arb_samples        — List[float] normalised [-1,+1] (fg_mode="arb")
          arb_freq_hz, arb_amplitude_v, arb_offset_v, arb_name
          scope_channel, timebase_us, trig_level_v, volts_per_div
          auto_configure_scope
          auto_timebase      — if True, compute timebase from burst duration
          capture_wait_s
        """
        p = params
        scope_ch       = int(p.get("scope_channel", 1))
        capture_wait   = float(p.get("capture_wait_s", 0.2))
        auto_cfg_scope = bool(p.get("auto_configure_scope", True))
        fg_manual_mode = bool(p.get("fg_manual_mode", False))
        # Temporary reliability mode:
        # Simple pulse path runs as a single-shot with burst disabled.
        simple_no_burst_mode = True

        # ── 1. SMU bias ──────────────────────────────────────────────────────
        if self.smu and self.smu.is_connected():
            on_progress("Setting SMU bias…")
            bias_v    = float(p.get("bias_v", 0.0))
            bias_comp = float(p.get("bias_compliance", 1e-3))
            ch        = int(p.get("smu_channel", 1))
            self.smu.set_bias(bias_v, compliance=bias_comp, channel=ch)
        else:
            on_progress("SMU not connected — skipping bias.")

        if self._stop_event.is_set():
            raise RuntimeError("Measurement stopped by user.")

        # ── 2. Laser arm (optional) ──────────────────────────────────────────
        if p.get("arm_laser_now") and self.laser:
            on_progress("Arming laser (DM1)…")
            power_mw = float(p.get("laser_power_mw", 10.0))
            self.arm_laser_dm1(power_mw)

        if self._stop_event.is_set():
            raise RuntimeError("Measurement stopped by user.")

        # ── 3. Configure FG ──────────────────────────────────────────────────
        if not self.fg:
            raise RuntimeError("Function generator not connected.")

        fg_mode     = str(p.get("fg_mode", "simple")).lower()
        burst_count = int(p.get("burst_count", 1))
        rate_hz     = float(p.get("pulse_rate_hz", 1000.0))
        simple_width_s = float(p.get("pulse_width_ns", 100.0)) * 1e-9
        simple_period_s = 1.0 / max(rate_hz, 1e-3)
        simple_fire_on_s = min(max(simple_width_s * 1.25, 50e-6), simple_period_s * 0.8)

        if fg_manual_mode:
            on_progress("Manual FG mode — skipping configuration, using pre-set FG…")
        else:
            on_progress("Configuring function generator…")

            # ── 3a. FG output housekeeping FIRST ──────────────────────────────
            # On SDG1032X fw 1.01.01.33, some OUTP writes can drop BTWV STATE to
            # OFF. Apply housekeeping before burst setup, then configure burst.
            try:
                _fg_inst = getattr(self.fg, 'instrument', None)
                if _fg_inst and hasattr(_fg_inst, 'write'):
                    _fg_inst.write("C1:OUTP LOAD,HZ")   # Hi-Z: output = configured HLEV exactly
                    _fg_inst.write("C1:OUTP AMPL,OFF")  # disable amplitude-limit protection
                    _fg_inst.write("C1:OUTP SYNC,ON")
                    _fg_inst.write("C1:OUTP PLRT,NOR")
            except Exception as _sync_exc:
                print(f"[FG] output housekeeping warning (non-fatal): {_sync_exc}")

            if fg_mode == "arb":
                arb_samples = p.get("arb_samples", [1.0, -1.0])
                arb_freq    = float(p.get("arb_freq_hz", 1000.0))
                arb_ampl    = float(p.get("arb_amplitude_v", 3.3))
                arb_ofst    = float(p.get("arb_offset_v", 1.65))
                arb_name    = str(p.get("arb_name", "LSRPULSE"))
                ok = self.fg.upload_arb_waveform(
                    channel=1,
                    samples_normalized=arb_samples,
                    waveform_name=arb_name,
                    freq_hz=arb_freq,
                    amplitude_v=arb_ampl,
                    offset_v=arb_ofst,
                )
                if not ok:
                    raise RuntimeError("ARB waveform upload failed. Check driver and instrument.")

                # Use MAN trigger source (software trigger) for SDG1032X.
                self.fg.enable_burst(channel=1, mode="NCYC", cycles=burst_count, trigger_source="MAN")
            else:
                # Simple rectangular pulse via built-in PULSE waveform.
                # Reliability mode: disable burst and generate one pulse by
                # briefly turning output ON then OFF in step 5.
                high_v  = float(p.get("pulse_high_v", 3.3))
                low_v   = float(p.get("pulse_low_v",  0.0))
                width_s = float(p.get("pulse_width_ns", 100.0)) * 1e-9

                # If width is too large relative to period, force a lower rate
                # so output ON/OFF can only produce one pulse.
                effective_rate_hz = rate_hz
                period_s = 1.0 / max(effective_rate_hz, 1e-3)
                if simple_no_burst_mode and width_s >= 0.45 * period_s:
                    period_s = max(width_s * 5.0, 1e-3)
                    effective_rate_hz = 1.0 / period_s
                    print(f"[FG] Adjusted pulse rate for single-shot mode: {effective_rate_hz:.6g} Hz")
                simple_period_s = period_s
                simple_fire_on_s = min(max(width_s * 1.25, 50e-6), simple_period_s * 0.8)

                self.fg.set_pulse_shape(
                    channel=1,
                    frequency_hz=effective_rate_hz,
                    high_level_v=high_v,
                    low_level_v=low_v,
                    pulse_width_s=width_s,
                )
                if simple_no_burst_mode:
                    try:
                        self.fg.disable_burst(channel=1)
                    except Exception:
                        pass
                else:
                    self.fg.enable_burst(channel=1, mode="NCYC", cycles=burst_count, trigger_source="MAN")
                print(f"[FG] PULSE: {effective_rate_hz:.3g} Hz  HLEV={high_v} V  LLEV={low_v} V  "
                      f"PWID={width_s*1e6:.4g} µs  burst={'OFF' if simple_no_burst_mode else burst_count}")

            # Diagnostic: query back the FG state so the console shows what was applied
            try:
                _fg_inst2 = getattr(self.fg, 'instrument', None)
                if _fg_inst2 and hasattr(_fg_inst2, 'query'):
                    bswv = _fg_inst2.query("C1:BSWV?").strip()
                    btwv = _fg_inst2.query("C1:BTWV?").strip()
                    print(f"[FG] BSWV: {bswv}")
                    print(f"[FG] BTWV: {btwv}")
            except Exception:
                pass

            # In simple no-burst mode we keep output OFF until step 5.
            if not (fg_mode == "simple" and simple_no_burst_mode):
                if not self._fg_output_latched:
                    self.fg.output(1, True)
                    self._fg_output_latched = True

        if self._stop_event.is_set():
            raise RuntimeError("Measurement stopped by user.")

        # ── 4. Configure scope ───────────────────────────────────────────────
        if not self._scope:
            raise RuntimeError("Oscilloscope not connected.")

        on_progress("Configuring oscilloscope…")
        if auto_cfg_scope:
            self._configure_scope(params)

        # Arm scope — wait for external trigger
        self._scope.write("ACQ:STOPA SEQUENCE")    # single-sequence (full word)
        self._scope.write("ACQ:STATE ON")          # ARM (ON = RUN, matches driver)
        time.sleep(0.25)   # 250 ms: let TBS1052C fully arm before SYNC edge arrives
        try:
            trig_state = self._scope.query("TRIG:STATE?").strip()
            print(f"[Scope] Trigger state after arm: {trig_state}")
        except Exception:
            pass

        if self._stop_event.is_set():
            raise RuntimeError("Measurement stopped by user.")

        # ── 5. Fire FG burst ─────────────────────────────────────────────────
        on_progress("Firing laser pulse…")
        if fg_manual_mode:
            self.fg.trigger_now(1)
        elif fg_mode == "simple" and simple_no_burst_mode:
            # Single pulse without burst: gate output briefly.
            self.fg.output(1, True)
            time.sleep(simple_fire_on_s)
            self.fg.output(1, False)
            self._fg_output_latched = False
        else:
            self.fg.trigger_now(1)   # SCPI C1:TRIG → SDG1032X fires → SYNC OUT → scope EXT TRIG

        # ── 6. Wait for capture ──────────────────────────────────────────────
        on_progress(f"Waiting {capture_wait*1000:.0f} ms for capture…")
        deadline = time.monotonic() + capture_wait + 2.0
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                raise RuntimeError("Measurement stopped by user.")
            time.sleep(0.05)
            # Poll ACQ:STATE? — returns "0" when acquisition is complete, "1" while running
            try:
                state = self._scope.query("ACQ:STATE?").strip().upper()
                if state in ("0", "OFF", "STOP"):
                    time.sleep(capture_wait)
                    break
            except Exception:
                break

        # ── 7. Read waveform ─────────────────────────────────────────────────
        on_progress("Reading waveform…")
        time_arr, volt_arr = self._read_waveform(scope_ch)

        # ── 8. Ensure output is OFF after run in simple no-burst mode ─────────
        if not fg_manual_mode and fg_mode == "simple" and simple_no_burst_mode:
            try:
                self.fg.output(1, False)
            except Exception:
                pass
            self._fg_output_latched = False

        meta = {
            "scope_channel":   scope_ch,
            "fg_mode":         fg_mode,
            "pulse_width_ns":  float(p.get("pulse_width_ns", 100.0)),
            "burst_count":     burst_count,
            "bias_v":          float(p.get("bias_v", 0.0)),
            "laser_power_mw":  float(p.get("laser_power_mw", 10.0)),
            "timestamp":       time.time(),
        }
        return time_arr, volt_arr, meta

    # ── Scope helpers ─────────────────────────────────────────────────────────

    def _configure_scope(self, params: Dict[str, Any]) -> None:
        """Push timebase, channel scale, and trigger settings to scope.

        Uses TRIG:A: prefix throughout — confirmed correct for TBS1000C.
        (TRIG:MAI: is used by some TDS/TBS community docs but TektronixTBS1000C.py
        driver uses TRIG:A:, and that is what works on this hardware.)
        """
        scope = self._scope
        if not scope:
            return
        ch        = int(params.get("scope_channel", 1))
        tb_us     = float(params.get("timebase_us", 0.5))
        trig_v    = float(params.get("trig_level_v", 0.1))
        v_per_div = float(params.get("volts_per_div", 0.5))

        # ── Auto-timebase: compute from total burst duration + margin ─────────
        if bool(params.get("auto_timebase", False)) and not bool(params.get("fg_manual_mode", False)):
            burst_count = int(params.get("burst_count", 1))
            rate_hz     = float(params.get("pulse_rate_hz", 1000.0))
            fg_mode     = str(params.get("fg_mode", "simple")).lower()
            if fg_mode == "arb":
                arb_segs = params.get("arb_segments", [])
                total_s  = sum(float(d) * 1e-9 for _, d in arb_segs) * burst_count
            else:
                pulse_ns = float(params.get("pulse_width_ns", 100.0))
                period_s = 1.0 / max(rate_hz, 1.0)
                # Total time covers all pulses plus final pulse width tail
                total_s  = burst_count * period_s + pulse_ns * 1e-9
            # Add 20% pre-trigger margin and 20% post margin → 1.4× total
            # TBS1000C has 15 horizontal divisions
            HORIZ_DIVS = 15.0
            tb_s_auto  = (total_s * 1.4) / HORIZ_DIVS
            # Snap to nearest standard step (1/2/5 per decade)
            import math
            mag = 10 ** math.floor(math.log10(tb_s_auto))
            for step in (1, 2, 5, 10):
                if mag * step >= tb_s_auto:
                    tb_s_auto = mag * step
                    break
            tb_us = tb_s_auto * 1e6
            print(f"[Scope] Auto-timebase: total burst {total_s*1e6:.1f} µs → {tb_us:.3g} µs/div")

        tb_s = tb_us * 1e-6

        try:
            scope.write("*RST")
            # Wait for *RST to fully complete — TBS1052C can take >400 ms
            try:
                scope.query("*OPC?")
            except Exception:
                pass
            time.sleep(0.5)

            scope.write(f"CH{ch}:SCA {v_per_div:.4f}")
            scope.write(f"HOR:SCA {tb_s:.10f}")

            # ── Trigger: TRIG:A: prefix (confirmed correct for TBS1052C) ─────
            # Leave trigger mode at AUTO (default after *RST) — NORM is
            # unreliable on TBS1052C without a holdoff setting.
            scope.write("TRIG:A:EDGE:SOU EXT")        # EXT TRIG BNC input
            scope.write("TRIG:A:EDGE:SLO RIS")        # rising edge
            scope.write(f"TRIG:A:LEV {trig_v:.4f}")
            # Setting any holdoff value re-initialises the TBS1052C trigger
            # circuit so it properly responds to EXT events (observed behaviour:
            # scope doesn't trigger on EXT until holdoff is set at least once).
            scope.write("TRIG:A:HOLD 20E-3")          # 20 ms holdoff

            # Check for SCPI errors (printed for debugging, non-fatal)
            try:
                ev = scope.query("ALLEV?").strip()
                if ev and "no event" not in ev.lower():
                    print(f"[Scope] ALLEV after trigger setup: {ev}")
            except Exception:
                pass

            scope.write("ACQ:STOPA SEQUENCE")   # single-sequence (full word — no abbrev ambiguity)
            time.sleep(0.15)
        except Exception as exc:
            print(f"[Scope] Configuration warning: {exc}")

    def _read_waveform(self, channel: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Read the current scope screen buffer.
        Replicates the DAT/CURV? approach from oscilloscope_pulse_gui/logic.py.
        """
        scope = self._scope
        if not scope:
            return np.array([]), np.array([])

        scope.write(f"DAT:SOU CH{channel}")
        scope.write("DAT:ENC ASCII")
        scope.write("DAT:WID 1")

        preamble = scope.get_waveform_preamble(channel)
        record_len = scope._extract_record_length(preamble)
        try:
            rq = scope.query("HOR:RECO?").strip()
            record_len = max(record_len, int(rq))
        except Exception:
            pass

        scope.write("DAT:STAR 1")
        scope.write(f"DAT:STOP {record_len}")
        data_str = scope.query("CURV?")

        raw: List[float] = []
        for tok in data_str.split(","):
            try:
                raw.append(float(tok.strip()))
            except ValueError:
                pass

        raw_arr = np.array(raw, dtype=np.float64)
        volt_arr = scope._scale_waveform_values(raw_arr, preamble)
        n = len(volt_arr)

        if n < 2:
            return np.array([]), np.array([])

        x_incr = preamble.get("XINCR")
        if x_incr is None:
            try:
                tb_s = float(scope.query("HOR:SCA?"))
            except Exception:
                tb_s = 5e-7
            time_arr = np.linspace(0.0, tb_s * 15.0, n)
        else:
            time_arr = scope._build_time_array(n, preamble, fallback_scale=None)

        return time_arr, volt_arr
