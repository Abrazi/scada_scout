"""
SCD Project Loader - Extracts IED devices from SCD files for IEC 61850 server instantiation.

This module parses IEC 61850 SCD (Substation Configuration Description) files,
extracts all defined IED (Intelligent Electronic Device) configurations including
IP addresses and communication parameters, and prepares them for instantiation
as IEC 61850 servers within the application.
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class IEDNetworkConfig:
    """Network configuration for an IED extracted from SCD Communication section."""
    ied_name: str
    ip_address: str
    subnet_mask: str = "255.255.255.0"
    gateway: str = "0.0.0.0"
    ap_name: str = ""  # Access Point name
    port: int = 102  # Default MMS port
    subnet_name: str = ""  # SubNetwork name from SCD


@dataclass
class IEDDefinition:
    """Complete IED definition extracted from SCD."""
    name: str
    desc: str
    manufacturer: str
    ied_type: str
    network_config: Optional[IEDNetworkConfig]
    access_points: List[str]
    logical_devices: List[str]
    
    def __repr__(self):
        return f"IED({self.name}, IP={self.network_config.ip_address if self.network_config else 'N/A'})"


class SCDProjectLoader:
    """
    Parses SCD files and extracts IED definitions with network configurations.
    
    The SCD file contains:
    - IED section: Defines IEDs with their data models
    - Communication section: Maps IEDs to IP addresses
    - DataTypeTemplates: Type definitions (not used here)
    
    This loader focuses on extracting IED names, IP addresses, and basic
    configuration needed to instantiate IEC 61850 servers.
    """
    
    def __init__(self, scd_file_path: str):
        """
        Initialize loader with path to SCD file.
        
        Args:
            scd_file_path: Path to .scd file
        """
        self.scd_file_path = scd_file_path
        self.tree = None
        self.root = None
        self.ns = {}
        self._parse()
        
    def _parse(self):
        """Parse SCD file and detect namespace."""
        try:
            path = Path(self.scd_file_path)
            if not path.exists():
                raise FileNotFoundError(f"SCD file not found: {self.scd_file_path}")
                
            file_size = path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # Warn for files > 100MB
                logger.warning(f"Large SCD file detected: {file_size / (1024*1024):.1f} MB")
                
            logger.info(f"Parsing SCD file: {self.scd_file_path}")
            
            # Use iterparse for large files to avoid full DOM load
            # But we need the tree for XPath queries, so parse normally
            self.tree = ET.parse(self.scd_file_path)
            self.root = self.tree.getroot()
            
            # Detect namespace
            if '}' in self.root.tag:
                ns_uri = self.root.tag.split('}')[0].strip('{')
                self.ns = {'scl': ns_uri}
            else:
                self.ns = {}
                
            logger.info("SCD parsing complete")
            
        except Exception as e:
            logger.error(f"Failed to parse SCD file: {e}")
            raise
            
    def extract_ieds(self, subnet_name: Optional[str] = None) -> List[IEDDefinition]:
        """
        Extract all IED definitions from the SCD file.
        
        Args:
            subnet_name: Optional SubNetwork name to filter IPs. If None, uses first IP found.
        
        Returns:
            List of IEDDefinition objects with network configurations
        """
        if self.root is None:
            logger.error("SCD not parsed, cannot extract IEDs")
            return []
            
        ieds = []
        
        # First, build network config map from Communication section
        network_map = self._parse_communication_section(subnet_name)
        
        # Find all IED elements
        ied_elements = self.root.findall(".//scl:IED", self.ns)
        if not ied_elements:
            ied_elements = self.root.findall(".//IED")
            
        logger.info(f"Found {len(ied_elements)} IED(s) in SCD")
        
        for ied_elem in ied_elements:
            try:
                ied = self._parse_ied_element(ied_elem, network_map)
                ieds.append(ied)
                logger.info(f"  - {ied.name}: {ied.desc} @ {ied.network_config.ip_address if ied.network_config else 'NO_IP'}")
            except Exception as e:
                logger.error(f"Failed to parse IED element: {e}")
                
        return ieds
        
    def _parse_communication_section(self, subnet_filter: Optional[str] = None) -> Dict[str, IEDNetworkConfig]:
        """
        Parse Communication section to extract IP address mappings.
        
        Structure:
        <Communication>
          <SubNetwork name="...">
            <ConnectedAP iedName="IED1" apName="AP1">
              <Address>
                <P type="IP">192.168.1.10</P>
                <P type="IP-SUBNET">255.255.255.0</P>
                <P type="IP-GATEWAY">192.168.1.1</P>
              </Address>
            </ConnectedAP>
          </SubNetwork>
        </Communication>
        
        Args:
            subnet_filter: Optional SubNetwork name to filter by
        
        Returns:
            Dictionary mapping IED name to network configuration
        """
        network_map = {}
        
        # Find Communication section
        comm_section = self.root.find(".//scl:Communication", self.ns)
        if comm_section is None:
            comm_section = self.root.find(".//Communication")
            
        if comm_section is None:
            logger.warning("No Communication section found in SCD")
            return network_map
            
        # Find all SubNetwork elements to track which subnet each IED belongs to
        subnets = comm_section.findall("scl:SubNetwork", self.ns)
        if not subnets:
            subnets = comm_section.findall("SubNetwork")
            
        for subnet in subnets:
            subnet_name = subnet.get("name", "")
            
            # If subnet_filter specified, skip other subnets
            if subnet_filter and subnet_name != subnet_filter:
                continue
                
            # Find ConnectedAP elements within this subnet
            connected_aps = subnet.findall("scl:ConnectedAP", self.ns)
            if not connected_aps:
                connected_aps = subnet.findall("ConnectedAP")
                
            for cap in connected_aps:
                ied_name = cap.get("iedName")
                ap_name = cap.get("apName", "")
            
                if not ied_name:
                    continue
                    
                # Extract address parameters
                address_elem = cap.find("scl:Address", self.ns)
                if address_elem is None:
                    address_elem = cap.find("Address")
                    
                if address_elem is None:
                    logger.warning(f"No Address found for IED {ied_name}")
                    continue
                    
                # Parse P elements for IP, subnet, gateway
                ip_address = None
                subnet_mask = "255.255.255.0"
                gateway = "0.0.0.0"
                port = 102  # Default MMS port
                
                p_elements = address_elem.findall("scl:P", self.ns)
                if not p_elements:
                    p_elements = address_elem.findall("P")
                    
                for p in p_elements:
                    p_type = p.get("type", "")
                    p_value = p.text
                    
                    if p_type == "IP":
                        ip_address = p_value
                    elif p_type == "IP-SUBNET":
                        subnet_mask = p_value
                    elif p_type == "IP-GATEWAY":
                        gateway = p_value
                    elif p_type == "OSI-TSEL":
                        # TSEL can encode port in some implementations
                        pass
                    elif p_type == "OSI-PSEL":
                        pass
                    elif p_type == "OSI-SSEL":
                        pass
                        
                if ip_address:
                    # Only add if IED not already in map (first occurrence wins)
                    # Or if we're filtering by subnet
                    if ied_name not in network_map or subnet_filter:
                        network_map[ied_name] = IEDNetworkConfig(
                            ied_name=ied_name,
                            ip_address=ip_address,
                            subnet_mask=subnet_mask,
                            gateway=gateway,
                            ap_name=ap_name,
                            port=port,
                            subnet_name=subnet_name
                        )
                
        logger.info(f"Parsed {len(network_map)} network configurations" + 
                   (f" from subnet '{subnet_filter}'" if subnet_filter else ""))
        return network_map
        
    def _parse_ied_element(self, ied_elem: ET.Element, 
                          network_map: Dict[str, IEDNetworkConfig]) -> IEDDefinition:
        """
        Parse single IED element into IEDDefinition.
        
        Args:
            ied_elem: XML element for IED
            network_map: Pre-parsed network configurations
            
        Returns:
            IEDDefinition object
        """
        name = ied_elem.get("name", "UNKNOWN")
        desc = ied_elem.get("desc", "")
        manufacturer = ied_elem.get("manufacturer", "")
        ied_type = ied_elem.get("type", "")
        
        # Get network config from map
        network_config = network_map.get(name)
        
        # Extract access points
        access_points = []
        ap_elements = ied_elem.findall("scl:AccessPoint", self.ns)
        if not ap_elements:
            ap_elements = ied_elem.findall("AccessPoint")
            
        for ap in ap_elements:
            ap_name = ap.get("name", "")
            if ap_name:
                access_points.append(ap_name)
                
        # Extract logical devices
        logical_devices = []
        # LDevices can be under AccessPoint/Server
        ld_elements = ied_elem.findall(".//scl:LDevice", self.ns)
        if not ld_elements:
            ld_elements = ied_elem.findall(".//LDevice")
            
        for ld in ld_elements:
            ld_inst = ld.get("inst", "")
            if ld_inst:
                logical_devices.append(ld_inst)
                
        return IEDDefinition(
            name=name,
            desc=desc,
            manufacturer=manufacturer,
            ied_type=ied_type,
            network_config=network_config,
            access_points=access_points,
            logical_devices=logical_devices
        )
        
    def get_subnetworks(self) -> List[Tuple[str, int]]:
        """
        Get list of all SubNetworks defined in Communication section.
        
        Returns:
            List of tuples (subnet_name, ied_count) for each SubNetwork
        """
        if self.root is None:
            return []
            
        subnets = []
        
        # Find Communication section
        comm_section = self.root.find(".//scl:Communication", self.ns)
        if comm_section is None:
            comm_section = self.root.find(".//Communication")
            
        if comm_section is None:
            return []
            
        # Find all SubNetwork elements
        subnet_elements = comm_section.findall("scl:SubNetwork", self.ns)
        if not subnet_elements:
            subnet_elements = comm_section.findall("SubNetwork")
            
        for subnet in subnet_elements:
            subnet_name = subnet.get("name", "Unnamed")
            
            # Count ConnectedAP elements (IEDs) in this subnet
            connected_aps = subnet.findall("scl:ConnectedAP", self.ns)
            if not connected_aps:
                connected_aps = subnet.findall("ConnectedAP")
                
            ied_count = len(connected_aps)
            subnets.append((subnet_name, ied_count))
            
        return subnets
        
    def get_ied_by_name(self, ied_name: str, subnet_name: Optional[str] = None) -> Optional[IEDDefinition]:
        """
        Get specific IED definition by name.
        
        Args:
            ied_name: Name of IED to retrieve
            subnet_name: Optional SubNetwork to use for IP address
            
        Returns:
            IEDDefinition if found, None otherwise
        """
        ieds = self.extract_ieds(subnet_name=subnet_name)
        for ied in ieds:
            if ied.name == ied_name:
                return ied
        return None
