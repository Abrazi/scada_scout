from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QCheckBox, QComboBox, QLineEdit, QLabel, QFileDialog
import subprocess
import os
from PySide6.QtCore import Qt, Signal as QtSignal, QObject
from PySide6.QtGui import QTextCursor, QColor
import html
import logging
from datetime import datetime
from src.core.packet_capture import PacketCaptureWorker
import psutil

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

        # Toolbar for Play/Pause and Filtering
        toolbar_layout = QHBoxLayout()
        layout.addLayout(toolbar_layout)

        # Pause/Resume
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setCheckable(True)
        self.btn_pause.clicked.connect(self._toggle_pause)
        toolbar_layout.addWidget(self.btn_pause)
        
        # Filter Source
        from PySide6.QtWidgets import QComboBox
        self.combo_source = QComboBox()
        self.combo_source.addItem("All Sources")
        self.combo_source.addItem("Application") # Only app logs
        self.combo_source.addItem("Devices") # All device logs
        self.combo_source.currentTextChanged.connect(self._apply_source_filter)
        toolbar_layout.addWidget(self.combo_source)
        
        toolbar_layout.addStretch()
        
        
        # Capture Controls
        self.btn_capture = QPushButton("Capture Traffic")
        self.btn_capture.setCheckable(True)
        self.btn_capture.clicked.connect(self._toggle_capture)
        # Style make it distinct
        self.btn_capture.setStyleSheet("""
            QPushButton:checked {
                background-color: #c94e4e;
                color: white;
            }
        """)
        toolbar_layout.addWidget(self.btn_capture)

        self.combo_capture_filter = QComboBox()
        self.combo_capture_filter.addItem("MMS (TCP 102)", "tcp port 102")
        self.combo_capture_filter.addItem("GOOSE (Ethertype 0x88b8)", "ether proto 0x88b8")
        self.combo_capture_filter.addItem("SV (Ethertype 0x88ba)", "ether proto 0x88ba")
        self.combo_capture_filter.addItem("All TCP", "tcp")
        self.combo_capture_filter.addItem("All Traffic", "")
        toolbar_layout.addWidget(self.combo_capture_filter)

        # Capture logging controls
        self.chk_log_file = QCheckBox("Log to File")
        self.chk_log_file.setChecked(False)
        toolbar_layout.addWidget(self.chk_log_file)

        self.le_log_file = QLineEdit()
        self.le_log_file.setPlaceholderText("packets.log")
        self.le_log_file.setFixedWidth(220)
        toolbar_layout.addWidget(self.le_log_file)

        self.btn_browse_log = QPushButton("Browse...")
        self.btn_browse_log.clicked.connect(self._browse_log_file)
        toolbar_layout.addWidget(self.btn_browse_log)

        self.chk_log_json = QCheckBox("JSON")
        self.chk_log_json.setChecked(False)
        toolbar_layout.addWidget(self.chk_log_json)

        # Rotation controls
        self.lbl_max_mb = QLabel("Max MB:")
        self.le_max_mb = QLineEdit()
        self.le_max_mb.setFixedWidth(80)
        self.le_max_mb.setPlaceholderText("10")
        toolbar_layout.addWidget(self.lbl_max_mb)
        toolbar_layout.addWidget(self.le_max_mb)

        self.lbl_max_files = QLabel("Rotations:")
        self.le_max_files = QLineEdit()
        self.le_max_files.setFixedWidth(50)
        self.le_max_files.setPlaceholderText("5")
        toolbar_layout.addWidget(self.lbl_max_files)
        toolbar_layout.addWidget(self.le_max_files)

        self.btn_apply_rotation = QPushButton("Apply Rotation")
        self.btn_apply_rotation.clicked.connect(self._apply_rotation_settings)
        toolbar_layout.addWidget(self.btn_apply_rotation)

        # Open log file button
        self.btn_open_log = QPushButton("Open Log")
        self.btn_open_log.clicked.connect(self._open_log_file)
        toolbar_layout.addWidget(self.btn_open_log)

        # Interface selection
        self.combo_iface = QComboBox()
        self.combo_iface.setFixedWidth(180)
        toolbar_layout.addWidget(self.combo_iface)

        self.btn_refresh_ifaces = QPushButton("Refresh Ifaces")
        self.btn_refresh_ifaces.clicked.connect(self._populate_ifaces)
        toolbar_layout.addWidget(self.btn_refresh_ifaces)

        # Populate interfaces initially
        self._populate_ifaces()

        self.all_events = [] # Store all events to support filtering
        self.is_paused = False
        self.source_filter = "All Sources" # or specific device name
        
        self.capture_worker = PacketCaptureWorker()
        self.capture_worker.packet_captured.connect(self._on_packet_captured)
        self.capture_worker.error_occurred.connect(self._on_capture_error)

    def _toggle_capture(self):
        if self.btn_capture.isChecked():
            filter_str = self.combo_capture_filter.currentData()
            # Apply logging and interface settings to worker
            log_to_file = self.chk_log_file.isChecked()
            log_path = self.le_log_file.text() if self.le_log_file.text() else None
            # If user requested logging but didn't provide a path, use default in cwd
            if log_to_file and not log_path:
                default_path = os.path.join(os.getcwd(), "packets.log")
                self.le_log_file.setText(default_path)
                log_path = default_path
            json_fmt = self.chk_log_json.isChecked()
            if log_to_file and log_path:
                try:
                    self.capture_worker.set_log_file(log_path, json_format=json_fmt)
                except Exception as e:
                    self.log_event("ERROR", "Network", f"Failed to set log file: {e}")

            # Apply rotation settings now if provided
            try:
                max_mb = int(self.le_max_mb.text()) if self.le_max_mb.text() else None
                max_files = int(self.le_max_files.text()) if self.le_max_files.text() else None
                if max_mb is not None or max_files is not None:
                    mb_bytes = (max_mb * 1024 * 1024) if max_mb is not None else None
                    self.capture_worker.set_log_rotation(mb_bytes if mb_bytes is not None else 0, max_files if max_files is not None else 5)
            except Exception:
                pass

            iface = self.combo_iface.currentText()
            if iface and iface != "(none)":
                try:
                    self.capture_worker.set_interface(iface)
                except Exception as e:
                    self.log_event("ERROR", "Network", f"Failed to set interface: {e}")

            self.capture_worker.start_capture(filter_str)
            self.log_event("INFO", "Network", f"Started capture with filter: {filter_str}")
        else:
            self.capture_worker.stop_capture()
            self.log_event("INFO", "Network", "Stopped capture")

    def _on_packet_captured(self, summary: str):
        self.log_event("PACKET", "Network", summary)

    def _browse_log_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select packet log file", "packets.log", "Log Files (*.log *.txt);;All Files (*)")
        if filename:
            self.le_log_file.setText(filename)

    def _open_log_file(self):
        path = self.le_log_file.text()
        if not path:
            self.log_event("ERROR", "Network", "No log file selected to open")
            return
        if not os.path.exists(path):
            self.log_event("ERROR", "Network", f"Log file does not exist: {path}")
            return
        try:
            if os.name == 'nt':
                os.startfile(path)
            elif os.name == 'posix':
                # Linux / macOS
                opener = 'xdg-open' if subprocess.run(['which', 'xdg-open'], capture_output=True).returncode == 0 else 'open'
                subprocess.Popen([opener, path])
            else:
                subprocess.Popen(['open', path])
        except Exception as e:
            self.log_event("ERROR", "Network", f"Failed to open log: {e}")

    def _apply_rotation_settings(self):
        try:
            max_mb = int(self.le_max_mb.text()) if self.le_max_mb.text() else None
            max_files = int(self.le_max_files.text()) if self.le_max_files.text() else None
            if max_mb is None and max_files is None:
                return
            mb_bytes = (max_mb * 1024 * 1024) if max_mb is not None else 0
            self.capture_worker.set_log_rotation(mb_bytes, max_files if max_files is not None else 5)
            self.log_event("INFO", "Network", f"Rotation set: {max_mb or 'default'} MB, {max_files or 'default'} files")
        except Exception as e:
            self.log_event("ERROR", "Network", f"Failed to apply rotation: {e}")

    def _populate_ifaces(self):
        self.combo_iface.clear()
        try:
            addrs = psutil.net_if_addrs()
            if not addrs:
                self.combo_iface.addItem("(none)")
                return
            # Add an empty option for default
            self.combo_iface.addItem("")
            for name in sorted(addrs.keys()):
                self.combo_iface.addItem(name)
        except Exception:
            self.combo_iface.addItem("(none)")

    def _on_capture_error(self, err: str):
        self.log_event("ERROR", "Network", err)
        # Uncheck button if crashed
        if self.btn_capture.isChecked():
             self.btn_capture.setChecked(False)

    def update_device_list(self, devices):
        """Updates the source filter with available devices."""
        # preserve current selection
        current = self.combo_source.currentText()
        
        self.combo_source.blockSignals(True)
        self.combo_source.clear()
        self.combo_source.addItem("All Sources")
        self.combo_source.addItem("Application") 
        self.combo_source.insertSeparator(2)
        
        for dev in devices:
            self.combo_source.addItem(dev)
            
        # restore selection if possible
        idx = self.combo_source.findText(current)
        if idx >= 0:
            self.combo_source.setCurrentIndex(idx)
        else:
            self.combo_source.setCurrentIndex(0)
            
        self.combo_source.blockSignals(False)

    def _toggle_pause(self):
        self.is_paused = self.btn_pause.isChecked()
        self.btn_pause.setText("Resume" if self.is_paused else "Pause")

    def _apply_source_filter(self, text):
        self.source_filter = text
        self._refresh_log_view()
        
    def _refresh_log_view(self):
        """Re-populates the text area based on current filter."""
        self.text_edit.clear()
        for event in self.all_events:
            self._display_event(event)

    def log_event(self, level: str, source: str, message: str):
        """Add an event to the log with timestamp and color coding."""
        if self.is_paused:
            return

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
        # Normalize event fields early to avoid UnboundLocalError
        level = event.get('level') if isinstance(event, dict) else getattr(event, 'level', None)
        source = event.get('source') if isinstance(event, dict) else getattr(event, 'source', None)
        message = event.get('message') if isinstance(event, dict) else getattr(event, 'message', None)

        # Filter logic:
        # If "Verbose" is OFF, hide TRANSACTION and detailed READ events unless it's a change or error
        if not self.chk_verbose.isChecked():
            # Hide transactions (IEC61850 calls)
            if level == 'TRANSACTION':
                return
            # Hide generic cyclic reads if not error
            if source == 'WatchList' and isinstance(message, str) and 'Read' in message and level == 'INFO':
                # Keep it only if it looks like a value update or error? Currently skip
                return

        # Source Filtering
        if self.source_filter == "All Sources":
            pass # Show all
        elif self.source_filter == "Application":
            # Show specific sources
            app_sources = ["Main", "AppController", "DeviceManager", "IEC61850Adapter", "EventLog", "SCDImport"]
            if source not in app_sources:
                # If source is likely a device name (not in this list), skip
                if not any(k in str(source) for k in ("Manager", "Main")):
                    return
        else:
            # Specific Device selected
            if source != self.source_filter:
                return
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
        elif level == "PACKET":
            color = "#569cd6" # Light Blue for packets
        else:
            color = "#d4d4d4"
        
        # Format the log entry
        # Escape message and preserve formatting using <pre>
        msg = message if isinstance(message, str) else str(message)
        escaped = html.escape(msg)
        entry_html = (
            f'<span style="color: #808080;">[{event["timestamp"]}]</span> '
            f'<span style="color: {color};">[{level}]</span> '
            f'<span style="color: #569cd6;">{event["source"]}:</span> '
            f'<pre style="white-space:pre-wrap;margin:0">{escaped}</pre>'
        )

        self.text_edit.append(entry_html)
        
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
