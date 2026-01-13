from PySide6.QtCore import QObject, Signal

class WorkerSignals(QObject):
    progress = Signal(str, str, int)
    status_changed = Signal(str, bool)
    device_updated = Signal(str, str) # old_name, new_name (if changed)
    finished = Signal()

class ConnectionWorker:
    def __init__(self, device_name, device, protocol):
        self.device_name = device_name
        self.device = device
        self.protocol = protocol
        self.signals = WorkerSignals()

    def run(self):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            device_name = self.device_name
            self.signals.progress.emit(device_name, f"Connecting to {self.device.config.ip_address}...", 20)
            
            if self.protocol.connect():
                self.signals.progress.emit(device_name, "Connected successfully", 40)
                self.signals.status_changed.emit(device_name, True)
                
                # Auto-Discover
                self.signals.progress.emit(device_name, "Discovering device structure...", 50)
                try:
                    root_node = self.protocol.discover()
                    self.device.root_node = root_node
                    
                    # Check for name change
                    new_name = root_node.name if root_node and root_node.name else device_name
                    
                    self.signals.progress.emit(device_name, "Discovery complete", 90)
                    
                    # Signal both old and new name
                    # If new_name is different, DeviceManager will handle the rename
                    self.signals.device_updated.emit(device_name, new_name)
                    
                except Exception as e:
                    logger.error(f"Discovery failed: {e}")
                    self.signals.progress.emit(device_name, "Discovery failed", 90)
                
                self.signals.progress.emit(device_name, "Ready", 100)
            else:
                self.signals.progress.emit(device_name, "Connection failed", 0)
                self.signals.status_changed.emit(device_name, False)
                
        except Exception as e:
             logger.error(f"Connection worker error: {e}")
             self.signals.progress.emit(self.device_name, f"Error: {e}", 0)
             self.signals.status_changed.emit(self.device_name, False)
        finally:
            self.signals.finished.emit()

from PySide6.QtCore import QThread, Signal

class SCDParseWorker(QThread):
    """Worker to parse SCD file in background thread."""
    progress = Signal(str, int) # message, percent
    finished_parsing = Signal(list, str) # result (list of ieds), error_msg (if any)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit("Reading SCD file...", 10)
            
            # Heavy import moved here to ensure it runs in thread if not already loaded
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

class BulkReadWorker:
    """Worker to read multiple signals in a background thread."""
    def __init__(self, device_manager, device_name, signals):
        self.device_manager = device_manager
        self.device_name = device_name
        self.signals_to_read = signals
        self.signals = WorkerSignals()

    def run(self):
        import time
        import logging
        logger = logging.getLogger(__name__)

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
                sig.quality = "Invalid" # Or SignalQuality.INVALID if we could import it
                sig.error = str(e)
                # We need to trigger update in DeviceManager to refresh UI
                # self.device_manager.update_signal(self.device_manager, sig) # Hypothetical
                
        self.signals.finished.emit()

import queue
import traceback
from PySide6.QtCore import Slot

class IEC61850Worker(QObject):
    """
    Dedicated Worker for IEC 61850 operations (Read/Write/Control).
    Uses a thread-safe queue to process requests sequentially off the GUI thread.
    Emits `data_ready` as (device_name, Signal)
    """
    data_ready = Signal(str, object)   # device_name, Signal
    error = Signal(str)
    finished = Signal()

    def __init__(self, iec_client, device_name: str):
        super().__init__()
        self._client = iec_client
        self._device_name = device_name
        self._queue = queue.Queue()
        self._running = True

    @Slot()
    def run(self):
        while self._running:
            try:
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                action = task.get("action")

                if action == "read":
                    # Expect a Signal object in task['signal']
                    signal = task.get('signal')
                    if signal is None:
                        continue

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

                    # Adapter implementations typically call the protocol data callback
                    # via BaseProtocol._emit_update(signal). Avoid duplicating the update
                    # here to prevent double-emits. If an adapter does not call back,
                    # the AppController can be extended to listen to this signal.

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
                    # Prefer operate API
                    if hasattr(self._client, 'operate'):
                        self._client.operate(signal, value)
                    elif hasattr(self._client, 'write_signal'):
                        # Try write as fallback
                        self._client.write_signal(signal, value)

            except Exception as e:
                self.error.emit(str(e))
                traceback.print_exc()

    def enqueue(self, task: dict):
        self._queue.put(task)

    def stop(self):
        self._running = False
        self.finished.emit()
