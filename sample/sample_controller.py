"""Shared sample-selection controller usable by Tk or Qt front-ends."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

from Equipment.Multiplexers.Multiplexer_10_OUT.Multiplexer_Class import MultiplexerController
from Equipment.multiplexer_manager import MultiplexerManager

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "Json_Files"

# Default sample configuration replicated from the legacy Tk GUI
DEFAULT_SAMPLE_CONFIG: Dict[str, Dict[str, Any]] = {
    "Cross_bar": {
        "sections": {
            "A": True,
            "B": True,
            "C": False,
            "D": True,
            "E": True,
            "F": False,
            "G": True,
            "H": True,
            "I": True,
            "J": True,
            "K": True,
            "L": True,
        },
        "devices": [str(i) for i in range(1, 11)],
    },
    "Device_Array_10": {
        "sections": {"A": True},
        "devices": [str(i) for i in range(1, 11)],
    },
}


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_device_maps() -> Dict[str, Dict[str, Any]]:
    mapping_path = CONFIG_DIR / "mapping.json"
    return _load_json(mapping_path)


def load_pin_mapping(filename: Optional[str] = None) -> Dict[str, Any]:
    mapping_path = CONFIG_DIR / "pin_mapping.json" if filename is None else Path(filename)
    try:
        with mapping_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        print(f"[SampleController] JSON file not found: {mapping_path}")
        return {}
    except json.JSONDecodeError:
        print("[SampleController] JSON mapping file malformed.")
        return {}


class VarWrapper:
    """Lightweight replacement for Tkinter Variable classes."""

    def __init__(self, value: Any = None) -> None:
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value


class SampleController:
    """Core sample-selection state machine shared by GUI implementations.

    Provides a superset of the legacy Tk `SampleGUI` interface so existing
    workflows (including `MeasurementGUI`) can interact with either the Tk
    widget hierarchy or this controller interchangeably.
    """

    def __init__(
        self,
        *,
        sample_config: Optional[Dict[str, Dict[str, Any]]] = None,
        device_maps: Optional[Dict[str, Dict[str, Any]]] = None,
        pin_mapping: Optional[Dict[str, Any]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.sample_config = sample_config or DEFAULT_SAMPLE_CONFIG
        self.device_maps = device_maps or load_device_maps()
        self.pin_mapping = pin_mapping or load_pin_mapping()
        self._logger: Callable[[str], None] = logger or (lambda msg: None)

        self.sample_name: str = ""
        self.sample_type: str = next(iter(self.sample_config))
        self.section: str = self._default_section(self.sample_type)

        self.current_device_map: str = self.sample_type
        self.device_mapping: Dict[str, Any] = self.device_maps.get(self.current_device_map, {})
        self.device_list: List[str] = list(self.device_mapping.keys())

        self.current_index: int = 0
        self.selected_devices: Set[str] = set(self.device_list)
        self.selected_indices: List[int] = list(range(len(self.device_list)))

        self.device_var: VarWrapper = VarWrapper(self.device_list[0] if self.device_list else "")

        self.multiplexer_type: str = "Pyswitchbox"
        self.mpx_manager: Optional[MultiplexerManager] = None
        self._multiplexer_controller: Optional[MultiplexerController] = None

        # Instantiate default multiplexer (if available)
        self.configure_multiplexer(self.multiplexer_type)

    # ------------------------------------------------------------------ #
    # Configuration helpers
    # ------------------------------------------------------------------ #
    def _default_section(self, sample_type: str) -> str:
        sections = self.sample_config.get(sample_type, {}).get("sections", {})
        for name, enabled in sections.items():
            if enabled:
                return name
        return ""

    def set_logger(self, logger: Callable[[str], None]) -> None:
        self._logger = logger

    def configure_multiplexer(self, mux_type: str) -> None:
        """Initialise the multiplexer adapter."""
        self.multiplexer_type = mux_type
        try:
            if mux_type == "Pyswitchbox":
                self.mpx_manager = MultiplexerManager.create("Pyswitchbox", pin_mapping=self.pin_mapping)
                self._log("[SampleController] Pyswitchbox multiplexer initialised.")
            elif mux_type == "Electronic_Mpx":
                try:
                    controller = MultiplexerController(simulation_mode=False)
                except Exception as exc:  # pragma: no cover - hardware path
                    self._log(f"[SampleController] Electronic_Mpx hardware unavailable ({exc}); using simulation.")
                    controller = MultiplexerController(simulation_mode=True)
                self._multiplexer_controller = controller
                self.mpx_manager = MultiplexerManager.create("Electronic_Mpx", controller=controller)
                self._log("[SampleController] Electronic_Mpx multiplexer initialised.")
            else:
                self.mpx_manager = None
                self._log(f"[SampleController] Unknown multiplexer type '{mux_type}'.")
        except Exception as exc:  # pragma: no cover - hardware path
            self.mpx_manager = None
            self._log(f"[SampleController] Multiplexer initialisation failed: {exc}")

    # ------------------------------------------------------------------ #
    # Sample / device management
    # ------------------------------------------------------------------ #
    def set_sample_type(self, sample_type: str) -> List[str]:
        if sample_type not in self.sample_config:
            raise ValueError(f"Unknown sample type '{sample_type}'.")
        self.sample_type = sample_type
        self.section = self._default_section(sample_type)
        self.update_device_map(sample_type)
        return self.get_sections(sample_type)

    def get_sample_types(self) -> List[str]:
        return list(self.sample_config.keys())

    def get_sections(self, sample_type: Optional[str] = None) -> List[str]:
        sample_type = sample_type or self.sample_type
        sections = self.sample_config.get(sample_type, {}).get("sections", {})
        return [name for name, enabled in sections.items() if enabled]

    def set_section(self, section: str) -> None:
        self.section = section

    def update_device_map(self, map_name: str) -> None:
        mapping = self.device_maps.get(map_name, {})
        self.current_device_map = map_name
        self.device_mapping = mapping
        self.device_list = list(mapping.keys())
        self.current_index = 0
        self.device_var.set(self.device_list[0] if self.device_list else "")
        self.replace_selection(self.device_list)

    def replace_selection(self, device_names: Iterable[str]) -> None:
        self.selected_devices = set(device_names)
        self.selected_indices = [
            idx for idx, name in enumerate(self.device_list) if name in self.selected_devices
        ]
        if not self.selected_indices and self.device_list:
            self.selected_indices = [0]
            self.selected_devices = {self.device_list[0]}

    def select_device(self, device_name: str) -> None:
        if device_name not in self.device_list:
            return
        idx = self.device_list.index(device_name)
        if idx not in self.selected_indices:
            self.selected_indices.append(idx)
            self.selected_indices.sort()
        self.selected_devices.add(device_name)

    def deselect_device(self, device_name: str) -> None:
        if device_name in self.selected_devices:
            self.selected_devices.remove(device_name)
        idx = self.device_list.index(device_name) if device_name in self.device_list else -1
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        if not self.selected_indices and self.device_list:
            self.selected_indices = [0]
            self.selected_devices = {self.device_list[0]}

    def toggle_device(self, device_name: str) -> None:
        if device_name in self.selected_devices:
            self.deselect_device(device_name)
        else:
            self.select_device(device_name)

    def select_all(self) -> None:
        self.replace_selection(self.device_list)

    def clear_selection(self) -> None:
        self.selected_devices.clear()
        self.selected_indices.clear()

    # ------------------------------------------------------------------ #
    # Device iteration helpers
    # ------------------------------------------------------------------ #
    @property
    def current_device_name(self) -> str:
        if not self.device_list:
            return ""
        return self.device_list[self.current_index]

    def set_current_device(self, device_name: str) -> None:
        if device_name not in self.device_list:
            return
        self.current_index = self.device_list.index(device_name)
        self.device_var.set(device_name)

    def get_selected_devices(self) -> List[str]:
        return [self.device_list[i] for i in self.selected_indices]

    def next_device(self) -> str:
        if not self.selected_indices:
            self._log("[SampleController] No devices selected.")
            return self.current_device_name

        if self.current_index in self.selected_indices:
            idx_in_selected = self.selected_indices.index(self.current_index)
            idx_in_selected = (idx_in_selected + 1) % len(self.selected_indices)
            self.current_index = self.selected_indices[idx_in_selected]
        else:
            self.current_index = self.selected_indices[0]

        device = self.current_device_name
        self.device_var.set(device)
        self._log(f"[SampleController] Next device: {device}")
        return device

    def previous_device(self) -> str:
        if not self.selected_indices:
            self._log("[SampleController] No devices selected.")
            return self.current_device_name

        if self.current_index in self.selected_indices:
            idx_in_selected = self.selected_indices.index(self.current_index)
            idx_in_selected = (idx_in_selected - 1) % len(self.selected_indices)
            self.current_index = self.selected_indices[idx_in_selected]
        else:
            self.current_index = self.selected_indices[0]

        device = self.current_device_name
        self.device_var.set(device)
        self._log(f"[SampleController] Previous device: {device}")
        return device

    # ------------------------------------------------------------------ #
    # Hardware routing
    # ------------------------------------------------------------------ #
    def change_relays(self) -> bool:
        """Route the multiplexer to the currently selected device."""
        device = self.current_device_name
        if not device:
            self._log("[SampleController] No device available to route.")
            return False

        if device not in self.selected_devices:
            self._log(f"[SampleController] Warning: {device} not selected; routing anyway.")

        if self.mpx_manager is None:
            self._log("[SampleController] Multiplexer manager not initialised.")
            return False

        success = False
        try:
            success = bool(self.mpx_manager.route_to_device(device, self.current_index))
        except Exception as exc:  # pragma: no cover - hardware path
            self._log(f"[SampleController] Multiplexer routing failed: {exc}")
            success = False

        if success:
            self._log(f"[SampleController] Routed to {device}.")
        else:
            self._log(f"[SampleController] Failed to route to {device}.")

        return success

    # ------------------------------------------------------------------ #
    # Convenience helpers for measurement GUI
    # ------------------------------------------------------------------ #
    def ensure_selection(self) -> Sequence[str]:
        selected = self.get_selected_devices()
        if not selected and self.device_list:
            selected = [self.device_list[self.current_index]]
            self.select_device(selected[0])
        return selected

    def apply_measurement_selection(self, devices: Iterable[str]) -> None:
        self.replace_selection(devices)
        if devices:
            first = next(iter(devices))
            self.set_current_device(first)

    def set_sample_name(self, name: str) -> None:
        self.sample_name = name

    def _log(self, message: str) -> None:
        try:
            self._logger(message)
        except Exception:
            pass


