import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath('src'))

from protocols.iec61850.server_adapter import IEC61850ServerAdapter
from models.device_models import DeviceConfig, DeviceType
from core.device_manager_core import Signal

def test_injection():
    scd_path = "/home/majid/Documents/scada_scout/dubgg/DUBGG.scd"
    ied_name = "ABBK3A03A1"

    config = DeviceConfig(
        name=ied_name,
        ip_address="0.0.0.0",
        port=10102,
        device_type=DeviceType.IEC61850_SERVER,
        scd_file_path=scd_path
    )

    adapter = IEC61850ServerAdapter(config)
    adapter.connect()

    # Create dummy signal.
    # Signal(name, address, ...)
    signal = Signal("stVal", "ABBK3A03A1CTRL/DCCILO1.EnaOpn.stVal", "")
    
    # Try to write
    print("\n--- ATTEMPTING WRITE ---")
    val = adapter.write_signal(signal, "1")
    print(f"\n--- WRITE RESULT: {val} ---")
    
    adapter.disconnect()

if __name__ == '__main__':
    test_injection()
