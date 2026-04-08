"""
Laser FG Scope GUI — Visual constants and application defaults.
"""

from __future__ import annotations

# ── Colour palette ─────────────────────────────────────────────────────────────
COLORS: dict = {
    "bg":           "#f0f0f0",
    "panel_bg":     "#f8f8f8",
    "accent":       "#e8f0fe",
    "header":       "#1565c0",
    "header_fg":    "#ffffff",
    "fg_secondary": "#555555",
    "fg_status":    "#333333",
    "warning_bg":   "#fff3cd",
    "warning_fg":   "#856404",
    "error_fg":     "#c62828",
    "success_fg":   "#1b5e20",
    "armed_fg":     "#2e7d32",
    "disarmed_fg":  "#c62828",
    "tooltip_bg":   "#ffffe0",
    "separator":    "#cccccc",
    "plot_bg":      "#ffffff",
    "plot_grid":    "#e0e0e0",
    "trace":        "#1565c0",
}

# ── Typography ─────────────────────────────────────────────────────────────────
FONT_FAMILY       = "Segoe UI"
FONT_SIZE         = 9
FONT_HEADER_SIZE  = 10
FONT_SMALL        = 8
FONT_MONO         = "Courier New"

# ── Layout ─────────────────────────────────────────────────────────────────────
LEFT_PANEL_WIDTH  = 340   # px — scrollable control column
WINDOW_MIN_W      = 1100
WINDOW_MIN_H      = 720

# ── Hardware defaults (shown in UI on first launch) ────────────────────────────
DEFAULT_FG_ADDRESS    = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"
DEFAULT_SCOPE_ADDRESS = ""          # auto-detect on first use
DEFAULT_4200_ADDRESS  = "GPIB0::17::INSTR"
DEFAULT_LASER_PORT    = "COM4"
DEFAULT_LASER_BAUD    = 19200

# ── Measurement defaults ────────────────────────────────────────────────────────
DEFAULT_LASER_POWER_MW   = 10.0     # mW — safe startup power
DEFAULT_BIAS_V           = 0.0      # V  — 4200 SMU bias
DEFAULT_BIAS_COMPLIANCE  = 1e-3     # A  — 1 mA default compliance
DEFAULT_SMU_CHANNEL      = 1        # 4200 SMU channel

DEFAULT_PULSE_HIGH_V     = 3.3      # V  — FG high level (TTL)
DEFAULT_PULSE_LOW_V      = 0.0      # V  — FG low level
DEFAULT_PULSE_WIDTH_NS   = 100.0    # ns
DEFAULT_PULSE_RATE_HZ    = 1000.0   # Hz
DEFAULT_BURST_COUNT      = 1        # single shot

DEFAULT_SCOPE_CHANNEL    = 1
DEFAULT_TIMEBASE_US      = 0.5      # µs/div
DEFAULT_TRIG_LEVEL_V     = 0.1      # V
DEFAULT_VOLTS_PER_DIV    = 0.5      # V/div

# Seconds to wait after firing FG before reading scope
DEFAULT_CAPTURE_WAIT_S   = 0.2

# ── ARB pattern defaults ────────────────────────────────────────────────────────
DEFAULT_ARB_SAMPLE_RATE_MSPS = 10.0    # MSa/s (10 MSa/s → 100 ns per point)
ARB_MAX_POINTS               = 16384
ARB_MIN_POINTS               = 2
ARB_DRIVER_VERIFIED          = True    # Set False to lock ARB tab pending verification

# ── Scope horizontal divisions (TBS1000C) ──────────────────────────────────────
SCOPE_HORIZ_DIVISIONS = 15.0

# ── Save defaults ──────────────────────────────────────────────────────────────
DEFAULT_SAVE_FOLDER   = ""      # blank = ask on first save (standalone mode)
DEFAULT_AUTO_SAVE     = False   # auto-save toggle default
