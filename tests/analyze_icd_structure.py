import xml.etree.ElementTree as ET

# Compare a working ICD with our extracted one
working_icd = r"c:\Users\majid\Documents\scadaScout\scada_scout\libiec61850\examples\server_example_basic_io\simpleIO_direct_control.icd"
test_scd = r"c:\Users\majid\Documents\scadaScout\scada_scout\test.scd"

print("=== Analyzing Working ICD Structure ===")
tree = ET.parse(working_icd)
root = tree.getroot()

print(f"Root tag: {root.tag}")
print(f"Root attributes: {root.attrib}")
print("\nTop-level children:")
for child in root:
    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
    print(f"  - {tag} (attribs: {list(child.attrib.keys())})")
    if tag == 'IED':
        print(f"    IED name: {child.get('name')}")
        for subchild in child:
            subtag = subchild.tag.split('}')[-1] if '}' in subchild.tag else subchild.tag
            print(f"      - {subtag}")

print("\n=== Analyzing Test SCD Structure ===")
tree2 = ET.parse(test_scd)
root2 = tree2.getroot()

print(f"Root tag: {root2.tag}")
print(f"Root attributes: {root2.attrib}")
print("\nTop-level children:")
for child in root2:
    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
    count = 0
    if tag == 'IED':
        count = 1
    else:
        count = len(list(child))
    print(f"  - {tag} (children: {count})")

# Look for namespace differences
print("\n=== Namespace Comparison ===")
print(f"Working ICD namespace: {root.tag.split('}')[0] if '}' in root.tag else 'NO NAMESPACE'}")
print(f"Test SCD namespace: {root2.tag.split('}')[0] if '}' in root2.tag else 'NO NAMESPACE'}")

# Check schema location
print("\n=== Schema Location ===")
xsi_ns = "{http://www.w3.org/2001/XMLSchema-instance}"
print(f"Working ICD schemaLocation: {root.get(xsi_ns + 'schemaLocation', 'NOT FOUND')}")
print(f"Test SCD schemaLocation: {root2.get(xsi_ns + 'schemaLocation', 'NOT FOUND')}")

# Check for AccessPoint in working ICD
print("\n=== AccessPoint Structure in Working ICD ===")
ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
def _ns(tag):
    return f"{{{ns}}}{tag}" if ns else tag

for ied in root.findall(_ns('IED')):
    print(f"IED: {ied.get('name')}")
    for ap in ied.findall(_ns('AccessPoint')):
        print(f"  AccessPoint: {ap.get('name')}")
        server = ap.find(_ns('Server'))
        if server:
            print(f"    Has Server element")
            for child in server:
                tag = child.tag.split('}')[-1]
                print(f"      - {tag}")
