"""
Tkinter GUI for exclusive LED control on Arduino (see arduino_firmware/led_control.ino).
Commands: 0-3 = LED on (D5/D7/D9/D11), 4 = all off.

Timed patterns (rotate, flash, custom pick) are driven from the PC with serial commands; no firmware change.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

import serial
from serial.tools import list_ports

BAUD = 115200
POST_OPEN_DELAY_S = 2.0

# Pin order matches firmware: index 0..3 -> D5, D7, D9, D11
LED_LABELS = [
    "Red (D5)",
    "Green (D7)",
    "White (D9)",
    "Blue (D11)",
]


class LedControlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LED testing — Arduino")
        self.geometry("420x560")
        self.minsize(380, 520)

        self._ser: Optional[serial.Serial] = None
        self._choice = tk.StringVar(value="off")
        self._port_var = tk.StringVar()
        self._status = tk.StringVar(value="Disconnected.")

        self._interval_var = tk.StringVar(value="500")
        self._pattern_kind = tk.StringVar(value="rotate")
        self._after_id: Optional[str] = None
        self._rotate_i = 0
        self._flash_on_phase = True
        self._flash_index = "0"
        self._custom_sequence: List[int] = []
        self._custom_step_idx = 0
        self._custom_include_vars: List[tk.BooleanVar] = [
            tk.BooleanVar(value=True) for _ in range(4)
        ]
        self._custom_checks: List[ttk.Checkbutton] = []

        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="COM port:").grid(row=0, column=0, sticky="w")
        self._port_combo = ttk.Combobox(
            top, textvariable=self._port_var, width=28, state="readonly"
        )
        self._port_combo.grid(row=0, column=1, sticky="ew", padx=(6, 4))
        ttk.Button(top, text="Refresh", command=self._refresh_ports).grid(
            row=0, column=2, sticky="e"
        )
        top.columnconfigure(1, weight=1)

        btn_row = ttk.Frame(top)
        btn_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self._connect_btn = ttk.Button(btn_row, text="Connect", command=self._toggle_connect)
        self._connect_btn.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="All LEDs off", command=self._all_leds_off).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        led_frame = ttk.LabelFrame(self, text="Manual (exclusive)", padding=10)
        led_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        off_rb = ttk.Radiobutton(
            led_frame,
            text="All off",
            variable=self._choice,
            value="off",
            command=self._on_manual_led_change,
        )
        off_rb.pack(anchor="w")
        self._manual_radios: List[ttk.Radiobutton] = [off_rb]

        for i, label in enumerate(LED_LABELS):
            rb = ttk.Radiobutton(
                led_frame,
                text=label,
                variable=self._choice,
                value=str(i),
                command=self._on_manual_led_change,
            )
            rb.pack(anchor="w")
            self._manual_radios.append(rb)

        pat = ttk.LabelFrame(self, text="Timed patterns", padding=10)
        pat.pack(fill=tk.X, padx=10, pady=(0, 6))

        ttk.Label(pat, text="Pattern:").grid(row=0, column=0, sticky="w")
        self._pattern_combo = ttk.Combobox(
            pat,
            textvariable=self._pattern_kind,
            values=("rotate", "flash", "custom"),
            state="readonly",
            width=18,
        )
        self._pattern_combo.grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Label(
            pat,
            text=(
                "Rotate: all four in order. Flash: blink the manual colour above. "
                "Custom: tick colours below; cycles Red→Green→White→Blue skipping unticked."
            ),
            wraplength=390,
            font=("TkDefaultFont", 8),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self._custom_frame = ttk.LabelFrame(
            pat,
            text="Custom cycle — colours to include",
            padding=(8, 6),
        )
        cust_inner = ttk.Frame(self._custom_frame)
        cust_inner.pack(fill=tk.X)
        for i, label in enumerate(LED_LABELS):
            short = label.split()[0]
            cb = ttk.Checkbutton(
                cust_inner,
                text=short,
                variable=self._custom_include_vars[i],
            )
            cb.grid(row=0, column=i, padx=(0, 10), sticky="w")
            self._custom_checks.append(cb)
        ttk.Label(
            self._custom_frame,
            text="Order is always Red, then Green, then White, then Blue (among those checked).",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(4, 0))
        self._custom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._custom_frame.grid_remove()

        ttk.Label(pat, text="Duration (ms):").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self._interval_entry = ttk.Entry(pat, textvariable=self._interval_var, width=10)
        self._interval_entry.grid(row=3, column=1, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Label(
            pat,
            text=(
                "Rotate / custom: time each colour stays on. "
                "Flash: on-time and off-time are each this long."
            ),
            wraplength=390,
            font=("TkDefaultFont", 8),
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))

        pat_btns = ttk.Frame(pat)
        pat_btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._pat_start = ttk.Button(pat_btns, text="Start", command=self._start_pattern)
        self._pat_start.pack(side=tk.LEFT, padx=(0, 6))
        self._pat_stop = ttk.Button(pat_btns, text="Stop", command=self._stop_pattern, state="disabled")
        self._pat_stop.pack(side=tk.LEFT)

        ttk.Label(self, textvariable=self._status, wraplength=380).pack(
            fill=tk.X, padx=10, pady=(0, 8)
        )

        self._refresh_ports()
        self._pattern_kind.trace_add("write", self._on_pattern_kind_trace)
        self._on_pattern_kind_trace()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _pattern_running(self) -> bool:
        return self._after_id is not None

    def _set_manual_led_widgets_enabled(self, enabled: bool) -> None:
        state: Callable[[ttk.Radiobutton], None] = (
            (lambda w: w.state(["!disabled"])) if enabled else (lambda w: w.state(["disabled"]))
        )
        for w in self._manual_radios:
            state(w)

    def _on_pattern_kind_trace(self, *_args: object) -> None:
        if self._pattern_kind.get() == "custom":
            self._custom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        else:
            self._custom_frame.grid_remove()

    def _set_pattern_controls_enabled(self, running: bool) -> None:
        self._pat_start.configure(state="disabled" if running else "normal")
        self._pat_stop.configure(state="normal" if running else "disabled")
        self._interval_entry.configure(state="disabled" if running else "normal")
        self._pattern_combo.configure(state="disabled" if running else "readonly")
        for cb in self._custom_checks:
            cb.configure(state="disabled" if running else "normal")

    def _refresh_ports(self) -> None:
        devices = [p.device for p in list_ports.comports()]
        self._port_combo["values"] = devices
        if devices and self._port_var.get() not in devices:
            self._port_var.set(devices[0])
        elif not devices:
            self._port_var.set("")
        if not self._pattern_running():
            self._status.set(
                f"Ports: {', '.join(devices) if devices else '(none found)'}"
            )

    def _toggle_connect(self) -> None:
        if self._ser and self._ser.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        port = self._port_var.get().strip()
        if not port:
            messagebox.showwarning("Port", "Select a COM port.")
            return
        try:
            self._ser = serial.Serial(
                port,
                BAUD,
                timeout=0.5,
                write_timeout=1.0,
            )
        except serial.SerialException as exc:
            self._status.set(f"Connect failed: {exc}")
            messagebox.showerror("Serial", str(exc))
            self._ser = None
            return

        self._connect_btn.configure(text="Disconnect")
        self._status.set(f"Connected to {port}. Waiting for board…")
        self.update_idletasks()
        time.sleep(POST_OPEN_DELAY_S)
        try:
            if self._ser:
                self._ser.reset_input_buffer()
        except serial.SerialException:
            pass
        self._status.set(f"Connected to {port}.")
        self._apply_manual_command()

    def _disconnect(self) -> None:
        self._stop_pattern(apply_manual=False)
        if self._ser:
            try:
                if self._ser.is_open:
                    self._send_command("4")
                    try:
                        self._ser.flush()
                    except serial.SerialException:
                        pass
                    time.sleep(0.05)
                    self._ser.close()
            except serial.SerialException:
                pass
            self._ser = None
        self._choice.set("off")
        self._connect_btn.configure(text="Connect")
        self._status.set("Disconnected.")

    def _send_command(self, line: str) -> None:
        if not self._ser or not self._ser.is_open:
            return
        try:
            self._ser.write(f"{line}\n".encode("ascii"))
        except serial.SerialException as exc:
            self._status.set(f"Write failed: {exc}")

    def _all_leds_off(self) -> None:
        if self._pattern_running():
            self._stop_pattern(apply_manual=False)
        self._choice.set("off")
        self._send_command("4")
        if self._ser and self._ser.is_open:
            port = self._port_var.get()
            self._status.set(f"Connected to {port}. All LEDs off.")

    def _apply_manual_command(self) -> None:
        v = self._choice.get()
        if v == "off":
            self._send_command("4")
        else:
            self._send_command(v)

    def _on_manual_led_change(self) -> None:
        if self._pattern_running():
            return
        self._apply_manual_command()

    def _parse_interval_ms(self) -> int:
        try:
            ms = int(self._interval_var.get().strip())
        except ValueError:
            ms = 500
        return max(50, min(ms, 60_000))

    def _start_pattern(self) -> None:
        if not self._ser or not self._ser.is_open:
            messagebox.showwarning("Serial", "Connect to the Arduino first.")
            return
        if self._pattern_running():
            return

        kind = self._pattern_kind.get()
        if kind == "flash":
            ch = self._choice.get()
            if ch == "off":
                messagebox.showwarning("Flash", "Select a colour above (not All off).")
                return
            self._flash_index = ch
            self._flash_on_phase = True

        if kind == "rotate":
            self._rotate_i = 0

        if kind == "custom":
            self._custom_sequence = [
                i for i in range(4) if self._custom_include_vars[i].get()
            ]
            if not self._custom_sequence:
                messagebox.showwarning(
                    "Custom cycle",
                    "Select at least one colour to include.",
                )
                return
            self._custom_step_idx = 0

        self._set_manual_led_widgets_enabled(False)
        self._set_pattern_controls_enabled(True)
        self._status.set(f"Pattern: {kind} …")
        self._pattern_tick()

    def _stop_pattern(self, apply_manual: bool = True) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._set_manual_led_widgets_enabled(True)
        self._set_pattern_controls_enabled(False)
        if apply_manual and self._ser and self._ser.is_open:
            self._apply_manual_command()
            port = self._port_var.get()
            self._status.set(f"Connected to {port}.")

    def _pattern_tick(self) -> None:
        if not self._ser or not self._ser.is_open:
            self._stop_pattern()
            return

        ms = self._parse_interval_ms()
        kind = self._pattern_kind.get()

        if kind == "rotate":
            self._send_command(str(self._rotate_i))
            self._rotate_i = (self._rotate_i + 1) % 4
        elif kind == "flash":
            if self._flash_on_phase:
                self._send_command(self._flash_index)
            else:
                self._send_command("4")
            self._flash_on_phase = not self._flash_on_phase
        elif kind == "custom":
            idx = self._custom_sequence[self._custom_step_idx]
            self._send_command(str(idx))
            self._custom_step_idx = (self._custom_step_idx + 1) % len(
                self._custom_sequence
            )

        self._after_id = self.after(ms, self._pattern_tick)

    def _on_close(self) -> None:
        self._disconnect()
        self.destroy()


def main() -> None:
    app = LedControlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
