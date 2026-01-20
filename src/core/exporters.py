"""
Cross-platform exporters for network configuration and device data
"""
import csv
import os
import platform
import tempfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple
from datetime import datetime
from src.models.device_models import Device, Node, Signal
from src.core.scd_parser import SCDParser
from src.utils.network_utils import NetworkScriptGenerator, NetworkUtils
from src.utils.archive_utils import ArchiveExtractor


def export_selected_ied_scl(scd_path: str, ied_name: str, filepath: str) -> Tuple[bool, str]:
    """
    Export a single IED from an SCD/SCL file to a new SCL file (IID/ICD/SCD).

    Args:
        scd_path: Source SCD/SCL file path
        ied_name: IED name to export
        filepath: Output file path (.iid/.icd/.scd)

    Returns:
        (success, error_message)
    """
    if not scd_path or not os.path.exists(scd_path):
        return False, "SCD file not found or not specified"

    if not ied_name:
        return False, "IED name not specified"

    try:
        tree = ET.parse(scd_path)
        root = tree.getroot()

        # Determine namespace (if any)
        ns_uri = None
        if "}" in root.tag:
            ns_uri = root.tag.split("}")[0].strip("{")

        def is_ied_element(elem: ET.Element) -> bool:
            if ns_uri:
                return elem.tag == f"{{{ns_uri}}}IED"
            return elem.tag == "IED" or elem.tag.endswith("}IED")

        # Verify target IED exists (direct child under root)
        ied_found = False
        available_ieds = []
        for child in list(root):
            if is_ied_element(child):
                child_name = child.get("name")
                if child_name:
                    available_ieds.append(child_name)
                    if child_name == ied_name:
                        ied_found = True

        if not ied_found:
            if available_ieds:
                return False, f"IED '{ied_name}' not found in SCD.\n\nAvailable IEDs:\n" + "\n".join(f"  • {n}" for n in available_ieds)
            else:
                return False, f"IED '{ied_name}' not found in SCD (no IEDs found in file)"

        # Remove all other IEDs (only keep the selected one)
        for child in list(root):
            if is_ied_element(child) and child.get("name") != ied_name:
                root.remove(child)

        # Filter Communication section to only include selected IED
        def is_communication_element(elem: ET.Element) -> bool:
            if ns_uri:
                return elem.tag == f"{{{ns_uri}}}Communication"
            return elem.tag == "Communication" or elem.tag.endswith("}Communication")
        
        def is_connected_ap_element(elem: ET.Element) -> bool:
            if ns_uri:
                return elem.tag == f"{{{ns_uri}}}ConnectedAP"
            return elem.tag == "ConnectedAP" or elem.tag.endswith("}ConnectedAP")
        
        for child in list(root):
            if is_communication_element(child):
                # Remove ConnectedAP elements that don't belong to selected IED
                for subnet in list(child):
                    for conn_ap in list(subnet):
                        if is_connected_ap_element(conn_ap):
                            if conn_ap.get("iedName") != ied_name:
                                subnet.remove(conn_ap)
                    # Remove empty subnets
                    if len(list(subnet)) == 0:
                        child.remove(subnet)
                # Remove Communication section if empty
                if len(list(child)) == 0:
                    root.remove(child)

        # Filter DataTypeTemplates to only include types referenced by selected IED
        # Note: This is complex and requires deep analysis of references
        # For now, we keep all DataTypeTemplates as they might be referenced
        # A full implementation would trace LNodeType/DOType/DAType references

        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        return True, f"Exported IED '{ied_name}' to {os.path.basename(filepath)}"

    except Exception as e:
        return False, str(e)


def export_ied_from_online_discovery(device: Device, filepath: str) -> Tuple[bool, str]:
    """
    Generate an ICD file from online discovery results (Device object structure).
    Creates a standards-compliant IEC 61850 ICD file from the discovered data model.

    Args:
        device: Device object with root_node containing discovered structure
        filepath: Output file path (.iid/.icd/.scd)

    Returns:
        (success, error_message)
    """
    if not device or not device.root_node:
        return False, "Device has no discovered structure"

    try:
        # IEC 61850 SCL namespace
        ns = "http://www.iec.ch/61850/2003/SCL"
        
        # Create root SCL element without namespace prefix
        root = ET.Element("SCL")
        root.set("xmlns", ns)
        root.set("version", "2007")
        root.set("revision", "B")
        
        # Add Header
        header = ET.SubElement(root, "Header")
        header.set("id", f"{device.config.name}_ICD")
        header.set("version", "1.0")
        header.set("revision", "1")
        header.set("toolID", "SCADA Scout")
        header.set("nameStructure", "IEDName")
        ET.SubElement(header, "Text").text = f"ICD generated from online discovery"
        ET.SubElement(header, "History")
        
        # Create IED element
        ied = ET.SubElement(root, "IED")
        ied.set("name", device.config.name)
        ied.set("type", "OnlineDiscovery")
        ied.set("manufacturer", "Unknown")
        ied.set("configVersion", datetime.now().strftime("%Y%m%d%H%M%S"))
        ied.set("desc", device.config.description or "IED discovered online")
        
        # Create Services (basic capabilities)
        services = ET.SubElement(ied, "Services")
        ET.SubElement(services, "DynAssociation")
        ET.SubElement(services, "GetDirectory")
        ET.SubElement(services, "GetDataObjectDefinition")
        ET.SubElement(services, "GetDataSetValue")
        ET.SubElement(services, "DataSetDirectory")
        ET.SubElement(services, "ReadWrite")
        ET.SubElement(services, "GetCBValues")
        ET.SubElement(services, "ConfReportControl")
        ET.SubElement(services, "GetLCBValues")
        ET.SubElement(services, "ReportSettings")
        
        # Create AccessPoint
        ap = ET.SubElement(ied, "AccessPoint")
        ap.set("name", "AP1")
        
        # Create Server
        server = ET.SubElement(ap, "Server")
        ET.SubElement(server, "Authentication")
        
        # Build LDevice elements from root_node structure
        _build_ldevices_from_node(server, device.root_node, ns)
        
        # Create Communication section
        comm = ET.SubElement(root, "Communication")
        subnet = ET.SubElement(comm, "SubNetwork")
        subnet.set("name", "SubNetwork1")
        subnet.set("type", "8-MMS")
        
        connected_ap = ET.SubElement(subnet, "ConnectedAP")
        connected_ap.set("iedName", device.config.name)
        connected_ap.set("apName", "AP1")
        
        address = ET.SubElement(connected_ap, "Address")
        p_ip = ET.SubElement(address, "P")
        p_ip.set("type", "IP")
        p_ip.text = device.config.ip_address
        
        p_subnet = ET.SubElement(address, "P")
        p_subnet.set("type", "IP-SUBNET")
        p_subnet.text = "255.255.255.0"
        
        p_gateway = ET.SubElement(address, "P")
        p_gateway.set("type", "IP-GATEWAY")
        p_gateway.text = "0.0.0.0"
        
        p_tsel = ET.SubElement(address, "P")
        p_tsel.set("type", "OSI-TSEL")
        p_tsel.text = "0001"
        
        p_ssel = ET.SubElement(address, "P")
        p_ssel.set("type", "OSI-SSEL")
        p_ssel.text = "0001"
        
        p_psel = ET.SubElement(address, "P")
        p_psel.set("type", "OSI-PSEL")
        p_psel.text = "00000001"
        
        p_ap_title = ET.SubElement(address, "P")
        p_ap_title.set("type", "OSI-AP-Title")
        p_ap_title.text = "1,3,9999,23"
        
        p_ae_qual = ET.SubElement(address, "P")
        p_ae_qual.set("type", "OSI-AE-Qualifier")
        p_ae_qual.text = "23"
        
        # Create DataTypeTemplates (simplified - basic types only)
        dtt = ET.SubElement(root, "DataTypeTemplates")
        _build_basic_data_types(dtt, ns)
        
        # Write to file with pretty formatting
        _indent(root)
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        
        return True, f"Generated ICD for '{device.config.name}' from online discovery"
        
    except Exception as e:
        return False, f"Failed to generate ICD: {str(e)}"


def _build_ldevices_from_node(server_elem: ET.Element, root_node: Node, ns: str):
    """Build LDevice elements from discovered Node structure."""
    # Root node represents IED, children are typically LDs
    for ld_node in root_node.children:
        # Create LDevice
        ld = ET.SubElement(server_elem, "LDevice")
        ld.set("inst", ld_node.name)
        if ld_node.description:
            ld.set("desc", ld_node.description)
        
        # Add LN0 (mandatory)
        ln0 = ET.SubElement(ld, "LN0")
        ln0.set("lnClass", "LLN0")
        ln0.set("inst", "")
        ln0.set("lnType", "LLN0_Type")
        
        # Add child LNs
        for ln_node in ld_node.children:
            # Parse LN name to extract class and instance
            ln_name = ln_node.name
            ln_class = ln_name[:4] if len(ln_name) >= 4 else ln_name
            ln_inst = ln_name[4:] if len(ln_name) > 4 else "1"
            
            ln = ET.SubElement(ld, "LN")
            ln.set("lnClass", ln_class)
            ln.set("inst", ln_inst)
            ln.set("lnType", f"{ln_class}_Type")
            if ln_node.description:
                ln.set("desc", ln_node.description)


def _build_basic_data_types(dtt_elem: ET.Element, ns: str):
    """Create basic DataTypeTemplates for discovered IED."""
    # LLN0 Type
    lln0_type = ET.SubElement(dtt_elem, "LNodeType")
    lln0_type.set("id", "LLN0_Type")
    lln0_type.set("lnClass", "LLN0")
    
    do1 = ET.SubElement(lln0_type, "DO")
    do1.set("name", "Mod")
    do1.set("type", "INC_Type")
    
    do2 = ET.SubElement(lln0_type, "DO")
    do2.set("name", "Beh")
    do2.set("type", "INS_Type")
    
    do3 = ET.SubElement(lln0_type, "DO")
    do3.set("name", "Health")
    do3.set("type", "INS_Type")
    
    do4 = ET.SubElement(lln0_type, "DO")
    do4.set("name", "NamPlt")
    do4.set("type", "LPL_Type")
    
    # Basic DO types
    for do_name, btype, cdc in [("INC_Type", "INT32", "INC"), ("INS_Type", "INT32", "INS"), ("LPL_Type", "VisString255", "LPL")]:
        do_type = ET.SubElement(dtt_elem, "DOType")
        do_type.set("id", do_name)
        do_type.set("cdc", cdc)
        
        da1 = ET.SubElement(do_type, "DA")
        da1.set("name", "stVal")
        da1.set("fc", "ST")
        da1.set("bType", btype)
        
        da2 = ET.SubElement(do_type, "DA")
        da2.set("name", "q")
        da2.set("fc", "ST")
        da2.set("bType", "Quality")
        
        da3 = ET.SubElement(do_type, "DA")
        da3.set("name", "t")
        da3.set("fc", "ST")
        da3.set("bType", "Timestamp")


def _indent(elem: ET.Element, level: int = 0):
    """Add pretty-printing indentation to XML tree."""
    indent_str = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent_str + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent_str
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent_str
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent_str



def export_network_config_script(devices: List[Device], filepath: str, 
                                 interface_name: str = None) -> Tuple[bool, str]:
    """
    Generate platform-specific network configuration script
    Automatically detects OS and generates appropriate script
    
    Args:
        devices: List of devices with IP addresses
        filepath: Output file path
        interface_name: Network interface name (auto-detected if None)
        
    Returns:
        (success, error_message)
    """
    try:
        # Extract unique IP addresses
        ip_addresses = []
        for device in devices:
            ip = device.config.ip_address
            if ip and ip not in ip_addresses:
                ip_addresses.append(ip)
        
        if not ip_addresses:
            return False, "No valid IP addresses found in device list"
        
        # Detect platform
        system = platform.system()
        
        # Auto-detect interface name if not provided
        if interface_name is None:
            if system == "Windows":
                interface_name = "Ethernet"
            elif system == "Darwin":  # macOS
                interface_name = "en0"
            else:  # Linux
                interface_name = "eth0"
        
        # Generate script based on platform
        generator = NetworkScriptGenerator()
        
        if system == "Windows":
            script_content = generator.generate_windows_batch(ip_addresses, interface_name)
            # Ensure .bat extension
            if not filepath.endswith('.bat'):
                filepath = filepath.rsplit('.', 1)[0] + '.bat'
        
        elif system == "Darwin":  # macOS
            script_content = generator.generate_macos_shell(ip_addresses, interface_name)
            # Ensure .sh extension
            if not filepath.endswith('.sh'):
                filepath = filepath.rsplit('.', 1)[0] + '.sh'
        
        else:  # Linux
            script_content = generator.generate_linux_shell(ip_addresses, interface_name)
            # Ensure .sh extension
            if not filepath.endswith('.sh'):
                filepath = filepath.rsplit('.', 1)[0] + '.sh'
        
        # Write script
        with open(filepath, 'w', newline='\n' if system != "Windows" else '\r\n') as f:
            f.write(script_content)
        
        # Make executable on Unix-like systems
        if system in ["Linux", "Darwin"]:
            os.chmod(filepath, 0o755)
        
        return True, f"Generated {system} script with {len(ip_addresses)} IP(s)"
        
    except Exception as e:
        return False, str(e)


def export_network_config_all_platforms(devices: List[Device], output_dir: str) -> Tuple[bool, str]:
    """
    Generate network configuration scripts for ALL platforms
    Useful for sharing configurations across different systems
    
    Args:
        devices: List of devices with IP addresses
        output_dir: Output directory for scripts
        
    Returns:
        (success, error_message)
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract IP addresses
        ip_addresses = []
        for device in devices:
            ip = device.config.ip_address
            if ip and ip not in ip_addresses:
                ip_addresses.append(ip)
        
        if not ip_addresses:
            return False, "No valid IP addresses found"
        
        generator = NetworkScriptGenerator()
        scripts_created = []
        
        # Windows .bat
        windows_script = generator.generate_windows_batch(ip_addresses, "Ethernet")
        windows_path = os.path.join(output_dir, "configure_network_windows.bat")
        with open(windows_path, 'w', newline='\r\n') as f:
            f.write(windows_script)
        scripts_created.append("Windows (.bat)")
        
        # Linux .sh
        linux_script = generator.generate_linux_shell(ip_addresses, "eth0")
        linux_path = os.path.join(output_dir, "configure_network_linux.sh")
        with open(linux_path, 'w', newline='\n') as f:
            f.write(linux_script)
        os.chmod(linux_path, 0o755)
        scripts_created.append("Linux (.sh)")
        
        # macOS .sh
        macos_script = generator.generate_macos_shell(ip_addresses, "en0")
        macos_path = os.path.join(output_dir, "configure_network_macos.sh")
        with open(macos_path, 'w', newline='\n') as f:
            f.write(macos_script)
        os.chmod(macos_path, 0o755)
        scripts_created.append("macOS (.sh)")
        
        # README
        readme_path = os.path.join(output_dir, "README.txt")
        with open(readme_path, 'w') as f:
            f.write("SCADA Scout - Network Configuration Scripts\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generated {len(ip_addresses)} IP address configuration(s)\n\n")
            f.write("IP Addresses:\n")
            for ip in ip_addresses:
                f.write(f"  - {ip}\n")
            f.write("\n")
            f.write("Platform-Specific Instructions:\n\n")
            f.write("WINDOWS:\n")
            f.write("  1. Right-click 'configure_network_windows.bat'\n")
            f.write("  2. Select 'Run as Administrator'\n")
            f.write("  3. Follow on-screen prompts\n\n")
            f.write("LINUX:\n")
            f.write("  1. Open terminal in this directory\n")
            f.write("  2. Run: sudo bash configure_network_linux.sh\n")
            f.write("  3. Enter password when prompted\n\n")
            f.write("macOS:\n")
            f.write("  1. Open terminal in this directory\n")
            f.write("  2. Run: sudo bash configure_network_macos.sh\n")
            f.write("  3. Enter password when prompted\n\n")
            f.write("IMPORTANT NOTES:\n")
            f.write("  - These scripts add IPs to existing configuration\n")
            f.write("  - On Linux/macOS, IPs are temporary (lost on reboot)\n")
            f.write("  - For permanent config, use system network settings\n")
            f.write("  - Default adapter names are used (Ethernet/eth0/en0)\n")
            f.write("  - Edit scripts if your adapter name differs\n")
        
        return True, f"Created scripts for: {', '.join(scripts_created)}"
        
    except Exception as e:
        return False, str(e)


def export_device_list_csv(devices: List[Device], filepath: str) -> Tuple[bool, str]:
    """
    Export device list to CSV (cross-platform compatible)
    
    Args:
        devices: List of devices
        filepath: Output CSV file path
        
    Returns:
        (success, error_message)
    """
    headers = [
        "IED Name", "IP Address", "Port", "Subnet Mask", 
        "Protocol", "Connected", "Last Update"
    ]
    
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for device in devices:
                row = [
                    device.config.name,
                    device.config.ip_address,
                    device.config.port,
                    "255.255.255.0",  # Default
                    device.config.device_type.value,
                    "Yes" if device.connected else "No",
                    device.last_update.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if device.last_update else "Never"
                ]
                writer.writerow(row)
        
        return True, f"Exported {len(devices)} device(s)"
        
    except Exception as e:
        return False, str(e)


def export_goose_details_csv(scd_path: str, filepath: str) -> Tuple[bool, str]:
    """
    Parse SCD and export GOOSE details to CSV
    
    Args:
        scd_path: Path to SCD file
        filepath: Output CSV file path
        
    Returns:
        (success, error_message)
    """
    if not scd_path or not os.path.exists(scd_path):
        return False, "SCD file not found or not specified"
        
    try:
        source_path = scd_path
        temp_dir = None

        if ArchiveExtractor.is_archive(scd_path):
            temp_dir = tempfile.TemporaryDirectory()
            archive_files = ArchiveExtractor.list_files(scd_path)

            # Prefer SCL files in order: .scd, .cid, .icd, .xml
            def scl_rank(name: str) -> int:
                lname = name.lower()
                if lname.endswith('.scd'):
                    return 0
                if lname.endswith('.cid'):
                    return 1
                if lname.endswith('.icd'):
                    return 2
                if lname.endswith('.xml'):
                    return 3
                return 99

            candidates = [f for f in archive_files if f.lower().endswith(('.scd', '.cid', '.icd', '.xml'))]
            if candidates:
                candidates.sort(key=scl_rank)
                chosen = candidates[0]
                source_path = ArchiveExtractor.extract_file(scd_path, chosen, temp_dir.name)
            else:
                # Fallback: extract all and search for SCL by extension or XML root tag
                ArchiveExtractor.extract_all(scd_path, temp_dir.name)

                def find_scl_file(root_dir: str) -> str:
                    # First pass: extension-based
                    for base, _, files in os.walk(root_dir):
                        for fname in files:
                            if fname.lower().endswith(('.scd', '.cid', '.icd', '.xml')):
                                return os.path.join(base, fname)

                    # Second pass: XML root tag match (SCL)
                    for base, _, files in os.walk(root_dir):
                        for fname in files:
                            file_path = os.path.join(base, fname)
                            try:
                                tree = ET.parse(file_path)
                                root = tree.getroot()
                                if root.tag.endswith('SCL'):
                                    return file_path
                            except Exception:
                                continue
                    return ""

                detected = find_scl_file(temp_dir.name)
                if not detected:
                    return False, "No SCL files found in archive"
                source_path = detected

        parser = SCDParser(source_path)
        goose_map = parser.extract_goose_map()
        
        headers = [
            "Item", "Subnetwork Name", "Mapping Type",
            "Source IED Name", "Source AP", "Source LDevice",
            "Source IP Address", "Source Subnet", "Source MAC Address", "Source VLAN-ID",
            "Source VLAN Priority", "Source APPID", "Source MinTime", "Source MaxTime",
            "Source DataSet", "DataSet Size", "Source ConfRev", "Source ControlBlock",
            "Source GoID", "Source FixedOffs", "Source LogicalNode", "Source DataAttribute", "Source Tag",
            "Destination IED Name", "Destination AP", "Destination LDevice",
            "Destination IP Address", "Destination Subnet", "Destination MAC Address",
            "Destination LogicalNode", "Destination ServiceType", "Destination IntAddr", "Destination Tag"
        ]
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for i, entry in enumerate(goose_map):
                row = entry.copy()
                row['Item'] = i + 1
                row['Subnetwork Name'] = entry.get('Source Subnet', '')
                
                # Fill missing keys
                for h in headers:
                    if h not in row:
                        row[h] = ""
                
                writer.writerow(row)
        
        return True, f"Exported {len(goose_map)} GOOSE mapping(s)"
        
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if 'temp_dir' in locals() and temp_dir is not None:
                temp_dir.cleanup()
        except Exception:
            pass


def export_diagnostics_report(devices: List[Device], filepath: str) -> Tuple[bool, str]:
    """
    Export comprehensive diagnostics report (cross-platform)
    
    Args:
        devices: List of devices
        filepath: Output text file path
        
    Returns:
        (success, error_message)
    """
    try:
        with open(filepath, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("SCADA SCOUT - DIAGNOSTICS REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            # System information
            platform_info = NetworkUtils.get_platform_info()
            f.write("SYSTEM INFORMATION\n")
            f.write("-" * 80 + "\n")
            f.write(f"Operating System: {platform_info['system']} {platform_info['release']}\n")
            f.write(f"Version: {platform_info['version']}\n")
            f.write(f"Architecture: {platform_info['machine']}\n")
            f.write(f"Hostname: {platform_info['hostname']}\n")
            f.write(f"Local IP: {platform_info['local_ip']}\n")
            f.write("\n")
            
            # Network interfaces
            interfaces = NetworkUtils.get_network_interfaces()
            f.write("NETWORK INTERFACES\n")
            f.write("-" * 80 + "\n")
            for iface in interfaces:
                f.write(f"Interface: {iface.name}\n")
                f.write(f"  IP: {iface.ip_address}\n")
                f.write(f"  Netmask: {iface.netmask}\n")
                if iface.mac_address:
                    f.write(f"  MAC: {iface.mac_address}\n")
                f.write(f"  Status: {'UP' if iface.is_up else 'DOWN'}\n")
                f.write("\n")
            
            # Device list
            f.write("CONFIGURED DEVICES\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Devices: {len(devices)}\n")
            f.write(f"Connected: {sum(1 for d in devices if d.connected)}\n")
            f.write(f"Disconnected: {sum(1 for d in devices if not d.connected)}\n")
            f.write("\n")
            
            for device in devices:
                f.write(f"Device: {device.config.name}\n")
                f.write(f"  Type: {device.config.device_type.value}\n")
                f.write(f"  Address: {device.config.ip_address}:{device.config.port}\n")
                f.write(f"  Status: {'CONNECTED' if device.connected else 'DISCONNECTED'}\n")
                
                if device.connected:
                    # Connectivity test
                    reachable = NetworkUtils.check_tcp_port(
                        device.config.ip_address,
                        device.config.port,
                        timeout=1.0
                    )
                    f.write(f"  Port Check: {'OPEN' if reachable else 'CLOSED/FILTERED'}\n")
                
                if device.last_update:
                    f.write(f"  Last Update: {device.last_update.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
                
                # Count signals
                if device.root_node:
                    signal_count = count_signals_recursive(device.root_node)
                    f.write(f"  Signals: {signal_count}\n")
                
                f.write("\n")
            
            f.write("=" * 80 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 80 + "\n")
        
        return True, "Diagnostics report generated"
        
    except Exception as e:
        return False, str(e)


def count_signals_recursive(node) -> int:
    """Recursively count signals in node tree"""
    count = len(node.signals)
    for child in node.children:
        count += count_signals_recursive(child)
    return count
