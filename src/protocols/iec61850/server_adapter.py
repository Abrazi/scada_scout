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
            if self.event_logger:
                self.event_logger.info("IEC61850Server", f"Loading model for {self.ied_name} from {scd_path}")

            # Try to create model from SCD
            # Note: libiec61850 might not fully support SCD files for server creation
            # It works better with ICD files or programmatically created models
            self.model = lib.ConfigFileParser_createModelFromConfigFileEx(scd_path.encode("utf-8"))
            
            if not self.model:
                # Alternative: Try to extract ICD section and create a temporary ICD file
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
                
                if not self.model:
                    raise RuntimeError(
                        f"Failed to create IED model from SCD: {scd_path}. "
                        f"libiec61850 server may not support this SCD format. "
                        f"Try using an ICD file instead, or check that the SCD contains valid IED definition for '{self.ied_name}'"
                    )
            
            # If we still don't have a model, try creating a minimal working model
            if not self.model:
                logger.warning("Attempting to create minimal test model as fallback")
                if self.event_logger:
                    self.event_logger.warning("IEC61850Server", "Creating minimal test model as fallback")
                
                self.model = self._create_minimal_model()
                if not self.model:
                    raise RuntimeError(
                        f"Failed to create any IED model for '{self.ied_name}'. "
                        f"Both SCD parsing and minimal model creation failed."
                    )

            # Create the IED server
            self.server = lib.IedServer_create(self.model)
            if not self.server:
                raise RuntimeError("Failed to create IED server from model")

            # Configure server settings
            try:
                # Bind to specific interface IP
                lib.IedServer_setLocalIpAddress(self.server, self.config.ip_address.encode("utf-8"))
                logger.info(f"Set server IP address: {self.config.ip_address}")
            except Exception as e:
                logger.warning(f"Could not set server IP address: {e}")

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

            # Start the server
            logger.info(f"Starting IEC61850 server on {self.config.ip_address}:{self.config.port}")
            start_result = lib.IedServer_start(self.server, int(self.config.port))
            
            # Check if server actually started
            if start_result == 0:  # 0 = success in libiec61850
                self.connected = True
                logger.info(f"IEC61850 server started successfully")
                
                if self.event_logger:
                    self.event_logger.info(
                        "IEC61850Server",
                        f"✅ Started IEC 61850 server '{self.ied_name}' on {self.config.ip_address}:{self.config.port}"
                    )
                return True
            else:
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
                try:
                    lib.IedServer_destroy(self.server)
                except Exception:
                    pass
        finally:
            self.server = None
            self.connected = False

        try:
            if self.model:
                lib.IedModel_destroy(self.model)
        except Exception:
            pass
        finally:
            self.model = None

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
        Extract ICD (IED Capability Description) from SCD for a specific IED.
        ICD files contain only the IED section and DataTypeTemplates, which libiec61850 handles better.
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
            target_ied = None
            for ied in root.findall(f".//{_ns('IED')}"):
                if ied.get('name') == ied_name:
                    target_ied = ied
                    break
            
            if target_ied is None:
                logger.error(f"IED '{ied_name}' not found in SCD")
                return None

            # Create new ICD root (simplified SCL with just this IED)
            # Copy root attributes but change to ICD-like structure
            icd_root = ET.Element(root.tag, root.attrib)
            
            # Copy Header if exists
            header = root.find(_ns('Header'))
            if header is not None:
                icd_root.append(header)
            
            # Add the IED
            icd_root.append(target_ied)
            
            # CRITICAL: Copy DataTypeTemplates - required for model creation
            dtt = root.find(_ns('DataTypeTemplates'))
            if dtt is not None:
                icd_root.append(dtt)
            else:
                logger.warning("No DataTypeTemplates found in SCD - model creation will likely fail")
            
            # Write to temporary ICD file
            icd_tree = ET.ElementTree(icd_root)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".icd")
            icd_tree.write(tmp.name, encoding="utf-8", xml_declaration=True)
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
            mod = lib.DataObject_create(b"Mod", lln0, 0)
            if not mod:
                logger.error("Failed to create DataObject Mod")
                return None

            # stVal (INT32, FC=ST)
            st_val = lib.DataAttribute_create(
                b"stVal",
                mod,
                lib.IEC61850_INT32,
                lib.IEC61850_FC_ST,
                0,
                0,
                0,
            )

            # q (QUALITY, FC=ST)
            quality = lib.DataAttribute_create(
                b"q",
                mod,
                lib.IEC61850_QUALITY,
                lib.IEC61850_FC_ST,
                0,
                0,
                0,
            )

            # t (TIMESTAMP, FC=ST)
            timestamp = lib.DataAttribute_create(
                b"t",
                mod,
                lib.IEC61850_TIMESTAMP,
                lib.IEC61850_FC_ST,
                0,
                0,
                0,
            )

            if not st_val or not quality or not timestamp:
                logger.error("Failed to create one or more data attributes")
                return None

            logger.info(f"Successfully created minimal dynamic model for {self.ied_name}")
            if self.event_logger:
                self.event_logger.info(
                    "IEC61850Server",
                    f"Created minimal dynamic model for {self.ied_name} (LD0/LLN0/Mod)"
                )

            return model
            
        except Exception as e:
            logger.error(f"Minimal model creation failed: {e}")
            return None
