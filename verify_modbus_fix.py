
import sys
import os
import time
import logging

# Ensure src is in path
sys.path.append(os.getcwd())

from src.core.device_manager import DeviceManager
from src.models.device_models import DeviceConfig, DeviceType, ModbusRegisterMap

# Setup logging
logging.basicConfig(level=logging.INFO)

def verify_modbus_discovery():
    dm = DeviceManager(config_path="test_devices.json")
    
    # Create a config with a register map
    config = DeviceConfig(
        name="TestModbus",
        device_type=DeviceType.MODBUS_TCP,
        ip_address="127.0.0.1",
        modbus_register_maps=[
            ModbusRegisterMap(
                start_address=40001,
                count=10,
                name="HoldingRegs"
            )
        ]
    )
    
    print("Adding device...")
    device = dm.add_device(config)
    
    # Check if root_node is populated IMMEDIATELY
    if not device.root_node:
        print("FAIL: root_node is None")
        return False
        
    print(f"Root Node: {device.root_node.name}")
    print(f"Children: {len(device.root_node.children)}")
    
    # Check for signals
    all_signals = []
    def collect(node):
        all_signals.extend(node.signals)
        for c in node.children:
            collect(c)
            
    collect(device.root_node)
    
    print(f"Total Signals Found: {len(all_signals)}")
    
    if len(all_signals) == 10:
        print("SUCCESS: Found expected 10 signals.")
        return True
    else:
        print(f"FAIL: Expected 10 signals, found {len(all_signals)}")
        return False

if __name__ == "__main__":
    success = verify_modbus_discovery()
    sys.exit(0 if success else 1)
