from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime
import logging
import time

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Node, Signal, SignalType, SignalQuality
from src.core.scd_parser import SCDParser

# Import the ctypes wrapper for libiec61850
from . import iec61850_wrapper as iec61850
from .control_models import ControlObjectRuntime, ControlModel, ControlState

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

class IEC61850Adapter(BaseProtocol):
    """
    Real implementation using libiec61850 (via pyiec61850 bindings).
    """

    def __init__(self, config: DeviceConfig, event_logger=None):
        super().__init__(config)
        self.connection = None
        self.connected = False
        self.event_logger = event_logger
        
        if self.event_logger:
            self.event_logger.info("IEC61850Adapter", f"Initialized for {config.ip_address}:{config.port}")
        self._last_read_times = {}
        self.controls: Dict[str, ControlObjectRuntime] = {} # Key: DO Object Reference
        
    def connect(self) -> bool:
        """Establish connection to the IED with comprehensive diagnostics."""
        if self.event_logger:
            self.event_logger.info("Connection", f"=== Starting connection to {self.config.ip_address}:{self.config.port} ===")
        
        # Step 1: Ping check
        if self.event_logger:
            self.event_logger.info("Connection", f"Step 1/4: Checking network reachability (ping {self.config.ip_address})...")
        
        ping_success = self._ping_device()
        
        if not ping_success:
            if self.event_logger:
                self.event_logger.error("Connection", f"❌ Ping FAILED - Device {self.config.ip_address} is not reachable")
            logger.error(f"Ping failed for {self.config.ip_address}")
            self.connected = False
            return False
        
        if self.event_logger:
            self.event_logger.info("Connection", f"✓ Ping successful - Device is reachable")
        
        # Step 2: TCP port check
        if self.event_logger:
            self.event_logger.info("Connection", f"Step 2/4: Checking TCP port {self.config.port}...")
        
        port_open = self._check_port()
        
        if not port_open:
            if self.event_logger:
                self.event_logger.warning("Connection", f"⚠ Port {self.config.port} may not be open (continuing anyway)")
        else:
            if self.event_logger:
                self.event_logger.info("Connection", f"✓ Port {self.config.port} is reachable")
        
        # Step 3: IEC 61850 connection attempt
        # Check if library is loaded
        if not iec61850.is_library_loaded():
            if self.event_logger:
                self.event_logger.error("Connection", f"Step 3/4: Library not loaded - {iec61850.get_load_error()}")
            self.connected = False
            return False
        
        try:
            if self.event_logger:
                self.event_logger.info("Connection", f"Step 3/4: Establishing IEC 61850 connection...")
            
            logger.info(f"Connecting to {self.config.ip_address} using libiec61850...")
            self.connection = iec61850.IedConnection_create()
            
            if self.event_logger:
                self.event_logger.transaction("IEC61850", f"→ IedConnection_connect({self.config.ip_address}, {self.config.port})")
            
            error = iec61850.IedConnection_connect(
                self.connection,
                self.config.ip_address,
                self.config.port
            )
            
            if error != 0:
                error_msg = f"Connection error code: {error}"
                if self.event_logger:
                    self.event_logger.error("Connection", f"❌ IEC 61850 connection FAILED - {error_msg}")
                logger.error(f"Failed to connect: {error_msg}")
                iec61850.IedConnection_destroy(self.connection)
                self.connection = None
                self.connected = False
                return False
            
            self.connected = True
            if self.event_logger:
                self.event_logger.transaction("IEC61850", f"← Connection SUCCESS")
                self.event_logger.info("Connection", f"✓ IEC 61850 connection established")
                self.event_logger.info("Connection", f"Step 4/4: Connection ready for operations")
            
            logger.info("Connected successfully!")
            return True
            
        except Exception as e:
            if self.event_logger:
                self.event_logger.error("Connection", f"❌ Connection EXCEPTION: {e}")
            logger.error(f"Connection failed: {e}")
            self.connected = False
            if self.connection:
                try:
                    iec61850.IedConnection_destroy(self.connection)
                except Exception as e:
                    logger.debug(f"Error destroying connection: {e}")
                self.connection = None
            return False
    
    def _ping_device(self) -> bool:
        """Ping the device to check network reachability."""
        import subprocess
        import platform
        
        try:
            # Determine ping command based on OS
            is_windows = platform.system().lower() == 'windows'
            param = '-n' if is_windows else '-c'
            timeout_param = '-w' if is_windows else '-W'
            # Send 2 pings with 1 second timeout (1000ms on Windows, 1000ms on Unix)
            command = ['ping', param, '2', timeout_param, '1000', self.config.ip_address]
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.warning(f"Ping check failed with exception: {e}")
            # If ping fails, we'll try to connect anyway
            return True  # Don't block connection on ping failure
    
    def _check_port(self) -> bool:
        """Check if TCP port is reachable."""
        import socket
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.config.ip_address, self.config.port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.warning(f"Port check failed: {e}")
            return None

    def _connect_mock(self):
        time.sleep(0.5)
        self.connected = True
        logger.info("MOCK: Connected.")
        return None

    def _parse_mms_value(self, mms_val):
        """Helper to parse generic MmsValue* to (value, SignalType, error_msg)."""
        if not mms_val:
            return None, SignalType.ANALOG, "No MMS value returned"

        val_type = iec61850.MmsValue_getType(mms_val)
        
        # Check for data access error first
        if val_type == iec61850.MMS_DATA_ACCESS_ERROR:
            return None, SignalType.ANALOG, "Data Access Error"
        
        if val_type == iec61850.MMS_BOOLEAN:
            return iec61850.MmsValue_getBoolean(mms_val), SignalType.DOUBLE_BINARY, ""
            
        elif val_type in [iec61850.MMS_INTEGER, iec61850.MMS_UNSIGNED]:
            return iec61850.MmsValue_toInt32(mms_val), SignalType.ANALOG, ""
            
        elif val_type == iec61850.MMS_FLOAT:
            return iec61850.MmsValue_toFloat(mms_val), SignalType.ANALOG, ""
            
        elif val_type == iec61850.MMS_VISIBLE_STRING:
             return iec61850.MmsValue_toString(mms_val), SignalType.STATE, ""
             
        elif val_type == iec61850.MMS_BIT_STRING:
            size = iec61850.MmsValue_getBitStringSize(mms_val)
            val = 0
            for i in range(size):
                if iec61850.MmsValue_getBitStringBit(mms_val, i):
                    val |= (1 << i)
            return f"0x{val:X} ({size}b)", SignalType.BINARY, ""
            
        elif val_type == iec61850.MMS_UTC_TIME:
             ts = self._get_timestamp_from_mms(mms_val)
             if ts:
                 return ts.strftime("%H:%M:%S.%f")[:-3], SignalType.TIMESTAMP, ""
             else:
                 return None, SignalType.TIMESTAMP, "Invalid timestamp format"

        elif val_type == iec61850.MMS_STRUCTURE:
             return "[Structure]", SignalType.STATE, ""
             
        elif val_type == iec61850.MMS_ARRAY:
             size = iec61850.MmsValue_getArraySize(mms_val)
             return f"[Array[{size}]]", SignalType.STATE, ""
             
        else:
             return "[Complex Data]", SignalType.STATE, ""

    def disconnect(self):
        if self.connection:
            iec61850.IedConnection_close(self.connection)
            self._cleanup_connection()
        self.connected = False
        logger.info("Disconnected.")

    def _cleanup_connection(self):
        if self.connection:
            iec61850.IedConnection_destroy(self.connection)
            self.connection = None

    def discover(self) -> Node:
        """Discover device structure with event logging."""
        if self.event_logger:
            self.event_logger.info("Discovery", "=== Starting device discovery ===")
        
        # If SCD file is available and preferred, use it
        if self.config.scd_file_path and self.config.use_scd_discovery:
            if self.event_logger:
                self.event_logger.info("Discovery", f"Using SCD file: {self.config.scd_file_path}")
            logger.info(f"Using SCD file for discovery: {self.config.scd_file_path}")
            return self._discover_from_scd()
        
        # Otherwise, use online discovery
        if self.event_logger:
            self.event_logger.info("Discovery", "Using Online Discovery (querying device directly)")
        logger.info("Using Online Discovery")
        return self._discover_online()

    def _discover_from_scd(self) -> Node:
        """Uses SCDParser to build the tree."""
        try:
            parser = SCDParser(self.config.scd_file_path)
            # Find IED in SCD that matches our config name, or take the first one
            root = parser.get_structure(ied_name=self.config.name)
            return root
        except Exception as e:
            logger.error(f"Offline discovery failed: {e}")
            return Node(name="Error_SCD_Parse")

    def _recursive_browse_da(self, parent_path: str, parent_node: Node, fc_name: str, depth: int = 0):
        """Recursively browse Data Attributes to find leaves."""
        if depth > 5: # Safety limit
            return

        try:
            # Try to get children
            ret = iec61850.IedConnection_getDataDirectory(self.connection, parent_path)
            children = None
            if isinstance(ret, (list, tuple)):
                children = ret[0]
            else:
                children = ret
            
            child_names = []
            if children:
                child_names = self._extract_string_list(children)
                iec61850.LinkedList_destroy(children)
            
            if not child_names:
                # It's a leaf (or empty structure)
                # Add as signal
                # Determine access and type heuristics
                name = parent_path.split('.')[-1]
                access = "RW" if "ctlVal" in name or "Oper" in parent_path else "RO"
                
                sig_type = None
                if name in ["stVal", "general", "q"]: sig_type = SignalType.STATE
                elif name in ["mag", "f", "i"]: sig_type = SignalType.ANALOG
                elif name in ["t"]: sig_type = SignalType.TIMESTAMP
                elif "ctlVal" in name: sig_type = SignalType.BINARY
                
                parent_node.signals.append(Signal(
                    name=name,
                    address=parent_path,
                    signal_type=sig_type,
                    access=access,
                    description=f"FC={fc_name}"
                ))
                return

            # It has children, recurse
            for child in child_names:
                full_path = f"{parent_path}.{child}"
                
                # Optimization: If child is a known leaf type, don't recurse (save RTT)
                # But be careful not to miss nested structs.
                # Leaves: stVal, q, t, ctlVal, f, i, b, d, dU
                # Structs: mag, cVal, phsA, ...
                
                # If we are sure it's a leaf, add it directly.
                # But 'd' can be Description (leaf) or something else? Usually leaf.
                # Let's recurse unless we are very sure.
                # Actually, browsing everything is safer.
                
                # Create a sub-node in the tree? 
                # The user wants "leaves read". 
                # Usually we flatten the signals list under the DO, 
                # OR we create a tree structure.
                # The current UI expects signals in the DO node?
                # The SignalsView shows a tree. If we add signals to DO, they show up as leaves of DO.
                # If we want a hierarchy like DO -> mag -> f, we need Nodes for mag.
                
                # Check if we should create a Node or just flatten the name.
                # "mag.f" as signal name is common.
                # But "phsA.cVal.mag.f" is long.
                # Let's try to create intermediate nodes if it's a complex struct.
                
                # For now, let's flatten into the DO for simplicity, 
                # using dot notation for signal names: "mag.f"
                # But wait, _recursive_browse_da is called with parent_node (DO).
                # If we recurse, we can pass the SAME parent_node and append "child.grandchild" name?
                # Or create new Nodes?
                # Creating new Nodes is better for the Tree View.
                
                # Let's check if it's likely a leaf.
                is_likely_leaf = child in ["stVal", "q", "t", "ctlVal", "f", "i", "b", "d", "dU", "Check", "Test"]
                
                if is_likely_leaf:
                     # Add as signal
                    access = "RW" if "ctlVal" in child else "RO"
                    sig_type = None
                    if child in ["stVal", "general", "q"]: sig_type = SignalType.STATE
                    elif child in ["f", "i"]: sig_type = SignalType.ANALOG
                    elif child in ["t"]: sig_type = SignalType.TIMESTAMP
                    elif "ctlVal" in child: sig_type = SignalType.BINARY
                    
                    parent_node.signals.append(Signal(
                        name=child,
                        address=full_path,
                        signal_type=sig_type,
                        access=access,
                        description=f"FC={fc_name}"
                    ))
                else:
                    # It's likely a struct (mag, cVal, phsA, etc.)
                    # Create a sub-node
                    sub_node = Node(name=child, description="Structure")
                    parent_node.children.append(sub_node)
                    self._recursive_browse_da(full_path, sub_node, fc_name, depth + 1)
                    
                    # If sub_node ends up empty (no leaves found), maybe it WAS a leaf?
                    # But we handled the "no children" case at the start of the function.
                    # So if we are here, it HAD children.
                    # But if we failed to browse children?
                    if not sub_node.children and not sub_node.signals:
                        # Remove empty node
                        parent_node.children.remove(sub_node)
                        # Maybe add as signal?
                        parent_node.signals.append(Signal(
                            name=child,
                            address=full_path,
                            access="RO",
                            description=f"FC={fc_name} (Unknown)"
                        ))

        except Exception as e:
            # If error, assume leaf or access denied
            # self.event_logger.debug("Discovery", f"Browse error at {parent_path}: {e}")
            pass

    def _discover_online(self) -> Node:
        """Browse IED structure directly from the connected device."""
        if not iec61850.is_library_loaded() or not self.connection:
             if self.event_logger:
                 self.event_logger.error("Discovery", "Library missing or not connected - Cannot perform online discovery")
             return Node(name=self.config.name, description="Error: libiec61850 not available")

        root = Node(name=self.config.name, description="IEC 61850 IED (Online)")
        
        if self.event_logger:
            self.event_logger.info("Discovery", "Querying IED server directory...")
        
        try:
            # Get the server directory (Logical Devices)
            ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = None
            if isinstance(ret, (list, tuple)):
                if len(ret) > 0:
                    ld_list = ret[0]
            else:
                ld_list = ret
            
            if not ld_list:
                if self.event_logger:
                    self.event_logger.warning("Discovery", "No Logical Devices found")
                return root
            
            ld_names = self._extract_string_list(ld_list)
            
            if self.event_logger:
                self.event_logger.info("Discovery", f"Found {len(ld_names)} Logical Device(s): {', '.join(ld_names)}")
            
            # Update root name from first LD (Heuristic)
            if ld_names:
                # 1. Try to find common prefix
                import os
                if len(ld_names) > 1:
                    derived_name = os.path.commonprefix(ld_names)
                    if derived_name.endswith('_') or derived_name.endswith('/'):
                        derived_name = derived_name[:-1]
                    if not derived_name:
                         derived_name = ld_names[0]
                else:
                    derived_name = ld_names[0]

                # 2. Cleanup suffix
                import re
                derived_name = re.sub(r'[_\W]?(LD|CTRL|PROT)\d*$', '', derived_name, flags=re.IGNORECASE)
                if '/' in derived_name:
                    derived_name = derived_name.split('/')[0]
                if not derived_name:
                    derived_name = ld_names[0]
                    
                root.name = derived_name
            
            # Browse each Logical Device
            for ld_name in ld_names:
                ld_node = Node(name=ld_name, description="Logical Device")
                root.children.append(ld_node)
                
                # Try to read Name Plate (NamPlt) from LLN0
                # Usually LD/LLN0.NamPlt.vendor
                try:
                    vendor_path = f"{ld_name}/LLN0.NamPlt.vendor"
                    vendor_res = iec61850.IedConnection_readStringValue(self.connection, vendor_path, iec61850.IEC61850_FC_DC)
                    if isinstance(vendor_res, (list, tuple)) and vendor_res[1] == iec61850.IED_ERROR_OK:
                        vendor = vendor_res[0]
                        root.description = f"IED: {vendor}"
                        # If we have a vendor, maybe we can get a better name?
                        # But 'root.name' is used for the tree root.
                        if self.event_logger:
                            self.event_logger.info("Discovery", f"Found Vendor: {vendor}")
                except: pass

                # Get Logical Nodes for this LD
                try:
                    ret_ln = iec61850.IedConnection_getLogicalDeviceDirectory(self.connection, ld_name)
                    ln_list = ret_ln[0] if isinstance(ret_ln, (list, tuple)) else ret_ln
                    
                    if ln_list:
                        ln_names = self._extract_string_list(ln_list)
                        
                        for ln_name in ln_names:
                            full_ln_ref = f"{ld_name}/{ln_name}"
                            ln_node = Node(name=ln_name, description="Logical Node")
                            ld_node.children.append(ln_node)
                            
                            # Get Data Objects for this LN
                            try:
                                ret_do = iec61850.IedConnection_getLogicalNodeDirectory(
                                    self.connection,
                                    full_ln_ref,
                                    iec61850.ACSI_CLASS_DATA_OBJECT
                                )
                                do_list = ret_do[0] if isinstance(ret_do, (list, tuple)) else ret_do
                                
                                if do_list:
                                    do_names = self._extract_string_list(do_list)
                                    
                                    for do_name in do_names:
                                        do_node = Node(name=do_name, description="Data Object")
                                        ln_node.children.append(do_node)
                                        
                                        full_do_ref = f"{full_ln_ref}.{do_name}"
                                        
                                        # Browse Data Attributes by Functional Constraint
                                        fcs = [
                                            (iec61850.IEC61850_FC_ST, "ST"),
                                            (iec61850.IEC61850_FC_MX, "MX"),
                                            (iec61850.IEC61850_FC_CO, "CO"),
                                            (iec61850.IEC61850_FC_CF, "CF"), # Important for ctlModel
                                            (iec61850.IEC61850_FC_SP, "SP"),
                                            (iec61850.IEC61850_FC_DC, "DC"),
                                        ]
                                        
                                        found_signals = False
                                        is_control = False
                                        
                                        # First pass: Check for ctlModel (Heuristic for Control Object)
                                        try:
                                            # We try to read ctlModel directly first to see if it exists
                                            # Using FC=CF
                                            ctl_model_path = f"{full_do_ref}.ctlModel"
                                            # NOTE: we don't know if ctlModel is at DO level or deeper, usually DO level for standard LN
                                            # But let's check directory first to be safe, or just try reading it?
                                            # Reading it is faster than browsing if we guess right.
                                            
                                            # Let's browse CF first to find ctlModel
                                            ret_cf = iec61850.IedConnection_getDataDirectoryByFC(
                                                self.connection, full_do_ref, iec61850.IEC61850_FC_CF
                                            )
                                            cf_list = ret_cf[0] if isinstance(ret_cf, (list, tuple)) else ret_cf
                                            if cf_list:
                                                cf_names = self._extract_string_list(cf_list)
                                                if "ctlModel" in cf_names:
                                                    # FOUND A CONTROL OBJECT!
                                                    is_control = True
                                                    # Read the model
                                                    ctl_val = self._read_ctl_model_direct(ctl_model_path)
                                                    
                                                    # Create Runtime Object
                                                    ctrl_runtime = ControlObjectRuntime(object_reference=full_do_ref)
                                                    ctrl_runtime.update_from_ctl_model_int(ctl_val)
                                                    self.controls[full_do_ref] = ctrl_runtime
                                                    
                                                    if self.event_logger:
                                                        self.event_logger.info("Discovery", f"  Found Control: {do_name} (Model={ctrl_runtime.ctl_model.name})")
                                                    
                                                    do_node.description += f" [Control: {ctrl_runtime.ctl_model.name}]"
                                                    
                                                iec61850.LinkedList_destroy(cf_list)
                                        except Exception: 
                                            pass

                                        for fc_val, fc_name in fcs:
                                            try:
                                                ret_da = iec61850.IedConnection_getDataDirectoryByFC(
                                                    self.connection, full_do_ref, fc_val
                                                )
                                                da_list = ret_da[0] if isinstance(ret_da, (list, tuple)) else ret_da
                                                
                                                if da_list:
                                                    da_names = self._extract_string_list(da_list)
                                                    for da_name in da_names:
                                                        full_da_path = f"{full_do_ref}.{da_name}"
                                                        
                                                        # Special handling for ctlModel - we already handled it, but let's show it in tree
                                                        
                                                        # Check if leaf
                                                        if da_name in ["stVal", "q", "t", "ctlVal", "ctlModel"]:
                                                            access = "RO"
                                                            sig_type = None
                                                            
                                                            if da_name == "stVal": sig_type = SignalType.STATE
                                                            elif da_name == "t": sig_type = SignalType.TIMESTAMP
                                                            elif da_name == "ctlModel": sig_type = SignalType.STATE
                                                            elif "ctlVal" in da_name: # Handle top-level ctlVal if any
                                                                 if is_control:
                                                                     access = "RW"
                                                                     sig_type = SignalType.COMMAND
                                                            
                                                            do_node.signals.append(Signal(
                                                                name=da_name,
                                                                address=full_da_path,
                                                                signal_type=sig_type,
                                                                access=access,
                                                                description=f"FC={fc_name}"
                                                            ))
                                                        else:
                                                            # Recurse
                                                            sub_node = Node(name=da_name, description=f"FC={fc_name}")
                                                            do_node.children.append(sub_node)
                                                            self._recursive_browse_da(full_da_path, sub_node, fc_name)
                                                            
                                                            if not sub_node.children and not sub_node.signals:
                                                                do_node.children.remove(sub_node)
                                                                do_node.signals.append(Signal(
                                                                    name=da_name,
                                                                    address=full_da_path,
                                                                    access="RO",
                                                                    description=f"FC={fc_name}"
                                                                ))
                                                    
                                                    found_signals = True
                                                    iec61850.LinkedList_destroy(da_list)
                                            except: continue
                                        
                                        if not found_signals:
                                            # Fallback generic browse
                                            try:
                                                ret_da = iec61850.IedConnection_getDataDirectory(self.connection, full_do_ref)
                                                da_list = ret_da[0] if isinstance(ret_da, (list, tuple)) else ret_da
                                                if da_list:
                                                    da_names = self._extract_string_list(da_list)
                                                    for da_name in da_names:
                                                        do_node.signals.append(Signal(
                                                            name=da_name, 
                                                            address=f"{full_do_ref}.{da_name}",
                                                            access="RO"
                                                        ))
                                                    iec61850.LinkedList_destroy(da_list)
                                            except: pass
                                            
                            except Exception: pass
                    
                    try: iec61850.LinkedList_destroy(ln_list)
                    except: pass
                        
                except Exception: pass
            
            try: iec61850.LinkedList_destroy(ld_list)
            except: pass
            
            if self.event_logger:
                self.event_logger.info("Discovery", f"✓ Online discovery complete")
            
            return root
            
        except Exception as e:
            if self.event_logger:
                self.event_logger.error("Discovery", f"Online discovery failed: {e}")
            logger.error(f"Online discovery failed: {e}")
            root.children.append(Node(name="Error", description=str(e)))
            return root

    def _read_ctl_model_direct(self, ctl_model_path: str) -> int:
        """Helper to read ctlModel during discovery."""
        try:
             val, err = iec61850.IedConnection_readInt32Value(
                 self.connection, ctl_model_path, iec61850.IEC61850_FC_CF
             )
             if err == iec61850.IED_ERROR_OK:
                 return val
        except Exception:
            pass
        return 1 # Default to Direct Normal if cannot read

    def _extract_string_list(self, linked_list) -> list:
        """
        Extract strings from a ctypes LinkedList.
        Uses the helper function from iec61850_wrapper.
        """
        if not linked_list:
            return []
        
        try:
            return iec61850.LinkedList_toStringList(linked_list)
        except Exception as e:
            logger.warning(f"LinkedList extraction failed: {e}")
            return []

    def _get_timestamp_from_mms(self, mms_val):
        """Helper to extract Python datetime from MmsValue."""
        if not mms_val:
            return None
        try:
            mms_type = iec61850.MmsValue_getType(mms_val)
            if mms_type == iec61850.MMS_UTC_TIME:
                unix_ts = iec61850.MmsValue_toUnixTimestamp(mms_val)
                # handle both float and int unix timestamps
                return datetime.fromtimestamp(unix_ts)
        except (ValueError, OSError, OverflowError):
             logger.debug(f"Failed to parse UTC time from MMS value")
        return None

    def read_signal(self, signal: Signal) -> Signal:
        """Read a single signal value from the IED."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ READ {signal.address}")
            
        if not self.connected:
            signal.quality = SignalQuality.NOT_CONNECTED
            if self.event_logger:
                self.event_logger.warning("IEC61850", f"← NOT CONNECTED (Internal State)")
            self._emit_update(signal) # Emit even if failed
            return signal

        if self.connection:
            # Check actual connection state
            state = iec61850.IedConnection_getState(self.connection)
            if state != iec61850.IED_STATE_CONNECTED:
                self.connected = False
                logger.warning(f"Connection lost detected during read for {self.config.ip_address} (State: {state})")
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← CONNECTION LOST (State: {state})")
                signal.quality = SignalQuality.NOT_CONNECTED
                self._emit_update(signal)
                return signal

        # Read from actual IED using correct pyiec61850 API
        try:
            # The address format from SCD is: "LD/LN.DO.DA"
            # But for reading we need the full path with LD prefix
            # Example: address might be "XCBR1.Pos.stVal", need to prepend LD
            address = signal.address
            
            # Clean up address if it has duplicated LD/LD prefix
            # This happens because SCD parser might add LD prefix, and then Adapter adds it again or similar.
            # User reported "GPS01ECB01CB1/GPS01ECB01CB1/XCBR1.Beh.stVal" -> Invalid.
            parts = address.split('/')
            if len(parts) >= 3 and parts[0] == parts[1]:
                # GPS/GPS/LN.DO... -> GPS/LN.DO...
                address = f"{parts[0]}/{'/'.join(parts[2:])}"
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"  Corrected address: {signal.address} -> {address}")
            
            # If address doesn't contain '/', it's missing LD - we need to find it
            if '/' not in address:
                # Try to prepend the IED name or LD name from config
                # Assuming config.name is the IED name
                # We need the Logical Device name. Often IEDName + "LD0" or similar.
                # But without knowing the LD structure, we can't guess. 
                # Hopefully the new SCDParser fix resolves the generation of these addresses.
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← INVALID ADDRESS: {address} (missing LD/)")
                signal.quality = SignalQuality.INVALID
                return signal
            
            # Special handling for Control attributes (SBO, Oper, Cancel)
            # These are often Write-Only or return specific structures.
            # Reading them as standard Data Attributes might fail.
            if any(x in address for x in [".SBO", ".SBOw", ".Oper", ".Cancel"]):
                 # Should we try to read them? 
                 # Maybe with FC=CO?
                 pass 
            
            # Common functional constraints to try
            # Map string FC to constant
            fc_map = {
                "ST": iec61850.IEC61850_FC_ST,
                "MX": iec61850.IEC61850_FC_MX,
                "CO": iec61850.IEC61850_FC_CO,
                "SP": iec61850.IEC61850_FC_SP,
                "CF": iec61850.IEC61850_FC_CF,
                "DC": iec61850.IEC61850_FC_DC,
                "SG": iec61850.IEC61850_FC_SG, 
                "SE": iec61850.IEC61850_FC_SE,
                "SV": iec61850.IEC61850_FC_SV
            }

            fcs_to_try = []
            
            # 1. OPTIMIZATION: If Signal has specific FC, use ONLY that one.
            if getattr(signal, 'fc', None) and signal.fc in fc_map:
                 fcs_to_try.append((signal.fc, fc_map[signal.fc]))
            else:
                # Intelligent FC selection based on attribute name patterns
                attr_name = address.split('.')[-1] if '.' in address else address
                
                # Known CF (Configuration) attributes
                cf_attrs = ['ctlModel', 'sboTimeout', 'sboClass', 'minVal', 'maxVal', 
                           'stepSize', 'dbRef', 'rangeC', 'units', 'd', 'dU', 'setVal',
                           'operTimeout', 'T0', 'T1', 'T2', 'T3']
                # Known ST (Status) attributes  
                st_attrs = ['stVal', 'q', 't', 'Beh', 'Health', 'Mod', 'general', 'dirGeneral']
                # Known MX (Measurement) attributes
                mx_attrs = ['mag', 'cVal', 'phsA', 'phsB', 'phsC', 'neut', 'res', 'angRef']
                # Known CO (Control) attributes
                co_attrs = ['Oper', 'SBO', 'SBOw', 'Cancel', 'origin', 'ctlNum']
                
                if attr_name in cf_attrs or any(attr_name.endswith(a) for a in cf_attrs):
                    fcs_to_try = [
                        ("CF", iec61850.IEC61850_FC_CF),
                        ("DC", iec61850.IEC61850_FC_DC),
                        ("ST", iec61850.IEC61850_FC_ST),
                    ]
                elif attr_name in st_attrs or any(attr_name.endswith(a) for a in st_attrs):
                    fcs_to_try = [
                        ("ST", iec61850.IEC61850_FC_ST),
                        ("MX", iec61850.IEC61850_FC_MX),
                    ]
                elif attr_name in mx_attrs or any(attr_name.endswith(a) for a in mx_attrs):
                    fcs_to_try = [
                        ("MX", iec61850.IEC61850_FC_MX),
                        ("ST", iec61850.IEC61850_FC_ST),
                    ]
                elif attr_name in co_attrs or any(attr_name.endswith(a) for a in co_attrs):
                    fcs_to_try = [
                        ("CO", iec61850.IEC61850_FC_CO),
                        ("ST", iec61850.IEC61850_FC_ST),
                    ]
                else:
                    # Default fallback - try all common FCs
                    fcs_to_try = [
                        ("ST", iec61850.IEC61850_FC_ST),
                        ("MX", iec61850.IEC61850_FC_MX),
                        ("CF", iec61850.IEC61850_FC_CF),
                        ("CO", iec61850.IEC61850_FC_CO),
                        ("SP", iec61850.IEC61850_FC_SP),
                        ("DC", iec61850.IEC61850_FC_DC),
                    ]
            
            # Prioritize FC from SCD description if available (Secondary check for older parsed signals)
            if not fcs_to_try:
                 import re
                 match = re.search(r"FC:([A-Z]{2})", signal.description or "")
                 if match:
                    prio_fc_name = match.group(1)
                    if prio_fc_name in fc_map:
                        fcs_to_try = [(prio_fc_name, fc_map[prio_fc_name])]
            
            # Final fallback
            if not fcs_to_try:
                 fcs_to_try = [
                    ("ST", iec61850.IEC61850_FC_ST),
                    ("MX", iec61850.IEC61850_FC_MX),
                    ("DC", iec61850.IEC61850_FC_DC)
                 ]

            value_read = False
            last_error = None
            successful_fc = None  # Track which FC succeeded
            
            def extract_val(res, expected_types=None):
                nonlocal last_error
                
                # Debug what we got
                # if self.event_logger: 
                #     self.event_logger.debug("IEC61850", f"DEBUG extract_val: {type(res)} {res}")

                # pyiec61850 usually returns [value, error]
                if isinstance(res, (list, tuple)) and len(res) >= 2:
                    if res[1] == iec61850.IED_ERROR_OK:
                        return res[0], True
                    if res[1] != iec61850.IED_ERROR_OK:
                         # ... error handling ...
                        error_descriptions = {
                            1: "NOT_CONNECTED",
                            2: "ALREADY_CONNECTED",
                            3: "CONNECTION_LOST",
                            4: "SERVICE_NOT_SUPPORTED",
                            5: "PARAMETER_VALUE_INCONSISTENT",
                            10: "OBJECT_REFERENCE_INVALID",
                            11: "OBJECT_UNDEFINED",
                            13: "OBJECT_DOES_NOT_EXIST",
                            20: "OBJECT_VALUE_INVALID",
                            21: "OBJECT_ACCESS_UNSUPPORTED",
                            22: "TYPE_INCONSISTENT",
                            23: "TEMPORARILY_UNAVAILABLE",
                            24: "OBJECT_ACCESS_DENIED",
                            25: "OBJECT_NONE_EXISTENT",
                        }
                        error_desc = error_descriptions.get(res[1], f"UNKNOWN({res[1]})")
                        last_error = f"IED Error {res[1]}: {error_desc}"
                        if self.event_logger:
                            self.event_logger.debug("IEC61850", f"    IED Error: {res[1]} ({error_desc}) for {address}")
                    return None, False
                
                # If not a list/tuple, it might be the value directly OR an error object
                if res is None:
                    return None, False
                
                # Critical check: If we get an int when expecting something else (like Swig Object or Float)
                # It indicates a potential raw error code return
                if expected_types:
                     if not isinstance(res, expected_types):
                         # Special case: float vs int/float
                         if float in expected_types and isinstance(res, (int, float)):
                             return res, True
                             
                         # If we expected MmsValue (Swig object) but got int
                         # (Swig objects usually aren't ints)
                         if isinstance(res, int) and int not in expected_types:
                             # Likely an error code returned directly
                             last_error = f"Raw Error Code: {res}"
                             if self.event_logger:
                                 self.event_logger.debug("IEC61850", f"    Raw Return Mismatch: Expected {expected_types}, got int {res}")
                             return None, False
                             
                return res, True
            
            for fc_name, fc in fcs_to_try:
                try:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"  Try FC={fc_name} for {address}")
                    
                    # 1. Try reading as Timestamp if it looks like one
                    if address.endswith(".t") or address.endswith(".T") or "Timestamp" in (signal.description or ""):
                        try:
                            # Use specialized read object for timestamps
                            res = iec61850.IedConnection_readObject(self.connection, address, fc)
                            mms_val, success = extract_val(res)
                            if success:
                                ts = self._get_timestamp_from_mms(mms_val)
                                if ts:
                                    signal.value = ts.strftime("%H:%M:%S.%f")[:-3]
                                    signal.timestamp = ts
                                    signal.signal_type = SignalType.TIMESTAMP
                                    signal.quality = SignalQuality.GOOD
                                    value_read = True
                                    successful_fc = fc
                                    iec61850.MmsValue_delete(mms_val)
                                    if self.event_logger:
                                        self.event_logger.transaction("IEC61850", f"← OK (TS): {address} = {signal.value}")
                                    break
                                else:
                                    if self.event_logger:
                                        self.event_logger.debug("IEC61850", f"  FC={fc_name} {address} read but not a valid UTC_TIME")
                                iec61850.MmsValue_delete(mms_val)
                        except Exception as e:
                            if self.event_logger:
                                self.event_logger.debug("IEC61850", f"  FC={fc_name} {address} TS read failed: {e}")
                            pass

                    # 2. Try reading as float first (most common for analog)
                    try:
                        res = iec61850.IedConnection_readFloatValue(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(float,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = {val}")
                            break
                    except: pass
                    
                    # Try reading as boolean
                    try:
                        res = iec61850.IedConnection_readBooleanValue(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(bool,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.BINARY
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = {val}")
                            break
                    except: pass
                    
                    # Try reading as int32
                    try:
                        res = iec61850.IedConnection_readInt32Value(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(int,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = {val}")
                            break
                    except: pass

                    # Try reading as BitString (for Dbpos etc)
                    try:
                        # readBitStringValue returns [value, error] where value is a BitString object or similar
                        res = iec61850.IedConnection_readBitStringValue(self.connection, address, fc)
                        val, success = extract_val(res) # BitString might be special object, skip type check for now
                        if success:
                            signal.value = val # This might need further parsing if it's a raw bitstring
                            signal.signal_type = SignalType.BINARY # Or DOUBLE_BINARY
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = BITSTRING")
                            break
                    except: pass

                    # Try reading as int64
                    try:
                        res = iec61850.IedConnection_readInt64Value(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(int,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            break
                    except: pass

                    # Try reading as string
                    try:
                        res = iec61850.IedConnection_readStringValue(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(str,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.STATE
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            break
                    except: pass

                    # Try generic readObject as fallback (Handles structs, arrays, enums, etc.)
                    try:
                         res = iec61850.IedConnection_readObject(self.connection, address, fc)
                         mms_val, success = extract_val(res)
                         if success:
                            # Convert MMS Value to string/value
                            val_str, val_type, error_msg = self._parse_mms_value(mms_val)
                            
                            if error_msg:
                                # Data access error at MMS level
                                signal.error = error_msg
                                signal.quality = SignalQuality.INVALID
                                if self.event_logger:
                                    self.event_logger.warning("IEC61850", f"← MMS ERROR (FC={fc_name}): {address} - {error_msg}")
                                # Don't break, try next FC
                            else:
                                signal.value = val_str
                                signal.signal_type = val_type
                                signal.quality = SignalQuality.GOOD
                                signal.timestamp = datetime.now()
                                value_read = True
                                successful_fc = fc
                                signal.error = ""  # Clear any previous error
                                
                                if self.event_logger:
                                    self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}) [Object]: {address} = {val_str}")
                                    
                                iec61850.MmsValue_delete(mms_val)
                                break
                         
                         if mms_val:
                             iec61850.MmsValue_delete(mms_val)
                    except: pass
                        
                except Exception as e:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"  FC={fc_name} failed: {e}")
                    last_error = str(e)
                    continue
            
            if value_read:
                # Success! Now try to get sibling timestamp (.t) if possible
                if ".stVal" in address or ".mag" in address or ".cVal" in address:
                    try:
                        parts = address.split('.')
                        if len(parts) > 1:
                            # Usually DO.stVal -> DO.t
                            # If it's DO.mag.f -> DO.t 
                            # We'll try to go up until we find the DO
                            base_do = ".".join(parts[:-1])
                            if ".mag" in address or ".cVal" in address:
                                # Go up one more level for nested attributes
                                base_do = ".".join(parts[:-2])
                            
                            # Check both .t and .T
                            for suffix in [".t", ".T"]:
                                t_addr = f"{base_do}{suffix}"
                                # Use the FC that successfully read the main value
                                res_t = iec61850.IedConnection_readObject(self.connection, t_addr, successful_fc) 
                                mms_t, ok_t = extract_val(res_t)
                                if ok_t:
                                    ts = self._get_timestamp_from_mms(mms_t)
                                    if ts:
                                        signal.timestamp = ts
                                    iec61850.MmsValue_delete(mms_t)
                                    break
                    except: pass

            if not value_read:
                signal.quality = SignalQuality.INVALID
                signal.value = None
                error_msg = "Could not read with any FC"
                if last_error:
                    error_msg = last_error
                signal.error = error_msg
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← FAILED: {address} - {error_msg}")
            
            # ENUM MAPPING
            if value_read and getattr(signal, 'enum_map', None) and isinstance(signal.value, int):
                if signal.value in signal.enum_map:
                    # Update value to string representation
                    # E.g. 1 -> "Open", 2 -> "Closed"
                    # Keep original value somewhere? Maybe just overwrite for display
                    signal.value = f"{signal.enum_map[signal.value]} ({signal.value})"
                    signal.signal_type = SignalType.STATE
            
            self._emit_update(signal) # CRITICAL: Emit the update!
            return signal
            
        except Exception as e:
            logger.error(f"Exception reading signal {signal.address}: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"← EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            signal.quality = SignalQuality.INVALID
            signal.value = None
            self._emit_update(signal)
            return signal

        # Real Read
        # We need the Object Reference (address)
        # Assuming signal.address is the full object reference e.g. "IED1_LD0/LLN0.Health.stVal"
        # Note: libiec61850 readValue expects functional constraint usually if not part of name?
        # Actually IedConnection_readFloatValue takes "objectReference" and "fc" (FunctionalConstraint)
        # But our Address string might contain it?
        # Usually address is "LD/LN.DO.DA". We need FC.
        # For now, let's assume FC is MX (Measurements) or ST (Status).
        
        # We need to map SignalType to correct read function
        
        fc = iec61850.IEC61850_FC_MX # Default to MX
        if signal.signal_type in [SignalType.BINARY, SignalType.DOUBLE_BINARY]:
             fc = iec61850.IEC61850_FC_ST
        
        # We might need to split address or pass it directly.
        # If address is "LD/LN.DO.DA", we also need to pass FC separately.
        
        try:
            val = None
            err = iec61850.IedConnection_readFloatValue(self.connection, signal.address, fc)
            # Checking err is tricky if it returns value directly or via pointer.
            # In pyiec61850, it often returns the value, or None on error?
            # Creating a MmsValue is safer.
            
            mms_value = iec61850.IedConnection_readObject(self.connection, signal.address, fc, 0)
            if mms_value:
                # Extract value
                val_type = iec61850.MmsValue_getType(mms_value)
                if val_type == iec61850.MMS_FLOAT:
                    signal.value = iec61850.MmsValue_toFloat(mms_value)
                elif val_type == iec61850.MMS_BOOLEAN:
                     signal.value = iec61850.MmsValue_getBoolean(mms_value)
                # ... handle other types
                
                signal.quality = SignalQuality.GOOD
                signal.timestamp = datetime.now()
                
                iec61850.MmsValue_delete(mms_value)
            else:
                 signal.quality = SignalQuality.INVALID

        except Exception as e:
            logger.debug(f"Read failed for {signal.address}: {e}")
            signal.quality = SignalQuality.INVALID
            
        return signal

    def select(self, signal: Signal, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Select-Before-Operate (SBO).
        Uses ControlObjectClient for higher-level abstraction.
        
        Args:
            signal: The signal to select.
            params: Optional dict with keys:
                - originator_category (int)
                - originator_identity (str)
                - interlock_check (bool)
                - synchro_check (bool)
                - test (bool)
        """
        if not self.connected:
            return False
            
        object_ref = self._get_control_object_reference(signal.address)
        if not object_ref:
            if self.event_logger:
                self.event_logger.error("IEC61850", f"SELECT: Could not determine Control Object from {signal.address}")
            return False

        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ SELECT {object_ref}")

        try:
            client = iec61850.ControlObjectClient_create(object_ref, self.connection)
            if not client:
                 if self.event_logger:
                     self.event_logger.error("IEC61850", "Failed to create ControlObjectClient")
                 return False
            
            # Apply parameters if provided
            if params:
                self._apply_control_params(client, params)
            
            success = iec61850.ControlObjectClient_select(client)
            iec61850.ControlObjectClient_destroy(client)
            
            if success:
                if self.event_logger:
                    self.event_logger.transaction("IEC61850", "← SELECT SUCCESS")
                
                # Update Runtime State
                if object_ref in self.controls:
                    self.controls[object_ref].state = ControlState.SELECTED
                    self.controls[object_ref].last_select_time = datetime.now()
                    
                return True
            else:
                if self.event_logger:
                    self.event_logger.error("IEC61850", "← SELECT FAILED")
                if object_ref in self.controls:
                     self.controls[object_ref].state = ControlState.FAILED
                return False
                
        except Exception as e:
            logger.error(f"Select failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"SELECT EXCEPTION: {e}")
            return False

    def operate(self, signal: Signal, value: Any, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Operate (Control) on a signal.
        Supports Direct Operate and SBO Operate phases.
        Uses cached ControlObjectRuntime if available.
        """
        object_ref = self._get_control_object_reference(signal.address)
        
        # If we successfully identified a Control Object Reference
        if object_ref and object_ref in self.controls:
             ctrl_runtime = self.controls[object_ref]
             
             # SBO Logic
             if ctrl_runtime.ctl_model.is_sbo:
                 # Check if we are already selected
                 # Since this adapter is stateless regarding MmsConnection (mostly), we assume we need to select.
                 # Optimization: If we just selected it, we might be good? 
                 # But for safety, we often re-select or assume the UI button called select() separately?
                 # USER REQUIREMENT: "Auto-Select strategy for simple UI" is what I had before.
                 # Let's keep Auto-Select if state is IDLE.
                 
                 if self.event_logger:
                     self.event_logger.transaction("IEC61850", f"Operating SBO Control ({ctrl_runtime.ctl_model.name})")

                 # If we haven't selected recently, do it now
                 # TODO: Check ctrl_runtime.state == SELECTED?
                 # For now, simplistic auto-select safety:
                 if not self.select(signal, params=params):
                      return False
             
             result = self._operate_control(object_ref, value, signal, params=params)
             
             if result:
                 ctrl_runtime.state = ControlState.OPERATED
                 ctrl_runtime.last_operate_time = datetime.now()
                 self._force_refresh_stval(object_ref)
             else:
                 ctrl_runtime.state = ControlState.FAILED
                 
             return result
             
        # Fallback for legacy/heuristics if not in discovery cache
        if object_ref and ("Oper" in signal.address or "ctlVal" in signal.address or getattr(signal, "access", "") == "RW"):
             # Original legacy logic
             ctl_model = self.read_ctl_model(object_ref) 
             is_sbo = ctl_model in [2, 4]
             
             if is_sbo:
                 if not self.select(signal, params=params):
                     return False
             
             return self._operate_control(object_ref, value, signal, params=params)
             
        # Otherwise, fall back to direct DataAttribute write
        return self.write_signal(signal, value)

    def read_ctl_model(self, object_ref: str) -> int:
        """Public alias for _read_ctl_model for external use."""
        # Check if object_ref is a full address (with attributes) or just the DO
        # If it looks like a signal address, strip last part if needed
        # But _read_ctl_model expects DO reference.
        # Let's try to smart resolve?
        # If input has no dots, it's likely wrong.
        return self._read_ctl_model(object_ref)

    def _read_ctl_model(self, object_ref: str) -> int:
        """
        Read the ctlModel attribute of the control object.
        Returns:
            0: status-only
            1: direct-with-normal-security (default fallback)
            2: sbo-with-normal-security
            3: direct-with-enhanced-security
            4: sbo-with-enhanced-security
        """
        ctl_model_path = f"{object_ref}.CF.ctlModel"
        # Often just .ctlModel if reading DO? But usually it's a structural DA. 
        # But we need specific reference.
        # Try constructing path: object + ".ctlModel" is NOT sufficient usually for ReadValue unless using CF FC.
        # Let's try object_ref + ".ctlModel" with FC=CF
        
        try:
             # Try standard path
             path = f"{object_ref}.ctlModel"
             val, err = iec61850.IedConnection_readInt32Value(
                 self.connection, path, iec61850.IEC61850_FC_CF
             )
             if err == iec61850.IED_ERROR_OK:
                 return val
             
             # Fallback: Maybe generic CDCu structure?
             pass 
        except Exception:
             pass
             
        return 1 # Assume Direct if read fails to avoid blocking compatible devices

    def _force_refresh_stval(self, object_ref: str):
        """Try to find and read the stVal associated with this control to update UI instantly."""
        # Heuristic: Replace control parts with stVal
        # object_ref is usually ".../GGIO1.SPCSO1"
        st_path = f"{object_ref}.stVal"
        
        # Create a dummy signal to reuse read_signal logic which handles parsing etc
        # But read_signal needs a 'signal' object from the model is best.
        # We'll just do a raw read and if we can find the signal in our cache, update it?
        # Better: Just read it raw and log it? 
        # The user wants the UI to update. The UI updates via DeviceManager polling or manual refresh.
        # If we read it here, we need to inject it into the system.
        
        # We can try to use read_signal if we can find the Signal object in device path.
        # This is expensive to search.
        # Simpler: Just read value and log it for now.
        # Or if we have a callback?
        pass # TODO: Full injection requires finding the Signal instance.

    def _operate_control(self, object_ref: str, value: Any, signal: Signal, params: Optional[Dict[str, Any]] = None) -> bool:
        """Handle standard IEC 61850 Control Model operation."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ OPERATE {object_ref} = {value}")
            
        if not self.connected:
            return False

        try:
            client = iec61850.ControlObjectClient_create(object_ref, self.connection)
            if not client:
                 return False
            
            # Create MmsValue for the control value
            mms_value = self._create_mms_value(value, signal)
            if not mms_value:
                iec61850.ControlObjectClient_destroy(client)
                return False

            # Apply parameters
            if params:
                self._apply_control_params(client, params)

            test_flag = params.get('test', False) if params else False
            
            success = iec61850.ControlObjectClient_operate(client, mms_value, 1 if test_flag else 0)
            
            # Error handling if success is False
            # Can we get the LastApplError?
            # libiec61850 often prints to stderr, but we can't easily capture it via ctypes without callback.
            
            iec61850.MmsValue_delete(mms_value)
            iec61850.ControlObjectClient_destroy(client)
            
            if success:
                if self.event_logger:
                    self.event_logger.transaction("IEC61850", "← OPERATE SUCCESS")
                return True
            else:
                if self.event_logger:
                    self.event_logger.error("IEC61850", "← OPERATE FAILED")
                return False
                
        except Exception as e:
            logger.error(f"Operate failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"OPERATE EXCEPTION: {e}")
            return False

    def _apply_control_params(self, client, params):
        """Helper to apply control parameters to the client."""
        if not params: return

        # Originator
        if 'originator_category' in params or 'originator_identity' in params:
             cat = params.get('originator_category', 0) # 0=NotSupported
             ident = params.get('originator_identity', "Station")
             iec61850.ControlObjectClient_setOriginator(client, cat, ident)
        
        # Checks
        if 'interlock_check' in params:
             iec61850.ControlObjectClient_setInterlockCheck(client, params['interlock_check'])
             
        if 'synchro_check' in params:
             iec61850.ControlObjectClient_setSynchroCheck(client, params['synchro_check'])
             
        if 'test' in params:
             # Some libs use setTestMode, others pass it to Operate args
             iec61850.ControlObjectClient_setTestMode(client, params['test'])

    def write_signal(self, signal: Signal, value: Any) -> bool:
        """
        Generic write to a Data Attribute (non-control).
        Use this for setting configuration parameters (FC=CF, SP, SE).
        """
        if not self.connected:
            return False
            
        # Check if it's actually a control
        object_ref = self._get_control_object_reference(signal.address)
        if object_ref and ("Oper" in signal.address or "ctlVal" in signal.address):
            return self._operate_control(object_ref, value, signal)

        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ WRITE {signal.address} = {value}")

        try:
            mms_value = self._create_mms_value(value, signal)
            if not mms_value:
                return False
            
            # Determine FC
            fc = iec61850.IEC61850_FC_CF # Default for settings
            if getattr(signal, 'fc', None):
                # Map logical FC to int
                pass # TODO: Implement mapping if needed, relies on heuristics often
            elif "setVal" in signal.address:
                fc = iec61850.IEC61850_FC_SP
                
            err = iec61850.IedConnection_writeObject(self.connection, signal.address, fc, mms_value)
            
            iec61850.MmsValue_delete(mms_value)
            
            if err == iec61850.IED_ERROR_OK:
                if self.event_logger:
                    self.event_logger.transaction("IEC61850", "← WRITE SUCCESS")
                return True
            else:
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← WRITE FAILED: Error {err}")
                return False

        except Exception as e:
            logger.error(f"Write failed: {e}")
            return False

    def cancel(self, signal: Signal) -> bool:
        """Cancel selection."""
        if not self.connected:
            return False
            
        object_ref = self._get_control_object_reference(signal.address)
        if not object_ref:
            return False
            
        try:
            client = iec61850.ControlObjectClient_create(object_ref, self.connection)
            if not client: return False
            
            success = iec61850.ControlObjectClient_cancel(client)
            iec61850.ControlObjectClient_destroy(client)
            return success
        except Exception as e:
            return False

    def _get_control_object_reference(self, address: str) -> str:
        """
        Extract the Control Object Reference (DO path) from a detailed signal address.
        E.g. "IED/LD.GGIO1.SPCSO1.Oper.ctlVal" -> "IED/LD.GGIO1.SPCSO1"
        """
        # Common suffixes for control attributes
        suffixes = [".Oper.ctlVal", ".Oper", ".SBO.ctlVal", ".SBO", ".SBOw.ctlVal", ".SBOw", ".Cancel.ctlVal", ".Cancel", ".ctlVal"]
        
        # Try to strip known control suffixes
        for suffix in suffixes:
            if address.endswith(suffix):
                return address[:-len(suffix)]
        
        # Heuristic: If it has at least one dot, and we think it's a control
        if "." in address:
            # Maybe the user selected the DO node directly?
            # Check if last part looks like a DA (start with lowercase generally, except Oper/SBO)
            pass
            
        # Fallback: Assume the address IS the object reference if it doesn't end in typical attribute names
        # But most Signals in the list will be leaf nodes (attributes).
        return None

    def _create_mms_value(self, value: Any, signal: Signal):
        """Create MmsValue from Python value."""
        try:
            if isinstance(value, bool):
                return iec61850.MmsValue_newBoolean(value)
            elif isinstance(value, float):
                return iec61850.MmsValue_newFloat(value)
            elif isinstance(value, int):
                return iec61850.MmsValue_newInt32(value)
            elif isinstance(value, str):
                return iec61850.MmsValue_newVisibleString(value)
            return None
        except:
            return None

    def _detect_vendor_pre_connect(self):
        pass
