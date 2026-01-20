from typing import List, Dict, Optional, Any
import logging
from PySide6.QtCore import QObject, Signal as QtSignal

from src.models.device_models import Device, DeviceConfig, Signal
from src.core.device_manager_core import DeviceManagerCore

logger = logging.getLogger(__name__)

class DeviceManager(QObject):
    """
    Qt Adapter for DeviceManagerCore.
    Exposes Qt Signals and Slots for the UI while delegating logic to the Core.
    """
    # Signals to notify UI of changes (matching original interface)
    device_added = QtSignal(Device)
    device_removed = QtSignal(str) 
    device_status_changed = QtSignal(str, bool) 
    device_updated = QtSignal(str) 
    device_renamed = QtSignal(str, str)
    connection_progress = QtSignal(str, str, int) 
    signal_updated = QtSignal(str, Signal) 
    project_cleared = QtSignal()
    batch_load_started = QtSignal()
    batch_load_finished = QtSignal()
    batch_clear_started = QtSignal()

    def __init__(self, config_path="devices.json"):
        super().__init__()
        self._core = DeviceManagerCore(config_path)
        
        # Bridge Core Events to Qt Signals
        self._core.on("device_added", self.device_added.emit)
        self._core.on("device_removed", self.device_removed.emit)
        self._core.on("device_status_changed", self.device_status_changed.emit)
        self._core.on("device_updated", self.device_updated.emit)
        # Optional rename event emitted by core with (old_name, new_name)
        try:
            self._core.on("device_renamed", self.device_renamed.emit)
        except Exception:
            pass
        self._core.on("connection_progress", self.connection_progress.emit)
        self._core.on("signal_updated", self.signal_updated.emit)
        self._core.on("project_cleared", self.project_cleared.emit)
        self._core.on("batch_load_started", self.batch_load_started.emit)
        self._core.on("batch_load_finished", self.batch_load_finished.emit)
        self._core.on("batch_clear_started", self.batch_clear_started.emit)

    @property
    def event_logger(self):
        return self._core.event_logger
    
    @event_logger.setter
    def event_logger(self, value):
        self._core.event_logger = value

    @property
    def config_path(self):
        return self._core.config_path
        
    @config_path.setter
    def config_path(self, value):
        self._core.config_path = value

    @property
    def subscription_manager(self):
        return self._core.subscription_manager

    # Delegate methods to Core
    def add_device(self, config: DeviceConfig):
        return self._core.add_device(config)

    def remove_device(self, device_name: str):
        return self._core.remove_device(device_name)

    def set_discovery_mode(self, device_name: str, use_scd: bool):
        return self._core.set_discovery_mode(device_name, use_scd)

    def update_device_config(self, config: DeviceConfig):
        return self._core.update_device_config(config)

    def disconnect_device(self, device_name: str):
        return self._core.disconnect_device(device_name)

    def get_device(self, device_name: str) -> Optional[Device]:
        return self._core.get_device(device_name)

    def get_protocol(self, device_name: str):
        """Get the protocol adapter for a device."""
        return self._core.get_protocol(device_name)

    def load_offline_scd(self, device_name: str):
        return self._core.load_offline_scd(device_name)

    def get_all_devices(self) -> List[Device]:
        return self._core.get_all_devices()

    def clear_all_devices(self):
        return self._core.clear_all_devices()

    def save_configuration(self, path: Optional[str] = None):
        return self._core.save_configuration(path)

    def load_configuration(self, path: Optional[str] = None):
        return self._core.load_configuration(path)

    def connect_device(self, device_name: str):
        return self._core.connect_device(device_name)

    def poll_devices(self):
        return self._core.poll_devices()

    def read_signal(self, device_name: str, signal: Signal) -> Optional[Signal]:
        return self._core.read_signal(device_name, signal)

    def write_signal(self, device_name: str, signal: Signal, value: Any) -> bool:
        return self._core.write_signal(device_name, signal, value)

    def send_control_command(self, device_name: str, signal: Signal, command: str, value: Any):
        return self._core.send_control_command(device_name, signal, command, value)

    def is_controllable(self, device_name: str, signal: Signal) -> bool:
        return self._core.is_controllable(device_name, signal)

    def start_user_script(self, name: str, code: str, interval: float = 0.5):
        return self._core.start_user_script(name, code, interval)

    def run_user_script_once(self, code: str):
        return self._core.run_user_script_once(code)

    def stop_user_script(self, name: str):
        return self._core.stop_user_script(name)

    def stop_all_user_scripts(self):
        return self._core.stop_all_user_scripts()

    def list_user_scripts(self):
        return self._core.list_user_scripts()

    def save_user_script(self, name: str, code: str, interval: float = 0.5):
        return self._core.save_user_script(name, code, interval)

    def delete_user_script(self, name: str):
        return self._core.delete_user_script(name)

    def get_saved_scripts(self):
        return self._core.get_saved_scripts()

    def resolve_script_tokens(self, code: str) -> str:
        """Resolve token placeholders in user script code to current unique addresses."""
        if not code:
            return code
        mgr = getattr(self._core, '_script_tag_manager', None)
        if mgr:
            try:
                return mgr.resolve_code(code)
            except Exception:
                return code
        return code

    def resolve_script_tokens_interactive(self, code: str, chooser) -> str:
        """Resolve tokens interactively using a `chooser(token, candidates)` callback for ambiguities.

        `chooser` should accept `(token_str, candidates_list)` and return the selected candidate string or None.
        """
        if not code:
            return code
        mgr = getattr(self._core, '_script_tag_manager', None)
        if mgr and hasattr(mgr, 'resolve_code_interactive'):
            try:
                return mgr.resolve_code_interactive(code, chooser)
            except Exception:
                return code
        return code

    def make_tag_token(self, unique_address: str) -> str:
        mgr = getattr(self._core, '_script_tag_manager', None)
        if mgr:
            try:
                return mgr.make_token(unique_address)
            except Exception:
                pass
        return f"{{{{TAG:{unique_address}}}}}"

    def get_signal_by_unique_address(self, unique_address: str) -> Optional[Signal]:
        return self._core.get_signal_by_unique_address(unique_address)

    def list_unique_addresses(self, device_name: Optional[str] = None):
        return self._core.list_unique_addresses(device_name)

    # For existing UI compatibility - in case any code accessed _devices directly
    # (Though they shouldn't have)
    @property
    def _devices(self):
        return self._core._devices
