import logging
import queue
import threading
import time
import traceback
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal
from src.core.events import EventEmitter
from src.models.device_models import Device

logger = logging.getLogger(__name__)

def _parse_scd_file(file_path):
    """
    Helper function for parallel SCD parsing.
    Must be module-level to be picklable for ProcessPoolExecutor.
    Returns: (mtime, tree, root, ns) tuple or None on failure
    """
    import os
    import xml.etree.ElementTree as ET
    
    try:
        if not os.path.exists(file_path):
            return None
        
        mtime = os.path.getmtime(file_path)
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Detect namespace
        if '}' in root.tag:
            ns_uri = root.tag.split('}')[0].strip('{')
            ns = {'scl': ns_uri}
        else:
            ns = {}
        
        return (mtime, tree, root, ns)
    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {e}")
        return None

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

    def _find_readable_signal(self, node):
        if not node:
            return None
        if hasattr(node, 'signals'):
            for signal in node.signals:
                if getattr(signal, 'access', 'RO') in ('RO', 'RW'):
                    return signal
        if hasattr(node, 'children'):
            for child in node.children:
                found = self._find_readable_signal(child)
                if found:
                    return found
        return None

    def _measure_initial_rtt(self, root_node):
        try:
            test_signal = self._find_readable_signal(root_node)
            if not test_signal:
                return

            start_time = time.perf_counter()
            result = self.protocol.read_signal(test_signal)
            end_time = time.perf_counter()

            if result:
                rtt_ms = (end_time - start_time) * 1000
                test_signal.last_rtt = rtt_ms
        except Exception as e:
            logger.debug(f"Initial RTT measurement failed: {e}")

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

                    # Measure initial RTT after discovery
                    self._measure_initial_rtt(root_node)
                    
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

class SCDParseWorker(QThread):
    """Worker to parse SCD file in background thread."""
    progress = Signal(str, int)
    finished_parsing = Signal(list, str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit("Reading SCD file...", 10)
            
            # Helper to defer import
            from src.core.scd_parser import SCDParser
            
            self.progress.emit("Parsing XML structure...", 30)
            parser = SCDParser(self.file_path)
            
            if parser.root is None:
                self.finished_parsing.emit([], "Failed to parse XML root.")
                return

            self.progress.emit("Extracting IED information...", 60)
            ieds = parser.extract_ieds_info()
            
            self.progress.emit("Finalizing...", 90)
            self.finished_parsing.emit(ieds, "")
            
        except Exception as e:
            self.finished_parsing.emit([], str(e))

class SCDImportWorker(QThread):
    """Worker to import multiple devices from SCD without blocking UI."""
    log = Signal(str)
    progress = Signal(int)
    finished_import = Signal(int, list)
    # Safe signal for Qt actions that must happen on main thread
    device_added = Signal(str)  # device_name

    def __init__(self, device_manager_core, configs, event_logger=None):
        super().__init__()
        # Use the CORE manager (not Qt wrapper) to avoid cross-thread Qt calls
        self.device_manager_core = device_manager_core
        self.configs = configs
        self.event_logger = event_logger
        self._stop_requested = False
        self._scd_parser_cache = {}  # Cache SCD parsers by file path

    def stop(self):
        self._stop_requested = True

    def run(self):
        import time
        import os
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from src.core.scd_parser import SCDParser
        
        total = len(self.configs)
        count = 0
        errors = []

        # Pre-parse unique SCD files in parallel using multiple CPU cores
        scd_files = set()
        for config in self.configs:
            if config.scd_file_path:
                scd_files.add(config.scd_file_path)
        
        if scd_files:
            self.log.emit(f"Parsing {len(scd_files)} SCD file(s)...")
            
            # Sequential parsing to avoid multiprocessing/Qt issues
            for scd_path in scd_files:
                if self._stop_requested:
                    break
                    
                try:
                    parser = SCDParser(scd_path)
                    self._scd_parser_cache[scd_path] = parser
                    self.log.emit(f"  ✓ Parsed {os.path.basename(scd_path)}")
                except Exception as e:
                    self.log.emit(f"  ⚠ Failed to parse {os.path.basename(scd_path)}: {e}")


        # Import devices (structure expansion already cached from pre-parse)
        for i, config in enumerate(self.configs):
            if self._stop_requested:
                break

            try:
                # Only log every 10th device or first/last to reduce UI overhead
                should_log_detail = (i % 10 == 0 or i == 0 or i == total - 1)
                
                if should_log_detail:
                    self.log.emit(f"[{i+1}/{total}] Importing {config.name} ({config.ip_address})...")
                
                # Use core manager directly - pass save=False to avoid redundant disk writes
                self.device_manager_core.add_device(config, save=False)
                
                # Note: load_offline_scd is already called inside add_device(), 
                # no need to call it manually here.
                
                # Notify main thread to update UI (safe cross-thread signal)
                # PERFORMANCE: Disable per-device UI update for bulk imports to prevent freezing
                # The UI will be refreshed once at the end.
                # self.device_added.emit(config.name)

                if should_log_detail:
                    self.log.emit(f"  ✓ Successfully imported {config.name}")

                if self.event_logger and should_log_detail:
                    self.event_logger.info("SCDImport", f"Imported device: {config.name} ({config.ip_address})")

                count += 1
            except Exception as e:
                import traceback
                msg = f"Failed to add {config.name}: {e}"
                self.log.emit(f"  ✗ ERROR: {msg}")
                # Log full traceback for debugging
                logger.error(f"Import error for {config.name}: {traceback.format_exc()}")
                errors.append(msg)
                if self.event_logger:
                    self.event_logger.error("SCDImport", f"Import failed for {config.name}: {e}")

            self.progress.emit(i + 1)
            
            # Small sleep to allow Qt event loop to process signals
            time.sleep(0.01)

        # PERFORMANCE: Perform a single bulk save after all devices are added
        try:
            self.device_manager_core.save_configuration()
            self.log.emit("✓ Persisted device configurations")
        except Exception as e:
            self.log.emit(f"⚠ Failed to save final configuration: {e}")

        self.log.emit(f"\n{'='*50}")
        self.log.emit(f"Import complete: {count}/{total} devices imported successfully")
        if errors:
            self.log.emit(f"Failed: {len(errors)} device(s)")

        self.finished_import.emit(count, errors)

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
                    from src.models.device_models import Signal, RTTState
                    dummy = Signal(name="Poll", address=sub.mms_path)
                    
                    # RTT Measurement (Synchronous)
                    t_start = time.monotonic()
                    dummy.rtt_state = RTTState.SENT
                    
                    self._client.read_signal(dummy)
                    
                    # If we got here, response received (or exception already raised)
                    t_end = time.monotonic()
                    rtt_ms = (t_end - t_start) * 1000.0
                    dummy.last_rtt = rtt_ms
                    dummy.rtt_state = RTTState.RECEIVED
            
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