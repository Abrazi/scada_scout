from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QTextEdit, QLabel, QScrollArea, QWidget
from PySide6.QtCore import Qt

class ScrollableMessageBox(QDialog):
    """
    A custom MessageBox that allows scrolling for long text content.
    Useful for displaying extensive error logs or import reports.
    """
    def __init__(self, title, message, details=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Message Label
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setProperty("class", "heading")
        layout.addWidget(lbl)
        
        # Details Area (Scrollable)
        if details:
            self.txt_details = QTextEdit()
            self.txt_details.setReadOnly(True)
            self.txt_details.setPlainText(details)
            layout.addWidget(self.txt_details)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

def show_scrollable_error(parent, title, message, details):
    """Helper to show the dialog."""
    dlg = ScrollableMessageBox(title, message, details, parent)
    # QDialog doesn't have setIcon like QMessageBox. 
    # Just execute the dialog.
    dlg.exec()
