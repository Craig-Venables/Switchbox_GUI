# Automated_tester_GUI.py
"""
Automated memristor tester (Excel-driven, TSP-capable)

Replace your existing file with this. It:
 - Loads lot/sections/devices from Excel (flexible column names).
 - Attempts TSP-based embedded sweep via instrument.run_tsp_sweep(...) (preferred).
 - Falls back to ad-hoc TSP scripting or to Python-controlled forming if necessary.
 - Adds a GUI button to run a full batch from the Excel device manifest.
"""

import os
import json
import math
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pandas as pd
except Exception:
    pd = None
    print("Warning: pandas not available. Excel config will be unavailable.")

# ---------------------------
# Defaults
# ---------------------------
DEFAULTS = {
    "Icomp_start_A": 1e-4,
    "Icomp_max_A": 1e-3,
    "V_form_max_V": 3.0,
    "energy_budget_J": 0.02,
    "area_um2": 10000.0,
    "pulse_widths_s": [100e-6, 1e-3, 10e-3],
    "pulse_deltaV": 0.1,
    "V_read": 0.1,
    "V_step": 0.05,
    "icc_factor": 10.0,
    "burn_abort_scale": 10.0,  # burn_abort = icc_start * burn_abort_scale if not given
}

# ---------------------------
# Dataclasses
# ---------------------------
@dataclass
class SectionMetadata:
    section_id: str
    area_um2: float = DEFAULTS["area_um2"]
    ito_rsheet: Optional[float] = None
    recommended_Icomp_start_A: float = DEFAULTS["Icomp_start_A"]
    recommended_Icomp_max_A: float = DEFAULTS["Icomp_max_A"]
    recommended_V_form_max_V: float = DEFAULTS["V_form_max_V"]
    notes: str = ""

@dataclass
class TestParams:
    V_read: float = DEFAULTS["V_read"]
    V_step: float = DEFAULTS["V_step"]
    V_form_max: float = DEFAULTS["V_form_max_V"]
    I_comp_start_A: float = DEFAULTS["Icomp_start_A"]
    I_comp_max_A: float = DEFAULTS["Icomp_max_A"]
    I_burn_base_A: float = 1e-3
    area_ref_um2: float = DEFAULTS["area_um2"]
    dlogI_threshold_decades_per_window: float = 1.0
    dlogI_window_V: float = 0.1
    jump_factor: float = 100.0
    nsamples_fast: int = 6
    fast_sample_dt_s: float = 0.002
    avg_samples: int = 3
    pulse_deltaV: float = DEFAULTS["pulse_deltaV"]
    pulse_widths_s: List[float] = field(default_factory=lambda: DEFAULTS["pulse_widths_s"])
    max_pulses_total: int = 6
    max_pulse_attempts_per_step: int = 3
    energy_budget_J: float = DEFAULTS["energy_budget_J"]
    base_data_dir: str = "./data"
    auto_save_traces: bool = True
    use_tsp: bool = True
    tsp_instrument_hint: str = "2401"
    debug_mode: bool = False  # When True, bypass pre-checks for quick bench debugging
    def to_dict(self):
        return asdict(self)

# ---------------------------
# InstrumentInterface (expected)
# ---------------------------
class InstrumentInterface:
    def safe_init(self) -> None:
        pass
    def set_voltage(self, voltage: float, Icc: Optional[float] = None) -> None:
        raise NotImplementedError
    def set_current(self, current: float, Vcc: Optional[float] = None) -> None:
        raise NotImplementedError
    def measure_voltage(self) -> float:
        raise NotImplementedError
    def measure_current(self) -> float:
        raise NotImplementedError
    def enable_output(self, enable: bool) -> None:
        raise NotImplementedError
    def close(self) -> None:
        raise NotImplementedError
    def run_tsp_sweep(self,
                      start_v: float,
                      stop_v: float,
                      step_v: float,
                      icc_start: float,
                      icc_factor: float = 10.0,
                      icc_max: Optional[float] = None,
                      delay_s: float = 0.005,
                      burn_abort_A: Optional[float] = None
                      ) -> Dict[str,Any]:
        """Optional: instrument-side TSP sweep. Return dict with status and arrays."""
        raise NotImplementedError

# ---------------------------
# Utilities
# ---------------------------
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime())

def save_json(path: str, obj: Any) -> None:
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

def write_trace_csv(path: str, trace: List[Tuple[float,float,float]]):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w") as f:
        f.write("t_s,V_V,I_A\n")
        for t, V, I in trace:
            f.write(f"{t:.9e},{V:.9e},{I:.9e}\n")

# ---------------------------
# Excel loader
# ---------------------------
def load_excel_config(path: str) -> Dict[str,Any]:
    if pd is None:
        raise RuntimeError("pandas required to load Excel config.")
    wb = pd.read_excel(path, sheet_name=None)
    lot = {}
    sections = {}
    devices = {}
    calibration_runs = []
    if "lot" in wb and not wb["lot"].empty:
        lot = wb["lot"].iloc[0].to_dict()
    if "sections" in wb:
        df = wb["sections"]
        for _, row in df.iterrows():
            r = row.to_dict()
            sec_id = None
            for c in ("section_id","section","id"):
                if c in r and pd.notna(r[c]):
                    sec_id = str(r[c]); break
            if not sec_id: continue
            sec_meta = {
                "section_id": sec_id,
                "area_um2": float(r.get("area_um2", r.get("area", DEFAULTS["area_um2"])) or DEFAULTS["area_um2"]),
                "ito_rsheet": r.get("ITO_rsheet_Ohm_per_square", r.get("ito_rsheet", None)),
                "recommended_Icomp_start_A": float(r.get("recommended_Icomp_start_A", r.get("Icomp_start_A", DEFAULTS["Icomp_start_A"])) or DEFAULTS["Icomp_start_A"]),
                "recommended_Icomp_max_A": float(r.get("recommended_Icomp_max_A", r.get("Icomp_max_A", DEFAULTS["Icomp_max_A"])) or DEFAULTS["Icomp_max_A"]),
                "recommended_V_form_max_V": float(r.get("recommended_V_form_max_V", r.get("V_form_max_V", DEFAULTS["V_form_max_V"])) or DEFAULTS["V_form_max_V"]),
                "notes": r.get("notes","")
            }
            sections[sec_id] = sec_meta
    if "chip_manifest" in wb:
        df = wb["chip_manifest"]
        for _, row in df.iterrows():
            r = row.to_dict()
            dev_id = None
            for c in ("device_id","dev_id","id"):
                if c in r and pd.notna(r[c]):
                    dev_id = str(r[c]); break
            if not dev_id: continue
            dev = {
                "device_id": dev_id,
                "chip_id": str(r.get("chip_id", r.get("wafer","chip"))),
                "section_id": str(r.get("section_id", r.get("section",""))),
                "x_um": r.get("x_um", None),
                "y_um": r.get("y_um", None),
                "area_um2": float(r.get("area_um2", DEFAULTS["area_um2"]) or DEFAULTS["area_um2"]),
                "stack_code": r.get("stack_code",""),
                "film_thickness_nm": float(r.get("film_thickness_nm", 100) or 100),
                "pmma_percent": float(r.get("pmma_percent", 2.0) or 2.0),
                "qd_conc_mg_per_ml": float(r.get("qd_conc_mg_per_ml", 0.1) or 0.1),
                "notes": r.get("notes","")
            }
            devices[dev_id] = dev
    if "calibration_runs" in wb:
        calibration_runs = [row.to_dict() for _, row in wb["calibration_runs"].iterrows()]
    lot.setdefault("lot_id", lot.get("lot_id","lot_auto"))
    return {"lot": lot, "sections": sections, "devices": devices, "calibration_runs": calibration_runs}

# ---------------------------
# AutoTester class
# ---------------------------
class AutoTester:
    def __init__(self, instrument: InstrumentInterface, params: TestParams, lot_config: Optional[Dict]=None):
        self.instrument = instrument
        self.params = params
        self.lot_config = lot_config or {"lot_id":"lot_auto","sections":{},"devices":{}}
        self.lock = threading.Lock()
        #todo find way too make it lift
        #self.master.lift()

    def load_excel(self, path: str):
        cfg = load_excel_config(path)
        self.lot_config.update(cfg["lot"])
        self.lot_config["sections"] = cfg["sections"]
        self.lot_config["devices"] = cfg["devices"]
        self.lot_config["calibration_runs"] = cfg.get("calibration_runs", [])

    def get_section_meta(self, section_id: str) -> SectionMetadata:
        sec = self.lot_config.get("sections", {}).get(section_id)
        if not sec:
            return SectionMetadata(section_id=section_id)
        return SectionMetadata(**sec)

    def test_device(self, device_meta: Dict[str,Any]):
        device_id = device_meta.get("device_id","unknown")
        chip_id = device_meta.get("chip_id","chip")
        base = os.path.join(self.params.base_data_dir, self.lot_config.get("lot_id","lot"))
        device_dir = os.path.join(base, chip_id, device_id)
        ensure_dir(device_dir)
        with self.lock:
            try: self.instrument.safe_init()
            except Exception: pass
        self._log(device_id, "TEST_START", {"device_meta": device_meta})
        if not self._pre_checks(device_meta):
            self._log(device_id, "PRECHECK_FAIL", {})
            return
        label = self._run_low_voltage_screen(device_meta, device_dir)
        if label in ("FORMED","FORMING_CANDIDATE"):
            self._log(device_id, "PREFORMED", {"label": label})
            self.run_characterization(device_meta, device_dir)
            return

        if self.params.use_tsp:
            tsp_result = self._try_tsp_forming(device_meta, device_dir)
            if tsp_result:
                status = tsp_result.get("status")
                if status == "FORMED":
                    self._log(device_id, "FORMED_TSP", tsp_result)
                    self.run_characterization(device_meta, device_dir)
                    return
                if status == "DAMAGE":
                    self._log(device_id, "DAMAGE_TSP", tsp_result)
                    return
            # else fallback to Python forming

        form_result = self._adaptive_forming_ramp(device_meta, device_dir)
        if form_result.get("status") == "FORMED":
            self._log(device_id, "FORMED_PY", form_result)
            self.run_characterization(device_meta, device_dir)
            return
        if form_result.get("status") == "DAMAGE":
            self._log(device_id, "DAMAGE_PY", form_result)
            return
        self._log(device_id, "NO_FORM", {})
        self.run_characterization(device_meta, device_dir)

    def run_batch_from_lot(self):
        devices = self.lot_config.get("devices", {})
        for dev_id, dev_meta in devices.items():
            # run each device sequentially
            self.test_device(dev_meta)

    # Pre-checks, low-voltage screen, triangular sweep, classifier (as before)
    def _pre_checks(self, device_meta: Dict[str,Any]) -> bool:
        if self.params.debug_mode:
            # In debug mode, skip pre-checks so you can test with a resistor or dummy
            self._log(device_meta.get("device_id","unknown"), "PRECHECK_DEBUG_BYPASS", {})
            return True
        device_id = device_meta.get("device_id","unknown")
        area = device_meta.get("area_um2", self.params.area_ref_um2)
        I_short_thresh = self.params.I_burn_base_A * (area / self.params.area_ref_um2)
        try:
            with self.lock:
                self.instrument.set_voltage(0.0, Icc=min(self.params.I_comp_start_A, self.params.I_comp_max_A))
                self.instrument.enable_output(True)
                self.instrument.set_voltage(self.params.V_read, Icc=min(self.params.I_comp_start_A, self.params.I_comp_max_A))
                time.sleep(0.02)
                readings = [self.instrument.measure_current() for _ in range(self.params.avg_samples)]
                I0 = sum(readings) / max(1, len(readings))
                self.instrument.set_voltage(0.0)
                self.instrument.enable_output(False)
        except Exception as e:
            self._log(device_id, "PRECHECK_EXCEPTION", {"error": str(e)})
            return False
        device_meta["pre_read_I"] = I0
        self._log(device_id, "PRE_READ", {"V_read": self.params.V_read, "I0_A": I0, "I_short_thresh_A": I_short_thresh})
        return abs(I0) < I_short_thresh

    def _run_low_voltage_screen(self, device_meta: Dict[str,Any], device_dir: str) -> str:
        device_id = device_meta.get("device_id","unknown")
        sweep_targets = [0.5, 1.0, 1.5]
        for vmax in sweep_targets:
            trace = self._run_triangular_sweep(vmax)
            if self.params.auto_save_traces:
                write_trace_csv(os.path.join(device_dir, f"{device_id}_low_v{vmax:.2f}_{timestamp()}.csv"), trace)
            label = self._classify_trace_simple(trace)
            self._log(device_id, "LOW_SWEEP", {"vmax": vmax, "label": label})
            if label in ("FORMED","FORMING_CANDIDATE"):
                return label
        return "UNFORMED"

    def _run_triangular_sweep(self, vmax: float, steps: int = 81, delay_s: float = 0.02, vneg: Optional[float] = None):
        trace = []
        half = steps//2
        neg_target = -abs(vneg if vneg is not None else vmax)
        pos_segment = [i*(vmax/half) for i in range(half+1)]
        neg_segment = [pos_segment[i] for i in range(half-1,-1,-1)]
        # scale negative segment to reach neg_target magnitude
        scale = abs(neg_target)/max(vmax, 1e-12)
        voltages = pos_segment + [ -abs(v)*scale for v in neg_segment ]
        try:
            with self.lock:
                self.instrument.set_voltage(0.0, Icc=min(self.params.I_comp_start_A, self.params.I_comp_max_A))
                self.instrument.enable_output(True)
                for V in voltages:
                    self.instrument.set_voltage(V, Icc=min(self.params.I_comp_start_A, self.params.I_comp_max_A))
                    time.sleep(delay_s)
                    I = self.instrument.measure_current()
                    trace.append((time.time(), V, I))
                self.instrument.set_voltage(0.0)
                self.instrument.enable_output(False)
        except Exception as e:
            self._log("SYS","TRI_SWEEP_ERROR",{"error":str(e)})
        return trace

    def _classify_trace_simple(self, trace):
        if not trace or len(trace)<3: return "UNFORMED"
        Is = [abs(p[2]) for p in trace]
        for i in range(1,len(Is)):
            if Is[i] >= self.params.jump_factor * max(Is[i-1], 1e-12):
                return "FORMING_CANDIDATE"
        start = sum(Is[:max(1,len(Is)//10)])/max(1,len(Is)//10)
        end = sum(Is[-max(1,len(Is)//10):])/max(1,len(Is)//10)
        if end >= 100*max(start,1e-12): return "FORMED"
        return "UNFORMED"

    # TSP forming attempt that uses Excel-derived params
    def _try_tsp_forming(self, device_meta: Dict[str,Any], device_dir: str) -> Optional[Dict[str,Any]]:
        device_id = device_meta.get("device_id","unknown")
        section_id = device_meta.get("section_id","")
        section = self.get_section_meta(section_id)
        # derive parameters from device_meta, calibration_runs, section, or defaults
        # priority: device_meta fields -> calibration_runs entries -> section defaults -> global defaults
        # scan calibration_runs for entries matching device_id
        cal_runs = self.lot_config.get("calibration_runs", [])
        cal_entry = None
        for entry in cal_runs:
            # flexible key matching
            if any(str(entry.get(k,"")) == str(device_id) for k in ("device_id","dev_id","id")):
                cal_entry = entry
                break

        start_v = 0.0
        stop_v = float(device_meta.get("V_form_max", device_meta.get("V_form_max_V", self.params.V_form_max)))
        step_v = float(device_meta.get("V_step", self.params.V_step))
        if cal_entry:
            start_v = float(cal_entry.get("start_v", cal_entry.get("start_voltage", start_v)))
            stop_v = float(cal_entry.get("stop_v", cal_entry.get("stop_voltage", stop_v)))
            step_v = float(cal_entry.get("step_v", cal_entry.get("step_voltage", step_v)))
        # compliance choices
        icc_start = float(device_meta.get("Icomp_start_A", device_meta.get("I_comp_start_A",
                       section.recommended_Icomp_start_A if section else self.params.I_comp_start_A)))
        icc_max = float(device_meta.get("Icomp_max_A", device_meta.get("I_comp_max_A",
                       section.recommended_Icomp_max_A if section else self.params.I_comp_max_A)))
        if cal_entry:
            icc_start = float(cal_entry.get("Icomp_start_A", icc_start))
            icc_max = float(cal_entry.get("Icomp_max_A", icc_max))
        icc_factor = float(device_meta.get("icc_factor", cal_entry.get("icc_factor", DEFAULTS["icc_factor"])) if cal_entry else device_meta.get("icc_factor", DEFAULTS["icc_factor"]))
        if cal_entry:
            burn_abort_A = float(device_meta.get("burn_abort_A", cal_entry.get("burn_abort_A", icc_start*DEFAULTS["burn_abort_scale"] if icc_start else icc_start*10)))
            delay_s = float(device_meta.get("tsp_delay_s", cal_entry.get("delay_s", 0.005)))
        else:
            burn_abort_A = float(device_meta.get("burn_abort_A", icc_start*DEFAULTS["burn_abort_scale"] if icc_start else icc_start*10))
            delay_s = float(device_meta.get("tsp_delay_s", 0.005))

        # call instrument.run_tsp_sweep if available
        try:
            if hasattr(self.instrument, "run_tsp_sweep"):
                result = self.instrument.run_tsp_sweep(start_v=start_v, stop_v=stop_v, step_v=step_v,
                                                       icc_start=icc_start, icc_factor=icc_factor,
                                                       icc_max=icc_max, delay_s=delay_s, burn_abort_A=burn_abort_A)
                # Save results to device_dir if present
                if result and "voltages" in result and self.params.auto_save_traces:
                    try:
                        fname = os.path.join(device_dir, f"{device_id}_tsp_{timestamp()}.csv")
                        with open(fname, "w") as f:
                            f.write("V_V,I_A\n")
                            for vv, ii in zip(result.get("voltages",[]), result.get("currents",[])):
                                f.write(f"{vv},{ii}\n")
                        result["trace_file"] = fname
                    except Exception:
                        pass
                return result
        except Exception as e:
            self._log(device_id, "TSP_METHOD_EXCEPTION", {"error": str(e)})
            # fall through to ad-hoc TSP script route below

        # If instrument has a device attribute with write/read, fallback ad-hoc TSP script (handled earlier in original code)
        # Reuse previous ad-hoc approach: build script and send via device.write/read (if available)
        try:
            dev_obj = getattr(self.instrument, "device", None)
            if dev_obj is None:
                return None
            # Build script (similar to earlier ad-hoc script)
            tsp_lines = [
                "smu.reset()",
                "smu.source.func = smu.FUNC_DC_VOLTAGE",
                "smu.measure.func = smu.FUNC_DC_CURRENT",
                "smu.source.autorangev = smu.ON",
                f"smu.source.limiti = {icc_start}",
                "smu.source.output = smu.ON",
                f"local startv = {start_v}",
                f"local stopv = {stop_v}",
                f"local stepv = {step_v}",
                f"local icc_factor = {icc_factor}",
                f"local icc_max = {icc_max}",
                f"local burn_abort = {burn_abort_A}",
                "local v = startv",
                "repeat",
                "  smu.source.levelv = v",
                f"  delay({delay_s})",
                "  local measV = smu.measure.read(smu.FUNC_DC_VOLTAGE)",
                "  local measI = smu.measure.read(smu.FUNC_DC_CURRENT)",
                "  print(string.format('DATA:%0.9g,%0.12g', measV, measI))",
                "  if math.abs(measI) >= burn_abort then",
                "    print('ABORT:CURRENT_EXCEEDED')",
                "    smu.source.output = smu.OFF",
                "    break",
                "  end",
                "  if math.abs(measI) > 0.9*smu.source.limiti then",
                "    local newlim = smu.source.limiti * icc_factor",
                "    if newlim > icc_max then newlim = icc_max end",
                "    smu.source.limiti = newlim",
                "    print(string.format('COMPLIANCE_RAISED:%0.12g', smu.source.limiti))",
                "  end",
                "  v = v + stepv",
                "until v > stopv",
                "smu.source.output = smu.OFF",
                "print('SWEEP_DONE')"
            ]
            tsp_script = "\n".join(tsp_lines)
            try:
                dev_obj.write(tsp_script)
            except Exception:
                try:
                    dev_obj.adapter.connection.write(tsp_script)
                except Exception as e:
                    self._log(device_id, "TSP_WRITE_FAIL", {"error": str(e)})
                    return None

            # read loop
            voltages = []
            currents = []
            start_t = time.time()
            nsteps = int(max(1, math.floor((stop_v - start_v) / max(1e-12, step_v)) + 1))
            timeout = max(10.0, nsteps * (delay_s * 2.5) + 5.0)
            got_abort = False
            last_line = ""
            while True:
                if time.time() - start_t > timeout:
                    raise TimeoutError("TSP read timeout")
                try:
                    line = dev_obj.adapter.connection.read().strip()
                except Exception:
                    try:
                        line = dev_obj.read().strip()
                    except Exception:
                        time.sleep(0.01)
                        continue
                if not line:
                    time.sleep(0.001)
                    continue
                for raw in line.splitlines():
                    raw = raw.strip()
                    if not raw:
                        continue
                    last_line = raw
                    if raw.startswith("DATA:"):
                        payload = raw.split(":",1)[1].strip()
                        parts = payload.split(",")
                        try:
                            vv = float(parts[0]); ii = float(parts[1])
                            voltages.append(vv); currents.append(ii)
                        except Exception:
                            pass
                    elif raw.startswith("ABORT:"):
                        got_abort = True
                        break
                    elif raw == "SWEEP_DONE":
                        break
                if got_abort or last_line == "SWEEP_DONE":
                    break

            if got_abort:
                trace_file = None
                try:
                    if voltages and currents:
                        trace_file = os.path.join(device_dir, f"{device_id}_tsp_abort_{timestamp()}.csv")
                        with open(trace_file,"w") as f:
                            f.write("V_V,I_A\n")
                            for vv,ii in zip(voltages,currents):
                                f.write(f"{vv},{ii}\n")
                except Exception:
                    trace_file = None
                return {"status":"DAMAGE", "message":"ABORT_INSTRUMENT", "voltages":voltages, "currents":currents, "trace_file":trace_file}

            # check for jump
            prev = max(1e-12, abs(currents[0])) if currents else 1e-12
            for vv, ii in zip(voltages[1:], currents[1:]):
                if abs(ii) >= self.params.jump_factor * prev:
                    trace_file = None
                    try:
                        if voltages and currents:
                            trace_file = os.path.join(device_dir, f"{device_id}_tsp_form_{timestamp()}.csv")
                            with open(trace_file,"w") as f:
                                f.write("V_V,I_A\n")
                                for vvv, iii in zip(voltages, currents):
                                    f.write(f"{vvv},{iii}\n")
                    except Exception:
                        trace_file = None
                    return {"status":"FORMED","V_form":vv,"voltages":voltages,"currents":currents,"trace_file":trace_file}
            return {"status":"NO_FORM","voltages":voltages,"currents":currents}
        except Exception as e:
            try:
                self.instrument.enable_output(False)
            except Exception:
                pass
            self._log(device_id, "TSP_EXCEPTION", {"error": str(e)})
            return None

    # Python-forming functions (adaptive ramp + pulses) unchanged from earlier
    def _adaptive_forming_ramp(self, device_meta: Dict[str,Any], device_dir: str) -> Dict[str,Any]:
        device_id = device_meta.get("device_id","unknown")
        area = device_meta.get("area_um2", self.params.area_ref_um2)
        sec = self.get_section_meta(device_meta.get("section_id",""))
        Icomp_start = sec.recommended_Icomp_start_A if sec else self.params.I_comp_start_A
        Icomp_max = sec.recommended_Icomp_max_A if sec else self.params.I_comp_max_A
        I_burn_thresh = self.params.I_burn_base_A * (area / self.params.area_ref_um2)
        energy_accum = 0.0; pulses_used = 0; prev_avg_I = None; prev_V = None
        V = 0.0
        try:
            with self.lock: self.instrument.enable_output(True)
        except Exception: pass
        while V < self.params.V_form_max:
            V += self.params.V_step
            frac = min(V/self.params.V_form_max, 1.0)
            Icomp = max(Icomp_start, min(Icomp_start + frac*(Icomp_max-Icomp_start), Icomp_max))
            Icomp = min(Icomp, self.params.I_comp_max_A)
            try:
                with self.lock:
                    self.instrument.set_voltage(V, Icc=Icomp)
                    time.sleep(0.002)
            except Exception as e:
                self.instrument.enable_output(False)
                return {"status":"DAMAGE","reason":str(e)}
            fast_samples=[]
            for i in range(self.params.nsamples_fast):
                try:
                    Iinst = self.instrument.measure_current()
                except Exception:
                    Iinst = float("nan")
                tnow = time.time(); fast_samples.append((tnow,V,Iinst))
                if not math.isnan(Iinst) and abs(Iinst) >= I_burn_thresh:
                    try: self.instrument.enable_output(False)
                    except Exception: pass
                    if self.params.auto_save_traces:
                        pth = os.path.join(device_dir, f"{device_id}_burn_{timestamp()}.csv")
                        write_trace_csv(pth, fast_samples)
                    return {"status":"DAMAGE","V":V,"I_peak":Iinst,"trace_file":pth}
                if i>0:
                    prev_inst = fast_samples[i-1][2]
                    if abs(prev_inst)>0 and abs(Iinst) >= self.params.jump_factor*abs(prev_inst):
                        if self.params.auto_save_traces:
                            pth = os.path.join(device_dir, f"{device_id}_instant_jump_{timestamp()}.csv")
                            write_trace_csv(pth, fast_samples)
                        try: self.instrument.enable_output(False)
                        except Exception: pass
                        formed_flag, form_info = self._soft_pulse_sequence(device_meta, device_dir, V, Icomp, energy_accum, pulses_used)
                        pulses_used += form_info.get("pulses",0)
                        energy_accum += form_info.get("energy",0.0)
                        if formed_flag:
                            try: self.instrument.enable_output(False)
                            except Exception: pass
                            return {"status":"FORMED","V_form":V,"pulses_used":pulses_used,"energy_J":energy_accum}
                        break
                time.sleep(self.params.fast_sample_dt_s)
            avg_vals=[]
            for _ in range(self.params.avg_samples):
                try: avg_vals.append(self.instrument.measure_current())
                except Exception: avg_vals.append(0.0)
                time.sleep(0.01)
            avg_I = sum(avg_vals)/max(1,len(avg_vals))
            if prev_avg_I is not None and prev_V is not None:
                dlogI = (math.log10(max(abs(avg_I),1e-12)) - math.log10(max(abs(prev_avg_I),1e-12)))
                dV = V - prev_V if V!=prev_V else 1e-9
                dlogI_per_V = dlogI / dV
            else:
                dlogI_per_V = 0.0
            if dlogI_per_V >= (self.params.dlogI_threshold_decades_per_window / self.params.dlogI_window_V):
                try: self.instrument.enable_output(False)
                except Exception: pass
                formed_flag, form_info = self._soft_pulse_sequence(device_meta, device_dir, V, Icomp, energy_accum, pulses_used)
                pulses_used += form_info.get("pulses",0)
                energy_accum += form_info.get("energy",0.0)
                if formed_flag:
                    try: self.instrument.enable_output(False)
                    except Exception: pass
                    return {"status":"FORMED","V_form":V,"pulses_used":pulses_used,"energy_J":energy_accum}
            prev_avg_I = avg_I; prev_V = V
            energy_accum += abs(V * avg_I * (self.params.V_step / max(1e-9, V))) if V!=0 else 0.0
            if energy_accum >= self.params.energy_budget_J:
                try: self.instrument.enable_output(False)
                except Exception: pass
                return {"status":"DAMAGE","reason":"energy_exceeded","energy_J":energy_accum}
        try: self.instrument.enable_output(False)
        except Exception: pass
        return {"status":"NO_FORM","energy_J":energy_accum}

    def _soft_pulse_sequence(self, device_meta, device_dir, last_V, Icomp, energy_accum, pulses_used):
        device_id = device_meta.get("device_id","unknown")
        pulses = 0; energy = 0.0; formed = False
        pre_read = device_meta.get("pre_read_I",0.0) or 0.0
        for pw in self.params.pulse_widths_s:
            if pulses_used + pulses >= self.params.max_pulses_total: break
            Vpulse = last_V + self.params.pulse_deltaV
            try:
                with self.lock:
                    if hasattr(self.instrument, "apply_pulse_and_capture"):
                        trace = self.instrument.apply_pulse_and_capture(Vpulse, pw, min(Icomp, self.params.I_comp_max_A))
                    else:
                        self.instrument.set_voltage(Vpulse, Icc=min(Icomp, self.params.I_comp_max_A))
                        time.sleep(pw)
                        I = self.instrument.measure_current()
                        trace = [(time.time(), Vpulse, I)]
            except Exception as e:
                self._log(device_id, "PULSE_ERROR", {"error": str(e), "Vpulse": Vpulse, "pw": pw})
                break
            if trace and self.params.auto_save_traces:
                pth = os.path.join(device_dir, f"{device_id}_pulse_{timestamp()}.csv")
                write_trace_csv(pth, trace)
            pulse_energy = 0.0
            if trace and len(trace)>1:
                for k in range(1,len(trace)):
                    dt = trace[k][0] - trace[k-1][0]
                    Vavg = 0.5*(trace[k][1]+trace[k-1][1])
                    Iavg = 0.5*(trace[k][2]+trace[k-1][2])
                    pulse_energy += abs(Vavg*Iavg)*dt
            else:
                pulse_energy = abs(Vpulse * min(Icomp, self.params.I_comp_max_A) * pw)
            pulses += 1; energy += pulse_energy; energy_accum += pulse_energy
            try:
                with self.lock:
                    self.instrument.set_voltage(self.params.V_read, Icc=min(self.params.I_comp_start_A, self.params.I_comp_max_A))
                    time.sleep(0.002)
                    Ipost = sum([self.instrument.measure_current() for _ in range(self.params.avg_samples)]) / self.params.avg_samples
                    self.instrument.set_voltage(0.0)
            except Exception:
                Ipost = float("nan")
            if abs(Ipost) >= max(10*abs(pre_read),1e-12):
                formed = True
                self._log(device_id, "FORMED_AFTER_PULSE", {"Vpulse":Vpulse,"pw":pw,"Ipost_A":Ipost,"pulse_energy_J":pulse_energy})
                break
            if energy_accum >= self.params.energy_budget_J:
                self._log(device_id,"ENERGY_BUDGET_EXCEEDED",{"energy_J":energy_accum})
                try: self.instrument.enable_output(False)
                except Exception: pass
                return (False,{"pulses":pulses,"energy":energy})
            if pulses >= self.params.max_pulse_attempts_per_step:
                break
        return (formed, {"pulses":pulses,"energy":energy})

    def run_characterization(self, device_meta: Dict[str,Any], device_dir: str):
        device_id = device_meta.get("device_id","unknown")
        vmin = -self.params.V_form_max; vmax = self.params.V_form_max
        steps = int((vmax - vmin) / max(1e-9, self.params.V_step)) + 1
        trace = []
        try:
            with self.lock:
                self.instrument.set_voltage(0.0, Icc=min(self.params.I_comp_max_A, 1e-3))
                self.instrument.enable_output(True)
                for i in range(steps):
                    V = vmin + i*((vmax - vmin)/max(1,steps-1))
                    self.instrument.set_voltage(V, Icc=min(self.params.I_comp_max_A, 1e-3))
                    time.sleep(0.02)
                    I = self.instrument.measure_current()
                    trace.append((time.time(),V,I))
                self.instrument.set_voltage(0.0); self.instrument.enable_output(False)
        except Exception as e:
            self._log(device_id,"CHAR_ERROR",{"error":str(e)})
        if self.params.auto_save_traces:
            pth = os.path.join(device_dir, f"{device_id}_bipolar_{timestamp()}.csv")
            write_trace_csv(pth, trace)
        summary = {"device_id":device_id,"I_read_A":None,"trace_file":pth}
        save_json(os.path.join(device_dir,"device_summary.json"),summary)
        self._log(device_id,"CHAR_COMPLETE",summary)

    def _log(self, device_id: str, event: str, details: Dict[str,Any]):
        base = os.path.join(self.params.base_data_dir, self.lot_config.get("lot_id","lot"))
        ensure_dir(base)
        log_path = os.path.join(base, "experiment_log.csv")
        ts = timestamp()
        json_details = json.dumps(details)
        safe_json = json_details.replace('"', "'")
        line = f'{ts},{device_id},{event},"{safe_json}"\n'
        with open(log_path, "a") as f:
            f.write(line)
        print(f"[{ts}] {device_id} - {event} - {details}")

# ---------------------------
# GUI: updated with Run batch button
# ---------------------------
class AutomatedTesterGUI(tk.Toplevel):
    def __init__(self, master=None, instrument: Optional[InstrumentInterface]=None, 
                 current_section: Optional[str]=None,
                 device_list: Optional[List[str]]=None,
                 get_next_device_cb: Optional[Any]=None,
                 current_device_id: Optional[str]=None,
                 host_gui: Optional[Any]=None):
        super().__init__(master)
        self.title("Automated Memristor Tester")
        self.geometry("700x820")
        self.instrument = instrument
        self.params = TestParams()
        self.lot_config = {"lot_id":"lot_auto","sections":{},"devices":{}}
        self.autotester = AutoTester(self.instrument if self.instrument else DummyInstrument(), self.params, self.lot_config)
        self.worker_thread = None
        # integration with external GUIs
        self.current_section = current_section or ""
        self.external_device_list = device_list or []
        self.current_device_id = current_device_id or (self.external_device_list[0] if self.external_device_list else "D1_G1")
        self.get_next_device_cb = get_next_device_cb
        self.host_gui = host_gui
        self._build_ui()
        # try to listen to host selection changes if master provides callbacks/variables
        try:
            if hasattr(master, 'bind') and callable(master.bind):
                # host may emit custom events like <<DeviceChanged>>; optional
                master.bind('<<DeviceChanged>>', lambda e: self._sync_from_host())
        except Exception:
            pass
        # periodic sync as fallback
        try:
            self._last_sync_key = None
            self.after(300, self._host_sync_tick)
        except Exception:
            pass

    def _build_ui(self):
        frm = ttk.Frame(self); frm.pack(fill="both",expand=True,padx=8,pady=8)
        ttk.Label(frm, text="Excel config:").grid(row=0,column=0,sticky="w")
        self.excel_path_var = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.excel_path_var, width=56).grid(row=0,column=1,columnspan=2,sticky="w")
        ttk.Button(frm, text="Load Excel...", command=self._load_excel).grid(row=0,column=3,sticky="w")
        self.use_tsp_var = tk.BooleanVar(value=self.params.use_tsp)
        ttk.Checkbutton(frm, text="Use embedded TSP (Keithley 2401)", variable=self.use_tsp_var).grid(row=1,column=0,columnspan=2,sticky="w")
        self.debug_mode_var = tk.BooleanVar(value=self.params.debug_mode)
        ttk.Checkbutton(frm, text="Debug mode (bypass precheck)", variable=self.debug_mode_var).grid(row=1,column=2,columnspan=2,sticky="w")
        # basic params...
        ttk.Label(frm, text="V_read (V):").grid(row=2,column=0,sticky="w")
        self.vread_var = tk.DoubleVar(value=self.params.V_read); ttk.Entry(frm,textvariable=self.vread_var,width=10).grid(row=2,column=1)
        ttk.Label(frm, text="V_step (V):").grid(row=2,column=2,sticky="w")
        self.vstep_var = tk.DoubleVar(value=self.params.V_step); ttk.Entry(frm,textvariable=self.vstep_var,width=10).grid(row=2,column=3)
        ttk.Label(frm, text="V_form_max (V):").grid(row=3,column=0,sticky="w")
        self.vform_var = tk.DoubleVar(value=self.params.V_form_max); ttk.Entry(frm,textvariable=self.vform_var,width=10).grid(row=3,column=1)
        ttk.Label(frm, text="I_comp_start (A):").grid(row=4,column=0,sticky="w")
        self.icomp_start_var = tk.DoubleVar(value=self.params.I_comp_start_A); ttk.Entry(frm,textvariable=self.icomp_start_var,width=12).grid(row=4,column=1)
        ttk.Label(frm, text="I_comp_max (A):").grid(row=4,column=2,sticky="w")
        self.icomp_max_var = tk.DoubleVar(value=self.params.I_comp_max_A); ttk.Entry(frm,textvariable=self.icomp_max_var,width=12).grid(row=4,column=3)
        ttk.Label(frm, text="Jump factor:").grid(row=5,column=0,sticky="w")
        self.jump_var = tk.DoubleVar(value=self.params.jump_factor); ttk.Entry(frm,textvariable=self.jump_var,width=12).grid(row=5,column=1)
        ttk.Label(frm, text="Fast samples/step:").grid(row=5,column=2,sticky="w")
        self.nsamples_var = tk.IntVar(value=self.params.nsamples_fast); ttk.Entry(frm,textvariable=self.nsamples_var,width=12).grid(row=5,column=3)
        ttk.Label(frm, text="Pulse delta V (V):").grid(row=6,column=0,sticky="w")
        self.pulse_dv_var = tk.DoubleVar(value=self.params.pulse_deltaV); ttk.Entry(frm,textvariable=self.pulse_dv_var,width=12).grid(row=6,column=1)
        ttk.Label(frm, text="Pulse widths (ms comma):").grid(row=6,column=2,sticky="w")
        self.pulse_widths_var = tk.StringVar(value=",".join(str(int(w*1e3)) for w in self.params.pulse_widths_s)); ttk.Entry(frm,textvariable=self.pulse_widths_var,width=24).grid(row=6,column=3)
        ttk.Label(frm, text="Device ID:").grid(row=7,column=0,sticky="w")
        self.device_id_var = tk.StringVar(value=self.current_device_id)
        ttk.Entry(frm,textvariable=self.device_id_var,width=12).grid(row=7,column=1)
        ttk.Label(frm, text="Device # (1-10):").grid(row=7,column=2,sticky="w")
        self.device_num_var = tk.IntVar(value=1)
        ttk.Spinbox(frm, from_=1, to=10, textvariable=self.device_num_var, width=6).grid(row=7,column=3)
        ttk.Label(frm, text="Chip ID:").grid(row=7,column=2,sticky="w")
        self.chip_id_var = tk.StringVar(value="chip1"); ttk.Entry(frm,textvariable=self.chip_id_var,width=12).grid(row=7,column=3)
        ttk.Label(frm, text="Section ID:").grid(row=8,column=0,sticky="w")
        self.section_id_var = tk.StringVar(value=self.current_section or "A"); ttk.Entry(frm,textvariable=self.section_id_var,width=12).grid(row=8,column=1)
        ttk.Label(frm, text="Area (um^2):").grid(row=8,column=2,sticky="w")
        self.area_var = tk.DoubleVar(value=DEFAULTS["area_um2"]); ttk.Entry(frm,textvariable=self.area_var,width=12).grid(row=8,column=3)
        self.measure_one_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Measure one device only", variable=self.measure_one_var).grid(row=9,column=0,sticky="w")
        ttk.Button(frm, text="Start Single Test", command=self._start_single_test).grid(row=9,column=1,pady=8)
        ttk.Button(frm, text="Run batch (Excel devices)", command=self._start_batch).grid(row=9,column=2,pady=8)
        ttk.Button(frm, text="Stop (safe)", command=self._stop_requested).grid(row=9,column=2,pady=8)
        ttk.Button(frm, text="Save params...", command=self._save_params).grid(row=9,column=3)
        ttk.Button(frm, text="Open data folder", command=self._open_data_folder).grid(row=9,column=4)
        self.status = tk.Text(frm, height=16); self.status.grid(row=10,column=0,columnspan=5,pady=8)
        self._append_status("Ready. Load Excel and run batch or start single test.")

    def _sync_from_host(self):
        try:
            # Try to pull current device/section from host GUI if available
            host = self.host_gui if self.host_gui is not None else self.master
            section_letter = None
            device_num = None
            # Prefer explicit fields from Measurement GUI
            if hasattr(host, 'device_section_and_number'):
                text = str(getattr(host, 'device_section_and_number'))
                # parse like 'A1'...'Z10'
                letters = ''.join([c for c in text if c.isalpha()])
                digits = ''.join([c for c in text if c.isdigit()])
                section_letter = letters or None
                device_num = int(digits) if digits else None
            # Fallback to section attribute
            if section_letter is None and hasattr(host, 'section'):
                section_letter = str(getattr(host, 'section'))
            # Fallback to current_index mapping (1-10)
            if device_num is None and hasattr(host, 'current_index'):
                try:
                    idx = int(getattr(host, 'current_index'))
                    device_num = (idx % 10) + 1
                except Exception:
                    device_num = None
            # Update UI if new
            key = f"{section_letter}-{device_num}"
            if key != getattr(self, '_last_sync_key', None) and (section_letter or device_num):
                if section_letter:
                    self.section_id_var.set(section_letter)
                if device_num:
                    self.device_num_var.set(device_num)
                    # Update device/chip IDs to match convention
                    self.device_id_var.set(f"device_{device_num}")
                    # keep chip id numeric 1-10
                    if hasattr(self, 'chip_id_var'):
                        self.chip_id_var.set(str(device_num))
                self._last_sync_key = key
        except Exception:
            pass

    def _host_sync_tick(self):
        try:
            self._sync_from_host()
        finally:
            try:
                self.after(300, self._host_sync_tick)
            except Exception:
                pass

    def _append_status(self, msg: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.status.insert("end", f"[{ts}] {msg}\n"); self.status.see("end")

    def _load_excel(self):
        p = filedialog.askopenfilename(title="Load Excel", filetypes=[("Excel","*.xlsx;*.xls"),("All files","*.*")])
        if not p: return
        if pd is None:
            messagebox.showerror("Missing", "pandas required")
            return
        try:
            self.autotester.load_excel(p)
            self.excel_path_var.set(p)
            self._append_status(f"Loaded excel: {p}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_params_from_ui(self):
        self.params.V_read = float(self.vread_var.get())
        self.params.V_step = float(self.vstep_var.get())
        self.params.V_form_max = float(self.vform_var.get())
        self.params.I_comp_start_A = float(self.icomp_start_var.get())
        self.params.I_comp_max_A = float(self.icomp_max_var.get())
        self.params.jump_factor = float(self.jump_var.get())
        self.params.nsamples_fast = int(self.nsamples_var.get())
        self.params.pulse_deltaV = float(self.pulse_dv_var.get())
        widths_str = self.pulse_widths_var.get()
        try:
            widths = [float(x.strip())*1e-3 for x in widths_str.split(",") if x.strip()]
            if widths: self.params.pulse_widths_s = widths
        except Exception:
            self._append_status("Pulse widths parse error; keeping old values.")
        self.params.use_tsp = bool(self.use_tsp_var.get())
        self.params.debug_mode = bool(self.debug_mode_var.get())
        self.autotester.params = self.params

    def _start_single_test(self):
        self._update_params_from_ui()
        device_meta = {
            "device_id": self.device_id_var.get(),
            "chip_id": self.chip_id_var.get(),
            "section_id": self.section_id_var.get(),
            "area_um2": float(self.area_var.get()),
            "stack_code": "UNKNOWN",
            "film_thickness_nm": 100
        }
        self._append_status(f"Starting test for {device_meta['device_id']}")
        self.worker_thread = threading.Thread(target=self._worker_single, args=(device_meta,), daemon=True)
        self.worker_thread.start()

    def _worker_single(self, device_meta):
        try:
            self.autotester.test_device(device_meta)
            self._append_status(f"Finished {device_meta['device_id']}")
            # If measuring multiple devices, request next from host GUI
            if not self.measure_one_var.get():
                next_dev = None
                try:
                    if self.get_next_device_cb:
                        next_dev = self.get_next_device_cb()
                except Exception:
                    next_dev = None
                if next_dev:
                    # Update UI fields and start next device automatically
                    self.device_id_var.set(next_dev)
                    self._append_status(f"Auto-advancing to next device: {next_dev}")
                    self._start_single_test()
        except Exception as e:
            self._append_status(f"Exception: {e}")

    def _start_batch(self):
        self._update_params_from_ui()
        # confirm
        if not messagebox.askokcancel("Run batch", "Start batch run for all devices from loaded Excel?"):
            return
        self._append_status("Starting batch run...")
        self.worker_thread = threading.Thread(target=self._worker_batch, daemon=True)
        self.worker_thread.start()

    def _worker_batch(self):
        try:
            self.autotester.run_batch_from_lot()
            self._append_status("Batch run complete")
        except Exception as e:
            self._append_status(f"Batch exception: {e}")

    def _stop_requested(self):
        try:
            if self.instrument:
                self.instrument.enable_output(False)
        except Exception:
            pass
        self._append_status("Stop requested (outputs disabled)")

    def _save_params(self):
        self._update_params_from_ui()
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON",".json")])
        if p:
            save_json(p, self.params.to_dict()); self._append_status(f"Saved params {p}")

    def _open_data_folder(self):
        base = os.path.abspath(self.params.base_data_dir)
        try:
            if os.name == "nt": os.startfile(base)
            else:
                import subprocess; subprocess.run(["xdg-open", base])
        except Exception as e:
            self._append_status(f"Open folder error: {e}")

# ---------------------------
# Dummy instrument (for testing GUI)
# ---------------------------
class DummyInstrument(InstrumentInterface):
    def __init__(self):
        self._V = 0.0; self._Icomp = DEFAULTS["Icomp_start_A"]; self._on=False
    def safe_init(self): pass
    def set_voltage(self, voltage: float, Icc: Optional[float]=None):
        self._V = float(voltage); 
        if Icc is not None: self._Icomp = float(Icc)
    def set_current(self, current: float, Vcc: Optional[float]=None): pass
    def measure_voltage(self)->float: return self._V
    def measure_current(self)->float:
        base = 1e-10 + 1e-10*abs(self._V)
        if abs(self._V) > 1.8:
            return min(self._Icomp*0.9, 1e-3*math.exp((abs(self._V)-1.8)))
        return base*math.exp(abs(self._V)*0.6)
    def enable_output(self, enable: bool): self._on = bool(enable)
    def close(self): pass
    # optional run_tsp_sweep for testing TSP path
    def run_tsp_sweep(self, start_v, stop_v, step_v, icc_start, icc_factor=10.0, icc_max=None, delay_s=0.005, burn_abort_A=None):
        # Simulate a sweep; rapidly produce array
        voltages=[]; currents=[]
        v=start_v
        while v<=stop_v+1e-12:
            voltages.append(v)
            if abs(v)>1.8:
                currents.append(min(icc_start*0.9, 1e-3*math.exp((abs(v)-1.8))))
            else:
                currents.append(1e-12*math.exp(abs(v)*0.6))
            v += step_v
        return {"status":"NO_FORM","voltages":voltages,"currents":currents}

# ---------------------------
# Run as module for quick testing
# ---------------------------
def main():
    root = tk.Tk(); root.withdraw()
    gui = AutomatedTesterGUI(root, instrument=DummyInstrument())
    gui.mainloop()

if __name__ == "__main__":
    main()
