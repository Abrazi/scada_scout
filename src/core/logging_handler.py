import logging
from PySide6.QtCore import QObject, Signal

class QtLogHandler(logging.Handler, QObject):
    """
    Redirects Python logging records to a Qt Signal.
    """
    new_record = Signal(str, str, str) # level, source, message

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        try:
            # Check if Qt object is still valid (not deleted during shutdown)
            if not hasattr(self, 'new_record'):
                return
                
            msg = self.format(record)
            level = record.levelname
            source = record.name
            
            # Simplify source names
            if source.startswith("src.core."):
                source = source.replace("src.core.", "")
            elif source.startswith("src.protocols."):
                source = source.split(".")[-1] # e.g. adapter
            elif source.startswith("src.ui."):
                source = source.split(".")[-1]
                
            self.new_record.emit(level, source, msg)
        except RuntimeError:
            # Qt object deleted, silently ignore
            pass
        except Exception:
            # Only call handleError if we can safely do so
            try:
                self.handleError(record)
            except:
                pass
