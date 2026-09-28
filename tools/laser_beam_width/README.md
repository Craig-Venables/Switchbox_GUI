# Laser Beam Width Tool

Live PyQt5 GUI to measure laser spot size from an overhead USB camera (back-illuminated sample).

## Setup

```bash
pip install -r tools/laser_beam_width/requirements.txt
```

On this lab PC, use **Python 3.10** (or any environment with `opencv-python` and `PyQt5`). The default conda Python 3.13 may not have these packages installed.

## Small spot workflow (few pixels wide)

1. **Display zoom** — set `8×`–`32×` under **Zoom & spot** to magnify the live view.
2. **Click image to set spot center** — enables manual centering on a tiny spot (magenta crosshair).
3. **ROI half-size** — use **10–30 px** for analysis (default 30).
4. **Sensor ROI (uc480)** — optional hardware crop: set e.g. 256×256 px, click **Apply sensor ROI** to zoom the sensor readout itself (reset with **Reset full sensor**).

Navitar lens zoom is manual on the hardware — use that first, then fine-tune with display zoom and sensor ROI in software.

## Run

From repo root:

```bash
python tools/laser_beam_width/main.py
```

## Camera

Your **Thorlabs C1284R13C (uc480)** camera is **not** a standard USB webcam. With a Logitech C920 also connected, OpenCV only sees the Logitech.

| Backend | Use for |
|---------|---------|
| **Thorlabs UC480 (ThorCam)** | Your overhead Thorlabs camera (default) |
| OpenCV (USB webcam) | Logitech C920 or other UVC webcams |
| Thorlabs TLCamera | Kiralux/Zelux models only (not your camera) |

Requires **ThorCam** installed (`C:\Program Files\Thorlabs\...`) and `pylablib`.

### Connect steps

1. **Close ThorCam** and any other app using the camera.
2. Restart this tool.
3. Backend: **Thorlabs UC480 (ThorCam)**
4. Click **Scan cameras** — you should see `C1284R13C (4102827807)`
5. Click **Connect**

If the camera shows `[in use]`, close other programs and try again.

### Z focus (built-in)

The sidebar **Z focus (Kinesis)** panel controls the Thorlabs Z stage without opening Kenisis:

1. Connect the camera first.
2. Click **Connect Z** (Kinesis only — does not load TLCamera).
3. Use **Z − / Z +** with a small jog step (default 0.05 mm) while watching the live image.

Serial and limits are in `beam_width_config.json` under `"stage"`.

### Running alongside Kenisis (motor GUI)

You **can** run both apps at once — they use different devices (uc480 camera vs Kinesis stage + VISA laser).

**Suggested workflow**

1. Start **beam width** first and **Connect** the camera.
2. Start **Kenisis** — motors connect on launch; click **Connect laser** and **Home motors** only when you need them (not at startup).
3. Jog the stage in Kenisis while watching the live camera in beam width.
4. If the stream drops, click **Disconnect → Connect** in beam width (Kenisis can stay open).

Kenisis must **not** use `from pylablib.devices import Thorlabs` (loads TLCamera SDK) — use the direct `KinesisMotor` import in `motor_control.py`.

A **single combined app** is optional later (stage jog panel embedded in beam width) if you want one window; not required for simultaneous use.

## Workflow

1. Connect camera (backend **OpenCV**, index **0**).
2. Optional: **Capture background** with laser OFF, enable **Subtract background**.
3. **Calibrate** (optional):
   - Enter known distance (µm) between two points on a ruler/grid at the sample plane.
   - Click **Calibrate: click two points**, then click both ends on the live image.
   - Or leave **Pixels only** checked to measure in px.
4. Read **FWHM** and **1/e²** widths (X, Y, major/minor) in the results panel.
5. **Freeze frame** for a stable reading; **Save snapshot + results** exports PNG, JSON, and CSV.

## Laser safety

Laser radiation can cause **permanent eye damage**. Use minimum power for alignment, keep beam paths enclosed, and wear appropriate eyewear. See also `gui/laser_fg_scope_gui/README.md`.

## Files

| File | Purpose |
|------|---------|
| `beam_width_config.json` | Camera settings and last calibration |
| `analysis/gaussian_fit.py` | Gaussian profile fit and width metrics |
| `camera/opencv_source.py` | USB capture |
| `gui/main_window.py` | Main application |
