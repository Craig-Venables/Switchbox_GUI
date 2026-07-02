# LED Testing (Arduino)

Tkinter GUI for exclusive LED control on Arduino. Firmware: `arduino_firmware/led_control/led_control.ino`.

## Run

```powershell
python tools/LED_testing/main.py
```

Also available from the Measurement GUI under **Hardware Tools → LED Testing (Arduino)**.

## Hardware

- Arduino with LEDs on D5, D7, D9, D11 (red, green, white, blue)
- Serial at 115200 baud
- Commands: indices 0–3 turn one LED on; command 4 turns all off
- Timed patterns (rotate, flash, custom) are driven from the PC over serial

## Build standalone exe

```powershell
python tools/LED_testing/build_exe.py
```

Output: `tools/LED_testing/dist/LEDTesting.exe` (Windows).

## See also

- [tools/Display/README.md](../Display/README.md) — similar Arduino + PyInstaller pattern
- [Documents/guides/GUI_EXTENSION_GUIDE.md](../../Documents/guides/GUI_EXTENSION_GUIDE.md) — tool registry integration
