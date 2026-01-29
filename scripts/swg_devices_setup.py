"""Switchgear Devices Setup for SCADA Scout
Converted from swgDevices.js (Triangle MicroWorks DTM Insight)

This script adds multiple Modbus TCP SERVER devices (GPS1-GPS4) representing switchgear
to the SCADA Scout DeviceManager. Each switchgear device is configured as a Modbus Slave 
Server that responds to Modbus requests with register definitions imported from Gen_Registers.csv.

Usage:
- Run this script once from the Scripts window with 'main(ctx)' to add all devices
- Modify the IP_MAP as needed before running
- CSV_PATH can be changed to use different register definitions
"""

from src.models.device_models import DeviceConfig, DeviceType
from src.utils.csv_register_importer import import_csv_to_device_config
import time
import os

# IP mapping from original JavaScript configuration
IP_MAP = {
    "GPS1": "172.16.31.63",
    "GPS2": "172.16.32.63",
    "GPS3": "172.16.33.63",
    "GPS4": "172.16.34.63"
}

# Modbus port (default 502)
MODBUS_PORT = 502

# CSV file with register definitions
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'Gen_Registers.csv')

# Register block configuration
BLOCK_SIZE = 100
GAP_THRESHOLD = 50


def main(ctx):
    """Add all switchgear Modbus SERVER devices to SCADA Scout DeviceManager.
    
    This is a one-shot script - it runs once when you click 'Run Script'.
    Creates Modbus Slave Servers that respond to Modbus requests.
    """
    ctx.log('info', '=== Starting Switchgear Modbus Servers Setup ===')
    
    # Access the device manager through the context
    dm = ctx._dm
    
    # Import register definitions from CSV
    ctx.log('info', f'Loading register definitions from {CSV_PATH}')
    register_blocks, signal_mappings = import_csv_to_device_config(
        CSV_PATH,
        block_size=BLOCK_SIZE,
        gap_threshold=GAP_THRESHOLD
    )
    
    if not register_blocks:
        ctx.log('error', f'Failed to load register definitions from {CSV_PATH}')
        ctx.log('error', 'Please ensure Gen_Registers.csv exists in the project root')
        return "Failed to load register definitions"
    
    ctx.log('info', f'Loaded {len(register_blocks)} register blocks and {len(signal_mappings)} mappings')
    
    added_count = 0
    skipped_count = 0
    
    for swg_id, ip_address in IP_MAP.items():
        # Check if device already exists
        existing_device = dm.get_device(swg_id)
        if existing_device:
            ctx.log('info', f'{swg_id} already exists at {ip_address}, skipping')
            skipped_count += 1
            continue
        
        # Create Modbus Server configuration with register blocks
        config = DeviceConfig(
            name=swg_id,
            device_type=DeviceType.MODBUS_SERVER,  # Server, not client!
            ip_address=ip_address,
            port=MODBUS_PORT,
            modbus_unit_id=1,
            enabled=True,
            modbus_slave_blocks=register_blocks,  # Register definitions
            modbus_slave_mappings=signal_mappings  # Signal mappings
        )
        
        try:
            # Add Modbus Server device to manager
            device = dm.add_device(config)
            ctx.log('info', f'Added switchgear Modbus Server: {swg_id} @ {ip_address}:{MODBUS_PORT}')
            ctx.log('info', f'  - {len(register_blocks)} register blocks configured')
            added_count += 1
            
            # Small delay to avoid overwhelming the system
            time.sleep(0.1)
            
        except Exception as e:
            ctx.log('error', f'Failed to add {swg_id}: {str(e)}')
            skipped_count += 1
    
    ctx.log('info', f'=== Setup Complete: {added_count} servers added, {skipped_count} skipped ===')
    ctx.log('info', 'Modbus Servers are ready to start (connect) from Device Manager')
    ctx.log('info', f'Each server has {len(register_blocks)} register blocks from Gen_Registers.csv')
    ctx.log('info', 'Once started, external Modbus clients can connect to these servers')
    
    return f"Added {added_count} switchgear Modbus servers, skipped {skipped_count}"


# Optional: tick function for continuous monitoring
def tick(ctx):
    """Example continuous monitoring function.
    
    Uncomment and modify if you want this script to run continuously.
    """
    pass
    # Example: Check if GPS1 is connected
    # device = ctx._dm.get_device('GPS1')
    # if device and device.connected:
    #     # Read a register value
    #     val = ctx.get('GPS1::1:3:40001')
    #     ctx.log('info', f'GPS1 Register 40001: {val}')
