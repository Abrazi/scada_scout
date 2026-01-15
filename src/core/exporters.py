"""
Cross-platform exporters for network configuration and device data
"""
import csv
import os
import platform
from typing import List, Dict, Tuple
from src.models.device_models import Device
from src.core.scd_parser import SCDParser
from src.utils.network_utils import NetworkScriptGenerator, NetworkUtils


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
        parser = SCDParser(scd_path)
        goose_map = parser.extract_goose_map()
        
        headers = [
            "Item", "Subnetwork Name", "Source IED Name", "Source AP", "Source LDevice",
            "Source IP Address", "Source Subnet", "Source MAC Address", "Source VLAN-ID",
            "Source APPID", "Source MinTime", "Source MaxTime", "Source DataSet",
            "DataSet Size", "Source ConfRev", "Source ControlBlock",
            "Source LogicalNode", "Source DataAttribute", "Source Tag",
            "Destination IED Name", "Destination AP", "Destination LDevice",
            "Destination IP Address", "Destination Subnet", "Destination MAC Address",
            "Destination LogicalNode", "Destination ServiceType", "Destination Tag"
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
