import ctypes
from src.protocols.iec61850 import lib61850 as lib

icd_path = r"C:/Users/majid/Documents/Ann1_BS63P068XUCXX1XT6A5.icd"

print(f"Testing: {icd_path}")
print("=" * 60)

# Test direct parsing
print("\n1. Testing ConfigFileParser_createModelFromConfigFileEx...")
model = lib.ConfigFileParser_createModelFromConfigFileEx(icd_path.encode("utf-8"))

if model:
    print("✅ SUCCESS! libiec61850 can parse this ICD file")
    print("   The file is valid for libiec61850")
    lib.IedModel_destroy(model)
else:
    print("❌ FAILED! libiec61850 rejected this ICD file")
    print("   Possible reasons:")
    print("   - File encoding issue")
    print("   - XML namespace issue")  
    print("   - Missing required elements")
    print("   - Schema validation failure")
    
# Check file basics
import os
import xml.etree.ElementTree as ET

print(f"\n2. File size: {os.path.getsize(icd_path)} bytes")

try:
    tree = ET.parse(icd_path)
    root = tree.getroot()
    print(f"3. XML parses OK in Python")
    print(f"4. Root tag: {root.tag}")
    
    # Count elements
    ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else None
    def _ns(tag):
        return f"{{{ns}}}{tag}" if ns else tag
    
    ied_count = len(list(root.findall(f".//{_ns('IED')}")))
    dtt = root.find(_ns('DataTypeTemplates'))
    
    print(f"5. IED count: {ied_count}")
    print(f"6. Has DataTypeTemplates: {dtt is not None}")
    
    if ied_count > 0:
        for ied in root.findall(f".//{_ns('IED')}"):
            print(f"   IED name: {ied.get('name')}")
            ap_count = len(list(ied.findall(_ns('AccessPoint'))))
            print(f"     AccessPoints: {ap_count}")
            
except Exception as e:
    print(f"❌ XML parsing failed: {e}")
