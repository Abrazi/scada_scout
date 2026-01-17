#!/usr/bin/env python3
"""
Test the IEC 61850 simulator startup flow to verify proper event logging
and no false failure messages.
"""
import time
import logging
import sys
from PySide6.QtCore import QCoreApplication
from src.models.device_models import DeviceConfig, DeviceType
from src.core.device_manager_core import DeviceManagerCore
from src.ui.widgets.event_log_widget import EventLogger

# Create Qt application (required for signals)
app = QCoreApplication(sys.argv)

# Set up logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs so we only see event_logger messages
    format='%(levelname)-8s: %(message)s'
)

print("=" * 70)
print("IEC 61850 Simulator Startup Test")
print("=" * 70)

# Create event logger
event_logger = EventLogger()

def on_event(level, source, message):
    """Display events as they're logged"""
    # Format with colors (simplified for terminal)
    color_map = {
        "ERROR": "\033[91m",    # Red
        "WARNING": "\033[93m",  # Yellow
        "INFO": "\033[96m",     # Cyan
        "DEBUG": "\033[94m",    # Blue
    }
    reset = "\033[0m"
    color = color_map.get(level, "")
    
    # Make success messages bold
    if "✅" in message:
        print(f"{color}\033[1m[{level}] {source}:\033[0m")
        for line in message.split('\n'):
            print(f"  {color}\033[1m{line}{reset}")
    else:
        print(f"{color}[{level}] {source}:{reset} {message}")

event_logger.event_logged.connect(on_event)

# Create device manager
print("\n1. Creating Device Manager...")
device_manager = DeviceManagerCore()
device_manager.event_logger = event_logger  # Set BEFORE adding devices

# Create server config (similar to what SimulateIEDDialog produces)
print("\n2. Creating IEC 61850 Server Configuration...")
server_config = DeviceConfig(
    name="TestSimulator",
    description="IEC 61850 Server Simulator",
    ip_address="127.0.0.1",
    port=10002,
    device_type=DeviceType.IEC61850_SERVER,
    scd_file_path="/home/majid/Documents/scada_scout/test.icd",
    protocol_params={"ied_name": "GPS01GPC01UPM01FCB01"}
)

# Add device (protocol created here with event_logger)
print("\n3. Adding Device to Device Manager...")
device_manager.add_device(server_config)
print(f"   Device added: {server_config.name}")

# Start connection (async)
print("\n4. Starting Server (Async)...")
device_manager.connect_device(server_config.name)

# Wait for connection to complete
print("\n5. Waiting for startup to complete...")
max_wait = 3
waited = 0
while waited < max_wait:
    time.sleep(0.5)
    waited += 0.5
    device = device_manager.get_device(server_config.name)
    if device and device.connected:
        print(f"\n✅ Server connected after {waited}s")
        break
    # Process Qt events to ensure signals are delivered
    app.processEvents()
else:
    print(f"\n⏱️  Timeout after {max_wait}s - check Event Log above for status")

# Final status
print("\n" + "=" * 70)
print("Final Status:")
print("=" * 70)
device = device_manager.get_device(server_config.name)
if device:
    print(f"Device Name: {device.config.name}")
    print(f"Connected: {device.connected}")
    print(f"Device Type: {device.config.device_type}")
    print(f"Listen Address: {device.config.ip_address}:{device.config.port}")
else:
    print("Device not found")

print("\n" + "=" * 70)
print("Test Complete - Check Event Log Messages Above")
print("=" * 70)
print("\nExpected Event Log Messages:")
print("  ✅ Successfully created dynamic model from SCD/ICD")
print("     with statistics (33 LDs, 203 LNs, 7898 attributes)")
print("  ✅ Started IEC 61850 server on IP:Port")
print("\nNo 'failure' or 'fallback' warnings should appear")
print("=" * 70)

# Cleanup
if device and device.connected:
    print("\nCleaning up...")
    device_manager.disconnect_device(server_config.name)
    print("Server stopped")
    time.sleep(0.5)
    app.processEvents()
