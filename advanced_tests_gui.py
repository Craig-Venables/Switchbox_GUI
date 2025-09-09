import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import numpy as np


class AdvancedTestsGUI:
    """Popup window for advanced/volatile memristor tests (SMU-first, PMU-later).

    Expects a provider with:
      - measurement_service (MeasurementService)
      - keithley (IV controller)
      - sample_name_var, final_device_letter, final_device_number
      - stop_measurement_flag (optional)
    """

    def __init__(self, master, provider):
        self.master = tk.Toplevel(master)
        self.master.title("Advanced Tests")
        self.master.geometry("500x1000")
        self.provider = provider
        self.ms = getattr(provider, 'measurement_service', None)
        self.keithley = getattr(provider, 'keithley', None)

        nb = ttk.Notebook(self.master)
        nb.pack(fill=tk.BOTH, expand=True)

        self.vol_tab = ttk.Frame(nb)
        nb.add(self.vol_tab, text="Volatile")

        self._build_volatile_tab(self.vol_tab)

    # ---------------- Volatile Tab ----------------
    def _build_volatile_tab(self, parent):
        wrap = ttk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Transient Decay
        tr = ttk.Labelframe(wrap, text="Transient Decay")
        tr.pack(fill=tk.X, pady=(0, 8))
        self.tr_pulse_v = tk.DoubleVar(value=0.8)
        self.tr_pulse_ms = tk.DoubleVar(value=1.0)
        self.tr_read_v = tk.DoubleVar(value=0.2)
        self.tr_cap_s = tk.DoubleVar(value=1.0)
        self.tr_dt_s = tk.DoubleVar(value=0.001)
        ttk.Label(tr, text="Pulse V").grid(row=0, column=0, sticky='w'); ttk.Entry(tr, textvariable=self.tr_pulse_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(tr, text="Pulse (ms)").grid(row=0, column=2, sticky='w'); ttk.Entry(tr, textvariable=self.tr_pulse_ms, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(tr, text="Read V").grid(row=1, column=0, sticky='w'); ttk.Entry(tr, textvariable=self.tr_read_v, width=10).grid(row=1, column=1, sticky='w')
        ttk.Label(tr, text="Capture (s)").grid(row=1, column=2, sticky='w'); ttk.Entry(tr, textvariable=self.tr_cap_s, width=10).grid(row=1, column=3, sticky='w')
        ttk.Label(tr, text="dt (s)").grid(row=2, column=0, sticky='w'); ttk.Entry(tr, textvariable=self.tr_dt_s, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(tr, text="Pulse once, then sample I(t) at Vread; extracts decay curves.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(tr, text="Run", command=self._run_transient_thread).grid(row=2, column=3, sticky='e')

        for c in range(4): tr.grid_columnconfigure(c, weight=1)

        # PPF
        ppf = ttk.Labelframe(wrap, text="Paired-Pulse Facilitation (PPF)")
        ppf.pack(fill=tk.X)
        self.ppf_pulse_v = tk.DoubleVar(value=0.8)
        self.ppf_pulse_ms = tk.DoubleVar(value=1.0)
        self.ppf_dt_csv = tk.StringVar(value="0.001,0.003,0.01,0.03,0.1")
        self.ppf_read_v = tk.DoubleVar(value=0.2)
        self.ppf_read_settle = tk.DoubleVar(value=0.002)
        ttk.Label(ppf, text="Pulse V").grid(row=0, column=0, sticky='w'); ttk.Entry(ppf, textvariable=self.ppf_pulse_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(ppf, text="Pulse (ms)").grid(row=0, column=2, sticky='w'); ttk.Entry(ppf, textvariable=self.ppf_pulse_ms, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(ppf, text="Δt list (s, csv)").grid(row=1, column=0, sticky='w'); ttk.Entry(ppf, textvariable=self.ppf_dt_csv, width=20).grid(row=1, column=1, sticky='w')
        ttk.Label(ppf, text="Read V").grid(row=1, column=2, sticky='w'); ttk.Entry(ppf, textvariable=self.ppf_read_v, width=10).grid(row=1, column=3, sticky='w')
        ttk.Label(ppf, text="Read settle (s)").grid(row=2, column=0, sticky='w'); ttk.Entry(ppf, textvariable=self.ppf_read_settle, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(ppf, text="Two pulses separated by Δt; PPF index vs Δt.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(ppf, text="Run", command=self._run_ppf_thread).grid(row=2, column=3, sticky='e')
        for c in range(4): ppf.grid_columnconfigure(c, weight=1)

        # STDP
        stdp = ttk.Labelframe(wrap, text="STDP (pre/post timing)")
        stdp.pack(fill=tk.X, pady=(8, 0))
        self.stdp_pre_v = tk.DoubleVar(value=0.8)
        self.stdp_post_v = tk.DoubleVar(value=-0.8)
        self.stdp_pulse_ms = tk.DoubleVar(value=1.0)
        self.stdp_dt_csv = tk.StringVar(value="-0.05,-0.02,-0.01,0.01,0.02,0.05")
        self.stdp_read_v = tk.DoubleVar(value=0.2)
        self.stdp_read_settle = tk.DoubleVar(value=0.002)
        ttk.Label(stdp, text="Pre V").grid(row=0, column=0, sticky='w'); ttk.Entry(stdp, textvariable=self.stdp_pre_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(stdp, text="Post V").grid(row=0, column=2, sticky='w'); ttk.Entry(stdp, textvariable=self.stdp_post_v, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(stdp, text="Pulse (ms)").grid(row=1, column=0, sticky='w'); ttk.Entry(stdp, textvariable=self.stdp_pulse_ms, width=10).grid(row=1, column=1, sticky='w')
        ttk.Label(stdp, text="Δt list (s, csv)").grid(row=1, column=2, sticky='w'); ttk.Entry(stdp, textvariable=self.stdp_dt_csv, width=20).grid(row=1, column=3, sticky='w')
        ttk.Label(stdp, text="Read V").grid(row=2, column=0, sticky='w'); ttk.Entry(stdp, textvariable=self.stdp_read_v, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(stdp, text="Read settle (s)").grid(row=2, column=2, sticky='w'); ttk.Entry(stdp, textvariable=self.stdp_read_settle, width=10).grid(row=2, column=3, sticky='w')
        ttk.Label(stdp, text="Pre/post pulses separated by Δt (±), Δw vs Δt.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(stdp, text="Run", command=self._run_stdp_thread).grid(row=2, column=4, sticky='e')
        for c in range(5): stdp.grid_columnconfigure(c, weight=1)

        # SRDP
        srdp = ttk.Labelframe(wrap, text="SRDP (rate dependent)")
        srdp.pack(fill=tk.X, pady=(8, 0))
        self.srdp_pulse_v = tk.DoubleVar(value=0.6)
        self.srdp_pulse_ms = tk.DoubleVar(value=1.0)
        self.srdp_freqs_csv = tk.StringVar(value="1,5,10,20,50")
        self.srdp_pulses = tk.IntVar(value=20)
        self.srdp_read_v = tk.DoubleVar(value=0.2)
        ttk.Label(srdp, text="Pulse V").grid(row=0, column=0, sticky='w'); ttk.Entry(srdp, textvariable=self.srdp_pulse_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(srdp, text="Pulse (ms)").grid(row=0, column=2, sticky='w'); ttk.Entry(srdp, textvariable=self.srdp_pulse_ms, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(srdp, text="Freqs (Hz, csv)").grid(row=1, column=0, sticky='w'); ttk.Entry(srdp, textvariable=self.srdp_freqs_csv, width=20).grid(row=1, column=1, sticky='w')
        ttk.Label(srdp, text="# pulses/train").grid(row=1, column=2, sticky='w'); ttk.Entry(srdp, textvariable=self.srdp_pulses, width=10).grid(row=1, column=3, sticky='w')
        ttk.Label(srdp, text="Read V").grid(row=2, column=0, sticky='w'); ttk.Entry(srdp, textvariable=self.srdp_read_v, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(srdp, text="Trains at various Hz; steady-state vs rate.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(srdp, text="Run", command=self._run_srdp_thread).grid(row=2, column=4, sticky='e')
        for c in range(5): srdp.grid_columnconfigure(c, weight=1)

        # Potentiation/Depression
        pdp = ttk.Labelframe(wrap, text="Potentiation/Depression")
        pdp.pack(fill=tk.X, pady=(8, 0))
        self.pd_set_v = tk.DoubleVar(value=0.8)
        self.pd_reset_v = tk.DoubleVar(value=-0.8)
        self.pd_pulse_ms = tk.DoubleVar(value=1.0)
        self.pd_cycles = tk.IntVar(value=10)
        self.pd_read_v = tk.DoubleVar(value=0.2)
        self.pd_relax_s = tk.DoubleVar(value=0.1)
        ttk.Label(pdp, text="SET V").grid(row=0, column=0, sticky='w'); ttk.Entry(pdp, textvariable=self.pd_set_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(pdp, text="RESET V").grid(row=0, column=2, sticky='w'); ttk.Entry(pdp, textvariable=self.pd_reset_v, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(pdp, text="Pulse (ms)").grid(row=1, column=0, sticky='w'); ttk.Entry(pdp, textvariable=self.pd_pulse_ms, width=10).grid(row=1, column=1, sticky='w')
        ttk.Label(pdp, text="Cycles").grid(row=1, column=2, sticky='w'); ttk.Entry(pdp, textvariable=self.pd_cycles, width=10).grid(row=1, column=3, sticky='w')
        ttk.Label(pdp, text="Read V").grid(row=2, column=0, sticky='w'); ttk.Entry(pdp, textvariable=self.pd_read_v, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(pdp, text="Relax (s)").grid(row=2, column=2, sticky='w'); ttk.Entry(pdp, textvariable=self.pd_relax_s, width=10).grid(row=2, column=3, sticky='w')
        ttk.Label(pdp, text="Alternate +/− pulses; immediate/post reads; volatility ratio.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(pdp, text="Run", command=self._run_potdep_thread).grid(row=2, column=4, sticky='e')
        for c in range(5): pdp.grid_columnconfigure(c, weight=1)

        # Frequency Response
        fr = ttk.Labelframe(wrap, text="Frequency Response")
        fr.pack(fill=tk.X, pady=(8, 0))
        self.fr_pulse_v = tk.DoubleVar(value=0.5)
        self.fr_pulse_ms = tk.DoubleVar(value=1.0)
        self.fr_freqs_csv = tk.StringVar(value="1,5,10,20,50")
        self.fr_pulses = tk.IntVar(value=10)
        self.fr_vbase = tk.DoubleVar(value=0.2)
        ttk.Label(fr, text="Pulse V").grid(row=0, column=0, sticky='w'); ttk.Entry(fr, textvariable=self.fr_pulse_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(fr, text="Pulse (ms)").grid(row=0, column=2, sticky='w'); ttk.Entry(fr, textvariable=self.fr_pulse_ms, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(fr, text="Freqs (Hz, csv)").grid(row=1, column=0, sticky='w'); ttk.Entry(fr, textvariable=self.fr_freqs_csv, width=20).grid(row=1, column=1, sticky='w')
        ttk.Label(fr, text="# pulses/freq").grid(row=1, column=2, sticky='w'); ttk.Entry(fr, textvariable=self.fr_pulses, width=10).grid(row=1, column=3, sticky='w')
        ttk.Label(fr, text="Vbase").grid(row=2, column=0, sticky='w'); ttk.Entry(fr, textvariable=self.fr_vbase, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(fr, text="Train at each Hz; avg read current as response.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(fr, text="Run", command=self._run_freqresp_thread).grid(row=2, column=4, sticky='e')
        for c in range(5): fr.grid_columnconfigure(c, weight=1)

        # Bias-dependent volatility
        bd = ttk.Labelframe(wrap, text="Bias-dependent Decay")
        bd.pack(fill=tk.X, pady=(8, 0))
        self.bd_pulse_v = tk.DoubleVar(value=0.8)
        self.bd_pulse_ms = tk.DoubleVar(value=1.0)
        self.bd_reads_csv = tk.StringVar(value="0.1,0.2,0.3")
        self.bd_cap_s = tk.DoubleVar(value=1.0)
        self.bd_dt_s = tk.DoubleVar(value=0.001)
        ttk.Label(bd, text="Pulse V").grid(row=0, column=0, sticky='w'); ttk.Entry(bd, textvariable=self.bd_pulse_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(bd, text="Pulse (ms)").grid(row=0, column=2, sticky='w'); ttk.Entry(bd, textvariable=self.bd_pulse_ms, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(bd, text="Read V list (csv)").grid(row=1, column=0, sticky='w'); ttk.Entry(bd, textvariable=self.bd_reads_csv, width=20).grid(row=1, column=1, sticky='w')
        ttk.Label(bd, text="Capture (s)").grid(row=1, column=2, sticky='w'); ttk.Entry(bd, textvariable=self.bd_cap_s, width=10).grid(row=1, column=3, sticky='w')
        ttk.Label(bd, text="dt (s)").grid(row=2, column=0, sticky='w'); ttk.Entry(bd, textvariable=self.bd_dt_s, width=10).grid(row=2, column=1, sticky='w')
        ttk.Label(bd, text="Repeat transients at different Vread; map decay vs bias.").grid(row=3, column=0, columnspan=4, sticky='w')
        ttk.Button(bd, text="Run", command=self._run_biasdecay_thread).grid(row=2, column=3, sticky='e')
        for c in range(4): bd.grid_columnconfigure(c, weight=1)

        # Noise/RTN
        rt = ttk.Labelframe(wrap, text="Noise/RTN (low-bias I(t))")
        rt.pack(fill=tk.X, pady=(8, 0))
        self.rt_read_v = tk.DoubleVar(value=0.1)
        self.rt_cap_s = tk.DoubleVar(value=5.0)
        self.rt_dt_s = tk.DoubleVar(value=0.001)
        ttk.Label(rt, text="Read V").grid(row=0, column=0, sticky='w'); ttk.Entry(rt, textvariable=self.rt_read_v, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(rt, text="Capture (s)").grid(row=0, column=2, sticky='w'); ttk.Entry(rt, textvariable=self.rt_cap_s, width=10).grid(row=0, column=3, sticky='w')
        ttk.Label(rt, text="dt (s)").grid(row=1, column=0, sticky='w'); ttk.Entry(rt, textvariable=self.rt_dt_s, width=10).grid(row=1, column=1, sticky='w')
        ttk.Label(rt, text="Record I(t) for RTN/noise statistics.").grid(row=2, column=0, columnspan=4, sticky='w')
        ttk.Button(rt, text="Run", command=self._run_noise_thread).grid(row=1, column=3, sticky='e')
        for c in range(4): rt.grid_columnconfigure(c, weight=1)

    # ---------------- Runners ----------------
    def _save_path(self, base_name: str) -> str:
        try:
            sample = self.provider.sample_name_var.get()
        except Exception:
            sample = "unknown"
        try:
            letter = self.provider.final_device_letter
            number = self.provider.final_device_number
        except Exception:
            letter, number = "X", 1
        save_dir = f"Data_save_loc\\{sample}\\{letter}\\{number}"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        # increment
        try:
            from Measurement_GUI import find_largest_number_in_folder
            key = find_largest_number_in_folder(save_dir)
        except Exception:
            key = None
        save_key = 0 if key is None else key + 1
        return f"{save_dir}\\{save_key}-{base_name}.txt"

    def _run_transient_thread(self):
        threading.Thread(target=self._run_transient, daemon=True).start()

    def _run_transient(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        p_v = float(self.tr_pulse_v.get()); p_ms = float(self.tr_pulse_ms.get())
        r_v = float(self.tr_read_v.get()); cap_s = float(self.tr_cap_s.get()); dt_s = float(self.tr_dt_s.get())
        t_arr, i_arr, v_arr = self.ms.run_transient_decay(
            keithley=self.keithley,
            pulse_voltage=p_v,
            pulse_width_ms=p_ms,
            read_voltage=r_v,
            capture_time_s=cap_s,
            sample_dt_s=dt_s,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
            on_point=None,
        )
        # Save
        path = self._save_path(f"TRANSIENT-{p_v}v-{p_ms}ms-Read{r_v}v-{cap_s}s@{dt_s}s-Py")
        try:
            data = np.column_stack((v_arr, i_arr, t_arr))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Time(s)", comments="")
        except Exception:
            pass
        messagebox.showinfo("Transient", f"Saved: {os.path.basename(path)}")

    def _run_ppf_thread(self):
        threading.Thread(target=self._run_ppf, daemon=True).start()

    def _run_ppf(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        p_v = float(self.ppf_pulse_v.get()); p_ms = float(self.ppf_pulse_ms.get())
        read_v = float(self.ppf_read_v.get()); settle = float(self.ppf_read_settle.get())
        try:
            dts = [float(x.strip()) for x in str(self.ppf_dt_csv.get()).split(',') if x.strip()]
        except Exception:
            dts = [0.001, 0.003, 0.01, 0.03, 0.1]
        dt_list, i1, i2, ppf_idx = self.ms.run_ppf(
            keithley=self.keithley,
            pulse_voltage=p_v,
            pulse_width_ms=p_ms,
            dt_list_s=dts,
            read_voltage=read_v,
            read_settle_s=settle,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
            on_point=None,
        )
        # Save
        path = self._save_path(f"PPF-{p_v}v-{p_ms}ms-Read{read_v}v-Py")
        try:
            # Voltage column is the read voltage; use a vector with constant value
            v = np.full_like(np.array(dt_list, dtype=float), float(read_v))
            data = np.column_stack((v, i2, dt_list, i1, ppf_idx))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Time(s) I1(A) PPF", comments="")
        except Exception:
            pass
        messagebox.showinfo("PPF", f"Saved: {os.path.basename(path)}")

    def _run_stdp_thread(self):
        threading.Thread(target=self._run_stdp, daemon=True).start()

    def _run_stdp(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        pre_v = float(self.stdp_pre_v.get()); post_v = float(self.stdp_post_v.get())
        p_ms = float(self.stdp_pulse_ms.get()); read_v = float(self.stdp_read_v.get()); settle = float(self.stdp_read_settle.get())
        try:
            dts = [float(x.strip()) for x in str(self.stdp_dt_csv.get()).split(',') if x.strip()]
        except Exception:
            dts = [-0.05, -0.02, -0.01, 0.01, 0.02, 0.05]
        dt, i0, ia, dw = self.ms.run_stdp(
            keithley=self.keithley,
            pre_voltage=pre_v,
            post_voltage=post_v,
            pulse_width_ms=p_ms,
            delta_t_list_s=dts,
            read_voltage=read_v,
            read_settle_s=settle,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
        )
        path = self._save_path(f"STDP-Pre{pre_v}v-Post{post_v}v-{p_ms}ms-Read{read_v}v-Py")
        try:
            v = np.full_like(np.array(dt, dtype=float), float(read_v))
            data = np.column_stack((v, ia, dt, i0, dw))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Time(s) I0(A) dW", comments="")
        except Exception:
            pass
        messagebox.showinfo("STDP", f"Saved: {os.path.basename(path)}")

    def _run_srdp_thread(self):
        threading.Thread(target=self._run_srdp, daemon=True).start()

    def _run_srdp(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        p_v = float(self.srdp_pulse_v.get()); p_ms = float(self.srdp_pulse_ms.get())
        read_v = float(self.srdp_read_v.get()); pulses = int(self.srdp_pulses.get())
        try:
            freqs = [float(x.strip()) for x in str(self.srdp_freqs_csv.get()).split(',') if x.strip()]
        except Exception:
            freqs = [1, 5, 10, 20, 50]
        f_list, i_ss = self.ms.run_srdp(
            keithley=self.keithley,
            pulse_voltage=p_v,
            pulse_width_ms=p_ms,
            freq_list_hz=freqs,
            pulses_per_train=pulses,
            read_voltage=read_v,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
        )
        path = self._save_path(f"SRDP-{p_v}v-{p_ms}ms-Read{read_v}v-Py")
        try:
            # interpret Time as frequency (Hz) column in third position after V,I if desired; here V=read V
            v = np.full_like(np.array(f_list, dtype=float), float(read_v))
            data = np.column_stack((v, i_ss, f_list))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Freq(Hz)", comments="")
        except Exception:
            pass
        messagebox.showinfo("SRDP", f"Saved: {os.path.basename(path)}")

    def _run_potdep_thread(self):
        threading.Thread(target=self._run_potdep, daemon=True).start()

    def _run_potdep(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        set_v = float(self.pd_set_v.get()); reset_v = float(self.pd_reset_v.get())
        p_ms = float(self.pd_pulse_ms.get()); cycles = int(self.pd_cycles.get())
        read_v = float(self.pd_read_v.get()); relax = float(self.pd_relax_s.get())
        idx, im, ip, rat = self.ms.run_pot_dep(
            keithley=self.keithley,
            set_voltage=set_v,
            reset_voltage=reset_v,
            pulse_width_ms=p_ms,
            cycles=cycles,
            read_voltage=read_v,
            relax_s=relax,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
        )
        path = self._save_path(f"POTDEP-Set{set_v}v-Reset{reset_v}v-{p_ms}ms-Read{read_v}v-Py")
        try:
            v = np.full_like(np.array(idx, dtype=float), float(read_v))
            data = np.column_stack((v, ip, idx, im, rat))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%d\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Cycle I_immediate(A) Volatility", comments="")
        except Exception:
            pass
        messagebox.showinfo("Pot/Dep", f"Saved: {os.path.basename(path)}")

    def _run_freqresp_thread(self):
        threading.Thread(target=self._run_freqresp, daemon=True).start()

    def _run_freqresp(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        p_v = float(self.fr_pulse_v.get()); p_ms = float(self.fr_pulse_ms.get())
        vbase = float(self.fr_vbase.get()); pulses = int(self.fr_pulses.get())
        try:
            freqs = [float(x.strip()) for x in str(self.fr_freqs_csv.get()).split(',') if x.strip()]
        except Exception:
            freqs = [1, 5, 10, 20, 50]
        # Ensure stop flag is reset at the start of the run
        try:
            self.provider.stop_measurement_flag = False
        except Exception:
            pass
        # Request raw samples (freq, current, elapsed time, voltage)
        f_raw, i_raw, t_raw, v_raw = self.ms.run_frequency_response(
            keithley=self.keithley,
            pulse_voltage=p_v,
            pulse_width_ms=p_ms,
            freq_list_hz=freqs,
            pulses_per_freq=pulses,
            vbase=vbase,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
            return_raw=True,
        )
        path = self._save_path(f"FREQRESP-{p_v}v-{p_ms}ms-Vbase{vbase}v-Py")
        try:
            # Save as Time(s), Current(A), Voltage(V), Freq(Hz)
            data = np.column_stack((t_raw, i_raw, v_raw, f_raw))
            np.savetxt(path, data, fmt="%0.9E\t%0.9E\t%0.6E\t%0.6E", header="Time(s) Current(A) Voltage(V) Freq(Hz)", comments="")
        except Exception:
            pass
        messagebox.showinfo("Frequency Response", f"Saved: {os.path.basename(path)}")

    def _run_biasdecay_thread(self):
        threading.Thread(target=self._run_biasdecay, daemon=True).start()

    def _run_biasdecay(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        p_v = float(self.bd_pulse_v.get()); p_ms = float(self.bd_pulse_ms.get())
        cap_s = float(self.bd_cap_s.get()); dt_s = float(self.bd_dt_s.get())
        try:
            reads = [float(x.strip()) for x in str(self.bd_reads_csv.get()).split(',') if x.strip()]
        except Exception:
            reads = [0.1, 0.2, 0.3]
        t_arr, i_arr, v_arr = self.ms.run_bias_dependent_decay(
            keithley=self.keithley,
            pulse_voltage=p_v,
            pulse_width_ms=p_ms,
            read_voltage_list=reads,
            capture_time_s=cap_s,
            sample_dt_s=dt_s,
            icc=1e-4,
            smu_type=getattr(self.provider, 'SMU_type', 'Keithley 2401'),
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
        )
        path = self._save_path(f"BIASDECAY-{p_v}v-{p_ms}ms-Cap{cap_s}s@{dt_s}s-Py")
        try:
            data = np.column_stack((v_arr, i_arr, t_arr))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Time(s)", comments="")
        except Exception:
            pass
        messagebox.showinfo("Bias-dependent Decay", f"Saved: {os.path.basename(path)}")

    def _run_noise_thread(self):
        threading.Thread(target=self._run_noise, daemon=True).start()

    def _run_noise(self):
        if not (self.ms and self.keithley):
            messagebox.showerror("Instrument", "MeasurementService/Keithley not available")
            return
        read_v = float(self.rt_read_v.get()); cap_s = float(self.rt_cap_s.get()); dt_s = float(self.rt_dt_s.get())
        v_arr, i_arr, t_arr = self.ms.run_noise_capture(
            keithley=self.keithley,
            read_voltage=read_v,
            capture_time_s=cap_s,
            sample_dt_s=dt_s,
            icc=1e-4,
            should_stop=lambda: getattr(self.provider, 'stop_measurement_flag', False),
            on_point=None,
        )
        path = self._save_path(f"NOISE-Read{read_v}v-{cap_s}s@{dt_s}s-Py")
        try:
            v = np.full_like(np.array(t_arr, dtype=float), float(read_v))
            data = np.column_stack((v, i_arr, t_arr))
            np.savetxt(path, data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Time(s)", comments="")
        except Exception:
            pass
        messagebox.showinfo("Noise/RTN", f"Saved: {os.path.basename(path)}")


