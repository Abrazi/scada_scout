from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime
import logging
import time
import threading

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
                            f"❌ IEC 61850 connection FAILED\n"
                            f"   {error_msg}\n"
                            f"   \n"
                            f"   Possible causes:\n"
                            f"   • No IEC 61850 server running on {self.config.ip_address}:{self.config.port}\n"
                            f"   • Server is running on a different port\n"
                            f"   • Firewall blocking the connection\n"
                            f"   \n"
                            f"   💡 To start a simulator: Right-click an IED → 'Start Simulator for this IED...'"
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
            with self._lock:
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
                        vendor_res = iec61850.IedConnection_readStringValue(self.connection, vendor_path, iec61850.IEC61850_FC_DC)
                    if isinstance(vendor_res, (list, tuple)) and vendor_res[1] == iec61850.IED_ERROR_OK:
                        vendor = vendor_res[0]
                        root.description = f"IED: {vendor}"
                        # If we have a vendor, maybe we can get a better name?
                        # But 'root.name' is used for the tree root.
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
                iec61850.LinkedList_destroy(ds_list)
            except Exception:
                pass
        except Exception:
            pass

    def _discover_datasets_online(self, full_ln_ref: str, ln_node: Node) -> None:
        try:
            with self._lock:
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
                return

            datasets_root = Node(name="DataSets", description="Container")
            for ds_name in ds_names:
                ds_node = Node(name=ds_name, description="Type=DataSet")
                dataset_ref = self._normalize_dataset_ref(full_ln_ref, ds_name)
                self._add_detail_leaf(ds_node, "Ref", dataset_ref)
                self._add_dataset_entries_online(dataset_ref, ds_node)
                datasets_root.children.append(ds_node)

            ln_node.children.append(datasets_root)
            iec61850.LinkedList_destroy(ds_list)
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
                    rpt_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.RptID", fc)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(rpt_node, "RptID", rpt_id)
                except Exception:
                    self._add_detail_leaf(rpt_node, "RptID", "")

                dat_set_val = ""
                try:
                    dat_set_val, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.DatSet", fc)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(rpt_node, "DatSet", dat_set_val)
                except Exception:
                    self._add_detail_leaf(rpt_node, "DatSet", "")

                for attr in ["BufTm", "IntgPd"]:
                    try:
                        val, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.{attr}", fc)
                        if err == iec61850.IED_ERROR_OK:
                            self._add_detail_leaf(rpt_node, attr, val)
                    except Exception:
                        self._add_detail_leaf(rpt_node, attr, "")

                for attr in ["TrgOps", "OptFlds"]:
                    try:
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
            try:
                iec61850.LinkedList_destroy(urcb_list)
            except Exception:
                pass
        except Exception:
            pass

        try:
            with self._lock:
                ret_brcb = iec61850.IedConnection_getLogicalNodeDirectory(
                    self.connection,
                    full_ln_ref,
                    iec61850.ACSI_CLASS_BRCB
                )
            brcb_list = ret_brcb[0] if isinstance(ret_brcb, (list, tuple)) else ret_brcb
            brcb_names = self._extract_string_list(brcb_list) if brcb_list else []
            add_report_nodes(brcb_names, "BRCB", iec61850.IEC61850_FC_BR)
            try:
                iec61850.LinkedList_destroy(brcb_list)
            except Exception:
                pass
        except Exception:
            pass

        if reports_root is not None:
            ln_node.children.append(reports_root)

    def _discover_goose_online(self, full_ln_ref: str, ln_node: Node) -> None:
        try:
            with self._lock:
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
                return

            goose_root = Node(name="GOOSE", description="Container")

            for gocb_name in gocb_names:
                gse_node = Node(name=gocb_name, description="Type=GoCB")
                gocb_ref = f"{full_ln_ref}.{gocb_name}"

                dat_set_val = ""
                try:
                    go_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.GoID", iec61850.IEC61850_FC_GO)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(gse_node, "GoID", go_id)
                except Exception:
                    self._add_detail_leaf(gse_node, "GoID", "")

                try:
                    dat_set_val, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.DatSet", iec61850.IEC61850_FC_GO)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(gse_node, "DatSet", dat_set_val)
                except Exception:
                    self._add_detail_leaf(gse_node, "DatSet", "")

                for attr in ["ConfRev", "MinTime", "MaxTime"]:
                    try:
                        val, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{gocb_ref}.{attr}", iec61850.IEC61850_FC_GO)
                        if err == iec61850.IED_ERROR_OK:
                            self._add_detail_leaf(gse_node, attr, val)
                    except Exception:
                        self._add_detail_leaf(gse_node, attr, "")

                try:
                    app_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{gocb_ref}.AppID", iec61850.IEC61850_FC_GO)
                    if err == iec61850.IED_ERROR_OK:
                        self._add_detail_leaf(gse_node, "AppID", app_id)
                except Exception:
                    self._add_detail_leaf(gse_node, "AppID", "")

                dataset_ref = self._normalize_dataset_ref(full_ln_ref, dat_set_val)
                self._add_dataset_entries_online(dataset_ref, gse_node)

                goose_root.children.append(gse_node)

            ln_node.children.append(goose_root)
            try:
                iec61850.LinkedList_destroy(gocb_list)
            except Exception:
                pass
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
                                    # Show full date + time in UTC with millisecond precision
                                    try:
                                        signal.value = ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UTC'
                                    except Exception:
                                        signal.value = str(ts)
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
            logger.debug(f"Read failed for {signal.address}: {e}")
            signal.quality = SignalQuality.INVALID
            
        return signal
            
        return signal

    def send_command(self, signal: Signal, value: Any, params: dict = None) -> bool:
        """
        High-level command sender that automatically handles SBO workflow.
        Replicates iedexplorer's DoSendCommandClick logic with detailed logging.
        
        For SBO models: SELECT -> wait -> OPERATE
        For Direct models: OPERATE only
        """
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ SEND_COMMAND {signal.address} = {value}")
            self.event_logger.info("IEC61850", f"Starting command execution for {signal.address}")

        if not self.connected or not self.connection:
            if self.event_logger:
                self.event_logger.error("IEC61850", "SEND_COMMAND FAILED: Not connected")
            return False

        try:
            # Initialize control context if needed
            object_ref = self._get_control_object_reference(signal.address)
            ctx = self.controls.get(object_ref)
            if not ctx:
                ctx = self.init_control_context(signal.address)

            if not ctx:
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"SEND_COMMAND FAILED: Control initialization failed for {signal.address}")
                return False

            # Check if SBO is required
            if ctx.ctl_model.is_sbo:
                # Check if SBO objects are actually available
                sbo_available = False
                try:
                    # Try to read the SBO reference to see if it exists
                    test_val, test_err = iec61850.IedConnection_readBooleanValue(
                        self.connection, ctx.sbo_reference, iec61850.IEC61850_FC_CO
                    )
                    if test_err == iec61850.IED_ERROR_OK:
                        sbo_available = True
                        iec61850.MmsValue_delete(test_val) if test_val else None
                except:
                    pass
                
                if not sbo_available:
                    if self.event_logger:
                        self.event_logger.warning("IEC61850", f"SBO objects not available despite ctlModel={ctx.ctl_model.name}. Falling back to direct control.")
                    # Fall back to direct operate
                    return self.operate(signal, value=value, params=params)
                
                # SBO workflow: SELECT -> wait -> OPERATE
                if self.event_logger:
                    self.event_logger.info("IEC61850", f"SBO Mode detected ({ctx.ctl_model.name}). Starting SBO sequence...")
                    self.event_logger.info("IEC61850", f"Control Model: {ctx.ctl_model.name}, SBO Reference: {ctx.sbo_reference}")

                # Find SBO and Oper addresses
                sbo_address = ctx.sbo_reference + ".ctlVal"
                oper_address = object_ref + ".Oper.ctlVal"

                # Create dummy signals for SBO and Oper
                from src.models.device_models import Signal as DummySignal
                sbo_signal = DummySignal(name="ctlVal", address=sbo_address)
                oper_signal = DummySignal(name="ctlVal", address=oper_address)

                # Step 1: SELECT
                if self.event_logger:
                    self.event_logger.transaction("IEC61850", f"  → SELECT {sbo_address}")
                    self.event_logger.info("IEC61850", f"  Executing SELECT with value={value}, current ctlNum={ctx.ctl_num}")

                select_success = self.select(sbo_signal, value=value, params=params)
                if not select_success:
                    if self.event_logger:
                        self.event_logger.error("IEC61850", "  ← SELECT FAILED - Aborting SBO sequence")
                    return False

                if self.event_logger:
                    self.event_logger.transaction("IEC61850", "  ← SELECT SUCCESS")
                    self.event_logger.info("IEC61850", f"  SELECT completed. State: {ctx.state.name}")

                # Step 2: Wait for SBO timeout (default 100ms like iedexplorer)
                sbo_timeout = params.get('sbo_timeout', 100) if params else 100
                if self.event_logger:
                    self.event_logger.info("IEC61850", f"  Waiting {sbo_timeout}ms for SBO timeout...")

                time.sleep(sbo_timeout / 1000.0)

                # Step 3: OPERATE
                if self.event_logger:
                    self.event_logger.transaction("IEC61850", f"  → OPERATE {oper_address}")
                    self.event_logger.info("IEC61850", f"  Executing OPERATE with value={value}, incremented ctlNum={ctx.ctl_num + 1}")

                operate_success = self.operate(oper_signal, value=value, params=params)
                if not operate_success:
                    if self.event_logger:
                        self.event_logger.error("IEC61850", "  ← OPERATE FAILED - SBO sequence incomplete")
                    return False

                if self.event_logger:
                    self.event_logger.transaction("IEC61850", "  ← OPERATE SUCCESS")
                    self.event_logger.transaction("IEC61850", "← SBO SEQUENCE COMPLETE")
                    self.event_logger.info("IEC61850", f"SBO sequence finished successfully. Final ctlNum={ctx.ctl_num}")

                return True

            else:
                # Direct control: OPERATE only
                if self.event_logger:
                    self.event_logger.info("IEC61850", f"Direct Control Mode ({ctx.ctl_model.name}). Sending OPERATE...")

                return self.operate(signal, value=value, params=params)

        except Exception as e:
            logger.error(f"Send command failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"SEND_COMMAND EXCEPTION: {e}")
            return False

    def select(self, signal: Signal, value: Any = None, params: dict = None) -> bool:
        """Perform SELECT phase (SBO) using ControlObjectClient API."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ SELECT {signal.address} = {value}")
            self.event_logger.info("IEC61850", f"Starting SBO SELECT phase for {signal.address}")

        if not self.connected or not self.connection:
            if self.event_logger:
                self.event_logger.error("IEC61850", "SELECT FAILED: Not connected")
            return False

        try:
            object_ref = self._get_control_object_reference(signal.address)
            if not object_ref:
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"SELECT FAILED: Invalid control reference from {signal.address}")
                return False

            if self.event_logger:
                self.event_logger.debug("IEC61850", f"Control object reference: {object_ref}")

            # Try to create ControlObjectClient
            # NOTE: This does synchronous network reads to discover control model!
            with self._lock:
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"Creating ControlObjectClient for {object_ref}...")
                
                control_client = iec61850.ControlObjectClient_create(object_ref, self.connection)
                
                if not control_client:
                    if self.event_logger:
                        self.event_logger.error("IEC61850", f"SELECT FAILED: ControlObjectClient_create returned NULL for {object_ref}")
                        self.event_logger.warning("IEC61850", "This usually means:")
                        self.event_logger.warning("IEC61850", "  1. Object reference is incorrect or doesn't exist")
                        self.event_logger.warning("IEC61850", "  2. IED timed out during control model discovery")
                        self.event_logger.warning("IEC61850", "  3. Control object is not properly configured in IED")
                        self.event_logger.warning("IEC61850", f"  Trying fallback: manual SBO write to {object_ref}.SBO")
                    
                    # FALLBACK: Try manual SBO write (old method) for IEDs that don't work with ControlObjectClient
                    return self._fallback_select(signal, value, object_ref)
                
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"✓ ControlObjectClient created successfully")
                
                try:
                    # Get control model
                    ctl_model_int = iec61850.ControlObjectClient_getControlModel(control_client)
                    if self.event_logger:
                        self.event_logger.info("IEC61850", f"Control model: {ctl_model_int} (0=STATUS_ONLY, 1=DIRECT_NORMAL, 2=SBO_NORMAL, 3=DIRECT_ENHANCED, 4=SBO_ENHANCED)")
                    
                    # Check if it's SBO model
                    if ctl_model_int == 0:  # STATUS_ONLY
                        if self.event_logger:
                            self.event_logger.error("IEC61850", f"SELECT FAILED: Object has ctlModel=StatusOnly (0)")
                        return False
                    
                    if ctl_model_int not in [2, 4]:  # SBO_NORMAL=2, SBO_ENHANCED=4
                        if self.event_logger:
                            self.event_logger.info("IEC61850", f"Object has ctlModel={ctl_model_int}. Skipping SELECT (Direct Control).")
                        return True
                    
                    if self.event_logger:
                        self.event_logger.info("IEC61850", f"Issuing SELECT (ctlModel={ctl_model_int})")
                    
                    # For SBO_ENHANCED (4), use selectWithValue; for SBO_NORMAL (2), use select
                    success = False
                    if ctl_model_int == 4 and value is not None:  # SBO_ENHANCED
                        # Create MmsValue for the value
                        mms_val = self._create_mms_value(value, signal)
                        if mms_val:
                            try:
                                if self.event_logger:
                                    self.event_logger.debug("IEC61850", "Calling ControlObjectClient_selectWithValue...")
                                success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_val)
                            finally:
                                iec61850.MmsValue_delete(mms_val)
                        else:
                            if self.event_logger:
                                self.event_logger.error("IEC61850", "SELECT FAILED: Could not create MmsValue")
                    else:  # SBO_NORMAL
                        if self.event_logger:
                            self.event_logger.debug("IEC61850", "Calling ControlObjectClient_select...")
                        success = iec61850.ControlObjectClient_select(control_client)
                    
                    if success:
                        if self.event_logger:
                            self.event_logger.transaction("IEC61850", "← SELECT SUCCESS")
                            self.event_logger.info("IEC61850", f"SELECT completed successfully")
                        
                        # Update context if it exists
                        ctx = self.controls.get(object_ref)
                        if ctx:
                            ctx.state = ControlState.SELECTED
                            ctx.last_select_time = datetime.now()
                        return True
                    else:
                        last_error = iec61850.ControlObjectClient_getLastError(control_client)
                        if self.event_logger:
                            self.event_logger.error("IEC61850", f"← SELECT FAILED: IED error code {last_error}")
                            self.event_logger.warning("IEC61850", f"Trying fallback method...")
                        
                        # FALLBACK: Try manual SBO write
                        return self._fallback_select(signal, value, object_ref)
                        
                finally:
                    # Always destroy the control client
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", "Destroying ControlObjectClient")
                    iec61850.ControlObjectClient_destroy(control_client)

        except Exception as e:
            logger.error(f"Select failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"SELECT EXCEPTION: {e}")
                self.event_logger.warning("IEC61850", f"Trying fallback method...")
            
            # FALLBACK: Try manual SBO write on exception
            object_ref = self._get_control_object_reference(signal.address)
            if object_ref:
                return self._fallback_select(signal, value, object_ref)
            return False

    def operate(self, signal: Signal, value: Any, params: dict = None) -> bool:
        """Perform OPERATE phase using ControlObjectClient API."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ OPERATE {signal.address} = {value}")
            self.event_logger.info("IEC61850", f"Starting OPERATE phase for {signal.address}")

        if not self.connected or not self.connection:
            if self.event_logger:
                self.event_logger.error("IEC61850", "OPERATE FAILED: Not connected")
            return False

        try:
            object_ref = self._get_control_object_reference(signal.address)
            if not object_ref:
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"OPERATE FAILED: Invalid control reference from {signal.address}")
                return False

            if self.event_logger:
                self.event_logger.debug("IEC61850", f"Control object reference: {object_ref}")

            # Try to create ControlObjectClient
            # NOTE: This does synchronous network reads to discover control model!
            with self._lock:
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"Creating ControlObjectClient for {object_ref}...")
                
                control_client = iec61850.ControlObjectClient_create(object_ref, self.connection)
                
                if not control_client:
                    if self.event_logger:
                        self.event_logger.error("IEC61850", f"OPERATE FAILED: ControlObjectClient_create returned NULL for {object_ref}")
                        self.event_logger.warning("IEC61850", "This usually means:")
                        self.event_logger.warning("IEC61850", "  1. Object reference is incorrect or doesn't exist")
                        self.event_logger.warning("IEC61850", "  2. IED timed out during control model discovery")
                        self.event_logger.warning("IEC61850", "  3. Control object is not properly configured in IED")
                        self.event_logger.warning("IEC61850", f"  Trying fallback: manual write to {object_ref}.Oper")
                    
                    # FALLBACK: Try manual Oper write (old method) for IEDs that don't work with ControlObjectClient
                    return self._fallback_operate(signal, value, object_ref)
                
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"✓ ControlObjectClient created successfully")
                
                try:
                    # Get control model
                    ctl_model_int = iec61850.ControlObjectClient_getControlModel(control_client)
                    if self.event_logger:
                        self.event_logger.info("IEC61850", f"Control model: {ctl_model_int} (0=STATUS_ONLY, 1=DIRECT_NORMAL, 2=SBO_NORMAL, 3=DIRECT_ENHANCED, 4=SBO_ENHANCED)")
                    
                    if ctl_model_int == 0:  # STATUS_ONLY
                        if self.event_logger:
                            self.event_logger.error("IEC61850", f"OPERATE FAILED: Object has ctlModel=StatusOnly (0)")
                        return False
                    
                    # Set originator information
                    ctx = self.controls.get(object_ref)
                    if ctx:
                        origin_cat = ctx.originator_cat if ctx.originator_cat > 0 else 3  # 3 = Remote
                        origin_id = ctx.originator_id if ctx.originator_id else "SCADA"
                    else:
                        origin_cat = 3  # Remote
                        origin_id = "SCADA"
                    
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"Setting originator: {origin_id}, category: {origin_cat}")
                    iec61850.ControlObjectClient_setOriginator(control_client, origin_id, origin_cat)
                    
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"Issuing OPERATE (ctlModel={ctl_model_int})")
                    
                    # Create MmsValue for the control value
                    mms_val = self._create_mms_value(value, signal)
                    if not mms_val:
                        if self.event_logger:
                            self.event_logger.error("IEC61850", "OPERATE FAILED: Could not create MmsValue")
                        return False
                    
                    try:
                        if self.event_logger:
                            self.event_logger.debug("IEC61850", f"Calling ControlObjectClient_operate with value={value}, operTime=0")
                        
                        # Call operate with operTime=0 (operate now)
                        success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
                        
                        if success:
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", "← OPERATE SUCCESS")
                                self.event_logger.info("IEC61850", f"OPERATE completed successfully")
                            
                            # Update context if it exists
                            if ctx:
                                ctx.state = ControlState.OPERATED
                                ctx.last_operate_time = datetime.now()
                            return True
                        else:
                            last_error = iec61850.ControlObjectClient_getLastError(control_client)
                            if self.event_logger:
                                self.event_logger.error("IEC61850", f"← OPERATE FAILED: IED error code {last_error}")
                                self.event_logger.warning("IEC61850", f"Trying fallback method...")
                            
                            # FALLBACK: Try manual Oper write
                            return self._fallback_operate(signal, value, object_ref)
                    finally:
                        iec61850.MmsValue_delete(mms_val)
                        
                finally:
                    # Always destroy the control client
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", "Destroying ControlObjectClient")
                    iec61850.ControlObjectClient_destroy(control_client)

        except Exception as e:
            logger.error(f"Operate failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"OPERATE EXCEPTION: {e}")
                self.event_logger.warning("IEC61850", f"Trying fallback method...")
            
            # FALLBACK: Try manual Oper write on exception
            object_ref = self._get_control_object_reference(signal.address)
            if object_ref:
                return self._fallback_operate(signal, value, object_ref)
            return False

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
            try:
                 # Try reading .ctlModel with FC=CF
                 val, err = iec61850.IedConnection_readInt32Value(
                     self.connection, f"{object_ref}.ctlModel", iec61850.IEC61850_FC_CF
                 )
                 if err == iec61850.IED_ERROR_OK:
                     ctl_model_val = val
                     if self.event_logger:
                         self.event_logger.debug("IEC61850", f"  Read ctlModel: {ctl_model_val}")
                 
                 # Action 3: Read current ctlNum for echoing
                 val_num, err_num = iec61850.IedConnection_readInt32Value(
                     self.connection, f"{object_ref}.ctlNum", iec61850.IEC61850_FC_ST
                 )
                 if err_num == iec61850.IED_ERROR_OK:
                     ctl_num_val = val_num
                     if self.event_logger:
                         self.event_logger.debug("IEC61850", f"  Read Current ctlNum: {ctl_num_val}")
            except Exception as e:
                 if self.event_logger:
                     self.event_logger.warning("IEC61850", f"  Exception reading control attributes: {e}")
            
            # 1.3 Discover Oper/SBO
            try:
                # Browse the DO to find Oper/SBO
                ret = iec61850.IedConnection_getDataDirectory(self.connection, object_ref)
                children = ret[0] if isinstance(ret, (list, tuple)) else ret
                if children:
                    names = self._extract_string_list(children)
                    iec61850.LinkedList_destroy(children)
                    
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
            # Cancel is usually written to .Cancel attribute or using ControlClient
            # We'll use a simple write to .Cancel if it exists
            with self._lock:
                struct = iec61850.MmsValue_newStructure(1)
                iec61850.MmsValue_setElement(struct, 0, iec61850.MmsValue_newBoolean(True))
                err = iec61850.IedConnection_writeObject(self.connection, f"{object_ref}.Cancel", iec61850.IEC61850_FC_CO, struct)
                iec61850.MmsValue_delete(struct)
            return err == iec61850.IED_ERROR_OK
        except:
            return False

    def _get_control_object_reference(self, address: str) -> str:
        """Extract the Control Object Reference (DO path)."""
        if not address: return None
        suffixes = [".Oper.ctlVal", ".Oper", ".SBO.ctlVal", ".SBO", ".SBOw.ctlVal", ".SBOw", 
                    ".Cancel.ctlVal", ".Cancel", ".ctlVal", ".stVal", ".q", ".t"]
        for suffix in suffixes:
            if address.endswith(suffix):
                return address[:-len(suffix)]
        return address

    def _build_operate_struct(self, value, ctx: ControlObjectRuntime, is_select: bool = False):
        """Builds the complex Operate structure manually (7 elements) with detailed logging."""
        struct = None
        try:
             # Standard IEC 61850 Operate structure baseline enforcement
             struct = iec61850.MmsValue_newStructure(7)
             if not struct: 
                 logger.error("Failed to allocate MmsValue structure.")
                 return None
             
             now_ms = int(time.time() * 1000)
             
             # Extract Baseline Values
             ctl_val_bool = bool(value)
             test_bool = False # Safe Baseline
             check_val = 0     # Safe Baseline
             cat = ctx.originator_cat if ctx.originator_cat > 0 else 3 # 3 = Remote (Action 2)
             ident = ctx.originator_id if ctx.originator_id and ctx.originator_id != "ScadaScout" else "SCADA"

             # Root Cause Fix #1: Handle ctlNum carefully (Action 3 / Option B)
             # We must ALWAYS fill the structure element to avoid NULL pointer crashes in the native encoder.
             # Echo back the last known ctlNum from the IED.
             ctl_num_to_send = ctx.ctl_num

             if self.event_logger:
                 self.event_logger.debug("IEC61850", f"Constructing {'SELECT' if is_select else 'OPERATE'} Payload (7 elements):")
                 self.event_logger.debug("IEC61850", f"  [0] ctlVal: {ctl_val_bool}")
                 self.event_logger.debug("IEC61850", f"  [1] operTm: {datetime.fromtimestamp(now_ms/1000).isoformat()} (Echoing T)")
                 self.event_logger.debug("IEC61850", f"  [2] origin: cat={cat}, id={ident}")
                 self.event_logger.debug("IEC61850", f"  [3] ctlNum: {ctl_num_to_send} (Echoed form IED)")
                 self.event_logger.debug("IEC61850", f"  [4] T: {datetime.fromtimestamp(now_ms/1000).isoformat()}")
                 self.event_logger.debug("IEC61850", f"  [5] Test: {test_bool}")
                 self.event_logger.debug("IEC61850", f"  [6] Check: {check_val}")

             # 0: ctlVal
             mms_val = self._create_mms_value(ctl_val_bool, None)
             if not mms_val:
                 logger.error(f"Failed to create ctlVal MmsValue for value: {ctl_val_bool}")
                 iec61850.MmsValue_delete(struct)
                 return None
             iec61850.MmsValue_setElement(struct, 0, mms_val)
             
             # 1: operTm (Required to be non-NULL for encoder stability)
             mms_tm = iec61850.MmsValue_newUtcTimeMs(now_ms)
             if mms_tm:
                 iec61850.MmsValue_setElement(struct, 1, mms_tm)
             else:
                 # Fallback to prevent NULL element crash
                 iec61850.MmsValue_setElement(struct, 1, iec61850.MmsValue_newBoolean(False))
             
             # 2: origin [cat, ident]
             origin = iec61850.MmsValue_newStructure(2)
             if origin:
                 iec61850.MmsValue_setElement(origin, 0, iec61850.MmsValue_newInteger(cat))
                 ident_val = iec61850.MmsValue_newVisibleString(ident)
                 if ident_val:
                     iec61850.MmsValue_setElement(origin, 1, ident_val)
                 iec61850.MmsValue_setElement(struct, 2, origin)
             
             # 3: ctlNum (MANDATORY non-NULL)
             iec61850.MmsValue_setElement(struct, 3, iec61850.MmsValue_newInteger(ctl_num_to_send))
             
             # 4: T
             mms_t = iec61850.MmsValue_newUtcTimeMs(now_ms)
             if mms_t:
                 iec61850.MmsValue_setElement(struct, 4, mms_t)
             else:
                 iec61850.MmsValue_setElement(struct, 4, iec61850.MmsValue_newBoolean(False))

             # 5: Test (BOOLEAN)
             iec61850.MmsValue_setElement(struct, 5, iec61850.MmsValue_newBoolean(test_bool))

             # 6: Check (CheckConditions - BitString[2])
             mms_check = iec61850.MmsValue_newBitString(2)
             if mms_check:
                 iec61850.MmsValue_setBitStringBit(mms_check, 0, False)
                 iec61850.MmsValue_setBitStringBit(mms_check, 1, False)
                 iec61850.MmsValue_setElement(struct, 6, mms_check)
             
             return struct
        except Exception as e:
             logger.error(f"Failed to build operate struct: {e}")
             if struct: iec61850.MmsValue_delete(struct)
             return None

    def _create_mms_value(self, value: Any, signal: Signal):
        """Create MmsValue from Python value."""
        try:
            if isinstance(value, bool):
                mms = iec61850.MmsValue_newBoolean(value)
                if not mms:
                    logger.error(f"Failed to create MMS Boolean for value: {value}")
                return mms
            elif isinstance(value, float):
                return iec61850.MmsValue_newFloat(value)
            elif isinstance(value, int):
                return iec61850.MmsValue_newInt32(value)
            elif isinstance(value, str):
                return iec61850.MmsValue_newVisibleString(value)
            return None
        except:
            return None

    def _fallback_select(self, signal: Signal, value: Any, object_ref: str) -> bool:
        """
        Fallback method: Simple write to .SBO or .SBOw attribute.
        Used when ControlObjectClient_create fails (e.g., IED timeout, incompatibility).
        """
        if self.event_logger:
            self.event_logger.info("IEC61850", "Using FALLBACK method: Direct write to SBO attribute")
        
        try:
            # Try SBOw first (enhanced), then SBO (normal)
            for sbo_attr in [f"{object_ref}.SBOw", f"{object_ref}.SBO"]:
                if self.event_logger:
                    self.event_logger.debug("IEC61850", f"Trying write to {sbo_attr}")
                
                # Create simple MmsValue (just the control value, not full structure)
                mms_val = self._create_mms_value(value, signal) if value is not None else iec61850.MmsValue_newBoolean(True)
                
                if not mms_val:
                    continue
                
                try:
                    err = iec61850.IedConnection_writeObject(self.connection, sbo_attr, iec61850.IEC61850_FC_CO, mms_val)
                    iec61850.MmsValue_delete(mms_val)
                    
                    if err == iec61850.IED_ERROR_OK:
                        if self.event_logger:
                            self.event_logger.transaction("IEC61850", "← FALLBACK SELECT SUCCESS")
                            self.event_logger.info("IEC61850", f"Fallback SELECT succeeded with {sbo_attr}")
                        return True
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
        Fallback method: Simple write to .Oper.ctlVal attribute.
        Used when ControlObjectClient_create fails (e.g., IED timeout, incompatibility).
        """
        if self.event_logger:
            self.event_logger.info("IEC61850", "Using FALLBACK method: Direct write to Oper.ctlVal")
        
        try:
            # Try direct write to .Oper.ctlVal
            oper_attr = f"{object_ref}.Oper.ctlVal"
            
            if self.event_logger:
                self.event_logger.debug("IEC61850", f"Writing to {oper_attr}")
            
            mms_val = self._create_mms_value(value, signal)
            if not mms_val:
                if self.event_logger:
                    self.event_logger.error("IEC61850", "Could not create MmsValue for fallback operate")
                return False
            
            try:
                err = iec61850.IedConnection_writeObject(self.connection, oper_attr, iec61850.IEC61850_FC_CO, mms_val)
                iec61850.MmsValue_delete(mms_val)
                
                if err == iec61850.IED_ERROR_OK:
                    if self.event_logger:
                        self.event_logger.transaction("IEC61850", "← FALLBACK OPERATE SUCCESS")
                        self.event_logger.info("IEC61850", f"Fallback OPERATE succeeded with {oper_attr}")
                    return True
                else:
                    if self.event_logger:
                        self.event_logger.error("IEC61850", f"← FALLBACK OPERATE FAILED: IED error {err}")
                    return False
                    
            except Exception as e:
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"Write to {oper_attr} failed: {e}")
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
                err = iec61850.IedConnection_writeObject(self.connection, signal.address, iec61850.IEC61850_FC_CF, mms_value)
                iec61850.MmsValue_delete(mms_value)
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
                server_identity = iec61850.IedConnection_getServerIdentity(self.connection)
                if server_identity:
                    info["server_identity"] = server_identity
                    # Parse vendor, model info from identity string if available
                    # Format varies by vendor
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
                ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            if not ld_list:
                return datasets
            
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
                        
                        # Get datasets for this LN
                        with self._lock:
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
                            
                            try:
                                iec61850.LinkedList_destroy(ds_list)
                            except Exception:
                                pass
                    
                    try:
                        iec61850.LinkedList_destroy(ln_list)
                    except Exception:
                        pass
            
            try:
                iec61850.LinkedList_destroy(ld_list)
            except Exception:
                pass
        
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
                ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = ret[0] if isinstance(ret, (list, tuple)) else ret
            if not ld_list:
                return reports
            
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
                        
                        # Get URCBs
                        try:
                            with self._lock:
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
                                
                                try:
                                    iec61850.LinkedList_destroy(urcb_list)
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.debug(f"Error reading URCBs for {full_ln_ref}: {e}")
                        
                        # Get BRCBs
                        try:
                            with self._lock:
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
                                
                                try:
                                    iec61850.LinkedList_destroy(brcb_list)
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.debug(f"Error reading BRCBs for {full_ln_ref}: {e}")
                    
                    try:
                        iec61850.LinkedList_destroy(ln_list)
                    except Exception:
                        pass
            
            try:
                iec61850.LinkedList_destroy(ld_list)
            except Exception:
                pass
        
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
                    rpt_id, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.RptID", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["rpt_id"] = rpt_id
            except Exception:
                pass
            
            # DatSet
            try:
                with self._lock:
                    dat_set, err = iec61850.IedConnection_readStringValue(self.connection, f"{rcb_ref}.DatSet", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["dataset"] = dat_set
            except Exception:
                pass
            
            # ConfRev
            try:
                with self._lock:
                    conf_rev, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.ConfRev", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["conf_rev"] = conf_rev
            except Exception:
                pass
            
            # BufTm
            try:
                with self._lock:
                    buf_tm, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.BufTm", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["buf_time"] = buf_tm
            except Exception:
                pass
            
            # IntgPd
            try:
                with self._lock:
                    intg_pd, err = iec61850.IedConnection_readUnsigned32Value(self.connection, f"{rcb_ref}.IntgPd", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["intg_pd"] = intg_pd
            except Exception:
                pass
            
            # TrgOps (bit string)
            try:
                with self._lock:
                    trg_ops, err = iec61850.IedConnection_readBitStringValue(self.connection, f"{rcb_ref}.TrgOps", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["trg_ops"] = str(trg_ops)
            except Exception:
                pass
            
            # OptFlds (bit string)
            try:
                with self._lock:
                    opt_flds, err = iec61850.IedConnection_readBitStringValue(self.connection, f"{rcb_ref}.OptFlds", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["opt_flds"] = str(opt_flds)
            except Exception:
                pass
            
            # RptEna (enabled)
            try:
                with self._lock:
                    rpt_ena, err = iec61850.IedConnection_readBooleanValue(self.connection, f"{rcb_ref}.RptEna", fc)
                if err == iec61850.IED_ERROR_OK:
                    rcb_info["enabled"] = rpt_ena
            except Exception:
                pass
            
            # GI (General Interrogation)
            try:
                with self._lock:
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