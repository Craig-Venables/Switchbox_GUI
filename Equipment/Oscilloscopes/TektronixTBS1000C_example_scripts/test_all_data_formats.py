#!/usr/bin/env python3
"""
Test all data format methods for Tektronix TBS1000C waveform acquisition
----------------------------------------------------------------
This script tests all available data formats and creates comparison plots:
  - ASCII format (8-bit and 16-bit)
  - RIBINARY format (8-bit and 16-bit)
  - RPBINARY format (8-bit and 16-bit)

For each format, it saves:
  - Raw ADC codes (unscaled)
  - Scaled voltages (scaled using preamble)
  - Comparison plots showing both

Usage:
  python test_all_data_formats.py <VISA_RESOURCE> [output_dir]
Example:
  python test_all_data_formats.py USB0::0x0699::0x03C4::C023684::INSTR
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# ==================== DEBUG CONTROL ====================
DEBUG_ENABLED = True

def debug_print(*args, **kwargs):
    """Print debug messages only if DEBUG_ENABLED is True."""
    if DEBUG_ENABLED:
        print(*args, **kwargs)
# =======================================================

# Tektronix TBS1000C has 15 horizontal divisions (not 10!)
HORIZONTAL_DIVISIONS = 15.0


def find_project_root(start: Path) -> Path:
    p = start
    for _ in range(6):
        if p.name.lower() == "switchbox_gui":
            return p
        if p.parent == p:
            break
        p = p.parent
    return start


# Ensure project root on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = find_project_root(SCRIPT_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C


def save_comparison_data(format_name, raw_codes, scaled_volts, time_array, output_dir: Path):
    """Save raw and scaled data for a specific format."""
    base_name = output_dir / f"format_{format_name}"
    
    # Save raw ADC codes
    raw_file = base_name.with_name(base_name.name + "_raw.txt")
    with raw_file.open("w", encoding="utf-8") as f:
        f.write("Index\tTime (s)\tRaw_ADC_Code\n")
        for i, (t, code) in enumerate(zip(time_array, raw_codes), start=1):
            f.write(f"{i}\t{t:.9e}\t{code:.0f}\n")
    
    # Save scaled voltages
    scaled_file = base_name.with_name(base_name.name + "_scaled.txt")
    with scaled_file.open("w", encoding="utf-8") as f:
        f.write("Index\tTime (s)\tVoltage (V)\n")
        for i, (t, v) in enumerate(zip(time_array, scaled_volts), start=1):
            f.write(f"{i}\t{t:.9e}\t{v:.9e}\n")
    
    debug_print(f"  Saved: {raw_file.name}")
    debug_print(f"  Saved: {scaled_file.name}")
    
    return raw_file, scaled_file


def plot_comparison(format_name, time_array, raw_codes, scaled_volts, output_dir: Path):
    """Create comparison plot showing both raw ADC codes and scaled voltages."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot raw ADC codes
    ax1.plot(time_array, raw_codes, 'b-', linewidth=0.5, alpha=0.7)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Raw ADC Code (integer)')
    ax1.set_title(f'{format_name} - Raw ADC Codes (Unscaled)')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
    
    # Plot scaled voltages
    ax2.plot(time_array, scaled_volts, 'r-', linewidth=0.5, alpha=0.7)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Voltage (V)')
    ax2.set_title(f'{format_name} - Scaled Voltages')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
    
    plt.tight_layout()
    
    plot_file = output_dir / f"format_{format_name}_comparison.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    debug_print(f"  Saved: {plot_file.name}")
    return plot_file


def test_ascii_format(scope, output_dir: Path, data_width: int = 1):
    """Test ASCII format with specified data width."""
    format_name = f"ASCII_{data_width}byte"
    debug_print(f"\n{'='*60}")
    debug_print(f"Testing {format_name} format...")
    debug_print(f"{'='*60}")
    
    try:
        scope.write("DAT:SOU CH1")
        scope.write("DAT:ENC ASCII")
        scope.write(f"DAT:WID {data_width}")
        
        preamble = scope.get_waveform_preamble(1)
        record_len = scope._extract_record_length(preamble)
        try:
            rec_query = scope.query("HOR:RECO?").strip()
            record_len = max(record_len, int(rec_query))
        except Exception:
            pass
        
        scope.write("DAT:STAR 1")
        scope.write(f"DAT:STOP {record_len}")
        
        data_str = scope.query("CURV?")
        data_points = []
        for value in data_str.split(','):
            try:
                data_points.append(float(value.strip()))
            except ValueError:
                continue
        raw_codes = np.array(data_points, dtype=np.float64)
        
        # Scale to volts
        scaled_volts = scope._scale_waveform_values(raw_codes, preamble)
        
        # Build time array
        x_incr = preamble.get("XINCR", None)
        if x_incr is not None:
            x_zero = preamble.get("XZERO", 0.0)
            pt_off = preamble.get("PT_OFF", preamble.get("XOFF", 0.0))
            indices = np.arange(len(raw_codes), dtype=np.float64) - (pt_off or 0.0)
            time_array = indices * x_incr + x_zero
        else:
            try:
                tb_scale = float(scope.query("HOR:SCA?"))
            except Exception:
                tb_scale = 0.2
            window = tb_scale * HORIZONTAL_DIVISIONS
            time_array = np.linspace(0.0, window, len(raw_codes))
        
        debug_print(f"  Points: {len(raw_codes)}")
        debug_print(f"  Raw ADC range: {np.min(raw_codes):.0f} to {np.max(raw_codes):.0f}")
        debug_print(f"  Scaled voltage range: {np.min(scaled_volts):.6f} to {np.max(scaled_volts):.6f} V")
        
        # Save data
        save_comparison_data(format_name, raw_codes, scaled_volts, time_array, output_dir)
        
        # Create plot
        plot_comparison(format_name, time_array, raw_codes, scaled_volts, output_dir)
        
        return {
            'format': format_name,
            'raw_codes': raw_codes,
            'scaled_volts': scaled_volts,
            'time_array': time_array,
            'num_points': len(raw_codes)
        }
        
    except Exception as e:
        debug_print(f"  ERROR: {format_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_binary_format(scope, output_dir: Path, encoding: str, data_width: int = 1):
    """Test binary format (RIBINARY or RPBINARY) with specified data width."""
    format_name = f"{encoding}_{data_width}byte"
    debug_print(f"\n{'='*60}")
    debug_print(f"Testing {format_name} format...")
    debug_print(f"{'='*60}")
    
    try:
        scope.write("DAT:SOU CH1")
        scope.write(f"DAT:ENC {encoding}")
        scope.write(f"DAT:WID {data_width}")
        
        preamble = scope.get_waveform_preamble(1)
        record_len = scope._extract_record_length(preamble)
        try:
            rec_query = scope.query("HOR:RECO?").strip()
            record_len = max(record_len, int(rec_query))
        except Exception:
            pass
        
        scope.write("DAT:STAR 1")
        scope.write(f"DAT:STOP {record_len}")
        
        # Read binary data
        scope.inst.chunk_size = 1024000  # Increase chunk size for binary
        
        # For Tektronix RIBINARY format:
        # - 1 byte = signed int8 ('b')
        # - 2 bytes = signed int16 ('h') 
        # Note: RPBINARY uses unsigned values, but we'll try both
        if data_width == 1:
            if encoding == "RPBINARY":
                datatype = 'B'  # 8-bit unsigned integer (RP = positive)
            else:
                datatype = 'b'  # 8-bit signed integer (RI = signed)
        else:
            if encoding == "RPBINARY":
                datatype = 'H'  # 16-bit unsigned integer
            else:
                datatype = 'h'  # 16-bit signed integer
        
        data_binary = scope.inst.query_binary_values("CURV?", datatype=datatype, container=np.array)
        raw_codes = data_binary.astype(np.float64)
        
        # RPBINARY offset: if unsigned, need to subtract 128 (for 8-bit) or 32768 (for 16-bit)
        if encoding == "RPBINARY":
            if data_width == 1:
                raw_codes = raw_codes - 128  # Convert unsigned 0-255 to signed -128 to 127
            else:
                raw_codes = raw_codes - 32768  # Convert unsigned 0-65535 to signed -32768 to 32767
        
        # Scale to volts
        scaled_volts = scope._scale_waveform_values(raw_codes, preamble)
        
        # Build time array
        x_incr = preamble.get("XINCR", None)
        if x_incr is not None:
            x_zero = preamble.get("XZERO", 0.0)
            pt_off = preamble.get("PT_OFF", preamble.get("XOFF", 0.0))
            indices = np.arange(len(raw_codes), dtype=np.float64) - (pt_off or 0.0)
            time_array = indices * x_incr + x_zero
        else:
            try:
                tb_scale = float(scope.query("HOR:SCA?"))
            except Exception:
                tb_scale = 0.2
            window = tb_scale * HORIZONTAL_DIVISIONS
            time_array = np.linspace(0.0, window, len(raw_codes))
        
        debug_print(f"  Points: {len(raw_codes)}")
        debug_print(f"  Raw ADC range: {np.min(raw_codes):.0f} to {np.max(raw_codes):.0f}")
        debug_print(f"  Scaled voltage range: {np.min(scaled_volts):.6f} to {np.max(scaled_volts):.6f} V")
        
        # Save data
        save_comparison_data(format_name, raw_codes, scaled_volts, time_array, output_dir)
        
        # Create plot
        plot_comparison(format_name, time_array, raw_codes, scaled_volts, output_dir)
        
        return {
            'format': format_name,
            'raw_codes': raw_codes,
            'scaled_volts': scaled_volts,
            'time_array': time_array,
            'num_points': len(raw_codes)
        }
        
    except Exception as e:
        debug_print(f"  ERROR: {format_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def plot_all_formats_comparison(results, output_dir: Path):
    """Create a master comparison plot showing all formats together."""
    if not results:
        return
    
    # Filter out None results
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        return
    
    num_formats = len(valid_results)
    fig, axes = plt.subplots(num_formats, 2, figsize=(14, 4*num_formats))
    
    if num_formats == 1:
        axes = axes.reshape(1, -1)
    
    for i, result in enumerate(valid_results):
        format_name = result['format']
        time_array = result['time_array']
        raw_codes = result['raw_codes']
        scaled_volts = result['scaled_volts']
        
        # Plot raw ADC codes
        axes[i, 0].plot(time_array, raw_codes, linewidth=0.5, alpha=0.7)
        axes[i, 0].set_ylabel('Raw ADC Code')
        axes[i, 0].set_title(f'{format_name} - Raw (Unscaled)')
        axes[i, 0].grid(True, alpha=0.3)
        
        # Plot scaled voltages
        axes[i, 1].plot(time_array, scaled_volts, 'r-', linewidth=0.5, alpha=0.7)
        axes[i, 1].set_ylabel('Voltage (V)')
        axes[i, 1].set_title(f'{format_name} - Scaled')
        axes[i, 1].grid(True, alpha=0.3)
        
        if i == len(valid_results) - 1:
            axes[i, 0].set_xlabel('Time (s)')
            axes[i, 1].set_xlabel('Time (s)')
    
    plt.tight_layout()
    master_plot = output_dir / "all_formats_comparison.png"
    plt.savefig(master_plot, dpi=150, bbox_inches='tight')
    plt.close()
    
    debug_print(f"\nSaved master comparison: {master_plot.name}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_all_data_formats.py <VISA_RESOURCE> [output_dir]")
        sys.exit(1)
    
    resource = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("format_comparison_output")
    output_dir.mkdir(exist_ok=True)
    
    scope = TektronixTBS1000C(resource=resource, timeout_ms=20000)
    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)
    
    results = []
    
    try:
        debug_print("\n" + "="*60)
        debug_print("Testing ALL data format methods for Tektronix TBS1000C")
        debug_print("="*60)
        
        # Test ASCII formats
        result = test_ascii_format(scope, output_dir, data_width=1)
        results.append(result)
        
        try:
            result = test_ascii_format(scope, output_dir, data_width=2)
            results.append(result)
        except Exception as e:
            debug_print(f"  Note: ASCII 2-byte may not be supported: {e}")
        
        # Test RIBINARY formats
        try:
            result = test_binary_format(scope, output_dir, encoding="RIBINARY", data_width=1)
            results.append(result)
        except Exception as e:
            debug_print(f"  Note: RIBINARY 1-byte may not be supported: {e}")
        
        try:
            result = test_binary_format(scope, output_dir, encoding="RIBINARY", data_width=2)
            results.append(result)
        except Exception as e:
            debug_print(f"  Note: RIBINARY 2-byte may not be supported: {e}")
        
        # Test RPBINARY formats
        try:
            result = test_binary_format(scope, output_dir, encoding="RPBINARY", data_width=1)
            results.append(result)
        except Exception as e:
            debug_print(f"  Note: RPBINARY 1-byte may not be supported: {e}")
        
        try:
            result = test_binary_format(scope, output_dir, encoding="RPBINARY", data_width=2)
            results.append(result)
        except Exception as e:
            debug_print(f"  Note: RPBINARY 2-byte may not be supported: {e}")
        
        # Create master comparison plot
        plot_all_formats_comparison(results, output_dir)
        
        # Summary
        debug_print(f"\n{'='*60}")
        debug_print("SUMMARY")
        debug_print(f"{'='*60}")
        valid_results = [r for r in results if r is not None]
        debug_print(f"Successfully tested {len(valid_results)} format(s):")
        for result in valid_results:
            debug_print(f"  - {result['format']}: {result['num_points']} points")
            debug_print(f"    Raw range: {np.min(result['raw_codes']):.0f} to {np.max(result['raw_codes']):.0f}")
            debug_print(f"    Voltage range: {np.min(result['scaled_volts']):.6f} to {np.max(result['scaled_volts']):.6f} V")
        
        debug_print(f"\nAll outputs saved to: {output_dir.absolute()}")
        
        # Recommendations
        debug_print(f"\n{'='*60}")
        debug_print("RECOMMENDATIONS")
        debug_print(f"{'='*60}")
        debug_print("Based on test results:")
        debug_print("")
        debug_print("✅ BEST CHOICE: RIBINARY_1byte")
        debug_print("   - Fast binary transfer (faster than ASCII)")
        debug_print("   - Accurate scaling (-1.024V matches USB CSV)")
        debug_print("   - Same accuracy as ASCII but with better performance")
        debug_print("   - No offset corrections needed")
        debug_print("")
        debug_print("✅ GOOD FOR DEBUGGING: ASCII_1byte")
        debug_print("   - Human-readable format (easy to inspect)")
        debug_print("   - Accurate scaling")
        debug_print("   - Slower for large datasets but easier to debug")
        debug_print("")
        debug_print("⚠️ 2-BYTE FORMATS: NOT RECOMMENDED")
        debug_print("   - Scaling is incorrect (preamble YMULT is for 8-bit)")
        debug_print("   - Would need custom scaling calculations")
        debug_print("   - No benefit for typical measurements")
        debug_print("")
        debug_print("💡 RECOMMENDED SETTINGS:")
        debug_print("   scope.write('DAT:ENC RIBINARY')  # or 'ASCII' for debugging")
        debug_print("   scope.write('DAT:WID 1')         # Always use 1-byte (8-bit)")
        debug_print("")
        
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()

