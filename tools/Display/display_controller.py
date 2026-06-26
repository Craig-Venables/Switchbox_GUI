"""
DisplayController — Python wrapper around the `display_control.ino` firmware.

Talks ASCII line commands over USB serial at 115200 baud to an Arduino
driving an Adafruit ST7789 TFT. Every command is acknowledged with `OK` or
`ERR <reason>`. Methods raise `DisplayError` on `ERR` replies, timeouts,
or invalid arguments.

Quick example
-------------
    from display_controller import DisplayController

    with DisplayController("COM7") as d:
        d.set_color("red")
        d.set_flash_delay_ms(500)
        d.set_flashing(True)
        print(d.query_state())

See also: `main.py` in this folder for the Tk GUI.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List, Optional, Union

import serial

DEFAULT_BAUD = 115200
POST_OPEN_DELAY_S = 2.0
ACK_TIMEOUT_S = 1.5

COLOR_NAMES: Dict[str, int] = {
    "red": 1,
    "green": 2,
    "blue": 3,
    "white": 4,
    "black": 5,
    "yellow": 6,
    "cyan": 7,
    "magenta": 8,
    "orange": 9,
}

# Reverse lookup for query_state() output.
INDEX_TO_NAME: Dict[int, str] = {v: k for k, v in COLOR_NAMES.items()}
INDEX_TO_NAME[0] = "custom"


class DisplayError(RuntimeError):
    """Raised when the firmware returns ERR or the link is unhealthy."""


class DisplayController:
    """Thin serial wrapper for the display_control firmware."""

    def __init__(
        self,
        port: str,
        baud: int = DEFAULT_BAUD,
        timeout: float = ACK_TIMEOUT_S,
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None

    # ---------- lifecycle ----------
    def connect(self) -> None:
        if self._ser is not None and self._ser.is_open:
            return
        self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        # Arduino resets on serial open; give the sketch time to boot.
        time.sleep(POST_OPEN_DELAY_S)
        self._drain()

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            finally:
                self._ser = None

    def __enter__(self) -> "DisplayController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ---------- public API ----------
    def set_color(self, color: Union[str, int]) -> None:
        """Set a palette colour by index (1..9) or by name (e.g. "red")."""
        idx = self._coerce_color_index(color)
        self._send(f"C{idx}")

    def set_rgb(self, r: int, g: int, b: int) -> None:
        """Set a custom 24-bit colour. Each channel must be in 0..255."""
        for name, v in (("r", r), ("g", g), ("b", b)):
            if not isinstance(v, int) or v < 0 or v > 255:
                raise DisplayError(f"{name}={v!r} out of range 0..255")
        self._send(f"RGB {r} {g} {b}")

    def set_flashing(self, on: bool) -> None:
        self._send("F1" if on else "F0")

    def set_flash_delay_ms(self, ms: int) -> None:
        """Set flash period in ms.

        Meaning depends on whether a sequence is set (see ``set_sequence``):

        - No sequence: full on+off cycle, so each phase lasts ``ms/2``.
        - With sequence: time spent on each colour before advancing.

        Firmware clamps to 20..60000.
        """
        if not isinstance(ms, int):
            raise DisplayError(f"flash delay must be int, got {type(ms).__name__}")
        self._send(f"D{ms}")

    def set_brightness(self, value: int) -> None:
        """Set backlight brightness via PWM, 0..255.

        Requires the TFT BLK / LITE pin to be wired to Arduino D6 (PWM).
        A value of 0 turns the backlight fully off (no light); see
        ``set_display`` for a labelled on/off toggle that remembers the
        previous non-zero value.
        """
        if not isinstance(value, int):
            raise DisplayError(f"brightness must be int, got {type(value).__name__}")
        if value < 0 or value > 255:
            raise DisplayError(f"brightness {value} out of range 0..255")
        self._send(f"B{value}")

    def set_display(self, on: bool) -> None:
        """Backlight on (restore last non-zero brightness) / off."""
        self._send("O1" if on else "O0")

    def set_sequence(self, colors: Optional[Iterable[Union[str, int]]]) -> None:
        """Set the colour cycle list (1..9 entries from the palette).

        When a sequence is set and flashing is on, the display cycles
        through these palette colours at ``flash_delay_ms`` per entry
        (instead of colour↔black). Pass ``None`` or an empty iterable to
        clear the sequence.

        Examples::

            d.set_sequence(["blue", "red"])
            d.set_sequence([3, 1])  # same thing
            d.set_sequence(None)    # clear
        """
        if colors is None:
            self._send("SEQ -")
            return
        indices: List[int] = [self._coerce_color_index(c) for c in colors]
        if not indices:
            self._send("SEQ -")
            return
        if len(indices) > 9:
            raise DisplayError(f"sequence too long ({len(indices)}; max 9)")
        self._send("SEQ " + ",".join(str(i) for i in indices))

    def query_state(self) -> Dict[str, Union[int, str, bool, List[int]]]:
        """Ask the firmware for its current state.

        Returns a dict::

            {
                "color_index": 1,           # 0 = custom
                "color_name": "red",        # "custom" if color_index == 0
                "custom_rgb565": 0xF800,
                "flashing": False,
                "flash_delay_ms": 1000,
                "brightness": 255,
                "sequence": [3, 1],         # empty list if no sequence set
            }
        """
        return self._send("?", expect_state=True)  # type: ignore[return-value]

    def help(self) -> str:
        """Print firmware help; returns the help line."""
        return self._send("H", expect_help=True)  # type: ignore[return-value]

    # ---------- internals ----------
    @staticmethod
    def _coerce_color_index(color: Union[str, int]) -> int:
        if isinstance(color, int):
            if 1 <= color <= 9:
                return color
            raise DisplayError(f"colour index {color} out of range 1..9")
        if isinstance(color, str):
            key = color.strip().lower()
            if key in COLOR_NAMES:
                return COLOR_NAMES[key]
            raise DisplayError(f"unknown colour name {color!r}")
        raise DisplayError(f"colour must be int or str, got {type(color).__name__}")

    def _require_open(self) -> serial.Serial:
        if self._ser is None or not self._ser.is_open:
            raise DisplayError("serial port is not open; call connect() first")
        return self._ser

    def _drain(self) -> None:
        ser = self._require_open()
        ser.reset_input_buffer()

    def _send(
        self,
        cmd: str,
        expect_state: bool = False,
        expect_help: bool = False,
    ):
        ser = self._require_open()
        payload = (cmd.rstrip("\r\n") + "\n").encode("ascii")
        ser.reset_input_buffer()
        ser.write(payload)
        ser.flush()

        state_line: Optional[str] = None
        help_line: Optional[str] = None
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("STATE "):
                state_line = line
                continue
            if line.startswith("CMDS:"):
                help_line = line
                continue
            if line == "OK":
                if expect_state:
                    if state_line is None:
                        raise DisplayError("no STATE line before OK")
                    return self._parse_state(state_line)
                if expect_help:
                    return help_line or ""
                return None
            if line.startswith("ERR"):
                raise DisplayError(line)
            # Any other line (e.g. "READY ...") is ignored.
        raise DisplayError(f"timeout waiting for ack to {cmd!r}")

    @staticmethod
    def _parse_state(line: str) -> Dict[str, Union[int, str, bool, List[int]]]:
        # Format: STATE C=<n> RGB=<hex> F=<0|1> D=<ms> B=<bright> SEQ=<csv|->
        out: Dict[str, Union[int, str, bool, List[int]]] = {}
        for tok in line.split()[1:]:
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            if k == "C":
                idx = int(v)
                out["color_index"] = idx
                out["color_name"] = INDEX_TO_NAME.get(idx, "?")
            elif k == "RGB":
                vv = v.lower()
                if vv.startswith("0x"):
                    vv = vv[2:]
                out["custom_rgb565"] = int(vv, 16)
            elif k == "F":
                out["flashing"] = v == "1"
            elif k == "D":
                out["flash_delay_ms"] = int(v)
            elif k == "B":
                out["brightness"] = int(v)
            elif k == "SEQ":
                if v == "-" or v == "":
                    out["sequence"] = []
                else:
                    out["sequence"] = [int(x) for x in v.split(",") if x]
        return out


@contextmanager
def open_display(port: str, baud: int = DEFAULT_BAUD) -> Iterator[DisplayController]:
    """Convenience context manager: ``with open_display("COM7") as d: ...``."""
    d = DisplayController(port, baud=baud)
    d.connect()
    try:
        yield d
    finally:
        d.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Quick CLI for display_control firmware.")
    parser.add_argument("port", help="Serial port, e.g. COM7 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("color", help="Set palette colour by name or index")
    sp.add_argument("value", help="red/green/blue/white/black/yellow/cyan/magenta/orange or 1..9")

    sp = sub.add_parser("rgb", help="Set custom RGB colour")
    sp.add_argument("r", type=int)
    sp.add_argument("g", type=int)
    sp.add_argument("b", type=int)

    sp = sub.add_parser("flash", help="Toggle flashing")
    sp.add_argument("state", choices=["on", "off"])

    sp = sub.add_parser("delay", help="Set flash period in ms (20..60000)")
    sp.add_argument("ms", type=int)

    sp = sub.add_parser("brightness", help="Set backlight brightness 0..255")
    sp.add_argument("value", type=int)

    sp = sub.add_parser("display", help="Backlight on (restore) / off (no light)")
    sp.add_argument("state", choices=["on", "off"])

    sp = sub.add_parser(
        "sequence",
        help="Set cycle list, e.g. 'blue red' or '3 1'. No args clears.",
    )
    sp.add_argument("colors", nargs="*", help="Names or indices 1..9")

    sub.add_parser("state", help="Print firmware state")

    args = parser.parse_args()
    with open_display(args.port, baud=args.baud) as d:
        if args.cmd == "color":
            try:
                d.set_color(int(args.value))
            except ValueError:
                d.set_color(args.value)
        elif args.cmd == "rgb":
            d.set_rgb(args.r, args.g, args.b)
        elif args.cmd == "flash":
            d.set_flashing(args.state == "on")
        elif args.cmd == "delay":
            d.set_flash_delay_ms(args.ms)
        elif args.cmd == "brightness":
            d.set_brightness(args.value)
        elif args.cmd == "display":
            d.set_display(args.state == "on")
        elif args.cmd == "sequence":
            if not args.colors:
                d.set_sequence(None)
            else:
                parsed: List[Union[str, int]] = []
                for c in args.colors:
                    try:
                        parsed.append(int(c))
                    except ValueError:
                        parsed.append(c)
                d.set_sequence(parsed)
        elif args.cmd == "state":
            print(d.query_state())
