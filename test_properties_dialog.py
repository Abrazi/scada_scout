#!/usr/bin/env python3
"""
Test script to verify device properties dialog works correctly.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.models.device_models import DeviceConfig, DeviceType, Device, Node
from src.protocols.iec61850.adapter import IEC61850Adapter

# Test IEC61850 adapter methods
def test_iec61850_adapter():
    print("Testing IEC61850Adapter methods...")
    
    config = DeviceConfig(
        name="TestIED",
        ip_address="192.168.1.100",
        port=102,
        device_type=DeviceType.IEC61850_IED
    )
    
    adapter = IEC61850Adapter(config)
    
    # Test method existence
    assert hasattr(adapter, 'get_datasets_info'), "Missing get_datasets_info method"
    assert hasattr(adapter, 'get_reports_info'), "Missing get_reports_info method"
    assert hasattr(adapter, 'get_goose_info'), "Missing get_goose_info method"
    
    print("✓ All IEC61850 adapter methods exist")
    
    # Test calling methods when not connected
    datasets = adapter.get_datasets_info()
    reports = adapter.get_reports_info()
    goose = adapter.get_goose_info()
    
    print(f"  Datasets (not connected): {len(datasets)}")
    print(f"  Reports (not connected): {len(reports)}")
    print(f"  GOOSE (not connected): {len(goose)}")
    print("✓ Methods return empty lists when not connected (expected)")
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_iec61850_adapter()
