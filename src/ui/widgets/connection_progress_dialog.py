from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QTimer

class ConnectionProgressDialog(QDialog):
    """
    Dialog showing connection progress with detailed status updates.
    """
    retry_requested = Signal()

    def __init__(self, device_name: str, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.setWindowTitle(f"Connecting to {device_name}")
        self.setModal(True)
        self.resize(500, 300)
        
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
        self.txt_log.setMaximumHeight(150)
        layout.addWidget(self.txt_log)
        
        # Button box
        btn_layout = QHBoxLayout()
        
        self.btn_retry = QPushButton("Retry")
        self.btn_retry.setVisible(False)
        self.btn_retry.clicked.connect(self._on_retry)
        btn_layout.addWidget(self.btn_retry)
        
        self.btn_close = QPushButton("Cancel") # Initially Cancel, becomes Close on completion
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
    def update_progress(self, message: str, percent: int):
        """Update the progress status."""
        self.lbl_status.setText(message)
        self.progress_bar.setValue(percent)
        self.txt_log.append(f"[{percent}%] {message}")
        
        if percent >= 100:
            self.lbl_status.setStyleSheet("color: green;")
            self.btn_close.setText("Close")
            self.btn_close.setEnabled(True)
            # Auto-close on success after a short delay
            QTimer.singleShot(1500, self.accept)
            
        elif percent == 0 and ("Error" in message or "failed" in message.lower()):
            self.lbl_status.setStyleSheet("color: red;")
            self.btn_close.setText("Close")
            self.btn_close.setEnabled(True)
            self.btn_retry.setVisible(True)
        else:
            # While in progress, ensure retry is hidden and status is normal
            self.lbl_status.setStyleSheet("")
            self.btn_retry.setVisible(False)

    def _on_retry(self):
        """Signal a retry and reset UI state."""
        self.btn_retry.setVisible(False)
        self.lbl_status.setStyleSheet("")
        self.lbl_status.setText("Retrying...")
        self.progress_bar.setValue(5)
        self.retry_requested.emit()
