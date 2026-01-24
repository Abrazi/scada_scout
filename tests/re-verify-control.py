import sys
import os
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig, Signal, DeviceType

def test_control_definitive():
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

    # Targeting a specific signal known to exist from previous discovery
    # GPS01ECB01Ds1/XSWI1.Pos.ctlVal
    ctl_addr = "GPS01ECB01Ds1/XSWI1.Pos.ctlVal"
    st_addr = "GPS01ECB01Ds1/XSWI1.Pos.stVal"
    
    ctl_sig = Signal(name="ctlVal", address=ctl_addr)
    st_sig = Signal(name="stVal", address=st_addr)

    # Read current state
    res = adapter.read_signal(st_sig)
    print(f"INITIAL stVal: {res.value}")
    # mapping = {0: "intermediate", 1: "open", 2: "closed", 3: "bad"}

    def perform_and_check(val):
        print(f"\n---> Sending ctlVal = {val}...")
        success = adapter.send_command(ctl_sig, val)
        print(f"Operation returned success: {success}")
        time.sleep(1) # Give it a moment to change
        res = adapter.read_signal(st_sig)
        print(f"RESULTING stVal: {res.value}")
        return res.value

    # Try to ensure we know what True and False do
    # If currently closed (2), try False then True
    # If currently open (1), try True then False
    
    current = res.value
    if "closed" in str(current) or "(2)" in str(current) or current == 2:
        print("BREAKER IS CLOSED. Attempting to Open...")
        perform_and_check(True) # Try True
        perform_and_check(False) # Try False
    else:
        print("BREAKER IS OPEN (or other). Attempting to Close...")
        perform_and_check(False) # Try False
        perform_and_check(True) # Try True

    adapter.disconnect()

if __name__ == "__main__":
    test_control_definitive()
