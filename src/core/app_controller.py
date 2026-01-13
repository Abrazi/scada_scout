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
        self.iec_thread = None
        self.iec_worker = None
        
        # Connect event logger to device manager
        self.device_manager.event_logger = self.event_logger
        
        # Connect tick to logic (placeholder for now)
        self.update_engine.tick.connect(self._on_tick)

    def init_iec_worker(self, iec_client):
        """Initialize the dedicated IEC 61850 worker thread."""
        from PySide6.QtCore import QThread
        from src.core.workers import IEC61850Worker
        
        if self.iec_thread and self.iec_thread.isRunning():
            return

        self.iec_thread = QThread()
        self.iec_worker = IEC61850Worker(iec_client)
        self.iec_worker.moveToThread(self.iec_thread)

        self.iec_thread.started.connect(self.iec_worker.run)
        self.iec_worker.data_ready.connect(self._on_iec_data)
        self.iec_worker.error.connect(self._log_worker_error)

        self.iec_thread.start()
        
        # Inject into update engine
        self.update_engine.set_iec_worker(self.iec_worker)
        logger.info("IEC 61850 Worker thread initialized.")

    @Slot(str, object)
    def _on_iec_data(self, ref, value):
        """Handle incoming data from async worker."""
        # Find signal by ref and update
        # device_manager.update_signal_by_ref(ref, value) -> Needs implementation
        pass 

    @Slot(str)
    def _log_worker_error(self, message):
        logger.error(f"IEC Worker Error: {message}")

    @Slot()
    def start_application(self):
        """Called when the application is ready to start."""
        logger.info("Application starting...")
        # Load saved configuration
        self.device_manager.load_configuration()
        self.update_engine.start()

    def _on_tick(self):
        """Periodic logic execution."""
        # Poll devices that have polling enabled
        # Update: We should use the worker for this if IEC61850
        self.device_manager.poll_devices()
