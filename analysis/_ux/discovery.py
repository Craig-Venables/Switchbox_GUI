"""Discover Pulse_measurements and Solartron_1260 folders under a sample tree."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


PULSE_FOLDER = "Pulse_measurements"
SOLARTRON_FOLDER = "Solartron_1260"
SKIP_SECTION_NAMES = {
    "device_tracking",
    "device_research",
    "sample_analysis",
    "analysis",
}


@dataclass(frozen=True)
class DeviceLocation:
    """One {sample}/{section}/{device} location."""

    sample_dir: Path
    sample_name: str
    section: str
    device: str

    @property
    def device_dir(self) -> Path:
        return self.sample_dir / self.section / self.device

    @property
    def device_id(self) -> str:
        return f"{self.sample_name}_{self.section}_{self.device}"

    @property
    def pulse_dir(self) -> Path:
        return self.device_dir / PULSE_FOLDER

    @property
    def solartron_dir(self) -> Path:
        return self.device_dir / SOLARTRON_FOLDER

    def has_pulse(self) -> bool:
        return self.pulse_dir.is_dir()

    def has_solartron(self) -> bool:
        return self.solartron_dir.is_dir()


def _is_section_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and len(path.name) == 1
        and path.name.isalpha()
        and path.name not in SKIP_SECTION_NAMES
    )


def _is_device_dir(path: Path) -> bool:
    return path.is_dir() and path.name.isdigit()


def iter_device_locations(sample_dir: Path | str) -> List[DeviceLocation]:
    """Walk sample for letter/number device folders."""
    sample_dir = Path(sample_dir)
    sample_name = sample_dir.name
    locations: List[DeviceLocation] = []
    if not sample_dir.is_dir():
        return locations

    for section_dir in sorted(sample_dir.iterdir()):
        if not _is_section_dir(section_dir):
            continue
        for device_dir in sorted(section_dir.iterdir()):
            if not _is_device_dir(device_dir):
                continue
            locations.append(
                DeviceLocation(
                    sample_dir=sample_dir,
                    sample_name=sample_name,
                    section=section_dir.name,
                    device=device_dir.name,
                )
            )
    return locations


def discover_pulse_devices(sample_dir: Path | str) -> List[DeviceLocation]:
    return [loc for loc in iter_device_locations(sample_dir) if loc.has_pulse()]


def discover_solartron_devices(sample_dir: Path | str) -> List[DeviceLocation]:
    return [loc for loc in iter_device_locations(sample_dir) if loc.has_solartron()]


def discover_aux_devices(
    sample_dir: Path | str,
    kinds: Sequence[str] = ("pulse", "solartron"),
) -> List[DeviceLocation]:
    """Devices that have any of the requested aux folders."""
    kinds_set = {k.lower() for k in kinds}
    out: List[DeviceLocation] = []
    for loc in iter_device_locations(sample_dir):
        want = False
        if "pulse" in kinds_set and loc.has_pulse():
            want = True
        if "solartron" in kinds_set and loc.has_solartron():
            want = True
        if want:
            out.append(loc)
    return out


def list_pulse_txt_files(pulse_dir: Path | str) -> List[Path]:
    """Non-recursive .txt files in Pulse_measurements, skipping logs."""
    pulse_dir = Path(pulse_dir)
    if not pulse_dir.is_dir():
        return []
    files: List[Path] = []
    for path in sorted(pulse_dir.glob("*.txt")):
        name_l = path.name.lower()
        if name_l.startswith("tsp_test_log") or name_l == "log.txt":
            continue
        files.append(path)
    return files


def list_solartron_runs(solartron_dir: Path | str) -> List[Path]:
    """
    Run folders under Solartron_1260 that contain origin_data/.
    """
    solartron_dir = Path(solartron_dir)
    if not solartron_dir.is_dir():
        return []
    runs: List[Path] = []
    for child in sorted(solartron_dir.iterdir()):
        if not child.is_dir():
            continue
        if (child / "origin_data").is_dir():
            runs.append(child)
    return runs


def parse_device_from_path(path: Path | str) -> Optional[Tuple[str, str, str]]:
    """
    From a path under .../{sample}/{section}/{device}/..., return
    (sample_name, section, device) when layout matches.
    """
    path = Path(path).resolve()
    parts = path.parts
    for i in range(len(parts) - 2):
        section, device = parts[i + 1], parts[i + 2]
        if len(section) == 1 and section.isalpha() and device.isdigit():
            sample = parts[i]
            return sample, section, device
    return None
