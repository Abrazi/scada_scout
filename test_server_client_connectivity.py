#!/usr/bin/env python3
"""
Test IEC 61850 Server-Client connectivity
"""
import sys
import time
import logging
from PySide6.QtCore import QCoreApplication

from src.models.device_models import DeviceConfig, DeviceType
from src.core.device_manager_core import DeviceManagerCore
from src.ui.widgets.event_log_widget import EventLogger

# Create Qt application
app = QCoreApplication(sys.argv)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s: %(message)s'
)

print("=" * 80)
print("IEC 61850 SERVER-CLIENT CONNECTIVITY TEST")
print("=" * 80)

# Create event logger
event_logger = EventLogger()

def on_event(level, source, message):
    """Display events"""
    color_map = {
        "ERROR": "\033[91m",
        "WARNING": "\033[93m",
        "INFO": "\033[96m",
        "TRANSACTION": "\033[95m",
    }
    reset = "\033[0m"
    color = color_map.get(level, "")
    
    if "✅" in message or "✓" in message:
        print(f"{color}\033[1m[{level}] {source}:\033[0m")
        for line in message.split('\n'):
            print(f"  {color}\033[1m{line}{reset}")
    else:
        # Truncate long messages
        msg_lines = message.split('\n')
        if len(msg_lines) > 3:
            short_msg = '\n'.join(msg_lines[:3]) + '\n  ...'
        else:
            short_msg = message
        print(f"{color}[{level}] {source}:{reset} {short_msg}")

event_logger.event_logged.connect(on_event)

# Create device manager
device_manager = DeviceManagerCore()
device_manager.event_logger = event_logger

print("\n" + "=" * 80)
print("PHASE 1: START IEC 61850 SERVER")
print("=" * 80)

# Server configuration
server_config = DeviceConfig(
    name="TestServer",
    description="Test IEC 61850 Server",
    ip_address="127.0.0.1",
    port=10102,  # Use different port to avoid conflicts
    device_type=DeviceType.IEC61850_SERVER,
    scd_file_path="/home/majid/Documents/scada_scout/test.icd",
    protocol_params={"ied_name": "GPS01GPC01UPM01FCB01"}
)

print(f"\n→ Starting server on {server_config.ip_address}:{server_config.port}")
device_manager.add_device(server_config)
device_manager.connect_device(server_config.name)

# Wait for server to start
print("→ Waiting for server to start...")
max_wait = 5
waited = 0
server_started = False
while waited < max_wait:
    time.sleep(0.5)
    waited += 0.5
    app.processEvents()
    
    server_device = device_manager.get_device(server_config.name)
    if server_device and server_device.connected:
        print(f"✅ Server started after {waited}s")
        server_started = True
        break

if not server_started:
    print(f"❌ Server failed to start within {max_wait}s")
    print("Check Event Log above for errors")
    sys.exit(1)

# Give server a moment to fully initialize
time.sleep(1)
app.processEvents()

print("\n" + "=" * 80)
print("PHASE 2: CONNECT CLIENT TO SERVER")
print("=" * 80)

# Client configuration - connect to the server we just started
client_config = DeviceConfig(
    name="TestClient",
    description="Test IEC 61850 Client",
    ip_address="127.0.0.1",
    port=10102,  # Connect to same port as server
    device_type=DeviceType.IEC61850_IED,
    protocol_params={}
)

print(f"\n→ Connecting client to {client_config.ip_address}:{client_config.port}")
device_manager.add_device(client_config)
device_manager.connect_device(client_config.name)

# Wait for client to connect
print("→ Waiting for client to connect...")
max_wait = 10
waited = 0
client_connected = False
while waited < max_wait:
    time.sleep(0.5)
    waited += 0.5
    app.processEvents()
    
    client_device = device_manager.get_device(client_config.name)
    if client_device and client_device.connected:
        print(f"✅ Client connected after {waited}s")
        client_connected = True
        break

if not client_connected:
    print(f"❌ Client failed to connect within {max_wait}s")
    print("\nPossible causes:")
    print("  1. Server port not properly bound")
    print("  2. Firewall blocking local connections")
    print("  3. Server not accepting connections")
    print("\nCheck Event Log above for detailed connection diagnostics")
else:
    print("\n" + "=" * 80)
    print("PHASE 3: VERIFY CONNECTION")
    print("=" * 80)
    
    client_device = device_manager.get_device(client_config.name)
    if client_device:
        print(f"\nClient Status:")
        print(f"  Connected: {client_device.connected}")
        print(f"  Root Node: {client_device.root_node.name if client_device.root_node else 'None'}")
        print(f"  Children: {len(client_device.root_node.children) if client_device.root_node else 0}")
        
        if client_device.root_node and len(client_device.root_node.children) > 0:
            print(f"\n✅ SUCCESS - Client discovered {len(client_device.root_node.children)} Logical Devices")
            print("\nFirst 5 Logical Devices:")
            for i, child in enumerate(client_device.root_node.children[:5]):
                print(f"  {i+1}. {child.name}")
        else:
            print("\n⚠️  Client connected but no model discovered")

print("\n" + "=" * 80)
print("CLEANUP")
print("=" * 80)

# Disconnect client first
if client_connected:
    print("→ Disconnecting client...")
    device_manager.disconnect_device(client_config.name)
    time.sleep(0.5)
    app.processEvents()

# Stop server
if server_started:
    print("→ Stopping server...")
    device_manager.disconnect_device(server_config.name)
    time.sleep(0.5)
    app.processEvents()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

if server_started and client_connected:
    print("\n✅ SERVER-CLIENT CONNECTIVITY: SUCCESS")
    print("   The IEC 61850 server can be accessed by clients")
else:
    print("\n❌ SERVER-CLIENT CONNECTIVITY: FAILED")
    if server_started and not client_connected:
        print("   Server started but client could not connect")
        print("   Check Event Log for connection error details")

print("=" * 80)
