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
