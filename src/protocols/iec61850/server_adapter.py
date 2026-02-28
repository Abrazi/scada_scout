import ctypes
import logging
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from typing import Optional, Any

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Node, Signal, SignalQuality
from src.core.scd_parser import SCDParser
from src.protocols.iec61850 import lib61850 as lib

logger = logging.getLogger(__name__)


class IEC61850ServerAdapter(BaseProtocol):
    """
    IEC 61850 server simulator backed by libiec61850.
    Loads a model from SCD and starts an MMS server on the configured IP/port.
    
    IP Binding Behavior:
    - config.ip_address = "0.0.0.0": Binds to all network interfaces (default)
    - config.ip_address = specific IP: Binds only to that IP address
    
    This allows multiple IEC 61850 servers to run simultaneously, each on a
    different IP address, making them accessible by their configured IPs on the network.
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
        self._cdc_control_dos = set()
        self._created_control_objects = {}  # Maps ref -> (data_object_ptr, ctl_model_val, ctl_model_str, ctl_model_da)
        self._sbo_bridge = None
        self._sbo_bridge_active = False
        self._sbo_operate_cb = None
        self._sbo_control_contexts = {}
        self._sbo_operate_cb_type = None
        self._use_c_sbo = os.environ.get("IEC61850_USE_C_SBO", "true").lower() == "true"
        self._load_sbo_bridge()

    def _load_sbo_bridge(self) -> None:
        if not self._use_c_sbo:
            logger.info("C SBO bridge disabled via IEC61850_USE_C_SBO=false")
            return

        system = os.name
        if system == "nt":
            lib_names = ["sbo_bridge.dll", "native_sbo_bridge.dll"]
        elif sys.platform == "darwin":
            lib_names = ["libsbo_bridge.dylib"]
        else:
            lib_names = ["libsbo_bridge.so"]

        search_paths = [
            os.path.dirname(__file__),
            os.getcwd(),
            os.path.join(os.getcwd(), "lib"),
        ]

        if system == "nt" and hasattr(os, "add_dll_directory"):
            for path in search_paths:
                if os.path.exists(path):
                    try:
                        os.add_dll_directory(path)
                    except Exception:
                        pass

        for path in search_paths:
            for name in lib_names:
                dll_path = os.path.join(path, name)
                if not os.path.exists(dll_path):
                    continue
                try:
                    bridge = ctypes.CDLL(dll_path)
                    bridge.SboBridge_create.argtypes = [ctypes.POINTER(lib.IedModel)]
                    bridge.SboBridge_create.restype = lib.IedServer
                    bridge.SboBridge_start.argtypes = [lib.IedServer, ctypes.c_int]
                    bridge.SboBridge_start.restype = ctypes.c_bool
                    bridge.SboBridge_stop.argtypes = [lib.IedServer]
                    bridge.SboBridge_stop.restype = None
                    bridge.SboBridge_destroy.argtypes = [lib.IedServer]
                    bridge.SboBridge_destroy.restype = None
                    bridge.SboBridge_registerControlPoint.argtypes = [
                        lib.IedServer,
                        ctypes.POINTER(lib.DataObject),
                        ctypes.c_char_p,
                        ctypes.c_uint32,
                    ]
                    bridge.SboBridge_registerControlPoint.restype = ctypes.c_int
                    self._sbo_operate_cb_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_uint8, ctypes.c_void_p)
                    bridge.SboBridge_setOperateCallback.argtypes = [self._sbo_operate_cb_type, ctypes.c_void_p]
                    bridge.SboBridge_setOperateCallback.restype = None
                    self._sbo_bridge = bridge
                    logger.info(f"Loaded C SBO bridge: {dll_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load C SBO bridge at {dll_path}: {e}")

        logger.info("C SBO bridge not found; falling back to Python handlers")

    def _debug_sbo_log(self, message: str) -> None:
        if os.environ.get("IEC61850_DEBUG_SBO_LOGS", "false").lower() == "true":
            print(message, flush=True)
            logger.debug(message)

    def _required_sbo_dais(self, ctl_model: str) -> set[str]:
        required = {"Oper", "Cancel"}
        if "enhanced" in (ctl_model or "").lower():
            required.add("SBOw")
        else:
            required.add("SBO")
        return required

    def _parse_scd_control_dois(self, scd_path: str, ied_name: str) -> list[dict]:
        results = []
        if not scd_path or not os.path.exists(scd_path):
            return results

        try:
            tree = ET.parse(scd_path)
            root = tree.getroot()

            ns_uri = None
            if "}" in root.tag:
                ns_uri = root.tag.split("}")[0].strip("{")

            def _ns(tag: str) -> str:
                return f"{{{ns_uri}}}{tag}" if ns_uri else tag

            for ied in root.findall(f".//{_ns('IED')}"):
                if ied.get("name") != ied_name:
                    continue

                for ldevice in ied.findall(f".//{_ns('LDevice')}"):
                    ld_inst = ldevice.get("inst", "LD0")
                    ld_inst_norm = self._strip_ied_prefix(ied_name, ld_inst) or ld_inst

                    for ln in ldevice.findall(f".//{_ns('LN')}") + ldevice.findall(f".//{_ns('LN0')}"):
                        prefix = ln.get("prefix", "")
                        ln_class = ln.get("lnClass", "")
                        inst = ln.get("inst", "")
                        full_ln_name = f"{prefix}{ln_class}{inst}"

                        for doi in ln.findall(f"{_ns('DOI')}"):
                            do_name = doi.get("name")
                            if not do_name:
                                continue

                            ctl_model = None
                            dai_names = set()
                            for dai in doi.findall(f"{_ns('DAI')}"):
                                name = dai.get("name")
                                if name:
                                    dai_names.add(name)
                                if name == "ctlModel":
                                    val = dai.find(f"{_ns('Val')}")
                                    if val is not None and val.text:
                                        ctl_model = val.text.strip()

                            if ctl_model:
                                ref = f"{ld_inst_norm}/{full_ln_name}.{do_name}"
                                results.append({
                                    "ref": ref,
                                    "ctl_model": ctl_model,
                                    "dai_names": dai_names,
                                })
            return results
        except Exception:
            return results

    @staticmethod
    def _find_available_ports(bind_ip: str, start_port: int = 10002, count: int = 3) -> list:
        """Find available ports starting from start_port"""
        import socket
        available = []
        port = start_port
        while len(available) < count and port < 65535:
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_sock.bind((bind_ip, port))
                test_sock.close()
                available.append(port)
            except OSError:
                pass
            port += 100  # Try ports in increments of 100
        return available

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
                    self.model = self._create_model_from_scd_parser()
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

            # Create the IED server (prefer C SBO bridge when available)
            self.server = None
            if self._sbo_bridge is not None:
                try:
                    self.server = self._sbo_bridge.SboBridge_create(self.model)
                    if self.server:
                        self._sbo_bridge_active = True
                        logger.info("Created IED server via C SBO bridge")
                except Exception as e:
                    logger.warning(f"C SBO bridge create failed, falling back to libiec61850: {e}")
                    self.server = None

            if not self.server:
                self.server = lib.IedServer_create(self.model)
                self._sbo_bridge_active = False

            if not self.server:
                raise RuntimeError("Failed to create IED server from model")

            # Configure server settings
            # Determine bind IP from configuration
            # - If config.ip_address is "0.0.0.0" or not set: bind to all interfaces
            # - Otherwise: bind to the specific IP (allows multiple servers on different IPs)
            bind_ip = self.config.ip_address if self.config.ip_address and self.config.ip_address != "0.0.0.0" else "0.0.0.0"
            
            if bind_ip == "0.0.0.0":
                logger.info(f"Server will listen on all interfaces (0.0.0.0)")
            else:
                logger.info(f"Server will listen on specific IP: {bind_ip}")
                # Verify IP is available on this system
                try:
                    from src.utils.network_utils import NetworkUtils
                    interfaces = NetworkUtils.get_network_interfaces()
                    local_ips = {iface.ip_address for iface in interfaces}
                    if bind_ip not in local_ips:
                        warning_msg = (
                            f"⚠️ IP {bind_ip} is not configured on this system.\n"
                            f"   Available IPs: {', '.join(sorted(local_ips))}\n"
                            f"   Falling back to 0.0.0.0 (all interfaces)"
                        )
                        logger.warning(warning_msg)
                        if self.event_logger:
                            self.event_logger.warning("IEC61850Server", warning_msg)
                        bind_ip = "0.0.0.0"
                except Exception as e:
                    logger.warning(f"Could not verify IP address, falling back to 0.0.0.0: {e}")
                    bind_ip = "0.0.0.0"
            
            # Set local IP address for single-access-point mode
            # Note: For multiple servers, we'll use IedServer_addAccessPoint instead
            try:
                lib.IedServer_setLocalIpAddress(self.server, bind_ip.encode("utf-8"))
                logger.debug(f"Set local IP address to: {bind_ip}")
            except Exception as e:
                logger.debug(f"Could not set local IP address (not critical): {e}")

            try:
                # Set server identity
                # Store as instance variables to avoid GC issues with C pointers
                self._ied_name_bytes = self.ied_name.encode("utf-8")
                self._vendor_bytes = b"SCADA Scout"
                self._model_bytes = b"IEC61850 Simulator"
                
                lib.IedServer_setServerIdentity(
                    self.server,
                    self._ied_name_bytes,
                    self._vendor_bytes,
                    self._model_bytes
                )
                logger.info(f"Set server identity: {self.ied_name}")
            except Exception as e:
                logger.warning(f"Could not set server identity: {e}")

            # Initialize default values if available
            try:
                if hasattr(lib, "IedServer_setAllModelDefaultValues"):
                    lib.IedServer_setAllModelDefaultValues(self.server)
                    logger.debug("Initialized model default values")
            except Exception as e:
                logger.debug(f"Could not set model default values: {e}")

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

            # Start the server (SBO handlers will be registered AFTER server starts)
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
            
            # Check if port is available on the bind IP
            import socket
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_sock.bind((bind_ip, int(self.config.port)))
                test_sock.close()
                logger.debug(f"Port {self.config.port} is available on {bind_ip}")
            except OSError as e:
                error_code = getattr(e, 'winerror', None) or getattr(e, 'errno', None)
                
                # Try to suggest available ports
                available_ports = self._find_available_ports(bind_ip)
                port_suggestion = f"\n   Suggested available ports: {', '.join(map(str, available_ports))}" if available_ports else ""
                
                # WinError 10013 = Access forbidden (port excluded/restricted by Windows)
                if error_code == 10013:
                    error_msg = (
                        f"❌ Port {self.config.port} is restricted by Windows.\n"
                        f"   This port is in a reserved/excluded range.\n"
                        f"   \n"
                        f"   Solutions:\n"
                        f"   1. Use a different port{port_suggestion}\n"
                        f"   2. Check excluded ports: netsh interface ipv4 show excludedportrange protocol=tcp\n"
                        f"   3. Remove exclusion (admin): netsh int ipv4 delete excludedportrange protocol=tcp startport={self.config.port} numberofports=1"
                    )
                    logger.error(error_msg)
                    if self.event_logger:
                        self.event_logger.error("IEC61850Server", error_msg)
                    raise RuntimeError(f"Port {self.config.port} is restricted by Windows (WinError 10013)")
                
                # WinError 10048 or EADDRINUSE = Port already in use
                elif error_code in (10048, 48, 98):  # Windows, macOS, Linux codes
                    error_msg = (
                        f"❌ Port {self.config.port} is already in use on {bind_ip}.\n"
                        f"   Another application is using this port.\n"
                        f"   \n"
                        f"   Solutions:\n"
                        f"   1. Use a different port{port_suggestion}\n"
                        f"   2. Stop the other application using this port\n"
                        f"   3. Check what's using it: netstat -ano | findstr :{self.config.port}"
                    )
                    logger.error(error_msg)
                    if self.event_logger:
                        self.event_logger.error("IEC61850Server", error_msg)
                    raise RuntimeError(f"Port {self.config.port} is already in use")
                
                # WinError 10049 = IP address not valid in this context
                elif error_code == 10049:
                    error_msg = (
                        f"❌ Cannot bind to {bind_ip}:{self.config.port}\n"
                        f"   The IP address is not configured on this system.\n"
                        f"   \n"
                        f"   Solutions:\n"
                        f"   1. Use 0.0.0.0 to listen on all interfaces\n"
                        f"   2. Configure the IP address on your network adapter\n"
                        f"   3. Use 'Check/Configure IPs' in the simulator dialog"
                    )
                    logger.error(error_msg)
                    if self.event_logger:
                        self.event_logger.error("IEC61850Server", error_msg)
                    raise RuntimeError(f"IP address {bind_ip} not available")
                
                # Generic error - log but continue (might still work)
                else:
                    logger.warning(f"Port check warning for {bind_ip}:{self.config.port}: {e}")
                    if self.event_logger:
                        self.event_logger.warning("IEC61850Server", 
                            f"⚠️ Port {self.config.port} may have issues on {bind_ip}\n"
                            f"   Error: {e}\n"
                            f"   Will attempt to start server anyway..."
                        )

            logger.info(f"Starting IEC61850 server on {bind_ip}:{self.config.port}")
            if self._sbo_bridge_active and self._sbo_bridge is not None:
                try:
                    self._sbo_bridge.SboBridge_start(self.server, int(self.config.port))
                    start_result = None
                except Exception as e:
                    logger.error(f"C SBO bridge start failed: {e}")
                    raise
            else:
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
                    
                    # Register SBO handlers NOW that server is running
                    try:
                        self._register_sbo_handlers()
                    except Exception as e:
                        logger.warning(f"Failed to register SBO handlers: {e}")
                    
                    if self.event_logger:
                        # Show actual binding info
                        if bind_ip == "0.0.0.0":
                            bind_info = f"0.0.0.0:{self.config.port} (accessible on all network interfaces)"
                        else:
                            bind_info = f"{bind_ip}:{self.config.port}"
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
                
                # Register SBO handlers NOW that server is running
                try:
                    self._register_sbo_handlers()
                except Exception as e:
                    logger.warning(f"Failed to register SBO handlers: {e}")

                if self.event_logger:
                    # Show actual binding info
                    if bind_ip == "0.0.0.0":
                        bind_info = f"0.0.0.0:{self.config.port} (accessible on all network interfaces)"
                    else:
                        bind_info = f"{bind_ip}:{self.config.port}"
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
                if self._sbo_bridge_active and self._sbo_bridge is not None:
                    try:
                        self._sbo_bridge.SboBridge_stop(self.server)
                    except Exception:
                        pass
                    try:
                        self._sbo_bridge.SboBridge_destroy(self.server)
                    except Exception:
                        pass
                else:
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
            self._sbo_bridge_active = False

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
        """Return cached value or direct C-level value for UI reads."""
        import ctypes
        
        # Try direct read if server is active
        if self.server:
            target_addr = signal.address
            if target_addr.startswith(self.ied_name):
                target_addr = target_addr[len(self.ied_name):]
                
            node_ptr = lib.IedModel_getModelNodeByObjectReference(self.model, signal.address.encode('utf-8'))
            if not node_ptr:
                node_ptr = lib.IedModel_getModelNodeByObjectReference(self.model, target_addr.encode('utf-8'))
                
            if node_ptr:
                da_ptr = ctypes.cast(node_ptr, ctypes.POINTER(lib.DataAttribute))
                mms_val = lib.IedServer_getAttributeValue(self.server, da_ptr)
                if mms_val:
                    parsed_val = self._parse_mms_value(mms_val)
                    if parsed_val is not None:
                        signal.value = parsed_val
                        signal.quality = SignalQuality.GOOD
                        self._value_cache[signal.address] = parsed_val
                        return signal

        # Fallback to cache
        value = self._value_cache.get(signal.address)
        signal.value = value
        signal.quality = SignalQuality.GOOD
        return signal

    def _parse_mms_value(self, mms_val) -> Any:
        if not mms_val:
            return None
        vtype = lib.MmsValue_getType(mms_val)
        if vtype == lib.MMS_BOOLEAN:
            return lib.MmsValue_getBoolean(mms_val)
        elif vtype in (lib.MMS_INTEGER, lib.MMS_UNSIGNED):
            return lib.MmsValue_toInt32(mms_val)
        elif vtype == lib.MMS_FLOAT:
            return lib.MmsValue_toFloat(mms_val)
        elif vtype == lib.MMS_VISIBLE_STRING:
            # MMS string might need decoding
            s = lib.MmsValue_toString(mms_val)
            if hasattr(s, 'decode'):
                return s.decode('utf-8')
            return s
        elif vtype == lib.MMS_BIT_STRING:
            if hasattr(lib, "MmsValue_getBitStringAsInteger"):
                return lib.MmsValue_getBitStringAsInteger(mms_val)
            size = lib.MmsValue_getBitStringSize(mms_val)
            val = 0
            for i in range(size):
                if lib.MmsValue_getBitStringBit(mms_val, i): val |= (1 << i)
            return val
        return f"[MmsType {vtype}]"

    def write_signal(self, signal: Signal, value: Any) -> bool:
        """
        Manually inject a raw value into a server attribute (e.g. stVal via UI or Python Scripts).
        Because this is a simulated server, we directly update the underlying MmsValue.
        """
        try:
            if not self.server:
                return False

            # libiec61850 expects the address starting with the Logical Device (e.g. CTRL/...)
            # The signal.address might be pre-fixed with IED name (e.g. ABBK3A03A1CTRL/...)
            target_addr = signal.address
            if target_addr.startswith(self.ied_name):
                target_addr = target_addr[len(self.ied_name):]

            import ctypes

            # 1. Resolve string address to ModelNode pointer using the IedModel
            # Object reference format is e.g. "CTRL/DCCILO1.EnaOpn.stVal" or "ABBK3A03A1CTRL/DCCILO1.EnaOpn.stVal"
            # IedModel_getModelNodeByObjectReference usually DOES expect the IED name prefix!
            node_ptr = lib.IedModel_getModelNodeByObjectReference(self.model, signal.address.encode('utf-8'))
            if not node_ptr:
                print(f"[DEBUG WRITE] Target attribute {signal.address} not found in model by full ObjectReference.", flush=True)
                
                # Fallback: try with the IED name stripped just in case
                node_ptr = lib.IedModel_getModelNodeByObjectReference(self.model, target_addr.encode('utf-8'))
                if not node_ptr:
                    print(f"[DEBUG WRITE] Target attribute {target_addr} not found in model by stripped ObjectReference.", flush=True)
                    logger.warning(f"write_signal: Target attribute {signal.address} does not exist.")
                    return False

            # Cast the ModelNode pointer to a DataAttribute pointer
            # In libiec61850's object model, DataAttribute extends ModelNode
            da_ptr = ctypes.cast(node_ptr, ctypes.POINTER(lib.DataAttribute))

            # 2. Get the exact node type to build the right MmsValue
            target_mms_val = lib.IedServer_getAttributeValue(self.server, da_ptr)
            if not target_mms_val:
                print(f"[DEBUG WRITE] Target attribute {target_addr} exists but couldn't get MmsValue.", flush=True)
                logger.warning(f"write_signal: Could not read MmsValue for {target_addr}.")
                return False

            target_type = lib.MmsValue_getType(target_mms_val)
            val_str = str(value).lower().strip()
            
            # Helper to parse boolean from common UI inputs
            is_truthy = val_str in ("true", "1", "on", "yes", "high")
            
            new_mms_val = None
            handled_dbpos = False

            try:
                if target_type == lib.MMS_BOOLEAN:
                    new_mms_val = lib.MmsValue_newBoolean(is_truthy)
                
                elif target_type in (lib.MMS_INTEGER, lib.MMS_UNSIGNED):
                    val_int = int(float(value)) if not isinstance(value, str) or value.isnumeric() else (1 if is_truthy else 0)
                    if hasattr(lib, "MmsValue_newIntegerFromInt32"):
                        new_mms_val = lib.MmsValue_newIntegerFromInt32(val_int)
                    elif hasattr(lib, "MmsValue_newInteger"):
                        new_mms_val = lib.MmsValue_newInteger(val_int)
                
                elif target_type == lib.MMS_BIT_STRING:
                    # Specific exception for Dbpos (2-bit string)
                    if hasattr(lib, "MmsValue_getBitStringSize") and lib.MmsValue_getBitStringSize(target_mms_val) == 2:
                        val_int = int(float(value)) if not isinstance(value, str) or value.isnumeric() else (2 if is_truthy else 1)
                        if hasattr(lib, "IedServer_updateDbposValue"):
                            lib.IedServer_updateDbposValue(self.server, da_ptr, val_int)
                            logger.debug(f"[SERVER_WRITE] Handled Dbpos BitString override for {target_addr}")
                            print(f"[DEBUG WRITE] Dbpos handled, returning True")
                            handled_dbpos = True
                
                elif target_type == lib.MMS_FLOAT:
                    val_float = float(value)
                    if hasattr(lib, "MmsValue_newFloat"):
                        new_mms_val = lib.MmsValue_newFloat(val_float)
                
                elif target_type == lib.MMS_VISIBLE_STRING:
                    if hasattr(lib, "MmsValue_newVisibleString"):
                        new_mms_val = lib.MmsValue_newVisibleString(val_str.encode('utf-8'))
                
            except ValueError as ve:
                logger.error(f"write_signal: Cannot cast '{value}' for MmsType {target_type}: {ve}")
                print(f"[DEBUG WRITE] ValueError during parsing/writing MMS value: {ve}, returning False")
                return False

            if new_mms_val and not handled_dbpos:
                lib.IedServer_updateAttributeValue(self.server, da_ptr, new_mms_val)
                lib.MmsValue_delete(new_mms_val)
                logger.info(f"[SERVER_WRITE] Injected {value} into {signal.address}")
                print(f"[DEBUG WRITE] Injected new_mms_val into {signal.address}, returning True")
                return True
            elif handled_dbpos:
                logger.info(f"[SERVER_WRITE] Injected Dbpos state {value} into {signal.address}")
                print(f"[DEBUG WRITE] Injected Dbpos state into {signal.address}, returning True")
                return True
            else:
                logger.warning(f"[SERVER_WRITE] Unsupported target MMS type {target_type} for manual write")
                print(f"[DEBUG WRITE] Unsupported target MMS type {target_type} for {signal.address}, returning False")
                return False
                
        except Exception as e:
            logger.exception(f"Exception during server_adapter.write_signal: {e}")
            print(f"[DEBUG WRITE] Exception during parsing/writing MMS value: {e}, returning False")
            return False

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

    def _create_model_from_scd_parser(self) -> Optional[int]:
        """Build a dynamic model from parsed SCD/ICD data (no artificial attribute safety limits)."""
        try:
            if not self.config.scd_file_path:
                return None

            parser = SCDParser(self.config.scd_file_path)
            root = parser.get_structure(self.ied_name)
            if not root or root.name in ("IED_Not_Found", "Error_No_SCD"):
                return None

            # Authority: use root.name if available from SCD, as it's the official IED name
            # ied_name from config is often a user-friendly label or IP based.
            ied_name = root.name if root and root.name not in ("IED_Not_Found", "Error_No_SCD") else (self.ied_name or "TEMPLATE")
            
            # Store the encoded model IED name separately to ensure it stays in memory
            self._model_ied_name_bytes = ied_name.encode("utf-8")
            
            model = lib.IedModel_create(self._model_ied_name_bytes)
            if not model:
                logger.warning("IedModel_create returned NULL")
                return None

            try:
                lib.IedModel_setIedName(model, self._model_ied_name_bytes)
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
            
            # Pre-create control DOs based on SCD definitions (before processing signals)
            # This ensures control objects exist with proper control options
            self._cdc_control_dos = set()
            control_dos_created = self._create_control_data_objects(ld_nodes, ln_nodes, do_nodes, root.name)
            if control_dos_created > 0:
                logger.info(f"Pre-created {control_dos_created} control Data Objects from SCD")
            else:
                logger.debug("No control Data Objects pre-created (may not have any, or pre-creation failed)")

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
                for i, do_name in enumerate(do_path):
                    current_path.append(do_name)
                    key = (addr_ld_norm, ln_name, ".".join(current_path))
                    if key in do_nodes:
                        parent = do_nodes[key]
                        continue

                    # Determine if this is a control DO - check if it's the last in path (before DA)
                    # and if the signal description indicates a control CDC
                    is_control_do = (i == len(do_path) - 1) and self._is_control_cdc(signal.description or "")
                    control_options = 0
                    
                    if is_control_do:
                        # Get control model from SCD if available
                        # Signal description may contain control info
                        control_options = self._get_control_options_for_signal(signal, addr_ld_norm, ln_name, do_name)
                    
                    new_do = lib.DataObject_create(do_name.encode("utf-8"), parent, control_options if is_control_do else 0)
                    if not new_do:
                        break
                    parent = ctypes.cast(new_do, ctypes.POINTER(lib.ModelNode))
                    do_nodes[key] = parent

                if not parent:
                    continue

                # Skip DA creation for CDC-created control DOs (they already include standard children)
                do_key = (addr_ld_norm, ln_name, ".".join(do_path))
                if do_key in self._cdc_control_dos:
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
                        # No safety limit: allow full attribute creation
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
    
    def _is_control_cdc(self, description: str) -> bool:
        """Check if the description indicates a control CDC type"""
        control_cdcs = ["DPC", "SPC", "INC", "ENC", "BSC", "APC", "BAC", "ISC"]
        desc_upper = description.upper()
        return any(cdc in desc_upper for cdc in control_cdcs)
    
    def _create_control_data_objects(self, ld_nodes: dict, ln_nodes: dict, do_nodes: dict, ied_name: str) -> int:
        """Pre-create all control Data Objects from SCD with proper control options"""
        created = 0
        print(f"[CTRL_CREATE] Starting control DO pre-creation for IED '{self.ied_name}'", flush=True)
        print(f"[CTRL_CREATE] SCD file path: {self.config.scd_file_path}", flush=True)
        logger.info(f"[CTRL_CREATE] Starting control DO pre-creation for IED '{self.ied_name}'")
        logger.info(f"[CTRL_CREATE] self.config.scd_file_path = {self.config.scd_file_path}")
        try:
            if not self.config.scd_file_path:
                logger.warning("[CTRL_CREATE] No SCD file path, skipping control DO pre-creation")
                print("[CTRL_CREATE] No SCD file path!", flush=True)
                return 0
            
            logger.info(f"[CTRL_CREATE] SCD file: {self.config.scd_file_path}")
            logger.debug(f"Available LDs: {list(ld_nodes.keys())}")
            logger.debug(f"Available LNs: {list(ln_nodes.keys())}")
            
            tree = ET.parse(self.config.scd_file_path)
            root = tree.getroot()
            
            ns_uri = None
            if "}" in root.tag:
                ns_uri = root.tag.split("}")[0].strip("{")
            
            def _ns(tag: str) -> str:
                return f"{{{ns_uri}}}{tag}" if ns_uri else tag
            
            # Find target IED
            found_ied = False
            print(f"[CTRL_CREATE] Searching for IED: {self.ied_name}", flush=True)
            for ied in root.findall(f".//{_ns('IED')}"):
                ied_name_attr = ied.get("name")
                print(f"[CTRL_CREATE] Found IED in SCD: {ied_name_attr}", flush=True)
                if ied_name_attr != self.ied_name:
                    continue
                
                found_ied = True
                logger.debug(f"Found IED: {self.ied_name}")
                print(f"[CTRL_CREATE] Matched target IED: {self.ied_name}", flush=True)
                
                for ldevice in ied.findall(f".//{_ns('LDevice')}"):
                    ld_inst = ldevice.get("inst", "LD0")
                    ld_inst_norm = self._strip_ied_prefix(ied_name, ld_inst) or ld_inst
                    
                    print(f"[CTRL_CREATE] Processing LDevice: {ld_inst} -> {ld_inst_norm}", flush=True)
                    logger.debug(f"Processing LDevice: {ld_inst} -> {ld_inst_norm}")
                    
                    for ln in ldevice.findall(f".//{_ns('LN')}") + ldevice.findall(f".//{_ns('LN0')}"):
                        prefix = ln.get("prefix", "")
                        lnClass = ln.get("lnClass", "")
                        inst = ln.get("inst", "")
                        full_ln_name = f"{prefix}{lnClass}{inst}"
                        
                        print(f"[CTRL_CREATE] Checking LN: ({ld_inst_norm}, {full_ln_name})", flush=True)
                        # Get the LogicalNode pointer
                        lnode = ln_nodes.get((ld_inst_norm, full_ln_name))
                        self._debug_sbo_log(
                            f"[SBO_DEBUG] LN {ld_inst_norm}/{full_ln_name} lnode={lnode}"
                        )
                        if not lnode:
                            print(f"[CTRL_CREATE] LN not in ln_nodes: ({ld_inst_norm}, {full_ln_name})", flush=True)
                            print(f"[CTRL_CREATE] Available keys: {list(ln_nodes.keys())[:5]}", flush=True)
                            logger.debug(f"LN not found in ln_nodes: ({ld_inst_norm}, {full_ln_name})")
                            continue
                        
                        # Find all DOIs with ctlModel
                        for doi in ln.findall(f"{_ns('DOI')}"):
                            do_name = doi.get("name")
                            if not do_name:
                                continue
                            
                            # Check if this DOI has a ctlModel
                            ctl_model = None
                            dai_names = set()
                            for dai in doi.findall(f"{_ns('DAI')}"):
                                dai_name = dai.get("name")
                                if dai_name:
                                    dai_names.add(dai_name)
                                if dai_name == "ctlModel":
                                    val = dai.find(f"{_ns('Val')}")
                                    if val is not None and val.text:
                                        ctl_model = val.text.strip()
                                        print(f"[CTRL_CREATE] Found ctlModel={ctl_model} for {ld_inst_norm}/{full_ln_name}.{do_name}", flush=True)
                                        logger.debug(f"Found ctlModel={ctl_model} for {ld_inst_norm}/{full_ln_name}.{do_name}")
                                    break
                            
                            # Skip if not a control or status-only
                            if not ctl_model:
                                continue
                            
                            if "status" in ctl_model.lower():
                                print(f"[CTRL_CREATE] Skipping status-only: {ld_inst_norm}/{full_ln_name}.{do_name}", flush=True)
                                logger.debug(f"Skipping status-only control: {ld_inst_norm}/{full_ln_name}.{do_name}")
                                continue

                            if "sbo" in ctl_model.lower():
                                required = self._required_sbo_dais(ctl_model)
                                missing = sorted(required - dai_names)
                                self._debug_sbo_log(
                                    f"[SBO_DEBUG] {ld_inst_norm}/{full_ln_name}.{do_name} ctlModel={ctl_model} "
                                    f"DAIs={sorted(dai_names)} missing={missing}"
                                )
                                if missing:
                                    logger.warning(
                                        f"SBO control {ld_inst_norm}/{full_ln_name}.{do_name} missing DAI {missing}; "
                                        "continuing and validating against the model"
                                    )
                            
                            # Map control model to libiec61850 constant
                            ctl_model_val = self._map_ctl_model(ctl_model)
                            if ctl_model_val is None:
                                logger.warning(f"Failed to map ctlModel '{ctl_model}' for {ld_inst_norm}/{full_ln_name}.{do_name}")
                                ctl_model_val = lib.CONTROL_MODEL_STATUS_ONLY
                            control_options = ctl_model_val
                            
                            # Create the control DataObject
                            key = (ld_inst_norm, full_ln_name, do_name)
                            print(f"[CTRL_CREATE] Creating DO: key={key}, lnClass={lnClass}", flush=True)
                            if key not in do_nodes:
                                parent = ctypes.cast(lnode, ctypes.POINTER(lib.ModelNode))
                                new_do = None

                                # Prefer CDC_DPC_create to populate control attributes; manual fallback keeps ctlModel aligned
                                print(f"[CTRL_CREATE] Checking CDC: lnClass={lnClass}, do_name={do_name}", flush=True)
                                ctl_model_da = None
                                if lnClass == "CSWI" and do_name == "Pos":
                                    if hasattr(lib, "CDC_DPC_create"):
                                        print(f"[CTRL_CREATE] Using CDC_DPC_create for {key}", flush=True)
                                        try:
                                            new_do = lib.CDC_DPC_create(
                                                do_name.encode("utf-8"),
                                                parent,
                                                ctl_model_val,
                                                control_options,
                                            )
                                            if new_do:
                                                self._cdc_control_dos.add(key)
                                                print(f"[CTRL_CREATE] CDC_DPC_create SUCCESS for {key}", flush=True)
                                                logger.info(
                                                    f"CDC_DPC_create success for {ld_inst_norm}/{full_ln_name}.{do_name}: "
                                                    f"ctlModel={ctl_model_val} ({ctl_model}), options={control_options}"
                                                )
                                            else:
                                                print(f"[CTRL_CREATE] CDC_DPC_create returned NULL for {key}", flush=True)
                                        except Exception as e:
                                            print(f"[CTRL_CREATE] CDC_DPC_create EXCEPTION: {e}", flush=True)
                                            logger.warning(
                                                f"CDC_DPC_create failed for {ld_inst_norm}/{full_ln_name}.{do_name}: {e}"
                                            )

                                    if not new_do:
                                        print(f"[CTRL_CREATE] Using MANUAL DPC creation for {key}", flush=True)
                                        try:
                                            print(
                                                f"[CTRL_CREATE] Calling _create_dpc_manually: "
                                                f"ctl_model_val={ctl_model_val}, options={control_options}",
                                                flush=True,
                                            )

                                            new_do, ctl_model_da = self._create_dpc_manually(
                                                do_name,
                                                parent,
                                                ctl_model_val,  # Control model (4 for sbo-with-enhanced-security)
                                                control_options,  # Control options
                                            )
                                            print(
                                                f"[CTRL_CREATE] _create_dpc_manually returned: "
                                                f"DO={new_do}, ctlModel DA={ctl_model_da}",
                                                flush=True,
                                            )
                                            self._debug_sbo_log(
                                                f"[SBO_DEBUG] Manual DPC pointers: parent={parent} new_do={new_do} ctl_model_da={ctl_model_da}"
                                            )
                                            if new_do:
                                                self._cdc_control_dos.add(key)
                                                print(f"[CTRL_CREATE] Manual DPC creation SUCCESS for {key}", flush=True)
                                                logger.info(
                                                    f"Manual DPC creation success for {ld_inst_norm}/{full_ln_name}.{do_name}: "
                                                    f"ctlModel={ctl_model_val} ({ctl_model}), options={control_options}"
                                                )
                                            else:
                                                print(f"[CTRL_CREATE] _create_dpc_manually returned NULL for {key}", flush=True)
                                                logger.warning(
                                                    f"Manual DPC creation returned NULL for {ld_inst_norm}/{full_ln_name}.{do_name}"
                                                )
                                        except Exception as e:
                                            print(f"[CTRL_CREATE] Manual DPC creation EXCEPTION: {e}", flush=True)
                                            logger.warning(
                                                f"Manual DPC creation failed for {ld_inst_norm}/{full_ln_name}.{do_name}: {e}"
                                            )

                                # Fallback to generic DataObject_create
                                if not new_do:
                                    new_do = lib.DataObject_create(do_name.encode("utf-8"), parent, control_options)
                                if new_do:
                                    do_nodes[key] = ctypes.cast(new_do, ctypes.POINTER(lib.ModelNode))
                                    created += 1
                                    logger.info(
                                        f"✓ Created control DO: {ld_inst_norm}/{full_ln_name}.{do_name} "
                                        f"with ctlModel={ctl_model} (options={control_options})"
                                    )

                                    # Store control object for SBO registration (even for non-SBO to keep mapping consistent)
                                    ref = f"{ld_inst_norm}/{full_ln_name}.{do_name}"
                                    if ctl_model_da is None:
                                        ctl_model_da = self._get_child_attribute(new_do, "ctlModel")
                                    self._created_control_objects[ref] = (
                                        new_do,
                                        ctl_model_val,
                                        ctl_model,
                                        ctl_model_da,
                                    )
                                    print(f"[CTRL_CREATE] Stored control object: {ref}", flush=True)
                                else:
                                    logger.warning(f"DataObject_create returned NULL for {ld_inst_norm}/{full_ln_name}.{do_name}")
                            else:
                                logger.debug(f"Control DO already exists: {key}")
            
            if not found_ied:
                logger.warning(f"IED '{self.ied_name}' not found in SCD")
            
            return created
            
        except Exception as e:
            logger.warning(f"Failed to pre-create control DOs: {e}", exc_info=True)
            return created
    
    def _get_control_options_for_signal(self, signal: Signal, ld_inst: str, ln_name: str, do_name: str) -> int:
        """Get control options by parsing SCD file for this specific DO"""
        try:
            if not self.config.scd_file_path:
                return 0
            
            # Build the object reference to search for
            ref = f"{ld_inst}/{ln_name}.{do_name}"
            
            # Parse SCD to find ctlModel for this DO
            tree = ET.parse(self.config.scd_file_path)
            root = tree.getroot()
            
            ns_uri = None
            if "}" in root.tag:
                ns_uri = root.tag.split("}")[0].strip("{")
            
            def _ns(tag: str) -> str:
                return f"{{{ns_uri}}}{tag}" if ns_uri else tag
            
            # Find the IED and logical device
            for ied in root.findall(f".//{_ns('IED')}"):
                if ied.get("name") != self.ied_name:
                    continue
                
                for ldevice in ied.findall(f".//{_ns('LDevice')}"):
                    if ldevice.get("inst") != ld_inst:
                        continue
                    
                    for ln in ldevice.findall(f".//{_ns('LN')}") + ldevice.findall(f".//{_ns('LN0')}"):
                        # Match by combining prefix + lnClass + inst
                        prefix = ln.get("prefix", "")
                        lnClass = ln.get("lnClass", "")
                        inst = ln.get("inst", "")
                        full_ln_name = f"{prefix}{lnClass}{inst}"
                        
                        if full_ln_name != ln_name:
                            continue
                        
                        # Find the DO
                        for doi in ln.findall(f"{_ns('DOI')}"):
                            if doi.get("name") != do_name:
                                continue
                            
                            # Look for ctlModel DAI
                            for dai in doi.findall(f"{_ns('DAI')}"):
                                if dai.get("name") == "ctlModel":
                                    val = dai.find(f"{_ns('Val')}")
                                    if val is not None and val.text:
                                        ctl_model = val.text.strip()
                                        mapped = self._map_ctl_model(ctl_model)
                                        if mapped is not None:
                                            logger.debug(f"Found ctlModel={ctl_model} for {ref}, using control option={mapped}")
                                            return mapped
            
            # No control model found, return default (status-only)
            return 0
            
        except Exception as e:
            logger.debug(f"Failed to get control options for {ld_inst}/{ln_name}.{do_name}: {e}")
            return 0

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
        disable_sbo = os.environ.get(
            "IEC61850_DISABLE_SBO_REGISTRATION",
            "false",  # Enabled on all platforms by default
        ).lower() == "true"
        if disable_sbo:
            print("[SBO_REGISTER] Disabled via IEC61850_DISABLE_SBO_REGISTRATION", flush=True)
            return

        print(f"[SBO_REGISTER] Starting handler registration", flush=True)
        print(f"[SBO_REGISTER] server={self.server}, model={self.model}, scd={self.config.scd_file_path}", flush=True)
        print(f"[SBO_REGISTER] Created control objects: {list(self._created_control_objects.keys())}", flush=True)
        
        if not self.server or not self.model:
            print(f"[SBO_REGISTER] Missing server or model, skipping", flush=True)
            return

        # Use the stored control objects from _create_control_data_objects
        if not self._created_control_objects:
            logger.debug("No control objects were created - nothing to register")
            return

        logger.info(f"Registering SBO handlers for {len(self._created_control_objects)} control objects")

        # If C SBO bridge is active, register control points in C and exit
        if self._sbo_bridge_active and self._sbo_bridge is not None:
            self._sbo_control_contexts = {}

            if self._sbo_operate_cb is None and self._sbo_operate_cb_type is not None:
                @self._sbo_operate_cb_type
                def _on_operate(obj_ref, command_value, _ctx):
                    try:
                        ref = obj_ref.decode("utf-8") if obj_ref else ""
                        ctx = self._sbo_control_contexts.get(ref)
                        if not ctx:
                            logger.debug(f"[SBO_BRIDGE] No context for {ref}")
                            return

                        state = bool(command_value)

                        if ctx.get("op_ok"):
                            op_ok_val = lib.MmsValue_newBoolean(True)
                            lib.IedServer_updateAttributeValue(self.server, ctx["op_ok"], op_ok_val)
                            lib.MmsValue_delete(op_ok_val)

                        if ctx.get("st_val"):
                            st_val = lib.MmsValue_newBoolean(state)
                            lib.IedServer_updateAttributeValue(self.server, ctx["st_val"], st_val)
                            lib.MmsValue_delete(st_val)

                        if ctx.get("t"):
                            ts = int(lib.Hal_getTimeInMs())
                            lib.IedServer_updateUTCTimeAttributeValue(self.server, ctx["t"], ts)

                        logger.info(f"[SBO_BRIDGE] Operate applied for {ref} (state={state})")
                    except Exception as cb_err:
                        logger.warning(f"[SBO_BRIDGE] Operate callback error: {cb_err}")

                self._sbo_operate_cb = _on_operate
                try:
                    self._sbo_bridge.SboBridge_setOperateCallback(self._sbo_operate_cb, None)
                    logger.info("[SBO_BRIDGE] Operate callback registered")
                except Exception as cb_set_err:
                    logger.warning(f"[SBO_BRIDGE] Failed to register operate callback: {cb_set_err}")

            registered_count = 0
            for ref, control_tuple in self._created_control_objects.items():
                if len(control_tuple) == 4:
                    data_object, ctl_model_val, ctl_model_str, ctl_model_da = control_tuple
                else:
                    data_object, ctl_model_val, ctl_model_str = control_tuple
                    ctl_model_da = None

                if "sbo" not in ctl_model_str.lower():
                    continue

                # Update control model in server
                try:
                    lib.IedServer_updateCtlModel(self.server, data_object, ctl_model_val)
                except Exception as e:
                    logger.debug(f"[SBO_BRIDGE] Failed to set ctlModel for {ref}: {e}")

                # Update ctlModel DA value if available
                if ctl_model_da is not None and hasattr(lib, "IedServer_updateAttributeValue"):
                    try:
                        if hasattr(lib, "IedServer_lockDataModel"):
                            lib.IedServer_lockDataModel(self.server)
                        mms_val = lib.MmsValue_newIntegerFromInt32(int(ctl_model_val))
                        lib.IedServer_updateAttributeValue(self.server, ctl_model_da, mms_val)
                        lib.MmsValue_delete(mms_val)
                        if hasattr(lib, "IedServer_unlockDataModel"):
                            lib.IedServer_unlockDataModel(self.server)
                    except Exception as e:
                        if hasattr(lib, "IedServer_unlockDataModel"):
                            try:
                                lib.IedServer_unlockDataModel(self.server)
                            except Exception:
                                pass
                        logger.debug(f"[SBO_BRIDGE] Failed to update ctlModel DA for {ref}: {e}")

                control_ctx = {
                    "ref": ref,
                    "st_val": self._get_child_attribute(data_object, "stVal"),
                    "op_ok": self._get_child_attribute(data_object, "opOk"),
                    "t": self._get_child_attribute(data_object, "t"),
                }
                self._sbo_control_contexts[ref] = control_ctx

                try:
                    result = self._sbo_bridge.SboBridge_registerControlPoint(
                        self.server,
                        data_object,
                        ref.encode("utf-8"),
                        int(self._sbo_select_timeout_ms),
                    )
                    if result == 0:
                        registered_count += 1
                    else:
                        logger.warning(f"[SBO_BRIDGE] Failed to register {ref} (code={result})")
                except Exception as e:
                    logger.warning(f"[SBO_BRIDGE] Exception registering {ref}: {e}")

            if registered_count > 0:
                logger.info(f"[SBO_BRIDGE] Registered {registered_count} SBO control points in C")
            else:
                logger.warning("[SBO_BRIDGE] No SBO control points were registered")
            return
        
        registered_count = 0
        for ref, control_tuple in self._created_control_objects.items():
            # Unpack the tuple - it might be 3 or 4 elements depending on manual vs CDC creation
            if len(control_tuple) == 4:
                data_object, ctl_model_val, ctl_model_str, ctl_model_da = control_tuple
            else:
                data_object, ctl_model_val, ctl_model_str = control_tuple
                ctl_model_da = None  # Will search for it
            
            print(f"[SBO_REGISTER] Processing {ref}: ctlModel={ctl_model_val}, DA={ctl_model_da}", flush=True)

            # --- Direct control (no SBO): register a simple control handler only ---
            if "sbo" not in ctl_model_str.lower():
                if "status" in ctl_model_str.lower():
                    print(f"[SBO_REGISTER] Skipping status-only: {ref} ({ctl_model_str})", flush=True)
                    continue
                try:
                    if not data_object:
                        continue
                    direct_ctx = {
                        "ref": ref,
                        "st_val": self._get_child_attribute(data_object, "stVal"),
                        "op_ok": self._get_child_attribute(data_object, "opOk"),
                        "t": self._get_child_attribute(data_object, "t"),
                    }
                    try:
                        lib.IedServer_updateCtlModel(self.server, data_object, ctl_model_val)
                    except Exception as e:
                        logger.debug(f"[DIRECT] Failed to set ctlModel for {ref}: {e}")
                    direct_handler = self._make_sbo_control_handler(direct_ctx)
                    direct_param = ctypes.py_object(direct_ctx)
                    direct_p_obj = ctypes.pointer(direct_param)
                    direct_param_ptr = ctypes.cast(direct_p_obj, ctypes.c_void_p)
                    lib.IedServer_setControlHandler(self.server, data_object, direct_handler, direct_param_ptr)
                    self._control_handlers.append((None, direct_handler))
                    self._control_handler_params.append(direct_param)
                    self._control_handler_ptrs.append(direct_p_obj)
                    logger.info(f"✓ Registered direct-control handler for {ref} (ctlModel={ctl_model_str})")
                    print(f"[SBO_REGISTER] ✓ Direct-control handler for {ref}", flush=True)
                    registered_count += 1
                except Exception as e:
                    logger.error(f"[DIRECT] Failed to register handler for {ref}: {e}", exc_info=True)
                continue

            required_attrs = sorted(self._required_sbo_dais(ctl_model_str))
            missing_attrs = [
                name for name in required_attrs if not self._get_child_attribute(data_object, name)
            ]
            if missing_attrs:
                logger.warning(
                    f"Skipping SBO registration for {ref}: missing control attributes {missing_attrs}"
                )
                self._debug_sbo_log(
                    f"[SBO_DEBUG] {ref} missing control attributes {missing_attrs}; skip registration"
                )
                continue
            
            try:
                if not data_object:
                    logger.warning(f"Skipping SBO registration for {ref}: data_object is NULL")
                    continue

                # Update ctlModel on the server (control behavior)
                try:
                    lib.IedServer_updateCtlModel(self.server, data_object, ctl_model_val)
                    print(f"[SBO_REGISTER] Updated control model for {ref}", flush=True)
                except Exception as e:
                    logger.warning(f"Failed to set ctlModel for {ref}: {e}")

                # Update the ctlModel DA value so clients see the correct numeric value
                try:
                    update_ctlmodel_da = os.environ.get(
                        "IEC61850_SBO_UPDATE_CTLMODEL_DA",
                        "true",  # Enabled on all platforms by default
                    ).lower() == "true"
                    if not update_ctlmodel_da:
                        print(f"[SBO_REGISTER] Skipping ctlModel DA update for {ref}", flush=True)
                    else:
                        # Use the stored pointer from manual DPC creation
                        ctl_attr = ctl_model_da
                        if ctl_attr is None:
                            ctl_attr = self._get_child_attribute(data_object, "ctlModel")
                        print(f"[SBO_REGISTER] Using stored ctlModel DA: {ctl_attr}", flush=True)
                        if ctl_attr is not None:
                            # Try multiple update methods
                            updated = False

                            # Method 1: Try updateInt32AttributeValue with data model locking
                            use_int32_update = os.environ.get(
                                "IEC61850_SBO_USE_INT32_UPDATE",
                                "true" if os.name == "nt" else "false",
                            ).lower() == "true"
                            if use_int32_update and hasattr(lib, "IedServer_updateInt32AttributeValue"):
                                try:
                                    # Lock the data model for thread-safe updates
                                    if hasattr(lib, "IedServer_lockDataModel"):
                                        lib.IedServer_lockDataModel(self.server)

                                    print(f"[SBO_REGISTER] Calling IedServer_updateInt32AttributeValue(server={self.server}, attr={ctl_attr}, value={int(ctl_model_val)})", flush=True)
                                    lib.IedServer_updateInt32AttributeValue(self.server, ctl_attr, int(ctl_model_val))
                                    print(f"[SBO_REGISTER] Used updateInt32AttributeValue", flush=True)

                                    # Unlock the data model
                                    if hasattr(lib, "IedServer_unlockDataModel"):
                                        lib.IedServer_unlockDataModel(self.server)

                                    updated = True
                                except Exception as e:
                                    # Make sure to unlock even if there's an error
                                    if hasattr(lib, "IedServer_unlockDataModel"):
                                        try:
                                            lib.IedServer_unlockDataModel(self.server)
                                        except Exception:
                                            pass
                                    print(f"[SBO_REGISTER] updateInt32AttributeValue failed: {e}", flush=True)

                            # Method 2: Try with MmsValue
                            if not updated and hasattr(lib, "MmsValue_newIntegerFromInt32"):
                                try:
                                    if hasattr(lib, "IedServer_lockDataModel"):
                                        lib.IedServer_lockDataModel(self.server)
                                    mms_val = lib.MmsValue_newIntegerFromInt32(int(ctl_model_val))
                                    if hasattr(lib, "IedServer_updateAttributeValue"):
                                        lib.IedServer_updateAttributeValue(self.server, ctl_attr, mms_val)
                                        print(f"[SBO_REGISTER] Used MmsValue method", flush=True)
                                        updated = True
                                    if hasattr(lib, "MmsValue_delete"):
                                        lib.MmsValue_delete(mms_val)
                                    if hasattr(lib, "IedServer_unlockDataModel"):
                                        lib.IedServer_unlockDataModel(self.server)
                                except Exception as e:
                                    if hasattr(lib, "IedServer_unlockDataModel"):
                                        try:
                                            lib.IedServer_unlockDataModel(self.server)
                                        except Exception:
                                            pass
                                    print(f"[SBO_REGISTER] MmsValue method failed: {e}", flush=True)

                            if updated:
                                print(f"[SBO_REGISTER] Set ctlModel DA value={ctl_model_val} for {ref}", flush=True)
                            else:
                                print(f"[SBO_REGISTER] WARNING: Could not update ctlModel value for {ref}", flush=True)
                        else:
                            print(f"[SBO_REGISTER] WARNING: ctlModel attribute not found for {ref}", flush=True)
                except Exception as e:
                    print(f"[SBO_REGISTER] ERROR updating ctlModel DA: {e}", flush=True)
                    logger.debug(f"Failed to update ctlModel DA for {ref}: {e}")

                # Create control context
                control_ctx = {
                    "ref": ref,
                    "st_val": self._get_child_attribute(data_object, "stVal"),
                    "op_ok": self._get_child_attribute(data_object, "opOk"),
                    "t": self._get_child_attribute(data_object, "t"),
                }
                self._debug_sbo_log(
                    f"[SBO_DEBUG] Register {ref} data_object={data_object} "
                    f"st_val={control_ctx['st_val']} op_ok={control_ctx['op_ok']} t={control_ctx['t']}"
                )

                # Create handlers
                check_handler = self._make_sbo_check_handler(control_ctx)
                control_handler = self._make_sbo_control_handler(control_ctx)

                param = ctypes.py_object(control_ctx)
                p_obj = ctypes.pointer(param)
                param_ptr = ctypes.cast(p_obj, ctypes.c_void_p)

                # Register handlers
                lib.IedServer_setPerformCheckHandler(self.server, data_object, check_handler, param_ptr)
                lib.IedServer_setControlHandler(self.server, data_object, control_handler, param_ptr)

                self._control_handlers.append((check_handler, control_handler))
                self._control_handler_params.append(param)
                self._control_handler_ptrs.append(p_obj)

                logger.info(f"✓ Registered SBO handlers for {ref} (ctlModel={ctl_model_str})")
                print(f"[SBO_REGISTER] ✓ Registered handlers for {ref}", flush=True)
                registered_count += 1
                
            except Exception as e:
                logger.error(f"Failed to register SBO handlers for {ref}: {e}", exc_info=True)
                print(f"[SBO_REGISTER] ERROR registering {ref}: {e}", flush=True)

        if registered_count > 0:
            logger.info(f"Successfully registered {registered_count} SBO control handlers")
        else:
            logger.warning(f"No SBO control handlers were registered")

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
    
    def _create_dpc_manually(self, name: str, parent, ctl_model: int, options: int):
        """
        Manually create a DPC (Double Point Control) structure with correct ctlModel value.
        This bypasses CDC_DPC_create which hardcodes ctlModel=0.
        
        DPC structure according to IEC 61850-7-3:
        - stVal (INT8, FC=ST) - status value
        - q (QUALITY, FC=ST) - quality
        - t (TIMESTAMP, FC=ST) - timestamp
        - ctlVal (CODED_ENUM, FC=CO) - control value
        - origin (ORIGIN, FC=CO) - originator
        - ctlNum (INT8U, FC=CO) - control number
        - T (TIMESTAMP, FC=CO) - control timestamp
        - Test (BOOLEAN, FC=CO) - test mode
        - Check (CHECK, FC=CO) - check
        - ctlModel (CODED_ENUM, FC=CF) - control model (THIS is what we need to set correctly!)
        - sboTimeout (INT32U, FC=CF) - SBO timeout
        - operTimeout (INT32U, FC=CF) - operate timeout
        - pulseConfig (PULSE_CONFIG, FC=CF) - pulse configuration
        """
        try:
            # Create the DataObject
            do = lib.DataObject_create(name.encode("utf-8"), parent, options)
            if not do:
                return None
            
            do_node = ctypes.cast(do, ctypes.POINTER(lib.ModelNode))
            
            # Create status attributes (FC=ST)
            lib.DataAttribute_create(b"stVal", do_node, lib.IEC61850_INT8, lib.IEC61850_FC_ST, 0, 0, 0)
            lib.DataAttribute_create(b"q", do_node, lib.IEC61850_QUALITY, lib.IEC61850_FC_ST, 0, 0, 0)
            lib.DataAttribute_create(b"t", do_node, lib.IEC61850_TIMESTAMP, lib.IEC61850_FC_ST, 0, 0, 0)
            
            # Create control attributes (FC=CO)
            # SBOw struct (required for sbo-with-enhanced-security)
            sbow = lib.DataAttribute_create(b"SBOw", do_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CO, 0, 0, 0)
            if sbow:
                sbow_node = ctypes.cast(sbow, ctypes.POINTER(lib.ModelNode))
                lib.DataAttribute_create(b"ctlVal", sbow_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)
                sbow_origin = lib.DataAttribute_create(b"origin", sbow_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CO, 0, 0, 0)
                if sbow_origin:
                    sbow_orig_node = ctypes.cast(sbow_origin, ctypes.POINTER(lib.ModelNode))
                    lib.DataAttribute_create(b"orCat", sbow_orig_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)
                    lib.DataAttribute_create(b"orIdent", sbow_orig_node, lib.IEC61850_OCTET_STRING_64, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"ctlNum", sbow_node, lib.IEC61850_INT8U, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"T", sbow_node, lib.IEC61850_TIMESTAMP, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"Test", sbow_node, lib.IEC61850_BOOLEAN, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"Check", sbow_node, lib.IEC61850_CHECK, lib.IEC61850_FC_CO, 0, 0, 0)

            # Oper struct (required by all clients for the operate service)
            oper = lib.DataAttribute_create(b"Oper", do_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CO, 0, 0, 0)
            if oper:
                oper_node = ctypes.cast(oper, ctypes.POINTER(lib.ModelNode))
                lib.DataAttribute_create(b"ctlVal", oper_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)
                oper_origin = lib.DataAttribute_create(b"origin", oper_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CO, 0, 0, 0)
                if oper_origin:
                    oper_orig_node = ctypes.cast(oper_origin, ctypes.POINTER(lib.ModelNode))
                    lib.DataAttribute_create(b"orCat", oper_orig_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)
                    lib.DataAttribute_create(b"orIdent", oper_orig_node, lib.IEC61850_OCTET_STRING_64, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"ctlNum", oper_node, lib.IEC61850_INT8U, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"T", oper_node, lib.IEC61850_TIMESTAMP, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"Test", oper_node, lib.IEC61850_BOOLEAN, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"Check", oper_node, lib.IEC61850_CHECK, lib.IEC61850_FC_CO, 0, 0, 0)

            # Cancel struct
            cancel = lib.DataAttribute_create(b"Cancel", do_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CO, 0, 0, 0)
            if cancel:
                cancel_node = ctypes.cast(cancel, ctypes.POINTER(lib.ModelNode))
                lib.DataAttribute_create(b"ctlVal", cancel_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"ctlNum", cancel_node, lib.IEC61850_INT8U, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"T", cancel_node, lib.IEC61850_TIMESTAMP, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"Test", cancel_node, lib.IEC61850_BOOLEAN, lib.IEC61850_FC_CO, 0, 0, 0)

            # ctlVal at top-level for direct/SBO-normal modes
            lib.DataAttribute_create(b"ctlVal", do_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)

            # Create origin structure (FC=CO)
            origin = lib.DataAttribute_create(b"origin", do_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CO, 0, 0, 0)
            if origin:
                origin_node = ctypes.cast(origin, ctypes.POINTER(lib.ModelNode))
                lib.DataAttribute_create(b"orCat", origin_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CO, 0, 0, 0)
                lib.DataAttribute_create(b"orIdent", origin_node, lib.IEC61850_OCTET_STRING_64, lib.IEC61850_FC_CO, 0, 0, 0)
            
            lib.DataAttribute_create(b"ctlNum", do_node, lib.IEC61850_INT8U, lib.IEC61850_FC_CO, 0, 0, 0)
            lib.DataAttribute_create(b"T", do_node, lib.IEC61850_TIMESTAMP, lib.IEC61850_FC_CO, 0, 0, 0)
            lib.DataAttribute_create(b"Test", do_node, lib.IEC61850_BOOLEAN, lib.IEC61850_FC_CO, 0, 0, 0)
            lib.DataAttribute_create(b"Check", do_node, lib.IEC61850_CHECK, lib.IEC61850_FC_CO, 0, 0, 0)
            
            # Create configuration attributes (FC=CF)
            # THIS is the critical one - create ctlModel DA (we'll set its value later via IedServer API)
            ctl_model_da = lib.DataAttribute_create(b"ctlModel", do_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CF, 0, 0, 0)
            if not ctl_model_da:
                print(f"[MANUAL_DPC] WARNING: Failed to create ctlModel DA for {name}", flush=True)
            else:
                print(f"[MANUAL_DPC] Created ctlModel DA for {name} (will set value={ctl_model} via server API)", flush=True)
                # Set the default value at build time so clients read ctlModel!=STATUS_ONLY immediately
                try:
                    mms_val = None
                    if hasattr(lib, "MmsValue_newIntegerFromInt32"):
                        mms_val = lib.MmsValue_newIntegerFromInt32(int(ctl_model))
                    elif hasattr(lib, "MmsValue_newInteger"):
                        mms_val = lib.MmsValue_newInteger(int(ctl_model))
                    elif hasattr(lib, "MmsValue_newUnsigned"):
                        mms_val = lib.MmsValue_newUnsigned(int(ctl_model))
                    if mms_val:
                        lib.DataAttribute_setValue(ctl_model_da, mms_val)
                        if hasattr(lib, "MmsValue_delete"):
                            lib.MmsValue_delete(mms_val)
                        print(f"[MANUAL_DPC] Initialized ctlModel default to {ctl_model} on DA", flush=True)
                    else:
                        print(f"[MANUAL_DPC] WARNING: Could not allocate MMS value for ctlModel", flush=True)
                except Exception as set_err:
                    print(f"[MANUAL_DPC] WARNING: Failed to set default ctlModel value: {set_err}", flush=True)
            
            lib.DataAttribute_create(b"sboTimeout", do_node, lib.IEC61850_INT32U, lib.IEC61850_FC_CF, 0, 0, 0)
            lib.DataAttribute_create(b"operTimeout", do_node, lib.IEC61850_INT32U, lib.IEC61850_FC_CF, 0, 0, 0)
            
            # Create pulseConfig structure (FC=CF)
            pulse = lib.DataAttribute_create(b"pulseConfig", do_node, lib.IEC61850_CONSTRUCTED, lib.IEC61850_FC_CF, 0, 0, 0)
            if pulse:
                pulse_node = ctypes.cast(pulse, ctypes.POINTER(lib.ModelNode))
                lib.DataAttribute_create(b"cmdQual", pulse_node, lib.IEC61850_ENUMERATED, lib.IEC61850_FC_CF, 0, 0, 0)
                lib.DataAttribute_create(b"onDur", pulse_node, lib.IEC61850_INT32U, lib.IEC61850_FC_CF, 0, 0, 0)
                lib.DataAttribute_create(b"offDur", pulse_node, lib.IEC61850_INT32U, lib.IEC61850_FC_CF, 0, 0, 0)
                lib.DataAttribute_create(b"numPls", pulse_node, lib.IEC61850_INT32U, lib.IEC61850_FC_CF, 0, 0, 0)
            
            print(f"[MANUAL_DPC] Successfully created DPC {name} with ctlModel={ctl_model}", flush=True)
            return do, ctl_model_da
            
        except Exception as e:
            print(f"[MANUAL_DPC] Error creating DPC: {e}", flush=True)
            return None, None

    def _get_child_attribute(self, data_object, name: str, fc: Optional[int] = None):
        if not data_object:
            return None

        use_fc_lookup = os.environ.get(
            "IEC61850_USE_FC_LOOKUP",
            "true" if os.name == "nt" else "false",
        ).lower() == "true"
        node = ctypes.cast(data_object, ctypes.POINTER(lib.ModelNode))

        # Try FC-specific lookup first if requested
        if use_fc_lookup and fc is not None and hasattr(lib, "ModelNode_getChildWithFc"):
            try:
                child = lib.ModelNode_getChildWithFc(node, name.encode("utf-8"), fc)
                if child:
                    return ctypes.cast(child, ctypes.POINTER(lib.DataAttribute))
            except Exception:
                pass

        # Fallback: generic child lookup
        child = lib.ModelNode_getChild(node, name.encode("utf-8"))
        if child:
            return ctypes.cast(child, ctypes.POINTER(lib.DataAttribute))

        return None

    # REMOVED: _make_write_access_handler - definition invalid

    def _make_sbo_check_handler(self, ctx):
        @lib.ControlPerformCheckHandler
        def _handler(action, _param, value, _test, _interlock_check):
            try:
                import ctypes
                ref = ctx["ref"]
                now = int(lib.Hal_getTimeInMs())

                if lib.ControlAction_isSelect(action):
                    logger.info(f"[SBO] Select request received for {ref}")
                    selected_at = self._sbo_state.get(ref)
                    
                    # Check if already selected and selection is still valid
                    if selected_at and (now - selected_at) < self._sbo_select_timeout_ms:
                        logger.warning(f"[SBO] {ref} already selected (age={(now-selected_at)}ms)")
                        lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_ALREADY_SELECTED)
                        return lib.CONTROL_OBJECT_ACCESS_DENIED

                    # Accept new selection
                    self._sbo_state[ref] = now
                    logger.info(f"[SBO] ✓ Select ACCEPTED for {ref}")
                    return lib.CONTROL_ACCEPTED

                # Operate: require prior selection
                if not lib.ControlAction_isSelect(action):
                    logger.info(f"[SBO] Operate request received for {ref}")
                    selected_at = self._sbo_state.get(ref)
                    
                    if not selected_at:
                        logger.warning(f"[SBO] {ref} not selected - rejecting operate")
                        try:
                            # Not all versions have setAddCause
                            if hasattr(lib, "ControlAction_setAddCause"):
                                lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_NOT_SELECTED)
                        except Exception:
                            pass
                        return lib.CONTROL_WAITING_FOR_SELECT
                    
                    if (now - selected_at) > self._sbo_select_timeout_ms:
                        logger.warning(f"[SBO] {ref} selection expired (age={(now-selected_at)}ms)")
                        try:
                            if hasattr(lib, "ControlAction_setAddCause"):
                                lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_NOT_SELECTED)
                        except Exception:
                            pass
                        return lib.CONTROL_WAITING_FOR_SELECT

                # Process Interlocking Check
                if _interlock_check and hasattr(lib, "MmsValue_getBoolean"):
                    # ref is e.g. "ABBK3A03A1CTRL/CBCSWI1.Pos" or "CTRL/CBCSWI1.Pos"
                    # We need to find the equivalent CILO e.g. "CTRL/DCCILO1.EnaOpn.stVal"
                    try:
                        cmd_val_type = lib.MmsValue_getType(value)
                        is_close = False # True = Close (1/On/True), False = Open (0/Off/False)
                        
                        if cmd_val_type == lib.MMS_BOOLEAN:
                            is_close = lib.MmsValue_getBoolean(value)
                        elif cmd_val_type in (lib.MMS_INTEGER, lib.MMS_UNSIGNED):
                            is_close = bool(lib.MmsValue_toInt32(value))
                        elif cmd_val_type == lib.MMS_BIT_STRING:
                            # Usually 2-bit for Pos: 01=Off(Open), 10=On(Close)
                            if hasattr(lib, "MmsValue_getBitStringAsInteger"):
                                bit_val = lib.MmsValue_getBitStringAsInteger(value)
                                if bit_val == 2: is_close = True  # 10=on
                                elif bit_val == 1: is_close = False # 01=off
                        
                        # Find LD and Prefix of the control object
                        # "CTRL/CBCSWI1.Pos" -> ld="CTRL", ln="CBCSWI1"
                        ref_parts = ref.split('/')
                        if len(ref_parts) == 2:
                            ld_name = ref_parts[0]
                            ln_part = ref_parts[1].split('.')[0] # CBCSWI1
                            
                            # Guess the CILO name. Often it shares inst or prefix. Or it's just 'CILO1'
                            # e.g. if we are CBCSWI1, look for CILO1 in the same LD.
                            # For safety, let's search all CILO nodes in our signal definitions for this LD.
                            cilo_lns = []
                            for sig_ref in self._value_cache.keys():
                                # Ensure the CILO is in the exact same Logical Device
                                if sig_ref.startswith(ld_name + '/') and "CILO" in sig_ref and "Ena" in sig_ref:
                                    cilo_lns.append(sig_ref)
                            
                            target_ena = "EnaCls.stVal" if is_close else "EnaOpn.stVal"
                            logger.info(f"[SBO] Interlock check requested. Direction Close={is_close}. Searching for {target_ena} in {ld_name}")
                            
                            interlock_passed = True # Default pass if no interlocking node found
                            
                            for c_ref in cilo_lns:
                                if target_ena in c_ref:
                                    # Found an interlocking node for this direction!
                                    logger.info(f"[SBO] Found matching interlock node: {c_ref}")
                                    
                                    # Check its value in the local C model directly
                                    node_ptr = lib.IedModel_getModelNodeByObjectReference(self.model, c_ref.encode('utf-8'))
                                    if not node_ptr and c_ref.startswith(self.ied_name):
                                        stripped_ref = c_ref[len(self.ied_name):]
                                        node_ptr = lib.IedModel_getModelNodeByObjectReference(self.model, stripped_ref.encode('utf-8'))
                                        
                                    if node_ptr:
                                        da_ptr = ctypes.cast(node_ptr, ctypes.POINTER(lib.DataAttribute))
                                        mms_val = lib.IedServer_getAttributeValue(self.server, da_ptr)
                                        if mms_val and lib.MmsValue_getType(mms_val) == lib.MMS_BOOLEAN:
                                            ena_val = lib.MmsValue_getBoolean(mms_val)
                                            logger.info(f"[SBO] Interlock check {c_ref} physical value -> {ena_val}")
                                            if not ena_val:
                                                interlock_passed = False
                                        else:
                                            logger.warning(f"[SBO] Could not read boolean from {c_ref}")
                                    else:
                                        logger.warning(f"[SBO] Node pointer not found in C-model for {c_ref}")
                                    break
                            
                            if not interlock_passed:
                                logger.warning(f"[SBO] Interlocking condition blocked Operate for {ref}")
                                try:
                                    if hasattr(lib, "ControlAction_setAddCause"):
                                        lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_BLOCKED_BY_INTERLOCKING)
                                except Exception:
                                    pass
                                return lib.CONTROL_OBJECT_ACCESS_DENIED
                                
                    except Exception as ie:
                        logger.error(f"[SBO] Interlock evaluation error: {ie}")

                logger.info(f"[SBO] ✓ Operate ACCEPTED for {ref} (selected {now-selected_at}ms ago)")
                return lib.CONTROL_ACCEPTED
                
                logger.debug(f"[SBO] Unknown action type for {ref}")
                return lib.CONTROL_ACCEPTED
            except Exception as e:
                logger.error(f"[SBO] Exception in check handler for {ref}: {e}", exc_info=True)
        return _handler

    def _make_sbo_control_handler(self, ctx):
        @lib.ControlHandler
        def _handler(action, _param, value, _test):
            try:
                ref = ctx["ref"]
                logger.info(f"[SBO] Control handler invoked for {ref}")
                
                val_type = lib.MmsValue_getType(value) if value else None
                state_bool = False
                state_int = -1
                
                # First extract the raw value intent
                try:
                    if val_type == lib.MMS_BOOLEAN:
                        state_bool = bool(lib.MmsValue_getBoolean(value))
                        state_int = 2 if state_bool else 1  # Standard Dbpos mapping: 2=ON, 1=OFF
                        logger.debug(f"[SBO] Control value (bool) for {ref}: {state_bool}")
                    elif val_type in (lib.MMS_INTEGER, lib.MMS_UNSIGNED):
                        if hasattr(lib, "MmsValue_toInt32"):
                            state_int = int(lib.MmsValue_toInt32(value))
                        elif hasattr(lib, "MmsValue_toUint32"):
                            state_int = int(lib.MmsValue_toUint32(value))
                        state_bool = True if state_int > 0 else False
                        logger.debug(f"[SBO] Control value (int) for {ref}: {state_int}")
                    else:
                        logger.warning(f"[SBO] Unhandled value type {val_type} for {ref}")
                except Exception as e:
                    logger.warning(f"[SBO] Failed to read control value: {e}")

                # Update opOk if available (usually boolean)
                if ctx.get("op_ok"):
                    op_ok_val = lib.MmsValue_newBoolean(True)
                    lib.IedServer_updateAttributeValue(self.server, ctx["op_ok"], op_ok_val)
                    lib.MmsValue_delete(op_ok_val)
                    logger.debug(f"[SBO] Updated opOk for {ref}")

                # Update stVal if available by inspecting its target type
                if ctx.get("st_val"):
                    target_mms_val = lib.IedServer_getAttributeValue(self.server, ctx["st_val"])
                    target_type = lib.MmsValue_getType(target_mms_val) if target_mms_val else None
                    new_mms_val = None
                    handled_dbpos = False

                    if target_type == lib.MMS_BOOLEAN:
                        new_mms_val = lib.MmsValue_newBoolean(state_bool)
                    elif target_type in (lib.MMS_INTEGER, lib.MMS_UNSIGNED):
                        if hasattr(lib, "MmsValue_newIntegerFromInt32"):
                            new_mms_val = lib.MmsValue_newIntegerFromInt32(state_int)
                        elif hasattr(lib, "MmsValue_newInteger"):
                            new_mms_val = lib.MmsValue_newInteger(state_int)
                    elif target_type == lib.MMS_BIT_STRING:
                        # Dbpos is represented as a 2-bit bitstring
                        if hasattr(lib, "MmsValue_getBitStringSize") and lib.MmsValue_getBitStringSize(target_mms_val) == 2:
                            if hasattr(lib, "IedServer_updateDbposValue"):
                                lib.IedServer_updateDbposValue(self.server, ctx["st_val"], state_int)
                                logger.debug(f"[SBO] Updated stVal via IedServer_updateDbposValue for {ref}")
                                handled_dbpos = True

                    if new_mms_val and not handled_dbpos:
                        lib.IedServer_updateAttributeValue(self.server, ctx["st_val"], new_mms_val)
                        lib.MmsValue_delete(new_mms_val)
                        logger.debug(f"[SBO] Updated stVal (type {target_type}) for {ref}")
                    elif not handled_dbpos:
                        logger.warning(f"[SBO] Could not create stVal update for target_type={target_type}")

                # Update timestamp if available
                if ctx.get("t"):
                    ts = int(lib.Hal_getTimeInMs())
                    lib.IedServer_updateUTCTimeAttributeValue(self.server, ctx["t"], ts)
                    logger.debug(f"[SBO] Updated timestamp for {ref}")

                # Clear selection on operate
                self._sbo_state.pop(ref, None)
                logger.info(f"[SBO] ✓ Control operation completed for {ref} (state={state_bool})")
                return lib.CONTROL_RESULT_OK
            except Exception as e:
                logger.error(f"[SBO] Exception in control handler for {ref}: {e}", exc_info=True)
                return lib.CONTROL_RESULT_FAILED
        return _handler
