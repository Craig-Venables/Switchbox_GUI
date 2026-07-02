"""Telegram bot setup and quick-scan notifications for SampleGUI."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PIL import Image, ImageDraw

from gui.sample_gui.config import resolve_default_save_root

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class TelegramController:
    """Load bots, capture scan canvas, and send completion notifications."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    def load_bots(self) -> None:
        from gui.messaging_config import load_messaging_config

        gui = self.gui
        gui.telegram_bots = {}
        for name, info in load_messaging_config().items():
            token = (info.get("token") or "").strip()
            chatid = (info.get("chatid") or "").strip()
            if token and chatid:
                gui.telegram_bots[name] = {"token": token, "chatid": chatid}

    def update_bot(self) -> None:
        gui = self.gui
        if not gui.telegram_enabled.get():
            gui.telegram_bot = None
            return

        bot_name = gui.telegram_bot_name_var.get().strip()
        if not bot_name or bot_name not in gui.telegram_bots:
            gui.telegram_bot = None
            return

        bot_config = gui.telegram_bots[bot_name]
        token = bot_config.get("token", "").strip()
        chat_id = bot_config.get("chatid", "").strip()
        if not token or not chat_id:
            gui.telegram_bot = None
            return

        try:
            from Notifications import TelegramBot

            gui.telegram_bot = TelegramBot(token, chat_id)
            gui._log_quick_scan(f"Telegram bot '{bot_name}' initialized")
        except Exception as exc:
            gui.telegram_bot = None
            gui._log_quick_scan(f"Failed to initialize Telegram bot '{bot_name}': {exc}")

    def capture_canvas_image(self) -> Optional[Path]:
        gui = self.gui
        if not hasattr(gui, "quick_scan_base_image") or gui.quick_scan_base_image is None:
            return None

        try:
            canvas_image = gui.quick_scan_base_image.copy()
            if canvas_image.mode != "RGBA":
                canvas_image = canvas_image.convert("RGBA")

            overlay = Image.new("RGBA", canvas_image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            orig_width, orig_height = (
                gui.original_image.size
                if hasattr(gui, "original_image") and gui.original_image
                else (600, 500)
            )
            quick_scan_width, quick_scan_height = 600, 500
            scale_x = orig_width / quick_scan_width
            scale_y = orig_height / quick_scan_height

            if gui.show_quick_scan_overlay.get() and hasattr(gui, "device_mapping"):
                for device, bounds in gui.device_mapping.items():
                    current = gui.quick_scan_results.get(device)
                    if current is None or (isinstance(current, float) and math.isnan(current)):
                        continue
                    x_min = int(min(bounds["x_min"] / scale_x, bounds["x_max"] / scale_x))
                    x_max = int(max(bounds["x_min"] / scale_x, bounds["x_max"] / scale_x))
                    y_min = int(min(bounds["y_min"] / scale_y, bounds["y_max"] / scale_y))
                    y_max = int(max(bounds["y_min"] / scale_y, bounds["y_max"] / scale_y))
                    if x_min >= x_max or y_min >= y_max:
                        continue
                    x_min = max(0, min(x_min, canvas_image.width - 1))
                    x_max = max(1, min(x_max, canvas_image.width))
                    y_min = max(0, min(y_min, canvas_image.height - 1))
                    y_max = max(1, min(y_max, canvas_image.height))
                    color = gui._current_to_color(current)
                    overlay_color = (
                        int(color[1:3], 16),
                        int(color[3:5], 16),
                        int(color[5:7], 16),
                        128,
                    )
                    draw.rectangle([x_min, y_min, x_max, y_max], fill=overlay_color)

            if gui.show_status_overlay.get() and hasattr(gui, "device_mapping"):
                for device, bounds in gui.device_mapping.items():
                    manual_status = gui.device_status.get(device, {}).get("manual_status", "undefined")
                    if manual_status == "undefined":
                        continue
                    x_min = int(min(bounds["x_min"] / scale_x, bounds["x_max"] / scale_x))
                    x_max = int(max(bounds["x_min"] / scale_x, bounds["x_max"] / scale_x))
                    y_min = int(min(bounds["y_min"] / scale_y, bounds["y_max"] / scale_y))
                    y_max = int(max(bounds["y_min"] / scale_y, bounds["y_max"] / scale_y))
                    if x_min >= x_max or y_min >= y_max:
                        continue
                    x_min = max(0, min(x_min, canvas_image.width - 1))
                    x_max = max(1, min(x_max, canvas_image.width))
                    y_min = max(0, min(y_min, canvas_image.height - 1))
                    y_max = max(1, min(y_max, canvas_image.height))
                    if manual_status == "working":
                        overlay_color = (76, 175, 80, 192)
                    elif manual_status == "broken":
                        overlay_color = (244, 67, 54, 192)
                    else:
                        continue
                    draw.rectangle([x_min, y_min, x_max, y_max], fill=overlay_color)

            final_image = Image.alpha_composite(canvas_image, overlay).convert("RGB")
            save_root = resolve_default_save_root()
            if gui.current_device_name:
                device_folder = gui.get_device_folder()
                device_folder.mkdir(parents=True, exist_ok=True)
                image_path = device_folder / f"quick_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            else:
                sample_dir = save_root / gui.sample_type_var.get()
                sample_dir.mkdir(parents=True, exist_ok=True)
                image_path = sample_dir / f"quick_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            final_image.save(image_path, "PNG")
            return image_path
        except Exception as exc:
            gui._log_quick_scan(f"Failed to capture canvas image: {exc}")
            return None

    def send_quick_scan_notification(self, aborted: bool) -> None:
        gui = self.gui
        if not gui.telegram_enabled.get() or gui.telegram_bot is None:
            return

        try:
            sample = gui.sample_type_var.get()
            device_name = gui.current_device_name or "Unknown Device"
            voltage = gui.quick_scan_voltage_var.get()
            status = "Aborted" if aborted else "Complete"
            device_count = len(gui.quick_scan_results)

            working_count = 0
            non_working_count = 0
            for _device, current in gui.quick_scan_results.items():
                if current is None or (isinstance(current, float) and math.isnan(current)):
                    continue
                if current >= gui.quick_scan_threshold:
                    working_count += 1
                else:
                    non_working_count += 1

            def escape_markdown(text: str) -> str:
                for ch in ("_", "*", "[", "]"):
                    text = text.replace(ch, f"\\{ch}")
                return text

            message = (
                f"Quick Scan {status}\n\n"
                f"Device: {escape_markdown(device_name)}\n"
                f"Sample Type: {escape_markdown(sample)}\n"
                f"Voltage: {voltage} V\n"
                f"Threshold: {escape_markdown(f'{gui.quick_scan_threshold:.3e}')} A\n"
                f"Devices Scanned: {device_count}\n"
                f"Working: {working_count}\n"
                f"Non-Working: {non_working_count}"
            )
            gui.telegram_bot.send_message(message)

            image_path = self.capture_canvas_image()
            if image_path and image_path.exists():
                caption = (
                    f"Quick Scan Heat Map - {escape_markdown(device_name)} "
                    f"({escape_markdown(sample)})"
                )
                gui.telegram_bot.send_image(str(image_path), caption)
                gui._log_quick_scan("Sent Telegram notification with image")
            else:
                gui._log_quick_scan("Sent Telegram notification (image capture failed)")
        except Exception as exc:
            gui._log_quick_scan(f"Failed to send Telegram notification: {exc}")
