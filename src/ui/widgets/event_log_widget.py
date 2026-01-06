from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QCheckBox
from PySide6.QtCore import Qt, Signal as QtSignal, QObject
from PySide6.QtGui import QTextCursor, QColor
import logging
from datetime import datetime

class EventLogWidget(QWidget):
    """
    Widget for displaying diagnostic events and IEC 61850 transactions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Text display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.text_edit)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.chk_verbose = QCheckBox("Show All Events (Verbose)")
        self.chk_verbose.setChecked(True) # Default to showing everything for debugging
        self.chk_verbose.stateChanged.connect(self._refresh_log_view)
        btn_layout.addWidget(self.chk_verbose)
        
        self.btn_clear = QPushButton("Clear Log")
        self.btn_clear.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.btn_clear)
        
        self.btn_export = QPushButton("Export Log...")
        self.btn_export.clicked.connect(self._export_log)
        btn_layout.addWidget(self.btn_export)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.all_events = [] # Store all events to support filtering
        
    def _refresh_log_view(self):
        """Re-populates the text area based on current filter."""
        self.text_edit.clear()
        for event in self.all_events:
            self._display_event(event)

    def log_event(self, level: str, source: str, message: str):
        """Add an event to the log with timestamp and color coding."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        event = {
            'timestamp': timestamp,
            'level': level,
            'source': source,
            'message': message
        }
        self.all_events.append(event)
        
        self._display_event(event)
        
    def _display_event(self, event):
        """Displays a singe event if it matches criteria."""
        # Filter logic:
        # If "Verbose" is OFF, hide TRANSACTION and detailed READ events unless it's a change or error
        if not self.chk_verbose.isChecked():
            # Hide transactions (IEC61850 calls)
            if event['level'] == 'TRANSACTION':
                return
            # Hide generic cyclic reads if not error
            if event['source'] == 'WatchList' and 'Read' in event['message'] and event['level'] == 'INFO':
                 # Keep it only if it looks like a value update or error?
                 pass 
        
        # Color code by level
        level = event['level']
        if level == "ERROR":
            color = "#f48771"
        elif level == "WARNING":
            color = "#dcdcaa"
        elif level == "INFO":
            color = "#4ec9b0"
        elif level == "DEBUG":
            color = "#9cdcfe"
        elif level == "TRANSACTION":
            color = "#c586c0"
        else:
            color = "#d4d4d4"
        
        # Format the log entry
        html = f'<span style="color: #808080;">[{event["timestamp"]}]</span> <span style="color: {color};">[{level}]</span> <span style="color: #569cd6;">{event["source"]}:</span> {event["message"]}'
        
        self.text_edit.append(html)
        
        # Auto-scroll to bottom
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)
    
    def clear_log(self):
        """Clear all log entries."""
        self.text_edit.clear()
        self.all_events = []
        self.log_event("INFO", "EventLog", "Log cleared")
    
    def _export_log(self):
        """Export log to file."""
        from PySide6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Event Log",
            "event_log.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.text_edit.toPlainText())
                self.log_event("INFO", "EventLog", f"Exported to {filename}")
            except Exception as e:
                self.log_event("ERROR", "EventLog", f"Export failed: {e}")


class EventLogger(QObject):
    """
    Centralized event logger that can be used across the application.
    """
    event_logged = QtSignal(str, str, str)  # level, source, message
    
    def __init__(self):
        super().__init__()
        
    def log(self, level: str, source: str, message: str):
        """Emit a log event."""
        self.event_logged.emit(level, source, message)
        
    def transaction(self, source: str, message: str):
        """Log an IEC 61850 transaction."""
        self.event_logged.emit("TRANSACTION", source, message)
        
    def error(self, source: str, message: str):
        """Log an error."""
        self.event_logged.emit("ERROR", source, message)
        
    def warning(self, source: str, message: str):
        """Log a warning."""
        self.event_logged.emit("WARNING", source, message)
        
    def info(self, source: str, message: str):
        """Log info."""
        self.event_logged.emit("INFO", source, message)
        
    def debug(self, source: str, message: str):
        """Log debug."""
        self.event_logged.emit("DEBUG", source, message)
