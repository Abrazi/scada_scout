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
        
        # Connect event logger to device manager
        self.device_manager.event_logger = self.event_logger
        
        # Connect tick to logic (placeholder for now)
        self.update_engine.tick.connect(self._on_tick)

    @Slot()
    def start_application(self):
        """Called when the application is ready to start."""
        logger.info("Application starting...")
        # TODO: Load saved configuration
        self.update_engine.start()

    def _on_tick(self):
        """Periodic logic execution."""
        # Future: Poll devices, Check connection health
        pass
