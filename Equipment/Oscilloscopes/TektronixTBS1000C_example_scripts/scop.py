#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Adjust import to your project structure
from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C

def main():
    if len(sys.argv) < 2:
        print("Usage: python dump_scope_settings.py <VISA_RESOURCE> [output.json]")
        print("Example: python dump_scope_settings.py USB0::0x0699::0x03C4::C023684::INSTR")
        sys.exit(1)

    resource = sys.argv[1]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scope_settings.json")

    scope = TektronixTBS1000C(resource=resource, timeout_ms=30000)

    if not scope.connect():
        print("Failed to connect to oscilloscope.")
        sys.exit(1)

    try:
        settings = {
            "idn": scope.idn(),
            "timebase": {
                "scale_s_div": scope.get_timebase_scale(),
                "position_s": getattr(scope, "get_timebase_position", lambda: None)()
            },
            "record_length": scope.query("HOR:RECO?"),
            "channel1": {
                "scale_v_div": scope.get_channel_scale(1),
                "offset_v": scope.get_channel_offset(1),
                "coupling": scope.query("CH1:COUP?"),
                "probe_atten": scope.query("CH1:PROBE?"),
                "display": scope.query("SEL:CH1?")
            },
            "channel2": {
                "scale_v_div": scope.get_channel_scale(2),
                "offset_v": scope.get_channel_offset(2),
                "coupling": scope.query("CH2:COUP?"),
                "probe_atten": scope.query("CH2:PROBE?"),
                "display": scope.query("SEL:CH2?")
            },
            "trigger": {
                "mode": scope.get_trigger_mode(),
                "source": scope.query("TRIG:A:EDGE:SOU?"),
                "level_v": scope.get_trigger_level(),
                "slope": scope.query("TRIG:A:EDGE:SLO?"),
                "holdoff_s": scope.query("TRIG:A:HOLD?")
            },
            "acquisition": {
                "mode": scope.query("ACQ:MOD?"),
                "stop_after": scope.query("ACQ:STOPA?"),
                "state": scope.query("ACQ:STATE?")
            }
        }

        out_path.write_text(json.dumps(settings, indent=2))
        print(f"Saved scope settings to {out_path.resolve()}")

    finally:
        scope.disconnect()

if __name__ == "__main__":
    main()