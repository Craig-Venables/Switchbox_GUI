"""Wiring help text and diagram for PMU TTL laser + SMU read."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

WIRING_SUMMARY = (
    "PMU → RPM → laser TTL (pulse only)\n"
    "SMU cables → device directly (no RPM)\n"
    "PMU CH2 → leave unconnected\n"
    "One GPIB owner only"
)

WIRING_HELP_TEXT = """
PMU TTL laser + SMU resistance — how to connect
===============================================

Your bench
----------
  PMU  →  RPM  →  laser TTL     (pulsing only)
  SMU  →  device pads           (cables straight out of the SMU — no RPM)

The RPM sits only on the PMU→laser path. The SMU does not go through an RPM
for this test.

Drive strength (common failure mode)
------------------------------------
A scope probe at the laser TTL pin can show a "nice" pulse while the laser
still stays off. The 4225-PMU has ~50 Ω source Z; the old USRLIB default used
the RPM 10 mA current range. Into a real laser MOD/TTL load that can sag
Vpeak below the driver's logic-high threshold. Bench-supply toggle works
because it can source much more current.

Modules now use PMU 10 V / 200 mA range (0.2 A) + pulse_load(1e6).
Recompile/reload A_pmu_laser_smu_read in Clarius after pulling this change.

Scope check (probe RIGHT at laser TTL, DC couple, 1 MΩ):
  1) Laser disconnected (open): note Vpeak  (expect ~5 V)
  2) Laser connected: note Vpeak again
  - Open ≈5 V, loaded still ≥ ~3.5–4 V → amplitude OK; check polarity / mode
  - Open ≈5 V, loaded << that (e.g. <2–3 V) → still sagging; add a TTL
    buffer/line driver between RPM and laser (best fix), or confirm the
    laser input is not 50 Ω-terminated (50 Ω into 50 Ω halves to ~2.5 V)

GPIB / KXCI
-----------
- Only one program may own the 4200 GPIB at a time.
- Close other tools before Test GPIB or Run.
- Typical address: GPIB0::17::INSTR
- Enable KXCI on the 4200.

Checklist
---------
  [ ] PMU1 CH1 → RPM (pulse) → coax → laser TTL / MOD in  (0 V / 5 V)
  [ ] PMU1 CH2 → nothing
  [ ] SMU force (+sense if 4-wire) → device HI   (direct from SMU)
  [ ] SMU LO → device LO
  [ ] Laser optics → sample
  [ ] Library loaded: A_pmu_laser_smu_read
      (pmu_laser_smu_run + pmu_laser_smu_stream rebuilt after drive-strength fix)
""".strip()


def draw_wiring_diagram(fig: "Figure") -> None:
    """Draw: PMU–RPM–laser and SMU–device (direct)."""
    fig.clear()
    ax: "Axes" = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.5)
    ax.axis("off")
    ax.set_title("PMU → RPM → laser   |   SMU → device (direct)", fontsize=12, pad=8)

    def box(x, y, w, h, label, color="#dce6f2"):
        from matplotlib.patches import FancyBboxPatch

        p = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.05,rounding_size=0.15",
            linewidth=1.2,
            edgecolor="#1f4e79",
            facecolor=color,
        )
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=8)

    def arrow(x0, y0, x1, y1, label="", color="#333333"):
        ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
        )
        if label:
            ax.text(
                (x0 + x1) / 2,
                (y0 + y1) / 2 + 0.22,
                label,
                ha="center",
                fontsize=7,
                color=color,
            )

    box(0.3, 5.2, 2.2, 1.4, "4225-PMU\nCH1", "#cfe2f3")
    box(3.0, 5.2, 2.0, 1.4, "4225-RPM\n(pulse only)", "#fff2cc")
    box(5.6, 5.2, 2.4, 1.4, "Laser TTL in\n0 V / 5 V", "#fce5cd")
    arrow(2.5, 5.9, 3.0, 5.9)
    arrow(5.0, 5.9, 5.6, 5.9, "TTL")

    box(0.3, 2.4, 2.2, 1.6, "SMU\n(force/sense)", "#d9ead3")
    box(3.0, 2.4, 2.4, 1.6, "Device pads\nHI / LO", "#ead1dc")
    arrow(2.5, 3.2, 3.0, 3.2, "direct cables\n(no RPM)", color="#38761d")

    box(6.0, 2.4, 2.4, 1.6, "Sample\n(optical)", "#ead1dc")
    arrow(6.8, 5.2, 7.2, 4.0, "light", color="#a64d79")

    ax.text(
        5.0,
        0.55,
        "RPM = laser pulsing path only. SMU cables come straight from the SMU.",
        ha="center",
        fontsize=8,
        style="italic",
    )
    fig.tight_layout()
