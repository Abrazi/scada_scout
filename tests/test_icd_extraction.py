import os
import ctypes
from src.protocols.iec61850 import lib61850 as lib
from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.models.device_models import DeviceConfig

# Test with user's real SCD
scd_path = r"c:\Users\majid\Documents\scadaScout\scada_scout\test.scd"
ied_name = "ABBK1A01A1"  # User's IED name from logs

print(f"Testing ICD extraction for {ied_name} from {scd_path}")

config = DeviceConfig(
    name=ied_name,
    ip_address="127.0.0.1",
    port=10003,
    scd_file_path=scd_path
)

adapter = IEC61850ServerAdapter(config)

# Test extraction
print("\n=== Testing ICD Extraction ===")
icd_path = adapter._extract_icd_from_scd(scd_path, ied_name)

if not icd_path:
    print("❌ Extraction failed")
    exit(1)

print(f"✅ Extracted to: {icd_path}")
print(f"   Size: {os.path.getsize(icd_path)} bytes")

# Test if libiec61850 can parse it
print("\n=== Testing Native Parser ===")
model = lib.ConfigFileParser_createModelFromConfigFileEx(icd_path.encode("utf-8"))

if model:
    print("✅ SUCCESS! libiec61850 accepted the extracted ICD")
    print("   This means the full model will be available (no minimal fallback)")
    lib.IedModel_destroy(model)
else:
    print("❌ FAILED! libiec61850 rejected the extracted ICD")
    print("   Will fall back to minimal model")
    
# Cleanup
try:
    os.unlink(icd_path)
except:
    pass
