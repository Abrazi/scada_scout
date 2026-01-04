import sys
import os

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.core.device_manager import DeviceManager
from src.core.app_controller import AppController
import logging

logging.basicConfig(level=logging.INFO)

def main():
    """
    Application Entry Point.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Scada Scout")
    
    # Core Logic Initialization
    device_manager = DeviceManager()
    controller = AppController(device_manager)
    
    window = MainWindow(device_manager)
    
    # Start the controller
    controller.start_application()
    
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
