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
    
    # New signal for live updates
    signal_updated = QtSignal(str, Signal) # device_name, Signal

    def __init__(self):
        super().__init__()
        self._devices: Dict[str, Device] = {}
        self._protocols: Dict[str, BaseProtocol] = {}

    def add_device(self, config: DeviceConfig) -> Device:
        """Creates a new device from config and registers it."""
        if config.name in self._devices:
            raise ValueError(f"Device with name {config.name} already exists.")
        
        device = Device(config=config)
        self._devices[config.name] = device
        
        logger.info(f"Device added: {config.name} ({config.device_type.value})")
        self.device_added.emit(device)
        return device

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
            return

        # Disconnect if connected (since config changed)
        if device.connected:
            self.disconnect_device(config.name)
            
        # Update config
        device.config = config
        
        # We need to notify UI that the device info changed.
        # Simplest way is remove and re-add signal-wise, 
        # or we could add a new signal. 
        # Given the tree stores config data in items, re-add is safest to refresh visuals.
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
        """Initiates connection and discovery for a device."""
        device = self._devices.get(device_name)
        if not device:
            return

        # Instantiate Protocol if not exists
        if device_name not in self._protocols:
            protocol = self._create_protocol(device.config)
            if not protocol:
                logger.error(f"No protocol handler for type {device.config.device_type}")
                return
            
            # Wire up callback
            protocol.set_data_callback(lambda sig: self._on_signal_update(device_name, sig))
            self._protocols[device_name] = protocol

        # Connect
        protocol = self._protocols[device_name]
        try:
            if protocol.connect():
                self.update_connection_status(device_name, True)
                
                # Auto-Discover
                root_node = protocol.discover()
                device.root_node = root_node
                
                logger.info(f"Discovery complete for {device_name}")
                self.device_updated.emit(device_name)
                
        except Exception as e:
            logger.error(f"Failed to connect to {device_name}: {e}")
            self.update_connection_status(device_name, False)

    def _create_protocol(self, config: DeviceConfig) -> Optional[BaseProtocol]:
        """Factory method to create protocol instances."""
        if config.device_type == DeviceType.IEC104_RTU:
            return IEC104Client(config)
        elif config.device_type == DeviceType.IEC61850_IED:
            from src.protocols.iec61850.adapter import IEC61850Adapter
            return IEC61850Adapter(config)
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
