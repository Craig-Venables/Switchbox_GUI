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
# Keithley 4200 SMU — minimal bias-only GPIB wrapper
# ---------------------------------------------------------------------------

class _Keithley4200Bias:
    """
    Minimal KXCI wrapper for simple DC bias on a Keithley 4200-SCS.

    Only sends the three KXCI commands needed for bias-and-hold:
      DV <ch>,0,<voltage>,<compliance>   — set voltage
      CN <ch>                            — connect (enable output)
      CL <ch>                            — clear/disconnect (disable output)

    No UL mode, no pulse functions.
    """

    def __init__(self, address: str = "GPIB0::17::INSTR") -> None:
        self.address = address
        self._rm = None
        self._inst = None
        self._output_on = False
        self._channel = 1

    def connect(self) -> bool:
        if not _PYVISA_OK:
            raise RuntimeError("pyvisa not installed — cannot connect to 4200.")
        try:
            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(self.address)
            self._inst.timeout = 10_000
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

    def set_bias(self, voltage: float, compliance: float = 1e-3, channel: int = 1) -> None:
        """Source voltage on the given SMU channel with current compliance."""
        if not self._inst:
            raise RuntimeError("4200 not connected.")
        self._channel = channel
        # KXCI DV: DV channel,range,voltage,compliance  (range 0 = auto)
        self._inst.write(f"DV {channel},0,{voltage:.6f},{compliance:.6e}")
        time.sleep(0.05)
        self._inst.write(f"CN {channel}")
        self._output_on = True

    def output_off(self, channel: Optional[int] = None) -> None:
        if not self._inst:
            return
        ch = channel or self._channel
        try:
            self._inst.write(f"CL {ch}")
        except Exception:
            pass
        self._output_on = False

    def disconnect(self) -> None:
        try:
            if self._output_on:
                self.output_off()
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
          fg_mode            — "simple" or "arb"
          pulse_high_v, pulse_low_v, pulse_width_ns, pulse_rate_hz, burst_count
          arb_samples        — List[float] normalised [-1,+1] (fg_mode="arb")
          arb_freq_hz, arb_amplitude_v, arb_offset_v, arb_name
          scope_channel, timebase_us, trig_level_v, volts_per_div
          auto_configure_scope
          capture_wait_s
        """
        p = params
        scope_ch       = int(p.get("scope_channel", 1))
        capture_wait   = float(p.get("capture_wait_s", 0.2))
        auto_cfg_scope = bool(p.get("auto_configure_scope", True))

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

        on_progress("Configuring function generator…")
        fg_mode = str(p.get("fg_mode", "simple")).lower()

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
        else:
            # Simple rectangular pulse via built-in PULSE waveform
            high_v  = float(p.get("pulse_high_v", 3.3))
            low_v   = float(p.get("pulse_low_v",  0.0))
            width_s = float(p.get("pulse_width_ns", 100.0)) * 1e-9
            rate_hz = float(p.get("pulse_rate_hz", 1000.0))
            self.fg.set_pulse_shape(
                channel=1,
                frequency_hz=rate_hz,
                high_level_v=high_v,
                low_level_v=low_v,
                pulse_width_s=width_s,
            )

        burst_count = int(p.get("burst_count", 1))
        self.fg.enable_burst(channel=1, mode="NCYC", cycles=burst_count, trigger_source="BUS")
        self.fg.output(1, True)

        if self._stop_event.is_set():
            raise RuntimeError("Measurement stopped by user.")

        # ── 4. Configure scope ───────────────────────────────────────────────
        if not self._scope:
            raise RuntimeError("Oscilloscope not connected.")

        on_progress("Configuring oscilloscope…")
        if auto_cfg_scope:
            self._configure_scope(params)

        # Arm scope — wait for external trigger
        self._scope.write("ACQ:STOPA SEQ")   # stop after one acquisition
        self._scope.write("ACQ:STATE RUN")
        time.sleep(0.015)  # 15 ms: ensure scope is armed before firing FG

        if self._stop_event.is_set():
            raise RuntimeError("Measurement stopped by user.")

        # ── 5. Fire FG burst ─────────────────────────────────────────────────
        on_progress("Firing laser pulse…")
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
                state = self._scope.query("ACQ:STATE?").strip()
                if state == "0":
                    time.sleep(capture_wait)
                    break
            except Exception:
                break

        # ── 7. Read waveform ─────────────────────────────────────────────────
        on_progress("Reading waveform…")
        time_arr, volt_arr = self._read_waveform(scope_ch)

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
        """Push timebase, channel scale, and trigger settings to scope."""
        scope = self._scope
        if not scope:
            return
        ch        = int(params.get("scope_channel", 1))
        tb_us     = float(params.get("timebase_us", 0.5))
        trig_v    = float(params.get("trig_level_v", 0.1))
        v_per_div = float(params.get("volts_per_div", 0.5))
        tb_s      = tb_us * 1e-6

        try:
            scope.write("*RST")
            time.sleep(0.3)
            scope.write(f"CH{ch}:SCA {v_per_div:.4f}")
            scope.write(f"HOR:SCA {tb_s:.10f}")
            scope.write("TRIG:MAI:TYP EDGE")
            scope.write("TRIG:MAI:EDGE:SOU EXT")
            scope.write("TRIG:MAI:EDGE:SLO RISE")
            scope.write(f"TRIG:MAI:LEV {trig_v:.4f}")
            scope.write(f"ACQ:STOPA SEQ")
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
