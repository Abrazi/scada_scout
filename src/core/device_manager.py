from typing import List, Dict, Optional, Any
import logging
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

    def __init__(self):
        super().__init__()
        self._devices: Dict[str, Device] = {}
        self._protocols: Dict[str, BaseProtocol] = {}
        self.event_logger = None  # Will be set by AppController

    def add_device(self, config: DeviceConfig) -> Device:
        """Creates a new device from config and registers it."""
        if config.name in self._devices:
            raise ValueError(f"Device with name {config.name} already exists.")
        
        device = Device(config=config)
        self._devices[config.name] = device
        
        # Instantiate protocol adapter
        protocol = self._create_protocol(config)
        if protocol:
            self._protocols[config.name] = protocol
            
        logger.info(f"Device added: {config.name} ({config.device_type.value})")
        self.device_added.emit(device)
        return device

    def remove_device(self, device_name: str):
        """Removes a device and cleans up its connection."""
        if device_name in self._protocols:
            protocol = self._protocols[device_name]
            if protocol.connected:
                protocol.disconnect()
            del self._protocols[device_name]
            
        if device_name in self._devices:
            del self._devices[device_name]
            self.device_removed.emit(device_name)
            if self.event_logger:
                self.event_logger.info("DeviceManager", f"Removed device: {device_name}")

    def update_device(self, old_name: str, new_config: DeviceConfig):
        """Updates a device configuration."""
        self.remove_device(old_name)
        self.add_device(new_config)

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

    def remove_device(self, device_name: str):
        """Removes a device from the manager."""
        if device_name in self._devices:
            # Ensure disconnected first
            self.disconnect_device(device_name)
            del self._devices[device_name]
            logger.info(f"Device removed: {device_name}")
            self.device_removed.emit(device_name)

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
             except:
                 pass
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

    def get_all_devices(self) -> List[Device]:
        return list(self._devices.values())

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
        return None

    def _on_signal_update(self, device_name: str, signal: Signal):
        """Internal callback when a protocol pushes data."""
        # Forward to UI
        self.signal_updated.emit(device_name, signal)

    def update_connection_status(self, device_name: str, connected: bool):
        """Updates the connection state of a device."""
        device = self._devices.get(device_name)
        if device:
            device.connected = connected
            self.device_status_changed.emit(device_name, connected)
            logger.info(f"Device {device_name} connected: {connected}")
    
    def read_signal(self, device_name: str, signal: Signal) -> Optional[Signal]:
        """Read a single signal value from a device."""
        protocol = self._protocols.get(device_name)
        if not protocol:
            logger.warning(f"No protocol found for device {device_name}")
            return None
        
        try:
            updated_signal = protocol.read_signal(signal)
            return updated_signal
        except Exception as e:
            logger.debug(f"Failed to read signal {signal.address} from {device_name}: {e}")
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
                except:
                    pass
            return

        # If we have specific device
        if command == 'SELECT':
            protocol.select(signal)
        elif command == 'OPERATE':
            protocol.operate(signal, value)
        elif command == 'CANCEL':
            protocol.cancel(signal)
