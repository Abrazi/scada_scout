#!/usr/bin/env python3
"""
Test actual simulation workflow: Start server, then connect client
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig, DeviceType

def main():
    print("=" * 80)
    print("Testing Actual Simulation Workflow")
    print("=" * 80)
    
    test_file = Path(__file__).parent / "test.icd"
    if not test_file.exists():
        test_file = Path(__file__).parent / "test.scd"
    
    if not test_file.exists():
        print("❌ No test file found")
        return 1
    
    # STEP 1: Start Server (simulating what the GUI does)
    print("\n📋 STEP 1: Starting IEC 61850 Server Simulator")
    print("-" * 80)
    
    server_config = DeviceConfig(
        name="SimulatedIED",
        ip_address="127.0.0.1",  # User enters this in GUI
        port=10002,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path=str(test_file),
        protocol_params={"ied_name": "TestIED"}
    )
    
    print(f"Server Config:")
    print(f"  Name: {server_config.name}")
    print(f"  IP (configured): {server_config.ip_address}")
    print(f"  Port: {server_config.port}")
    print(f"  Type: {server_config.device_type}")
    
    server = IEC61850ServerAdapter(server_config, event_logger=None)
    if not server.connect():
        print("❌ Server failed to start")
        return 1
    
    print("✅ Server started")
    time.sleep(1)
    
    # STEP 2: Try to connect client (simulating what user does)
    print("\n📋 STEP 2: Connecting Client to Simulator")
    print("-" * 80)
    
    # User tries to connect using 127.0.0.1:10002
    client_config = DeviceConfig(
        name="Client",
        ip_address="127.0.0.1",
        port=10002,
        device_type=DeviceType.IEC61850_IED
    )
    
    print(f"Client Config:")
    print(f"  Connecting to: {client_config.ip_address}:{client_config.port}")
    
    client = IEC61850Adapter(client_config, event_logger=None)
    
    print("\nAttempting connection...")
    if client.connect():
        print("✅ Client connected successfully!")
        
        # Try to discover
        print("\nDiscovering devices...")
        root = client.discover()
        if root and root.children:
            print(f"✅ Discovery successful - Found {len(root.children)} logical devices")
        else:
            print("⚠️ Connected but discovery failed")
        
        client.disconnect()
    else:
        print("❌ Client failed to connect")
        print("\n🔍 DIAGNOSIS:")
        print("   The server is running but the client cannot connect.")
        print("   This suggests the server might not be listening on 127.0.0.1")
        print("   or there's an issue with the binding.")
    
    # Cleanup
    print("\n📋 Cleanup")
    print("-" * 80)
    server.disconnect()
    print("✅ Server stopped")
    
    print("\n" + "=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
