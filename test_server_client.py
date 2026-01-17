#!/usr/bin/env python3
"""Test IEC61850 server with a simple client read"""

import time
from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.protocols.iec61850.adapter import IEC61850Adapter as IEC61850ClientAdapter

# Start server
server_config = DeviceConfig(
    name="TestICDServer",
    ip_address="127.0.0.1",
    port=10002,
    device_type=DeviceType.IEC61850_SERVER,
    scd_file_path="/home/majid/Documents/scada_scout/test.icd",
    protocol_params={"ied_name": "GPS01GPC01UPM01FCB01"},
)

server = IEC61850ServerAdapter(server_config)
print("\n=== Starting server ===")
started = server.connect()
print(f"Server started: {started}")

if not started:
    print("Server failed to start!")
    exit(1)

# Give server time to start
time.sleep(1)

# Connect client
client_config = DeviceConfig(
    name="TestClient",
    ip_address="127.0.0.1",
    port=10002,
    device_type=DeviceType.IEC61850_IED,
    protocol_params={}
)

client = IEC61850ClientAdapter(client_config)
print("\n=== Connecting client ===")
connected = client.connect()
print(f"Client connected: {connected}")

if connected:
    # Discover model
    print("\n=== Discovering model ===")
    tree = client.discover()
    print(f"Root: {tree.name}")
    print(f"Children (LDs): {len(tree.children)}")
    if tree.children:
        first_ld = tree.children[0]
        print(f"\nFirst LD: {first_ld.name} ({len(first_ld.children)} LNs)")
        if first_ld.children:
            first_ln = first_ld.children[0]
            print(f"  First LN: {first_ln.name} ({len(first_ln.signals)} signals)")
            if first_ln.signals:
                print(f"    Sample signal: {first_ln.signals[0].address}")
    
    client.disconnect()
    print("\nClient disconnected")

# Stop server
server.disconnect()
print("Server stopped successfully!")
