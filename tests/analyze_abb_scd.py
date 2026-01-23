import xml.etree.ElementTree as ET

scd_path = r"c:\Users\majid\Documents\scadaScout\scada_scout\test.scd"
ied_name = "ABBK1A01A1"

tree = ET.parse(scd_path)
root = tree.getroot()

ns_uri = root.tag.split('}')[0].strip('{') if '}' in root.tag else None
def _ns(tag):
    return f"{{{ns_uri}}}{tag}" if ns_uri else tag

print(f"=== Analyzing '{ied_name}' in ABB SCD ===\n")

# Find the IED
for ied in root.findall(f".//{_ns('IED')}"):
    if ied.get('name') == ied_name:
        print(f"IED '{ied_name}' structure:")
        for child in ied:
            tag = child.tag.split('}')[-1]
            print(f"  {tag}")
            if tag == 'Server':
                print(f"    [Server has {len(list(child))} children]")
                for subchild in child:
                    subtag = subchild.tag.split('}')[-1]
                    print(f"      {subtag}")
            elif tag == 'AccessPoint':
                print(f"    name={child.get('name')}")
                for subchild in child:
                    subtag = subchild.tag.split('}')[-1]
                    print(f"      {subtag}")
                    if subtag == 'Server':
                        print(f"        [Server has {len(list(subchild))} children]")
                        for ssub in subchild:
                            sstag = ssub.tag.split('}')[-1]
                            sname = ssub.get('inst', ssub.get('name', 'N/A'))
                            print(f"          {sstag} (name/inst={sname})")
        break

# Check Communication section
print(f"\n=== Communication Section ===")
comm = root.find(_ns('Communication'))
if comm:
    for subnet in comm.findall(_ns('SubNetwork')):
        sn_name = subnet.get('name', 'N/A')
        for cap in subnet.findall(_ns('ConnectedAP')):
            if cap.get('iedName') == ied_name:
                print(f"Found ConnectedAP for {ied_name}:")
                print(f"  apName: {cap.get('apName')}")
                # Check for GSE/SMV under ConnectedAP
                for child in cap:
                    tag = child.tag.split('}')[-1]
                    print(f"  {tag}")
