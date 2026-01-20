import logging
import json
import os
import threading
from typing import List, Dict, Optional, Any

from src.core.events import EventEmitter
from src.models.device_models import Device, DeviceConfig, DeviceType, Node, Signal, SignalQuality
from src.protocols.base_protocol import BaseProtocol
from src.core.subscription_manager import IECSubscriptionManager
from src.core.script_tag_manager import ScriptTagManager

logger = logging.getLogger(__name__)

class DeviceManagerCore(EventEmitter):
    """
    Manages the lifecycle of devices.
    Maintains the list of configured devices and their runtime state.
    Framework-agnostic implementation.
    """
    def __init__(self, config_path="devices.json"):
        super().__init__()
        self._devices: Dict[str, Device] = {}
        self._protocols: Dict[str, BaseProtocol] = {}
        self.event_logger = None 
        self.protocol_workers: Dict[str, object] = {}
        self.config_path = config_path
        self.folder_descriptions: Dict[str, str] = {} # folder_name -> description
        self._active_workers = []
        self._script_manager = None
        self._script_tag_manager = ScriptTagManager(self)
        self._saved_scripts = {}
        # Load persisted user scripts and update token internals
        try:
            self._load_user_scripts()
        except Exception:
            logger.exception("Failed to load persisted user scripts")
        
        # Authoritative Subscription Manager
        self.subscription_manager = IECSubscriptionManager()

    def add_device(self, config: DeviceConfig, save: bool = True):
        """Creates a new device from config and registers it."""
        if config.name in self._devices:
            logger.warning(f"Device '{config.name}' already exists.")
            return None
        
        device = Device(config=config)
        self._devices[config.name] = device
        
        # Instantiate protocol adapter
        protocol = self._create_protocol(config)
        if protocol:
            # CRITICAL: Set callback immediately so updates are propagated
            protocol.set_data_callback(lambda sig: self._on_signal_update(config.name, sig))
            self._protocols[config.name] = protocol
            
        logger.info(f"Device added: {config.name} ({config.device_type.value})")
        self.emit("device_added", device)
        if save:
            self.save_configuration()
        
        # Try to populate tree immediately (Offline Discovery)
        self.load_offline_scd(config.name)
        
        return device

    def remove_device(self, device_name: str, save: bool = True):
        """Removes a device and cleans up its connection. Set save=False for batch operations."""
        if device_name in self._devices:
            # Disconnect protocol and cleanup
            try:
                self.disconnect_device(device_name)
            except Exception:
                pass

            # Remove device object
            try:
                del self._devices[device_name]
            except KeyError:
                pass

            # Remove protocol wrapper
            if device_name in self._protocols:
                try:
                    del self._protocols[device_name]
                except Exception:
                    pass

            # Cleanup any Protocol worker assigned to this device
            if hasattr(self, 'protocol_workers') and device_name in self.protocol_workers:
                try:
                    wk = self.protocol_workers.pop(device_name)
                    try:
                        wk.stop()
                    except Exception:
                        pass
                except Exception:
                    pass

            logger.info(f"Device removed: {device_name}")
            self.emit("device_removed", device_name)
            if save:
                self.save_configuration()

    def remove_devices_bulk(self, device_names: List[str]):
        """Removes multiple devices efficiently with single save operation."""
        # Log batch start
        logger.info(f"Batch removing {len(device_names)} devices...")
        self.emit("batch_clear_started") # Signal UI to pause updates
        
        for name in device_names:
            self.remove_device(name, save=False)
            
        self.save_configuration()
        self.emit("project_cleared") # Trigger full UI refresh (easiest way to sync)

    def set_discovery_mode(self, device_name: str, use_scd: bool):
        """Switches between SCD and Online discovery for a device."""
        if device_name not in self._devices:
            return
            
        device = self._devices[device_name]
        device.config.use_scd_discovery = use_scd
        logger.info(f"Set discovery mode for {device_name} to {'SCD' if use_scd else 'Online'}")
        
        if device.connected:
            self.disconnect_device(device_name)
            self.connect_device(device_name)
        else:
            if use_scd and device.config.scd_file_path:
                 try:
                     # Assuming device.discover() is a method that returns a root node if we had logic here
                     # But discover logic is usually in protocol/worker. 
                     # We can trigger offline load manually.
                     self.load_offline_scd(device_name)
                 except Exception as e:
                     logger.error(f"Failed to load SCD: {e}")
        
        self.update_device_config(device.config)
        self.save_configuration()

    def update_device_config(self, config: DeviceConfig):
        """Updates the configuration of an existing device."""
        device = self._devices.get(config.name)
        if not device:
            return

        if device.connected:
            self.disconnect_device(config.name)
        
        if config.name in self._protocols:
             try:
                 self._protocols[config.name].disconnect()
             except Exception as e:
                 logger.debug(f"Error disconnecting {config.name} during reconfigure: {e}")
             del self._protocols[config.name]
            
        device.config = config
        
        self.emit("device_removed", config.name)
        self.emit("device_added", device)
        self.save_configuration()

    def disconnect_device(self, device_name: str):
        """Disconnects a device."""
        if device_name in self._protocols:
            try:
                self._protocols[device_name].disconnect()
                del self._protocols[device_name]
            except Exception as e:
                logger.error(f"Error disconnecting {device_name}: {e}")
        
        self.update_connection_status(device_name, False)

    def get_device(self, device_name: str) -> Optional[Device]:
        return self._devices.get(device_name)

    def get_protocol(self, device_name: str) -> Optional[BaseProtocol]:
        """Get the protocol adapter for a device."""
        return self._protocols.get(device_name)

    def load_offline_scd(self, device_name: str):
        """Triggers offline discovery from SCD file without connecting."""
        device = self._devices.get(device_name)
        if not device:
            return
        
        is_modbus = device.config.device_type in [DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER]
        has_maps = (len(device.config.modbus_register_maps) > 0 or 
                    len(device.config.modbus_slave_mappings) > 0 or
                    len(device.config.modbus_slave_blocks) > 0)
        
        if not device.config.scd_file_path and not (is_modbus and has_maps):
            return

        if device_name not in self._protocols:
             protocol = self._create_protocol(device.config)
             if protocol:
                 protocol.set_data_callback(lambda sig: self._on_signal_update(device_name, sig))
                 self._protocols[device_name] = protocol
        
        protocol = self._protocols.get(device_name)
        if protocol and hasattr(protocol, 'discover'):
            try:
                root = protocol.discover()
                device.root_node = root
                self._assign_unique_addresses(device_name, device.root_node)
                self.emit("device_updated", device_name)
                logger.info(f"Offline SCD loaded for {device_name}")
            except Exception as e:
                logger.error(f"Failed to load offline SCD for {device_name}: {e}")

    def get_all_devices(self) -> List[Device]:
        return list(self._devices.values())

    def clear_all_devices(self):
        """Remove all devices and cleanup protocols and workers."""
        # Signal start of batch clear
        self.emit("batch_clear_started")
        
        names = list(self._devices.keys())
        for name in names:
            try:
                self.remove_device(name)
            except Exception:
                logger.exception(f"Error removing device during clear_all_devices: {name}")

        try:
            self._protocols.clear()
        except Exception:
            pass

        try:
            if hasattr(self, 'protocol_workers'):
                for wk in list(self.protocol_workers.values()):
                    try:
                        wk.stop()
                    except Exception:
                        pass
                self.protocol_workers.clear()
        except Exception:
            pass

        try:
            self.emit("project_cleared")
        except Exception:
            pass

    def save_configuration(self, path: Optional[str] = None):
        """Saves current state to a JSON file."""
        target_path = path or self.config_path
        try:
            configs = [d.config.to_dict() for d in self._devices.values()]
            data = {
                'devices': configs,
                'folders': self.folder_descriptions
            }
            with open(target_path, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Configuration saved to {target_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def load_configuration(self, path: Optional[str] = None):
        """Loads state from a JSON file."""
        target_path = path or self.config_path
        if not os.path.exists(target_path):
            logger.info(f"No configuration file found at {target_path}")
            return
            
        self.emit("project_cleared")

        try:
            with open(target_path, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                configs = data
                folders = {}
            else:
                configs = data.get('devices', [])
                folders = data.get('folders', {})
            
            self.folder_descriptions.update(folders)
            
            # Signal start of batch load for UI optimization
            self.emit("batch_load_started")
            
            for config_data in configs:
                try:
                    config = DeviceConfig.from_dict(config_data)
                    self.add_device(config, save=False)
                except Exception as e:
                    logger.error(f"Failed to load device config: {e}")
            
            # Signal end of batch load
            self.emit("batch_load_finished")
            self.save_configuration()
            
            logger.info(f"Configuration loaded from {target_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")

    def connect_device(self, device_name: str):
        """Initiates connection and discovery for a device in background."""
        device = self._devices.get(device_name)
        if not device:
            return

        self.emit("connection_progress", device_name, "Preparing connection...", 5)

        if device_name not in self._protocols:
            self.emit("connection_progress", device_name, "Initializing protocol adapter...", 10)
            protocol = self._create_protocol(device.config)
            if not protocol:
                logger.error(f"No protocol handler for type {device.config.device_type}")
                self.emit("connection_progress", device_name, "Error: No protocol handler", 0)
                return
            
            protocol.set_data_callback(lambda sig: self._on_signal_update(device_name, sig))
            self._protocols[device_name] = protocol

        from src.core.workers import ConnectionWorker, IEC61850Worker, ModbusWorker
        
        protocol = self._protocols[device_name]
        
        # Start Connection Worker (for initial connect/discovery)
        worker = ConnectionWorker(device_name, device, protocol)
        
        # Wire up worker events to our event emitter
        worker.on("progress", lambda dn, msg, pct: self.emit("connection_progress", dn, msg, pct))
        worker.on("status_changed", lambda dn, s: self.update_connection_status(dn, s))
        worker.on("device_updated", lambda dn, nn: self._handle_device_update_signal(dn, nn))
        worker.on("finished", lambda: self._on_connection_finished(worker))
        
        # Instantiate dedicated protocol worker for runtime operations
        if device.config.device_type == DeviceType.IEC61850_IED:
            if hasattr(protocol, 'client'): 
                # Create IEC Worker with Subscription Manager
                iec_worker = IEC61850Worker(protocol, device_name, self.subscription_manager)
                # iec_worker.on("data_ready", lambda dn, sig: self.emit("signal_updated", dn, sig))
                iec_worker.on("error", lambda msg: logger.error(f"IEC Worker Error: {msg}"))
                
                t_iec = threading.Thread(target=iec_worker.run, daemon=True)
                t_iec.start()
                
                self.protocol_workers[device_name] = iec_worker

        elif device.config.device_type in [DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER]:
            modbus_worker = ModbusWorker(protocol, device_name)
            t_mb = threading.Thread(target=modbus_worker.run, daemon=True)
            t_mb.start()
            self.protocol_workers[device_name] = modbus_worker

        self._active_workers.append(worker)
        
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

    def _handle_device_update_signal(self, old_name: str, new_name: str):
        if old_name != new_name:
            if new_name not in self._devices:
                device = self._devices.get(old_name)
                if device:
                    device.config.name = new_name
                    self._devices[new_name] = self._devices.pop(old_name)
                    self._protocols[new_name] = self._protocols.pop(old_name)
                    if device.root_node:
                        self._assign_unique_addresses(new_name, device.root_node)

                    self.emit("device_removed", old_name)
                    self.emit("device_added", device)
                    self.emit("connection_progress", new_name, f"Renamed to {new_name}", 95)
                    self.emit("device_updated", new_name)

                    # Notify script manager so running scripts can be restarted if tokens changed
                    try:
                        if self._script_tag_manager and self._script_manager:
                            self._script_manager.restart_scripts_with_token_resolution(self._script_tag_manager)
                    except Exception:
                        logger.exception("Failed to restart scripts after device rename")
            else:
                self.emit("device_updated", new_name)
        else:
            device = self._devices.get(old_name)
            if device and device.root_node:
                self._assign_unique_addresses(old_name, device.root_node)
                try:
                    if self._script_tag_manager and self._script_manager:
                        self._script_manager.restart_scripts_with_token_resolution(self._script_tag_manager)
                except Exception:
                    logger.exception("Failed to restart scripts after device update")
            self.emit("device_updated", old_name)

    def _on_connection_finished(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def _create_protocol(self, config: DeviceConfig) -> Optional[BaseProtocol]:
        """Factory method to instantiate the correct protocol adapter."""
        if config.device_type == DeviceType.IEC61850_IED:
            from src.protocols.iec61850.adapter import IEC61850Adapter
            return IEC61850Adapter(config, event_logger=self.event_logger)
        elif config.device_type == DeviceType.IEC61850_SERVER:
            from src.protocols.iec61850.server_adapter import IEC61850ServerAdapter
            return IEC61850ServerAdapter(config, event_logger=self.event_logger)
        elif config.device_type == DeviceType.IEC104_RTU:
            from src.protocols.iec104.mock_client import IEC104MockClient
            return IEC104MockClient(config)
        elif config.device_type == DeviceType.MODBUS_TCP:
            from src.protocols.modbus.adapter import ModbusTCPAdapter
            return ModbusTCPAdapter(config, event_logger=self.event_logger)
        elif config.device_type == DeviceType.MODBUS_SERVER:
            from src.protocols.modbus.server_adapter import ModbusServerAdapter
            return ModbusServerAdapter(config, event_logger=self.event_logger)
        return None

    def _on_signal_update(self, device_name: str, signal: Signal):
        """Internal callback when a protocol pushes data."""
        if not getattr(signal, 'unique_address', ''):
            signal.unique_address = f"{device_name}::{signal.address}"
        if self.event_logger:
            self.event_logger.debug("DeviceManager", f"Received update for {signal.address} Value={signal.value}")
        self.emit("signal_updated", device_name, signal)

    def update_connection_status(self, device_name: str, connected: bool):
        device = self._devices.get(device_name)
        if device:
            device.connected = connected
            self.emit("device_status_changed", device_name, connected)
            logger.info(f"Device {device_name} connected: {connected}")
            
    def poll_devices(self):
        """
        Periodically called by UpdateEngine.
        Previously used for auto-polling the entire tree. 
        Now DISABLED to optimize performance.
        Polling is now handled by WatchListManager for specific signals only.
        """
        pass
        # for name, device in self._devices.items():
        #     if device.connected and getattr(device.config, 'polling_enabled', False):
        #          pass 

    # _poll_node_recursive removed to prevent accidental usage
    
    def read_signal(self, device_name: str, signal: Signal) -> Optional[Signal]:
        protocol = self._protocols.get(device_name)
        if not protocol:
            # FIX: Return signal synchronously with error if not connected, 
            # so WatchList doesn't hang waiting for async update.
            signal.quality = SignalQuality.NOT_CONNECTED
            signal.error = "Device Disconnected"
            return signal
        
        # If an Protocol worker is available for this device, enqueue to it (non-blocking)
        worker = self.protocol_workers.get(device_name)
        if worker is not None:
            try:
                worker.enqueue({
                    'action': 'read',
                    'signal': signal
                })
                return None
            except Exception as e:
                logger.debug(f"Failed to enqueue read to IEC worker for {device_name}: {e}")

        try:
            updated_signal = protocol.read_signal(signal)

            # Sync connection status if protocol has it
            if hasattr(protocol, 'connected'):
                if protocol.connected != self._devices[device_name].connected:
                    self.update_connection_status(device_name, protocol.connected)

            return updated_signal
        except Exception as e:
            logger.warning(f"Failed to read signal {signal.address} from {device_name}: {e}")
            return None

    def write_signal(self, device_name: str, signal: Signal, value: Any) -> bool:
        protocol = self._protocols.get(device_name)
        if not protocol or not hasattr(protocol, 'write_signal'):
            return False
        try:
            return bool(protocol.write_signal(signal, value))
        except Exception as e:
            logger.warning(f"Failed to write signal {signal.address} to {device_name}: {e}")
            return False

    def parse_unique_address(self, unique_address: str):
        if not unique_address or "::" not in unique_address:
            return None, None
        device_name, address = unique_address.split("::", 1)
        # Strip any uniqueness suffix (e.g., #2)
        if "#" in address:
            address = address.split("#", 1)[0]
        return device_name, address

    def get_signal_by_unique_address(self, unique_address: str) -> Optional[Signal]:
        device_name, address = self.parse_unique_address(unique_address)
        if not device_name or not address:
            return None
        device = self._devices.get(device_name)
        if not device or not device.root_node:
            return None
        return self._find_signal_in_node(device.root_node, address, unique_address)

    def list_unique_addresses(self, device_name: Optional[str] = None):
        addresses = []
        devices = [self._devices.get(device_name)] if device_name else self._devices.values()
        for device in devices:
            if not device or not device.root_node:
                continue
            addresses.extend(self._collect_unique_addresses(device.config.name, device.root_node))
        return addresses

    def start_user_script(self, name: str, code: str, interval: float = 0.5):
        if not self._script_manager:
            from src.core.script_runtime import UserScriptManager
            self._script_manager = UserScriptManager(self, self.event_logger)
        # Persist script so it survives restarts
        try:
            self.save_user_script(name, code, interval)
        except Exception:
            logger.exception("Failed to persist user script on start")
        self._script_manager.start_script(name, code, interval)

    # --- User script persistence ---
    def _scripts_file_path(self):
        try:
            cfg = os.path.abspath(self.config_path)
            folder = os.path.dirname(cfg)
            return os.path.join(folder, 'user_scripts.json')
        except Exception:
            return 'user_scripts.json'

    def _load_user_scripts(self):
        path = self._scripts_file_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            scripts = {}
            for entry in data or []:
                name = entry.get('name')
                code = entry.get('code', '')
                interval = entry.get('interval', 0.5)
                # Update token internals to current canonical values while preserving token wrappers
                try:
                    if self._script_tag_manager:
                        code = self._script_tag_manager.update_tokens(code)
                except Exception:
                    pass
                scripts[name] = {'code': code, 'interval': interval}
            self._saved_scripts = scripts
            # Persist back any updated token internals
            try:
                self._save_user_scripts_file()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to load user scripts file: {e}")

    def _save_user_scripts_file(self):
        path = self._scripts_file_path()
        data = []
        for name, meta in (self._saved_scripts or {}).items():
            data.append({'name': name, 'code': meta.get('code', ''), 'interval': meta.get('interval', 0.5)})
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user scripts file: {e}")

    def save_user_script(self, name: str, code: str, interval: float = 0.5):
        if not name:
            raise ValueError('Script name required')
        self._saved_scripts[name] = {'code': code, 'interval': interval}
        try:
            self._save_user_scripts_file()
        except Exception:
            logger.exception('Failed to persist user script')

    def delete_user_script(self, name: str):
        if name in self._saved_scripts:
            del self._saved_scripts[name]
            try:
                self._save_user_scripts_file()
            except Exception:
                logger.exception('Failed to delete user script from disk')

    def get_saved_scripts(self):
        return dict(self._saved_scripts)

    def run_user_script_once(self, code: str):
        from src.core.script_runtime import run_script_once
        run_script_once(code, self, self.event_logger)

    def stop_user_script(self, name: str):
        if self._script_manager:
            self._script_manager.stop_script(name)

    def stop_all_user_scripts(self):
        if self._script_manager:
            self._script_manager.stop_all()

    def list_user_scripts(self):
        if not self._script_manager:
            return []
        return self._script_manager.list_scripts()

    def _assign_unique_addresses(self, device_name: str, node: Optional[Node]):
        if not node:
            return
        seen = {}

        def _walk(n: Node):
            for sig in getattr(n, 'signals', []) or []:
                base = f"{device_name}::{sig.address}"
                count = seen.get(base, 0) + 1
                seen[base] = count
                sig.unique_address = f"{base}#{count}" if count > 1 else base
            for child in getattr(n, 'children', []) or []:
                _walk(child)

        _walk(node)

    def _collect_unique_addresses(self, device_name: str, node: Node):
        collected = []
        if hasattr(node, 'signals') and node.signals:
            for sig in node.signals:
                if getattr(sig, 'unique_address', ''):
                    collected.append(sig.unique_address)
                else:
                    collected.append(f"{device_name}::{sig.address}")
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                collected.extend(self._collect_unique_addresses(device_name, child))
        return collected

    def _find_signal_in_node(self, node: Node, address: str, unique_address: Optional[str] = None) -> Optional[Signal]:
        if hasattr(node, 'signals') and node.signals:
            for sig in node.signals:
                if unique_address and getattr(sig, 'unique_address', None) == unique_address:
                    return sig
                if sig.address == address:
                    return sig
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                found = self._find_signal_in_node(child, address, unique_address)
                if found:
                    return found
        return None

    def send_control_command(self, device_name: str, signal: Signal, command: str, value: Any):
        if device_name not in self._protocols:
             # Basic fuzzy logic removed for cleaner core, strict matching preferred
             # But keeping the loop fallback just in case for now to match old behavior
             pass

        protocol = self._protocols.get(device_name)
        if not protocol:
             # Fallback
            for name, proto in self._protocols.items():
                try:
                    if command == 'SELECT':
                        proto.select(signal)
                    elif command == 'OPERATE':
                        proto.operate(signal, value)
                    elif command == 'CANCEL':
                        proto.cancel(signal)
                    elif command == 'SEND_COMMAND':
                        proto.send_command(signal, value)
                except Exception:
                    pass
            return

        if command == 'SELECT':
            protocol.select(signal)
        elif command == 'OPERATE':
            protocol.operate(signal, value)
        elif command == 'CANCEL':
            protocol.cancel(signal)
        elif command == 'SEND_COMMAND':
            # New automatic SBO workflow
            protocol.send_command(signal, value)
            
    def is_controllable(self, device_name: str, signal: Signal) -> bool:
        if "ctlVal" not in signal.address:
            return False

        protocol = self._protocols.get(device_name)
        if not protocol:
            return False
            
        if hasattr(protocol, 'check_control_model'):
             return protocol.check_control_model(signal.address)
             
        return True 
