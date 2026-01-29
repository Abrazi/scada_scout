#!/usr/bin/env python3
"""Test script to verify Modbus server setup with registers
Run this standalone to test if devices are created with register blocks
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType
from src.utils.csv_register_importer import import_csv_to_device_config

def test_device_creation():
    """Test creating a single Modbus server device with registers"""
    
    print("=" * 80)
    print("Testing Modbus Server Device Creation with Registers")
    print("=" * 80)
    
    # Create device manager
    dm = DeviceManagerCore()
    
    # Import register definitions
    print("\n1. Loading register definitions from Gen_Registers.csv...")
    csv_path = os.path.join(os.path.dirname(__file__), 'Gen_Registers.csv')
    
    register_blocks, signal_mappings = import_csv_to_device_config(
        csv_path,
        block_size=100,
        gap_threshold=50
    )
    
    if not register_blocks:
        print("✗ FAILED: Could not load register blocks from CSV")
        return False
    
    print(f"✓ Loaded {len(register_blocks)} register blocks")
    print(f"✓ Loaded {len(signal_mappings)} signal mappings")
    
    # Create test device config
    print("\n2. Creating device configuration...")
    config = DeviceConfig(
        name="TEST_G1",
        device_type=DeviceType.MODBUS_SERVER,
        ip_address="172.16.31.13",
        port=502,
        modbus_unit_id=1,
        enabled=True,
        modbus_slave_blocks=register_blocks,
        modbus_slave_mappings=signal_mappings
    )
    
    print(f"✓ Config created: {config.name}")
    print(f"  - Device Type: {config.device_type.value}")
    print(f"  - Register Blocks: {len(config.modbus_slave_blocks)}")
    print(f"  - Signal Mappings: {len(config.modbus_slave_mappings)}")
    
    # Add device to manager
    print("\n3. Adding device to manager...")
    try:
        device = dm.add_device(config)
        print(f"✓ Device added: {device.config.name}")
        
        # Verify register blocks are stored
        print("\n4. Verifying device configuration...")
        stored_blocks = device.config.modbus_slave_blocks
        stored_mappings = device.config.modbus_slave_mappings
        
        print(f"  - Stored Register Blocks: {len(stored_blocks)}")
        print(f"  - Stored Signal Mappings: {len(stored_mappings)}")
        
        if len(stored_blocks) > 0:
            print(f"\n5. First register block details:")
            block = stored_blocks[0]
            print(f"  - Name: {block.name}")
            print(f"  - Type: {block.register_type}")
            print(f"  - Start Address: {block.start_address}")
            print(f"  - Count: {block.count}")
            print(f"  - Description: {block.description}")
        
        if len(stored_mappings) > 0:
            print(f"\n6. Sample signal mappings (first 5):")
            for i, mapping in enumerate(stored_mappings[:5]):
                print(f"  - {mapping.name} @ {mapping.address}: {mapping.data_type.value}")
        
        # Test serialization
        print("\n7. Testing configuration serialization...")
        config_dict = device.config.to_dict()
        print(f"  - Serialized blocks: {len(config_dict.get('modbus_slave_blocks', []))}")
        print(f"  - Serialized mappings: {len(config_dict.get('modbus_slave_mappings', []))}")
        
        # Test deserialization
        print("\n8. Testing configuration deserialization...")
        restored_config = DeviceConfig.from_dict(config_dict)
        print(f"  - Restored blocks: {len(restored_config.modbus_slave_blocks)}")
        print(f"  - Restored mappings: {len(restored_config.modbus_slave_mappings)}")
        
        if (len(restored_config.modbus_slave_blocks) == len(register_blocks) and
            len(restored_config.modbus_slave_mappings) == len(signal_mappings)):
            print("\n" + "=" * 80)
            print("✓ ALL TESTS PASSED")
            print("=" * 80)
            print("\nDevice creation with register blocks is working correctly.")
            print("You can now use the setup scripts in SCADA Scout.")
            return True
        else:
            print("\n✗ FAILED: Serialization/deserialization mismatch")
            return False
            
    except Exception as e:
        print(f"\n✗ FAILED: Error adding device: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_device_creation()
    sys.exit(0 if success else 1)
