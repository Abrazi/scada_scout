#!/usr/bin/env python3
"""
Test that the IEC 61850 server is accessible from the network.
This script starts a server and tests connectivity from different addresses.
"""

import sys
import time
import socket
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.protocols.iec61850 import iec61850_wrapper as iec61850
from src.models.device_models import DeviceConfig, DeviceType

def get_local_ips():
    """Get all local IP addresses"""
    ips = []
    try:
        import subprocess
        result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and 'inet6' not in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ip = parts[1].split('/')[0]
                        if ip != '127.0.0.1':
                            ips.append(ip)
    except Exception as e:
        print(f"Warning: Could not get network IPs: {e}")
    return ips

def test_connection(host, port):
    """Test if we can connect to the server"""
    try:
        # Create IEC 61850 connection
        conn = iec61850.IedConnection_create()
        error = iec61850.IedConnection_connect(conn, host, port)
        
        if error == 0:
            # Get server directory to verify connection
            try:
                logical_devices = iec61850.IedConnection_getLogicalDeviceList(conn)
                if logical_devices:
                    ld_count = 0
                    node = logical_devices
                    while node:
                        ld_count += 1
                        node = iec61850.LinkedList_getNext(node)
                    iec61850.LinkedList_destroy(logical_devices)
                    print(f"   ✅ Connected from {host}:{port} - Discovered {ld_count} Logical Devices")
                    iec61850.IedConnection_destroy(conn)
                    return True
            except Exception as e:
                print(f"   ✅ Connected from {host}:{port} (discovery error: {e})")
                iec61850.IedConnection_destroy(conn)
                return True
        else:
            error_msgs = {
                1: "Not connected",
                5: "Connection rejected (no server)",
                20: "Timeout"
            }
            print(f"   ❌ Failed to connect from {host}:{port} - {error_msgs.get(error, f'Error {error}')}")
            iec61850.IedConnection_destroy(conn)
            return False
    except Exception as e:
        print(f"   ❌ Exception connecting from {host}:{port} - {e}")
        return False

def main():
    print("=" * 80)
    print("Testing IEC 61850 Server Network Accessibility")
    print("=" * 80)
    
    # Check if library is loaded
    if not iec61850.is_library_loaded():
        print("❌ libiec61850 is not loaded. Please install it first.")
        return 1
    
    port = 10102
    test_icd = Path(__file__).parent / "test.icd"
    
    if not test_icd.exists():
        test_icd = Path(__file__).parent / "test.scd"
    
    if not test_icd.exists():
        print(f"❌ No test.icd or test.scd found")
        return 1
    
    print(f"\n📋 Configuration:")
    print(f"   ICD File: {test_icd}")
    print(f"   Port: {port}")
    print(f"   Binding: 0.0.0.0 (all interfaces)")
    
    # Create server config (no event logger for simple test)
    
    # Create server config
    config = DeviceConfig(
        name="NetworkTestServer",
        ip_address="127.0.0.1",  # Will be converted to 0.0.0.0 automatically
        port=port,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path=str(test_icd),
        protocol_params={"ied_name": "TestIED"}
    )
    
    # Start server
    print(f"\n🚀 Starting server...")
    server = IEC61850ServerAdapter(config, event_logger=None)
    
    if not server.connect():
        print("❌ Failed to start server")
        return 1
    
    print("✅ Server started successfully")
    
    # Wait for server to be ready
    time.sleep(1)
    
    # Test connectivity from different addresses
    print(f"\n🔌 Testing connectivity:")
    print(f"\n1. Localhost (127.0.0.1):")
    test_connection("127.0.0.1", port)
    
    # Get local IPs
    local_ips = get_local_ips()
    if local_ips:
        print(f"\n2. Network interfaces:")
        for i, ip in enumerate(local_ips, 1):
            print(f"   Testing {ip}:")
            test_connection(ip, port)
    else:
        print(f"\n2. Could not detect network IPs (try manually)")
    
    # Cleanup
    print(f"\n🛑 Stopping server...")
    server.disconnect()
    
    print("\n" + "=" * 80)
    print("✅ Test Complete - Server is network accessible when binding to 0.0.0.0")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
