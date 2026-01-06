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
            return False

    def _connect_mock(self):
        time.sleep(0.5)
        self.connected = True
        logger.info("MOCK: Connected.")
        return True

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
            root = parser.get_structure(ied_name=None)
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
                                        
                                        # For full discovery, we'd need to browse Data Attributes here
                                        # For now, create signals for common attributes (Standard IEC 61850 attributes)
                                        # We use full_ln_ref which includes LD name: "LDName/LNName"
                                        
                                        # Common attributes to try
                                        common_das = ["stVal", "q", "t", "mag.f", "cVal.mag.f", "Oper.ctlVal"]
                                        
                                        for da_name in common_das:
                                            # The path should be the FULL Object Reference: LD/LN.DO.DA
                                            full_da_path = f"{full_ln_ref}.{do_name}.{da_name}"
                                            
                                            sig = Signal(
                                                name=da_name,
                                                address=full_da_path,
                                                signal_type=None,
                                                access="RW"
                                            )
                                            # Add to DO node signals list
                                            do_node.signals.append(sig)
                                        
                                        # Log if signals added
                                        # self.event_logger.debug("Debug", f"Added {len(do_node.signals)} signals to {do_name}")
                                            
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

    def read_signal(self, signal: Signal) -> Signal:
        """Read a single signal value from the IED."""
        if self.event_logger:
            self.event_logger.transaction("IEC61850", f"→ READ {signal.address}")
            
        if not self.connected:
            signal.quality = SignalQuality.NOT_CONNECTED
            if self.event_logger:
                self.event_logger.warning("IEC61850", f"← NOT CONNECTED")
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
            
            # If address doesn't contain '/', it's missing LD - we need to find it
            if '/' not in address:
                # This is a problem - we need the full reference
                # For now, log and fail
                if self.event_logger:
                    self.event_logger.error("IEC61850", f"← INVALID ADDRESS: {address} (missing LD/)")
                signal.quality = SignalQuality.INVALID
                return signal
            
            # Common functional constraints to try
            fcs_to_try = [
                ("ST", iec61850.IEC61850_FC_ST),  # Status
                ("MX", iec61850.IEC61850_FC_MX),  # Measured value
                ("CO", iec61850.IEC61850_FC_CO),  # Control
                ("SP", iec61850.IEC61850_FC_SP),  # Set point
                ("CF", iec61850.IEC61850_FC_CF),  # Configuration
            ]
            
            value_read = False
            last_error = None
            
            for fc_name, fc in fcs_to_try:
                try:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"  Try FC={fc_name} for {address}")
                    
                    # Try reading as float first (most common for analog)
                    try:
                        float_val = iec61850.IedConnection_readFloatValue(
                            self.connection,
                            address,
                            fc
                        )
                        
                        # If we got a valid float (not None), use it
                        if float_val is not None:
                            signal.value = float_val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = {float_val}")
                            break
                    except Exception as e:
                        last_error = str(e)
                        pass
                    
                    # Try reading as boolean
                    try:
                        bool_val = iec61850.IedConnection_readBooleanValue(
                            self.connection,
                            address,
                            fc
                        )
                        
                        if bool_val is not None:
                            signal.value = bool_val
                            signal.signal_type = SignalType.BINARY
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = {bool_val}")
                            break
                    except Exception as e:
                        last_error = str(e)
                        pass
                    
                    # Try reading as int32
                    try:
                        int_val = iec61850.IedConnection_readInt32Value(
                            self.connection,
                            address,
                            fc
                        )
                        
                        if int_val is not None:
                            signal.value = int_val
                            signal.signal_type = SignalType.ANALOG
                            signal.quality = SignalQuality.GOOD
                            signal.timestamp = datetime.now()
                            value_read = True
                            
                            if self.event_logger:
                                self.event_logger.transaction("IEC61850", f"← OK (FC={fc_name}): {address} = {int_val}")
                            break
                    except Exception as e:
                        last_error = str(e)
                        pass
                        
                except Exception as e:
                    if self.event_logger:
                        self.event_logger.debug("IEC61850", f"  FC={fc_name} failed: {e}")
                    last_error = str(e)
                    continue
            
            if not value_read:
                signal.quality = SignalQuality.INVALID
                signal.value = None
                if self.event_logger:
                    error_msg = f"Could not read {address} with any FC"
                    if last_error:
                        error_msg += f" (Last error: {last_error})"
                    self.event_logger.error("IEC61850", f"← FAILED: {error_msg}")
            
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
