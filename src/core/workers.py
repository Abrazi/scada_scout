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
                # read_signal triggers status synchronization in DeviceManager
                self.device_manager.read_signal(self.device_name, sig)
                # Small sleep to be nice to the network/IED
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
    """
    data_ready = Signal(str, object)   # ref, value
    error = Signal(str)
    finished = Signal()

    def __init__(self, iec_client):
        super().__init__()
        self._client = iec_client
        self._queue = queue.Queue()
        self._running = True

    @Slot()
    def run(self):
        while self._running:
            try:
                # Blocking get with timeout allows checking _running flag
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                action = task["action"]
                if action == "read":
                    ref = task["ref"]
                    # Assume client.read returns python value or MmsValue
                    # We might need to handle the conversion here or in client wrapper
                    if hasattr(self._client, 'read_value'):
                         val = self._client.read_value(ref)
                    else:
                         val = self._client.read(ref)
                    
                    self.data_ready.emit(ref, val)

                elif action == "write":
                    self._client.write(task["ref"], task["value"])

                elif action == "control":
                    # Support SBO vs Direct
                    val = task.get("value")
                    sbo = task.get("sbo", False)
                    
                    if hasattr(self._client, 'operate'):
                        self._client.operate(task["ref"], val, sbo)
                    else:
                        # Fallback if operate signature differs, relying on wrapper
                        # But user provided specific call signature, likely for a cleaner wrapper
                        pass

            except Exception as e:
                self.error.emit(str(e))
                traceback.print_exc()

    def enqueue(self, task: dict):
        self._queue.put(task)

    def stop(self):
        self._running = False
        self.finished.emit()
