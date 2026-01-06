import csv
import os
from typing import List, Dict
from src.models.device_models import Device
from src.core.scd_parser import SCDParser

def export_network_config_bat(devices: List[Device], filepath: str, adapter_name: str = "Ethernet"):
    """
    Generates a Windows BAT file to add IP addresses to a network adapter.
    """
    try:
        with open(filepath, 'w', newline='\r\n') as f:
            f.write("@echo off\n")
            f.write(f"echo Configuring IPs for adapter '{adapter_name}'...\n")
            f.write("REM Run as Administrator\n\n")
            
            for device in devices:
                ip = device.config.ip_address
                # Skip localhost or invalid IPs for production scripts usually, 
                # but user wants 'all ips'.
                if ip == "127.0.0.1" or not ip:
                    continue
                
                # Assuming /24 subnet for simplicity if unknown, or we could store mask in config later.
                # Standard netsh: netsh interface ip add address "Ethernet" 192.168.1.10 255.255.255.0
                cmd = f'netsh interface ip add address "{adapter_name}" {ip} 255.255.255.0\n'
                f.write(cmd)
            
            f.write("\necho Done.\n")
            f.write("pause\n")
        return True, ""
    except Exception as e:
        return False, str(e)

def export_device_list_csv(devices: List[Device], filepath: str):
    """
    Exports device list to CSV.
    """
    headers = ["IED Name", "IP Address", "Subnet Mask", "Subnetwork", "Access Point", "Protocol", "Redundancy Protocol"]
    
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for device in devices:
                # We mainly have Name and IP in runtime DeviceConfig.
                # To get Subnet/AP/etc., we might need to look back at SCD or store it.
                # For now, we fill what we have.
                
                row = [
                    device.config.name,
                    device.config.ip_address,
                    "255.255.255.0", # Default/Unknown
                    "", # Subnetwork unknown in runtime config
                    "", # Access Point unknown in runtime config
                    device.config.device_type.value,
                    "None"
                ]
                writer.writerow(row)
        return True, ""
    except Exception as e:
        return False, str(e)

def export_goose_details_csv(scd_path: str, filepath: str):
    """
    Parses the SCD again to extract GOOSE details and exports to CSV.
    """
    if not scd_path or not os.path.exists(scd_path):
        return False, "SCD file not found or not specified."
        
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
                # Flatten/Map entry to headers
                # Our extract_goose_map returns keys matching most headers directly.
                # We need to add 'Item' and empty Destination fields (as SCD parsing for DESTINATION is hard/not implemented yet)
                
                row = entry.copy()
                row['Item'] = i + 1
                row['Subnetwork Name'] = entry.get('Source Subnet', '') # Shared
                
                # Fill missing keys to avoid DictWriter error
                for h in headers:
                    if h not in row:
                        row[h] = ""
                
                writer.writerow(row)
        return True, ""
    except Exception as e:
        return False, str(e)
