import time
from Siglent_SDG1032X import SiglentSDG1032X

def main():
    """Simple test script for experimenting with SDG1032X commands."""
    print("🎯 Simple SDG1032X Command Tester")
    print("=" * 40)

    # ============ CONFIGURATION ============
    VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"
    CHANNEL = 1
    
    # ===== EASY COMMAND VARIABLES =====
    # Change these to experiment with different commands
    
    # Basic waveform settings
    WAVEFORM_TYPE = "ARB"          # Options: "SINE", "SQUARE", "RAMP", "PULSE", "ARB", "DC"
    FREQUENCY = "1000HZ"           # Frequency in Hz (e.g., "1000HZ", "1KHZ", "1MHZ")
    AMPLITUDE = "3V"               # Amplitude (e.g., "3V", "5V", "1.5V")
    OFFSET = "0V"                  # Offset voltage (e.g., "0V", "1V", "-1V")
    
    # ARB specific settings
    ARB_WAVEFORM_NAME = "PULSE"    # Name for ARB waveform
    ARB_INDEX = 0                  # Index for ARB waveform (0-63)
    
    # Burst settings
    BURST_MODE = "NCYC"            # "NCYC" = number of cycles, "INF" = infinite
    BURST_CYCLES = 1               # Number of cycles for burst mode
    TRIGGER_SOURCE = "BUS"         # "BUS", "EXT", "MAN"
    
    # Output settings
    OUTPUT_STATE = True            # True = ON, False = OFF
    OUTPUT_LOAD = "HIGHZ"          # "HIGHZ", "50", "75", "100", "150", "200", "600"
    
    # ============ MAIN EXECUTION ============
    print("🔌 Connecting to function generator...")
    gen = SiglentSDG1032X(resource=VISA_RESOURCE)

    if not gen.connect():
        print("❌ Failed to connect to generator!")
        print(f"   VISA Resource: {VISA_RESOURCE}")
        return

    try:
        print(f"✅ Connected: {gen.idn()}")
        print()
        
        # Show current configuration
        print("📊 Current Configuration:")
        print(f"   Channel: {CHANNEL}")
        print(f"   Waveform: {WAVEFORM_TYPE}")
        print(f"   Frequency: {FREQUENCY}")
        print(f"   Amplitude: {AMPLITUDE}")
        print(f"   Offset: {OFFSET}")
        print(f"   Output: {'ON' if OUTPUT_STATE else 'OFF'}")
        print(f"   Load: {OUTPUT_LOAD}")
        print()

        # ===== SEND COMMANDS =====
        print("📤 Sending commands...")
        
        # 1. Set basic waveform
        print(f"1. Setting basic waveform: {WAVEFORM_TYPE}")
        gen.set_basic_waveform(
            channel=CHANNEL,
            wvtype=WAVEFORM_TYPE,
            frequency=FREQUENCY,
            amplitude=AMPLITUDE,
            offset=OFFSET
        )
        
        # 2. Set output load
        print(f"2. Setting output load: {OUTPUT_LOAD}")
        gen.set_output_load(CHANNEL, OUTPUT_LOAD)
        
        # 3. If ARB mode, set ARB waveform
        if WAVEFORM_TYPE == "ARB":
            print(f"3. Setting ARB waveform: {ARB_WAVEFORM_NAME} (index {ARB_INDEX})")
            gen.set_arb_waveform(channel=CHANNEL, waveform_name=ARB_WAVEFORM_NAME, index=ARB_INDEX)
        
        # 4. Enable burst mode
        print(f"4. Enabling burst mode: {BURST_MODE}, {BURST_CYCLES} cycles")
        gen.enable_burst(
            channel=CHANNEL,
            mode=BURST_MODE,
            cycles=BURST_CYCLES,
            trigger_source=TRIGGER_SOURCE
        )
        
        # 5. Enable output
        print(f"5. Enabling output: {OUTPUT_STATE}")
        gen.output(CHANNEL, OUTPUT_STATE)
        
        print("✅ All commands sent successfully!")
        print()
        
        # 6. Send trigger
        print("🚀 Sending trigger...")
        gen.trigger_now(CHANNEL)
        print("✨ Trigger sent!")
        
        # Check for errors
        err = gen.error_query()
        if not err.startswith("0"):
            print(f"⚠️  Warning: {err}")
        else:
            print("✅ No errors detected")
            
        # Wait a moment to see the output
        print("\n⏳ Waiting 3 seconds to observe output...")
        time.sleep(3)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        try:
            gen.output(CHANNEL, False)
            gen.disable_burst(CHANNEL)
            gen.disconnect()
            print("✅ Disconnected successfully")
        except:
            print("⚠️  Warning: Some cleanup steps failed")

        print("\n🎯 Test completed!")
        print("💡 Modify the variables at the top to experiment with different commands")


def test_arb_upload():
    """Test ARB waveform upload with simple commands."""
    print("🎯 Simple ARB Upload Test")
    print("=" * 40)

    VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"
    CHANNEL = 1
    
    # Simple square wave data (0V, 3V, 0V, 3V...)
    WAVEFORM_DATA = [0.0, 0.0, 0.0, 0.0, 3.0, 3.0, 3.0, 3.0]  # 8 samples
    WAVEFORM_NAME = "SQUARE"
    WAVEFORM_INDEX = 0
    
    print("🔌 Connecting to function generator...")
    gen = SiglentSDG1032X(resource=VISA_RESOURCE)

    if not gen.connect():
        print("❌ Failed to connect!")
        return

    try:
        print(f"✅ Connected: {gen.idn()}")
        print()
        
        print("📤 Uploading ARB waveform...")
        print(f"   Data: {WAVEFORM_DATA}")
        print(f"   Name: {WAVEFORM_NAME}")
        print(f"   Index: {WAVEFORM_INDEX}")
        
        # Upload ARB data
        success = gen.upload_arb_data(CHANNEL, WAVEFORM_DATA, WAVEFORM_NAME)
        if success:
            print("✅ ARB upload successful!")
            
            # Set ARB waveform
            gen.set_arb_waveform(CHANNEL, WAVEFORM_NAME, WAVEFORM_INDEX)
            print("✅ ARB waveform set!")
            
            # Configure basic settings
            gen.set_basic_waveform(CHANNEL, "ARB", "1000HZ", "3V", "0V")
            gen.set_output_load(CHANNEL, "HIGHZ")
            gen.enable_burst(CHANNEL, "NCYC", 1, "BUS")
            gen.output(CHANNEL, True)
            
            print("🚀 Sending trigger...")
            gen.trigger_now(CHANNEL)
            print("✨ ARB waveform sent!")
            
        else:
            print("❌ ARB upload failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        gen.output(CHANNEL, False)
        gen.disconnect()
        print("✅ Disconnected")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--arb":
        test_arb_upload()
    elif len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("🎯 Simple SDG1032X Command Tester")
        print("=" * 40)
        print()
        print("USAGE:")
        print("  python simple_test.py              # Run basic command test")
        print("  python simple_test.py --arb        # Test ARB upload")
        print("  python simple_test.py --help       # Show this help")
        print()
        print("VARIABLES TO MODIFY:")
        print("  WAVEFORM_TYPE: 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'ARB', 'DC'")
        print("  FREQUENCY: '1000HZ', '1KHZ', '1MHZ'")
        print("  AMPLITUDE: '3V', '5V', '1.5V'")
        print("  OFFSET: '0V', '1V', '-1V'")
        print("  BURST_MODE: 'NCYC' (cycles), 'INF' (infinite)")
        print("  OUTPUT_LOAD: 'HIGHZ', '50', '75', '100', '150', '200', '600'")
        print()
        print("EXAMPLES:")
        print("  WAVEFORM_TYPE = 'SINE'     # Sine wave")
        print("  WAVEFORM_TYPE = 'SQUARE'   # Square wave")
        print("  WAVEFORM_TYPE = 'ARB'      # Arbitrary waveform")
        print("  FREQUENCY = '1KHZ'         # 1 kHz")
        print("  AMPLITUDE = '5V'           # 5V peak-to-peak")
    else:
        main()
