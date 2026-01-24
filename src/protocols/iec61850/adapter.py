from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime
import logging
import time
import threading
import re

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

# Map of IedClientError codes to descriptive strings
IED_CLIENT_ERROR_MAP = {
    0: "OK",
    1: "Not connected",
    2: "Already connected",
    3: "Connection lost",
    4: "Service not supported",
    5: "Connection rejected",
    6: "Outstanding call limit reached",
    7: "Invalid argument",
    10: "Object Reference invalid",
    11: "Unexpected value received",
    12: "Timeout",
    13: "Access denied",
    14: "Object undefined",
    15: "Invalid address",
    16: "Hardware fault",
    17: "Type inconsistent",
    18: "Temporarily unavailable",
    19: "Object value invalid",
    20: "Option not supported",
    99: "Unknown error"
}

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
        self._lock = threading.Lock() # libiec61850 connection is not thread-safe
        
        # Diagnostic check for UTC time binding
        if not hasattr(iec61850, 'MmsValue_newUtcTimeMs'):
            logger.warning("iec61850_wrapper is missing MmsValue_newUtcTimeMs attribute!")
        else:
            logger.debug("iec61850_wrapper has MmsValue_newUtcTimeMs.")
        
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
            
            with self._lock:
                if self.connection:
                    logger.info("Already connecting or connected.")
                    return True

                logger.info(f"Connecting to {self.config.ip_address} using libiec61850...")
                self.connection = iec61850.IedConnection_create()
                if not self.connection:
                    logger.error("Failed to create IedConnection handle")
                    return False
                
                if self.event_logger:
                    self.event_logger.transaction("IEC61850", f"→ IedConnection_connect({self.config.ip_address}, {self.config.port})")
                
                error = iec61850.IedConnection_connect(
                    self.connection,
                    self.config.ip_address,
                    self.config.port
                )
                
                if error != 0:
                    # Map error codes to human-readable messages
                    error_messages = {
                        1: "Not connected",
                        2: "Already connected",
                        3: "Connection lost",
                        4: "Service not supported",
                        5: "Connection rejected (no server responding on this port)",
                        6: "Outstanding call limit reached",
                        10: "Invalid argument provided",
                        20: "Timeout",
                        21: "Access denied",
                        22: "Object does not exist",
                    }
                    
                    error_description = error_messages.get(error, f"Unknown error ({error})")
                    error_msg = f"Error code {error}: {error_description}"
                    
                    if self.event_logger:
                        if error == 5:
                            self.event_logger.error(
                                "Connection", 
                                f"❌ IEC 61850 connection FAILED\n   {error_msg}\n   \n   Possible causes:\n   • No IEC 61850 server running on {self.config.ip_address}:{self.config.port}\n"
                            )
                        else:
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
                 # Show full date + time in UTC with millisecond precision
                 return ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UTC', SignalType.TIMESTAMP, ""
             else:
                 return None, SignalType.TIMESTAMP, "Invalid timestamp format"

        elif val_type == iec61850.MMS_STRUCTURE:
             # Try to expand common structures (e.g., TimeOfDay) for readability.
             try:
                 size = iec61850.MmsValue_getArraySize(mms_val)
                 elems = []
                 for i in range(size):
                     try:
                         ev = iec61850.MmsValue_getElement(mms_val, i)
                         if not ev:
                             elems.append((None, None))
                             continue
                         v, vtype, _ = self._parse_mms_value(ev)
                         elems.append((v, vtype))
                     except Exception:
                         elems.append((None, None))

                 # Heuristic: If first element is a UTC time, treat as TimeOfDay-like structure
                 if elems and elems[0][1] == SignalType.TIMESTAMP:
                     # Common field names for TimeOfDay-like structs
                     field_names = ['time', 'leapSecondKnown', 'clockFailure', 'clockNotSynchronized', 'timeAccuracy']
                     parts = []
                     for idx, (val, vtype) in enumerate(elems):
                         name = field_names[idx] if idx < len(field_names) else f'field{idx}'
                         parts.append(f"{name}={val}")
                     return "; ".join(parts), SignalType.TIMESTAMP, ""
                 else:
                     # Generic struct: list values
                     parts = [str(v[0]) if v[0] is not None else 'None' for v in elems]
                     return f"Structure[{', '.join(parts)}]", SignalType.STATE, ""
             except Exception:
                 return "[Structure]", SignalType.STATE, ""
             
        elif val_type == iec61850.MMS_ARRAY:
             size = iec61850.MmsValue_getArraySize(mms_val)
             return f"[Array[{size}]]", SignalType.STATE, ""
             
             return "[Complex Data]", SignalType.STATE, ""

    def _safe_destroy_list(self, list_ptr):
        """Safely destroy a LinkedList handle and ensure it's valid."""
        if list_ptr:
            try:
                # Always destroy list while holding the connection lock 
                # as the list is linked to the connection's memory context
                with self._lock:
                    if self.connection:
                        iec61850.LinkedList_destroy(list_ptr)
            except: pass

    def _safe_delete_mms(self, mms_val):
        """Safely delete an MmsValue handle."""
        if mms_val:
            try:
                iec61850.MmsValue_delete(mms_val)
            except: pass

    def _safe_destroy_control_client(self, client):
        """Safely destroy a ControlObjectClient handle."""
        if client:
            try:
                # Holding lock is safer as client references connection
                with self._lock:
                    if self.connection:
                        iec61850.ControlObjectClient_destroy(client)
            except: pass

    def disconnect(self):
        with self._lock:
            if self.connection:
                try:
                    iec61850.IedConnection_close(self.connection)
                except: pass
                self._cleanup_connection_locked()
        self.connected = False
        logger.info("Disconnected.")

    def _cleanup_connection_locked(self):
        """Internal cleanup, MUST be called with self._lock held."""
        if self.connection:
            try:
                iec61850.IedConnection_destroy(self.connection)
            except: pass
            self.connection = None

    def discover(self) -> Node:
        """Discover device structure with event logging."""
        if self.event_logger:
            self.event_logger.info("Discovery", "=== Starting device discovery ===")
        
        # If SCD file is available and preferred, use it
        if self.config.scd_file_path and self.config.use_scd_discovery:
            if self.event_logger:
                # Demote SCD discovery notification to debug to keep Event Log tidy
                try:
                    self.event_logger.transaction("Discovery", f"Using SCD file: {self.config.scd_file_path}")
                except Exception:
                    pass
            logger.debug(f"Using SCD file for discovery: {self.config.scd_file_path}")
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
            with self._lock:
                if not self.connection: return
                ret = iec61850.IedConnection_getDataDirectory(self.connection, parent_path)
            
            children = ret[0] if isinstance(ret, (list, tuple)) else ret
            
            child_names = []
            if children:
                child_names = self._extract_string_list(children)
                self._safe_destroy_list(children)
            
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
            with self._lock:
                if not self.connection: return root
                ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            
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
            
            seen_vendors = set()

            # Browse each Logical Device
            for ld_name in ld_names:
                ld_node = Node(name=ld_name, description="Logical Device")
                root.children.append(ld_node)
                
                # Try to read Name Plate (NamPlt) from LLN0
                # Usually LD/LLN0.NamPlt.vendor
                try:
                    vendor_path = f"{ld_name}/LLN0.NamPlt.vendor"
                    with self._lock:
                        if not self.connection: break
                        vendor_res = iec61850.IedConnection_readStringValue(self.connection, vendor_path, iec61850.IEC61850_FC_DC)
                    
                    if isinstance(vendor_res, (list, tuple)) and vendor_res[1] == iec61850.IED_ERROR_OK:
                        vendor = vendor_res[0]
                        root.description = f"IED: {vendor}"
                        if self.event_logger and vendor and vendor not in seen_vendors:
                            self.event_logger.info("Discovery", f"Found Vendor: {vendor}")
                            seen_vendors.add(vendor)
                except: pass

                # Get Logical Nodes for this LD
                try:
                    with self._lock:
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
                                with self._lock:
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
                                            (iec61850.IEC61850_FC_SP, "SP"),
                                            (iec61850.IEC61850_FC_CF, "CF"),
                                            (iec61850.IEC61850_FC_DC, "DC"),
                                        ]
                                        
                                        found_signals = False
                                        
                                        # Strict JIT Rule: Do NOT read ctlModel here.
                                        # Just browse structure.
                                        
                                        for fc_val, fc_name in fcs:
                                            try:
                                                with self._lock:
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
                                                    with self._lock:
                                                        iec61850.LinkedList_destroy(da_list)
                                            except: continue
                                        
                                        if not found_signals:
                                            # Fallback generic browse
                                            try:
                                                with self._lock:
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
                                                    with self._lock:
                                                        iec61850.LinkedList_destroy(da_list)
                                            except: pass

                            except Exception:
                                # Close the try block from line 491 (Get Data Objects for this LN)
                                pass

                            # Add DataSets, Reports, and GOOSE control blocks (independent of DO browse)
                            try:
                                self._discover_datasets_online(full_ln_ref, ln_node)
                                self._discover_reports_online(full_ln_ref, ln_node)
                                self._discover_goose_online(full_ln_ref, ln_node)
                            except Exception:
                                pass
                    
                    try:
                        with self._lock:
                            iec61850.LinkedList_destroy(ln_list)
                    except: pass
                        
                except Exception: pass
            
            try:
                with self._lock:
                    iec61850.LinkedList_destroy(ld_list)
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
             with self._lock:
                 if not self.connection: return 1
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

    def _add_detail_leaf(self, parent_node: Node, label: str, value: Optional[Any]) -> None:
        if value is None or value == "":
            parent_node.children.append(Node(name=label, description="Detail"))
        else:
            parent_node.children.append(Node(name=f"{label}={value}", description="Detail"))

    def _normalize_dataset_ref(self, full_ln_ref: str, dataset_name: str) -> str:
        if not dataset_name:
            return ""
        if "/" in dataset_name:
            return dataset_name
        ld_name = full_ln_ref.split("/")[0] if "/" in full_ln_ref else ""
        if "$" in dataset_name:
            return f"{ld_name}/{dataset_name}" if ld_name else dataset_name
        return f"{full_ln_ref}${dataset_name}"

    def _add_dataset_entries_online(self, dataset_ref: str, parent_node: Node) -> None:
        if not dataset_ref:
            return
        try:
            with self._lock:
                if not self.connection: return
                ret = iec61850.IedConnection_getDataSetDirectory(self.connection, dataset_ref)
            
            ds_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            err = ret[1] if isinstance(ret, (list, tuple)) and len(ret) > 1 else None

            if ds_list and (err is None or err == iec61850.IED_ERROR_OK):
                entries = self._extract_string_list(ds_list)
                if entries:
                    entries_root = Node(name="DataSetEntries", description="FCDA members")
                    for entry in entries:
                        entries_root.children.append(Node(name=entry, description="FCDA"))
                    parent_node.children.append(entries_root)
            try:
                with self._lock:
                    iec61850.LinkedList_destroy(ds_list)
            except Exception:
                pass
        except Exception:
            pass

    def _discover_datasets_online(self, full_ln_ref: str, ln_node: Node) -> None:
        try:
            with self._lock:
                if not self.connection: return
                ret_ds = iec61850.IedConnection_getLogicalNodeDirectory(
                    self.connection,
                    full_ln_ref,
                    iec61850.ACSI_CLASS_DATA_SET
                )
            ds_list = ret_ds[0] if isinstance(ret_ds, (list, tuple)) else ret_ds
            if not ds_list:
                return

            ds_names = self._extract_string_list(ds_list)
            if not ds_names:
                self._safe_destroy_list(ds_list)
                return

            datasets_root = Node(name="DataSets", description="Container")
            for ds_name in ds_names:
                ds_node = Node(name=ds_name, description="Type=DataSet")
                dataset_ref = self._normalize_dataset_ref(full_ln_ref, ds_name)
                self._add_detail_leaf(ds_node, "Ref", dataset_ref)
                self._add_dataset_entries_online(dataset_ref, ds_node)
                datasets_root.children.append(ds_node)

            ln_node.children.append(datasets_root)
            self._safe_destroy_list(ds_list)
        except Exception:
            pass

    def _discover_reports_online(self, full_ln_ref: str, ln_node: Node) -> None:
        reports_root = None

        def add_report_nodes(rcb_names, rcb_type, fc):
            nonlocal reports_root
            if not rcb_names:
                return
            if reports_root is None:
                reports_root = Node(name="Reports", description="Container")

            for rcb_name in rcb_names:
                rpt_node = Node(name=rcb_name, description=f"Type={rcb_type}")
                rcb_ref = f"{full_ln_ref}.{rcb_name}"

                # Read common attributes
                try:
                    with self._lock:
                        rpt_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.RptID", fc)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(rpt_node, "RptID", rpt_id)
                except Exception:
                    self._add_detail_leaf(rpt_node, "RptID", "")

                dat_set_val = ""
                try:
                    with self._lock:
                        dat_set_val, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.DatSet", fc)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(rpt_node, "DatSet", dat_set_val)
                except Exception:
                    self._add_detail_leaf(rpt_node, "DatSet", "")

                for attr in ["BufTm", "IntgPd"]:
                    try:
                        with self._lock:
                            val, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.{attr}", fc)
                        if err == iec61850.IED_ERROR_OK:
                            self._add_detail_leaf(rpt_node, attr, val)
                    except Exception:
                        self._add_detail_leaf(rpt_node, attr, "")

                for attr in ["TrgOps", "OptFlds"]:
                    try:
                        with self._lock:
                            val, err = iec61850.IedConnection_readBitStringValue(self.connection, f"{rcb_ref}.{attr}", fc)
                        if err == iec61850.IED_ERROR_OK:
                            self._add_detail_leaf(rpt_node, attr, val)
                    except Exception:
                        self._add_detail_leaf(rpt_node, attr, "")

                dataset_ref = self._normalize_dataset_ref(full_ln_ref, dat_set_val)
                self._add_dataset_entries_online(dataset_ref, rpt_node)

                reports_root.children.append(rpt_node)

        try:
            with self._lock:
                ret_urcb = iec61850.IedConnection_getLogicalNodeDirectory(
                    self.connection,
                    full_ln_ref,
                    iec61850.ACSI_CLASS_URCB
                )
            urcb_list = ret_urcb[0] if isinstance(ret_urcb, (list, tuple)) else ret_urcb
            urcb_names = self._extract_string_list(urcb_list) if urcb_list else []
            add_report_nodes(urcb_names, "URCB", iec61850.IEC61850_FC_RP)
            self._safe_destroy_list(urcb_list)
        except Exception:
            pass

        try:
            with self._lock:
                if not self.connection: return
                ret_brcb = iec61850.IedConnection_getLogicalNodeDirectory(
                    self.connection,
                    full_ln_ref,
                    iec61850.ACSI_CLASS_BRCB
                )
            brcb_list = ret_brcb[0] if isinstance(ret_brcb, (list, tuple)) else ret_brcb
            brcb_names = self._extract_string_list(brcb_list) if brcb_list else []
            add_report_nodes(brcb_names, "BRCB", iec61850.IEC61850_FC_BR)
            self._safe_destroy_list(brcb_list)
        except Exception:
            pass

        if reports_root is not None:
            ln_node.children.append(reports_root)

    def _discover_goose_online(self, full_ln_ref: str, ln_node: Node) -> None:
        try:
            with self._lock:
                if not self.connection: return
                ret_gocb = iec61850.IedConnection_getLogicalNodeDirectory(
                    self.connection,
                    full_ln_ref,
                    iec61850.ACSI_CLASS_GoCB
                )
            gocb_list = ret_gocb[0] if isinstance(ret_gocb, (list, tuple)) else ret_gocb
            if not gocb_list:
                return

            gocb_names = self._extract_string_list(gocb_list)
            if not gocb_names:
                self._safe_destroy_list(gocb_list)
                return

            goose_root = Node(name="GOOSE", description="Container")

            for gocb_name in gocb_names:
                gse_node = Node(name=gocb_name, description="Type=GoCB")
                gocb_ref = f"{full_ln_ref}.{gocb_name}"

                dat_set_val = ""
                try:
                    with self._lock:
                        if not self.connection: break
                        go_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.GoID", iec61850.IEC61850_FC_GO)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(gse_node, "GoID", go_id)
                except Exception:
                    self._add_detail_leaf(gse_node, "GoID", "")

                try:
                    with self._lock:
                        if not self.connection: break
                        dat_set_val, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.DatSet", iec61850.IEC61850_FC_GO)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(gse_node, "DatSet", dat_set_val)
                except Exception:
                    self._add_detail_leaf(gse_node, "DatSet", "")

                for attr in ["ConfRev", "MinTime", "MaxTime"]:
                    try:
                        with self._lock:
                            if not self.connection: break
                            val, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{gocb_ref}.{attr}", iec61850.IEC61850_FC_GO)
                        if err == iec61850.IED_ERROR_OK:
                            self._add_detail_leaf(gse_node, attr, val)
                    except Exception:
                        self._add_detail_leaf(gse_node, attr, "")

                try:
                    with self._lock:
                        if not self.connection: break
                        app_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.AppID", iec61850.IEC61850_FC_GO)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(gse_node, "AppID", app_id)
                except Exception:
                    self._add_detail_leaf(gse_node, "AppID", "")

                dataset_ref = self._normalize_dataset_ref(full_ln_ref, dat_set_val)
                self._add_dataset_entries_online(dataset_ref, gse_node)

                goose_root.children.append(gse_node)

            ln_node.children.append(goose_root)
            self._safe_destroy_list(gocb_list)
        except Exception:
            pass

    def _get_timestamp_from_mms(self, mms_val):
        """Helper to extract Python datetime from MmsValue."""
        if not mms_val:
            return None
        try:
            mms_type = iec61850.MmsValue_getType(mms_val)
            if mms_type == iec61850.MMS_UTC_TIME:
                unix_ts = iec61850.MmsValue_toUnixTimestamp(mms_val)
                # handle both float and int unix timestamps
                # Interpret as UTC and return a timezone-aware datetime
                try:
                    return datetime.utcfromtimestamp(unix_ts).replace(tzinfo=datetime.timezone.utc)
                except Exception:
                    return datetime.fromtimestamp(unix_ts)
        except (ValueError, OSError, OverflowError):
             logger.debug(f"Failed to parse UTC time from MMS value")
        return None

    def read_signal(self, signal: Signal) -> Signal:
        """Read a single signal value from the IED."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ READ {signal.address}")
            
        if not self.connected or not self.connection:
            signal.quality = SignalQuality.NOT_CONNECTED
            if self.event_logger:
                self.event_logger.warning("IEC61850", f"← NOT CONNECTED (Internal State)")
            self._emit_update(signal) # Emit even if failed
            return signal

        with self._lock:
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
            parts = address.split('/')
            if len(parts) >= 3 and parts[0] == parts[1]:
                # GPS/GPS/LN.DO... -> GPS/LN.DO...
                address = f"{parts[0]}/{'/'.join(parts[2:])}"
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"  Corrected address: {signal.address} -> {address}")
            
            # If address doesn't contain '/', it's missing LD - we need to find it
            if '/' not in address:
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← INVALID ADDRESS: {address} (missing LD/)")
                signal.quality = SignalQuality.INVALID
                return signal
            
            # Common functional constraints to try
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
            if getattr(signal, 'fc', None) and signal.fc in fc_map:
                 fcs_to_try.append((signal.fc, fc_map[signal.fc]))
            else:
                attr_name = re.split(r'[\.\$]', address)[-1]
                cf_attrs = ['ctlModel', 'sboTimeout', 'sboClass', 'minVal', 'maxVal', 
                           'stepSize', 'dbRef', 'rangeC', 'units', 'd', 'dU', 'setVal',
                           'operTimeout', 'T0', 'T1', 'T2', 'T3']
                st_attrs = ['stVal', 'q', 't', 'Beh', 'Health', 'Mod', 'general', 'dirGeneral']
                mx_attrs = ['mag', 'cVal', 'phsA', 'phsB', 'phsC', 'neut', 'res', 'angRef']
                co_attrs = ['Oper', 'SBO', 'SBOw', 'Cancel', 'origin', 'ctlNum']
                
                if attr_name in cf_attrs or any(attr_name.endswith(a) for a in cf_attrs):
                    fcs_to_try = [("CF", iec61850.IEC61850_FC_CF), ("DC", iec61850.IEC61850_FC_DC), ("ST", iec61850.IEC61850_FC_ST)]
                elif attr_name in st_attrs or any(attr_name.endswith(a) for a in st_attrs):
                    fcs_to_try = [("ST", iec61850.IEC61850_FC_ST), ("MX", iec61850.IEC61850_FC_MX)]
                elif attr_name in mx_attrs or any(attr_name.endswith(a) for a in mx_attrs):
                    fcs_to_try = [("MX", iec61850.IEC61850_FC_MX), ("ST", iec61850.IEC61850_FC_ST)]
                elif attr_name in co_attrs or any(attr_name.endswith(a) for a in co_attrs):
                    fcs_to_try = [("CO", iec61850.IEC61850_FC_CO), ("ST", iec61850.IEC61850_FC_ST)]
                else:
                    fcs_to_try = [("ST", iec61850.IEC61850_FC_ST), ("MX", iec61850.IEC61850_FC_MX), ("CF", iec61850.IEC61850_FC_CF)]
            
            value_read = False
            last_error = None
            successful_fc = None

            def extract_val(res, expected_types=None):
                nonlocal last_error
                if isinstance(res, (list, tuple)) and len(res) >= 2:
                    if res[1] == iec61850.IED_ERROR_OK: return res[0], True
                    return None, False
                if res is None: return None, False
                if expected_types and not isinstance(res, expected_types):
                    if float in expected_types and isinstance(res, (int, float)): return res, True
                    return None, False
                return res, True

            with self._lock:
                if not self.connection:
                    signal.quality = SignalQuality.NOT_CONNECTED
                    self._emit_update(signal)
                    return signal

                for fc_name, fc in fcs_to_try:
                    try:
                        # 1. Try reading as Timestamp if it looks like one
                        if address.endswith(".t") or address.endswith(".T") or "Timestamp" in (signal.description or ""):
                            res = iec61850.IedConnection_readObject(self.connection, address, fc)
                            mms_val, success = extract_val(res)
                            if success:
                                ts = self._get_timestamp_from_mms(mms_val)
                                if ts:
                                    signal.value = ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UTC'
                                    signal.timestamp = ts
                                    signal.signal_type = SignalType.TIMESTAMP
                                    signal.quality = SignalQuality.GOOD
                                    value_read = True
                                    successful_fc = fc
                                    self._safe_delete_mms(mms_val)
                                    break
                                self._safe_delete_mms(mms_val)

                        # 2. Try reading as float
                        if not self.connection: break
                        res = iec61850.IedConnection_readFloatValue(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(float,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            break
                        
                        # Try reading as boolean
                        if not self.connection: break
                        res = iec61850.IedConnection_readBooleanValue(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(bool,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.BINARY
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            break
                        
                        # Try reading as int32
                        if not self.connection: break
                        res = iec61850.IedConnection_readInt32Value(self.connection, address, fc)
                        val, success = extract_val(res, expected_types=(int,))
                        if success:
                            signal.value = val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            successful_fc = fc
                            break

                        # Try generic readObject
                        if not self.connection: break
                        res = iec61850.IedConnection_readObject(self.connection, address, fc)
                        mms_val, success = extract_val(res)
                        if success:
                            val_str, val_type, error_msg = self._parse_mms_value(mms_val)
                            if not error_msg:
                                signal.value = val_str
                                signal.signal_type = val_type
                                signal.quality = SignalQuality.GOOD
                                signal.timestamp = datetime.now()
                                value_read = True
                                successful_fc = fc
                                self._safe_delete_mms(mms_val)
                                break
                            self._safe_delete_mms(mms_val)
                    except Exception as e:
                        last_error = str(e)

                if value_read and any(x in address for x in [".stVal", "$stVal", ".mag", "$mag"]):
                    try:
                        last_sep_idx = max(address.rfind('.'), address.rfind('$'))
                        if last_sep_idx != -1 and self.connection:
                            base_do = address[:last_sep_idx]
                            for suffix in [".t", ".T", "$t", "$T"]:
                                t_addr = f"{base_do}{suffix}"
                                res_t = iec61850.IedConnection_readObject(self.connection, t_addr, successful_fc) 
                                mms_t, ok_t = extract_val(res_t)
                                if ok_t:
                                    ts = self._get_timestamp_from_mms(mms_t)
                                    if ts: signal.timestamp = ts
                                    self._safe_delete_mms(mms_t)
                                    break
                    except: pass

            if not value_read:
                signal.quality = SignalQuality.INVALID
                signal.value = None
                signal.error = last_error or "Could not read with any FC"

            # ENUM MAPPING
            if value_read and getattr(signal, 'enum_map', None) and isinstance(signal.value, int):
                if signal.value in signal.enum_map:
                    signal.value = f"{signal.enum_map[signal.value]} ({signal.value})"
                    signal.signal_type = SignalType.STATE
            
            self._emit_update(signal)
            return signal
            
        except Exception as e:
            if self.event_logger:
                self.event_logger.error("IEC61850", f"CRITICAL READ FAILURE for {signal.address}: {e}")
            signal.quality = SignalQuality.INVALID
            
        return signal
            
        return signal

    def send_command(self, signal: Signal, value: Any, params: dict = None) -> bool:
        """
        High-level command sender that automatically handles SBO workflow.
        """
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ SEND_COMMAND {signal.address} = {value}")

        if not self.connected or not self.connection:
            return False

        try:
            object_ref = self._get_control_object_reference(signal.address)
            ctx = self.controls.get(object_ref) or self.init_control_context(signal.address)
            if not ctx: return False

            # Use high-level ControlObjectClient for SBO flow
            if ctx.ctl_model.is_sbo:
                if self.event_logger:
                    self.event_logger.info("IEC61850", f"SBO sequence for {object_ref} (model={ctx.ctl_model.name})")

                # Create ONE client for the entire sequence
                with self._lock:
                    client = iec61850.ControlObjectClient_create(ctx.object_reference, self.connection)
                
                if not client:
                    if self.event_logger: self.event_logger.error("IEC61850", "Failed to create ControlObjectClient")
                    return self._fallback_operate(signal, value, object_ref)

                try:
                    # SELECT phase
                    if not self.select(signal, value, params, control_client=client):
                        return False

                    # WAIT phase
                    sbo_timeout = params.get('sbo_timeout', 100) if params else 100
                    time.sleep(sbo_timeout / 1000.0)

                    # OPERATE phase (sharing same client)
                    return self.operate(signal, value, params, control_client=client)
                finally:
                    with self._lock:
                        iec61850.ControlObjectClient_destroy(client)
            else:
                # Direct Control
                return self.operate(signal, value, params)

        except Exception as e:
            logger.error(f"Send command failed: {e}")
            return False

    def select(self, signal: Signal, value: Any = None, params: dict = None, control_client: Any = None) -> bool:
        """Perform SELECT phase."""
        own_client = False
        try:
            object_ref = self._get_control_object_reference(signal.address)
            if not control_client:
                with self._lock:
                    control_client = iec61850.ControlObjectClient_create(object_ref, self.connection)
                own_client = True

            if not control_client:
                return self._fallback_select(signal, value, object_ref)

            ctx = self.controls.get(object_ref)
            origin_id, origin_cat = self._compute_originator_info(ctx)
            
            with self._lock:
                if not self.connection: return False
                iec61850.ControlObjectClient_setOriginator(control_client, origin_id, origin_cat)
                ctl_model = iec61850.ControlObjectClient_getControlModel(control_client)
            
            success = False
            if ctl_model == 4 and value is not None: # SBO_ENHANCED
                mms_val = self._create_mms_value(value, signal)
                if mms_val:
                    try:
                        with self._lock:
                            if not self.connection: return False
                            success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_val)
                    finally:
                        self._safe_delete_mms(mms_val)
            else:
                with self._lock:
                    if not self.connection: return False
                    success = iec61850.ControlObjectClient_select(control_client)

            if success:
                if self.event_logger: self.event_logger.transaction("IEC61850", "← SELECT SUCCESS")
                if ctx:
                    ctx.state = ControlState.SELECTED
                    # Try to capture the updated ctlNum assigned by IED during selection
                    try:
                         with self._lock:
                             if not self.connection: return True
                             val, err = iec61850.IedConnection_readInt32Value(self.connection, f"{object_ref}.ctlNum", iec61850.IEC61850_FC_ST)
                         if err == iec61850.IED_ERROR_OK:
                             ctx.ctl_num = val
                             if self.event_logger: self.event_logger.debug("IEC61850", f"Captured ied-assigned ctlNum: {val}")
                    except: pass
                return True
            else:
                with self._lock:
                    if not self.connection: return False
                    err_code = iec61850.ControlObjectClient_getLastError(control_client)
                err_msg = IED_CLIENT_ERROR_MAP.get(err_code, f"Unknown IED error ({err_code})")
                self._last_control_error = f"SELECT FAILED: {err_msg}"
                
                if self.event_logger: self.event_logger.error("IEC61850", f"SELECT FAILED (IED Error: {err_code} - {err_msg})")
                return self._fallback_select(signal, value, object_ref)

        finally:
            if own_client and control_client:
                with self._lock: 
                    self._safe_destroy_control_client(control_client)

    def operate(self, signal: Signal, value: Any, params: dict = None, control_client: Any = None) -> bool:
        """Perform OPERATE phase."""
        own_client = False
        try:
            object_ref = self._get_control_object_reference(signal.address)
            if not control_client:
                with self._lock:
                    control_client = iec61850.ControlObjectClient_create(object_ref, self.connection)
                own_client = True

            if not control_client:
                return self._fallback_operate(signal, value, object_ref)

            ctx = self.controls.get(object_ref)
            origin_id, origin_cat = self._compute_originator_info(ctx)
            
            with self._lock:
                if not self.connection: return False
                iec61850.ControlObjectClient_setOriginator(control_client, origin_id, origin_cat)
                # Sync ctlNum only if we are using a fresh client for this phase
                if own_client and ctx and ctx.ctl_num is not None:
                    iec61850.ControlObjectClient_setCtlNum(control_client, ctx.ctl_num)

            mms_val = self._create_mms_value(value, signal)
            if not mms_val: return False

            try:
                with self._lock:
                    if not self.connection: return False
                    success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
                if success:
                    if self.event_logger: self.event_logger.transaction("IEC61850", "← OPERATE SUCCESS")
                    if ctx:
                        ctx.state = ControlState.OPERATED
                        ctx.ctl_num = (ctx.ctl_num + 1) % 256
                    return True
                else:
                    with self._lock:
                        if not self.connection: return False
                        err_code = iec61850.ControlObjectClient_getLastError(control_client)
                    err_msg = IED_CLIENT_ERROR_MAP.get(err_code, f"Unknown IED error ({err_code})")
                    self._last_control_error = f"OPERATE FAILED: {err_msg}"
                    
                    if self.event_logger: self.event_logger.error("IEC61850", f"OPERATE FAILED (IED Error: {err_code} - {err_msg})")
                    return self._fallback_operate(signal, value, object_ref)
            finally:
                self._safe_delete_mms(mms_val)

        except Exception as e:
            logger.error(f"Operate failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"OPERATE EXCEPTION: {e}")
                self.event_logger.warning("IEC61850", f"Trying fallback method...")
            
            object_ref = self._get_control_object_reference(signal.address)
            if object_ref:
                return self._fallback_operate(signal, value, object_ref)
            return False
        finally:
            if own_client and control_client:
                with self._lock: 
                    self._safe_destroy_control_client(control_client)

    def init_control_context(self, signal_address: str) -> Optional[ControlObjectRuntime]:
        """
        Step 1: JIT Control Context Initialization with Standard-Compliant Redirection.
        """
        if not self.connected or not self.connection:
            return None
            
        original_do_ref = self._get_control_object_reference(signal_address)
        if not original_do_ref:
            return None

        object_ref = original_do_ref

        # Standard-Compliant CB Control Chain Fix:
        # If user targets XCBR/Pos, redirect to CSWI/Pos (Control Interface)
        if "XCBR" in object_ref and "Pos" in object_ref:
            cswi_ref = object_ref.replace("XCBR", "CSWI")
            if self.event_logger:
                self.event_logger.info("IEC61850", f"Redirecting Control Chain from {object_ref} to {cswi_ref} (CSWI)")
            object_ref = cswi_ref
            
        if self.event_logger:
            self.event_logger.info("IEC61850", f"Initializing Control Context for {object_ref}")
            
        # 1.1 Read ctlModel and ctlNum (Action 3)
        ctl_model_val = 0
        ctl_num_val = 0
        supports_oper = False
        supports_sbo = False
        supports_sbow = False
        
        with self._lock:
            if not self.connection: return None
            try:
                 # Try reading .ctlModel or $ctlModel with FC=CF
                 # Some IEDs use . while others (like the user's) use $
                 val = 0
                 err = iec61850.IED_ERROR_OK
                 
                 for sep in [".", "$"]:
                     if not self.connection: break
                     val, err = iec61850.IedConnection_readInt32Value(
                         self.connection, f"{object_ref}{sep}ctlModel", iec61850.IEC61850_FC_CF
                     )
                     if err == iec61850.IED_ERROR_OK:
                         ctl_model_val = val
                         if self.event_logger:
                             self.event_logger.debug("IEC61850", f"  Read ctlModel using '{sep}': {ctl_model_val}")
                         break
                 
                 # Action 3: Read current ctlNum for echoing
                 for sep in [".", "$"]:
                     if not self.connection: break
                     val_num, err_num = iec61850.IedConnection_readInt32Value(
                         self.connection, f"{object_ref}{sep}ctlNum", iec61850.IEC61850_FC_ST
                     )
                     if err_num == iec61850.IED_ERROR_OK:
                         ctl_num_val = val_num
                         if self.event_logger:
                             self.event_logger.debug("IEC61850", f"  Read Current ctlNum using '{sep}': {ctl_num_val}")
                         break
            except Exception as e:
                 if self.event_logger:
                     self.event_logger.warning("IEC61850", f"  Exception reading control attributes: {e}")
            
            # 1.3 Discover Oper/SBO
            try:
                if not self.connection: return None
                # Browse the DO to find Oper/SBO
                ret = iec61850.IedConnection_getDataDirectory(self.connection, object_ref)
                children = ret[0] if isinstance(ret, (list, tuple)) else ret
                if children:
                    names = self._extract_string_list(children)
                    self._safe_destroy_list(children)
                    
                    if "Oper" in names: supports_oper = True
                    if "SBO" in names: supports_sbo = True
                    if "SBOw" in names: supports_sbow = True
            except: pass
        
        if self.event_logger:
            self.event_logger.debug("IEC61850", f"  Capabilities: Oper={supports_oper}, SBO={supports_sbo}, SBOw={supports_sbow}")
            
        # Build Context
        ctx = ControlObjectRuntime(object_reference=object_ref)
        ctx.update_from_ctl_model_int(ctl_model_val)
        ctx.ctl_num = ctl_num_val # Initialization with IED's current value

        # Determine SBO Reference
        if supports_sbow:
            ctx.sbo_reference = f"{object_ref}.SBOw"
        elif supports_sbo:
            ctx.sbo_reference = f"{object_ref}.SBO"
        # Add to cache (Multiple entries for robust lookup)
        self.controls[signal_address] = ctx 
        self.controls[original_do_ref] = ctx
        self.controls[object_ref] = ctx
        
        return ctx

    def clear_control_context(self, signal_address: str):
        """Teardown control context."""
        object_ref = self._get_control_object_reference(signal_address)
        if object_ref and object_ref in self.controls:
             del self.controls[object_ref]

    def cancel(self, signal: Signal) -> bool:
        """Cancel selection."""
        if not self.connected or not self.connection:
            return False
        object_ref = self._get_control_object_reference(signal.address)
        if not object_ref: return False
        try:
            with self._lock:
                if not self.connection: return False
                struct = iec61850.MmsValue_newStructure(1)
                iec61850.MmsValue_setElement(struct, 0, iec61850.MmsValue_newBoolean(True))
                err = iec61850.IedConnection_writeObject(self.connection, f"{object_ref}.Cancel", iec61850.IEC61850_FC_CO, struct)
                self._safe_delete_mms(struct)
            return err == iec61850.IED_ERROR_OK
        except:
            return False

    def _get_control_object_reference(self, address: str) -> str:
        """Extract the Control Object Reference (DO path)."""
        if not address: return None
        # Order matters: try longer suffixes first to avoid partial matches
        # Support both . and $ separators
        suffixes = [
            ".Oper.ctlVal", "$Oper$ctlVal", 
            ".SBO.ctlVal", "$SBO$ctlVal", 
            ".SBOw.ctlVal", "$SBOw$ctlVal", 
            ".Cancel.ctlVal", "$Cancel$ctlVal",
            ".Oper", "$Oper", 
            ".SBO", "$SBO", 
            ".SBOw", "$SBOw", 
            ".Cancel", "$Cancel", 
            ".ctlVal", "$ctlVal", 
            ".stVal", "$stVal", 
            ".q", "$q", 
            ".t", "$t"
        ]
        for suffix in suffixes:
            if address.endswith(suffix):
                return address[:-len(suffix)]
        return address

    def _create_mms_value(self, value, signal):
        """Create MmsValue with inverted ctlVal for this IED."""
        if isinstance(value, bool):
            return iec61850.MmsValue_newBoolean(not value)
        elif isinstance(value, int):
            return iec61850.MmsValue_newInt32(0 if value else 1)
        else:
            return None

    def _build_operate_struct(self, value, ctx: ControlObjectRuntime, is_select: bool = False):
        """Builds the complex Operate structure by modifying an existing template from the IED."""
        struct = None
        try:
             # Strategy: Use existing structure as template to ensure all types (origin, T, etc.) match IED expectations
             path = ctx.sbo_reference if is_select else f"{ctx.object_reference}.Oper"
             with self._lock:
                 struct, err = iec61850.IedConnection_readObject(self.connection, path, iec61850.IEC61850_FC_CO)
             
             if not struct:
                 # Minimal fallback if read fails 
                 struct = iec61850.MmsValue_newStructure(6 if is_select else 7)
                 if self.event_logger: self.event_logger.debug("IEC61850", f"Could not read {path}. Building from scratch.")

             if not struct: return None
             
             # Overwrite ONLY critical components
             # 0: ctlVal (BOOLEAN) - inverted for this IED
             iec61850.MmsValue_setElement(struct, 0, iec61850.MmsValue_newBoolean(not bool(value)))
             
             size = iec61850.MmsValue_getArraySize(struct)
             # ctlNum index: SBOw=2, Oper=3
             ctl_num_idx = 2 if size == 6 else 3
             if size > ctl_num_idx:
                 iec61850.MmsValue_setElement(struct, ctl_num_idx, iec61850.MmsValue_newUnsigned(ctx.ctl_num))

             if self.event_logger:
                 self.event_logger.debug("IEC61850", f"Modified {path} structure (size {size}): ctlVal={bool(value)}, ctlNum={ctx.ctl_num}")
             
             return struct
        except Exception as e:
             logger.error(f"Failed to build operate struct: {e}")
             if struct: iec61850.MmsValue_delete(struct)
             return None
        except Exception as e:
             logger.error(f"Failed to build operate struct: {e}")
             if struct: iec61850.MmsValue_delete(struct)
             return None


    def _compute_originator_info(self, ctx):
        """Return a tuple (origin_id, origin_cat) normalized for ControlAction calls.

        Rules:
        - origin_cat must be between 1 and 7; 0 or missing -> default to 3 (Remote)
        - origin_id default is "SCADA"; treat "ScadaScout" as default placeholder
        - This is pure-Python and unit-testable.
        """
        default_cat = 3
        default_id = "SCADA"
        if not ctx:
            return default_id, default_cat
        cat = getattr(ctx, 'originator_cat', None)
        ident = getattr(ctx, 'originator_id', None)
        try:
            cat = int(cat) if cat is not None else 0
        except Exception:
            cat = 0
        if not (1 <= cat <= 7):
            cat = default_cat
        if not ident or str(ident).strip() == "ScadaScout":
            ident = default_id
        return ident, cat

    def _normalize_ctlnum(self, val) -> int:
        """Normalize a ctlNum-like value to integer in 0..255 (uint8).

        - Accepts int-like or numeric strings (decimal/hex).
        - On parse failure, raises ValueError.
        - Ensures result is in 0..255 by modulo 256.
        """
        if val is None:
            raise ValueError("ctlNum is None")
        # Accept strings like '0x1' as hex
        if isinstance(val, str):
            text = val.strip()
            if text.lower().startswith('0x'):
                num = int(text, 16)
            else:
                num = int(text)
        else:
            num = int(val)
        # Normalize into uint8 range
        return num % 256

    def _wait_for_ctlnum(self, ctx, object_ref: str, timeout_ms: int = 600) -> bool:
        """Wait up to timeout_ms for the IED-assigned ctlNum to become available.

        Strategy (in order):
        - poll `{sbo_ref}.ctlNum` if ctx.sbo_reference available
        - poll `{object_ref}.ctlNum`
        - try reading full SBO structure and extract element[3]
        - if native async select callback is available, invoke it once and wait briefly

        Returns True and updates ctx.ctl_num when a non-None ctlNum is found. Returns False on timeout.
        """
        if not ctx:
            return False

        deadline = time.time() + (timeout_ms / 1000.0)
        # quick helper to attempt reads
        def _attempt_reads() -> int | None:
            # 1) SBOx.ctlNum
            sbo = getattr(ctx, 'sbo_reference', None)
            if sbo:
                try:
                    with self._lock:
                        if not self.connection: return None
                        v, e = iec61850.IedConnection_readInt32Value(self.connection, f"{sbo}.ctlNum", iec61850.IEC61850_FC_ST)
                    if e == iec61850.IED_ERROR_OK and v is not None:
                        return int(v) % 256
                except Exception:
                    pass
                # try reading full structure
                try:
                    with self._lock:
                        if not self.connection: return None
                        m = iec61850.IedConnection_readObject(self.connection, f"{sbo}", iec61850.IEC61850_FC_ST)
                    if m:
                        try:
                            elem = iec61850.MmsValue_getElement(m, 3)
                            if elem:
                                return int(iec61850.MmsValue_toInt32(elem)) % 256
                        finally:
                            self._safe_delete_mms(m)
                except Exception:
                    pass

            # 2) object_ref.ctlNum
            try:
                with self._lock:
                    if not self.connection: return None
                    v, e = iec61850.IedConnection_readInt32Value(self.connection, f"{object_ref}.ctlNum", iec61850.IEC61850_FC_ST)
                if e == iec61850.IED_ERROR_OK and v is not None:
                    return int(v) % 256
            except Exception:
                pass

            return None

        # fast-poll until deadline
        while time.time() < deadline:
            num = _attempt_reads()
            if num is not None:
                try:
                    ctx.ctl_num = self._normalize_ctlnum(num)
                except Exception:
                    ctx.ctl_num = int(num) % 256
                # clear any previous control error
                try: delattr(self, '_last_control_error')
                except Exception: pass
                return True
            time.sleep(0.08)

        # last-resort: try async ControlObjectClient_selectAsync to capture ControlAction ctlNum
        try:
            if hasattr(iec61850, 'ControlObjectClient_selectAsync') and hasattr(self, 'controls'):
                # create a temporary client and call async select to get callback
                try:
                    client = iec61850.ControlObjectClient_create(object_ref, self.connection)
                except Exception:
                    client = None
                if client:
                    import threading
                    ev = threading.Event()
                    captured = {'ctl': None}

                    def _cb(req_id, action_ptr, err_code, action_type, is_select):
                        try:
                            num = iec61850.ControlAction_getCtlNum(action_ptr)
                            captured['ctl'] = int(num) % 256
                        except Exception:
                            captured['ctl'] = None
                        finally:
                            ev.set()

                    try:
                        # prefer selectWithValueAsync when available
                        if hasattr(iec61850, 'ControlObjectClient_selectWithValueAsync'):
                            with self._lock:
                                if not self.connection: return False
                                iec61850.ControlObjectClient_selectWithValueAsync(client, None, None, _cb, None)
                        else:
                            with self._lock:
                                if not self.connection: return False
                                iec61850.ControlObjectClient_selectAsync(client, None, _cb, None)

                        if ev.wait(min(0.5, timeout_ms/1000.0)) and captured['ctl'] is not None:
                            ctx.ctl_num = captured['ctl']
                            try: delattr(self, '_last_control_error')
                            except Exception: pass
                            return True
                    finally:
                        self._safe_destroy_control_client(client)
        except Exception:
            pass

        # timed out: set a human-friendly control error for UI/diagnostics
        self._last_control_error = "Could not determine IED-assigned ctlNum after SELECT"
        return False

    def _fallback_select(self, signal: Signal, value: Any, object_ref: str) -> bool:
        """
        Fallback method: Write to .SBO or .SBOw attribute with proper structure.
        Used when ControlObjectClient_create fails (e.g., IED timeout, incompatibility).
        """
        if self.event_logger:
            self.event_logger.info("IEC61850", "Using FALLBACK method: Direct write to SBO attribute")
        
        try:
            # Get control context for ctlNum and originator info
            ctx = self.controls.get(object_ref)
            
            # Try SBOw first (enhanced), then SBO (normal) with both separators
            attrs_to_try = []
            for sep in [".", "$"]:
                attrs_to_try.extend([f"{object_ref}{sep}SBOw", f"{object_ref}{sep}SBO"])
                
            for sbo_attr in attrs_to_try:
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"Trying write to {sbo_attr}")
                
                # For SBO, we need to write a structure, not just a simple value
                # Try with full 7-element structure first (like Operate)
                if ctx:
                    mms_val = self._build_operate_struct(value, ctx, is_select=True)
                else:
                    # If no context, create a simple boolean value
                    mms_val = self._create_mms_value(value, signal) if value is not None else iec61850.MmsValue_newBoolean(True)
                
                if not mms_val:
                    continue
                
                try:
                    with self._lock:
                        err = iec61850.IedConnection_writeObject(self.connection, sbo_attr, iec61850.IEC61850_FC_CO, mms_val)
                    iec61850.MmsValue_delete(mms_val)
                    
                    if err == iec61850.IED_ERROR_OK:
                        if self.event_logger:
                            self.event_logger.transaction("IEC61850", "← FALLBACK SELECT SUCCESS")
                            self.event_logger.info("IEC61850", f"Fallback SELECT succeeded with {sbo_attr}")
                        
                        # Update context if it exists
                        if ctx:
                            ctx.state = ControlState.SELECTED
                            ctx.last_select_time = datetime.now()
                        return True
                    else:
                        if self.event_logger:
                            self.event_logger.error("IEC61850", f"Fallback SELECT to {sbo_attr} failed with IED error: {err}")
                except Exception as e:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"Write to {sbo_attr} failed: {e}")
                    continue
            
            if self.event_logger:
                self.event_logger.error("IEC61850", "← FALLBACK SELECT FAILED: All methods exhausted")
            return False
            
        except Exception as e:
            logger.error(f"Fallback select failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"FALLBACK SELECT EXCEPTION: {e}")
            return False

    def _fallback_operate(self, signal: Signal, value: Any, object_ref: str) -> bool:
        """
        Fallback method: Write to .Oper attribute with proper structure.
        Used when ControlObjectClient_create fails (e.g., IED timeout, incompatibility).
        """
        if self.event_logger:
            self.event_logger.info("IEC61850", "Using FALLBACK method: Direct write to Oper attribute")
        
        try:
            # Get control context for ctlNum and originator info
            ctx = self.controls.get(object_ref)
            
            # Try direct write to Oper or Oper.ctlVal with both separators
            attrs_to_try = []
            for sep in [".", "$"]:
                attrs_to_try.extend([f"{object_ref}{sep}Oper", f"{object_ref}{sep}Oper{sep}ctlVal"])
                
            for oper_attr in attrs_to_try:
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"Writing to {oper_attr}")
                
                # For .Oper, use full structure; for .Oper.ctlVal, use simple value
                if oper_attr.endswith(".Oper") or oper_attr.endswith("$Oper"):
                    if ctx:
                        mms_val = self._build_operate_struct(value, ctx, is_select=False)
                    else:
                        # No context - skip structure writes
                        continue
                else:
                    # .Oper.ctlVal - write simple value
                    mms_val = self._create_mms_value(value, signal)
                
                if not mms_val:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"Could not create MmsValue for {oper_attr}")
                    continue
                
                try:
                    with self._lock:
                        err = iec61850.IedConnection_writeObject(self.connection, oper_attr, iec61850.IEC61850_FC_CO, mms_val)
                    iec61850.MmsValue_delete(mms_val)
                    
                    if err == iec61850.IED_ERROR_OK:
                        if self.event_logger:
                            self.event_logger.transaction("IEC61850", "← FALLBACK OPERATE SUCCESS")
                            self.event_logger.info("IEC61850", f"Fallback OPERATE succeeded with {oper_attr}")
                        
                        # Update context if it exists
                        if ctx:
                            ctx.state = ControlState.OPERATED
                            ctx.last_operate_time = datetime.now()
                            try:
                                ctx.ctl_num = (int(ctx.ctl_num) + 1) % 256
                            except Exception:
                                ctx.ctl_num = 0
                        return True
                    else:
                        if self.event_logger:
                            self.event_logger.debug("IEC61850", f"Write to {oper_attr} returned error {err}")
                        # Try next method
                        continue
                        
                except Exception as e:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"Write to {oper_attr} failed: {e}")
                    continue
            
            if self.event_logger:
                self.event_logger.error("IEC61850", "← FALLBACK OPERATE FAILED: All methods exhausted")
            return False
            
        except Exception as e:
            logger.error(f"Fallback operate failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"FALLBACK OPERATE EXCEPTION: {e}")
            return False

    def write_signal(self, signal: Signal, value: Any) -> bool:
        """Generic write for non-control attributes."""
        if not self.connected: return False
        
        # Check if it's actually a control and redirect
        obj_ref = self._get_control_object_reference(signal.address)
        # If it's a known control DA, use operate/select
        if "ctlVal" in signal.address or "Oper" in signal.address:
            return self.operate(signal, value)

        try:
            mms_value = self._create_mms_value(value, signal)
            if not mms_value: return False
            
            # Use CF as default for writes (usually settings)
            with self._lock:
                if not self.connection: return False
                err = iec61850.IedConnection_writeObject(self.connection, signal.address, iec61850.IEC61850_FC_CF, mms_value)
                self._safe_delete_mms(mms_value)
            return err == iec61850.IED_ERROR_OK
        except:
            return False

    def _detect_vendor_pre_connect(self):
        pass    
    # Device Properties Retrieval Methods
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get comprehensive device information for properties dialog."""
        info = {
            "vendor": "Unknown",
            "model": "Unknown",
            "revision": "Unknown",
            "server_identity": None,
            "datasets_count": 0,
            "reports_count": 0,
            "goose_count": 0,
            "control_objects_count": len(self.controls) if hasattr(self, 'controls') else 0,
            "logical_devices": [],
            "communication_params": {}
        }
        
        if not self.connected or not self.connection:
            return info
        
        try:
            # Try to read server identity
            with self._lock:
                if not self.connection: return info
                server_identity = iec61850.IedConnection_getServerIdentity(self.connection)
                if server_identity:
                    info["server_identity"] = server_identity
        except Exception as e:
            logger.debug(f"Could not retrieve server identity: {e}")
        
        return info
    
    def get_datasets_info(self) -> list:
        """Get detailed information about all datasets."""
        datasets = []
        
        if not self.connected or not self.connection:
            return datasets
        
        try:
            # Get logical device list
            with self._lock:
                if not self.connection: return datasets
                ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            if not ld_list:
                return datasets
            
            ld_names = self._extract_string_list(ld_list)
            
            for ld_name in ld_names:
                # Get logical nodes
                with self._lock:
                    if not self.connection: break
                    ret_ln = iec61850.IedConnection_getLogicalDeviceDirectory(self.connection, ld_name)
                ln_list = ret_ln[0] if isinstance(ret_ln, (list, tuple)) else ret_ln
                
                if ln_list:
                    ln_names = self._extract_string_list(ln_list)
                    
                    for ln_name in ln_names:
                        full_ln_ref = f"{ld_name}/{ln_name}"
                        
                        # Get datasets for this LN
                        with self._lock:
                            if not self.connection: break
                            ret_ds = iec61850.IedConnection_getLogicalNodeDirectory(
                                self.connection,
                                full_ln_ref,
                                iec61850.ACSI_CLASS_DATA_SET
                            )
                        
                        ds_list = ret_ds[0] if isinstance(ret_ds, (list, tuple)) else ret_ds
                        if ds_list:
                            ds_names = self._extract_string_list(ds_list)
                            
                            for ds_name in ds_names:
                                dataset_ref = self._normalize_dataset_ref(full_ln_ref, ds_name)
                                
                                # Get dataset entries
                                entries = []
                                try:
                                    with self._lock:
                                        if not self.connection: break
                                        ret_entries = iec61850.IedConnection_getDataSetDirectory(
                                            self.connection, dataset_ref
                                        )
                                    
                                    if ret_entries and len(ret_entries) > 1:
                                        entry_list = ret_entries[1]
                                        if entry_list:
                                            entry_names = self._extract_string_list(entry_list)
                                            entries = entry_names if entry_names else []
                                except Exception as e:
                                    logger.debug(f"Could not read dataset entries for {dataset_ref}: {e}")
                                
                                datasets.append({
                                    "name": ds_name,
                                    "logical_node": full_ln_ref,
                                    "reference": dataset_ref,
                                    "entries": entries,
                                    "entry_count": len(entries)
                                })
                            
                            self._safe_destroy_list(ds_list)
                    
                    self._safe_destroy_list(ln_list)
            
            self._safe_destroy_list(ld_list)
        
        except Exception as e:
            logger.error(f"Error retrieving datasets info: {e}")
        
        return datasets
    
    def get_reports_info(self) -> list:
        """Get detailed information about all report control blocks."""
        reports = []
        
        if not self.connected or not self.connection:
            return reports
        
        try:
            # Get logical device list
            with self._lock:
                if not self.connection: return reports
                ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            if not ld_list:
                return reports
            
            ld_names = self._extract_string_list(ld_list)
            
            for ld_name in ld_names:
                # Get logical nodes
                with self._lock:
                    if not self.connection: break
                    ret_ln = iec61850.IedConnection_getLogicalDeviceDirectory(self.connection, ld_name)
                ln_list = ret_ln[0] if isinstance(ret_ln, (list, tuple)) else ret_ln
                
                if ln_list:
                    ln_names = self._extract_string_list(ln_list)
                    
                    for ln_name in ln_names:
                        full_ln_ref = f"{ld_name}/{ln_name}"
                        
                        # Get URCBs
                        try:
                            with self._lock:
                                if not self.connection: break
                                ret_urcb = iec61850.IedConnection_getLogicalNodeDirectory(
                                    self.connection,
                                    full_ln_ref,
                                    iec61850.ACSI_CLASS_URCB
                                )
                            
                            urcb_list = ret_urcb[0] if isinstance(ret_urcb, (list, tuple)) else ret_urcb
                            if urcb_list:
                                urcb_names = self._extract_string_list(urcb_list)
                                
                                for rcb_name in urcb_names:
                                    rcb_info = self._read_report_attributes(
                                        full_ln_ref, rcb_name, "URCB", iec61850.IEC61850_FC_RP
                                    )
                                    if rcb_info:
                                        reports.append(rcb_info)
                                
                                self._safe_destroy_list(urcb_list)
                        except Exception as e:
                            logger.debug(f"Error reading URCBs for {full_ln_ref}: {e}")
                        
                        # Get BRCBs
                        try:
                            with self._lock:
                                if not self.connection: break
                                ret_brcb = iec61850.IedConnection_getLogicalNodeDirectory(
                                    self.connection,
                                    full_ln_ref,
                                    iec61850.ACSI_CLASS_BRCB
                                )
                            
                            brcb_list = ret_brcb[0] if isinstance(ret_brcb, (list, tuple)) else ret_brcb
                            if brcb_list:
                                brcb_names = self._extract_string_list(brcb_list)
                                
                                for rcb_name in brcb_names:
                                    rcb_info = self._read_report_attributes(
                                        full_ln_ref, rcb_name, "BRCB", iec61850.IEC61850_FC_BR
                                    )
                                    if rcb_info:
                                        reports.append(rcb_info)
                                
                                self._safe_destroy_list(brcb_list)
                        except Exception as e:
                            logger.debug(f"Error reading BRCBs for {full_ln_ref}: {e}")
                    
                    self._safe_destroy_list(ln_list)
            
            self._safe_destroy_list(ld_list)
        
        except Exception as e:
            logger.error(f"Error retrieving reports info: {e}")
        
        return reports
    
    def _read_report_attributes(self, full_ln_ref: str, rcb_name: str, rcb_type: str, fc: int) -> Optional[Dict[str, Any]]:
        """Read all attributes of a report control block."""
        rcb_ref = f"{full_ln_ref}.{rcb_name}"
        
        rcb_info = {
            "name": rcb_name,
            "logical_node": full_ln_ref,
            "reference": rcb_ref,
            "type": rcb_type,
            "rpt_id": "",
            "dataset": "",
            "conf_rev": 0,
            "opt_flds": "",
            "buf_time": 0,
            "trg_ops": "",
            "intg_pd": 0,
            "gi": False,
            "enabled": False
        }
        
        try:
            # RptID
            try:
                with self._lock:
                    if self.connection:
                        rpt_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.RptID", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["rpt_id"] = rpt_id
            except Exception:
                pass
            
            # DatSet
            try:
                with self._lock:
                    if self.connection:
                        dat_set, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.DatSet", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["dataset"] = dat_set
            except Exception:
                pass
            
            # ConfRev
            try:
                with self._lock:
                    if self.connection:
                        conf_rev, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.ConfRev", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["conf_rev"] = conf_rev
            except Exception:
                pass
            
            # BufTm
            try:
                with self._lock:
                    if self.connection:
                        buf_tm, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.BufTm", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["buf_time"] = buf_tm
            except Exception:
                pass
            
            # IntgPd
            try:
                with self._lock:
                    if self.connection:
                        intg_pd, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.IntgPd", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["intg_pd"] = intg_pd
            except Exception:
                pass
            
            # TrgOps (bit string)
            try:
                with self._lock:
                    if self.connection:
                        trg_ops, err = iec61850.IedConnection_readBitStringValue(self.connection, f"{rcb_ref}.TrgOps", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["trg_ops"] = str(trg_ops)
            except Exception:
                pass
            
            # OptFlds (bit string)
            try:
                with self._lock:
                    if self.connection:
                        opt_flds, err = iec61850.IedConnection_readBitStringValue(self.connection, f"{rcb_ref}.OptFlds", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["opt_flds"] = str(opt_flds)
            except Exception:
                pass
            
            # RptEna (enabled)
            try:
                with self._lock:
                    if self.connection:
                        rpt_ena, err = iec61850.IedConnection_readBooleanValue(self.connection, f"{rcb_ref}.RptEna", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["enabled"] = rpt_ena
            except Exception:
                pass
            
            # GI (General Interrogation)
            try:
                with self._lock:
                    if self.connection:
                        gi, err = iec61850.IedConnection_readBooleanValue(self.connection, f"{rcb_ref}.GI", fc)
                        if err == iec61850.IED_ERROR_OK:
                            rcb_info["gi"] = gi
            except Exception:
                pass
        
        except Exception as e:
            logger.debug(f"Error reading report attributes for {rcb_ref}: {e}")
        
        return rcb_info
    
    def get_goose_info(self) -> list:
        """Get detailed information about all GOOSE control blocks."""
        goose_cbs = []
        
        if not self.connected or not self.connection:
            return goose_cbs
        
        try:
            # Get logical device list
            with self._lock:
                ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            if not ld_list:
                return goose_cbs
            
            ld_names = self._extract_string_list(ld_list)
            
            for ld_name in ld_names:
                # Get logical nodes
                with self._lock:
                    ret_ln = iec61850.IedConnection_getLogicalDeviceDirectory(self.connection, ld_name)
                ln_list = ret_ln[0] if isinstance(ret_ln, (list, tuple)) else ret_ln
                
                if ln_list:
                    ln_names = self._extract_string_list(ln_list)
                    
                    for ln_name in ln_names:
                        full_ln_ref = f"{ld_name}/{ln_name}"
                        
                        # Get GOOSE control blocks
                        try:
                            with self._lock:
                                ret_gocb = iec61850.IedConnection_getLogicalNodeDirectory(
                                    self.connection,
                                    full_ln_ref,
                                    iec61850.ACSI_CLASS_GoCB
                                )
                            
                            gocb_list = ret_gocb[0] if isinstance(ret_gocb, (list, tuple)) else ret_gocb
                            if gocb_list:
                                gocb_names = self._extract_string_list(gocb_list)
                                
                                for gocb_name in gocb_names:
                                    gocb_info = self._read_goose_attributes(full_ln_ref, gocb_name)
                                    if gocb_info:
                                        goose_cbs.append(gocb_info)
                                
                                try:
                                    iec61850.LinkedList_destroy(gocb_list)
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.debug(f"Error reading GOOSE CBs for {full_ln_ref}: {e}")
                    
                    try:
                        iec61850.LinkedList_destroy(ln_list)
                    except Exception:
                        pass
            
            try:
                iec61850.LinkedList_destroy(ld_list)
            except Exception:
                pass
        
        except Exception as e:
            logger.error(f"Error retrieving GOOSE info: {e}")
        
        return goose_cbs
    
    def _read_goose_attributes(self, full_ln_ref: str, gocb_name: str) -> Optional[Dict[str, Any]]:
        """Read all attributes of a GOOSE control block."""
        gocb_ref = f"{full_ln_ref}.{gocb_name}"
        fc = iec61850.IEC61850_FC_GO
        
        gocb_info = {
            "name": gocb_name,
            "logical_node": full_ln_ref,
            "reference": gocb_ref,
            "go_id": "",
            "dataset": "",
            "app_id": "",
            "conf_rev": 0,
            "nds_com": False,
            "min_time": 0,
            "max_time": 0,
            "fixed_offs": False,
            "go_ena": False
        }
        
        try:
            # GoID
            try:
                with self._lock:
                    go_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.GoID", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["go_id"] = go_id
            except Exception:
                pass
            
            # DatSet
            try:
                with self._lock:
                    dat_set, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.DatSet", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["dataset"] = dat_set
            except Exception:
                pass
            
            # AppID
            try:
                with self._lock:
                    app_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.AppID", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["app_id"] = app_id
            except Exception:
                pass
            
            # ConfRev
            try:
                with self._lock:
                    conf_rev, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{gocb_ref}.ConfRev", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["conf_rev"] = conf_rev
            except Exception:
                pass
            
            # MinTime
            try:
                with self._lock:
                    min_time, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{gocb_ref}.MinTime", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["min_time"] = min_time
            except Exception:
                pass
            
            # MaxTime
            try:
                with self._lock:
                    max_time, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{gocb_ref}.MaxTime", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["max_time"] = max_time
            except Exception:
                pass
            
            # GoEna (enabled)
            try:
                with self._lock:
                    go_ena, err = iec61850.IedConnection_readBooleanValue(self.connection, f"{gocb_ref}.GoEna", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["go_ena"] = go_ena
            except Exception:
                pass
            
            # NdsCom (needs commissioning)
            try:
                with self._lock:
                    nds_com, err = iec61850.IedConnection_readBooleanValue(self.connection, f"{gocb_ref}.NdsCom", fc)
                if err == iec61850.IED_ERROR_OK:
                    gocb_info["nds_com"] = nds_com
            except Exception:
                pass
        
        except Exception as e:
            logger.debug(f"Error reading GOOSE attributes for {gocb_ref}: {e}")
        
        return gocb_info