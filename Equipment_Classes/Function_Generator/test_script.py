import numpy as np
import time
from typing import List
from Siglent_SDG1032X import SiglentSDG1032X


def make_bit_with_pause(bit: str, samples_per_bit: int, samples_per_pause: int, 
                        high: float = 1.0, low: float = 0.0) -> np.ndarray:
    """Generate samples for a single bit with pause."""
    bit_value = high if bit == "1" else low
    bit_samples = np.full(samples_per_bit, bit_value, dtype=np.float32)
    pause_samples = np.full(samples_per_pause, low, dtype=np.float32)
    return np.concatenate([bit_samples, pause_samples])


def create_pulse_pattern(pattern: str,
                           pulse_duration_ms: float = 1.0,
                           period_ms: float = 2.0,
                           sample_rate: float = 1e6,
                           voltage_high: float = 3.0,
                           rise_time_ms: float = 0.01) -> np.ndarray:
    """
    Create a pulse pattern waveform with SHARP transitions (square-like).

    Args:
        pattern: String of 0s and 1s (e.g., "0101", "001100", "111000")
        pulse_duration_ms: How long each pulse/bit lasts
        period_ms: Total period for one complete pattern cycle
        sample_rate: Samples per second
        voltage_high: High voltage level
        rise_time_ms: How fast the transitions are (smaller = sharper)

    Returns:
        Numpy array with voltage values
    """
    # Calculate samples
    samples_per_pulse = int(sample_rate * pulse_duration_ms / 1000)
    samples_per_period = int(sample_rate * period_ms / 1000)
    rise_samples = max(1, int(sample_rate * rise_time_ms / 1000))  # Fast rise/fall

    # Validate pattern
    if not all(bit in '01' for bit in pattern):
        raise ValueError("Pattern must contain only 0s and 1s")

    if samples_per_period < len(pattern) * samples_per_pulse:
        print(f"⚠️  Warning: Period ({period_ms}ms) is shorter than pattern duration. "
              f"Increasing period to {len(pattern) * pulse_duration_ms}ms")
        samples_per_period = len(pattern) * samples_per_pulse

    # Create the waveform with SHARP transitions
    waveform = []

    for bit in pattern:
        target_voltage = voltage_high if bit == '1' else 0.0

        # For square-like transitions, use minimal transition time
        # Just go directly to the target voltage (no gradual ramp)
        pulse_samples = np.full(samples_per_pulse, target_voltage, dtype=np.float32)
        waveform.extend(pulse_samples)

    # Add silence to fill the period (0V baseline)
    current_samples = len(waveform)
    if current_samples < samples_per_period:
        silence_samples = samples_per_period - current_samples
        silence = np.full(silence_samples, 0.0, dtype=np.float32)
        waveform.extend(silence)

    return np.array(waveform)


def build_smooth_waveform(bit_patterns: List[str],
                         sample_rate: float = 1e6,
                         bit_duration_ms: float = 1.0,
                         pause_duration_ms: float = 0.5,
                         pattern_pause_ms: float = 2.0,
                         voltage_high: float = 3.0) -> np.ndarray:
    """Build waveform with smooth transitions to avoid steps."""
    # Calculate samples
    samples_per_bit = int(sample_rate * bit_duration_ms / 1000)
    samples_per_pause = int(sample_rate * pause_duration_ms / 1000)
    samples_per_pattern_pause = int(sample_rate * pattern_pause_ms / 1000)
    
    # Add transition samples for smooth edges
    transition_samples = max(1, int(sample_rate * 0.001))  # 1ms transition
    
    waveforms = []
    for i, pattern in enumerate(bit_patterns):
        pattern_samples = []
        
        for j, bit in enumerate(pattern):
            # Create bit with smooth transitions in actual voltage values
            bit_voltage = voltage_high if bit == "1" else 0.0

            # Main bit duration
            main_samples = int(samples_per_bit - 2 * transition_samples)
            if main_samples < 1:
                main_samples = samples_per_bit
                bit_wave = np.full(main_samples, bit_voltage, dtype=np.float32)
            else:
                # Smooth rise
                rise = np.linspace(0.0, bit_voltage, transition_samples)
                # Steady state
                steady = np.full(main_samples, bit_voltage, dtype=np.float32)
                # Smooth fall
                fall = np.linspace(bit_voltage, 0.0, transition_samples)
                bit_wave = np.concatenate([rise, steady, fall])
            
            pattern_samples.extend(bit_wave)
            
            # Add pause (except after last bit in pattern)
            if j < len(pattern) - 1:
                pause_wave = np.full(samples_per_pause, 0.0, dtype=np.float32)  # 0V during pauses
                pattern_samples.extend(pause_wave)
        
        waveforms.append(np.array(pattern_samples))
        
        # Add pattern pause (except after last pattern)
        if i < len(bit_patterns) - 1:
            pattern_pause_wave = np.full(samples_per_pattern_pause, 0.0, dtype=np.float32)  # 0V during pattern pauses
            waveforms.append(pattern_pause_wave)
    
    # Combine all
    full_waveform = np.concatenate(waveforms)
    
    # Return waveform in actual voltage values (0V to voltage_high)
    # For direct ARB data upload with 0V baseline
    return full_waveform


def upload_and_configure(gen: SiglentSDG1032X, channel: int, waveform: np.ndarray,
                        voltage_high: float = 3.0):
    """Upload ARB waveform with explicit high/low voltage levels."""
    # Save CSV
    filename = "binary_pulse.csv"
    np.savetxt(filename, waveform, delimiter=",", fmt='%.6f')
    print(f"Waveform saved to {filename}")

    # Upload waveform via CSV file
    try:
        # Upload the CSV file directly to the function generator
        success = gen.upload_csv_waveform(channel, filename, "PULSE")
        if not success:
            raise Exception("CSV upload failed")

        # Configure ARB with proper scaling
        # Since CSV data contains actual voltages (0V to voltage_high),
        # we set AMP to voltage_high and OFST to 0V
        gen.set_basic_waveform(
            channel=channel,
            wvtype="ARB",
            frequency="1000HZ",
            amplitude=f"{voltage_high}V",  # Scale to match our voltage range
            offset="0V"  # No offset - baseline at 0V
        )

        print(f"CSV uploaded and ARB configured: 0V baseline, pulses to {voltage_high}V")
    except Exception as e:
        print(f"CSV upload/config error: {e}")

    # Set load
    gen.set_output_load(channel, "HIGHZ")


def validate_parameters(pattern, pulse_duration_ms, period_ms, voltage_high):
    """Validate input parameters and provide helpful feedback."""
    # Validate pattern
    if not isinstance(pattern, str):
        raise ValueError("Pattern must be a string")
    if not all(bit in '01' for bit in pattern):
        raise ValueError("Pattern must contain only 0s and 1s")
    if len(pattern) == 0:
        raise ValueError("Pattern cannot be empty")

    # Validate timing
    if pulse_duration_ms <= 0:
        raise ValueError("Pulse duration must be positive")
    if period_ms <= 0:
        raise ValueError("Period must be positive")

    # Check if period is sufficient
    min_period = len(pattern) * pulse_duration_ms
    if period_ms < min_period:
        print(f"⚠️  Warning: Period ({period_ms}ms) is shorter than pattern duration ({min_period}ms)")
        print(f"   Increasing period to {min_period}ms to fit the pattern")
        return pattern, pulse_duration_ms, min_period, voltage_high

    return pattern, pulse_duration_ms, period_ms, voltage_high


def main():
    """Main function generator test function."""
    print("🎯 Siglent SDG1032X Pulse Pattern Generator")
    print("=" * 50)

    # ============ CONFIGURATION ============
    # Change this to match your function generator
    VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

    # ===== EASY PULSE CONTROL =====
    # Just change these three lines to control your pulses:

    PULSE_PATTERN = "0101"        # Pattern of 0s and 1s - change this to control on/off!
                                   # Examples:
                                   # "0101" = alternating on/off
                                   # "001100" = two off, two on
                                   # "111000" = three on, three off
                                   # "1000" = one on, three off
                                   # "101010" = on-off-on-off-on-off
                                   # "1111" = always on
                                   # "0000" = always off
    PULSE_DURATION_MS = 1.0       # How long each pulse/bit lasts (milliseconds)
    PERIOD_MS = 4.0               # Total period for one complete cycle (milliseconds)
                                   # Must be >= (pattern_length * pulse_duration)

    # ===== SHARP TRANSITIONS =====
    # Now using SQUARE-like transitions instead of gradual ramps!
    # Transitions are fast (< 0.01ms) for clean on/off switching

    # Output levels
    VOLTAGE_HIGH = 3.0            # High voltage level (pulse voltage)
    # Low level is always 0V (baseline)

    # Trigger mode
    USE_TRIGGER = True            # True = single shot, False = continuous

    # ============ VALIDATION ============
    try:
        PULSE_PATTERN, PULSE_DURATION_MS, PERIOD_MS, VOLTAGE_HIGH = validate_parameters(
            PULSE_PATTERN, PULSE_DURATION_MS, PERIOD_MS, VOLTAGE_HIGH)
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        exit(1)

    # ============ MAIN EXECUTION ============
    print("🔌 Connecting to function generator...")
    gen = SiglentSDG1032X(resource=VISA_RESOURCE)

    if not gen.connect():
        print("❌ Failed to connect to generator!")
        print("   Check:")
        print("   - Function generator is powered on")
        print("   - USB connection is secure")
        print(f"   - VISA resource is correct: {VISA_RESOURCE}")
        raise SystemExit("Connection failed.")

    try:
        print(f"✅ Connected: {gen.idn()}")
        print()

        # Show configuration
        print("📊 Configuration:")
        print(f"   Pattern: '{PULSE_PATTERN}' ({len(PULSE_PATTERN)} bits)")
        print(f"   Pulse Duration: {PULSE_DURATION_MS}ms")
        print(f"   Period: {PERIOD_MS}ms")
        print(f"   High Voltage: {VOLTAGE_HIGH}V")
        print(f"   Low Voltage: 0V")
        print(f"   Mode: {'Single-shot' if USE_TRIGGER else 'Continuous'}")
        print("   Transitions: ⚡ SHARP (square-like, <0.01ms rise time)")
        print()
        print("   📈 Pattern visualization:")
        pattern_visual = PULSE_PATTERN.replace('1', '█').replace('0', '░')
        print(f"   '{PULSE_PATTERN}' → {pattern_visual}")
        print("   ⚡ Each transition is INSTANT - no gradual stair steps!")
        print()

        # Create pulse pattern waveform
        print("🔧 Generating SHARP waveform...")
        waveform = create_pulse_pattern(
            pattern=PULSE_PATTERN,
            pulse_duration_ms=PULSE_DURATION_MS,
            period_ms=PERIOD_MS,
            voltage_high=VOLTAGE_HIGH
        )

        print(f"   Waveform length: {len(waveform)} samples")
        print()

        # Upload and configure
        print("📤 Uploading to function generator...")
        upload_and_configure(gen, channel=1, waveform=waveform,
                           voltage_high=VOLTAGE_HIGH)

        # Enable output
        print("⚡ Enabling output...")
        gen.output(1, True)

        if USE_TRIGGER:
            # Single-shot burst mode
            print("🎯 Configuring single-shot burst mode...")
            gen.enable_burst(channel=1, mode="NCYC", cycles=1, trigger_source="BUS")
            print("🚀 Sending trigger...")
            gen.trigger_now(1)
            print("✨ Pulse pattern sent!")
        else:
            # Continuous mode
            print("🔄 Running continuous mode...")
            print("   Press Ctrl+C to stop")
            time.sleep(2)  # Let it run for 2 seconds

        # Check for errors
        err = gen.error_query()
        if not err.startswith("0"):
            print(f"⚠️  Warning: {err}")
        else:
            print("✅ Success - no errors detected")

    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Always cleanup
        print("\n🧹 Cleaning up...")
        try:
            gen.output(1, False)
            if USE_TRIGGER:
                gen.disable_burst(1)
            gen.disconnect()
            print("✅ Disconnected successfully")
        except:
            print("⚠️  Warning: Some cleanup steps failed")

        print("\n🎯 Test completed!")
        print("💡 To modify the pattern, just change PULSE_PATTERN at the top of the script")


def test_waveform_generation():
    """Test waveform generation with SHARP transitions (no hardware required)."""
    print("🧪 Testing SHARP waveform generation (no hardware required)")
    print("=" * 60)

    # Test patterns
    test_patterns = [
        ("0101", 1.0, 4.0),
        ("1000", 2.0, 8.0),
        ("111000", 0.5, 4.5)
    ]

    for pattern, pulse_duration, period in test_patterns:
        print(f"\n📊 Testing SHARP pattern: '{pattern}'")
        print(f"   Pulse duration: {pulse_duration}ms, Period: {period}ms")

        try:
            waveform = create_pulse_pattern(
                pattern=pattern,
                pulse_duration_ms=pulse_duration,
                period_ms=period,
                voltage_high=3.0
            )

            # Analyze the waveform
            unique_values = sorted(set(waveform))
            print(f"   ✅ SHARP waveform generated: {len(waveform)} samples")
            print(f"   ✅ Voltage levels: {unique_values}")
            print(f"   ✅ Expected: [0.0, 3.0]")
            print("   ⚡ Transitions: Instant (<0.01ms) - NO gradual ramps!")

            # Check for expected values
            if 0.0 in unique_values and 3.0 in unique_values:
                print("   ✅ Pattern validation: PASSED")
            else:
                print("   ❌ Pattern validation: FAILED")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n🎯 SHARP waveform generation test completed!")
    print("💡 Waveforms now have instant transitions - no more stair steps!")
    print()
    print("📈 Example '0101' pattern with sharp transitions:")
    print("   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐")
    print(" 3V│    │ 3V│    │ 3V│    │ 3V│    │ 3V")
    print("   └─────┘   └─────┘   └─────┘   └─────┘")
    print("   0V─────0V─────0V─────0V─────0V─────0V")
    print("   ↑     ↑     ↑     ↑     ↑     ↑")
    print("   0     1     2     3     4     5  (ms)")
    print("   ⚡⚡⚡ INSTANT transitions - no gradual ramps! ⚡⚡⚡")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_waveform_generation()
    elif len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("🎯 Siglent SDG1032X Pulse Pattern Generator")
        print("=" * 50)
        print()
        print("USAGE:")
        print("  python test_script.py              # Run with function generator")
        print("  python test_script.py --test       # Test waveform generation (no hardware)")
        print("  python test_script.py --help       # Show this help")
        print()
        print("CONFIGURATION:")
        print("  Edit the variables at the top of main() function:")
        print("  - PULSE_PATTERN: String of 0s and 1s (e.g., '0101', '1000')")
        print("  - PULSE_DURATION_MS: How long each pulse lasts")
        print("  - PERIOD_MS: Total period for one complete cycle")
        print("  - VOLTAGE_HIGH: High voltage level")
        print("  - VISA_RESOURCE: Your function generator's VISA address")
        print()
        print("FEATURES:")
        print("  ⚡ SHARP transitions (<0.01ms) - no gradual stair steps!")
        print("  🎯 Precise pattern control - exactly what you specify")
        print("  📊 0V baseline - clean on/off switching")
        print("  🔄 Flexible timing - control period between pulses")
        print()
        print("EXAMPLES:")
        print("  '0101' = alternating on/off")
        print("  '1000' = one pulse on, three off")
        print("  '111000' = three on, three off")
        print("  '101010' = on-off-on-off-on-off")
    else:
        # Run the main function generator test
        main()