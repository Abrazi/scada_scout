import os
import xml.etree.ElementTree as ET
from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
from src.models.device_models import DeviceConfig

scd_path = r"c:\Users\majid\Documents\scadaScout\scada_scout\test.scd"
ied_name = "ABBK1A01A1"

config = DeviceConfig(
    name=ied_name,
    ip_address="127.0.0.1",
    port=10003,
    scd_file_path=scd_path
)

adapter = IEC61850ServerAdapter(config)
icd_path = adapter._extract_icd_from_scd(scd_path, ied_name)

if icd_path:
    print(f"Extracted ICD: {icd_path}")
    
    tree = ET.parse(icd_path)
    root = tree.getroot()
    
    print(f"\nRoot: {root.tag}")
    print("Children:")
    for child in root:
        tag = child.tag.split('}')[-1]
        print(f"  {tag}")
        if tag == 'IED':
            print(f"    name={child.get('name')}")
            for subchild in child:
                subtag = subchild.tag.split('}')[-1]
                print(f"      {subtag} (name={subchild.get('name', 'N/A')})")
                
    # Save for manual inspection
    output = icd_path.replace('.icd', '_debug.icd')
    tree.write(output, encoding='utf-8', xml_declaration=True)
    print(f"\nSaved debug copy to: {output}")
