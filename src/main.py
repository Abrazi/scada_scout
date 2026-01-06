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
    
    # No default devices added on startup
    # User must add manually or import SCD
    # Create Main Window
    window = MainWindow(device_manager)
    window.show()
    
    # Connect event logger to event log widget (Internal App Events)
    controller.event_logger.event_logged.connect(window.event_log_widget.log_event)
    
    # Connect Python Logging to event log widget
    from src.core.logging_handler import QtLogHandler
    qt_handler = QtLogHandler()
    qt_handler.new_record.connect(window.event_log_widget.log_event)
    
    # Add handler to root logger
    import logging
    logging.getLogger().addHandler(qt_handler)
    
    controller.event_logger.info("Application", "SCADA Scout started successfully")
    # Start the controller
    controller.start_application()
    
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
