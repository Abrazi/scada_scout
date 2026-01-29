#!/usr/bin/env python3
"""
Diagnostic script to trace why SBO commands are not being sent to IED.
Tests connection, control context initialization, and packet transmission.
"""

import sys
import logging
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.device_models import DeviceConfig, DeviceType, Signal, SignalQuality
from src.protocols.iec61850.adapter import IEC61850Adapter
from src.core.event_logger import EventLogger

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def diagnose_sbo_flow():
    """Test each step of SBO flow with detailed diagnostics."""
    
    print("=" * 80)
    print("SBO FLOW DIAGNOSTIC TOOL")
    print("=" * 80)
    
    # Configuration
    ied_ip = "172.16.11.18"
    ied_port = 102
    control_object = "GPS01ECB01CB1/CSWI1.Pos"
    
    print(f"\n1. CONFIGURATION")
    print(f"   IED Address: {ied_ip}:{ied_port}")
    print(f"   Control Object: {control_object}")
    
    # Create adapter
    print(f"\n2. CREATING ADAPTER")
    config = DeviceConfig(
        name="TestIED",
        device_type=DeviceType.IEC61850_IED,
        ip_address=ied_ip,
        port=ied_port
    )
    
    event_logger = EventLogger()
    adapter = IEC61850Adapter(config, event_logger=event_logger)
    print(f"   ✓ Adapter created")
    
    # Connect to IED
    print(f"\n3. CONNECTING TO IED")
    try:
        if adapter.connect():
            print(f"   ✓ Connection successful")
            print(f"   - adapter.connected = {adapter.connected}")
            print(f"   - adapter.connection = {adapter.connection}")
        else:
            print(f"   ✗ Connection FAILED")
            print(f"   - adapter.connected = {adapter.connected}")
            print(f"   - adapter.connection = {adapter.connection}")
            return
    except Exception as e:
        print(f"   ✗ Connection exception: {e}")
        return
    
    # Test control context initialization
    print(f"\n4. INITIALIZING CONTROL CONTEXT")
    try:
        # Create signal object
        signal = Signal(
            name="Pos",
            address=f"TestIED::{control_object}",
            value=False,
            quality=SignalQuality.GOOD
        )
        
        object_ref = adapter._get_control_object_reference(signal.address)
        print(f"   - Object reference: {object_ref}")
        
        ctx = adapter.init_control_context(signal.address)
        if ctx:
            print(f"   ✓ Control context initialized")
            print(f"   - object_reference: {ctx.object_reference}")
            print(f"   - ctl_model: {ctx.ctl_model.name} (value={ctx.ctl_model.value})")
            print(f"   - is_sbo: {ctx.ctl_model.is_sbo}")
            print(f"   - ctl_num: {ctx.ctl_num}")
            print(f"   - sbo_reference: {ctx.sbo_reference}")
            print(f"   - originator_id: {ctx.originator_id}")
            print(f"   - originator_cat: {ctx.originator_cat}")
        else:
            print(f"   ✗ Control context initialization FAILED")
            print(f"   This is likely why no packets are being sent!")
            
            # Try to diagnose why
            print(f"\n   DIAGNOSING FAILURE:")
            print(f"   - Checking connection status...")
            if not adapter.connected:
                print(f"     ✗ adapter.connected = False")
            if not adapter.connection:
                print(f"     ✗ adapter.connection = None")
            
            print(f"   - Trying to read ctlModel manually...")
            from src.protocols.iec61850 import iec61850_wrapper as iec61850
            val, err = iec61850.IedConnection_readInt32Value(
                adapter.connection, f"{object_ref}.ctlModel", iec61850.IEC61850_FC_CF
            )
            print(f"     Result: value={val}, error={err}")
            if err != 0:
                print(f"     ✗ Failed to read ctlModel (error code {err})")
                print(f"     This means the object reference may be invalid")
            
            return
    except Exception as e:
        print(f"   ✗ Exception during context initialization: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test send_command
    print(f"\n5. TESTING SEND_COMMAND")
    try:
        print(f"   Calling send_command({control_object}, True)...")
        
        # Enable packet capture if possible
        print(f"   NOTE: Check packets.log for network traffic")
        
        success = adapter.send_command(signal, True, params={})
        
        if success:
            print(f"   ✓ send_command returned SUCCESS")
        else:
            print(f"   ✗ send_command returned FAILURE")
            
            # Check for error message
            error = getattr(adapter, '_last_control_error', None)
            if error:
                print(f"   Error message: {error}")
        
        # Check if SELECT was actually called
        print(f"\n   Checking if packets were sent...")
        print(f"   - Review packets.log for SELECT/OPERATE MMS messages")
        print(f"   - Look for MMS service tags: 0xa6 (SELECT) or 0xa5 (OPERATE)")
        
    except Exception as e:
        print(f"   ✗ Exception during send_command: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    print(f"\n6. DISCONNECTING")
    try:
        adapter.disconnect()
        print(f"   ✓ Disconnected")
    except Exception as e:
        print(f"   ✗ Disconnect exception: {e}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    
    # Summary
    print(f"\nSUMMARY:")
    print(f"- If connection failed: Check IED IP/port and network connectivity")
    print(f"- If context init failed: Check object reference format")
    print(f"- If send_command failed: Check event_logger messages and packets.log")
    print(f"- Expected packets: SELECT (0xa6) followed by OPERATE (0xa5)")
    print(f"- To capture packets: Use Wireshark on port 102 or check packets.log")

if __name__ == "__main__":
    diagnose_sbo_flow()
