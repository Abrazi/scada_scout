from typing import List, Dict, Optional, Any
import logging
import json
import os
from PySide6.QtCore import QObject, Signal as QtSignal

from src.models.device_models import Device, DeviceConfig, DeviceType, Node, Signal
from src.protocols.base_protocol import BaseProtocol
from src.protocols.iec104.client import IEC104Client

logger = logging.getLogger(__name__)

class DeviceManager(QObject):
    """
    Manages the lifecycle of devices.
    Maintains the list of configured devices and their runtime state.
    """
    # Signals to notify UI of changes
    device_added = QtSignal(Device)
    device_removed = QtSignal(str)  # device_name
    device_status_changed = QtSignal(str, bool)  # device_name, connected_state
    device_updated = QtSignal(str) # device_name, model changed (discovery complete)
    connection_progress = QtSignal(str, str, int)  # device_name, message, percent
    
    # New signal for live updates
    signal_updated = QtSignal(str, Signal) # device_name, Signal
    project_cleared = QtSignal() # Emitted when all devices are removed/project loaded

    def __init__(self, config_path="devices.json"):
        super().__init__()
        self._devices: Dict[str, Device] = {}
        self._protocols: Dict[str, BaseProtocol] = {}
        self.event_logger = None  # Will be set by AppController
        # per-device IEC worker mapping (set by AppController)
        self.iec_workers: Dict[str, object] = {}
        self.config_path = config_path
        self.folder_descriptions: Dict[str, str] = {} # folder_name -> description

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
        self.device_added.emit(device)
        self.save_configuration()
        
        # Try to populate tree immediately (Offline Discovery)
        # This handles Modbus maps/blocks and SCD files
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

            # Cleanup any IEC worker assigned to this device
            if hasattr(self, 'iec_workers') and device_name in self.iec_workers:
                try:
                    wk = self.iec_workers.pop(device_name)
                    # Attempt to stop worker if it exposes stop()
                    try:
                        wk.stop()
                    except Exception:
                        pass
                except Exception:
                    pass

            logger.info(f"Device removed: {device_name}")
            self.device_removed.emit(device_name)
            self.save_configuration()
            

    def set_discovery_mode(self, device_name: str, use_scd: bool):
        """Switches between SCD and Online discovery for a device."""
        if device_name not in self._devices: # Changed from self.devices to self._devices
            return
            
        device = self._devices[device_name] # Changed from self.devices to self._devices
        device.config.use_scd_discovery = use_scd
        logger.info(f"Set discovery mode for {device_name} to {'SCD' if use_scd else 'Online'}")
        
        # Trigger re-discovery
        # If connected, we might want to stay connected but refresh tree?
        # Or disconnect first to be safe?
        # Let's simple reconnect.
        if device.connected:
            self.disconnect_device(device_name)
            self.connect_device(device_name)
        else:
            # Just refresh tree? 
            # If not connected, we can't do online discovery easily without connecting.
            # But if switching TO SCD, we can do it offline.
            if use_scd and device.config.scd_file_path:
                 # Manually trigger load
                 try:
                     # Assuming device.discover() is a method that returns a root node
                     root = device.discover() 
                     # self.device_roots does not exist, root_node is stored in device
                     device.root_node = root 
                     # Signal expects only device_name
                     self.device_updated.emit(device_name) 
                 except Exception as e:
                     logger.error(f"Failed to load SCD: {e}")
        # Trigger refresh
        self.update_device_config(device.config)
        self.save_configuration()

    def update_device_config(self, config: DeviceConfig):
        """Updates the configuration of an existing device."""
        device = self._devices.get(config.name)
        if not device:
            # If name changed, we might need to handle lookup differently
            # But currently UI passes original name.
            return

        # 1. Disconnect if connected
        if device.connected:
            self.disconnect_device(config.name)
        
        # 2. Force remove protocol instance if it exists (even if not connected)
        # This ensures the next connect() creates a fresh adapter with new config
        if config.name in self._protocols:
             try:
                 self._protocols[config.name].disconnect() # Safe to call
             except Exception as e:
                 logger.debug(f"Error disconnecting {config.name} during reconfigure: {e}")
             del self._protocols[config.name]
            
        # 3. Update config
        device.config = config
        
        # We need to notify UI that the device info changed.
        self.device_removed.emit(config.name)
        self.device_added.emit(device)

    def disconnect_device(self, device_name: str):
        """Disconnects a device."""
        if device_name in self._protocols:
            try:
                self._protocols[device_name].disconnect()
                del self._protocols[device_name] # Remove protocol instance
            except Exception as e:
                logger.error(f"Error disconnecting {device_name}: {e}")
        
        self.update_connection_status(device_name, False)

    def get_device(self, device_name: str) -> Optional[Device]:
        return self._devices.get(device_name)

    def load_offline_scd(self, device_name: str):
        """
        Triggers offline discovery from SCD file without connecting.
        Useful for populating the tree immediately after import.
        """
        device = self._devices.get(device_name)
        if not device:
            return
        
        # Require either SCD path OR it's a Modbus device with maps or blocks
        is_modbus = device.config.device_type in [DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER]
        has_maps = (len(device.config.modbus_register_maps) > 0 or 
                    len(device.config.modbus_slave_mappings) > 0 or
                    len(device.config.modbus_slave_blocks) > 0)
        
        if not device.config.scd_file_path and not (is_modbus and has_maps):
            return

        # We need a protocol adapter to run discovery logic (it has the parser logic)
        # Even if not connected, we can instantiate it.
        if device_name not in self._protocols:
             protocol = self._create_protocol(device.config)
             if protocol:
                 self._protocols[device_name] = protocol
        
        protocol = self._protocols.get(device_name)
        if protocol and hasattr(protocol, 'discover'):
            try:
                # Force SCD usage just in case? config.use_scd_discovery should be true from import
                root = protocol.discover()
                device.root_node = root
                self.device_updated.emit(device_name)
                logger.info(f"Offline SCD loaded for {device_name}")
            except Exception as e:
                logger.error(f"Failed to load offline SCD for {device_name}: {e}")

    def get_all_devices(self) -> List[Device]:
        return list(self._devices.values())

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
            
        self.project_cleared.emit() # Clear UI before loading new ones

        try:
            with open(target_path, 'r') as f:
                data = json.load(f)
            
            # Handle both old format (list of configs) and new format (dict)
            if isinstance(data, list):
                configs = data
                folders = {}
            else:
                configs = data.get('devices', [])
                folders = data.get('folders', {})
            
            # Apply folder metadata first
            self.folder_descriptions.update(folders)
            
            for config_data in configs:
                try:
                    config = DeviceConfig.from_dict(config_data)
                    self.add_device(config)
                    # Try to populate tree immediately
                    self.load_offline_scd(config.name)
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

        # Emit initial progress
        self.connection_progress.emit(device_name, "Preparing connection...", 5)

        # Instantiate Protocol if not exists (in main thread for safety)
        if device_name not in self._protocols:
            self.connection_progress.emit(device_name, "Initializing protocol adapter...", 10)
            protocol = self._create_protocol(device.config)
            if not protocol:
                logger.error(f"No protocol handler for type {device.config.device_type}")
                self.connection_progress.emit(device_name, "Error: No protocol handler", 0)
                return
            
            # Wire up callback
            protocol.set_data_callback(lambda sig: self._on_signal_update(device_name, sig))
            self._protocols[device_name] = protocol

        # Start background worker
        from src.core.workers import ConnectionWorker
        
        protocol = self._protocols[device_name]
        
        worker = ConnectionWorker(device_name, device, protocol)
        worker.signals.progress.connect(self.connection_progress)
        worker.signals.status_changed.connect(self.update_connection_status)
        worker.signals.device_updated.connect(self._handle_device_update_signal) 
        worker.signals.finished.connect(lambda: self._on_connection_finished(worker))
        
        # Keep reference to avoid GC
        if not hasattr(self, '_active_workers'):
            self._active_workers = []
        self._active_workers.append(worker)
        
        # Start
        import threading
        t = threading.Thread(target=worker.run)
        t.daemon = True
        t.start()

    def _handle_device_update_signal(self, old_name: str, new_name: str):
        """Called by worker to update device name if discovered."""
        if old_name != new_name:
            if new_name not in self._devices:
                 # Perform rename logic
                 device = self._devices.get(old_name)
                 if device:
                     device.config.name = new_name
                     self._devices[new_name] = self._devices.pop(old_name)
                     self._protocols[new_name] = self._protocols.pop(old_name)
                     
                     self.device_removed.emit(old_name)
                     self.device_added.emit(device)
                     self.connection_progress.emit(new_name, f"Renamed to {new_name}", 95)
                     self.device_updated.emit(new_name)
            else:
                self.device_updated.emit(new_name)
        else:
             self.device_updated.emit(old_name)

    def get_or_create_protocol(self, device_name: str) -> Optional[BaseProtocol]:
        """Ensures a protocol adapter exists for the device and returns it."""
        device = self._devices.get(device_name)
        if not device:
            return None
        
        if device_name not in self._protocols:
            protocol = self._create_protocol(device.config)
            if protocol:
                # Wire up callback
                protocol.set_data_callback(lambda sig: self._on_signal_update(device_name, sig))
                self._protocols[device_name] = protocol
        
        return self._protocols.get(device_name)

    def _on_connection_finished(self, worker):
        if hasattr(self, '_active_workers') and worker in self._active_workers:
            self._active_workers.remove(worker)

    def _create_protocol(self, config: DeviceConfig) -> Optional[BaseProtocol]:
        """Factory method to instantiate the correct protocol adapter."""
        if config.device_type == DeviceType.IEC61850_IED:
            from src.protocols.iec61850.adapter import IEC61850Adapter
            # Pass event logger if available
            event_logger = getattr(self, 'event_logger', None)
            return IEC61850Adapter(config, event_logger=event_logger)
        elif config.device_type == DeviceType.IEC104_RTU:
            from src.protocols.iec104.mock_client import IEC104MockClient
            return IEC104MockClient(config)
        elif config.device_type == DeviceType.MODBUS_TCP:
            from src.protocols.modbus.adapter import ModbusTCPAdapter
            event_logger = getattr(self, 'event_logger', None)
            return ModbusTCPAdapter(config, event_logger=event_logger)
        elif config.device_type == DeviceType.MODBUS_SERVER:
            from src.protocols.modbus.server_adapter import ModbusServerAdapter
            event_logger = getattr(self, 'event_logger', None)
            return ModbusServerAdapter(config, event_logger=event_logger)
        return None

    def _on_signal_update(self, device_name: str, signal: Signal):
        """Internal callback when a protocol pushes data."""
        # Forward to UI
        if self.event_logger:
            self.event_logger.debug("DeviceManager", f"Received update for {signal.address} Value={signal.value}")
        self.signal_updated.emit(device_name, signal)

    def update_connection_status(self, device_name: str, connected: bool):
        """Updates the connection state of a device."""
        device = self._devices.get(device_name)
        if device:
            device.connected = connected
            self.device_status_changed.emit(device_name, connected)
            logger.info(f"Device {device_name} connected: {connected}")
            
    def poll_devices(self):
        """Polls signals for all devices with polling enabled.
        
        Note: Auto-polling is disabled by default. Only watch-list items or
        explicit refresh calls will trigger reads. Devices should populate
        their tree on connection but not auto-read all signals.
        """
        import time
        now = time.time()
        
        # Auto-polling disabled - only watch list reads are allowed
        # To enable per-device polling, set device.config.polling_enabled = True
        # and override this method or call _poll_node_recursive explicitly
        
        for name, device in self._devices.items():
            # Skip automatic polling; polling now only happens on watch list or manual refresh
            if device.connected and getattr(device.config, 'polling_enabled', False):
                # This is only reached if explicitly enabled
                last_poll = getattr(device, '_last_poll_time', 0)
                if now - last_poll >= device.config.poll_interval:
                    device._last_poll_time = now
                    # For now, we poll all signals in the device tree
                    if device.root_node:
                        self._poll_node_recursive(name, device.root_node)

    def _poll_node_recursive(self, device_name: str, node: Node):
        """Recursively poll signals in a node."""
        for sig in node.signals:
            # We only poll read or read-write signals
            if sig.access in ["RO", "RW"]:
                self.read_signal(device_name, sig)
                # read_signal triggers protocol.read_signal, which calls _emit_update,
                # which calls our _on_signal_update, which emits signal_updated.
                # So we NO LONGER need to emit manually here to avoid double-events.
                
        for child in node.children:
            self._poll_node_recursive(device_name, child)
    
    def read_signal(self, device_name: str, signal: Signal) -> Optional[Signal]:
        """Read a single signal value from a device."""
        protocol = self._protocols.get(device_name)
        if not protocol:
            logger.warning(f"No protocol found for device {device_name}")
            if self.event_logger:
                self.event_logger.error("DeviceManager", f"Read failed: No protocol for {device_name}")
            return None
        
        if self.event_logger:
            self.event_logger.debug("DeviceManager", f"Delegating read for {signal.address} to protocol")
        
        # If an IEC worker is available for this device, enqueue to it (non-blocking)
        try:
            worker = self.iec_workers.get(device_name)
        except Exception:
            worker = None

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
            # If an exception happened in the protocol, consider it disconnected if it's a connection error
            return None

    def send_control_command(self, device_name: str, signal: Signal, command: str, value: Any):
        """Delegates control command to the appropriate protocol."""
        # Find protocol
        if device_name not in self._protocols:
             # Try to find if the signal belongs to a known device if device_name is vague?
             # For now, we rely on exact name.
             # But the UI sends execution blindly.
             # Let's try to match signal to device if device_name is invalid context.
             pass
        
        protocol = self._protocols.get(device_name)
        if not protocol:
            # Fallback search: check which protocol has this signal?
            # Too complex.
            # Let's just try to assume the signal name contains the device name 
            # OR iterate all protocols and try calling 'operate' if they support it?
            
            # Robust: Iterate
            for name, proto in self._protocols.items():
                # We can't strictly know ownership, but we can try.
                # IEC 61850 adapter's mock operate returns true.
                try:
                    if command == 'SELECT':
                        proto.select(signal)
                    elif command == 'OPERATE':
                        proto.operate(signal, value)
                    elif command == 'CANCEL':
                        proto.cancel(signal)
                except Exception as e:
                    logger.error(f"Error sending control command: {e}")
            return

        if command == 'SELECT':
            protocol.select(signal)
        elif command == 'OPERATE':
            protocol.operate(signal, value)
        elif command == 'CANCEL':
            protocol.cancel(signal)

    def is_controllable(self, device_name: str, signal: Signal) -> bool:
        """
        Determines if a Data Attribute is controllable based on IEC 61850 rules.
        Checks ctlModel behavior.
        """
        # 1. Name check
        if "ctlVal" not in signal.address:
            return False

        # 2. Find ctlModel via adapter
        protocol = self._protocols.get(device_name)
        if not protocol:
            return False
            
        # Construct path to ctlModel (sibling of ctlVal)
        # e.g. Device/LN.Pos.Oper.ctlVal -> Device/LN.Pos.Oper.ctlModel ??
        # Or usually Device/LN.Pos.ctlModel is at CF level? 
        # Actually ctlModel is usually a CF (Configuration) attribute of the control object.
        # It's usually at the same level as Oper/SBOw? 
        # Let's look for sibling 'ctlModel'.
        
        base_path = signal.address.rsplit('.', 1)[0] # Strip .ctlVal
        # If path is ...Oper.ctlVal, parent is Oper. ctlModel is inside Oper?
        # No, ctlModel is usually in the Logical Node or the DO.
        # Standard: DO contains ctlModel.
        # If signal is ...DO.Oper.ctlVal -> ctlModel is at ...DO.ctlModel
        
        # Heuristic: Try to read ctlModel at the DO level.
        # We need to guess the DO path.
        # If address is 'IED/LN.Pos.Oper.ctlVal', DO is 'IED/LN.Pos'.
        
        # User logic: "ln = da.parent.parent" implies: ctlVal -> Oper -> DO ?
        # So we go up 2 levels.
        parts = signal.address.split('.')
        if len(parts) >= 2:
             # Try finding ctlModel at varying levels up
             # This requires reading the model or having it cached.
             # Adapter's 'discover' populates simple model.
             pass
             
        # For robustness, we delegating to the adapter to read/check it.
        if hasattr(protocol, 'check_control_model'):
             return protocol.check_control_model(signal.address)
             
        return True # Fallback if we can't check

