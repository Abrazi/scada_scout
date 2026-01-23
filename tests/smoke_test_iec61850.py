import os
import time
import logging
import ctypes
from src.protocols.iec61850 import lib61850 as lib
from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.models.device_models import DeviceConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmokeTest")

def main():
    # 1. Define constants explicitly (since they might be missing in lib61850.py)
    IEC61850_FC_ALL = -1  # Adjust if needed
    ACCESS_POLICY_ALLOW = 0 # 0=Allowed, 1=Denied? Check lib header logic usually 0 is allow

    # Create dummy config
    # Ensure test.ercd exists or use a dummydef main():
    scd_path = r"c:\Users\majid\Documents\scadaScout\scada_scout\test.scd"  # User renamed to .scd
    if not os.path.exists(scd_path):
        logger.error(f"SCD file not found: {scd_path}")
        return

    config = DeviceConfig(
        name="SmokeTestIED",
        ip_address="127.0.0.1",
        port=10003, # Correct int type
        scd_file_path=scd_path,
        protocol_params={"protocol": "IEC 61850"}
    )

    server = IEC61850ServerAdapter(config)

    logger.info("Starting Server...")
    try:
        if server.connect():
            logger.info("Server started successfully.")
        else:
            logger.error("Server failed to start.")
            return
    except Exception as e:
         logger.error(f"Server start exception: {e}")
         return

    time.sleep(1)

    logger.info("Starting Client to Connect...")
    connection = None
    try:
        # Client connect
        error = lib.IedClientError()
        connection = lib.IedConnection_create()
        lib.IedConnection_connect(connection, ctypes.byref(error), b"127.0.0.1", 10003)
        
        if error.value != 0:
            logger.error(f"Client connection failed code: {error.value}")
            return
        logger.info("Client connected!")

        # Discovery (often triggers potential crashes)
        error = lib.IedClientError()
        device_list = lib.IedConnection_getLogicalDeviceList(connection, ctypes.byref(error))
        if error.value == 0 and device_list:
            logger.info(f"Devices found: {device_list}")
            lib.LinkedList_destroy(device_list)
        else:
            logger.warning(f"Device discovery failed or empty: {error.value}")

        # Attempt a WRITE (critical trigger)
        # We need to find a variable. Assume one exists or just try something?
        # We'll just rely on detection for now, maybe try reading first.
        
        time.sleep(1) 
        
    except Exception as e:
        logger.error(f"Client Exception: {e}")
    finally:
        if connection:
            lib.IedConnection_close(connection)
            lib.IedConnection_destroy(connection)
        
        logger.info("Stopping server...")
        server.disconnect()
        logger.info("Test Done.")

if __name__ == "__main__":
    main()
