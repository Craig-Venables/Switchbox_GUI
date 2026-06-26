# Display tool — Arduino ST7789 + Python control

PC-side control for an Adafruit ST7789 TFT driven by an Arduino, while
keeping the existing physical Up / Down / Change-colour buttons working.

The original sketch in `existingcode/memristor_device_tester1.ino` is left
untouched. A new sketch in `arduino_firmware/display_control.ino` adds a
small ASCII serial protocol and a non-blocking flash loop so the Arduino
can be commanded from Python (or any serial terminal) at the same time as
the buttons are pressed.

## Layout

```
tools/Display/
├── arduino_firmware/
│   └── display_control/
│       └── display_control.ino   # New firmware (flash this one)
├── existingcode/
│   └── memristor_device_tester1.ino   # Original sketch, unchanged
├── display_controller.py     # DisplayController class + tiny CLI
├── main.py                   # Tk GUI
├── requirements.txt
└── README.md
```

The Arduino IDE requires the `.ino` file to sit inside a folder of the
same name — that's why `display_control.ino` lives at
`arduino_firmware/display_control/display_control.ino` rather than
directly under `arduino_firmware/`.

## Wiring

The CS / DC / RST / SPI / button pins are unchanged from the original
sketch. The only addition is one optional wire from the TFT backlight pin
to **Arduino D6** if you want brightness control or true display-off
(no light).

| Signal      | Arduino pin | Required? |
| ----------- | ----------- | --------- |
| TFT CS      | D10         | yes       |
| TFT DC      | D9          | yes       |
| TFT RST     | D8          | yes       |
| SPI MOSI    | D11 (Uno)   | yes       |
| SPI SCK     | D13 (Uno)   | yes       |
| Button Up   | D2 (to +5V) | yes       |
| Button Down | D3 (to +5V) | yes       |
| Button ChangeColour | D4 (to +5V) | yes |
| TFT BLK / LITE / LED | **D6** (PWM) | **only for brightness & display-off** |

Buttons are wired exactly as in the original sketch (`INPUT`, active HIGH).
The new firmware adds a small `millis()`-based debounce so multiple presses
from one push don't fire repeatedly.

### Backlight wiring (for brightness / true off)

The Adafruit ST7789 breakout exposes the backlight LED control as a pin
labelled **BLK**, **LITE**, or **LED**. By default it is tied high (full
brightness). To control it from the Arduino, connect that pin to **D6**
on the Arduino (D6 is PWM-capable). No series resistor is needed for the
Adafruit breakouts — they already include the LED driver.

If you leave BLK unwired, the brightness slider and Display OFF button
will appear to do nothing (the firmware still acks them; the LED just
stays on at full brightness because nothing is connected to D6). All
colour / flash / cycle features still work.

## Firmware

### 1. Install the Arduino libraries (one-time)

If you see this on compile:

```
fatal error: Adafruit_ST7789.h: No such file or directory
```

then the Arduino IDE doesn't have the display libraries yet. In the
Arduino IDE go to **Tools → Manage Libraries...** (or **Sketch → Include
Library → Manage Libraries...**) and install both of these — the same
libraries the original `memristor_device_tester1.ino` sketch needs:

- **Adafruit GFX Library** (by Adafruit)
- **Adafruit ST7735 and ST7789 Library** (by Adafruit) — this provides
  both `Adafruit_GFX.h` and `Adafruit_ST7789.h`.

When prompted, accept any dependency it offers (e.g.
*Adafruit BusIO*).

### 2. Open and upload

Open `arduino_firmware/display_control/display_control.ino` in the
Arduino IDE, pick the correct board and COM port under **Tools**, and
upload.

Serial runs at **115200 baud**.

## Python install

```powershell
pip install -r tools/Display/requirements.txt
```

## GUI

```powershell
python tools/Display/main.py
```

1. Pick the Arduino's COM port and press **Connect**.
2. Click any palette colour to set the screen.
3. Move the R / G / B sliders and press **Apply RGB** for a custom colour.
4. Tick **Flash on** and set a period (ms), then **Apply period**.
5. Under **Colour cycle**, tick the colours you want to cycle through
   (e.g. *Red* and *Blue*), press **Apply sequence**, and turn flash on
   — the screen will now walk those colours at the flash period. Press
   **Clear sequence** to go back to the normal colour↔black flash.
6. **Brightness** PWMs the backlight pin (needs BLK wired to D6). The
   slider is 0..255; **Display OFF (no light)** sets it to 0 and
   **Display ON** restores the last non-zero brightness.
7. **Query state** asks the firmware what it's currently doing and
   updates every control in the GUI to match.

The physical buttons keep working and update the same state — pressing the
on-board ChangeColour button while the GUI is connected just walks the
palette and the GUI shows the next ack/status when you press *Query state*.

## Build a standalone .exe

The GUI can be bundled into a single Windows executable with PyInstaller —
useful for handing it to someone who doesn't have Python installed.

```powershell
python tools/Display/build_exe.py
```

The first run installs PyInstaller if it isn't already present. Output:

```
tools/Display/dist/DisplayControl.exe   (~10 MB)
```

Double-click `DisplayControl.exe` to launch — no Python required. The
build is windowed (no console window) and uses
[`DisplayControl.spec`](DisplayControl.spec); edit that file if you need
to tweak hidden imports, add an icon, etc.

To rebuild from scratch, just rerun `build_exe.py` (it passes `--clean
--noconfirm` to PyInstaller). Build/cache folders that can safely be
deleted between builds: `tools/Display/build/` and
`tools/Display/dist/`.

## Programmatic use

```python
from display_controller import DisplayController

with DisplayController("COM7") as d:
    d.set_color("blue")              # palette by name
    d.set_color(2)                   # or by index 1..9
    d.set_rgb(255, 140, 0)           # custom 24-bit colour

    # Cycle red <-> blue while flashing, 400 ms per colour
    d.set_sequence(["red", "blue"])
    d.set_flash_delay_ms(400)
    d.set_flashing(True)

    d.set_brightness(64)             # dim
    d.set_display(False)             # fully off (no light)
    d.set_display(True)              # restore previous brightness

    d.set_sequence(None)             # back to plain colour <-> black flash
    print(d.query_state())
```

Errors raise `DisplayError`. `connect()` waits ~2 s after opening the port
so the Arduino has time to finish its post-reset boot before any commands
are sent (same trick as `tools/LED_testing/main.py`).

There's also a minimal CLI for one-shot commands:

```powershell
python tools/Display/display_controller.py COM7 color red
python tools/Display/display_controller.py COM7 rgb 0 200 255
python tools/Display/display_controller.py COM7 flash on
python tools/Display/display_controller.py COM7 delay 300
python tools/Display/display_controller.py COM7 sequence red blue
python tools/Display/display_controller.py COM7 sequence            # clear
python tools/Display/display_controller.py COM7 brightness 128
python tools/Display/display_controller.py COM7 display off
python tools/Display/display_controller.py COM7 display on
python tools/Display/display_controller.py COM7 state
```

## Serial protocol

All commands are ASCII, terminated with `\n`. Every command is followed by
a single ack line: `OK` on success or `ERR <reason>` on failure. Lines
starting with `STATE ` or `CMDS:` are informational and precede the `OK`.

| Command           | Meaning                                                          |
| ----------------- | ---------------------------------------------------------------- |
| `C<n>`            | Palette colour, `n` in 1..9. See table below.                    |
| `RGB r g b`       | Custom 24-bit colour (each 0..255). Selects the custom slot.     |
| `F0` / `F1`       | Flash off / on.                                                  |
| `D<ms>`           | Flash period in ms, clamped 20..60000. With no sequence it's the full on+off cycle (each phase is `ms/2`); with a sequence it's the time spent on each colour. |
| `SEQ c1[,c2,...]` | Set colour cycle list (1..9 entries from the palette). `SEQ` alone (or `SEQ -`) clears the sequence. |
| `B<n>`            | Backlight brightness 0..255 via PWM on D6. `B0` = no light.      |
| `O0` / `O1`       | Backlight off / on. `O1` restores the last non-zero brightness.  |
| `?`               | Reply `STATE C=<n> RGB=<hex> F=<0\|1> D=<ms> B=<n> SEQ=<csv\|->` then `OK`. |
| `H`               | Print command help line, then `OK`.                              |

Palette indices:

| `n` | Colour  |
| --- | ------- |
| 1   | Red     |
| 2   | Green   |
| 3   | Blue    |
| 4   | White   |
| 5   | Black   |
| 6   | Yellow  |
| 7   | Cyan    |
| 8   | Magenta |
| 9   | Orange  |

Index `0` is reserved for the "custom" slot set by `RGB`. The colour-cycle
button on the Arduino walks 1..9 and skips the custom slot.

### Examples

```text
C3              -> blue
RGB 255 64 0    -> custom orange-red
SEQ 1,3         -> cycle list is [red, blue]
D 500           -> 500 ms per entry (with seq) or 1 Hz flash (without)
F1              -> start flashing/cycling
B 64            -> dim to ~25%
O0              -> fully off (no light)
O1              -> restore last brightness
SEQ -           -> clear the cycle list
F0              -> stop flashing
?               -> STATE C=1 RGB=0xff80 F=0 D=500 B=64 SEQ=-
```

## Differences from the original sketch

- The flash loop no longer uses `delay()`, so serial commands and button
  presses stay responsive while the screen is flashing.
- Adds yellow, cyan, magenta, and orange to the palette.
- Adds a "custom" slot driven by the `RGB r g b` command.
- Adds an arbitrary **colour cycle list** (`SEQ`) so flashing can walk
  any subset of the palette instead of only colour↔black.
- Adds **backlight brightness PWM** (`B<n>`) and a true display **off**
  (`O0`) that kills the backlight (no light at all), with `O1` to
  restore.
- Adds the `?` and `H` commands for state / help.
- Button behaviour is preserved (Up = enable flash or double the period,
  Down = enable flash or halve the period, Up+Down = stop flashing,
  ChangeColour = cycle palette), now with a small debounce.
