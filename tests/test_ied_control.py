import sys
import os
import time
import logging

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850.adapter import IEC61850Adapter
from src.models.device_models import DeviceConfig, Signal, SignalType

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_control_operation():
    # Setup connection details
    ip = "172.16.11.18"
    port = 102
    
    # Create adapter
    adapter = IEC61850Adapter(DeviceConfig(name="TestIED", ip_address=ip, port=port))
    
    logger.info(f"Connecting to {ip}:{port}...")
    if not adapter.connect():
        logger.error("Failed to connect")
        return

    logger.info("Connected!")
    
    # Define the signal - adjusting path based on user logs
    # User log: GPS01ECB01CB1/CSWI1.Pos.SBOw.ctlNum
    signal_address = "GPS01ECB01CB1/CSWI1.Pos"
    
    # Create a signal object
    signal = Signal(
        name="Circuit Breaker",
        address=signal_address,
        signal_type=SignalType.COMMAND,
        description="Breaker Control"
    )
    
    try:
        # TEST 1: Read current status
        logger.info(f"Reading current status of {signal_address}...")
        val = adapter.read_signal(signal)
        logger.info(f"Current Value: {val}")
        
        # TEST 2: Select (SBO)
        # Try to select with False (Off) as user mentioned this closes it
        logger.info("Tentative SBO with False (Off)...")
        ctl_val = False
        
        # We need to manually construct the params that the dialog would send
        # In the app, select() usually handles SBO
        
        # Note: The adapter.select() method might need specific params
        # Let's try to mimic what the UI does.
        
        logger.info("Executing Select...")
        # The select method in adapter uses _create_mms_value
        success = adapter.select(signal, ctl_val)
        logger.info(f"Select Result: {success}")
        
        if success:
            logger.info("Waiting 1s before Operate...")
            time.sleep(1)
            
            logger.info("Executing Operate...")
            success_op = adapter.operate(signal, ctl_val)
            logger.info(f"Operate Result: {success_op}")
            
    except Exception as e:
        logger.exception("Exception during test")
    finally:
        adapter.disconnect()
        logger.info("Disconnected")

if __name__ == "__main__":
    test_control_operation()
