import sys
import os
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850.adapter import IEC61850Adapter, iec61850
from src.models.device_models import DeviceConfig, Signal, DeviceType

def diagnostic_read():
    config = DeviceConfig(
        name="TestIED",
        ip_address="172.16.11.18",
        port=102,
        device_type=DeviceType.IEC61850_IED
    )
    
    adapter = IEC61850Adapter(config)
    if not adapter.connect():
        print("Failed to connect")
        return

    # Try different formats for Pos.stVal
    variations = [
        ("GPS01ECB01Ds1/XSWI1.Pos.stVal", iec61850.IEC61850_FC_ST),
        ("GPS01ECB01Ds1/XSWI1.Pos$stVal", iec61850.IEC61850_FC_ST),
        ("GPS01ECB01Ds1/XSWI1$Pos$stVal", iec61850.IEC61850_FC_ST),
        ("GPS01ECB01Ds1/XSWI1.Pos.stVal", iec61850.IEC61850_FC_MX),
        ("GPS01ECB01Ds1/XSWI1.Pos.stVal", iec61850.IEC61850_FC_CF),
    ]

    print(f"{'Path':<40} | {'FC':<5} | {'Result'}")
    print("-" * 60)

    for path, fc in variations:
        try:
             with adapter._lock:
                 # Try readObject (MMS)
                 mms_res = iec61850.IedConnection_readObject(adapter.connection, path, fc)
                 if isinstance(mms_res, (list, tuple)) and len(mms_res) >= 2:
                     mms_val = mms_res[0]
                     err = mms_res[1]
                 else:
                     mms_val = mms_res
                     err = iec61850.IED_ERROR_OK # fallback assume ok if return object
                 
             if err == iec61850.IED_ERROR_OK and mms_val:
                 val_str, val_type, err_msg = adapter._parse_mms_value(mms_val)
                 print(f"{path:<40} | {fc:<5} | SUCCESS: {val_str} (Type: {val_type})")
                 iec61850.MmsValue_delete(mms_val)
             else:
                 print(f"{path:<40} | {fc:<5} | FAILED: ERROR {err}")
        except Exception as e:
            print(f"{path:<40} | {fc:<5} | EXCEPTION: {e}")

    # Also test the adapter's read_signal directly
    print("\nTesting adapter.read_signal:")
    sig = Signal(name="stVal", address="GPS01ECB01Ds1/XSWI1.Pos.stVal")
    res = adapter.read_signal(sig)
    print(f"Result for DOT stVal: {res.value} (Quality: {res.quality})")
    
    sig2 = Signal(name="stVal", address="GPS01ECB01Ds1/XSWI1.Pos$stVal")
    res2 = adapter.read_signal(sig2)
    print(f"Result for DOLLAR stVal: {res2.value} (Quality: {res2.quality})")

    adapter.disconnect()

if __name__ == "__main__":
    diagnostic_read()
