## Moku:Go Laser Controller

Classes `MonkuGoController` and `LaserFunctionGenerator` provide a clean API to drive laser pulses with Moku:Go.

### Why two instruments?
- Pulse-based methods use WaveformGenerator with `type='Pulse'` for the sharpest edges (≈16 ns min width/edge).
- Binary bit patterns use ArbitraryWaveformGenerator (AWG) LUTs for arbitrary sequences like `10110011`.

### Installation
Ensure the Moku Python SDK is installed and your device IP is reachable.

### Quickstart
```python
from Equipment_Classes.Moku.laser_controller import MonkuGoController, LaserFunctionGenerator

ctrl = MonkuGoController('192.168.0.45')
laser = LaserFunctionGenerator(ctrl, channel=1)

# Single 16 ns pulse, 200 ns period (one cycle)
laser.send_single_pulse(voltage_high=1.0, pulse_width=16e-9, edge_time=16e-9, period=200e-9)

# Pulse train: 50 ns width, 200 ns period, 16 ns edges, 100 pulses
laser.send_pulse_train(voltage_high=1.2, pulse_width=50e-9, period=200e-9, edge_time=16e-9, count=100)

# Voltage sweep: 0.5V → 2.0V in 4 steps, 20 pulses per step
laser.send_voltage_sweep_pulses(
    voltage_start=0.5,
    voltage_stop=2.0,
    steps=4,
    pulses_per_step=20,
    pulse_width=50e-9,
    period=200e-9,
    edge_time=16e-9,
    dwell_between_steps_s=0.1,
)

# Binary pattern at 100 ns/bit (AWG LUT)
laser.send_binary_pattern('10110011', bit_period=100e-9, high_voltage=1.0, samples_per_bit=10)

# Stop everything (best-effort)
laser.stop_all()
```

### Pulse sketches (approximate)

- Single pulse (width=50 ns, edge=16 ns):
```
0V ──╭──────╮────
     │      │
1V   ╰──────╯
     ^16ns  ^50ns (flat)
```

- Pulse train (period=200 ns, width=50 ns, edge=16 ns):
```
0V ──╭──╮────╭──╮────╭──╮──
     │  │    │  │    │  │
1V   ╰──╯    ╰──╯    ╰──╯
     <- 200 ns ->
```

- Binary pattern (bit=100 ns, samples_per_bit=10):
```
0V ──╭╮────╭╮╭╮────────╭╮╭╮
     ││    ││││        ││││
1V   ╰╯    ╰╯╰╯        ╰╯╰╯   (1=high, 0=low)
```

### Design notes
- Pulse methods use hardware Pulse engine for minimal achievable rise/fall (set `edge_time`, clamped to ≈16 ns).
- Binary LUT method auto-picks an AWG sample rate label and playback frequency.
- All timing/voltage parameters are explicit so you can sweep for device/laser tuning.


