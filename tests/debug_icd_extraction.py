import os
import ctypes
import logging
import xml.etree.ElementTree as ET
from src.protocols.iec61850 import lib61850 as lib
from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.models.device_models import DeviceConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugExtraction")

def main():
    scd_path = r"c:\Users\majid\Documents\scadaScout\scada_scout\test.icd" # Use existing file
    if not os.path.exists(scd_path):
        logger.error(f"SCD not found: {scd_path}")
        return

    # Dummy config
    config = DeviceConfig(
        name="GPS01GPC01UPM01FCB01", # Use the real IED name from logs
        ip_address="127.0.0.1",
        port=10002,
        scd_file_path=scd_path,
        protocol_params={"protocol": "IEC 61850"}
    )

    adapter = IEC61850ServerAdapter(config)
    
    logger.info("Attempting extraction...")
    icd_path = adapter._extract_icd_from_scd(scd_path, config.name)
    
    if not icd_path:
        logger.error("Extraction returned None")
        return

    logger.info(f"Extracted to: {icd_path}")
    
    # Verify content
    try:
        with open(icd_path, 'r', encoding='utf-8') as f:
            head = f.read(500)
            logger.info(f"File head:\n{head}")
    except Exception as e:
        logger.error(f"Read error: {e}")

    # Try loading with libiec61850
    logger.info("Attempting native load...")
    model = lib.ConfigFileParser_createModelFromConfigFileEx(icd_path.encode("utf-8"))
    
    if model:
        logger.info("SUCCESS: Model loaded natively from extracted ICD!")
        lib.IedModel_destroy(model)
    else:
        logger.error("FAILURE: Native load returned NULL. The extracted ICD is invalid for libiec61850.")

if __name__ == "__main__":
    main()
