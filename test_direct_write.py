#!/usr/bin/env python3
"""
Test IEDScout-style direct write fallback for IEC61850 control.

This script tests the new functionality that mimics IEDScout's approach:
instead of using formal SELECT/OPERATE control services, it directly writes
to the Oper control object when SELECT fails.

Based on PCAP analysis showing IEDScout uses:
- MMS WRITE service (0xa5) instead of Control/SELECT (0xa6)
- Direct write to CSWI1$CO$Pos$Oper with origin structure
"""

from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import Signal, DeviceConfig
from src.core.event_logger import EventLogger
import sys

def test_direct_write():
    """Test control with automatic fallback to direct write."""
    
    # Setup
    logger = EventLogger()
    config = DeviceConfig(
        name='TestIED', 
        ip_address='172.16.11.18', 
        port=102, 
        device_type='IEC61850'
    )
    adapter = IEC61850Adapter(config, event_logger=logger)
    
    print('='*60)
    print('Testing IEDScout-style Direct Write Fallback')
    print('='*60)
    print(f'Target IED: {config.ip_address}:{config.port}')
    print()
    
    # Connect
    print('Step 1: Connecting to IED...')
    try:
        if not adapter.connect():
            print('✗ Connection failed - IED may be offline')
            print('\nWhen IED is online, this test will:')
            print('  1. Try formal SELECT/OPERATE control (expected to fail with Error 20)')
            print('  2. Automatically fallback to IEDScout-style direct write')
            print('  3. Try multiple path formats:')
            print('     - GPS01ECB01CB1/CSWI1$CO$Pos$Oper (dollar signs)')
            print('     - GPS01ECB01CB1/CSWI1.CO.Pos.Oper (dots)')
            print('     - GPS01ECB01CB1/CSWI1.Pos.Oper (simple)')
            print('  4. Report which path worked')
            return False
    except Exception as e:
        print(f'✗ Connection error: {e}')
        return False
        
    print('✓ Connected successfully')
    print()
    
    # Discover
    print('Step 2: Discovering device model...')
    try:
        adapter.discover()
        print('✓ Discovery complete')
    except Exception as e:
        print(f'✗ Discovery failed: {e}')
        adapter.disconnect()
        return False
    print()
    
    # Test control command
    signal = Signal(
        name='Position', 
        address='GPS01ECB01CB1/CSWI1.Pos',
        value=False
    )
    
    print('Step 3: Sending control command (value=True)...')
    print('  - First attempt: Formal SELECT/OPERATE (expected to fail with Error 20)')
    print('  - Second attempt: IEDScout-style direct write to Oper object')
    print()
    
    try:
        result = adapter.send_command(signal, True, {})
    except Exception as e:
        print(f'✗ Exception during command: {e}')
        adapter.disconnect()
        return False
    
    print()
    print('='*60)
    if result:
        print('✓ SUCCESS: Control command succeeded!')
        print('  IEDScout-style direct write worked')
    else:
        error = getattr(adapter, '_last_control_error', 'Unknown error')
        print(f'✗ FAILED: {error}')
        print()
        print('Check the event log above for details about which paths were tried')
    print('='*60)
    
    adapter.disconnect()
    return result

if __name__ == '__main__':
    success = test_direct_write()
    sys.exit(0 if success else 1)
