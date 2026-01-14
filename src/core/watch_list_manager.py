import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json
from PySide6.QtCore import QObject, Signal as QtSignal, QTimer
from src.models.device_models import Signal

logger = logging.getLogger(__name__)

@dataclass
class WatchedSignal:
    """Wrapper for a signal in the watch list"""
    device_name: str
    signal: Signal
    watch_id: str  # Unique ID: device_name + signal.address
    
    def to_dict(self):
        return {
            'device_name': self.device_name,
            'signal_name': self.signal.name,
            'signal_address': self.signal.address,
            'signal_type': self.signal.signal_type.value,
            'watch_id': self.watch_id
        }
    
class WatchListManager(QObject):
    """
    Manages a list of signals to monitor with periodic polling.
    """
    # Signals
    signal_updated = QtSignal(str, Signal)  # watch_id, updated_signal
    watch_list_changed = QtSignal()  # Emitted when list is modified
    
    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
        self._watched_signals: Dict[str, WatchedSignal] = {}
        self._poll_interval_ms = 1000  # Default 1 second
        
        # Polling timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_all_signals)
        
        # Connect to DeviceManager updates
        if hasattr(self.device_manager, 'signal_updated'):
             self.device_manager.signal_updated.connect(self._on_device_signal_updated)
        
    def add_signal(self, device_name: str, signal: Signal):
        """Add a signal to the watch list."""
        watch_id = f"{device_name}::{signal.address}"
        
        if watch_id in self._watched_signals:
            logger.warning(f"Signal {watch_id} already in watch list")
            return
        
        watched = WatchedSignal(
            device_name=device_name,
            signal=signal,
            watch_id=watch_id
        )
        
        self._watched_signals[watch_id] = watched
        logger.info(f"Added signal to watch list: {watch_id}")
        self.watch_list_changed.emit()
        
        # Start polling if not already running
        if not self._poll_timer.isActive():
            self._poll_timer.start(self._poll_interval_ms)
        
        # Trigger immediate poll for this signal
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._poll_all_signals)
    
    def remove_signal(self, watch_id: str):
        """Remove a signal from the watch list."""
        if watch_id in self._watched_signals:
            del self._watched_signals[watch_id]
            logger.info(f"Removed signal from watch list: {watch_id}")
            self.watch_list_changed.emit()
            
            # Stop polling if list is empty
            if not self._watched_signals:
                self._poll_timer.stop()
    
    def clear_all(self):
        """Remove all signals from watch list."""
        self._watched_signals.clear()
        self._poll_timer.stop()
        logger.info("Cleared watch list")
        self.watch_list_changed.emit()
    
    def get_all_watched(self) -> List[WatchedSignal]:
        """Get all watched signals."""
        return list(self._watched_signals.values())
    
    def set_poll_interval(self, interval_ms: int):
        """Set the polling interval in milliseconds."""
        self._poll_interval_ms = max(100, interval_ms)  # Minimum 100ms
        
        if self._poll_timer.isActive():
            self._poll_timer.stop()
            self._poll_timer.start(self._poll_interval_ms)
        
        logger.info(f"Poll interval set to {self._poll_interval_ms}ms")
    
    def get_poll_interval(self) -> int:
        """Get current poll interval."""
        return self._poll_interval_ms
    
    def _poll_all_signals(self):
        """Poll all watched signals for updates."""
        for watch_id, watched in self._watched_signals.items():
            try:
                # Read signal from device
                updated_signal = self.device_manager.read_signal(
                    watched.device_name, 
                    watched.signal
                )
                
                if updated_signal:
                    # Sync Result (from cache or blocking read)
                    watched.signal = updated_signal
                    self.signal_updated.emit(watch_id, updated_signal)
                else:
                    # Async read enqueued - DO NOT invalidate signal yet.
                    # Wait for _on_device_signal_updated to handle the result
                    pass
                    
            except Exception as e:
                logger.debug(f"Failed to poll {watch_id}: {e}")

    def _on_device_signal_updated(self, device_name: str, signal: Signal):
        """Handle signal updates from DeviceManager (e.g. from async workers)."""
        watch_id = f"{device_name}::{signal.address}"
        if watch_id in self._watched_signals:
            watched = self._watched_signals[watch_id]
            watched.signal = signal
            self.signal_updated.emit(watch_id, signal)
    
    def save_to_file(self, filepath: str):
        """Save watch list to JSON file."""
        try:
            data = {
                'poll_interval_ms': self._poll_interval_ms,
                'signals': [ws.to_dict() for ws in self._watched_signals.values()]
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved watch list to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save watch list: {e}")
    
    def load_from_file(self, filepath: str):
        """Load watch list from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Clear existing
            self.clear_all()
            
            # Set interval
            self.set_poll_interval(data.get('poll_interval_ms', 1000))
            
            # Add signals
            # Note: We need to reconstruct Signal objects from the saved data
            # This requires looking up the actual signal from the device manager
            for sig_data in data.get('signals', []):
                device_name = sig_data['device_name']
                signal_address = sig_data['signal_address']
                
                # Try to find the signal in the device structure
                device = self.device_manager.get_device(device_name)
                if device and device.root_node:
                    signal = self._find_signal_in_node(device.root_node, signal_address)
                    if signal:
                        self.add_signal(device_name, signal)
                    else:
                        logger.warning(f"Could not find signal {signal_address} in device {device_name}")
            
            logger.info(f"Loaded watch list from {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to load watch list: {e}")
    
    def _find_signal_in_node(self, node, address: str) -> Optional[Signal]:
        """Recursively find a signal by address in the node tree."""
        # Check signals in current node
        for signal in node.signals:
            if signal.address == address:
                return signal
        
        # Check children
        for child in node.children:
            found = self._find_signal_in_node(child, address)
            if found:
                return found
        
        return None
