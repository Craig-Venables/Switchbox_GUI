import threading
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import pandas as pd

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200A_PMUDualChannel


class PMUMinimalGUI(tk.Tk):
	def __init__(self):
		super().__init__()
		self.title("4200A PMU - Minimal Controller")
		self.geometry("900x600")

		self.pmu: Keithley4200A_PMUDualChannel | None = None

		self._build_controls()
		self._build_plot()

	def _build_controls(self):
		frm = ttk.Frame(self)
		frm.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

		# Connection
		self.addr_var = tk.StringVar(value="192.168.0.10:8888|PMU1")
		self.conn_btn = ttk.Button(frm, text="Connect", command=self.on_connect)
		self.disc_btn = ttk.Button(frm, text="Disconnect", command=self.on_disconnect, state=tk.DISABLED)
		self.idn_lbl = ttk.Label(frm, text="Status: Disconnected", width=30)

		row0 = ttk.Frame(frm); row0.pack(fill=tk.X, pady=2)
		ttk.Label(row0, text="Address:").pack(side=tk.LEFT)
		ttk.Entry(row0, textvariable=self.addr_var, width=30).pack(side=tk.LEFT, padx=4)
		self.conn_btn.pack(in_=row0, side=tk.LEFT, padx=4)
		self.disc_btn.pack(in_=row0, side=tk.LEFT, padx=4)
		self.idn_lbl.pack(in_=row0, side=tk.LEFT, padx=8)

		# Pulse params
		self.amp_var = tk.DoubleVar(value=0.5)
		self.base_var = tk.DoubleVar(value=0.0)
		self.width_var = tk.DoubleVar(value=10e-6)
		self.period_var = tk.DoubleVar(value=20e-6)
		self.npulses_var = tk.IntVar(value=1)
		self.src_ch_var = tk.IntVar(value=1)
		self.vrng_var = tk.DoubleVar(value=2.0)
		self.irng_var = tk.DoubleVar(value=200e-6)

		row1 = ttk.Frame(frm); row1.pack(fill=tk.X, pady=2)
		for label, var, w in [
			("Amplitude V", self.amp_var, 8),
			("Base V", self.base_var, 8),
			("Width s", self.width_var, 10),
			("Period s", self.period_var, 10),
			("Pulses", self.npulses_var, 6),
		]:
			container = ttk.Frame(row1); container.pack(side=tk.LEFT, padx=6)
			ttk.Label(container, text=label).pack(anchor=tk.W)
			ttk.Entry(container, textvariable=var, width=w).pack()

		row2 = ttk.Frame(frm); row2.pack(fill=tk.X, pady=2)
		# Source channel
		sch_box = ttk.Frame(row2); sch_box.pack(side=tk.LEFT, padx=6)
		ttk.Label(sch_box, text="Source CH").pack(anchor=tk.W)
		ch_sel = ttk.Combobox(sch_box, values=[1, 2], width=5, state="readonly", textvariable=self.src_ch_var)
		ch_sel.pack()
		ch_sel.current(0)

		# Ranges
		vr_box = ttk.Frame(row2); vr_box.pack(side=tk.LEFT, padx=6)
		ttk.Label(vr_box, text="V meas range (V)").pack(anchor=tk.W)
		ttk.Entry(vr_box, textvariable=self.vrng_var, width=10).pack()

		ir_box = ttk.Frame(row2); ir_box.pack(side=tk.LEFT, padx=6)
		ttk.Label(ir_box, text="I meas range (A)").pack(anchor=tk.W)
		ttk.Entry(ir_box, textvariable=self.irng_var, width=10).pack()

		# Run button
		self.run_btn = ttk.Button(frm, text="Run Pulse", command=self.on_run, state=tk.DISABLED)
		self.run_btn.pack(pady=6)

	def _build_plot(self):
		plot_frame = ttk.Frame(self)
		plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

		self.fig = Figure(figsize=(6, 4), dpi=100)
		self.ax = self.fig.add_subplot(111)
		self.ax.set_xlabel("Time (s)")
		self.ax.set_ylabel("Current (A)")
		self.ax.grid(True, alpha=0.3)

		self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
		self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

	def _set_connected(self, connected: bool, msg: str = ""):
		self.conn_btn.config(state=(tk.DISABLED if connected else tk.NORMAL))
		self.disc_btn.config(state=(tk.NORMAL if connected else tk.DISABLED))
		self.run_btn.config(state=(tk.NORMAL if connected else tk.DISABLED))
		self.idn_lbl.config(text=f"Status: {'Connected' if connected else 'Disconnected'} {msg}")

	def on_connect(self):
		addr = (self.addr_var.get() or "").strip()
		if not addr:
			messagebox.showwarning("Address", "Please enter an address like 192.168.0.10:8888|PMU1")
			return
			
		# Establish connection (in UI thread; quick calls)
		try:
			self.pmu = Keithley4200A_PMUDualChannel(addr)
			self._set_connected(True, f"({addr})")
		except Exception as exc:
			self.pmu = None
			self._set_connected(False)
			messagebox.showerror("Connection Failed", str(exc))

	def on_disconnect(self):
		try:
			if self.pmu:
				self.pmu.close()
		finally:
			self.pmu = None
			self._set_connected(False)

	def on_run(self):
		if not self.pmu:
			messagebox.showwarning("Not connected", "Connect to the PMU first.")
			return

		# Capture parameters
		amp = float(self.amp_var.get())
		base = float(self.base_var.get())
		width = float(self.width_var.get())
		period = float(self.period_var.get())
		npulses = int(self.npulses_var.get())
		src_ch = int(self.src_ch_var.get())
		v_rng = float(self.vrng_var.get())
		i_rng = float(self.irng_var.get())

		self.run_btn.config(state=tk.DISABLED)
		threading.Thread(target=self._run_and_plot, args=(amp, base, width, period, npulses, src_ch, v_rng, i_rng), daemon=True).start()

	def _run_and_plot(self, amp, base, width, period, npulses, src_ch, v_rng, i_rng):
		try:
			# Use the existing dual-channel helper to measure and fetch a DataFrame
			df = self.pmu.measure_at_voltage(
				amplitude_v=float(amp), base_v=float(base),
				width_s=float(width), period_s=float(period),
				meas_start_pct=0.0, meas_stop_pct=1.0,
				source_channel=int(src_ch), hold_other_at_zero=True,
				force_fixed_ranges=True,
				v_meas_range=float(v_rng), i_meas_range=float(i_rng),
				num_pulses=int(npulses), timeout_s=30.0,
			)
			# Plot time vs current
			self._update_plot(df)
		except Exception as exc:
			self.after(0, lambda: messagebox.showerror("Run Failed", str(exc)))
		finally:
			self.after(0, lambda: self.run_btn.config(state=(tk.NORMAL if self.pmu else tk.DISABLED)))

	def _update_plot(self, df: pd.DataFrame):
		def do_plot():
			self.ax.clear()
			self.ax.set_xlabel("Time (s)")
			self.ax.set_ylabel("Current (A)")
			self.ax.grid(True, alpha=0.3)
			if df is not None and not df.empty and "t (s)" in df.columns and "I (A)" in df.columns:
				self.ax.plot(df["t (s)"], df["I (A)"], color="#1976d2", lw=1.2)
			else:
				self.ax.text(0.5, 0.5, "No data", transform=self.ax.transAxes, ha="center", va="center")
			self.canvas.draw_idle()
		self.after(0, do_plot)

	def destroy(self):
		try:
			if self.pmu:
				self.pmu.close()
		except Exception:
			pass
		super().destroy()


if __name__ == "__main__":
	app = PMUMinimalGUI()
	app.mainloop()
