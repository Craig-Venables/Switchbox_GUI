"""
Laser FG Scope GUI — Help Panel
================================
Displayed in the Help tab:
  1. Wiring diagram image
  2. Text sub-tabs: Quick Start | How It Works | What's Automatic | HW Limits | Parameters
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_DIAGRAM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "wiring_diagram.png",
)

# ── Text content ──────────────────────────────────────────────────────────────

_QUICK_START = """\
QUICK START — STEP BY STEP
════════════════════════════

Before you start, check the wiring diagram image above matches your bench setup.

─────────────────────────────────────────────────────────────────────────────
ONE-TIME SETUP (do once per session)
─────────────────────────────────────────────────────────────────────────────

Step 1  Go to the Connections tab.
        Enter the VISA address for the function generator (SDG1032X) and
        oscilloscope (TBS1000C), the GPIB address for the 4200 SMU, and
        the COM port for the laser.
        Click Connect on each instrument.
        Green dot = connected.

Step 2  Go back to the Controls tab.
        Set the laser power (mW) in the Laser Settings section.
        Click "Arm DM1 (enable TTL gate)".
        The laser is now powered at that level but emission is GATED —
        the function generator TTL signal controls when it fires.
        ⚠ Wear laser safety goggles before arming.

That's it for setup. Now you can Run as many times as you like.

─────────────────────────────────────────────────────────────────────────────
EACH MEASUREMENT (press Run)
─────────────────────────────────────────────────────────────────────────────

Step 3  Set your pulse parameters in the Function Generator section:
          Simple Pulse tab: width, rep rate, high voltage, burst count.
          ARB Pattern tab:  build a multi-segment pattern (advanced).

Step 4  Set the scope settings: timebase, trigger level, channel.
        Leave "Auto-configure scope" ticked for the GUI to apply these.

Step 5  (Optional) Set the 4200 SMU bias voltage. This is applied
        automatically on every Run. Leave at 0 V if not needed.

Step 6  Press ▶ Run.
        The GUI programs the FG and scope automatically, fires one burst
        of laser pulses, captures the waveform, and plots the result.
        You do NOT touch the FG or scope front panels.

Step 7  The waveform appears on the right.
        Use Save CSV + PNG to export.

─────────────────────────────────────────────────────────────────────────────
TO STOP
─────────────────────────────────────────────────────────────────────────────
  Press ■ Stop at any time. When finished for the session:
  • Click "Disarm (emission off)" on the laser panel.
  • Go to 4200 Bias → Output OFF.
  • Cover the laser aperture.
"""

_HOW_IT_WORKS = """\
WHAT HAPPENS WHEN YOU PRESS RUN
════════════════════════════════

Everything below is fully AUTOMATIC — the GUI sends all SCPI/serial
commands. You do not touch any instrument front panel.

Step 1 — SMU Bias  (Keithley 4200, if connected)
  Sends KXCI commands:
    DV <ch>,0,<voltage>,<compliance>   — force the set voltage
    CN <ch>                            — connect / enable output
  The 4200 holds this voltage for the entire measurement.
  NO C module / UL mode is used.  Just two direct KXCI commands.
  If the 4200 is not connected this step is skipped silently.

Step 2 — Laser re-arm check
  Only if you ticked "Re-arm before each Run" (advanced option).
  Normally you arm the laser ONCE with the Arm DM1 button; Run
  does not re-send the serial commands each time (saves ~0.7 s).

Step 3 — Function Generator configuration  (SDG1032X)
  Simple Pulse mode:
    C1:BSWV WVTP,PULSE            — select PULSE waveform type
    C1:BSWV FRQ,<rate>            — set repetition frequency
    C1:BSWV HIGH,<high_v>         — set HIGH level
    C1:BSWV LOW,<low_v>           — set LOW level
    C1:BSWV WIDTH,<width_s>       — set pulse width
  ARB Pattern mode:
    C1:WVDT WVNM,... WAVEDATA,<binary>  — upload waveform (WVDT binary)
    C1:ARWV NAME,LSRPULSE               — select it
    C1:BSWV WVTP,ARB                    — set to ARB mode
  Both modes then:
    C1:BTWV STATE,ON               — enable burst
    C1:BTWV TRSR,BUS               — software trigger source
    C1:BTWV TIME,<burst_count>     — number of pulses
    C1:OUTP CH1,ON                 — turn on CH1 output

Step 4 — Oscilloscope configuration  (TBS1000C, if auto-configure ticked)
  *RST                             — reset to defaults
  CH<n>:SCA <v_per_div>           — set vertical scale
  HOR:SCA <tb_s>                  — set horizontal timebase
  TRIG:MAI:TYP EDGE               — edge trigger type
  TRIG:MAI:EDGE:SOU EXT           — external trigger input
  TRIG:MAI:EDGE:SLO RIS           — rising edge
  TRIG:MAI:LEV <trig_v>           — trigger threshold
  ACQ:STOPA SEQ                   — stop after one acquisition
  ACQ:STATE RUN                   — ARM — ready for trigger

  15 ms wait to ensure the scope is fully armed.

Step 5 — Fire  (hardware-synchronised from here)
  C1:TRIG is sent to the SDG1032X.
  The SDG1032X CH1 output fires the pulse(s) → TTL drives laser DM1.
  SDG1032X SYNC OUT fires at the same moment (hardware) →
    TBS1000C EXT TRIG starts the acquisition.
  Sub-nanosecond jitter. No Python timing involved after this point.

Step 6 — Wait for capture
  Polls TRIG:STATE? until the scope reports SAVE (captured).
  Falls back to a configurable sleep if polling times out.

Step 7 — Read waveform
  DAT:SOU CH<n>    — select channel
  DAT:ENC ASCII    — ASCII encoding
  WFMO?            — read preamble (scaling info)
  CURV?            — read raw ADC codes
  Scales using YMULT / YOFF / YZERO from the preamble.
  Builds time array from XINCR.
  Result: time[], voltage[] arrays sent to the plot.
"""

_AUTOMATIC_VS_MANUAL = """\
WHAT IS AUTOMATIC vs WHAT YOU DO MANUALLY
══════════════════════════════════════════

FULLY AUTOMATIC ON EVERY RUN PRESS
────────────────────────────────────────────────────────────────────
  ✔ Function generator programming (pulse shape, burst, output on)
  ✔ ARB waveform binary upload (if ARB mode selected)
  ✔ Scope configuration (timebase, trigger, V/div)  [if auto-configure ticked]
  ✔ Scope armed for single acquisition
  ✔ Hardware fire via C1:TRIG
  ✔ Waveform readback and plot update
  ✔ SMU bias applied (if 4200 connected)

You never touch the FG or scope front panels during measurement.

────────────────────────────────────────────────────────────────────
MANUAL — ONCE PER SESSION (setup only)
────────────────────────────────────────────────────────────────────
  ☐ Connect instruments (Connections tab — one per instrument)
  ☐ Arm the laser: set power, press "Arm DM1 (enable TTL gate)"
      This takes ~0.7 s of serial commands and is intentionally kept
      separate so you can verify the laser is ready before firing.
      After arming, you Run as many times as you like without re-arming.

────────────────────────────────────────────────────────────────────
OPTIONAL MANUAL ACTIONS
────────────────────────────────────────────────────────────────────
  ◦ "Apply Bias" button — applies SMU voltage immediately outside a Run
      (useful for pre-biasing before pressing Run the first time)
  ◦ Untick "Auto-configure scope" if you have set the scope up manually
      and don't want *RST to reset your settings each Run
  ◦ "Output OFF" on the bias panel — safe power-down of the 4200 SMU

────────────────────────────────────────────────────────────────────
WHEN YOU DO NOT HAVE ALL 4 INSTRUMENTS
────────────────────────────────────────────────────────────────────
  • Missing 4200 SMU   → bias step is skipped, rest works normally
  • Missing laser      → FG still runs, scope captures FG signal directly
  • FG is REQUIRED     → Run will error if FG not connected
  • Scope is REQUIRED  → Run will error if scope not connected
"""

_HW_LIMITS = """\
HARDWARE LIMITS AT A GLANCE
════════════════════════════

Instrument          │ Key limit
────────────────────┼──────────────────────────────────────────────
SDG1032X (FG)       │ PULSE mode min width : 32.6 ns
                    │ PULSE mode edge time  : 16.8 ns rise/fall
                    │ ARB sample rate       : up to 30 MSa/s
                    │ ARB min resolution    : 33 ns/pt at 30 MSa/s
                    │ ARB max points        : 16,384
                    │ SYNC OUT jitter       : < 2 ns to CH1
────────────────────┼──────────────────────────────────────────────
Oxxius LBX-405 DM1  │ Rise / fall time      : ≤ 2 ns
                    │ Bandwidth             : ≥ 150 MHz
                    │ TTL HIGH threshold    : 2.5 V  (use ≥ 3.3 V)
                    │ TTL LOW threshold     : 0.8 V  (use 0 V)
────────────────────┼──────────────────────────────────────────────
TBS1000C Scope      │ Sample rate           : 1 GS/s max
                    │ Bandwidth             : 50–200 MHz (variant)
                    │ Record length         : up to 20,000 pts
                    │ Effective rise time   : ≈ 1.75 ns (200 MHz)
────────────────────┼──────────────────────────────────────────────
Keithley 4200 SMU   │ Role in this GUI      : DC bias only
                    │ Bias method           : KXCI DV / CN / CL
                    │ No C module used      : interactive mode only
────────────────────┴──────────────────────────────────────────────
"""

_PARAM_GUIDE = """\
PARAMETER GUIDE
═══════════════

LASER SETTINGS
  Set power (mW)
    Power level set over serial before arming.
    Start low (5–10 mW) and increase once you confirm the setup works.
    Class 3B — always wear goggles before arming.

  Arm DM1 / Disarm
    Arm: sends PM <mW>, APC 1, DM 1, emission on  over serial.
    After arming the laser is ready but emission is gated by FG TTL.
    Disarm: turns emission off and disables DM mode.

SIMPLE PULSE TAB
  Pulse High Voltage (V)
    FG CH1 output HIGH level. Must exceed laser TTL threshold (≥ 2.5 V).
    3.3 V is the recommended value for the Oxxius DM1 input.
    Do NOT exceed 5 V into the laser modulation input.

  Pulse Low Voltage (V)
    FG CH1 LOW level. 0 V = laser off. Keep at 0 V.

  Pulse Width (ns)
    On-time of each laser pulse. Minimum 32.6 ns in Simple Pulse mode.
    For sub-100 ns pulses at 33 ns resolution, use ARB Pattern mode.

  Rep Rate (Hz)
    How fast pulses repeat within a burst. 1 kHz = 1 ms period.
    Must satisfy: period > pulse width (FG will clamp otherwise).

  Burst Count
    Number of pulses fired per Run button press.
    1 = single shot. Use >1 for repeated pulses in one capture.

ARB PATTERN TAB
  Sample Rate (MSa/s)
    DAC sample rate. 10 MSa/s = 100 ns per sample. 30 MSa/s = 33 ns/sample.
    More samples = finer timing resolution but fewer total points.

  Segment table
    Each row is a (Level, Duration_ns) pair. H = TTL high, L = TTL low.
    Total points = sum of all segments × sample_rate. Max 16,384 points.
    Press Preview to see the pattern before uploading.

SCOPE SETTINGS
  Timebase (µs/div)
    Set to ~3–5× expected pulse width. 100 ns pulse → use 50–100 ns/div.

  Trigger Level (V)
    SDG1032X SYNC OUT peak is ~3.3 V. Set trigger to 1.5–2.0 V.
    This is the EXT TRIG threshold, not the signal level.

  V/div (V)
    Vertical scale. Match the expected signal amplitude at the DUT output.
    If using a 10× probe, the apparent amplitude is 10× smaller.

  Auto-configure scope
    When ticked, the GUI sends *RST + all settings to scope before each Run.
    Untick if you have configured the scope manually and want to keep settings.

  Capture wait (s)
    Time to wait after firing before reading the waveform.
    0.2 s is usually enough. Increase if the scope occasionally misses the trigger.

4200 SMU BIAS
  Bias Voltage (V)
    DC voltage applied to the DUT. Common range: ±0.5 V to ±5 V.
    Applied automatically at the start of each Run.

  Compliance (A)
    Maximum current the SMU will source. 1 mA default protects most devices.
    Increase for low-resistance devices if needed.
"""


class HelpPanel(ttk.Frame):
    """Help tab: wiring diagram image + documentation sub-tabs."""

    def __init__(self, parent: tk.Widget, **kw) -> None:
        super().__init__(parent, **kw)
        self._img_ref: Optional[Any] = None
        self._build()

    def _build(self) -> None:
        # ── Wiring diagram ────────────────────────────────────────────────────
        img_lf = ttk.LabelFrame(self, text="  Wiring Diagram", padding=4)
        img_lf.pack(fill="x", padx=6, pady=(6, 4))

        self._img_label = tk.Label(img_lf, bg="#ffffff",
                                   text="Loading wiring diagram…")
        self._img_label.pack(fill="x")
        self.after(50, self._load_image)

        # ── Documentation sub-tabs ────────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        tabs = [
            ("Quick Start",        _QUICK_START),
            ("How It Works",       _HOW_IT_WORKS),
            ("Auto vs Manual",     _AUTOMATIC_VS_MANUAL),
            ("HW Limits",          _HW_LIMITS),
            ("Parameters",         _PARAM_GUIDE),
        ]
        for title, content in tabs:
            self._add_text_tab(nb, title, content)

    def _add_text_tab(self, nb: ttk.Notebook, title: str, content: str) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text=f" {title} ")
        txt = tk.Text(
            frame, wrap="none", relief="flat",
            font=("Courier New", 8), bg="#fafafa",
            height=16, state="normal",
        )
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        txt.pack(fill="both", expand=True, side="left")
        txt.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        txt.insert("1.0", content.strip())
        txt.configure(state="disabled")

    def _load_image(self) -> None:
        if not os.path.exists(_DIAGRAM_PATH):
            self._img_label.configure(
                text="wiring_diagram.png not found — see gui/laser_fg_scope_gui/",
                fg="red",
            )
            return

        if _PIL_OK:
            try:
                img = Image.open(_DIAGRAM_PATH)
                max_w = 330
                w, h = img.size
                if w > max_w:
                    img = img.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
                self._img_ref = ImageTk.PhotoImage(img)
                self._img_label.configure(image=self._img_ref, text="")
                return
            except Exception as exc:
                self._img_label.configure(
                    text=f"Could not load image: {exc}", fg="red")
                return

        # Fallback: tk.PhotoImage (PNG, Tk 8.6+)
        try:
            photo = tk.PhotoImage(file=_DIAGRAM_PATH)
            w = photo.width()
            if w > 330:
                factor = max(1, w // 330)
                photo = photo.subsample(factor, factor)
            self._img_ref = photo
            self._img_label.configure(image=self._img_ref, text="")
        except Exception:
            self._img_label.configure(
                text=(
                    "Install Pillow for image display:  pip install pillow\n"
                    "Diagram file: gui/laser_fg_scope_gui/wiring_diagram.png"
                ),
                justify="left", fg="#555",
            )
