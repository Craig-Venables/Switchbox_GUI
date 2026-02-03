"""
Secure Messaging (Telegram) Config Loader
==========================================

Loads Telegram bot config from file with security best practices:
- Prefer messaging_data.local.json (gitignored) over messaging_data.json
- Optional MESSAGING_CONFIG_PATH env var for custom path
- Optional per-profile env overrides: TELEGRAM_TOKEN_<NAME>, TELEGRAM_CHATID_<NAME>

Never log or expose tokens. Use messaging_data.json.example for structure only.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict

# Project root: gui/messaging_config.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_JSON_DIR = _PROJECT_ROOT / "Json_Files"

# Default filenames: local (gitignored) first, then fallback
_LOCAL_FILENAME = "messaging_data.local.json"
_DEFAULT_FILENAME = "messaging_data.json"


def _env_key(name: str) -> str:
    """Sanitize profile name for env var: 'Craig' -> 'CRAIG', 'My Bot' -> 'MY_BOT'."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip()).strip("_")
    return s.upper() if s else ""


def get_messaging_config_path() -> Path:
    """
    Resolve path to messaging config file.
    Order: MESSAGING_CONFIG_PATH env -> messaging_data.local.json -> messaging_data.json.
    """
    env_path = os.environ.get("MESSAGING_CONFIG_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_absolute():
            return p
        return _PROJECT_ROOT / p
    local = _JSON_DIR / _LOCAL_FILENAME
    if local.exists():
        return local
    return _JSON_DIR / _DEFAULT_FILENAME


def load_messaging_config() -> Dict[str, Dict[str, str]]:
    """
    Load messaging profiles from config file and apply env overrides.

    Returns:
        Dict mapping profile name -> {"token": str, "chatid": str}.
        Empty dict if file missing or invalid. Never returns or logs secrets.
    """
    config_path = get_messaging_config_path()
    data: Dict = {}
    try:
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data = raw
    except FileNotFoundError:
        pass
    except Exception as exc:
        # Log without including path that might reveal user dir; do not log file content
        print(f"[Messaging] Failed to load config: {type(exc).__name__}")

    result: Dict[str, Dict[str, str]] = {}
    for raw_name, raw_info in (data or {}).items():
        if not isinstance(raw_info, dict):
            continue
        name = str(raw_name).strip()
        if not name:
            continue
        token = str(raw_info.get("token", "") or "").strip()
        chatid = str(raw_info.get("chatid", raw_info.get("chat_id", "")) or "").strip()

        # Env overrides (allow secrets from env only)
        env_key_name = _env_key(name)
        if env_key_name:
            token = os.environ.get(f"TELEGRAM_TOKEN_{env_key_name}", token).strip()
            chatid = os.environ.get(f"TELEGRAM_CHATID_{env_key_name}", chatid).strip()

        result[name] = {"token": token, "chatid": chatid}

    return result
