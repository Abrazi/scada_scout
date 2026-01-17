#!/usr/bin/env python3
"""
Demonstration of IEC 61850 SBO (Select Before Operate) workflow replication.

This script demonstrates the new send_command method that automatically handles
the SBO sequence (SELECT -> wait -> OPERATE) just like iedexplorer.

Usage:
    python demo_sbo_workflow.py
"""

import sys
import os
import time
from unittest.mock import Mock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.device_models import DeviceConfig, Signal, SignalType, DeviceType
from src.protocols.base_protocol import BaseProtocol

def demo_sbo_workflow():
    """Demonstrate the SBO workflow logic."""
    print("=== IEC 61850 SBO Workflow Demonstration ===\n")

    # Mock the IEC 61850 adapter
    from src.protocols.iec61850.adapter import IEC61850Adapter
    from src.protocols.iec61850.control_models import ControlModel, ControlObjectRuntime

    # Create a mock config
    config = DeviceConfig(
        name="DemoDevice",
        ip_address="192.168.1.100",
        port=102,
        device_type=DeviceType.IEC61850_IED
    )

    # Create adapter instance (without connecting)
    adapter = IEC61850Adapter(config)

    # Mock the connection and library
    adapter.connected = True
    adapter.connection = Mock()

    # Mock the control context for SBO
    ctx = ControlObjectRuntime(
        object_reference="CSWI1.Pos",
        ctl_model=ControlModel.SBO_NORMAL,
        supports_sbo=True,
        supports_direct=True,
        sbo_reference="CSWI1.Pos.SBO"
    )
    adapter.controls["CSWI1.Pos"] = ctx

    # Mock the select and operate methods
    adapter.select = Mock(return_value=True)
    adapter.operate = Mock(return_value=True)

    # Create a test signal
    signal = Signal(
        name="ctlVal",
        address="CSWI1.Pos.Oper.ctlVal",
        signal_type=SignalType.BINARY
    )

    print("1. Testing SBO Mode:")
    print(f"   Signal: {signal.address}")
    print(f"   Control Model: {ctx.ctl_model.name}")
    print("   Expected: SELECT -> wait -> OPERATE")
    # Test the send_command method
    start_time = time.time()
    result = adapter.send_command(signal, value=True, params={'sbo_timeout': 200})
    end_time = time.time()

    print(f"   Result: {'SUCCESS' if result else 'FAILED'}")
    print(f"   Duration: {(end_time - start_time):.2f} seconds")
    # Verify the calls
    print("   Method calls:")
    print(f"     select() called: {adapter.select.called}")
    print(f"     operate() called: {adapter.operate.called}")

    if adapter.select.called:
        select_args = adapter.select.call_args
        print(f"     select() signal: {select_args[0][0].address}")

    if adapter.operate.called:
        operate_args = adapter.operate.call_args
        print(f"     operate() signal: {operate_args[0][0].address}")

    print("\n2. Testing Direct Control Mode:")
    # Change to direct control
    ctx.ctl_model = ControlModel.DIRECT_NORMAL

    # Reset mocks
    adapter.select.reset_mock()
    adapter.operate.reset_mock()

    print(f"   Control Model: {ctx.ctl_model.name}")
    print("   Expected: OPERATE only")
    result = adapter.send_command(signal, value=False)

    print(f"   Result: {'SUCCESS' if result else 'FAILED'}")
    print("   Method calls:")
    print(f"     select() called: {adapter.select.called}")
    print(f"     operate() called: {adapter.operate.called}")

    print("\n=== Demonstration Complete ===")
    print("\nKey Features Implemented:")
    print("✓ Automatic SBO sequence detection")
    print("✓ SELECT -> timeout -> OPERATE workflow")
    print("✓ Direct control bypass for non-SBO models")
    print("✓ Configurable SBO timeout")
    print("✓ Compatible with existing select()/operate() methods")

if __name__ == "__main__":
    demo_sbo_workflow()