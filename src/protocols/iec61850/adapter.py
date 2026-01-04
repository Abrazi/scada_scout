from typing import Optional, Any
from enum import Enum
import logging
from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Node, Signal, SignalType, SignalQuality
from src.core.scd_parser import SCDParser

# Placeholder for libiec61850 import in a real app
# import iec61850 

logger = logging.getLogger(__name__)

class VendorProfile(Enum):
    AUTO = "Auto"
    STANDARD = "Standard"
    ABB = "ABB"
    SIEMENS = "Siemens"
    SCHNEIDER = "Schneider"
    SEL = "SEL"
    GE = "GE"
    NR_ELECTRIC = "NRElectric"

# Internal Mock Connection (reused)
class IedConnection:
    def __init__(self):
        self._connected = False

    def Connect(self, ip, port):
        self._connected = True

    def Close(self):
        self._connected = False
        
    def ReadValue(self, url: str, fc: str):
         return 0

    def GetServerDirectory(self, detail=False):
        return ["IED1_LD0"] # Fallback

    def GetLogicalDeviceDirectory(self, ld):
        return ["LLN0"]

    def GetLogicalNodeDirectory(self, ln):
        return []

class IEC61850Adapter(BaseProtocol):
    """
    Adapter for IEC 61850 Client communication.
    Supports Online Discovery and Offline SCD Import.
    Detects Vendor Profiles for compatibility quirks.
    """

    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._connection = IedConnection()
        self._map_signal_to_fc = {} 
        self.vendor_profile = VendorProfile.AUTO
        self.quirks = {}

    def connect(self) -> bool:
        """Establishes MMS connection to the IED."""
        try:
            # 1. Detect Vendor from Config or Name (Pre-connect)
            self._detect_vendor_pre_connect()
            
            logger.info(f"Connecting to {self.config.ip_address} (Vendor: {self.vendor_profile.value})...")
            self._connection.Connect(self.config.ip_address, self.config.port)
            
            # 2. Detect Vendor from Online Data (Post-connect)
            # self._detect_vendor_online()
            
            return True
        except Exception as e:
            logger.error(f"IEC61850 Connection failed: {e}")
            return False

    def disconnect(self):
        self._connection.Close()

    def discover(self) -> Node:
        """
        Browses IED. Prefer SCD file if available, else Online Discovery.
        """
        if self.config.scd_file_path:
            logger.info(f"Using SCD file for discovery: {self.config.scd_file_path}")
            return self._discover_offline()
        else:
            logger.info("Using Online Discovery")
            return self._discover_online()

    def _discover_offline(self) -> Node:
        """Uses SCDParser to build the tree."""
        try:
            parser = SCDParser(self.config.scd_file_path)
            # Find IED in SCD that matches our config name, or take the first one
            root = parser.get_structure(ied_name=None)
            
            # Post-process: Update addresses to match what we expect for MMS
            # The parser gives us relative structure. MMS addresses are LD/LN.DO.DA
            # We need to walk the tree to fix addresses if needed, but for now 
            # SCDParser tries to set reasonable partial paths.
            
            return root
        except Exception as e:
            logger.error(f"Offline discovery failed: {e}")
            return Node(name="Error_SCD_Parse")

    def _discover_online(self) -> Node:
        """Recursive online browse (Mocked for now)."""
        root = Node(name=self.config.name, description="IEC 61850 IED")
        
        # Simplified Mock for demonstration
        # In a real app, this reuses the logic we wrote previously
        ld_node = Node(name=f"{self.config.name}_LD0", description="Logical Device")
        root.children.append(ld_node)
        
        ln_node = Node(name="LLN0", description="Logical Node")
        ld_node.children.append(ln_node)
        
        # Add some vendor specific dummy data based on profile
        if self.vendor_profile == VendorProfile.ABB:
             ln_node.children.append(Node(name="ABB_Specific_DO", description="Vendor Ext"))
        elif self.vendor_profile == VendorProfile.SIEMENS:
             ln_node.children.append(Node(name="Siemens_Specific_DO", description="Vendor Ext"))

        return root

    def read_signal(self, signal: Signal) -> Signal:
        # Mock reading
        return signal

    def select(self, signal: Signal) -> bool:
        """Simulates Select operation."""
        logger.info(f"IEC61850: Selecting {signal.address}...")
        # Mock success
        return True

    def operate(self, signal: Signal, value: Any) -> bool:
        """Simulates Operate operation."""
        logger.info(f"IEC61850: Operating {signal.address} with value {value}...")
        
        # Simulate feedback by updating the signal value locally
        # In real life, we wait for the report or poll next cycle
        signal.value = value
        if self._data_callback:
            self._data_callback(signal)
            
        return True

    def cancel(self, signal: Signal) -> bool:
        """Simulates Cancel operation."""
        logger.info(f"IEC61850: Canceling selection on {signal.address}...")
        return True

    def _detect_vendor_pre_connect(self):
        """Guess vendor from name or metadata."""
        name = self.config.name.upper()
        if "ABB" in name or "RELION" in name:
            self.vendor_profile = VendorProfile.ABB
        elif "SIEMENS" in name or "SIPROTEC" in name:
            self.vendor_profile = VendorProfile.SIEMENS
        elif "SCHNEIDER" in name or "EASERGY" in name:
            self.vendor_profile = VendorProfile.SCHNEIDER
        elif "SEL" in name:
            self.vendor_profile = VendorProfile.SEL
        
        self._apply_quirks()

    def _apply_quirks(self):
        """Set flags based on reference implementation logic."""
        if self.vendor_profile == VendorProfile.ABB:
            self.quirks = {"origin_in_sbo": False, "check_in_sbo": True, "read_delay": 150}
        elif self.vendor_profile == VendorProfile.SIEMENS:
            self.quirks = {"origin_in_sbo": True, "check_in_sbo": True, "read_delay": 100}
        # ... map others from C# code
