from PySide6.QtWidgets import QDialog, QVBoxLayout, QProgressBar, QTextEdit, QPushButton, QLabel
from PySide6.QtCore import Qt, QTimer

class ImportProgressDialog(QDialog):
    """
    Shows progress and log messages during a long import process.
    Contains a progress bar and a text log area.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importing SCD...")
        self.setFixedSize(600, 400)
        self.setModal(True)
        # Remove close button to force completion
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        
        self.layout = QVBoxLayout(self)
        
        self.lbl_status = QLabel("Initializing import...")
        self.layout.addWidget(self.lbl_status)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.layout.addWidget(self.progress)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: monospace; padding: 5px;")
        self.layout.addWidget(self.log_area)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.setEnabled(False) # Disabled until finished
        self.btn_close.clicked.connect(self.accept)
        self.layout.addWidget(self.btn_close)
        
    def set_progress(self, value, max_val=None):
        if max_val:
            self.progress.setMaximum(max_val)
        self.progress.setValue(value)
        
    def add_log(self, message):
        self.log_area.append(message)
        # Scroll to bottom
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())
        # Update status label with last message
        self.lbl_status.setText(message)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
    def finish(self):
        self.progress.setValue(self.progress.maximum())
        self.lbl_status.setText("Import Complete.")
        self.btn_close.setEnabled(True)
