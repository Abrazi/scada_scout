#!/usr/bin/env python3
"""
Test script for IEC 61850 SBO (Select Before Operate) functionality.
Tests the updated SBO implementation based on iedexplorer patterns.

Usage: python test_sbo_fix.py
"""

import sys
import os
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.iec61850.adapter import IEC61850Adapter
from src.protocols.iec61850 import iec61850_wrapper as iec61850

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_sbo_on_target_device():
    """Test SBO functionality on the target device 172.16.11.118:102"""

    print("=== SCADA Scout SBO Test ===")
    print("Testing SBO (Select Before Operate) on GPS01ECB01CB1/CSWI1.Pos.Oper.ctlVal")
    print("Target: 172.16.11.18:102")
    print()

    # Create event logger (None for headless testing)
    event_logger = None

    # Create device config
    config = DeviceConfig(
        name="TestDevice",
        ip_address="172.16.11.18",
        port=102,
        device_type=DeviceType.IEC61850_IED
    )

    # Create adapter
    adapter = IEC61850Adapter(config, event_logger)

    try:
        print("1. Connecting to device...")
        if not adapter.connect():
            print("❌ Connection failed")
            return False

        print("✓ Connected successfully")
        print()

        # Create signal for the target control
        from src.models.device_models import Signal, SignalType
        signal = Signal(
            name="Pos",
            address="GPS01ECB01CB1/CSWI1.Pos.Oper.ctlVal",
            signal_type=SignalType.DOUBLE_BINARY
        )

        print("2. Testing SBO sequence...")
        print("   Target: GPS01ECB01CB1/CSWI1.Pos.Oper.ctlVal")
        print("   Command: Operate to True (Close)")
        print()

        # First, try to initialize control context
        print("   Initializing control context...")
        ctx = adapter.init_control_context(signal.address)
        if ctx:
            print(f"   ✓ Control context initialized: {ctx.object_reference}")
            print(f"     - Control Model: {ctx.ctl_model}")
            print(f"     - SBO Reference: {ctx.sbo_reference}")
            print(f"     - Current ctlNum: {ctx.ctl_num}")
        else:
            print("   ❌ Control context initialization failed")
            return False

        print()

        # Check if SBOw object exists
        print(f"   Checking if SBOw object exists: {ctx.sbo_reference}")
        try:
            # Try to read the SBOw object
            val, err = iec61850.IedConnection_readBooleanValue(
                adapter.connection, ctx.sbo_reference, iec61850.IEC61850_FC_CO
            )
            if err == iec61850.IED_ERROR_OK:
                print(f"   ✓ SBOw object readable, current value: {val}")
            else:
                print(f"   ❌ SBOw object not readable, error: {err}")
        except Exception as e:
            print(f"   ❌ Error reading SBOw object: {e}")

        # Check what control objects are available
        print(f"   Checking available control objects for: {ctx.object_reference}")
        
        objects_to_check = [
            f"{ctx.object_reference}.Oper",
            f"{ctx.object_reference}.SBO", 
            f"{ctx.object_reference}.SBOw",
            f"{ctx.object_reference}.Cancel"
        ]
        
        # Try different functional constraints
        fcs = [
            ("CO", iec61850.IEC61850_FC_CO),
            ("CF", iec61850.IEC61850_FC_CF),
            ("ST", iec61850.IEC61850_FC_ST),
            ("MX", iec61850.IEC61850_FC_MX)
        ]
        
        for obj in objects_to_check:
            print(f"   Testing {obj} with different FCs:")
            for fc_name, fc_val in fcs:
                try:
                    val, err = iec61850.IedConnection_readBooleanValue(
                        adapter.connection, obj, fc_val
                    )
                    if err == iec61850.IED_ERROR_OK:
                        print(f"     ✓ {fc_name}: {val}")
                        break
                    else:
                        print(f"     ❌ {fc_name}: error {err}")
                except Exception as e:
                    print(f"     ❌ {fc_name}: exception {e}")
            print()

        print()

        # Test the SBO sequence using send_command (should auto-detect and fallback)
        start_time = time.time()
        try:
            success = adapter.send_command(signal, True, params={'sbo_timeout': 100})
        except Exception as e:
            print(f"Exception during send_command: {e}")
            success = False
        end_time = time.time()

        print()
        if success:
            print("✓ SBO sequence completed successfully!")
            print(f"   Duration: {end_time - start_time:.2f} seconds")
        else:
            print("❌ SBO sequence failed!")
            print("   Check the event logs above for details")

        print()
        print("3. Test Summary:")
        print(f"   - Connection: ✓")
        print(f"   - SBO Sequence: {'✓' if success else '❌'}")
        print(f"   - Duration: {end_time - start_time:.2f} seconds")
        print("   - Target Device: 172.16.11.18:102")
        print("   - Control Object: GPS01ECB01CB1/CSWI1.Pos.Oper.ctlVal")

        return success

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

    finally:
        print()
        print("4. Cleaning up...")
        try:
            adapter.disconnect()
            print("✓ Disconnected")
        except:
            pass

if __name__ == "__main__":
    success = test_sbo_on_target_device()
    sys.exit(0 if success else 1)