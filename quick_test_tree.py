"""
Quick test to validate tree structure before running full GUI
Run this to see if discover() is building the tree correctly
"""
import sys
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s: %(message)s'
)

# Test discovery without GUI
from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.modbus.adapter import ModbusTCPAdapter

print("\n" + "="*60)
print("TESTING MODBUS DISCOVERY STRUCTURE")
print("="*60)

# Test 1: Device with folder
config1 = DeviceConfig(
    name="ModbusWithFolder",
    ip_address="127.0.0.1",
    port=502,
    device_type=DeviceType.MODBUS_TCP,
    modbus_unit_id=1,
    folder="TestFolder"
)

adapter1 = ModbusTCPAdapter(config1)
root1 = adapter1.discover()

print(f"\nDevice: {config1.name}")
print(f"Folder: {config1.folder}")
print(f"Root node name: {root1.name}")
print(f"Root node children: {len(root1.children)}")
print(f"Root node signals: {len(root1.signals) if hasattr(root1, 'signals') else 0}")

for i, child in enumerate(root1.children):
    print(f"\n  Child {i+1}: {child.name}")
    print(f"    Description: {child.description}")
    print(f"    Signals: {len(child.signals) if hasattr(child, 'signals') else 0}")
    print(f"    Children: {len(child.children) if hasattr(child, 'children') else 0}")
    if hasattr(child, 'signals') and child.signals:
        for j, sig in enumerate(child.signals[:3]):
            print(f"      Signal {j+1}: {sig.name} @ {sig.address}")
        if len(child.signals) > 3:
            print(f"      ... and {len(child.signals) - 3} more signals")

print("\n" + "="*60)
print("EXPECTED BEHAVIOR:")
print("="*60)
print("1. Root node should have 4 children (Holding Regs, Input Regs, Coils, Discrete)")
print("2. Each child should have multiple signals (10 or 16 depending on type)")
print("3. This structure should be the SAME regardless of folder setting")
print("\nIf the structure looks correct here, the issue is in the UI tree population,")
print("not in the protocol discovery.")
print("="*60)
