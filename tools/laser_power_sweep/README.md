# Laser Power Sweep

Standalone PyQt5 tool: measure laser power with a **Thorlabs PM100D** while sweeping either **digital mW setpoints** or **TTL + current %** (pmu-style, manual TTL).

## Control modes

| Mode | How power is set | TTL |
|------|------------------|-----|
| **Digital power (mW)** | `set_to_digital_power_control(set_mw)` + emission ON | Not used |
| **TTL + current %** | `set_current_percent_for_ttl(%)` after `prepare_for_ttl_modulation` | **You** hold ~5 V on TTL manually (FG/bench supply) |

The tool does **not** control a function generator. In TTL mode, apply 5 V to the laser TTL input yourself — keep TTL LOW for zeroing, HIGH during each measurement (use the settle time to apply voltage before the PM100D reads).

## Safety

- PM100D max **50 mW** — digital setpoints above 50 mW rejected.
- Abort if any reading **≥ 40 mW** (configurable).
- Zero meter with laser/TTL OFF.

## Run

```bash
python tools/laser_power_sweep/main.py
```

## TTL + current % workflow

1. Select **TTL + current % — you hold 5 V on TTL manually**.
2. Connect laser + PM100D (laser arms TTL modulation).
3. Zero meter (TTL LOW).
4. Enter current levels e.g. `10, 20, …, 100`.
5. Start sweep — for each point the tool sets `CM` %, waits settle time (apply 5 V on TTL), then measures.

## Outputs

`laser_power_sweep_*.csv` / `.json` / `.png` — column `set_mw` or `set_current_pct` by mode.

Optional spot size for power density:

- **Manual** — enter mean FWHM and 1/e² diameter (µm)
- **From focus scan** — pick folder (e.g. `Desktop\laser_fit\on ito`), click **Load Z list**, select **Z position**; FWHM and 1/e² are pulled from `beam_width_*.json` (mean of X/Y axes, same as `plot_focus_scan.py`)

Intensity columns (mW/µm²; `1 mW/µm² = 100 kW/cm²`):

- **1/e²** — Gaussian **peak** \(I_0 = 2P/(\pi w^2)\) with \(w = d_{1/e^2}/2\)
- **FWHM** — average inside the FWHM disk (\(0.5\,P / A_\mathrm{FWHM}\); a Gaussian puts half its power there)

Saved JSON includes `focus_scan_dir`, `focus_scan_z_mm`, `fwhm_um`, `e2_um`.
