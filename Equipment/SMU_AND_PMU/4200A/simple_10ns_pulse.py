"""
Simple 10ns Pulse Example - Direct translation from PMU_10ns_Pulse_Example.c

Based on Keithley's C example. Just generates continuous 10ns pulses.
No fancy validation, no tests - just the basic example.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.SMU_AND_PMU.ProxyClass import Proxy


class PMU_10ns_Simple:
    """Bare-bones 10ns pulse generator following the C example exactly."""
    
    def __init__(self, ip="192.168.0.10", port=8888, card="PMU1"):
        self.ip = ip
        self.port = port
        self.card = card
        
        # Connect
        self.lpt = Proxy(ip, port, "lpt")
        self.param = Proxy(ip, port, "param")
        
        self.lpt.initialize()
        self.lpt.tstsel(1)
        self.lpt.devint()
        
        self.card_id = self.lpt.getinstid(card)
        print(f"Connected to {card}")
    
    def run_10ns_pulse(self, channel=1):
        """
        Generate continuous 10ns pulses - direct from C example.
        
        Settings from C example:
        - Load: 50 ohm
        - Current Limit: 200 mA
        - Rise/Fall: 10 ns
        - Delay: 0 s
        - Voltage Range: 5V
        - Low Voltage: -1V
        - High Voltage: +1V
        - Period: 20 ns
        - Width: 10 ns
        """
        ch = int(channel)
        
        # Pulse Settings - SLOWED DOWN to see square wave clearly
        setLoad = 50.0
        setCurrent = 0.2
        setRise = 20e-9      # 100 ns (slower edges)
        setFall = 20e-9      # 100 ns (slower edges)
        setDelay = 0.0
        setRange = 5.0
        setVLow = 0
        setVHigh = 1
        setPeriod = 500e-9      # 1 ms = 1 kHz (MUCH slower, easy to see)
        setWidth = 250e-9     # 500 µs pulse width
        
        # Set RPM to pulse mode (does nothing if no RPM)
        try:
            self.lpt.rpm_config(self.card_id, ch, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
        except:
            pass
        
        # Set to 2-level pulse mode
        self.lpt.pg2_init(self.card_id, 0)
        
        # Reset to defaults
        self.lpt.pulse_init(self.card_id)
        
        # Configure pulse (following C example order)
        self.lpt.pulse_load(self.card_id, ch, setLoad)
        self.lpt.pulse_current_limit(self.card_id, ch, setCurrent)
        self.lpt.pulse_rise(self.card_id, ch, setRise)
        self.lpt.pulse_fall(self.card_id, ch, setFall)
        self.lpt.pulse_delay(self.card_id, ch, setDelay)
        self.lpt.pulse_range(self.card_id, ch, setRange)
        self.lpt.pulse_vlow(self.card_id, ch, setVLow)
        self.lpt.pulse_vhigh(self.card_id, ch, setVHigh)
        self.lpt.pulse_period(self.card_id, setPeriod)
        self.lpt.pulse_width(self.card_id, ch, setWidth)
        
        # Output the pulse
        self.lpt.pulse_output(self.card_id, ch, 1)  # Turn ON
        self.lpt.pulse_trig(self.card_id, 1)        # Continuous trigger
        
        print(f"10ns pulses running on channel {ch}")
        print("Press Ctrl+C to stop")
    
    def stop(self, channel=1):
        """Stop pulse output."""
        self.lpt.pulse_output(self.card_id, int(channel), 0)
        print("Stopped")
    
    def cleanup(self):
        """Clean shutdown."""
        try:
            self.lpt.pulse_output(self.card_id, 1, 0)
            self.lpt.pulse_output(self.card_id, 2, 0)
        except:
            pass
        try:
            self.lpt.tstdsl()
            self.lpt.devint()
        except:
            pass


if __name__ == "__main__":
    # Simple usage
    pmu = PMU_10ns_Simple(ip="192.168.0.10", port=8888, card="PMU1")
    
    try:
        pmu.run_10ns_pulse(channel=1)
        
        # Run until Ctrl+C
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nStopping...")
        pmu.stop(1)
        pmu.cleanup()

