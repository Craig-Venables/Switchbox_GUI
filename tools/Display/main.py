"""
Tk GUI for the Switchbox Display tool.

Drives an Adafruit ST7789 TFT through the `display_control.ino` Arduino
firmware over USB serial.

Run::

    python tools/Display/main.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

import serial
from serial.tools import list_ports

from display_controller import COLOR_NAMES, DisplayController, DisplayError

PALETTE: List[str] = [
    "red", "green", "blue",
    "white", "black", "yellow",
    "cyan", "magenta", "orange",
]

PREVIEW_HEX = {
    "red":     "#ff0000",
    "green":   "#00c000",
    "blue":    "#0000ff",
    "white":   "#ffffff",
    "black":   "#101010",
    "yellow":  "#ffff00",
    "cyan":    "#00ffff",
    "magenta": "#ff00ff",
    "orange":  "#ff8c00",
}

BTN_FG = {
    "red":     "#ffffff",
    "green":   "#000000",
    "blue":    "#ffffff",
    "white":   "#000000",
    "black":   "#ffffff",
    "yellow":  "#000000",
    "cyan":    "#000000",
    "magenta": "#ffffff",
    "orange":  "#000000",
}


class DisplayControlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Display Control — Arduino ST7789")
        self.geometry("500x600")
        self.minsize(460, 560)

        style = ttk.Style(self)
        try:
            style.theme_use("vista")   # Windows native look
        except tk.TclError:
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
        style.configure("TNotebook.Tab", padding=[14, 6])
        style.configure("TLabelframe.Label", font=("TkDefaultFont", 9, "bold"))

        # Model
        self._ctrl: Optional[DisplayController] = None
        self._flash_active = False

        # Vars
        self._port_var        = tk.StringVar()
        self._r_var           = tk.IntVar(value=255)
        self._g_var           = tk.IntVar(value=140)
        self._b_var           = tk.IntVar(value=0)
        self._delay_var       = tk.StringVar(value="500")
        self._brightness_var  = tk.IntVar(value=255)
        self._bright_pct_var  = tk.StringVar(value="100%")
        self._status_text     = tk.StringVar(value="Not connected — choose a port and press Connect.")
        self._seq_vars: List[tk.BooleanVar] = [tk.BooleanVar(value=False) for _ in PALETTE]

        self._build_ui()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    #  UI construction                                                      #
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        self._build_connection_bar()
        self._build_notebook()
        self._build_status_bar()
        self._set_controls_enabled(False)

    # ---- connection bar (always visible at top) ----------------------- #
    def _build_connection_bar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 8, 10, 6))
        bar.pack(fill=tk.X)

        self._dot = tk.Label(
            bar, text="●", fg="#cc0000", bg=self.cget("bg"),
            font=("TkDefaultFont", 16),
        )
        self._dot.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(bar, text="Port:").pack(side=tk.LEFT)
        self._port_combo = ttk.Combobox(
            bar, textvariable=self._port_var, width=14, state="readonly",
        )
        self._port_combo.pack(side=tk.LEFT, padx=(4, 4), fill=tk.X, expand=True)
        ttk.Button(bar, text="Refresh", width=7, command=self._refresh_ports).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self._connect_btn = ttk.Button(
            bar, text="Connect", command=self._toggle_connect, width=12,
        )
        self._connect_btn.pack(side=tk.LEFT)

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X)

    # ---- tabbed content ----------------------------------------------- #
    def _build_notebook(self) -> None:
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self._build_colour_tab()
        self._build_flash_tab()
        self._build_brightness_tab()

    # ---- Colour tab --------------------------------------------------- #
    def _build_colour_tab(self) -> None:
        tab = ttk.Frame(self._nb, padding=10)
        self._nb.add(tab, text="  Colour  ")

        # Palette
        pal = ttk.LabelFrame(tab, text="Palette", padding=8)
        pal.pack(fill=tk.X, pady=(0, 10))
        for i, name in enumerate(PALETTE):
            r, c = divmod(i, 3)
            tk.Button(
                pal,
                text=name.capitalize(),
                bg=PREVIEW_HEX[name],
                fg=BTN_FG[name],
                activebackground=PREVIEW_HEX[name],
                activeforeground=BTN_FG[name],
                font=("TkDefaultFont", 10, "bold"),
                relief="raised", bd=2,
                cursor="hand2",
                command=lambda n=name: self._set_color(n),
            ).grid(row=r, column=c, padx=3, pady=3, sticky="nsew", ipady=6)
        for c in range(3):
            pal.columnconfigure(c, weight=1)

        # Custom RGB
        rgb = ttk.LabelFrame(tab, text="Custom colour", padding=8)
        rgb.pack(fill=tk.X)

        self._swatch = tk.Label(rgb, text="", bg="#ff8c00", width=4, relief="groove")
        self._swatch.grid(row=0, column=0, rowspan=3, padx=(0, 10), sticky="nsew")

        for row, (lbl, var) in enumerate(
            (("R", self._r_var), ("G", self._g_var), ("B", self._b_var))
        ):
            ttk.Label(rgb, text=lbl, width=2).grid(row=row, column=1, sticky="w")
            sc = ttk.Scale(
                rgb, from_=0, to=255, orient="horizontal",
                command=lambda v, _v=var: self._on_rgb_change(_v, v),
            )
            sc.set(var.get())
            sc.grid(row=row, column=2, sticky="ew", padx=(4, 4))
            e = ttk.Entry(rgb, textvariable=var, width=4)
            e.grid(row=row, column=3)
            e.bind("<Return>",   lambda _e: self._update_swatch())
            e.bind("<FocusOut>", lambda _e: self._update_swatch())
        rgb.columnconfigure(2, weight=1)

        ttk.Button(rgb, text="Apply custom colour", command=self._apply_rgb).grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )
        self._update_swatch()

    # ---- Flash & Cycle tab -------------------------------------------- #
    def _build_flash_tab(self) -> None:
        tab = ttk.Frame(self._nb, padding=10)
        self._nb.add(tab, text="  Flash & Cycle  ")

        # Big flash toggle
        flash_lf = ttk.LabelFrame(tab, text="Flashing", padding=10)
        flash_lf.pack(fill=tk.X, pady=(0, 10))

        self._flash_btn = tk.Button(
            flash_lf,
            text="Flash: OFF",
            font=("TkDefaultFont", 13, "bold"),
            bg="#d0d0d0", fg="#444444",
            activebackground="#d0d0d0",
            relief="raised", bd=3,
            cursor="hand2", height=2,
            command=self._toggle_flash,
        )
        self._flash_btn.pack(fill=tk.X, pady=(0, 8))

        period_row = ttk.Frame(flash_lf)
        period_row.pack(fill=tk.X)
        ttk.Label(period_row, text="Period (ms):").pack(side=tk.LEFT)
        period_entry = ttk.Entry(period_row, textvariable=self._delay_var, width=8)
        period_entry.pack(side=tk.LEFT, padx=(6, 6))
        period_entry.bind("<Return>", lambda _e: self._apply_delay())
        ttk.Button(period_row, text="Apply", command=self._apply_delay).pack(side=tk.LEFT)

        ttk.Label(
            flash_lf,
            text=(
                "No cycle: screen alternates colour ↔ black.\n"
                "With a cycle (below): steps through chosen colours instead."
            ),
            font=("TkDefaultFont", 8), foreground="#666666", justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # Colour cycle
        seq_lf = ttk.LabelFrame(tab, text="Colour cycle", padding=10)
        seq_lf.pack(fill=tk.X)

        ttk.Label(
            seq_lf,
            text="Tick the colours to cycle through (e.g. Red + Blue). Flash must be ON.",
            font=("TkDefaultFont", 8), foreground="#666666",
            wraplength=420, justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        for i, name in enumerate(PALETTE):
            r, c = divmod(i, 3)
            cell = ttk.Frame(seq_lf)
            cell.grid(row=1 + r, column=c, sticky="w", padx=6, pady=2)
            tk.Label(cell, bg=PREVIEW_HEX[name], width=2, relief="groove").pack(
                side=tk.LEFT, padx=(0, 4)
            )
            ttk.Checkbutton(cell, text=name.capitalize(), variable=self._seq_vars[i]).pack(
                side=tk.LEFT
            )
        for c in range(3):
            seq_lf.columnconfigure(c, weight=1)

        btns = ttk.Frame(seq_lf)
        btns.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="Apply cycle", command=self._apply_sequence).pack(side=tk.LEFT)
        ttk.Button(btns, text="Clear cycle", command=self._clear_sequence).pack(
            side=tk.LEFT, padx=(8, 0)
        )

    # ---- Brightness tab ----------------------------------------------- #
    def _build_brightness_tab(self) -> None:
        tab = ttk.Frame(self._nb, padding=10)
        self._nb.add(tab, text="  Brightness  ")

        bright_lf = ttk.LabelFrame(tab, text="Backlight brightness", padding=10)
        bright_lf.pack(fill=tk.X, pady=(0, 12))

        slider_row = ttk.Frame(bright_lf)
        slider_row.pack(fill=tk.X)
        self._brightness_scale = ttk.Scale(
            slider_row, from_=0, to=255, orient="horizontal",
            command=self._on_brightness_slide,
        )
        self._brightness_scale.set(255)
        self._brightness_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        # Auto-apply when the user releases the slider
        self._brightness_scale.bind("<ButtonRelease-1>", lambda _e: self._apply_brightness())

        e = ttk.Entry(slider_row, textvariable=self._brightness_var, width=5)
        e.pack(side=tk.LEFT)
        e.bind("<Return>", lambda _e: self._apply_brightness())
        ttk.Button(slider_row, text="Apply", command=self._apply_brightness).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        pct_row = ttk.Frame(bright_lf)
        pct_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pct_row, text="Level:").pack(side=tk.LEFT)
        ttk.Label(pct_row, textvariable=self._bright_pct_var,
                  font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Label(
            bright_lf,
            text="Note: requires TFT BLK / LITE pin wired to Arduino D6.",
            font=("TkDefaultFont", 8), foreground="#666666",
        ).pack(anchor="w", pady=(6, 0))

        # Power on / off
        power_lf = ttk.LabelFrame(tab, text="Display power", padding=10)
        power_lf.pack(fill=tk.X)

        btn_row = ttk.Frame(power_lf)
        btn_row.pack(fill=tk.X)

        tk.Button(
            btn_row,
            text="Turn ON",
            bg="#2e8b2e", fg="#ffffff",
            activebackground="#3aaa3a", activeforeground="#ffffff",
            font=("TkDefaultFont", 10, "bold"),
            relief="raised", bd=2, cursor="hand2",
            command=self._display_on, width=12,
        ).pack(side=tk.LEFT, ipady=4)

        tk.Button(
            btn_row,
            text="Turn OFF",
            bg="#8b2e2e", fg="#ffffff",
            activebackground="#aa3a3a", activeforeground="#ffffff",
            font=("TkDefaultFont", 10, "bold"),
            relief="raised", bd=2, cursor="hand2",
            command=self._display_off, width=12,
        ).pack(side=tk.LEFT, padx=(10, 0), ipady=4)

        ttk.Label(
            power_lf,
            text=(
                "Turn OFF kills the backlight (no light at all). "
                "Turn ON restores the previous brightness level."
            ),
            font=("TkDefaultFont", 8), foreground="#666666",
            wraplength=420, justify="left",
        ).pack(anchor="w", pady=(8, 0))

    # ---- status bar (always visible at bottom) ------------------------ #
    def _build_status_bar(self) -> None:
        ttk.Separator(self, orient="horizontal").pack(fill=tk.X)

        foot = ttk.Frame(self, padding=(8, 4))
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        self._sync_btn = ttk.Button(
            foot, text="Sync state from Arduino", command=self._on_query
        )
        self._sync_btn.pack(side=tk.RIGHT)

        self._status_bar = tk.Label(
            self,
            textvariable=self._status_text,
            bg="#f0f0f0", fg="#333333",
            anchor="w", padx=10, pady=5,
            font=("TkDefaultFont", 9),
            wraplength=440, justify="left",
        )
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------ #
    #  Helpers                                                              #
    # ------------------------------------------------------------------ #
    def _set_status(self, text: str, kind: str = "ok") -> None:
        self._status_text.set(text)
        bg  = {"ok": "#d4edda", "error": "#f8d7da", "info": "#f0f0f0"}.get(kind, "#f0f0f0")
        fg  = {"ok": "#155724", "error": "#721c24", "info": "#333333"}.get(kind, "#333333")
        self._status_bar.configure(bg=bg, fg=fg)

    def _set_dot(self, connected: bool) -> None:
        self._dot.configure(fg=("#2e8b2e" if connected else "#cc0000"))

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        for child in self.winfo_children():
            self._recurse_state(child, state, enabled)
        self._connect_btn.state(["!disabled"])
        self._port_combo.state(["!disabled"] if not enabled else ["disabled"])
        self._sync_btn.state(state)

    def _recurse_state(self, widget, state: list, enabled: bool) -> None:
        if widget is self._connect_btn or widget is self._port_combo:
            return
        try:
            if isinstance(widget, (ttk.Button, ttk.Checkbutton, ttk.Entry,
                                   ttk.Combobox, ttk.Scale)):
                widget.state(state)
            elif isinstance(widget, tk.Button):
                widget.configure(state="normal" if enabled else "disabled")
        except tk.TclError:
            pass
        for ch in widget.winfo_children():
            self._recurse_state(ch, state, enabled)

    def _refresh_ports(self) -> None:
        ports = sorted(p.device for p in list_ports.comports())
        self._port_combo["values"] = ports
        if ports and not self._port_var.get():
            self._port_var.set(ports[0])
        if not ports:
            self._set_status("No serial ports found — is the Arduino plugged in?", "info")

    def _safe_call(self, fn, desc: str) -> bool:
        if self._ctrl is None or not self._ctrl.is_open:
            self._set_status("Not connected.", "error")
            return False
        try:
            fn()
        except (DisplayError, serial.SerialException, OSError) as exc:
            self._set_status(f"{desc} failed: {exc}", "error")
            return False
        self._set_status(desc, "ok")
        return True

    # ------------------------------------------------------------------ #
    #  Connect / disconnect                                                 #
    # ------------------------------------------------------------------ #
    def _toggle_connect(self) -> None:
        if self._ctrl is not None and self._ctrl.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        port = self._port_var.get().strip()
        if not port:
            messagebox.showwarning("Display", "Pick a COM port first.")
            return
        self._set_status(f"Connecting to {port}…", "info")
        self.update_idletasks()
        try:
            ctrl = DisplayController(port)
            ctrl.connect()
        except (serial.SerialException, DisplayError, OSError) as exc:
            self._set_status(f"Connection to {port} failed: {exc}", "error")
            messagebox.showerror("Display", f"Could not open {port}:\n{exc}")
            return
        self._ctrl = ctrl
        self._connect_btn.configure(text="Disconnect")
        self._set_dot(True)
        self._set_controls_enabled(True)
        self._set_status(f"Connected to {port}. Use the tabs above to control the display.", "ok")

    def _disconnect(self) -> None:
        if self._ctrl is None:
            return
        try:
            if self._ctrl.is_open:
                try:
                    self._ctrl.set_flashing(False)
                except DisplayError:
                    pass
            self._ctrl.close()
        finally:
            self._ctrl = None
            self._connect_btn.configure(text="Connect")
            self._set_dot(False)
            self._flash_active = False
            self._update_flash_btn()
            self._set_controls_enabled(False)
            self._set_status("Disconnected.", "info")

    # ------------------------------------------------------------------ #
    #  Colour tab callbacks                                                 #
    # ------------------------------------------------------------------ #
    def _set_color(self, name: str) -> None:
        self._safe_call(
            lambda: self._ctrl.set_color(name),
            f"Colour set to {name.capitalize()}",
        )

    def _apply_rgb(self) -> None:
        try:
            r = max(0, min(255, int(self._r_var.get())))
            g = max(0, min(255, int(self._g_var.get())))
            b = max(0, min(255, int(self._b_var.get())))
        except (tk.TclError, ValueError):
            self._set_status("RGB values must be integers 0–255.", "error")
            return
        self._r_var.set(r)
        self._g_var.set(g)
        self._b_var.set(b)
        self._update_swatch()
        self._safe_call(
            lambda: self._ctrl.set_rgb(r, g, b),
            f"Custom colour ({r}, {g}, {b}) applied",
        )

    def _on_rgb_change(self, var: tk.IntVar, value: str) -> None:
        try:
            var.set(int(float(value)))
        except (ValueError, tk.TclError):
            return
        self._update_swatch()

    def _update_swatch(self) -> None:
        try:
            r = max(0, min(255, int(self._r_var.get())))
            g = max(0, min(255, int(self._g_var.get())))
            b = max(0, min(255, int(self._b_var.get())))
        except (tk.TclError, ValueError):
            return
        self._swatch.configure(bg=f"#{r:02x}{g:02x}{b:02x}")

    # ------------------------------------------------------------------ #
    #  Flash & Cycle tab callbacks                                          #
    # ------------------------------------------------------------------ #
    def _toggle_flash(self) -> None:
        new_state = not self._flash_active
        if self._safe_call(
            lambda: self._ctrl.set_flashing(new_state),
            f"Flash {'started' if new_state else 'stopped'}",
        ):
            self._flash_active = new_state
            self._update_flash_btn()

    def _update_flash_btn(self) -> None:
        if self._flash_active:
            self._flash_btn.configure(
                text="Flash: ON  ●",
                bg="#1a56cc", fg="#ffffff",
                activebackground="#2266dd", activeforeground="#ffffff",
            )
        else:
            self._flash_btn.configure(
                text="Flash: OFF",
                bg="#d0d0d0", fg="#444444",
                activebackground="#d0d0d0", activeforeground="#444444",
            )

    def _apply_delay(self) -> None:
        try:
            ms = int(self._delay_var.get())
        except ValueError:
            self._set_status("Period must be a whole number of milliseconds.", "error")
            return
        ms = max(20, min(60000, ms))
        self._delay_var.set(str(ms))
        self._safe_call(
            lambda: self._ctrl.set_flash_delay_ms(ms),
            f"Flash period set to {ms} ms",
        )

    def _selected_sequence(self) -> List[str]:
        return [name for name, var in zip(PALETTE, self._seq_vars) if var.get()]

    def _apply_sequence(self) -> None:
        colors = self._selected_sequence()
        if not colors:
            self._set_status("Tick at least one colour to create a cycle.", "error")
            return
        desc = " → ".join(c.capitalize() for c in colors)
        self._safe_call(lambda: self._ctrl.set_sequence(colors), f"Cycle: {desc}")

    def _clear_sequence(self) -> None:
        for var in self._seq_vars:
            var.set(False)
        self._safe_call(lambda: self._ctrl.set_sequence(None), "Colour cycle cleared")

    # ------------------------------------------------------------------ #
    #  Brightness tab callbacks                                             #
    # ------------------------------------------------------------------ #
    def _on_brightness_slide(self, value: str) -> None:
        try:
            n = int(float(value))
            self._brightness_var.set(n)
            self._bright_pct_var.set(f"{round(n / 255 * 100)}%")
        except (ValueError, tk.TclError):
            pass

    def _apply_brightness(self) -> None:
        try:
            n = int(self._brightness_var.get())
        except (ValueError, tk.TclError):
            self._set_status("Brightness must be 0–255.", "error")
            return
        n = max(0, min(255, n))
        self._brightness_var.set(n)
        self._brightness_scale.set(n)
        self._bright_pct_var.set(f"{round(n / 255 * 100)}%")
        self._safe_call(
            lambda: self._ctrl.set_brightness(n),
            f"Brightness set to {n} ({round(n / 255 * 100)}%)",
        )

    def _display_on(self) -> None:
        self._safe_call(lambda: self._ctrl.set_display(True), "Display turned ON")

    def _display_off(self) -> None:
        if self._safe_call(lambda: self._ctrl.set_display(False), "Display turned OFF"):
            self._brightness_var.set(0)
            self._brightness_scale.set(0)
            self._bright_pct_var.set("0%")

    # ------------------------------------------------------------------ #
    #  Sync from Arduino                                                    #
    # ------------------------------------------------------------------ #
    def _on_query(self) -> None:
        if self._ctrl is None or not self._ctrl.is_open:
            self._set_status("Not connected.", "error")
            return
        try:
            state = self._ctrl.query_state()
        except (DisplayError, serial.SerialException, OSError) as exc:
            self._set_status(f"Sync failed: {exc}", "error")
            return

        if "flashing" in state:
            self._flash_active = bool(state["flashing"])
            self._update_flash_btn()
        if "flash_delay_ms" in state:
            self._delay_var.set(str(state["flash_delay_ms"]))
        if "brightness" in state:
            b = int(state["brightness"])
            self._brightness_var.set(b)
            self._brightness_scale.set(b)
            self._bright_pct_var.set(f"{round(b / 255 * 100)}%")
        if "sequence" in state:
            seq = list(state["sequence"])   # type: ignore[arg-type]
            for i in range(len(PALETTE)):
                self._seq_vars[i].set((i + 1) in seq)

        seq_list = list(state.get("sequence") or [])
        seq_desc = (
            " → ".join(
                PALETTE[i - 1].capitalize()
                for i in seq_list
                if 1 <= i <= len(PALETTE)
            )
            if seq_list else "none"
        )
        cn = str(state.get("color_name", "?")).capitalize()
        fl = "on" if state.get("flashing") else "off"
        d  = state.get("flash_delay_ms", "?")
        br = state.get("brightness", "?")
        self._set_status(
            f"Synced — colour: {cn},  flash: {fl},  period: {d} ms,  "
            f"brightness: {br},  cycle: {seq_desc}",
            "ok",
        )

    # ------------------------------------------------------------------ #
    #  Shutdown                                                             #
    # ------------------------------------------------------------------ #
    def _on_close(self) -> None:
        try:
            if self._ctrl is not None and self._ctrl.is_open:
                try:
                    self._ctrl.set_flashing(False)
                except DisplayError:
                    pass
                self._ctrl.close()
        finally:
            self.destroy()


def main() -> None:
    missing = [c for c in PALETTE if c not in COLOR_NAMES]
    if missing:
        raise RuntimeError(f"palette colours missing from controller: {missing}")
    DisplayControlApp().mainloop()


if __name__ == "__main__":
    main()
