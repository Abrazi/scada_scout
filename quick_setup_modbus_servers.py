#!/usr/bin/env python3
"""
Quick Setup Script - Add All Modbus Servers
This script adds both generator and switchgear Modbus servers with full register definitions.
Run this script directly to add all 26 servers (22 generators + 4 switchgear) to SCADA Scout.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType
from src.utils.csv_register_importer import import_csv_to_device_config
import time

# Generator IP mapping
GENERATOR_IPS = {
    "G1": "172.16.31.13", "G2": "172.16.31.23", "G3": "172.16.31.33", "G4": "172.16.31.43", "G5": "172.16.31.53",
    "G6": "172.16.32.13", "G7": "172.16.32.23", "G8": "172.16.32.33", "G9": "172.16.32.43", "G10": "172.16.32.53",
    "G11": "172.16.33.13", "G12": "172.16.33.23", "G13": "172.16.33.33", "G14": "172.16.33.43", "G15": "172.16.33.53",
    "G16": "172.16.34.13", "G17": "172.16.34.23", "G18": "172.16.34.33", "G19": "172.16.34.43", "G20": "172.16.34.53",
    "G21": "172.16.35.13", "G22": "172.16.35.23",
}

# Switchgear IP mapping
SWITCHGEAR_IPS = {
    "GPS1": "172.16.31.63",
    "GPS2": "172.16.32.63",
    "GPS3": "172.16.33.63",
    "GPS4": "172.16.34.63"
}

MODBUS_PORT = 502
CSV_PATH = 'Gen_Registers.csv'


def add_modbus_servers():
    """Add all Modbus servers with register definitions"""
    
    print("=" * 80)
    print("SCADA Scout - Modbus Server Quick Setup")
    print("=" * 80)
    print()
    
    # Create device manager
    print("1. Initializing Device Manager...")
    dm = DeviceManagerCore()
    print("✓ Device Manager ready")
    
    # Load register definitions
    print(f"\n2. Loading register definitions from {CSV_PATH}...")
    register_blocks, signal_mappings = import_csv_to_device_config(
        CSV_PATH,
        block_size=100,
        gap_threshold=50
    )
    
    if not register_blocks:
        print(f"✗ FAILED: Could not load register definitions from {CSV_PATH}")
        print("Please ensure Gen_Registers.csv exists in the project root directory")
        return False
    
    print(f"✓ Loaded {len(register_blocks)} register blocks")
    print(f"✓ Loaded {len(signal_mappings)} signal mappings")
    
    # Add generator servers
    print("\n3. Adding Generator Modbus Servers (G1-G22)...")
    gen_added = 0
    gen_skipped = 0
    
    for gen_id, ip_address in GENERATOR_IPS.items():
        # Check if exists
        if dm.get_device(gen_id):
            print(f"  - {gen_id}: Already exists, skipping")
            gen_skipped += 1
            continue
        
        # Create config
        config = DeviceConfig(
            name=gen_id,
            device_type=DeviceType.MODBUS_SERVER,
            ip_address=ip_address,
            port=MODBUS_PORT,
            modbus_unit_id=1,
            enabled=True,
            modbus_slave_blocks=register_blocks,
            modbus_slave_mappings=signal_mappings
        )
        
        try:
            device = dm.add_device(config)
            print(f"  ✓ {gen_id}: Added @ {ip_address}:{MODBUS_PORT} ({len(register_blocks)} blocks, {len(signal_mappings)} mappings)")
            gen_added += 1
            time.sleep(0.05)  # Small delay
        except Exception as e:
            print(f"  ✗ {gen_id}: Failed - {str(e)}")
            gen_skipped += 1
    
    print(f"\nGenerators: {gen_added} added, {gen_skipped} skipped")
    
    # Add switchgear servers
    print("\n4. Adding Switchgear Modbus Servers (GPS1-GPS4)...")
    swg_added = 0
    swg_skipped = 0
    
    for swg_id, ip_address in SWITCHGEAR_IPS.items():
        # Check if exists
        if dm.get_device(swg_id):
            print(f"  - {swg_id}: Already exists, skipping")
            swg_skipped += 1
            continue
        
        # Create config
        config = DeviceConfig(
            name=swg_id,
            device_type=DeviceType.MODBUS_SERVER,
            ip_address=ip_address,
            port=MODBUS_PORT,
            modbus_unit_id=1,
            enabled=True,
            modbus_slave_blocks=register_blocks,
            modbus_slave_mappings=signal_mappings
        )
        
        try:
            device = dm.add_device(config)
            print(f"  ✓ {swg_id}: Added @ {ip_address}:{MODBUS_PORT} ({len(register_blocks)} blocks, {len(signal_mappings)} mappings)")
            swg_added += 1
            time.sleep(0.05)
        except Exception as e:
            print(f"  ✗ {swg_id}: Failed - {str(e)}")
            swg_skipped += 1
    
    print(f"\nSwitchgear: {swg_added} added, {swg_skipped} skipped")
    
    # Save configuration
    print("\n5. Saving configuration to devices.json...")
    try:
        dm.save_configuration()
        print("✓ Configuration saved")
    except Exception as e:
        print(f"✗ Warning: Could not save configuration - {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SETUP COMPLETE")
    print("=" * 80)
    print(f"Total Servers Added: {gen_added + swg_added}")
    print(f"  - Generators: {gen_added}")
    print(f"  - Switchgear: {swg_added}")
    print(f"Total Skipped: {gen_skipped + swg_skipped}")
    print()
    print("Each server has:")
    print(f"  - {len(register_blocks)} register blocks")
    print(f"  - {len(signal_mappings)} signal mappings")
    print(f"  - Registers: R000-R200 (holding registers 40000-40200)")
    print()
    print("Next Steps:")
    print("1. Start SCADA Scout: python src/main.py")
    print("2. Open Device Manager")
    print("3. Select a server (e.g., G1)")
    print("4. Click 'Connect' to start the server")
    print("5. External Modbus clients can now connect!")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = add_modbus_servers()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
