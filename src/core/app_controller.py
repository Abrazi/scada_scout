import logging
from PySide6.QtCore import QObject, Slot

from src.core.device_manager import DeviceManager
from src.core.update_engine import UpdateEngine
from src.models.device_models import DeviceConfig, DeviceType
from src.ui.widgets.event_log_widget import EventLogger

logger = logging.getLogger(__name__)

class AppController(QObject):
    """
    Main Application Controller.
    Orchestrates interaction between the UI and the Core Logic.
    """
    def __init__(self, device_manager: DeviceManager):
        super().__init__()
        self.device_manager = device_manager
        self.update_engine = UpdateEngine(interval_ms=1000)
        self.event_logger = EventLogger()
        # Per-device IEC worker/thread mappings
        self.iec_threads = {}
        self.iec_workers = {}
        
        # Connect event logger to device manager
        self.device_manager.event_logger = self.event_logger
        
        # Connect tick to logic (placeholder for now)
        self.update_engine.tick.connect(self._on_tick)
        # Watch for device connection events so we can create IEC worker
        self.device_manager.device_status_changed.connect(self._on_device_status_changed)

    def init_iec_worker(self, iec_client, device_name: str):
        """Initialize the dedicated IEC 61850 worker thread for a specific device."""
        from PySide6.QtCore import QThread
        from src.core.workers import IEC61850Worker
        # If already initialized for this device, ignore
        if device_name in self.iec_threads and self.iec_threads[device_name].isRunning():
            return

        thread = QThread()
        worker = IEC61850Worker(iec_client, device_name)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.data_ready.connect(self._on_iec_data)
        worker.error.connect(self._log_worker_error)

        # Store mappings
        self.iec_threads[device_name] = thread
        self.iec_workers[device_name] = worker

        # Expose to DeviceManager for enqueuing
        if not hasattr(self.device_manager, 'iec_workers'):
            self.device_manager.iec_workers = {}
        self.device_manager.iec_workers[device_name] = worker

        thread.start()
        logger.info(f"IEC 61850 Worker thread initialized for {device_name}.")

    def _on_device_status_changed(self, device_name: str, connected: bool):
        """When a device connects, create the IEC worker for it if appropriate."""
        try:
            if not connected:
                return

            # Get protocol adapter
            proto = self.device_manager.get_or_create_protocol(device_name)
            if not proto:
                return

            # Only create worker for IEC61850Adapter instances
            from src.protocols.iec61850.adapter import IEC61850Adapter
            if isinstance(proto, IEC61850Adapter):
                self.init_iec_worker(proto, device_name)
        except Exception as e:
            logger.debug(f"_on_device_status_changed error: {e}")

    @Slot(str, object)
    def _on_iec_data(self, ref, value):
        """Handle incoming data from async worker."""
        # ref is device_name, value is Signal object
        try:
            device_name = ref
            signal = value
            # Use DeviceManager internal path to handle logging and emit
            if hasattr(self.device_manager, '_on_signal_update'):
                self.device_manager._on_signal_update(device_name, signal)
            else:
                # Fallback: emit public signal
                self.device_manager.signal_updated.emit(device_name, signal)
        except Exception as e:
            logger.error(f"Error handling IEC data: {e}")

    @Slot(str)
    def _log_worker_error(self, message):
        logger.error(f"IEC Worker Error: {message}")

    @Slot()
    def start_application(self):
        """Called when the application is ready to start."""
        logger.info("Application starting...")
        # Load saved configuration
        self.device_manager.load_configuration()
        # Expose update engine and device manager so UpdateEngine can schedule reads
        setattr(self.device_manager, 'update_engine', self.update_engine)
        self.update_engine.set_device_manager(self.device_manager)
        self.update_engine.start()

    def _on_tick(self):
        """Periodic logic execution."""
        # Poll devices that have polling enabled
        # Run polling off the GUI thread to avoid blocking the UI
        import threading

        # If a previous poll thread is still running, skip this tick
        if hasattr(self, '_poll_thread') and getattr(self, '_poll_thread') is not None:
            if self._poll_thread.is_alive():
                return

        def _poll():
            try:
                self.device_manager.poll_devices()
            except Exception as e:
                logger.error(f"Background poll error: {e}")

        self._poll_thread = threading.Thread(target=_poll, daemon=True)
        self._poll_thread.start()

    def shutdown(self):
        """Gracefully stop background IEC workers and threads."""
        logger.info("Shutting down IEC workers...")
        try:
            for name, worker in list(self.iec_workers.items()):
                try:
                    worker.stop()
                except Exception:
                    pass

            for name, thread in list(self.iec_threads.items()):
                try:
                    # Ask thread to quit and wait briefly
                    thread.quit()
                    thread.wait(500)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error during shutdown: {e}")
