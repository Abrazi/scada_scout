#!/usr/bin/env python3
"""
Quick test to demonstrate file selection dialog for compressed SCD files
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel
from src.ui.widgets.scd_import_dialog import SCDImportDialog

def test_dialog():
    app = QApplication(sys.argv)
    
    # Create a simple window with button to test
    window = QWidget()
    window.setWindowTitle("Test SCD Import with Compressed Files")
    layout = QVBoxLayout()
    
    info = QLabel("Click the button below to test importing from compressed files.\n"
                  "Try selecting dubgg.sz to see the file selection dialog.")
    layout.addWidget(info)
    
    btn = QPushButton("Open SCD Import Dialog")
    
    def show_import_dialog():
        dialog = SCDImportDialog(window)
        dialog.exec()
    
    btn.clicked.connect(show_import_dialog)
    layout.addWidget(btn)
    
    window.setLayout(layout)
    window.resize(400, 150)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_dialog()
