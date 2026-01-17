from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QComboBox, QPushButton, QPlainTextEdit, QLabel, QCheckBox, QSpinBox, QLineEdit
from PySide6.QtCore import Qt
import shutil
import os
import sys

class NetworkSettingsPanel(QWidget):
    """Reusable network/packet-capture settings panel used by SettingsDialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Capture backend group
        capture_group = QGroupBox("Packet Capture")
        capture_layout = QFormLayout(capture_group)

        self.capture_backend = QComboBox()
        self.capture_backend.addItems(["Auto", "AsyncSniffer (Scapy)", "dumpcap (FIFO)"])

        cb_container = QWidget()
        cb_layout = QHBoxLayout(cb_container)
        cb_layout.setContentsMargins(0,0,0,0)
        cb_layout.addWidget(self.capture_backend)

        self._setcap_btn = QPushButton("Copy setcap")
        self._setcap_btn.setFlat(True)
        cb_layout.addWidget(self._setcap_btn)

        self._open_terminal_btn = QPushButton("Open terminal & paste")
        self._open_terminal_btn.setFlat(True)
        cb_layout.addWidget(self._open_terminal_btn)

        capture_layout.addRow("Capture Backend:", cb_container)

        self._setcap_text = QPlainTextEdit()
        self._setcap_text.setReadOnly(True)
        self._setcap_text.setFixedHeight(140)
        capture_layout.addRow("Setcap Commands:", self._setcap_text)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFlat(True)
        capture_layout.addRow("", self._refresh_btn)

        self._dumpcap_warning_label = QLabel("")
        self._dumpcap_warning_label.setWordWrap(True)
        self._dumpcap_warning_label.setVisible(False)
        capture_layout.addRow("", self._dumpcap_warning_label)

        layout.addWidget(capture_group)

        # Defaults for capture widget behavior
        defaults_group = QGroupBox("Capture Defaults")
        defaults_layout = QFormLayout(defaults_group)

        self.default_filter = QComboBox()
        self.default_filter.addItems(["MMS (TCP 102)", "GOOSE (0x88b8)", "SV (0x88ba)", "All TCP", "All Traffic"])
        defaults_layout.addRow("Default Filter:", self.default_filter)

        self.default_iface = QLineEdit()
        self.default_iface.setPlaceholderText("(empty = auto detect)")
        defaults_layout.addRow("Default Interface:", self.default_iface)

        self.default_log_to_file = QCheckBox("Log to File by default")
        defaults_layout.addRow("", self.default_log_to_file)

        self.default_log_path = QLineEdit()
        self.default_log_path.setPlaceholderText("packets.log")
        defaults_layout.addRow("Default Log Path:", self.default_log_path)

        self.default_json = QCheckBox("Log JSON by default")
        defaults_layout.addRow("", self.default_json)

        self.default_max_mb = QSpinBox()
        self.default_max_mb.setRange(1, 1024)
        self.default_max_mb.setValue(10)
        defaults_layout.addRow("Max MB (rotate):", self.default_max_mb)

        self.default_max_files = QSpinBox()
        self.default_max_files.setRange(1, 50)
        self.default_max_files.setValue(5)
        defaults_layout.addRow("Rotation files:", self.default_max_files)

        layout.addWidget(defaults_group)

        layout.addStretch()
