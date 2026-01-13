from PySide6.QtCore import QObject, QTimer, Signal
import logging

logger = logging.getLogger(__name__)

class UpdateEngine(QObject):
    """
    Periodic Update Engine.
    Triggers periodic tasks such as polling devices or refreshing the UI.
    """
    # Signal emitted every tick (e.g., 100ms or 1s)
    tick = Signal()

    def __init__(self, interval_ms: int = 1000):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._interval = interval_ms
        self._running = False
        self.device_manager = None

    def set_device_manager(self, device_manager):
        """Inject the DeviceManager so UpdateEngine can schedule reads via it."""
        self.device_manager = device_manager

    def refresh_live_data(self, device_name: str, signals: list):
        """Asynchronously refresh a list of Signal objects for a device.

        This delegates to DeviceManager.read_signal so that DeviceManager
        can route reads to the proper per-device IEC worker or fall back
        to synchronous protocol reads when necessary.
        """
        if not self.device_manager:
            return

        for sig in signals:
            try:
                self.device_manager.read_signal(device_name, sig)
            except Exception:
                pass

    def start(self):
        """Starts the update timer."""
        if not self._running:
            self._timer.start(self._interval)
            self._running = True
            logger.info(f"UpdateEngine started (interval={self._interval}ms)")

    def stop(self):
        """Stops the update timer."""
        if self._running:
            self._timer.stop()
            self._running = False
            logger.info("UpdateEngine stopped")

    def _on_timeout(self):
        """Called when timer expires."""
        self.tick.emit()
