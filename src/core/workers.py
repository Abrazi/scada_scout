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
