from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit
from PySide6.QtCore import Qt

class ConnectionProgressDialog(QDialog):
    """
    Dialog showing connection progress with detailed status updates.
    """
    def __init__(self, device_name: str, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.setWindowTitle(f"Connecting to {device_name}")
        self.setModal(True)
        self.resize(500, 250)
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Device name label
        self.lbl_device = QLabel(f"<b>Device:</b> {self.device_name}")
        layout.addWidget(self.lbl_device)
        
        # Current status label
        self.lbl_status = QLabel("Initializing...")
        layout.addWidget(self.lbl_status)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Detailed log (expandable)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(100)
        layout.addWidget(self.txt_log)
        
        # Close button (disabled until complete or error)
        self.btn_close = QPushButton("Close")
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close)
        
    def update_progress(self, message: str, percent: int):
        """Update the progress status."""
        self.lbl_status.setText(message)
        self.progress_bar.setValue(percent)
        self.txt_log.append(f"[{percent}%] {message}")
        
        # Enable close button if complete or error
        if percent >= 100 or percent == 0:
            self.btn_close.setEnabled(True)
            if percent == 0 and "Error" in message:
                self.lbl_status.setStyleSheet("color: red;")
            elif percent >= 100:
                self.lbl_status.setStyleSheet("color: green;")
