import xml.etree.ElementTree as ET

def check_interlock_in_scd(scd_path):
    tree = ET.parse(scd_path)
    root = tree.getroot()
    ns = {'ns': 'http://www.iec.ch/61850/2003/SCL'}
    
    # just dumping out LN names to find the CILO relation
    for ln in root.findall(f".//ns:LDevice[@inst='CTRL']//ns:LN[@lnClass='CILO']", ns):
        print(f"LN: CILO {ln.get('inst')} {ln.get('prefix')}")

check_interlock_in_scd("tests/data/DUBGG.scd")
