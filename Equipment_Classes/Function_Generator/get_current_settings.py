import sys
import json
from pathlib import Path
import argparse
from typing import Dict, Any


# Ensure project root on sys.path so absolute imports work when run as a script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment_Classes.Function_Generator.Siglent_SDG1032X import SiglentSDG1032X


def _parse_key_value_list(raw: str) -> Dict[str, Any]:
    """Parse comma-separated KV list like 'WVTP,PULSE,FRQ,1KHZ,AMP,1VPP' to dict.

    Returns the raw strings; caller can post-process values if needed.
    """
    result: Dict[str, Any] = {}
    if not raw:
        return result
    # Some responses may include leading/trailing quotes or newlines
    text = raw.strip().strip("\"'")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    # Pair up keys and values
    for i in range(0, len(parts) - 1, 2):
        key = parts[i].upper()
        val = parts[i + 1]
        result[key] = val
    return result


def get_channel_settings(resource: str, channel: int) -> Dict[str, Any]:
    gen = SiglentSDG1032X(resource=resource)
    if not gen.connect():
        raise RuntimeError("Failed to connect to function generator")

    try:
        idn = gen.idn()

        # Basic waveform and burst settings
        bswv_raw = gen.read_basic_waveform(channel)
        btwv_raw = gen.read_burst(channel)

        # Output state
        try:
            outp_state = gen.query(f"C{channel}:OUTP?")
        except Exception as e:
            outp_state = f"ERR {e}"

        # ARB waveform status (if supported)
        try:
            arwv_raw = gen.query(f"C{channel}:ARWV?")
        except Exception:
            arwv_raw = None

        # Parse to dictionaries
        bswv = _parse_key_value_list(bswv_raw) if isinstance(bswv_raw, str) else {"RAW": bswv_raw}
        btwv = _parse_key_value_list(btwv_raw) if isinstance(btwv_raw, str) else {"RAW": btwv_raw}

        settings: Dict[str, Any] = {
            "idn": idn,
            "channel": int(channel),
            "output": outp_state,
            "bswv": bswv,
            "btwv": btwv,
        }
        if arwv_raw is not None:
            settings["arwv"] = arwv_raw

        # Last error, if any
        try:
            settings["error"] = gen.error_query()
        except Exception:
            pass

        return settings
    finally:
        try:
            gen.disconnect()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Read current channel settings from Siglent SDG1032X")
    parser.add_argument("--resource", required=True, help="VISA resource (e.g. TCPIP0::192.168.1.2::INSTR)")
    parser.add_argument("--channel", type=int, default=1, help="Channel number (1 or 2)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    settings = get_channel_settings(args.resource, int(args.channel))
    if args.pretty:
        print(json.dumps(settings, indent=2))
    else:
        print(json.dumps(settings, separators=(",", ":")))


if __name__ == "__main__":
    main()

#python Equipment_Classes/Function_Generator/get_current_settings.py --resource USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR --channel 1 --pretty
