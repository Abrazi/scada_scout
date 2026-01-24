import sys
import os
import time
import logging
from datetime import datetime

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig, Signal, SignalType

# Mock Event Logger
class MockEventLogger:
    def info(self, component, msg): print(f"[INFO][{component}] {msg}")
    def error(self, component, msg): print(f"[ERROR][{component}] {msg}")
    def warning(self, component, msg): print(f"[WARN][{component}] {msg}")
    def debug(self, component, msg): print(f"[DEBUG][{component}] {msg}")
    def transaction(self, component, msg): print(f"[TRANS][{component}] {msg}")

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def test_operation():
    ip = "172.16.11.18"
    port = 102
    address = "GPS01ECB01CB1/CSWI1.Pos.Oper.ctlVal"
    
    config = DeviceConfig(
        name="TestIED",
        ip_address=ip,
        port=port,
        protocol_params={"protocol": "IEC 61850"}
    )
    
    event_logger = MockEventLogger()
    adapter = IEC61850Adapter(config, event_logger=event_logger)
    
    print(f"Connecting to {ip}:{port}...")
    if not adapter.connect():
        print("Failed to connect!")
        return
    
    print("Connected successfully.")
    
    sig = Signal(name="Pos", address=address)
    
    # Try to operate
    val_to_send = True
    print(f"Sending command: {address} = {val_to_send}...")
    success = adapter.send_command(sig, val_to_send)
    
    if success:
        print("Command sent successfully!")
    else:
        print("Command failed!")
    
    print("Disconnecting...")
    adapter.disconnect()

if __name__ == "__main__":
    test_operation()
