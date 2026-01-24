import sys
import os
import time
import logging
from datetime import datetime

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig, Signal, SignalType

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("ReproIssue")

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
    
    adapter = IEC61850Adapter(config)
    
    print(f"Connecting to {ip}:{port}...")
    if not adapter.connect():
        print("Failed to connect!")
        return
    
    print("Connected successfully.")
    
    # Try to read the signal first
    sig = Signal(name="Pos", address=address)
    print(f"Reading signal {address}...")
    updated_sig = adapter.read_signal(sig)
    print(f"Value read: {updated_sig.value}, Error: {updated_sig.error}")
    
    # Try to operate (toggle or set to True)
    # Most Pos controls take boolean or int (Dbpos)
    # We'll try to set it to True (1)
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
