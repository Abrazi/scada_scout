import logging
from PySide6.QtCore import QObject, Slot

from src.core.device_manager import DeviceManager
from src.core.update_engine import UpdateEngine
from src.models.device_models import DeviceConfig, DeviceType

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
        
        # Connect tick to logic (placeholder for now)
        self.update_engine.tick.connect(self._on_tick)

    @Slot()
    def start_application(self):
        """Called when the application is ready to start."""
        logger.info("Application starting...")
        # TODO: Load saved configuration
        self._create_mock_device()
        self.update_engine.start()

    def _on_tick(self):
        """Periodic logic execution."""
        # Future: Poll devices, Check connection health
        pass

    def _create_mock_device(self):
        """Creates a temporary mock device for testing UI."""
        config = DeviceConfig(
            name="Simulated_IED_01",
            ip_address="127.0.0.1",
            port=2404,
            device_type=DeviceType.IEC61850_IED
        )
        try:
            self.device_manager.add_device(config)
            # Auto-connect for demo purposes
            self.device_manager.connect_device(config.name)
        except ValueError as e:
            logger.warning(str(e))
