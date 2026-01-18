from PySide6.QtCore import QObject, Signal as QtSignal
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class EventLogger(QObject):
    """
    Centralized event logger that maintains history and can be saved/loaded.
    """
    event_logged = QtSignal(str, str, str)  # level, source, message
    history_cleared = QtSignal()

    def __init__(self, max_history=1000):
        super().__init__()
        self._history = []
        self._max_history = max_history

    def log(self, level: str, source: str, message: str):
        """Record and emit a log event."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event = {
            'timestamp': timestamp,
            'level': level,
            'source': source,
            'message': message
        }
        
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
            
        self.event_logged.emit(level, source, message)

    def transaction(self, source: str, message: str):
        self.log("TRANSACTION", source, message)

    def error(self, source: str, message: str):
        self.log("ERROR", source, message)

    def warning(self, source: str, message: str):
        self.log("WARNING", source, message)

    def info(self, source: str, message: str):
        self.log("INFO", source, message)

    def debug(self, source: str, message: str):
        self.log("DEBUG", source, message)

    def get_history(self):
        return self._history

    def clear_history(self):
        self._history = []
        self.history_cleared.emit()

    def save_to_file(self, filepath: str):
        try:
            with open(filepath, 'w') as f:
                json.dump(self._history, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save event history: {e}")

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                self._history = json.load(f)
            # Re-emit events for UI to populate? 
            # Better to just let UI re-read from get_history() after a signal
            self.history_cleared.emit() # Signal UI to refresh from history
        except Exception as e:
            logger.error(f"Failed to load event history: {e}")
