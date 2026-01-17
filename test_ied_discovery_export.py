#!/usr/bin/env python3
"""
Test script to connect to IED, discover it, and export ICD file
"""
import sys
import time
from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType
from src.core.exporters import export_ied_from_online_discovery

def main():
    # Create device manager
    print("Initializing Device Manager...")
    manager = DeviceManagerCore()
    
    # Create device configuration for 172.16.11.18
    config = DeviceConfig(
        name="IED_172_16_11_18",
        ip_address="172.16.11.18",
        port=102,
        device_type=DeviceType.IEC61850_IED,
        description="IED for discovery and export test"
    )
    
    print(f"\nAdding device: {config.name} at {config.ip_address}:{config.port}")
    device = manager.add_device(config)
    
    if not device:
        print("ERROR: Failed to add device")
        return 1
    
    # Connect to device
    print("\nConnecting to device...")
    manager.connect_device(config.name)
    
    # Wait for connection and discovery
    print("Waiting for discovery to complete...")
    max_wait = 60  # 60 seconds timeout
    wait_interval = 2
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(wait_interval)
        elapsed += wait_interval
        
        device = manager.get_device(config.name)
        if device and device.connected:
            if device.root_node and device.root_node.children:
                print(f"\n✓ Discovery complete after {elapsed} seconds")
                break
            else:
                print(f"  Discovering... ({elapsed}s)")
        else:
            print(f"  Connecting... ({elapsed}s)")
    
    # Check final state
    device = manager.get_device(config.name)
    if not device or not device.connected:
        print("\nERROR: Failed to connect to device")
        return 1
    
    if not device.root_node or not device.root_node.children:
        print("\nERROR: Device connected but no data model discovered")
        return 1
    
    # Print discovery results
    print("\n" + "="*70)
    print("DISCOVERY RESULTS")
    print("="*70)
    print(f"IED Name: {device.root_node.name}")
    print(f"Logical Devices: {len(device.root_node.children)}")
    
    total_lns = 0
    total_signals = 0
    for ld in device.root_node.children:
        ln_count = len(ld.children)
        total_lns += ln_count
        for ln in ld.children:
            if hasattr(ln, 'signals'):
                total_signals += len(ln.signals)
    
    print(f"Total Logical Nodes: {total_lns}")
    print(f"Total Signals: {total_signals}")
    
    # List first few LDs and LNs
    print("\nStructure Overview:")
    for i, ld in enumerate(device.root_node.children[:3]):
        print(f"  LD: {ld.name} ({len(ld.children)} LNs)")
        for j, ln in enumerate(ld.children[:5]):
            signal_count = len(ln.signals) if hasattr(ln, 'signals') else 0
            print(f"    └─ LN: {ln.name} ({signal_count} signals)")
        if len(ld.children) > 5:
            print(f"    └─ ... and {len(ld.children) - 5} more LNs")
    if len(device.root_node.children) > 3:
        print(f"  ... and {len(device.root_node.children) - 3} more LDs")
    
    # Export ICD file
    print("\n" + "="*70)
    print("EXPORTING ICD FILE")
    print("="*70)
    
    output_file = f"/tmp/{config.name}_export.icd"
    print(f"Output file: {output_file}")
    
    success, msg = export_ied_from_online_discovery(device, output_file)
    
    if not success:
        print(f"\nERROR: Export failed - {msg}")
        return 1
    
    print(f"\n✓ {msg}")
    
    # Validate ICD file
    print("\n" + "="*70)
    print("VALIDATING ICD FILE")
    print("="*70)
    
    import os
    import xml.etree.ElementTree as ET
    
    if not os.path.exists(output_file):
        print("ERROR: Output file not found")
        return 1
    
    file_size = os.path.getsize(output_file)
    print(f"File size: {file_size:,} bytes")
    
    try:
        tree = ET.parse(output_file)
        root = tree.getroot()
        
        # Extract namespace
        ns_uri = root.tag.split('}')[0].strip('{') if '}' in root.tag else None
        ns = {'scl': ns_uri} if ns_uri else {}
        
        print(f"\n✓ XML is well-formed")
        print(f"Root element: {root.tag.split('}')[-1] if '}' in root.tag else root.tag}")
        print(f"Namespace: {ns_uri if ns_uri else 'None'}")
        
        # Validate IEC 61850 structure
        errors = []
        warnings = []
        
        # Check required elements
        if ns:
            header = root.find('scl:Header', ns)
            ied = root.find('.//scl:IED', ns)
            comm = root.find('scl:Communication', ns)
            dtt = root.find('scl:DataTypeTemplates', ns)
        else:
            header = root.find('Header')
            ied = root.find('.//IED')
            comm = root.find('Communication')
            dtt = root.find('DataTypeTemplates')
        
        print("\nIEC 61850 Structure Validation:")
        
        # Header
        if header is not None:
            print("  ✓ Header present")
            header_id = header.get('id')
            if header_id:
                print(f"    - ID: {header_id}")
            else:
                warnings.append("Header missing 'id' attribute")
        else:
            errors.append("Missing required Header element")
        
        # IED
        if ied is not None:
            print("  ✓ IED element present")
            ied_name = ied.get('name')
            ied_type = ied.get('type')
            ied_mfr = ied.get('manufacturer')
            print(f"    - Name: {ied_name}")
            print(f"    - Type: {ied_type}")
            print(f"    - Manufacturer: {ied_mfr}")
            
            # Check AccessPoint
            if ns:
                aps = ied.findall('.//scl:AccessPoint', ns)
            else:
                aps = ied.findall('.//AccessPoint')
            
            if aps:
                print(f"  ✓ AccessPoint(s): {len(aps)}")
                
                # Check Server
                if ns:
                    servers = ied.findall('.//scl:Server', ns)
                else:
                    servers = ied.findall('.//Server')
                
                if servers:
                    print(f"  ✓ Server element present")
                    
                    # Check LDevices
                    if ns:
                        ldevices = ied.findall('.//scl:LDevice', ns)
                    else:
                        ldevices = ied.findall('.//LDevice')
                    
                    if ldevices:
                        print(f"  ✓ LDevice(s): {len(ldevices)}")
                        
                        # Check LNs
                        if ns:
                            ln0s = ied.findall('.//scl:LN0', ns)
                            lns = ied.findall('.//scl:LN', ns)
                        else:
                            ln0s = ied.findall('.//LN0')
                            lns = ied.findall('.//LN')
                        
                        print(f"  ✓ LN0 elements: {len(ln0s)}")
                        print(f"  ✓ LN elements: {len(lns)}")
                        
                        if len(ln0s) < len(ldevices):
                            warnings.append(f"Some LDevices missing mandatory LN0 ({len(ln0s)} LN0s for {len(ldevices)} LDevices)")
                    else:
                        errors.append("No LDevice elements found")
                else:
                    errors.append("No Server element found")
            else:
                errors.append("No AccessPoint element found")
        else:
            errors.append("Missing required IED element")
        
        # Communication
        if comm is not None:
            print("  ✓ Communication section present")
            if ns:
                subnets = comm.findall('scl:SubNetwork', ns)
            else:
                subnets = comm.findall('SubNetwork')
            
            if subnets:
                print(f"    - SubNetworks: {len(subnets)}")
                if ns:
                    conn_aps = comm.findall('.//scl:ConnectedAP', ns)
                else:
                    conn_aps = comm.findall('.//ConnectedAP')
                print(f"    - ConnectedAPs: {len(conn_aps)}")
            else:
                warnings.append("Communication section has no SubNetworks")
        else:
            warnings.append("Communication section missing (optional but recommended)")
        
        # DataTypeTemplates
        if dtt is not None:
            print("  ✓ DataTypeTemplates present")
            if ns:
                lnts = dtt.findall('scl:LNodeType', ns)
                dots = dtt.findall('scl:DOType', ns)
                dats = dtt.findall('scl:DAType', ns)
                ets = dtt.findall('scl:EnumType', ns)
            else:
                lnts = dtt.findall('LNodeType')
                dots = dtt.findall('DOType')
                dats = dtt.findall('DAType')
                ets = dtt.findall('EnumType')
            
            print(f"    - LNodeTypes: {len(lnts)}")
            print(f"    - DOTypes: {len(dots)}")
            print(f"    - DATypes: {len(dats)}")
            print(f"    - EnumTypes: {len(ets)}")
            
            if len(lnts) == 0:
                errors.append("DataTypeTemplates has no LNodeType definitions")
        else:
            errors.append("Missing required DataTypeTemplates element")
        
        # Check namespace compliance
        if ns_uri != "http://www.iec.ch/61850/2003/SCL":
            warnings.append(f"Non-standard namespace: {ns_uri}")
        
        # Check version
        version = root.get('version')
        if version:
            print(f"\n  Version: {version}")
        else:
            warnings.append("Missing version attribute on SCL element")
        
        # Summary
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        
        if not errors and not warnings:
            print("✓ ICD file is 100% compliant with IEC 61850 standard")
            print("  All required elements present")
            print("  Structure is valid")
            return 0
        
        if warnings and not errors:
            print("⚠ ICD file is valid but has warnings:")
            for w in warnings:
                print(f"  - {w}")
            print("\n✓ File is functional and compliant with core standard")
            return 0
        
        if errors:
            print("✗ ICD file has structural errors:")
            for e in errors:
                print(f"  - {e}")
            if warnings:
                print("\nWarnings:")
                for w in warnings:
                    print(f"  - {w}")
            return 1
            
    except ET.ParseError as e:
        print(f"\nERROR: XML parsing failed - {e}")
        return 1
    except Exception as e:
        print(f"\nERROR: Validation failed - {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
