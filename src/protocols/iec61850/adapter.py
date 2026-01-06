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

from datetime import datetime
import logging
import time
from typing import Dict, Any, Optional

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import Signal, SignalType, SignalQuality, Node, DeviceConfig
from src.core.scd_parser import SCDParser

# Try to import real library, fallback to mock if missing (dev mode)
try:
    from pyiec61850 import iec61850
    HAS_LIBIEC61850 = True
except ImportError:
    HAS_LIBIEC61850 = False

logger = logging.getLogger(__name__)

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
        if not HAS_LIBIEC61850:
            if self.event_logger:
                self.event_logger.warning("Connection", "Step 3/4: Using MOCK mode (libiec61850 not available)")
            self.connected = True
            return True
        
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
                except:
                    pass
                self.connection = None
            return False
    
    def _ping_device(self) -> bool:
        """Ping the device to check network reachability."""
        import subprocess
        import platform
        
        try:
            # Determine ping command based on OS
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            # Send 2 pings with 1 second timeout
            command = ['ping', param, '2', '-W', '1', self.config.ip_address]
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3
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

    def _discover_online(self) -> Node:
        """Browse IED structure directly from the connected device."""
        if not HAS_LIBIEC61850 or not self.connection:
             if self.event_logger:
                 self.event_logger.warning("Discovery", "Cannot perform online discovery - not connected or library missing")
             return Node(name=self.config.name, description="Not Connected")

        root = Node(name=self.config.name, description="IEC 61850 IED (Online)")
        
        if self.event_logger:
            self.event_logger.info("Discovery", "Querying IED server directory...")
        
        try:
            # Get the server directory (Logical Devices)
            # Use getLogicalDeviceList which is specific for LD names
            # getLogicalDeviceList returns [LinkedList, ErrorCode] in this binding
            ret = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            ld_list = None
            if isinstance(ret, (list, tuple)):
                if len(ret) > 0:
                    ld_list = ret[0]
            else:
                ld_list = ret
            
            if not ld_list:
                if self.event_logger:
                    self.event_logger.warning("Discovery", "No Logical Devices found (getLogicalDeviceList returned empty)")
                return root
            
            # Try to convert LinkedList to Python list
            ld_names = self._extract_string_list(ld_list)
            
            if self.event_logger:
                self.event_logger.info("Discovery", f"Found {len(ld_names)} Logical Device(s): {', '.join(ld_names)}")
            
            # Update root name from first LD (Heuristic)
            # MMS exposes Logical Devices (Domains).
            # We try to derive a clean IED name.
            if ld_names:
                # 1. Try to find common prefix if multiple LDs
                import os
                if len(ld_names) > 1:
                    derived_name = os.path.commonprefix(ld_names)
                    if derived_name.endswith('_') or derived_name.endswith('/'):
                        derived_name = derived_name[:-1]
                    if not derived_name:
                         # Fallback to first
                         derived_name = ld_names[0]
                else:
                    derived_name = ld_names[0]

                # 2. Cleanup suffix like "LD0", "LD1", "/LD0"
                # Many IEDs use naming "MyIEDLD0" or "MyIED_LD0"
                import re
                # Remove trailing "LD" + digits
                derived_name = re.sub(r'[_\W]?(LD|CTRL|PROT)\d*$', '', derived_name, flags=re.IGNORECASE)
                # Remove trailing slash part if any
                if '/' in derived_name:
                    derived_name = derived_name.split('/')[0]
                
                # If we stripped everything (empty), revert to raw name
                if not derived_name:
                    derived_name = ld_names[0]
                    
                root.name = derived_name
                if self.event_logger:
                    self.event_logger.info("Discovery", f"Derived IED name '{derived_name}' from Logical Device(s) {ld_names}")
            
            # Browse each Logical Device
            for ld_name in ld_names:
                if self.event_logger:
                    self.event_logger.debug("Discovery", f"Browsing Logical Device: {ld_name}")
                
                ld_node = Node(name=ld_name, description="Logical Device")
                root.children.append(ld_node)
                
                # Get Logical Nodes for this LD
                try:
                    if self.event_logger:
                        self.event_logger.transaction("IEC61850", f"→ getLogicalDeviceDirectory({ld_name})")
                    
                    ret_ln = iec61850.IedConnection_getLogicalDeviceDirectory(self.connection, ld_name)
                    
                    ln_list = None
                    if isinstance(ret_ln, (list, tuple)):
                         ln_list = ret_ln[0]
                    else:
                         ln_list = ret_ln
                    
                    if ln_list:
                        ln_names = self._extract_string_list(ln_list)
                        
                        if self.event_logger:
                            self.event_logger.debug("Discovery", f"  Found {len(ln_names)} Logical Node(s) in {ld_name}")
                        
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
                                
                                do_list = None
                                if isinstance(ret_do, (list, tuple)):
                                    self.event_logger.info("Debug", f"DO List Raw: {ret_do}")
                                    do_list = ret_do[0]
                                else:
                                    self.event_logger.info("Debug", f"DO List Raw: {ret_do}")
                                    do_list = ret_do
                                
                                if do_list:
                                    do_names = self._extract_string_list(do_list)
                                    self.event_logger.info("Debug", f"Extracted DOs: {do_names}")
                                    
                                    for do_name in do_names:
                                        do_node = Node(name=do_name, description="Data Object")
                                        do_node = Node(name=do_name, description="Data Object")
                                        ln_node.children.append(do_node)
                                        
                                        # 1. Browse Data Attributes by Functional Constraint
                                        full_do_ref = f"{full_ln_ref}.{do_name}"
                                        
                                        fcs = [
                                            (iec61850.IEC61850_FC_ST, "ST", "RO"),
                                            (iec61850.IEC61850_FC_MX, "MX", "RO"),
                                            (iec61850.IEC61850_FC_CO, "CO", "RW"),
                                            (iec61850.IEC61850_FC_SP, "SP", "RW"),
                                            (iec61850.IEC61850_FC_CF, "CF", "RW"),
                                            (iec61850.IEC61850_FC_DC, "DC", "RO"),
                                        ]
                                        
                                        for fc_val, fc_name, access in fcs:
                                            try:
                                                # Use get Data Directory filtered by FC
                                                ret_da = iec61850.IedConnection_getDataDirectoryByFC(
                                                    self.connection, full_do_ref, fc_val
                                                )
                                                da_list = ret_da[0] if isinstance(ret_da, (list, tuple)) else ret_da
                                                
                                                if da_list:
                                                    da_names = self._extract_string_list(da_list)
                                                    for da_name in da_names:
                                                        # Special handling for nested structures like mag, cVal (usually in MX or ST)
                                                        if da_name in ["mag", "cVal", "Oper", "SBOw", "Cancel"]:
                                                            sub_ref = f"{full_do_ref}.{da_name}"
                                                            # Browsing sub-directory might also need FC? 
                                                            # Usually yes, but getDataDirectory might be enough for sub-elements
                                                            ret_sub = iec61850.IedConnection_getDataDirectory(self.connection, sub_ref)
                                                            sub_list = ret_sub[0] if isinstance(ret_sub, (list, tuple)) else ret_sub
                                                            if sub_list:
                                                                sub_das = self._extract_string_list(sub_list)
                                                                for sub_da in sub_das:
                                                                    leaf_name = f"{da_name}.{sub_da}"
                                                                    leaf_path = f"{full_do_ref}.{leaf_name}"
                                                                    # Only ctlVal is controllable
                                                                    sig_access = "RW" if "ctlVal" in leaf_name else "RO"
                                                                    
                                                                    # Set Signal Type
                                                                    sig_type = None
                                                                    if leaf_name.endswith(".t") or leaf_name.endswith(".T"):
                                                                        sig_type = SignalType.TIMESTAMP
                                                                    
                                                                    sig = Signal(
                                                                        name=leaf_name,
                                                                        address=leaf_path,
                                                                        signal_type=sig_type,
                                                                        access=sig_access,
                                                                        description=f"FC={fc_name} (Nested)"
                                                                    )
                                                                    do_node.signals.append(sig)
                                                                iec61850.LinkedList_destroy(sub_list)
                                                        else:
                                                            full_da_path = f"{full_do_ref}.{da_name}"
                                                            sig_access = "RW" if "ctlVal" in da_name else "RO"
                                                            
                                                            sig_type = None
                                                            if da_name.endswith(".t") or da_name.endswith(".T"):
                                                                sig_type = SignalType.TIMESTAMP
                                                                
                                                            sig = Signal(
                                                                name=da_name,
                                                                address=full_da_path,
                                                                signal_type=sig_type,
                                                                access=sig_access,
                                                                description=f"FC={fc_name}"
                                                            )
                                                            do_node.signals.append(sig)
                                                    
                                                    iec61850.LinkedList_destroy(da_list)
                                                    
                                            except Exception as e:
                                                # If ByFC fails, we just continue to next FC
                                                continue
                                                
                                        # Fallback if NO signals found by FC and we haven't added any
                                        if not do_node.signals:
                                            if self.event_logger:
                                                self.event_logger.debug("Discovery", f"    FC browsing yielded no results for {full_do_ref}, using generic discovery")
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
                                            
                            except Exception as e:
                                if self.event_logger:
                                    self.event_logger.debug("Discovery", f"  Could not browse DOs for {full_ln_ref}: {e}")
                                
                    try:
                        iec61850.LinkedList_destroy(ln_list)
                    except:
                        pass
                        
                except Exception as e:
                    if self.event_logger:
                        self.event_logger.warning("Discovery", f"Failed to browse LD {ld_name}: {e}")
            
            try:
                iec61850.LinkedList_destroy(ld_list)
            except:
                pass
            
            if self.event_logger:
                self.event_logger.info("Discovery", f"✓ Online discovery complete - found {len(root.children)} Logical Device(s)")
            
            return root
            
        except Exception as e:
            if self.event_logger:
                self.event_logger.error("Discovery", f"Online discovery failed: {e}")
            logger.error(f"Online discovery failed: {e}")
            import traceback
            traceback.print_exc()
            root.children.append(Node(name="Error", description=str(e)))
            return root
    
    def _extract_string_list(self, linked_list) -> list:
        """
        Extract strings from a pyiec61850 LinkedList.
        """
        result = []
        if not linked_list:
            return result
        
        # Debug logging manually since self.event_logger might not be passed here easily? 
        # Actually this is a method of the class, so we can use self.event_logger if available.
        # But let's use print for safety if logger is filtered.
        # print(f"DEBUG: _extract_string_list called with type {type(linked_list)}")
        
        import ctypes
            
        try:
            current = linked_list
            max_items = 1000
            count = 0
            
            while current and count < max_items:
                # 1. Try to get data pointer
                data = iec61850.LinkedList_getData(current)
                
                # print(f"DEBUG: Item {count}: data type {type(data)}")
                
                if data:
                    # Case A: It's already a string (rare with these bindings but possible)
                    if isinstance(data, str):
                        result.append(data)
                    else:
                        # Case B: It's a SWIG Object / Pointer
                        try:
                            # Try to get address. SWIG objects usually implement __int__ or have .this
                            addr = 0
                            if hasattr(data, "this"):
                                addr = int(data.this)
                            elif hasattr(data, "__int__"):
                                addr = int(data)
                            
                            if addr:
                                c_str = ctypes.cast(addr, ctypes.c_char_p)
                                if c_str.value:
                                    val = c_str.value.decode('utf-8', errors='ignore')
                                    result.append(val)
                                    # print(f"DEBUG: Extracted string: {val}")
                            # Fallback: sometimes str(data) works for simple types
                            else:
                                s = str(data)
                                if "Swig" not in s and "ptr" not in s and "0x" not in s:
                                    result.append(s)
                                    
                        except Exception as e:
                            # logger.debug(f"Failed to cast data: {e}")
                            pass
                
                # Move to next
                current = iec61850.LinkedList_getNext(current)
                count += 1
                
        except Exception as e:
            logger.warning(f"LinkedList iteration failed: {e}")
            
        return result

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
        except:
             pass
        return None

    def read_signal(self, signal: Signal) -> Signal:
        """Read a single signal value from the IED."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ READ {signal.address}")
            
        if not self.connected:
            signal.quality = SignalQuality.NOT_CONNECTED
            if self.event_logger:
                self.event_logger.warning("IEC61850", f"← NOT CONNECTED (Internal State)")
            return signal

        if HAS_LIBIEC61850 and self.connection:
            # Check actual connection state
            state = iec61850.IedConnection_getState(self.connection)
            if state != iec61850.IED_STATE_CONNECTED:
                self.connected = False
                logger.warning(f"Connection lost detected during read for {self.config.ip_address} (State: {state})")
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← CONNECTION LOST (State: {state})")
                signal.quality = SignalQuality.NOT_CONNECTED
                return signal

        if not HAS_LIBIEC61850:
            # Mock update for testing
            import random
            if signal.signal_type == SignalType.ANALOG:
                signal.value = round(random.uniform(220.0, 240.0), 2)
            elif signal.signal_type == SignalType.BINARY:
                signal.value = random.choice([True, False])
            signal.timestamp = datetime.now()
            signal.quality = SignalQuality.GOOD
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
            
            return signal
            
        except Exception as e:
            logger.error(f"Exception reading signal {signal.address}: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850", f"← EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            signal.quality = SignalQuality.INVALID
            signal.value = None
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

    def select(self, signal: Signal) -> bool:
        # Placeholder for real select
        return True

    def operate(self, signal: Signal, value: Any) -> bool:
        # Placeholder for real operate
        return True

    def cancel(self, signal: Signal) -> bool:
        return True
    
    def _detect_vendor_pre_connect(self):
        pass # Keep cleanup
