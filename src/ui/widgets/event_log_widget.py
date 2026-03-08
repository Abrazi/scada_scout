from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QCheckBox, QComboBox, QLineEdit, QLabel, QFileDialog, QMessageBox, QGridLayout
import subprocess
import os
from PySide6.QtCore import Qt, Signal as QtSignal, QObject
from PySide6.QtGui import QTextCursor, QColor
import html
import logging
from datetime import datetime
from src.core.packet_capture import PacketCaptureWorker
import psutil

from src.core.event_logger import EventLogger

class EventLogWidget(QWidget):
    """
    Widget for displaying diagnostic events and IEC 61850 transactions.
    """
    def __init__(self, device_manager=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Text display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # Use themed event log style from QSS (QTextEdit#eventLog)
        self.text_edit.setObjectName("eventLog")
        layout.addWidget(self.text_edit)
        
        # Filter bar (like Wireshark)
        filter_bar_layout = QHBoxLayout()
        
        lbl_filter = QLabel("Filter:")
        filter_bar_layout.addWidget(lbl_filter)
        
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText("Filter events (e.g., 'error', 'level:ERROR', 'source:DeviceName', 'connection')")
        self.le_filter.setMaximumHeight(25)
        self.le_filter.textChanged.connect(self._on_filter_text_changed)
        filter_bar_layout.addWidget(self.le_filter)
        
        self.btn_filter_clear = QPushButton("✕")
        self.btn_filter_clear.setMaximumWidth(30)
        self.btn_filter_clear.setToolTip("Clear filter")
        self.btn_filter_clear.clicked.connect(lambda: self.le_filter.clear())
        filter_bar_layout.addWidget(self.btn_filter_clear)
        
        layout.addLayout(filter_bar_layout)
        
        # Control buttons in two rows for better flexibility
        # Row 1: Basic controls
        row1_layout = QHBoxLayout()
        
        self.chk_verbose = QCheckBox("Show All Events")
        self.chk_verbose.setChecked(True)
        self.chk_verbose.stateChanged.connect(self._refresh_log_view)
        row1_layout.addWidget(self.chk_verbose)
        
        self.btn_pause = QPushButton("⏸️ Pause")
        self.btn_pause.setCheckable(True)
        self.btn_pause.clicked.connect(self._toggle_pause)
        row1_layout.addWidget(self.btn_pause)
        
        # Filter Source  — populated with All Sources / Application / separator / <device names>
        self.combo_source = QComboBox()
        self.combo_source.addItem("All Sources")
        self.combo_source.addItem("Application")
        self.combo_source.currentTextChanged.connect(self._apply_source_filter)
        self.combo_source.setMinimumWidth(300)  # Wider to show device details in dropdown
        row1_layout.addWidget(self.combo_source)
        
        # Device details label — shows connection info for selected device
        self.lbl_device_details = QLabel("")
        self.lbl_device_details.setStyleSheet("color: #808080; font-size: 9px; margin-left: 8px;")
        self.lbl_device_details.setMinimumWidth(200)
        row1_layout.addWidget(self.lbl_device_details)
        
        self.btn_clear = QPushButton("🗑️ Clear")
        self.btn_clear.clicked.connect(self.clear_log)
        row1_layout.addWidget(self.btn_clear)
        
        self.btn_export = QPushButton("💾 Export...")
        self.btn_export.clicked.connect(self._export_log)
        row1_layout.addWidget(self.btn_export)
        
        row1_layout.addStretch()
        layout.addLayout(row1_layout)

        # Row 2: Packet Capture Controls
        row2_layout = QHBoxLayout()
        
        self.btn_capture = QPushButton("📡 Capture")
        self.btn_capture.setCheckable(True)
        self.btn_capture.clicked.connect(self._toggle_capture)
        row2_layout.addWidget(self.btn_capture)

        # Capture type selector
        self.combo_capture_type = QComboBox()
        self.combo_capture_type.addItem("Network", "network")
        self.combo_capture_type.addItem("Serial", "serial")
        self.combo_capture_type.currentTextChanged.connect(self._on_capture_type_changed)
        row2_layout.addWidget(self.combo_capture_type)

        self.combo_capture_filter = QComboBox()
        self.combo_capture_filter.addItem("MMS (TCP 102)", "tcp port 102")
        self.combo_capture_filter.addItem("GOOSE (0x88b8)", "ether proto 0x88b8")
        self.combo_capture_filter.addItem("SV (0x88ba)", "ether proto 0x88ba")
        self.combo_capture_filter.addItem("All TCP", "tcp")
        self.combo_capture_filter.addItem("All Traffic", "")
        self.combo_capture_filter.setMinimumWidth(120)
        row2_layout.addWidget(self.combo_capture_filter)

        self.combo_iface = QComboBox()
        self.combo_iface.setMinimumWidth(120)
        row2_layout.addWidget(self.combo_iface)

        # Serial port selector (initially hidden)
        self.combo_serial_port = QComboBox()
        self.combo_serial_port.setMinimumWidth(120)
        self.combo_serial_port.hide()
        row2_layout.addWidget(self.combo_serial_port)

        # Serial baudrate selector (initially hidden)
        self.combo_serial_baud = QComboBox()
        self.combo_serial_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.combo_serial_baud.setCurrentText("9600")
        self.combo_serial_baud.setMaximumWidth(80)
        self.combo_serial_baud.hide()
        row2_layout.addWidget(self.combo_serial_baud)

        self.btn_refresh_ifaces = QPushButton("↻")
        self.btn_refresh_ifaces.setToolTip("Refresh Interfaces/Ports")
        self.btn_refresh_ifaces.setMaximumWidth(40)
        self.btn_refresh_ifaces.clicked.connect(self._populate_interfaces)
        row2_layout.addWidget(self.btn_refresh_ifaces)

        self.chk_log_file = QCheckBox("Log to File")
        self.chk_log_file.setChecked(False)
        row2_layout.addWidget(self.chk_log_file)

        self.le_log_file = QLineEdit()
        self.le_log_file.setPlaceholderText("packets.log")
        self.le_log_file.setMinimumWidth(120)
        row2_layout.addWidget(self.le_log_file)

        self.btn_browse_log = QPushButton("...")
        self.btn_browse_log.setToolTip("Browse for log file location")
        self.btn_browse_log.setMaximumWidth(40)
        self.btn_browse_log.clicked.connect(self._browse_log_file)
        row2_layout.addWidget(self.btn_browse_log)

        self.btn_open_log = QPushButton("📂")
        self.btn_open_log.setToolTip("Open log file")
        self.btn_open_log.setMaximumWidth(40)
        self.btn_open_log.clicked.connect(self._open_log_file)
        row2_layout.addWidget(self.btn_open_log)

        self.chk_log_json = QCheckBox("JSON")
        row2_layout.addWidget(self.chk_log_json)

        self.lbl_max_mb = QLabel("Max MB:")
        self.le_max_mb = QLineEdit()
        self.le_max_mb.setMaximumWidth(60)
        self.le_max_mb.setPlaceholderText("10")
        row2_layout.addWidget(self.lbl_max_mb)
        row2_layout.addWidget(self.le_max_mb)

        self.lbl_max_files = QLabel("Rot:")
        self.le_max_files = QLineEdit()
        self.le_max_files.setMaximumWidth(40)
        self.le_max_files.setPlaceholderText("5")
        row2_layout.addWidget(self.lbl_max_files)
        row2_layout.addWidget(self.le_max_files)

        self.btn_apply_rotation = QPushButton("Apply")
        self.btn_apply_rotation.setToolTip("Apply rotation settings")
        self.btn_apply_rotation.clicked.connect(self._apply_rotation_settings)
        row2_layout.addWidget(self.btn_apply_rotation)

        row2_layout.addStretch()
        layout.addLayout(row2_layout)

        # Populate interfaces initially
        self._populate_interfaces()

        self.is_paused = False
        self.source_filter = "All Sources"  # or specific device name
        self.text_filter = ""  # Free-text filter from filter bar
        self._known_device_names: set = set()  # updated by update_device_list()
        self._device_details: dict = {}  # Maps device name to config details
        self._last_event_sig = None
        
        self.capture_worker = PacketCaptureWorker()
        self.capture_worker.packet_captured.connect(self._on_packet_captured)
        self.capture_worker.error_occurred.connect(self._on_capture_error)
        
        # New: If logger is provided, connect to it
        self.event_logger = None

        # Apply saved defaults from settings (if any)
        try:
            from PySide6.QtCore import QSettings
            qs = QSettings("ScadaScout", "UI")
            # Default filter may be stored as label; try matching by text
            default_filter = qs.value("capture_default_filter", None)
            if default_filter:
                idx = self.combo_capture_filter.findText(default_filter)
                if idx >= 0:
                    self.combo_capture_filter.setCurrentIndex(idx)
            # Default interface
            default_iface = qs.value("capture_default_iface", "")
            if default_iface:
                # Will apply after populate; store and set after populate
                self._pending_default_iface = default_iface
            else:
                self._pending_default_iface = None
            # Logging defaults
            self.chk_log_file.setChecked(qs.value("capture_default_log", False, type=bool))
            self.le_log_file.setText(qs.value("capture_default_log_path", ""))
            self.chk_log_json.setChecked(qs.value("capture_default_json", False, type=bool))
            self.le_max_mb.setText(str(qs.value("capture_default_max_mb", 10)))
            self.le_max_files.setText(str(qs.value("capture_default_max_files", 5)))
        except Exception:
            self._pending_default_iface = None

        # Apply pending iface if set
        try:
            if hasattr(self, '_pending_default_iface') and self._pending_default_iface:
                # Populate interfaces then set selection if present
                self._populate_interfaces()
                # Set selection based on capture type
                capture_type = self.combo_capture_type.currentData()
                if capture_type == "network":
                    idx = self.combo_iface.findText(self._pending_default_iface)
                    if idx >= 0:
                        self.combo_iface.setCurrentIndex(idx)
        except Exception:
            pass

        # Initialize capture type UI
        self._on_capture_type_changed()

    def _toggle_capture(self):
        if self.btn_capture.isChecked():
            capture_type = self.combo_capture_type.currentData()
            
            if capture_type == "network":
                # Check if scapy is available before proceeding
                if not self.capture_worker._scapy_available:
                    import sys
                    if sys.platform.startswith('win'):
                        error_msg = f"Scapy is not installed. Error: {self.capture_worker._scapy_error}\n\nTo enable packet capture, install scapy:\n  pip install scapy\n\nOn Windows, you also need Npcap (installed with Wireshark)."
                    else:
                        error_msg = f"Scapy is not installed. Error: {self.capture_worker._scapy_error}\n\nTo enable packet capture, install scapy:\n  pip install scapy\n\nOn Linux, you may also need: sudo apt-get install tcpdump"
                    self.log_event("ERROR", "Network", error_msg)
                    self.btn_capture.setChecked(False)
                    QMessageBox.warning(self, "Scapy Not Available", error_msg)
                    return
                # Check raw-socket / pcap privileges (only relevant on Linux)
                priv_result = self._check_capture_privileges()
                if priv_result:
                    self.log_event("WARNING", "Network", priv_result)
                    QMessageBox.warning(self, "Insufficient Capture Privileges", priv_result)
                    self.btn_capture.setChecked(False)
                    return
            elif capture_type == "serial":
                # Check if pyserial is available
                if not self.capture_worker._scapy_available and not hasattr(self.capture_worker, '_serial_available'):
                    # We need to check pyserial availability
                    try:
                        import serial
                        self.capture_worker._serial_available = True
                    except ImportError:
                        error_msg = "pyserial is not installed. Install with: pip install pyserial"
                        self.log_event("ERROR", "Serial", error_msg)
                        self.btn_capture.setChecked(False)
                        QMessageBox.warning(self, "Serial Not Available", error_msg)
                        return
            
            filter_str = self.combo_capture_filter.currentData()
            
            # Apply logging and interface settings to worker
            log_to_file = self.chk_log_file.isChecked()
            log_path = self.le_log_file.text() if self.le_log_file.text() else None
            # If user requested logging but didn't provide a path, use default in cwd
            if log_to_file and not log_path:
                default_path = os.path.join(os.getcwd(), "capture.log")
                self.le_log_file.setText(default_path)
                log_path = default_path
            json_fmt = self.chk_log_json.isChecked()
            if log_to_file and log_path:
                try:
                    self.capture_worker.set_log_file(log_path, json_format=json_fmt)
                except Exception as e:
                    self.log_event("ERROR", "Capture", f"Failed to set log file: {e}")

            # Apply rotation settings now if provided
            try:
                max_mb = int(self.le_max_mb.text()) if self.le_max_mb.text() else None
                max_files = int(self.le_max_files.text()) if self.le_max_files.text() else None
                if max_mb is not None or max_files is not None:
                    mb_bytes = (max_mb * 1024 * 1024) if max_mb is not None else None
                    self.capture_worker.set_log_rotation(mb_bytes if mb_bytes is not None else 0, max_files if max_files is not None else 5)
            except Exception:
                pass

            if capture_type == "network":
                iface = self.combo_iface.currentText()
                if iface and iface != "(none)":
                    try:
                        self.capture_worker.set_interface(iface)
                    except Exception as e:
                        self.log_event("ERROR", "Network", f"Failed to set interface: {e}")
            else:  # serial
                serial_port = self.combo_serial_port.currentData()
                baudrate = int(self.combo_serial_baud.currentText())
                if serial_port:
                    try:
                        self.capture_worker.set_serial_port(serial_port, baudrate)
                    except Exception as e:
                        self.log_event("ERROR", "Serial", f"Failed to configure serial port: {e}")

            try:
                # --- RTU tap mode: try eavesdropping on an existing transport first ---
                if capture_type == "serial" and self.device_manager:
                    transport = self._find_rtu_transport()
                    if transport is not None:
                        if self.capture_worker.start_rtu_tap(transport):
                            port_name = getattr(getattr(transport, 'config', None), 'port', '?')
                            self.log_event("INFO", "Capture",
                                           f"Started RTU tap on {port_name} (eavesdrop mode — port stays open)")
                            self._update_capture_button_style(running=True)
                            return

                self.capture_worker.start_capture(filter_str, capture_type=capture_type)
                capture_desc = "network" if capture_type == "network" else f"serial ({self.combo_serial_port.currentData()}@{self.combo_serial_baud.currentText()})"
                self.log_event("INFO", "Capture", f"Started {capture_desc} capture with filter: {filter_str}")
                self._update_capture_button_style(running=True)
            except Exception as e:
                self.log_event("ERROR", "Capture", f"Failed to start capture: {e}")
                QMessageBox.critical(self, "Capture Error", f"Failed to start capture: {e}")
                self.btn_capture.setChecked(False)
                self._update_capture_button_style(running=False, error=True)
        else:
            self.capture_worker.stop_capture()
            self.log_event("INFO", "Capture", "Stopped capture")
            self._update_capture_button_style(running=False)

    def _find_rtu_transport(self):
        """Search connected devices for a Modbus RTU transport that is open.

        Returns the first open SerialTransport (or any transport with
        add_tap_callback), or None.
        """
        if not self.device_manager:
            return None
        try:
            for device in self.device_manager.get_all_devices():
                protocol = self.device_manager.get_protocol(device.config.name)
                if protocol is None:
                    continue
                transport = getattr(protocol, 'transport', None)
                if transport is None:
                    continue
                if hasattr(transport, 'add_tap_callback') and getattr(transport, 'is_open', False):
                    return transport
        except Exception:
            pass
        return None

    def _on_packet_captured(self, summary: str):
        # Determine if this is a network or serial packet
        if "[SERIAL]" in summary:
            self.log_event("PACKET", "Serial", summary)
        else:
            self.log_event("PACKET", "Network", summary)

    def _update_capture_button_style(self, running: bool, error: bool = False):
        """Visually update the capture button to indicate running/stopped/error."""
        # Use themed button classes instead of inline styles
        def apply_button_class(btn, cls):
            if cls:
                btn.setProperty("class", cls)
            else:
                btn.setProperty("class", "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if error:
            apply_button_class(self.btn_capture, "danger")
            self.btn_capture.setText("📡 Capture")
            return

        if running:
            apply_button_class(self.btn_capture, "success")
            self.btn_capture.setText("📡 Capturing...")
        else:
            apply_button_class(self.btn_capture, None)
            self.btn_capture.setText("📡 Capture")

    def _check_capture_privileges(self) -> str:
        """Check if current process has packet capture privileges.
        Returns error message string if privileges insufficient, or empty string if OK.
        On Windows, this always returns empty (privilege check happens at capture time).
        On Linux, tests AF_PACKET socket creation.
        """
        import sys
        
        # On Windows, Npcap handles privileges - check at runtime
        if sys.platform.startswith('win'):
            return ""  # Don't pre-check on Windows

        # If dumpcap is selected (or auto with dumpcap available), skip raw-socket check
        try:
            preferred = getattr(self.capture_worker, "_preferred_backend", "auto")
            dumpcap_available = bool(getattr(self.capture_worker, "_dumpcap_path", None))
            if preferred == "dumpcap" or (preferred == "auto" and dumpcap_available):
                return ""
        except Exception:
            pass
        
        # On Linux/Unix, try to create a raw packet socket
        try:
            import socket
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3))
            s.close()
            return ""  # Success
        except AttributeError:
            # AF_PACKET not available (not Linux)
            return ""
        except PermissionError:
            # Linux: insufficient privileges
            import os
            import shutil
            python_path = os.path.realpath(sys.executable)
            dumpcap_path = shutil.which("dumpcap") or "/usr/bin/dumpcap"
            warn = (
                "Current user lacks privileges to capture packets on Linux.\n\n"
                "Solutions:\n"
                "1. Use dumpcap (recommended):\n"
                "   sudo apt-get install wireshark\n"
                f"   sudo setcap 'cap_net_raw,cap_net_admin+eip' {dumpcap_path}\n\n"
                "2. Grant capture capabilities to the real Python interpreter (run once):\n"
                f"   sudo setcap 'cap_net_raw,cap_net_admin+eip' {python_path}\n\n"
                "3. Run the application with sudo (not recommended)\n\n"
                "Capture will likely fail without one of these.\n\n"
                "Note: If dumpcap is already installed and configured on your system,\n"
                "you can ignore this warning and select the dumpcap backend for capture."
            )
            return warn
        except Exception:
            # Other error - allow attempt (might work with dumpcap)
            return ""

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

    def _populate_interfaces(self):
        """Populate network interfaces or serial ports based on capture type."""
        capture_type = self.combo_capture_type.currentData()
        
        if capture_type == "network":
            self.combo_iface.clear()
            self.combo_iface.show()
            self.combo_serial_port.hide()
            self.combo_serial_baud.hide()
            
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
        else:  # serial
            self.combo_iface.hide()
            self.combo_serial_port.show()
            self.combo_serial_baud.show()
            
            self.combo_serial_port.clear()
            try:
                ports = self.capture_worker.get_available_serial_ports()
                if not ports:
                    self.combo_serial_port.addItem("(none)")
                    return
                # Add an empty option for default
                self.combo_serial_port.addItem("")
                for device, description in ports:
                    display_text = f"{device} - {description}" if description else device
                    self.combo_serial_port.addItem(display_text, device)
            except Exception:
                self.combo_serial_port.addItem("(none)")

    def _on_capture_type_changed(self):
        """Handle capture type change between network and serial."""
        self._populate_interfaces()
        
        # Update filter options based on type
        self.combo_capture_filter.clear()
        capture_type = self.combo_capture_type.currentData()
        
        if capture_type == "network":
            self.combo_capture_filter.addItem("MMS (TCP 102)", "tcp port 102")
            self.combo_capture_filter.addItem("GOOSE (0x88b8)", "ether proto 0x88b8")
            self.combo_capture_filter.addItem("SV (0x88ba)", "ether proto 0x88ba")
            self.combo_capture_filter.addItem("All TCP", "tcp")
            self.combo_capture_filter.addItem("All Traffic", "")
        else:  # serial
            self.combo_capture_filter.addItem("Modbus RTU", "modbus")
            self.combo_capture_filter.addItem("All Serial", "")

    def _populate_ifaces(self):
        """Legacy method for backward compatibility."""
        self._populate_interfaces()

    def _on_capture_error(self, err: str):
        self.log_event("ERROR", "Network", err)
        # Uncheck button if crashed
        if self.btn_capture.isChecked():
             self.btn_capture.setChecked(False)
        
        # Show user-friendly message for common issues
        if "Scapy not available" in err or "No module named 'scapy'" in err:
            QMessageBox.warning(self, "Packet Capture Error", 
                f"{err}\n\nPlease install scapy:\n  pip install scapy")
        elif "permission" in err.lower() or "access" in err.lower():
            QMessageBox.warning(self, "Packet Capture Error", 
                f"{err}\n\nPacket capture requires elevated privileges.\nOn Linux: Try running with sudo\nOn Windows: Run as Administrator")

    def update_device_list(self, devices):
        """Updates the source filter with available devices.
        
        Displays device names with connection details (IP:port or serial port info).
        Stores device configs for filtering later.
        """
        # preserve current selection
        current = self.combo_source.currentText()

        self.combo_source.blockSignals(True)
        self.combo_source.clear()
        self.combo_source.addItem("All Sources")
        self.combo_source.addItem("Application")
        self.combo_source.insertSeparator(2)

        self._known_device_names = set()
        self._device_details.clear()
        
        for dev in devices:
            config = dev.config if hasattr(dev, 'config') else None
            if not config:
                continue
                
            name = config.name
            self._known_device_names.add(name)
            
            # Build display string with device details
            display_text = self._format_device_display(config)
            
            # Store device config for later reference
            self._device_details[name] = {
                'config': config,
                'display_text': display_text
            }
            
            self.combo_source.addItem(display_text)

        # Debug output
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Event log: Updated device list with {len(self._known_device_names)} devices")
        logger.debug(f"Event log: Known device names: {self._known_device_names}")

        # restore selection if possible
        idx = self.combo_source.findText(current)
        if idx >= 0:
            self.combo_source.setCurrentIndex(idx)
        else:
            self.combo_source.setCurrentIndex(0)

        self.combo_source.blockSignals(False)

    def _format_device_display(self, config) -> str:
        """Format device display string with connection details.
        
        Examples:
        - "Device1 (IEC61850 | 192.168.1.100:102)"
        - "ModbusRTU (Serial | /dev/ttyUSB0@9600)"
        - "ModbusTCP (TCP | 192.168.1.50:502)"
        """
        name = config.name if hasattr(config, 'name') else "Unknown"
        device_type = config.device_type.value if hasattr(config, 'device_type') else "Unknown"
        
        # Build connection detail based on device type and configuration
        detail = ""
        
        # Check for serial-based connections (Modbus RTU, IEC104)
        if hasattr(config, 'serial_port') and config.serial_port:
            baudrate = getattr(config, 'serial_baudrate', 9600)
            detail = f"{config.serial_port}@{baudrate}"
        # Check for network-based connections
        elif hasattr(config, 'ip_address') and config.ip_address:
            ip = config.ip_address
            port = getattr(config, 'port', None)
            if port:
                detail = f"{ip}:{port}"
            else:
                detail = ip
        
        # Format final display string
        if detail:
            return f"{name} ({device_type} | {detail})"
        else:
            return f"{name} ({device_type})"

    def update_font(self, font_family="Consolas", font_size=9):
        """Update the console font for the event log."""
        from PySide6.QtGui import QFont
        font = QFont(font_family, font_size)
        self.text_edit.setFont(font)

    def _toggle_pause(self):
        self.is_paused = self.btn_pause.isChecked()
        self.btn_pause.setText("Resume" if self.is_paused else "Pause")

    def _on_filter_text_changed(self, text):
        """Handle filter text box changes (Wireshark-style filter)."""
        self.text_filter = text.strip()
        self._refresh_log_view()

    def _apply_filter_expression(self, event) -> bool:
        """Parse and apply text filter expression to an event.
        
        Supports syntax like:
        - "error" - case-insensitive keyword search in message
        - "level:ERROR" - filter by log level
        - "source:DeviceName" - filter by source
        - "connection" - search in message
        - Multiple terms: "error connection" (AND logic)
        
        Returns True if event passes filter, False otherwise.
        """
        if not self.text_filter:
            return True  # No filter applied
        
        level = event.get('level', '')
        source = event.get('source', '')
        message = event.get('message', '')
        
        # Parse filter expression
        terms = self.text_filter.split()
        
        for term in terms:
            term_lower = term.lower()
            
            # Parse special filter formats
            if ':' in term:
                key, value = term.split(':', 1)
                key_lower = key.lower()
                value_lower = value.lower()
                
                if key_lower == 'level':
                    # Filter by level: level:ERROR, level:WARNING, etc.
                    if level.lower() != value_lower:
                        return False
                elif key_lower == 'source':
                    # Filter by source: source:DeviceName
                    if value_lower not in source.lower():
                        return False
                elif key_lower == 'msg':
                    # Filter by message content: msg:keyword
                    if value_lower not in message.lower():
                        return False
            else:
                # Plain text search in all fields (message, source)
                message_lower = message.lower() if message else ""
                source_lower = source.lower() if source else ""
                
                # Match if term appears in message OR source
                if not (term_lower in message_lower or term_lower in source_lower):
                    return False
        
        return True

    def _apply_source_filter(self, text):
        # Extract device name from display text
        # Display format: "DeviceName (Type | Details)" or "DeviceName (Type)"
        # If it's one of the special items (All Sources, Application), use as-is
        if text in ("All Sources", "Application"):
            self.source_filter = text
            self.lbl_device_details.setText("")
        else:
            # Extract device name: everything before the first " ("
            if " (" in text:
                device_name = text.split(" (")[0]
                self.source_filter = device_name
            else:
                self.source_filter = text
                device_name = text
            
            # Update device details label
            if device_name in self._device_details:
                detail_info = self._device_details[device_name]
                config = detail_info['config']
                detail_text = self._build_device_detail_text(config)
                self.lbl_device_details.setText(detail_text)
                # Debug: show what we're filtering for
                import logging
                logging.getLogger(__name__).debug(f"Filter set to device: {device_name}")
            else:
                self.lbl_device_details.setText("")
                import logging
                logging.getLogger(__name__).warning(f"Device '{device_name}' not found in device_details. Known devices: {list(self._device_details.keys())}")
        
        self._refresh_log_view()

    def _build_device_detail_text(self, config) -> str:
        """Build detailed connection information text for display.
        
        Returns a formatted string like:
        "IP: 192.168.1.100, Port: 102, Type: IEC61850"
        """
        details = []
        
        # Device type
        if hasattr(config, 'device_type'):
            details.append(f"Type: {config.device_type.value}")
        
        # IP and port for network devices
        if hasattr(config, 'ip_address') and config.ip_address:
            details.append(f"IP: {config.ip_address}")
            if hasattr(config, 'port') and config.port:
                details.append(f"Port: {config.port}")
        
        # Serial port info for serial devices
        if hasattr(config, 'serial_port') and config.serial_port:
            baudrate = getattr(config, 'serial_baudrate', 9600)
            parity = getattr(config, 'serial_parity', 'N')
            stopbits = getattr(config, 'serial_stopbits', 1)
            details.append(f"Port: {config.serial_port}@{baudrate},{parity},{int(stopbits)}")
        
        # Description if available
        if hasattr(config, 'description') and config.description:
            details.append(f"Desc: {config.description}")
        
        return " | ".join(details)

    def set_event_logger(self, logger: EventLogger):
        """Connects the widget to a core event logger."""
        self.event_logger = logger
        self.event_logger.event_logged.connect(self.log_event)
        self.event_logger.history_cleared.connect(self._on_history_cleared)
        # Load existing history
        self._refresh_log_view()

    def _on_history_cleared(self):
        self._refresh_log_view()

    def _refresh_log_view(self):
        """Re-populates the text area based on current filter."""
        self.text_edit.clear()
        if not self.event_logger:
            return
            
        for event in self.event_logger.get_history():
            self._display_event(event)

    def log_event(self, level: str, source: str, message: str):
        """Processes an event from the logger or direct call."""
        if self.is_paused:
            return

        signature = f"{level}|{source}|{message}"
        if signature == self._last_event_sig:
            return
        self._last_event_sig = signature

        # Create a display-only event dict if it wasn't already in history
        # (Though usually this will be called via Signal)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        event = {
            'timestamp': timestamp,
            'level': level,
            'source': source,
            'message': message
        }
        
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
            pass  # show everything

        elif self.source_filter == "Application":
            # "Application" means: NOT a device event.
            # Any source that matches a known device name is excluded.
            if self._known_device_names and source in self._known_device_names:
                return
            # Also exclude packet events (they belong to capture, not application)
            if level == "PACKET":
                return

        else:
            # Specific device selected
            # Match if source equals device name or contains it in some way
            device_name = self.source_filter
            source_str = source if source else ""
            
            # Exact match on device name
            is_match = (source_str == device_name)
            
            # Also match if source contains device name (case-insensitive substring match)
            if not is_match and device_name:
                source_lower = source_str.lower()
                device_lower = device_name.lower()
                # Use substring matching for flexibility
                is_match = (device_lower in source_lower or source_lower in device_lower)
            
            # Skip if no match
            if not is_match:
                return
        
        # Text filter (Wireshark-style)
        if not self._apply_filter_expression(event):
            return
                
        if level == "ERROR":
            color = "#f48771"  # Red
        elif level == "WARNING":
            color = "#dcdcaa"  # Yellow  
        elif level == "INFO":
            color = "#4fc1ff"  # Bright Cyan - More visible for success messages
        elif level == "DEBUG":
            color = "#9cdcfe"  # Light Blue
        elif level == "TRANSACTION":
            color = "#c586c0"  # Purple
        elif level == "PACKET":
            color = "#569cd6"  # Blue for packets
        else:
            color = "#d4d4d4"  # Gray
        
        # Format the log entry
        # Normalize message: trim, collapse whitespace/newlines, and truncate for tidy display
        import re
        full_msg = message if isinstance(message, str) else str(message)
        full_msg = full_msg.strip()
        # Collapse any sequence of whitespace/newlines into single space for compact display
        compact = re.sub(r"\s+", " ", full_msg)
        # Truncate long messages for the log view, keep full in tooltip
        max_len = 300
        display_msg = compact if len(compact) <= max_len else compact[:max_len] + "..."
        escaped_display = html.escape(display_msg)
        escaped_full = html.escape(full_msg)

        # Make success messages stand out with bold text for ✅ indicators
        title_attr = f' title="{escaped_full}"' if escaped_full else ''
        if '✅' in full_msg:
            entry_html = (
                f'<span style="color: #808080;">[{event["timestamp"]}]</span> '
                f'<span style="color: {color}; font-weight: bold;">[{level}]</span> '
                f'<span style="color: #569cd6; font-weight: bold;">{event["source"]}:</span> '
                f'<pre style="white-space:pre-wrap;margin:0; color: {color}; font-weight: bold;"{title_attr}>{escaped_display}</pre>'
            )
        else:
            entry_html = (
                f'<span style="color: #808080;">[{event["timestamp"]}]</span> '
                f'<span style="color: {color};">[{level}]</span> '
                f'<span style="color: #569cd6;">{event["source"]}:</span> '
                f'<pre style="white-space:pre-wrap;margin:0"{title_attr}>{escaped_display}</pre>'
            )

        self.text_edit.append(entry_html)
        
        # Auto-scroll to bottom
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)
    
    def clear_log(self):
        """Clear all log entries."""
        if self.event_logger:
            self.event_logger.clear_history()
        else:
            self.text_edit.clear()
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
            except Exception as e:
                pass
