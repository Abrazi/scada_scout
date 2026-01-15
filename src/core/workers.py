import logging
import queue
import threading
import time
import traceback
from typing import Any, Dict, Optional

from src.core.events import EventEmitter
from src.models.device_models import Device

logger = logging.getLogger(__name__)

class Worker(EventEmitter):
    """Base class for workers with event capabilities."""
    def __init__(self):
        super().__init__()

class ConnectionWorker(Worker):
    def __init__(self, device_name: str, device: Device, protocol):
        super().__init__()
        self.device_name = device_name
        self.device = device
        self.protocol = protocol

    def run(self):
        try:
            device_name = self.device_name
            self.emit("progress", device_name, f"Connecting to {self.device.config.ip_address}...", 20)
            
            if self.protocol.connect():
                self.emit("progress", device_name, "Connected successfully", 40)
                self.emit("status_changed", device_name, True)
                
                # Auto-Discover
                self.emit("progress", device_name, "Discovering device structure...", 50)
                try:
                    root_node = self.protocol.discover()
                    self.device.root_node = root_node
                    
                    # Check for name change
                    new_name = root_node.name if root_node and root_node.name else device_name
                    
                    self.emit("progress", device_name, "Discovery complete", 90)
                    
                    # Signal both old and new name
                    # If new_name is different, DeviceManager will handle the rename
                    self.emit("device_updated", device_name, new_name)
                    
                except Exception as e:
                    logger.error(f"Discovery failed: {e}")
                    self.emit("progress", device_name, "Discovery failed", 90)
                
                self.emit("progress", device_name, "Ready", 100)
            else:
                self.emit("progress", device_name, "Connection failed", 0)
                self.emit("status_changed", device_name, False)
                
        except Exception as e:
             logger.error(f"Connection worker error: {e}")
             self.emit("progress", self.device_name, f"Error: {e}", 0)
             self.emit("status_changed", self.device_name, False)
        finally:
            self.emit("finished")

class SCDParseWorker(Worker):
    """Worker to parse SCD file in background thread."""
    # Events: progress(msg, percent), finished_parsing(ieds, error_msg)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.emit("progress", "Reading SCD file...", 10)
            
            # Helper to defer import
            from src.core.scd_parser import SCDParser
            
            self.emit("progress", "Parsing XML structure...", 30)
            parser = SCDParser(self.file_path)
            
            if parser.root is None:
                self.emit("finished_parsing", [], "Failed to parse XML root.")
                return

            self.emit("progress", "Extracting IED information...", 60)
            ieds = parser.extract_ieds_info()
            
            self.emit("progress", "Finalizing...", 90)
            self.emit("finished_parsing", ieds, "")
            
        except Exception as e:
            self.emit("finished_parsing", [], str(e))

class BulkReadWorker(Worker):
    """Worker to read multiple signals in a background thread."""
    def __init__(self, device_manager, device_name, signals):
        super().__init__()
        self.device_manager = device_manager
        self.device_name = device_name
        self.signals_to_read = signals

    def run(self):
        for sig in self.signals_to_read:
            try:
                # read_signal will enqueue to IEC worker if available (non-blocking)
                res = self.device_manager.read_signal(self.device_name, sig)
                # If read_signal returns a Signal (synchronous path), it's already processed.
                # If it returns None, the read was enqueued and will be delivered asynchronously.
                # Small sleep to be nice to the network/IED when synchronous
                if res is not None:
                    time.sleep(0.001)
            except Exception as e:
                logger.warning(f"BulkReadWorker error for {self.device_name}: {e}")
                
                # IMPORTANT: Update signal state on error so UI knows it failed
                sig.quality = "Invalid"
                sig.error = str(e)
                # We need to trigger update in DeviceManager to refresh UI
                # self.device_manager.update_signal(self.device_manager, sig) # Hypothetical
                
        self.emit("finished")

from src.models.subscription_models import SubscriptionMode

class IEC61850Worker(Worker):
    """
    Dedicated Worker for IEC 61850 operations (Read/Write/Control).
    Uses a thread-safe queue to process requests sequentially off the main thread.
    
    NEW: Adheres to IECSubscriptionManager for polling.
    """

    def __init__(self, iec_client, device_name: str, subscription_manager):
        super().__init__()
        self._client = iec_client
        self._device_name = device_name
        self._subscription_manager = subscription_manager
        self._queue = queue.Queue()
        self._running = True
        
        # Poll throttling (e.g. 1 sec default)
        self._poll_interval = 1.0  
        self._last_poll_time = 0

    def run(self):
        while self._running:
            try:
                # Use a timeout to allow "tick" logic if queue is empty
                # We aim for ~1s polling cycle
                task = self._queue.get(timeout=0.1)
                self._handle_task(task)
            except queue.Empty:
                # No high-priority tasks, check if we should poll
                self._check_polling()
            except Exception as e:
                logger.error(f"Worker Loop Error: {e}")
                
    def _check_polling(self):
        """Execute READ_POLLING subscriptions if interval elapsed."""
        now = time.time()
        if now - self._last_poll_time >= self._poll_interval:
            self._last_poll_time = now
            self._execute_polling()
            
    def _execute_polling(self):
        """Poll all signals subscribed with READ_POLLING."""
        subs = self._subscription_manager.get_subscriptions(
            self._device_name, 
            SubscriptionMode.READ_POLLING
        )
        
        if not subs:
            return

        # Optimization: We could group by FC or Dataset here if adapter supports it.
        # For now, simplistic iteration.
        for sub in subs:
            try:
                # Construct a logical signal object from the subscription
                # We need a Signal object to pass to the adapter/client
                # We can't easily reconstruct the full object, but we have the address.
                # Assuming adapter.read(address) works or we fake a Signal.
                
                # Create a minimal Signal wrapper
                # Ideally, we should fetch the real Signal object from DeviceManager
                # BUT DeviceManager is in another thread.
                # The adapter usually needs: address, fc (optional), type (optional)
                
                # Check strict filter: double check if still subscribed (redundant but safe)
                if not self._subscription_manager.is_subscribed(self._device_name, sub.mms_path):
                    continue

                if hasattr(self._client, 'read'):
                    # Direct read by address
                    val = self._client.read(sub.mms_path)
                    # The adapter handles updating its internal cache and emitting signal_update
                    # via the callback registered in DeviceManager.add_device
                elif hasattr(self._client, 'read_signal'):
                    # Legacy: needs object. 
                    # Use a dummy signal
                    from src.models.device_models import Signal
                    dummy = Signal(name="Poll", address=sub.mms_path)
                    self._client.read_signal(dummy)
            
            except Exception as e:
                logger.debug(f"Poll fail {self._device_name} {sub.mms_path}: {e}")

    def _handle_task(self, task):
            try:
                action = task.get("action")

                if action == "read":
                    # Expect a Signal object in task['signal']
                    signal = task.get('signal')
                    if signal is None:
                        return

                    # Adapter's read_signal returns an updated Signal
                    if hasattr(self._client, 'read_signal'):
                        updated = self._client.read_signal(signal)
                    else:
                        # Fallback: try to call read by address if available
                        if hasattr(self._client, 'read'):
                            val = self._client.read(signal.address)
                            signal.value = val
                            updated = signal
                        else:
                            updated = signal
                    
                    # We can emit data_ready if needed, but usually the adapter calls back.
                    # self.emit("data_ready", self._device_name, updated)

                elif action == "write":
                    signal = task.get('signal')
                    value = task.get('value')
                    if hasattr(self._client, 'write_signal'):
                        self._client.write_signal(signal, value)
                    elif hasattr(self._client, 'write'):
                        self._client.write(signal.address, value)

                elif action == "control":
                    signal = task.get('signal')
                    value = task.get('value')
                    params = task.get('params') # Extract params
                    
                    # Prefer operate API
                    if hasattr(self._client, 'operate'):
                        # Pass params if supported
                        import inspect
                        sig = inspect.signature(self._client.operate)
                        if 'params' in sig.parameters:
                            self._client.operate(signal, value, params=params)
                        else:
                            self._client.operate(signal, value)
                            
                    elif hasattr(self._client, 'write_signal'):
                        # Try write as fallback
                        self._client.write_signal(signal, value)

                elif action == "select":
                    signal = task.get('signal')
                    params = task.get('params')
                    if hasattr(self._client, 'select'):
                        # Pass params if supported
                        import inspect
                        sig = inspect.signature(self._client.select)
                        if 'params' in sig.parameters:
                            self._client.select(signal, params=params)
                        else:
                            self._client.select(signal)

            except Exception as e:
                self.emit("error", str(e))
                traceback.print_exc()

    def enqueue(self, task: dict):
        self._queue.put(task)

    def stop(self):
        self._running = False
        self.emit("finished")

class ModbusWorker(Worker):
    """
    Dedicated Worker for Modbus operations (Read/Write).
    Handles blocking PyModbus calls in a background thread.
    Events: data_ready(device_name, Signal), error(str), finished()
    """

    def __init__(self, modbus_client, device_name: str):
        super().__init__()
        self._client = modbus_client
        self._device_name = device_name
        self._queue = queue.Queue()
        self._running = True

    def run(self):
        while self._running:
            try:
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                action = task.get("action")
                signal = task.get('signal')
                
                if not signal:
                    continue

                if action == "read":
                    if hasattr(self._client, 'read_signal'):
                        updated = self._client.read_signal(signal)
                        # read_signal usually emits update via base protocol
                        
                elif action == "write":
                    value = task.get('value')
                    if hasattr(self._client, 'write_signal'):
                        self._client.write_signal(signal, value)

            except Exception as e:
                # If an error occurs that wasn't handled by the adapter (e.g. crash in worker logic),
                # we must ensure the signal is marked as invalid and UI is notified.
                if signal:
                    signal.quality = "Invalid" # Using string enum match or object
                    # Try to set SignalQuality enum if possible, else string
                    try:
                         from src.models.device_models import SignalQuality
                         signal.quality = SignalQuality.INVALID
                    except:
                         pass
                         
                    signal.error = str(e)
                    # Force emit update if client has the mechanism
                    if hasattr(self._client, '_emit_update'):
                        self._client._emit_update(signal)
                    
                self.emit("error", str(e))

    def enqueue(self, task: dict):
        self._queue.put(task)

    def stop(self):
        self._running = False
        self.emit("finished")