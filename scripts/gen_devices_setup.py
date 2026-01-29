"""Generator Devices Setup for SCADA Scout
Converted from GenDevices.js (Triangle MicroWorks DTM Insight)

This script adds multiple Modbus TCP SERVER devices (G1-G22) representing generators
to the SCADA Scout DeviceManager. Each generator is configured as a Modbus Slave Server
that responds to Modbus requests with register definitions imported from Gen_Registers.csv.

Usage:
- Run this script once from the Scripts window with 'main(ctx)' to add all devices
- Modify the IP_MAP or DEVICE_RANGE as needed before running
- CSV_PATH can be changed to use different register definitions
"""

from src.models.device_models import DeviceConfig, DeviceType
from src.utils.csv_register_importer import import_csv_to_device_config
import time
import os

# IP mapping from original Excel/JavaScript configuration
IP_MAP = {
    "G1": "172.16.31.13", "G2": "172.16.31.23", "G3": "172.16.31.33", "G4": "172.16.31.43", "G5": "172.16.31.53",
    "G6": "172.16.32.13", "G7": "172.16.32.23", "G8": "172.16.32.33", "G9": "172.16.32.43", "G10": "172.16.32.53",
    "G11": "172.16.33.13", "G12": "172.16.33.23", "G13": "172.16.33.33", "G14": "172.16.33.43", "G15": "172.16.33.53",
    "G16": "172.16.34.13", "G17": "172.16.34.23", "G18": "172.16.34.33", "G19": "172.16.34.43", "G20": "172.16.34.53",
    "G21": "172.16.35.13", "G22": "172.16.35.23",
}

# Which generators to add (change to add subset, e.g. [1, 2, 3] for G1-G3)
DEVICE_RANGE = range(1, 23)  # G1 to G22

# Modbus port (default 502)
MODBUS_PORT = 502

# CSV file with register definitions
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'Gen_Registers.csv')

# Register block configuration
BLOCK_SIZE = 100  # Max registers per block
GAP_THRESHOLD = 50  # Max gap to merge blocks


def main(ctx):
    """Add all generator Modbus SERVER devices to SCADA Scout DeviceManager.
    
    This is a one-shot script - it runs once when you click 'Run Script'.
    Creates Modbus Slave Servers that respond to Modbus requests.
    """
    ctx.log('info', '=== Starting Generator Modbus Servers Setup ===')
    
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
    
    for i in DEVICE_RANGE:
        gen_id = f"G{i}"
        
        if gen_id not in IP_MAP:
            ctx.log('warning', f'No IP mapping found for {gen_id}, skipping')
            skipped_count += 1
            continue
            
        ip_address = IP_MAP[gen_id]
        
        # Check if device already exists
        existing_device = dm.get_device(gen_id)
        if existing_device:
            ctx.log('info', f'{gen_id} already exists at {ip_address}, skipping')
            skipped_count += 1
            continue
        
        # Create Modbus Server configuration with register blocks
        config = DeviceConfig(
            name=gen_id,
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
            ctx.log('info', f'Added generator Modbus Server: {gen_id} @ {ip_address}:{MODBUS_PORT}')
            ctx.log('info', f'  - {len(register_blocks)} register blocks configured')
            added_count += 1
            
            # Small delay to avoid overwhelming the system
            time.sleep(0.1)
            
        except Exception as e:
            ctx.log('error', f'Failed to add {gen_id}: {str(e)}')
            skipped_count += 1
    
    ctx.log('info', f'=== Setup Complete: {added_count} servers added, {skipped_count} skipped ===')
    ctx.log('info', 'Modbus Servers are ready to start (connect) from Device Manager')
    ctx.log('info', f'Each server has {len(register_blocks)} register blocks from Gen_Registers.csv')
    ctx.log('info', 'Once started, external Modbus clients can connect to these servers')
    
    return f"Added {added_count} generator Modbus servers, skipped {skipped_count}"


# Optional: tick function for continuous monitoring
def tick(ctx):
    """Example continuous monitoring function.
    
    Uncomment and modify if you want this script to run continuously.
    """
    pass
    # Example: Check if G1 is connected
    # device = ctx._dm.get_device('G1')
    # if device and device.connected:
    #     # Read a register value
    #     val = ctx.get('G1::1:3:40001')
    #     ctx.log('info', f'G1 Register 40001: {val}')
