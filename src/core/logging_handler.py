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
        except Exception:
            self.handleError(record)
