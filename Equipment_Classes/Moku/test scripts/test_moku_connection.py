#
# Moku:Go Connection Test
#
# Simple script to test connectivity to Moku:Go device
# Helps troubleshoot connection issues before running main scripts
#
# (c) 2024
#

from moku.instruments import ArbitraryWaveformGenerator
import socket

def test_network_connectivity(ip, port=80, timeout=5):
    """Test basic network connectivity to IP address."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def test_moku_connection(ip):
    """Test connection to Moku:Go AWG."""
    print(f"🔌 Testing connection to Moku:Go at {ip}...")
    print("-" * 50)

    # Test 1: Basic network connectivity
    print("Test 1: Network connectivity...")
    if test_network_connectivity(ip):
        print(f"✅ Network: {ip} is reachable")
    else:
        print(f"❌ Network: Cannot reach {ip}")
        print("   Possible causes:")
        print("   - Wrong IP address")
        print("   - Moku:Go not powered on")
        print("   - Network configuration issue")
        print("   - Firewall blocking connection")
        return False

    # Test 2: Moku API connection
    print("\nTest 2: Moku API connection...")
    try:
        awg = ArbitraryWaveformGenerator(ip, force_connect=True, connect_timeout=10)
        print("✅ Moku API: Connection successful!")
        print(f"   Device: {awg}")
        return True
    except Exception as e:
        print(f"❌ Moku API: Connection failed - {e}")
        print("   Possible causes:")
        print("   - Moku:Go not in AWG mode")
        print("   - Firmware version incompatibility")
        print("   - Network timeout")
        return False

def scan_network_range(base_ip="192.168.0", start=1, end=254):
    """Scan network range for potential Moku:Go devices."""
    print(f"\n🔍 Scanning network range {base_ip}.{start}-{end}...")
    found_devices = []

    for i in range(start, end + 1):
        ip = f"{base_ip}.{i}"
        if test_network_connectivity(ip, timeout=1):
            print(f"📡 Found device at: {ip}")
            found_devices.append(ip)

    if found_devices:
        print(f"\n✅ Found {len(found_devices)} device(s):")
        for ip in found_devices:
            print(f"   {ip}")
        print("\n💡 Try these IPs in your scripts!")
    else:
        print("\n❌ No devices found in this range")

    return found_devices

def main():
    print("🔧 Moku:Go Connection Test Utility")
    print("=" * 50)

    # Default IP to test
    default_ip = "192.168.0.45"

    print(f"Default test IP: {default_ip}")
    print("You can modify this in the script or enter a different IP below.")
    print()

    # Get user input for IP
    user_ip = input(f"Enter Moku:Go IP address [{default_ip}]: ").strip()
    if not user_ip:
        user_ip = default_ip

    # Test the specified IP
    if test_moku_connection(user_ip):
        print("
🎉 SUCCESS! Your Moku:Go is ready to use!"        print("   You can now run your binary transmitter scripts."    else:
        print("
❌ Connection test failed."        print("   Let's try scanning your network for Moku:Go devices...")

        # Ask if user wants to scan network
        scan_choice = input("\nScan network for devices? (y/n) [y]: ").strip().lower()
        if scan_choice in ['', 'y', 'yes']:
            base_ip = input("Enter network base (e.g., 192.168.0) [192.168.0]: ").strip()
            if not base_ip:
                base_ip = "192.168.0"

            scan_network_range(base_ip)

    print("\n" + "="*50)
    print("💡 Troubleshooting tips:")
    print("   1. Check Moku:Go is powered on and connected")
    print("   2. Verify IP address in Moku:Go settings")
    print("   3. Ensure Moku:Go is in the correct mode (AWG)")
    print("   4. Try different IP addresses")
    print("   5. Check network/firewall settings")
    print("   6. Restart Moku:Go and try again")

if __name__ == "__main__":
    main()
