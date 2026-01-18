import logging
from PySide6.QtCore import QObject, Slot

from src.core.device_manager import DeviceManager
from src.core.update_engine import UpdateEngine
from src.core.watch_list_manager import WatchListManager
from src.models.device_models import DeviceConfig, DeviceType
from src.core.event_logger import EventLogger

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
        self.watch_list_manager = WatchListManager(self.device_manager)
        
        # Connect event logger to device manager
        self.device_manager.event_logger = self.event_logger
        
        # Connect tick to logic (placeholder for now)
        self.update_engine.tick.connect(self._on_tick)
        # Watch for device connection events so we can create IEC worker
        self.device_manager.device_status_changed.connect(self._on_device_status_changed)

    def init_iec_worker(self, iec_client, device_name: str):
        """Deprecated: Worker management moved to DeviceManager."""
        pass

    def _on_device_status_changed(self, device_name: str, connected: bool):
        """When a device connects, create the IEC worker for it if appropriate."""
        # Worker creation is now handled by DeviceManager.connect_device
        pass

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
                # self.device_manager.poll_devices() # DISABLED: Optimization
                # Polling is now handled by self.watch_list_manager's internal timer
                pass
            except Exception as e:
                logger.error(f"Background poll error: {e}")

        self._poll_thread = threading.Thread(target=_poll, daemon=True)
        self._poll_thread.start()

    def shutdown(self):
        """Gracefully stop background IEC workers and threads."""
        logger.info("Shutting down application...")

        # Stop data pump first to prevent new polls
        if self.update_engine:
            self.update_engine.stop()

        # Wait for any active polling thread
        if hasattr(self, '_poll_thread') and self._poll_thread and self._poll_thread.is_alive():
            try:
                self._poll_thread.join(timeout=1.0)
            except Exception:
                pass

        if hasattr(self.device_manager, 'clear_all_devices'):
            self.device_manager.clear_all_devices()
            
        # logger.info("Shutting down IEC workers...")
        # Legacy cleanup - can be removed if strictly using DeviceManager

