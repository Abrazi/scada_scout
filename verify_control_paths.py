
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd()))

from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig

def test_control_path_extraction():
    config = DeviceConfig(name="Test", ip_address="127.0.0.1", port=102)
    adapter = IEC61850Adapter(config)
    
    test_cases = [
        # Standard . separator
        ("GPS01ECB01CB1/CSWI1.Pos.Oper.ctlVal", "GPS01ECB01CB1/CSWI1.Pos"),
        ("GPS01ECB01CB1/CSWI1.Pos.stVal", "GPS01ECB01CB1/CSWI1.Pos"),
        ("GPS01ECB01CB1/CSWI1.Pos.ctlVal", "GPS01ECB01CB1/CSWI1.Pos"),
        
        # $ separator
        ("GPS01ECB01CB1/CSWI1$Pos$Oper$ctlVal", "GPS01ECB01CB1/CSWI1$Pos"),
        ("GPS01ECB01CB1/CSWI1$Pos$stVal", "GPS01ECB01CB1/CSWI1$Pos"),
        ("GPS01ECB01CB1/CSWI1$Pos$ctlVal", "GPS01ECB01CB1/CSWI1$Pos"),
        
        # Mixed/Other
        ("IED/LLN0.Health.stVal", "IED/LLN0.Health"),
        ("IED/CSWI1$Pos.Oper.ctlVal", "IED/CSWI1$Pos"),
    ]
    
    success = True
    for addr, expected in test_cases:
        result = adapter._get_control_object_reference(addr)
        if result == expected:
            print(f"PASS: {addr} -> {result}")
        else:
            print(f"FAIL: {addr} -> {result} (Expected: {expected})")
            success = False
            
    return success

if __name__ == "__main__":
    if test_control_path_extraction():
        print("\nAll path extraction tests PASSED!")
        sys.exit(0)
    else:
        print("\nSome tests FAILED!")
        sys.exit(1)
