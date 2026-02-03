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
    # Timestamp when a read request was sent (epoch seconds)
    last_request_ts: float = None
    # Last measured response time in milliseconds
    last_response_ms: int = None
    # Maximum observed response time in milliseconds
    max_response_ms: int = None
    
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
    # Use `object` for the signal parameter to avoid Shiboken attempting to
    # convert our domain Signal class to a C++ type when emitting.
    # Emitted args: watch_id (str), updated_signal (object), response_ms (object)
    # Use `object` for response_ms so None can be emitted safely.
    signal_updated = QtSignal(str, object, object)
    watch_list_changed = QtSignal()  # Emitted when list is modified
    polling_progress = QtSignal(int, int)  # current, total
    
    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
        self._watched_signals: Dict[str, WatchedSignal] = {}
        self._poll_interval_ms = 1000  # Default 1 second
        self._max_poll_batch = 50  # Maximum signals to poll per batch
        self._poll_index = 0  # Current position in polling rotation
        self._pending_updates = []  # Batch pending UI updates
        self._batch_update_active = False
        
        # Polling timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_all_signals)
        
        # Batch update timer (emit batched updates every 100ms)
        self._batch_timer = QTimer()
        self._batch_timer.timeout.connect(self._emit_batched_updates)
        self._batch_timer.start(100)  # 100ms batch interval
        
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
        
        # Auto-adjust batch size based on total signal count
        total_signals = len(self._watched_signals)
        if total_signals > 200:
            self._max_poll_batch = 100  # Larger batches for 200+ signals
        elif total_signals > 100:
            self._max_poll_batch = 75   # Medium batches for 100-200 signals
        else:
            self._max_poll_batch = 50   # Default batch size
        
        logger.info(f"Added signal to watch list: {watch_id} (total: {total_signals}, batch: {self._max_poll_batch})")
        self.watch_list_changed.emit()
        
        # Start polling if not already running
        if not self._poll_timer.isActive():
            self._poll_timer.start(self._poll_interval_ms)
        
        # Trigger immediate poll for this signal (only for small lists)
        if total_signals < 50:
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
    
    def get_signals_for_device(self, device_name: str) -> List[Signal]:
        """Get all signals being watched for a specific device."""
        signals = []
        for watched in self._watched_signals.values():
            if watched.device_name == device_name:
                signals.append(watched.signal)
        return signals

    def get_watched(self, watch_id: str) -> Optional[WatchedSignal]:
        """Get a watched signal by watch_id."""
        return self._watched_signals.get(watch_id)
    
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
        """Poll watched signals in chunks to prevent UI freezing."""
        if not self._watched_signals:
            return
        
        # Convert to list for indexed access
        watch_items = list(self._watched_signals.items())
        total_signals = len(watch_items)
        
        # Chunk polling: only poll up to _max_poll_batch signals per timer tick
        start_idx = self._poll_index
        end_idx = min(start_idx + self._max_poll_batch, total_signals)
        
        # Emit progress for large lists
        if total_signals > 100:
            self.polling_progress.emit(end_idx, total_signals)
        
        # Poll this chunk
        for i in range(start_idx, end_idx):
            watch_id, watched = watch_items[i]
            try:
                # Record request timestamp
                import time
                watched.last_request_ts = time.time()

                updated_signal = self.device_manager.read_signal(
                    watched.device_name,
                    watched.signal
                )
                
                if updated_signal:
                    # Sync Result (from cache or blocking read)
                    watched.signal = updated_signal
                    # Compute RTT if possible
                    try:
                        if watched.last_request_ts:
                            rtt_ms = int(round((time.time() - watched.last_request_ts) * 1000))
                        else:
                            rtt_ms = None
                    except Exception:
                        rtt_ms = None

                    watched.last_response_ms = rtt_ms
                    if rtt_ms is not None:
                        if watched.max_response_ms is None or rtt_ms > watched.max_response_ms:
                            watched.max_response_ms = rtt_ms
                        updated_signal.last_rtt = float(rtt_ms)
                        watched.signal.last_rtt = float(rtt_ms)
                    
                    # Batch the update instead of emitting immediately
                    self._pending_updates.append((watch_id, updated_signal, rtt_ms))
                else:
                    # Async read enqueued
                    pass
                    
            except Exception as e:
                logger.debug(f"Failed to poll {watch_id}: {e}")
        
        # Move to next chunk
        self._poll_index = end_idx % total_signals if end_idx < total_signals else 0
        
        # Log progress for large lists
        if total_signals > 100 and end_idx >= total_signals:
            logger.debug(f"Completed polling cycle for {total_signals} signals")

    def _emit_batched_updates(self):
        """Emit pending signal updates in a batch."""
        if not self._pending_updates:
            return
        
        # Emit all pending updates
        for watch_id, signal, rtt_ms in self._pending_updates:
            self.signal_updated.emit(watch_id, signal, rtt_ms)
        
        # Clear batch
        self._pending_updates.clear()
    
    def _on_device_signal_updated(self, device_name: str, signal: Signal):
        """Handle signal updates from DeviceManager (e.g. from async workers)."""
        watch_id = f"{device_name}::{signal.address}"
        if watch_id in self._watched_signals:
            watched = self._watched_signals[watch_id]
            watched.signal = signal
            # Compute RTT if we have a request timestamp
            try:
                import time
                if watched.last_request_ts:
                    rtt_ms = int(round((time.time() - watched.last_request_ts) * 1000))
                else:
                    rtt_ms = None
            except Exception:
                rtt_ms = None

            watched.last_response_ms = rtt_ms
            if rtt_ms is not None:
                if watched.max_response_ms is None or rtt_ms > watched.max_response_ms:
                    watched.max_response_ms = rtt_ms
                signal.last_rtt = float(rtt_ms)
                watched.signal.last_rtt = float(rtt_ms)
            # Clear the last_request_ts
            watched.last_request_ts = None
            
            # Batch the update instead of emitting immediately
            self._pending_updates.append((watch_id, signal, rtt_ms))
    
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

    def rename_device(self, old_name: str, new_name: str):
        """Update in-memory watched signals when a device is renamed.

        This updates `device_name` and `watch_id` on each `WatchedSignal` and
        moves them under the new keys in `_watched_signals`.
        """
        if not old_name or not new_name or old_name == new_name:
            return

        to_move = {k: v for k, v in self._watched_signals.items() if k.startswith(f"{old_name}::")}
        if not to_move:
            return

        for old_key, watched in to_move.items():
            try:
                # Compute new key
                suffix = old_key.split("::", 1)[1]
                new_key = f"{new_name}::{suffix}"
                # Update object
                watched.device_name = new_name
                watched.watch_id = new_key
                # Also update underlying Signal.unique_address if present
                try:
                    if hasattr(watched.signal, 'unique_address') and watched.signal.unique_address:
                        watched.signal.unique_address = watched.signal.unique_address.replace(f"{old_name}::", f"{new_name}::", 1)
                except Exception:
                    pass

                # Insert under new key and remove old
                self._watched_signals[new_key] = watched
                del self._watched_signals[old_key]
            except Exception:
                logger.exception(f"Failed to migrate watched signal {old_key} to {new_name}")

        logger.info(f"Updated watch list entries for renamed device {old_name} -> {new_name}")
        self.watch_list_changed.emit()
    
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
