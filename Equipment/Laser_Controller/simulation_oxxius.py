"""In-process Oxxius stand-in. No serial port is opened.

Emission and the power setpoint are written to the process-wide laser link
so the SMU simulator can raise current while a pulse is on.
"""

from __future__ import annotations

import random
import time

from Equipment.Laser_Controller.sim_link import get_laser_link

_SIM_PORTS = frozenset({"SIM", "SIMULATION", "SIM::LASER"})


def is_simulation_port(port: str) -> bool:
    """True for the laser-simulator port names the pulse GUI accepts."""
    return str(port).strip().upper() in _SIM_PORTS


class SimulatedOxxius:
    """Drop-in for ``OxxiusLaser`` used when the port is SIM.

    ``live_hiccups`` adds a short random delay before emission turns on inside
    ``pulse_on_ms`` (late turn-on, like a serial round-trip). Leave it
    False in pytest. The GUI connect path turns it on and leaves the hard
    faults below off.

    ``late_on_s`` is an extra deterministic sleep before ``emission_on``,
    applied even when ``live_hiccups`` is False. ``fail_emission`` makes
    ``emission_on`` raise and leave the link off.
    """

    def __init__(
        self,
        port: str = "SIM",
        baud: int = 38400,
        timeout: float = 1.0,
        safe_power_mw: float | None = 10,
        verbose: bool = False,
        live_hiccups: bool = False,
        late_on_s: float = 0.0,
        fail_emission: bool = False,
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.verbose = verbose
        self.live_hiccups = bool(live_hiccups)
        self.late_on_s = float(late_on_s)
        self.fail_emission = bool(fail_emission)
        self._closed = False
        self.power_mw = 0.0 if safe_power_mw is None else float(safe_power_mw)
        self._link = get_laser_link()
        self._link.set_power_mw(self.power_mw)
        self._link.set_emitting(False)
        self._log(f"simulator ready port={port!r} power_mw={self.power_mw}")

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[LASER SIM] {message}", flush=True)

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("Simulated Oxxius is closed")

    def idn(self) -> str:
        self._require_open()
        return "Oxxius LBX-SIM SIM"

    def emission_on(self) -> str:
        self._require_open()
        if self.fail_emission:
            self._link.set_emitting(False)
            raise RuntimeError("Simulated Oxxius emission failed")
        self._link.set_emitting(True, power_mw=self.power_mw)
        self._log(f"emission on {self.power_mw} mW")
        return "DL 1"

    def emission_off(self) -> str:
        self._require_open()
        self._link.set_power_mw(self.power_mw)
        self._link.set_emitting(False)
        self._log("emission off")
        return "DL 0"

    def pulse_on_ms(self, duration_ms: float) -> str:
        """Emission on, real sleep of ``duration_ms``, then emission off.

        The optical runner times this call with ``perf_counter``, so the
        sleep is a real ``time.sleep``.
        """
        self._require_open()
        if self.live_hiccups:
            time.sleep(random.uniform(0.005, 0.040))
        # Deterministic late turn-on, independent of the random hiccup.
        if self.late_on_s > 0.0:
            time.sleep(self.late_on_s)
        try:
            self.emission_on()
        except Exception:
            self._link.set_emitting(False)
            raise
        time.sleep(float(duration_ms) / 1000.0)
        return self.emission_off()

    def pulse_train(
        self,
        n_pulses: int,
        on_ms: float,
        off_ms: float,
        power_mw: float | None = None,
    ) -> list[str]:
        self._require_open()
        if n_pulses < 1:
            return []
        if power_mw is not None:
            self.set_power(power_mw)
        replies: list[str] = []
        last = int(n_pulses) - 1
        for i in range(int(n_pulses)):
            replies.append(self.pulse_on_ms(on_ms))
            if i < last:
                time.sleep(float(off_ms) / 1000.0)
        return replies

    def set_power(self, value: float) -> str:
        self._require_open()
        self.power_mw = float(value)
        self._link.set_power_mw(self.power_mw)
        self._log(f"power {self.power_mw} mW")
        return f"PM {self.power_mw}"

    def set_to_digital_power_control(self, power_mw: float) -> dict[str, str]:
        """Emission off, remember ``power_mw``. Emission stays off."""
        self._require_open()
        off = self.emission_off()
        power = self.set_power(power_mw)
        self.emission_off()
        return {"emission_off": off, "power": power, "APC": "1", "AM": "0", "TTL": "0"}

    def set_to_analog_modulation_mode(self, power_mw: float = 100) -> dict[str, str]:
        """Match the hardware helper: set power, then leave emission on."""
        self._require_open()
        off = self.emission_off()
        power = self.set_power(power_mw)
        on = self.emission_on()
        return {"emission_off": off, "power": power, "emission_on": on, "AM": "1", "APC": "1"}

    def close(self, restore_to_manual_control: bool = True) -> None:
        """Emission off, then refuse later calls. No serial port to close."""
        self._require_open()
        self.emission_off()
        self._closed = True
        self._log(f"closed restore_to_manual_control={restore_to_manual_control}")
