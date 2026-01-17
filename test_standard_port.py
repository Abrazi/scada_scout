#!/usr/bin/env python3
"""
Test IEC 61850 Server on standard port 102 (requires sudo/root)
"""
import sys
import time
import os
from PySide6.QtCore import QCoreApplication

from src.models.device_models import DeviceConfig, DeviceType
from src.core.device_manager_core import DeviceManagerCore  
from src.ui.widgets.event_log_widget import EventLogger

# Check if running as root (required for port 102)
if os.geteuid() != 0:
    print("=" * 80)
    print("⚠️  WARNING: Not running as root")
    print("=" * 80)
    print("\nPort 102 requires root/administrator privileges.")
    print("Testing will use port 10102 instead.\n")
    print("To test on port 102, run:")
    print("  sudo python test_standard_port.py")
    print("=" * 80)
    test_port = 10102
else:
    print("✓ Running as root - will test on standard port 102")
    test_port = 102

# Create Qt application
app = QCoreApplication(sys.argv)

# Create event logger
event_logger = EventLogger()

connection_events = []

def on_event(level, source, message):
    connection_events.append((level, source, message))
    # Only show important messages
    if level in ["ERROR", "WARNING"] or "✅" in message or "❌" in message:
        color = "\033[91m" if level == "ERROR" else "\033[93m" if level == "WARNING" else "\033[96m"
        reset = "\033[0m"
        print(f"{color}[{level}] {source}:{reset} {message[:100]}")

event_logger.event_logged.connect(on_event)

# Create device manager
device_manager = DeviceManagerCore()
device_manager.event_logger = event_logger

print(f"\n{'=' * 80}")
print(f"Testing IEC 61850 Server on port {test_port}")
print(f"{'=' * 80}\n")

# Server configuration
server_config = DeviceConfig(
    name="StandardPortServer",
    ip_address="127.0.0.1",
    port=test_port,
    device_type=DeviceType.IEC61850_SERVER,
    scd_file_path="/home/majid/Documents/scada_scout/test.icd",
    protocol_params={"ied_name": "GPS01GPC01UPM01FCB01"}
)

print(f"→ Starting server on {server_config.ip_address}:{test_port}...")
device_manager.add_device(server_config)
device_manager.connect_device(server_config.name)

# Wait for server
time.sleep(2)
for _ in range(10):
    app.processEvents()
    time.sleep(0.1)

server_device = device_manager.get_device(server_config.name)
if server_device and server_device.connected:
    print(f"✅ Server started successfully on port {test_port}")
    
    # Try client connection
    print(f"\n→ Testing client connection...")
    client_config = DeviceConfig(
        name="TestClient",
        ip_address="127.0.0.1",
        port=test_port,
        device_type=DeviceType.IEC61850_IED
    )
    
    device_manager.add_device(client_config)
    device_manager.connect_device(client_config.name)
    
    time.sleep(3)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.1)
    
    client_device = device_manager.get_device(client_config.name)
    if client_device and client_device.connected:
        print(f"✅ Client connected successfully")
        print(f"   Discovered: {len(client_device.root_node.children) if client_device.root_node else 0} Logical Devices")
    else:
        print(f"❌ Client failed to connect")
    
    # Cleanup
    device_manager.disconnect_device(client_config.name)
    device_manager.disconnect_device(server_config.name)
else:
    print(f"❌ Server failed to start on port {test_port}")
    
    # Check for permission errors
    for level, source, msg in connection_events:
        if "permission" in msg.lower() or "bind" in msg.lower() or "port" in msg.lower():
            print(f"\n⚠️  Port binding issue detected:")
            print(f"   {msg}")

print(f"\n{'=' * 80}")
print("Test complete")
print(f"{'=' * 80}")
