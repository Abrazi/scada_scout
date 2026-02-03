"""
Test script to debug tree population issues
"""
import sys
import logging
from src.models.device_models import DeviceConfig, DeviceType, Node, Signal

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def print_node_structure(node, indent=0):
    """Recursively print node structure"""
    prefix = "  " * indent
    print(f"{prefix}Node: {node.name} (desc: {node.description})")
    
    if hasattr(node, 'signals') and node.signals:
        print(f"{prefix}  Signals: {len(node.signals)}")
        for sig in node.signals[:3]:  # Show first 3
            print(f"{prefix}    - {sig.name} @ {sig.address}")
        if len(node.signals) > 3:
            print(f"{prefix}    ... and {len(node.signals) - 3} more")
    
    if hasattr(node, 'children') and node.children:
        print(f"{prefix}  Children: {len(node.children)}")
        for child in node.children:
            print_node_structure(child, indent + 2)

def test_modbus_structure():
    """Test Modbus discovery structure"""
    print("\n=== TESTING MODBUS STRUCTURE ===")
    from src.protocols.modbus.adapter import ModbusTCPAdapter
    
    config = DeviceConfig(
        name="TestModbus",
        ip_address="127.0.0.1",
        port=502,
        device_type=DeviceType.MODBUS_TCP,
        modbus_unit_id=1,
        folder="TestFolder"  # With folder
    )
    
    adapter = ModbusTCPAdapter(config)
    # Don't connect, just test discovery structure
    root = adapter.discover()
    print(f"\nRoot node: {root.name}")
    print(f"Root children: {len(root.children)}")
    print(f"Root signals: {len(root.signals) if hasattr(root, 'signals') else 0}")
    print_node_structure(root)

def test_iec61850_structure():
    """Test IEC61850 SCD discovery structure"""
    print("\n=== TESTING IEC61850 SCD STRUCTURE ===")
    import os
    
    # Find an SCD file to test with
    scd_files = []
    for file in os.listdir('.'):
        if file.endswith('.iid') or file.endswith('.scd'):
            scd_files.append(file)
    
    if not scd_files:
        print("No SCD files found for testing")
        return
    
    from src.protocols.iec61850.adapter import IEC61850Adapter
    
    config = DeviceConfig(
        name="TestIED",
        ip_address="127.0.0.1",
        port=102,
        device_type=DeviceType.IEC61850_IED,
        scd_file_path=scd_files[0],
        use_scd_discovery=True,
        folder="TestFolder"  # With folder
    )
    
    adapter = IEC61850Adapter(config)
    root = adapter.discover()
    print(f"\nRoot node: {root.name}")
    print(f"Root children: {len(root.children) if hasattr(root, 'children') else 0}")
    print(f"Root signals: {len(root.signals) if hasattr(root, 'signals') else 0}")
    if hasattr(root, 'children'):
        print_node_structure(root)

if __name__ == "__main__":
    test_modbus_structure()
    # test_iec61850_structure()
