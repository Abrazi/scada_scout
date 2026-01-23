import ctypes
import logging
import os
import tempfile
import xml.etree.ElementTree as ET
from typing import Optional

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Node, Signal, SignalQuality
from src.core.scd_parser import SCDParser
from src.protocols.iec61850 import lib61850 as lib

logger = logging.getLogger(__name__)


class IEC61850ServerAdapter(BaseProtocol):
    """
    IEC 61850 server simulator backed by libiec61850.
    Loads a model from SCD and starts an MMS server on the configured IP/port.
    """

    def __init__(self, config: DeviceConfig, event_logger=None):
        super().__init__(config)
        self.server = None
        self.model = None
        self.connected = False
        self.event_logger = event_logger
        self._filtered_scd_path: Optional[str] = None
        self.ied_name = config.protocol_params.get("ied_name", config.name) if config.protocol_params else config.name
        self._value_cache = {}
        self._control_handlers = []
        self._control_handler_params = []
        self._control_handler_ptrs = []  # Store pointers to prevent GC

        self._sbo_state = {}
        self._sbo_select_timeout_ms = 30000

    def connect(self) -> bool:
        if not self.config.scd_file_path:
            if self.event_logger:
                self.event_logger.error("IEC61850Server", "No SCD file provided for server simulation")
            return False

        try:
            # Verify file exists and is readable
            scd_path = self.config.scd_file_path
            if not os.path.exists(scd_path):
                raise RuntimeError(f"SCD file does not exist: {scd_path}")
            
            file_size = os.path.getsize(scd_path)
            if file_size == 0:
                raise RuntimeError(f"SCD file is empty: {scd_path}")
            
            logger.info(f"Loading IED model from: {scd_path} ({file_size} bytes)")
            # Keep parsing info out of the Event Log to reduce noise; keep it in the normal logger for debugging
            logger.debug(f"Parsing SCD/ICD for {self.ied_name} from {scd_path}")

            # Try to create model from SCD/ICD/CID
            # Note: libiec61850 works best with ICD/CID files
            self.model = lib.ConfigFileParser_createModelFromConfigFileEx(scd_path.encode("utf-8"))
            
            if not self.model:
                file_ext = os.path.splitext(scd_path)[1].lower()
                
                # If it's already an ICD/CID and failed, don't try extraction
                if file_ext in (".icd", ".cid"):
                    logger.warning(f"ConfigFileParser failed on {file_ext} file, trying dynamic model")
                    if self.event_logger:
                        self.event_logger.warning("IEC61850Server", f"{file_ext.upper()} parsing failed")
                else:
                    # It's an SCD - try extracting ICD section
                    logger.warning("ConfigFileParser_createModelFromConfigFileEx failed, trying ICD extraction")
                    if self.event_logger:
                        self.event_logger.warning("IEC61850Server", "SCD parsing failed, attempting ICD extraction")
                    
                    # Try to extract ICD and create model from that
                    icd_path = self._extract_icd_from_scd(scd_path, self.ied_name)
                    if icd_path:
                        self.model = lib.ConfigFileParser_createModelFromConfigFileEx(icd_path.encode("utf-8"))
                        if self.model:
                            self._filtered_scd_path = icd_path
                            logger.info(f"Successfully loaded model from extracted ICD: {icd_path}")
            
            # Native parser failed - try Python dynamic builder
            # Check environment variable to control dynamic builder behavior
            use_dynamic_builder = os.environ.get("IEC61850_USE_DYNAMIC_BUILDER", "true").lower() == "true"
            
            if not self.model:
                if use_dynamic_builder:
                    logger.warning("Native parser failed - trying Python dynamic model builder")
                    if self.event_logger:
                        self.event_logger.warning(
                            "IEC61850Server",
                            "⚠️ ConfigFileParser failed - attempting Python dynamic builder\n"
                            "   • May work with some libiec61850 builds\n"
                            "   • Set IEC61850_USE_DYNAMIC_BUILDER=false to disable"
                        )
                    
                    # Try dynamic model builder from SCD parser (increased limit)
                    self.model = self._create_model_from_scd_parser(max_attributes=10000)
                    
                    if self.model:
                        logger.info("Successfully created dynamic model from SCD parser")
                        if self.event_logger:
                            self.event_logger.info(
                                "IEC61850Server",
                                "✅ Dynamic model built from SCD (may be unstable with some DLL builds)"
                            )
                
                if not self.model:
                    logger.error("Using minimal model only (LLN0 with Mod data object)")
                    if self.event_logger:
                        self.event_logger.error(
                            "IEC61850Server",
                            "⚠️ Minimal model only (LLN0)\n"
                            "   • Full model requires working libiec61850 with ConfigFileParser\n"
                            "   • Or set IEC61850_USE_DYNAMIC_BUILDER=true (may crash some builds)"
                        )
                    
                    self.model = self._create_minimal_model()
                
                if not self.model:
                    raise RuntimeError(
                        f"Failed to create IED model for '{self.ied_name}'"
                    )

            # Create the IED server
            self.server = lib.IedServer_create(self.model)
            if not self.server:
                raise RuntimeError("Failed to create IED server from model")

            # Configure server settings
            try:
                # For IEC 61850 servers, ALWAYS bind to 0.0.0.0 (all interfaces)
                # The config.ip_address represents the advertised IP, not the bind address
                # This prevents WinError 10049 on Windows when the specific IP isn't available
                bind_ip = "0.0.0.0"
                logger.info(f"Server will listen on all interfaces (0.0.0.0)")
                
                # Note: IedServer_setLocalIpAddress may be used for specific scenarios
                # but for standard operation, omitting it or using 0.0.0.0 works best
                try:
                    lib.IedServer_setLocalIpAddress(self.server, bind_ip.encode("utf-8"))
                    logger.debug(f"Set local IP address to: {bind_ip}")
                except Exception as e:
                    logger.debug(f"Could not set local IP address (not critical): {e}")
            except Exception as e:
                logger.warning(f"Could not configure server IP settings: {e}")

            try:
                # Set server identity
                lib.IedServer_setServerIdentity(
                    self.server,
                    self.ied_name.encode("utf-8"),
                    b"SCADA Scout",
                    b"IEC61850 Simulator"
                )
                logger.info(f"Set server identity: {self.ied_name}")
            except Exception as e:
                logger.warning(f"Could not set server identity: {e}")

            # Set default write access policy to ALLOW (critical for some clients)
            # This prevents undefined behavior if a client tries to write to an unmapped variable
            try:
                if hasattr(lib, "IedServer_setWriteAccessPolicy"):
                    # Define constants manually if missing in lib
                    fc_all = getattr(lib, "IEC61850_FC_ALL", -1) 
                    policy_allow = getattr(lib, "ACCESS_POLICY_ALLOW", 0) # 0 is typical ALLOW enum value in C
                    
                    lib.IedServer_setWriteAccessPolicy(
                        self.server,
                        fc_all,
                        policy_allow
                    )
                    logger.info(f"Set default write access policy to ALLOW (FC={fc_all}, Policy={policy_allow})")
            except Exception as e:
                logger.warning(f"Could not set write access policy: {e}")

            # Register write access handler for debugging
            # REMOVED: WriteAccessHandler not defined in lib61850.py, unsafe to use
            # try:
            #     self._write_access_handler = self._make_write_access_handler()
            #     if hasattr(lib, "IedServer_handleWriteAccess"):
            #         lib.IedServer_handleWriteAccess(self.server, None, self._write_access_handler, None)
            #         logger.info("Registered write access handler")
            # except Exception as e:
            #     logger.warning(f"Failed to register write access handler: {e}")


            # Register SBO control handlers (if any)
            try:
                self._register_sbo_handlers()
            except Exception as e:
                logger.warning(f"Failed to register SBO handlers: {e}")

            # Start the server
            if int(self.config.port) < 1024:
                # Check for administrator/root privileges on Windows/Linux
                import sys
                import platform
                
                needs_elevation = False
                if platform.system() == "Windows":
                    try:
                        import ctypes
                        needs_elevation = not ctypes.windll.shell32.IsUserAnAdmin()
                    except Exception:
                        needs_elevation = True  # Assume needs elevation if check fails
                elif hasattr(os, "geteuid"):
                    needs_elevation = os.geteuid() != 0
                else:
                    needs_elevation = True  # Unknown system, assume needs elevation
                
                if needs_elevation:
                    error_msg = (
                        f"⚠️ Port {self.config.port} requires administrator/root privileges.\n"
                        f"   • On Windows: Run as Administrator\n"
                        f"   • On Linux: Use sudo or run as root\n"
                        f"   • Alternative: Use a port >= 1024 (e.g., 10002)"
                    )
                    logger.error(error_msg)
                    if self.event_logger:
                        self.event_logger.error("IEC61850Server", error_msg)
                    raise RuntimeError(f"Port {self.config.port} requires elevated privileges")

            # Verify model is valid before attempting start
            if not self.model:
                raise RuntimeError("Cannot start server: model is NULL")
            
            # Check if port is available
            import socket
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_sock.bind(("0.0.0.0", int(self.config.port)))
                test_sock.close()
                logger.debug(f"Port {self.config.port} is available for binding")
            except OSError as e:
                logger.warning(f"Port {self.config.port} may be in use or unavailable: {e}")
                if self.event_logger:
                    self.event_logger.warning("IEC61850Server", f"⚠️ Port {self.config.port} may already be in use")

            logger.info(f"Starting IEC61850 server on 0.0.0.0:{self.config.port}")
            start_result = lib.IedServer_start(self.server, int(self.config.port))

            # Some libiec61850 builds return void; check isRunning if so
            if start_result is None:
                is_running = False
                # Retry a few times to avoid false negatives right after start
                for attempt in range(10):  # Increased retries
                    try:
                        import time
                        time.sleep(0.05)  # Small delay before check
                        is_running = bool(lib.IedServer_isRunning(self.server))
                        if is_running:
                            logger.debug(f"Server running check succeeded on attempt {attempt + 1}")
                            break
                        logger.debug(f"Server not running on attempt {attempt + 1}, retrying...")
                    except Exception as e:
                        logger.debug(f"Exception checking isRunning on attempt {attempt + 1}: {e}")
                        is_running = False
                
                if is_running:
                    self.connected = True
                    logger.info("IEC61850 server started successfully")
                    if self.event_logger:
                        # Show actual binding info
                        bind_info = f"0.0.0.0:{self.config.port} (accessible on all network interfaces)"
                        self.event_logger.info(
                            "IEC61850Server",
                            f"✅ Started IEC 61850 server '{self.ied_name}' on {bind_info}"
                        )
                    return True
                
                # Gather diagnostic info
                diag_info = []
                diag_info.append(f"Bind IP: {bind_ip}")
                diag_info.append(f"Port: {self.config.port}")
                diag_info.append(f"Model valid: {self.model is not None}")
                try:
                    state = lib.IedServer_getState(self.server)
                    diag_info.append(f"Server state: {state}")
                except Exception:
                    diag_info.append("Server state: unknown")
                
                error_msg = f"Failed to start IEC61850 server (isRunning=false). {', '.join(diag_info)}"
                if self.event_logger:
                    self.event_logger.error("IEC61850Server", 
                        f"❌ Server start failed\n" +
                        "\n".join([f"   • {d}" for d in diag_info]) +
                        "\n   • Try a different port or check if libiec61850 is properly installed"
                    )
                raise RuntimeError(error_msg)

            # Check if server actually started (when return code is available)
            if start_result == 0:  # 0 = success in libiec61850
                self.connected = True
                logger.info("IEC61850 server started successfully")

                if self.event_logger:
                    # Show actual binding info
                    bind_info = f"0.0.0.0:{self.config.port} (accessible on all network interfaces)"
                    self.event_logger.info(
                        "IEC61850Server",
                        f"✅ Started IEC 61850 server '{self.ied_name}' on {bind_info}"
                    )
                return True

            error_msg = f"Failed to start IEC61850 server (error code: {start_result})"
            if start_result == 1:
                error_msg += " - Port may be in use"
            elif start_result == 2:
                error_msg += " - Network interface not available"

            logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            logger.error(f"IEC61850 server start failed: {e}")
            if self.event_logger:
                self.event_logger.error("IEC61850Server", f"Server start failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        try:
            if self.server:
                try:
                    lib.IedServer_stop(self.server)
                except Exception:
                    pass
                # Always destroy server - it will clean up the model internally
                # Do NOT call IedModel_destroy separately - causes double-free
                try:
                    lib.IedServer_destroy(self.server)
                except Exception:
                    pass
        finally:
            self.server = None
            self.model = None  # Clear reference but don't destroy - server handles it
            self.connected = False

        # Clean up temporary files (both filtered SCD and extracted ICD)
        if self._filtered_scd_path and os.path.exists(self._filtered_scd_path):
            try:
                os.remove(self._filtered_scd_path)
            except Exception:
                pass
            self._filtered_scd_path = None

        if self.event_logger:
            self.event_logger.info("IEC61850Server", "IEC 61850 server stopped")

    def discover(self) -> Node:
        """Build the device tree from SCD for UI display."""
        if not self.config.scd_file_path:
            return Node(name=self.ied_name)
        parser = SCDParser(self.config.scd_file_path)
        return parser.get_structure(self.ied_name)

    def read_signal(self, signal: Signal) -> Signal:
        """Return cached value (if any) for UI reads."""
        value = self._value_cache.get(signal.address)
        signal.value = value
        signal.quality = SignalQuality.GOOD
        return signal

    def _create_filtered_scd(self, scd_path: str, ied_name: str) -> str:
        """Create a temporary SCD containing only the selected IED and its Communication entries."""
        try:
            tree = ET.parse(scd_path)
            root = tree.getroot()

            # Detect namespace
            ns_uri = None
            if '}' in root.tag:
                ns_uri = root.tag.split('}')[0].strip('{')

            def _ns(tag: str) -> str:
                return f"{{{ns_uri}}}{tag}" if ns_uri else tag

            # Check if the IED exists
            target_ied = None
            ied_elements = root.findall(f".//{_ns('IED')}")
            for ied in ied_elements:
                if ied.get('name') == ied_name:
                    target_ied = ied
                    break
            
            if target_ied is None:
                logger.error(f"IED '{ied_name}' not found in SCD file")
                if self.event_logger:
                    self.event_logger.error("IEC61850Server", f"IED '{ied_name}' not found in SCD")
                raise ValueError(f"IED '{ied_name}' not found in SCD file")

            # Remove other IEDs (keep only the target)
            for ied in ied_elements:
                if ied.get('name') != ied_name:
                    parent = ied.getparent() if hasattr(ied, 'getparent') else None
                    if parent is not None:
                        parent.remove(ied)
            # ElementTree lacks getparent; fallback by rebuilding
            if not hasattr(ET.Element, 'getparent'):
                for parent in root.iter():
                    for child in list(parent):
                        if child.tag == _ns('IED') and child.get('name') != ied_name:
                            parent.remove(child)

            # Filter Communication section to keep only relevant ConnectedAPs
            comm = root.find(_ns('Communication'))
            if comm is not None:
                for sub in list(comm.findall(_ns('SubNetwork'))):
                    for cap in list(sub.findall(_ns('ConnectedAP'))):
                        if cap.get('iedName') != ied_name:
                            sub.remove(cap)
                    # Keep subnet even if empty - some parsers might need it
                    if len(list(sub.findall(_ns('ConnectedAP')))) == 0:
                        comm.remove(sub)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".scd")
            tree.write(tmp.name, encoding="utf-8", xml_declaration=True)
            tmp.close()
            
            # Verify the file was written
            if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) == 0:
                raise RuntimeError(f"Failed to write filtered SCD file to {tmp.name}")
            
            logger.info(f"Created filtered SCD for {ied_name} at {tmp.name} ({os.path.getsize(tmp.name)} bytes)")
            return tmp.name
        except Exception as e:
            logger.error(f"Failed to filter SCD for IED {ied_name}: {e}", exc_info=True)
            if self.event_logger:
                self.event_logger.error("IEC61850Server", f"SCD filtering failed for {ied_name}: {e}")
            # Return original path as fallback
            return scd_path

    def _extract_icd_from_scd(self, scd_path: str, ied_name: str) -> Optional[str]:
        """
        Extract ICD for specific IED from SCD.
        Simply extracts the IED element and DataTypeTemplates.
        """
        try:
            tree = ET.parse(scd_path)
            root = tree.getroot()

            # Detect namespace
            ns_uri = None
            if '}' in root.tag:
                ns_uri = root.tag.split('}')[0].strip('{')

            def _ns(tag: str) -> str:
                return f"{{{ns_uri}}}{tag}" if ns_uri else tag

            # Find the target IED
            source_ied = None
            for ied in root.findall(f".//{_ns('IED')}"):
                if ied.get('name') == ied_name:
                    source_ied = ied
                    break
            
            if source_ied is None:
                logger.error(f"IED '{ied_name}' not found in SCD")
                return None

            # Create new SCL root for ICD (minimal, standards-compliant)
            # Use same namespace and schema as source
            icd_root = ET.Element(root.tag)
            # Copy only essential root attributes
            for attr in ['version', 'revision', 'release']:
                if attr in root.attrib:
                    icd_root.set(attr, root.attrib[attr])
            
            # Copy namespace declarations
            for attr, value in root.attrib.items():
                if attr.startswith('{') or 'xmlns' in attr:
                    icd_root.set(attr, value)
            
            # Copy Header (optional but recommended)
            header = root.find(_ns('Header'))
            if header is not None:
                icd_root.append(ET.fromstring(ET.tostring(header)))
            
            # Copy the IED as-is (ABB SCDs already have proper ICD-style structure)
            icd_root.append(ET.fromstring(ET.tostring(source_ied)))
            
            # CRITICAL: Copy DataTypeTemplates - absolutely required
            dtt = root.find(_ns('DataTypeTemplates'))
            if dtt is not None:
                icd_root.append(ET.fromstring(ET.tostring(dtt)))
            else:
                logger.error("No DataTypeTemplates in SCD - cannot create valid ICD")
                return None
            
            # Write to temporary ICD file with proper encoding
            icd_tree = ET.ElementTree(icd_root)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".icd", mode='wb')
            icd_tree.write(tmp, encoding="utf-8", xml_declaration=True)
            tmp.close()
            
            file_size = os.path.getsize(tmp.name)
            logger.info(f"Extracted ICD for {ied_name}: {tmp.name} ({file_size} bytes)")
            
            return tmp.name
            
        except Exception as e:
            logger.error(f"Failed to extract ICD from SCD: {e}", exc_info=True)
            if self.event_logger:
                self.event_logger.error("IEC61850Server", f"ICD extraction failed: {e}")
            return None

    def _create_minimal_model(self) -> Optional[int]:
        """
        Create a minimal working IED model when SCD parsing fails.
        This provides a basic functional server for testing.
        """
        try:
            logger.info(f"Creating minimal dynamic model for {self.ied_name}")

            # Use libiec61850 dynamic model API (similar to IEDExplorer SCLServer)
            required_funcs = [
                "IedModel_create",
                "LogicalDevice_create",
                "LogicalNode_create",
                "DataObject_create",
                "DataAttribute_create",
            ]
            for func_name in required_funcs:
                if not hasattr(lib, func_name):
                    logger.error(f"libiec61850 missing required function: {func_name}")
                    return None

            # Create root model
            model = lib.IedModel_create(self.ied_name.encode("utf-8"))
            if not model:
                logger.error("Failed to create IedModel")
                return None

            # Create logical device (LD0)
            ldevice = lib.LogicalDevice_create(b"LD0", model)
            if not ldevice:
                logger.error("Failed to create LogicalDevice")
                return None

            # Create logical node (LLN0)
            lln0 = lib.LogicalNode_create(b"LLN0", ldevice)
            if not lln0:
                logger.error("Failed to create LogicalNode LLN0")
                return None

            # Create DataObject Mod and basic attributes (stVal, q, t)
            lln0_node = ctypes.cast(lln0, ctypes.POINTER(lib.ModelNode))
            mod = lib.DataObject_create(b"Mod", lln0_node, 0)
            if not mod:
                logger.error("Failed to create DataObject Mod")
                return None

            mod_node = ctypes.cast(mod, ctypes.POINTER(lib.ModelNode))

            # stVal (INT32, FC=ST)
            st_val = lib.DataAttribute_create(
                b"stVal",
                mod_node,
                lib.IEC61850_INT32,
                lib.IEC61850_FC_ST,
                0,
                0,
                0,
            )

            # q (QUALITY, FC=ST)
            quality = lib.DataAttribute_create(
                b"q",
                mod_node,
                lib.IEC61850_QUALITY,
                lib.IEC61850_FC_ST,
                0,
                0,
                0,
            )

            # t (TIMESTAMP, FC=ST)
            timestamp = lib.DataAttribute_create(
                b"t",
                mod_node,
                lib.IEC61850_TIMESTAMP,
                lib.IEC61850_FC_ST,
                0,
                0,
                0,
            )

            if not st_val or not quality or not timestamp:
                logger.error("Failed to create one or more data attributes")
                return None

            logger.debug(f"Successfully created minimal dynamic model for {self.ied_name}")

            return model
            
        except Exception as e:
            logger.error(f"Minimal model creation failed: {e}")
            return None

    def _create_model_from_scd_parser(self, max_attributes: int = 1000) -> Optional[int]:
        """Build a dynamic model from parsed SCD/ICD data (best-effort with safety limits)."""
        try:
            if not self.config.scd_file_path:
                return None

            parser = SCDParser(self.config.scd_file_path)
            root = parser.get_structure(self.ied_name)
            if not root or root.name in ("IED_Not_Found", "Error_No_SCD"):
                return None

            model = lib.IedModel_create(root.name.encode("utf-8"))
            if not model:
                logger.warning("IedModel_create returned NULL")
                return None

            try:
                lib.IedModel_setIedName(model, root.name.encode("utf-8"))
            except Exception:
                pass

            ld_nodes = {}
            ln_nodes = {}
            do_nodes = {}

            ld_created = 0
            ln_created = 0

            for ld_node in root.children:
                ld_inst = self._strip_ied_prefix(root.name, ld_node.name)
                ld_inst = ld_inst or "LD0"
                ldevice = lib.LogicalDevice_create(ld_inst.encode("utf-8"), model)
                if not ldevice:
                    logger.debug(f"LogicalDevice_create failed for {ld_inst}")
                    continue
                ld_nodes[ld_inst] = ldevice
                ld_created += 1

                for ln_node in ld_node.children:
                    lnode = lib.LogicalNode_create(ln_node.name.encode("utf-8"), ldevice)
                    if not lnode:
                        logger.debug(f"LogicalNode_create failed for {ld_inst}/{ln_node.name}")
                        continue
                    ln_nodes[(ld_inst, ln_node.name)] = lnode
                    ln_created += 1

            created_attrs = 0
            processed = 0
            skipped_no_slash = 0
            skipped_no_dot = 0
            skipped_no_lnode = 0
            skipped_short_path = 0
            
            # Build DataObjects/DataAttributes from signals (recursively)
            for signal in self._iter_signals(root):
                if not signal.address or "/" not in signal.address:
                    skipped_no_slash += 1
                    continue
                addr_ld, rest = signal.address.split("/", 1)
                addr_ld_norm = self._strip_ied_prefix(root.name, addr_ld)
                addr_ld_norm = addr_ld_norm or addr_ld
                if "." not in rest:
                    skipped_no_dot += 1
                    continue
                ln_name, path = rest.split(".", 1)

                lnode = ln_nodes.get((addr_ld_norm, ln_name))
                if not lnode:
                    if processed < 5:  # Log first few misses
                        logger.debug(f"LN not found: ({addr_ld_norm}, {ln_name}) from {signal.address}")
                    skipped_no_lnode += 1
                    continue
                
                processed += 1

                parts = path.split(".")
                if len(parts) < 2:
                    skipped_short_path += 1
                    continue

                da_name = parts[-1]
                do_path = parts[:-1]

                parent = ctypes.cast(lnode, ctypes.POINTER(lib.ModelNode))
                current_path = []
                for do_name in do_path:
                    current_path.append(do_name)
                    key = (addr_ld_norm, ln_name, ".".join(current_path))
                    if key in do_nodes:
                        parent = do_nodes[key]
                        continue

                    new_do = lib.DataObject_create(do_name.encode("utf-8"), parent, 0)
                    if not new_do:
                        break
                    parent = ctypes.cast(new_do, ctypes.POINTER(lib.ModelNode))
                    do_nodes[key] = parent

                if not parent:
                    continue

                fc, btype = self._parse_signal_meta(signal)
                da_type = self._map_btype_to_da_type(btype)
                fc_type = self._map_fc_to_const(fc)

                try:
                    da = lib.DataAttribute_create(
                        da_name.encode("utf-8"),
                        parent,
                        da_type,
                        fc_type,
                        0,
                        0,
                        0,
                    )
                    if da:
                        created_attrs += 1
                        # Safety limit: stop if we've created too many attributes
                        if created_attrs >= max_attributes:
                            logger.warning(f"Reached safety limit of {max_attributes} attributes, stopping")
                            break
                except Exception as e:
                    logger.debug(f"Failed to create DA {da_name} in {addr_ld_norm}/{ln_name}: {e}")

            logger.debug(
                f"Dynamic model build: LDs={ld_created}, LNs={ln_created}, attrs={created_attrs}"
            )
            logger.debug(
                f"Skipped: no_slash={skipped_no_slash}, no_dot={skipped_no_dot}, "
                f"no_lnode={skipped_no_lnode}, short_path={skipped_short_path}, processed={processed}"
            )

            if created_attrs == 0:
                logger.warning("Dynamic model creation produced 0 attributes")
                if self.event_logger:
                    self.event_logger.warning(
                        "IEC61850Server",
                        "⚠️ Dynamic model created but has 0 attributes"
                    )
                return None

            logger.debug(f"Created dynamic model from SCD/ICD for {root.name} with {created_attrs} attributes")
            return model

        except Exception as e:
            logger.warning(f"Dynamic model creation from SCD failed: {e}")
            return None

    def _strip_ied_prefix(self, ied_name: str, ld_name: str) -> str:
        if ld_name.startswith(ied_name):
            return ld_name[len(ied_name):]
        return ld_name

    def _iter_signals(self, node: Node):
        for sig in node.signals:
            yield sig
        for child in node.children:
            yield from self._iter_signals(child)

    def _parse_signal_meta(self, signal: Signal) -> tuple[str, str]:
        fc = signal.fc
        btype = ""
        desc = signal.description or ""
        if not fc and "FC:" in desc:
            try:
                fc = desc.split("FC:", 1)[1].split()[0]
            except Exception:
                fc = ""
        if "Type:" in desc:
            try:
                btype = desc.split("Type:", 1)[1].split()[0]
            except Exception:
                btype = ""
        return fc, btype

    def _map_fc_to_const(self, fc: str) -> int:
        fc_map = {
            "ST": lib.IEC61850_FC_ST,
            "MX": lib.IEC61850_FC_MX,
            "SP": lib.IEC61850_FC_SP,
            "SV": lib.IEC61850_FC_SV,
            "CF": lib.IEC61850_FC_CF,
            "DC": lib.IEC61850_FC_DC,
            "SG": lib.IEC61850_FC_SG,
            "SE": lib.IEC61850_FC_SE,
            "SR": lib.IEC61850_FC_SR,
            "OR": lib.IEC61850_FC_OR,
            "BL": lib.IEC61850_FC_BL,
            "EX": lib.IEC61850_FC_EX,
            "CO": lib.IEC61850_FC_CO,
        }
        return fc_map.get((fc or "ST"), lib.IEC61850_FC_ST)

    def _map_btype_to_da_type(self, btype: str) -> int:
        btype = (btype or "").strip()
        btype_map = {
            "BOOLEAN": lib.IEC61850_BOOLEAN,
            "INT8": lib.IEC61850_INT8,
            "INT16": lib.IEC61850_INT16,
            "INT32": lib.IEC61850_INT32,
            "INT8U": lib.IEC61850_INT8U,
            "INT16U": lib.IEC61850_INT16U,
            "INT32U": lib.IEC61850_INT32U,
            "FLOAT32": lib.IEC61850_FLOAT32,
            "FLOAT64": lib.IEC61850_FLOAT64,
            "Enum": lib.IEC61850_ENUMERATED,
            "Dbpos": lib.IEC61850_ENUMERATED,
            "Quality": lib.IEC61850_QUALITY,
            "Timestamp": lib.IEC61850_TIMESTAMP,
            "Check": lib.IEC61850_CHECK,
            "Struct": lib.IEC61850_CONSTRUCTED,
            "EntryID": lib.IEC61850_OCTET_STRING_8,
            "PhyComAddr": lib.IEC61850_PHYCOMADDR,
            "OptFlds": lib.IEC61850_OPTFLDS,
            "TrgOps": lib.IEC61850_TRGOPS,
            "VisString32": lib.IEC61850_VISIBLE_STRING_32,
            "VisString64": lib.IEC61850_VISIBLE_STRING_64,
            "VisString65": lib.IEC61850_VISIBLE_STRING_65,
            "VisString129": lib.IEC61850_VISIBLE_STRING_129,
            "VisString255": lib.IEC61850_VISIBLE_STRING_255,
            "Octet64": lib.IEC61850_OCTET_STRING_64,
            "Octet8": lib.IEC61850_OCTET_STRING_8,
        }
        return btype_map.get(btype, lib.IEC61850_BOOLEAN)

    def _register_sbo_handlers(self) -> None:
        """Register SBO select/operate handlers for control DOs defined in the SCD."""
        if not self.server or not self.model or not self.config.scd_file_path:
            return

        sbo_controls = self._find_sbo_control_objects(self.config.scd_file_path, self.ied_name)
        if not sbo_controls:
            return

        for ref, ctl_model in sbo_controls:
            model_node = lib.IedModel_getModelNodeByObjectReference(self.model, ref.encode("utf-8"))
            if not model_node:
                logger.warning(f"SBO control object not found in model: {ref}")
                continue

            data_object = ctypes.cast(model_node, ctypes.POINTER(lib.DataObject))
            if not data_object:
                logger.warning(f"Failed to cast model node to DataObject: {ref}")
                continue

            ctl_model_value = self._map_ctl_model(ctl_model)
            if ctl_model_value is not None:
                try:
                    lib.IedServer_updateCtlModel(self.server, data_object, ctl_model_value)
                except Exception as e:
                    logger.warning(f"Failed to set ctlModel for {ref}: {e}")

            control_ctx = {
                "ref": ref,
                "st_val": self._get_child_attribute(data_object, "stVal"),
                "op_ok": self._get_child_attribute(data_object, "opOk"),
                "t": self._get_child_attribute(data_object, "t"),
            }

            check_handler = self._make_sbo_check_handler(control_ctx)
            control_handler = self._make_sbo_control_handler(control_ctx)

            param = ctypes.py_object(control_ctx)
            # pointers must be kept alive!
            p_obj = ctypes.pointer(param)
            param_ptr = ctypes.cast(p_obj, ctypes.c_void_p)

            lib.IedServer_setPerformCheckHandler(self.server, data_object, check_handler, param_ptr)
            lib.IedServer_setControlHandler(self.server, data_object, control_handler, param_ptr)

            self._control_handlers.append((check_handler, control_handler))
            self._control_handler_params.append(param)
            self._control_handler_ptrs.append(p_obj)  # Keep pointer alive

            logger.info(f"Registered SBO handlers for {ref}")

    def _find_sbo_control_objects(self, scd_path: str, ied_name: str) -> list[tuple[str, str]]:
        """Find control DOs with SBO control model in the SCD and return object references."""
        results = []
        try:
            tree = ET.parse(scd_path)
            root = tree.getroot()

            ns_uri = None
            if "}" in root.tag:
                ns_uri = root.tag.split("}")[0].strip("{")

            def _ns(tag: str) -> str:
                return f"{{{ns_uri}}}{tag}" if ns_uri else tag

            # Find target IED
            target_ied = None
            for ied in root.findall(f".//{_ns('IED')}"):
                if ied.get("name") == ied_name:
                    target_ied = ied
                    break
            if target_ied is None:
                return results

            for ldevice in target_ied.findall(f".//{_ns('LDevice')}"):
                ld_inst = ldevice.get("inst", "LD0")
                for ln in list(ldevice):
                    tag = ln.tag.split("}")[-1]
                    if tag not in ("LN", "LN0"):
                        continue
                    ln_class = ln.get("lnClass", "LLN0")
                    ln_inst = ln.get("inst", "")
                    ln_prefix = ln.get("prefix", "")
                    ln_name = f"{ln_prefix}{ln_class}{ln_inst}"

                    for doi in ln.findall(f"{_ns('DOI')}"):
                        do_name = doi.get("name")
                        if not do_name:
                            continue

                        ctl_model = None
                        for dai in doi.findall(f"{_ns('DAI')}"):
                            if dai.get("name") == "ctlModel":
                                val = dai.find(f"{_ns('Val')}")
                                if val is not None and val.text:
                                    ctl_model = val.text.strip()
                                break

                        if ctl_model and "sbo" in ctl_model.lower():
                            ref = f"{ld_inst}/{ln_name}.{do_name}"
                            results.append((ref, ctl_model))

            return results
        except Exception as e:
            logger.warning(f"Failed to parse SCD for SBO controls: {e}")
            return results

    def _map_ctl_model(self, ctl_model: str) -> Optional[int]:
        if not ctl_model:
            return None
        model = ctl_model.strip().lower()
        if model == "sbo-with-enhanced-security":
            return lib.CONTROL_MODEL_SBO_ENHANCED
        if model == "sbo-with-normal-security":
            return lib.CONTROL_MODEL_SBO_NORMAL
        if model == "direct-with-enhanced-security":
            return lib.CONTROL_MODEL_DIRECT_ENHANCED
        if model == "direct-with-normal-security":
            return lib.CONTROL_MODEL_DIRECT_NORMAL
        if model == "status-only":
            return lib.CONTROL_MODEL_STATUS_ONLY
        return None

    def _get_child_attribute(self, data_object, name: str):
        node = ctypes.cast(data_object, ctypes.POINTER(lib.ModelNode))
        child = lib.ModelNode_getChild(node, name.encode("utf-8"))
        if not child:
            return None
        return ctypes.cast(child, ctypes.POINTER(lib.DataAttribute))

    # REMOVED: _make_write_access_handler - definition invalid

    def _make_sbo_check_handler(self, ctx):
        @lib.ControlPerformCheckHandler
        def _handler(action, _param, value, _test, _interlock_check):
            try:
                ref = ctx["ref"]
                now = int(lib.Hal_getTimeInMs())

                if lib.ControlAction_isSelect(action):
                    selected_at = self._sbo_state.get(ref)
                    # 30s timeout default
                    if selected_at and (now - selected_at) < self._sbo_select_timeout_ms:
                        lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_ALREADY_SELECTED)
                        return lib.CONTROL_OBJECT_ACCESS_DENIED

                    self._sbo_state[ref] = now
                    # logger.debug(f"SBO Select accepted for {ref}")
                    return lib.CONTROL_ACCEPTED

                # Operate: require selection
                selected_at = self._sbo_state.get(ref)
                if not selected_at or (now - selected_at) > self._sbo_select_timeout_ms:
                    lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_NOT_SELECTED)
                    return lib.CONTROL_WAITING_FOR_SELECT

                # logger.debug(f"SBO Operate accepted for {ref}")
                return lib.CONTROL_ACCEPTED
            except Exception as e:
                logger.error(f"Exception in SBO check handler: {e}")
                return lib.CONTROL_OBJECT_ACCESS_DENIED
        return _handler

    def _make_sbo_control_handler(self, ctx):
        @lib.ControlHandler
        def _handler(action, _param, value, _test):
            try:
                ref = ctx["ref"]
                state = False
                try:
                    state = bool(lib.MmsValue_getBoolean(value)) if value else False
                except Exception:
                    pass

                # Update opOk if available
                if ctx.get("op_ok"):
                    op_ok_val = lib.MmsValue_newBoolean(True)
                    lib.IedServer_updateAttributeValue(self.server, ctx["op_ok"], op_ok_val)
                    lib.MmsValue_delete(op_ok_val)

                # Update stVal if available
                if ctx.get("st_val"):
                    st_val = lib.MmsValue_newBoolean(state)
                    lib.IedServer_updateAttributeValue(self.server, ctx["st_val"], st_val)
                    lib.MmsValue_delete(st_val)

                # Update timestamp if available
                if ctx.get("t"):
                    ts = int(lib.Hal_getTimeInMs())
                    lib.IedServer_updateUTCTimeAttributeValue(self.server, ctx["t"], ts)

                # Clear selection on operate
                self._sbo_state.pop(ref, None)
                # logger.info(f"Control operate executed for {ref} (state={state})")
                return lib.CONTROL_RESULT_OK
            except Exception as e:
                logger.error(f"Exception in SBO control handler: {e}")
                return lib.CONTROL_RESULT_FAILED
        return _handler
