import logging
import json
import os
import threading
from typing import List, Dict, Optional, Any

from src.core.events import EventEmitter
from src.models.device_models import Device, DeviceConfig, DeviceType, Node, Signal
from src.protocols.base_protocol import BaseProtocol

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

    def add_device(self, config: DeviceConfig):
        """Creates a new device from config and registers it."""
        if config.name in self._devices:
            logger.warning(f"Device '{config.name}' already exists.")
            return
        
        device = Device(config=config)
        self._devices[config.name] = device
        
        # Instantiate protocol adapter
        protocol = self._create_protocol(config)
        if protocol:
            self._protocols[config.name] = protocol
            
        logger.info(f"Device added: {config.name} ({config.device_type.value})")
        self.emit("device_added", device)
        self.save_configuration()
        
        # Try to populate tree immediately (Offline Discovery)
        self.load_offline_scd(config.name)
        
        return device

    def remove_device(self, device_name: str):
        """Removes a device and cleans up its connection."""
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
            self.save_configuration()

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
                 self._protocols[device_name] = protocol
        
        protocol = self._protocols.get(device_name)
        if protocol and hasattr(protocol, 'discover'):
            try:
                root = protocol.discover()
                device.root_node = root
                self.emit("device_updated", device_name)
                logger.info(f"Offline SCD loaded for {device_name}")
            except Exception as e:
                logger.error(f"Failed to load offline SCD for {device_name}: {e}")

    def get_all_devices(self) -> List[Device]:
        return list(self._devices.values())

    def clear_all_devices(self):
        """Remove all devices and cleanup protocols and workers."""
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
            
            for config_data in configs:
                try:
                    config = DeviceConfig.from_dict(config_data)
                    self.add_device(config)
                except Exception as e:
                    logger.error(f"Failed to load device config: {e}")
            
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
                iec_worker = IEC61850Worker(protocol, device_name)
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
                     
                     self.emit("device_removed", old_name)
                     self.emit("device_added", device)
                     self.emit("connection_progress", new_name, f"Renamed to {new_name}", 95)
                     self.emit("device_updated", new_name)
            else:
                self.emit("device_updated", new_name)
        else:
             self.emit("device_updated", old_name)

    def _on_connection_finished(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def _create_protocol(self, config: DeviceConfig) -> Optional[BaseProtocol]:
        """Factory method to instantiate the correct protocol adapter."""
        if config.device_type == DeviceType.IEC61850_IED:
            from src.protocols.iec61850.adapter import IEC61850Adapter
            return IEC61850Adapter(config, event_logger=self.event_logger)
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
            logger.warning(f"No protocol found for device {device_name}")
            return None
        
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
                except Exception:
                    pass
            return

        if command == 'SELECT':
            protocol.select(signal)
        elif command == 'OPERATE':
            protocol.operate(signal, value)
        elif command == 'CANCEL':
            protocol.cancel(signal)
            
    def is_controllable(self, device_name: str, signal: Signal) -> bool:
        if "ctlVal" not in signal.address:
            return False

        protocol = self._protocols.get(device_name)
        if not protocol:
            return False
            
        if hasattr(protocol, 'check_control_model'):
             return protocol.check_control_model(signal.address)
             
        return True 
