import sys
import os
import logging
import traceback

# Ensure src is in python path (current dir is root)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Basic logging setup
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("scada_scout")

def main():
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        
        # Initialize Application
        print("Initializing QApplication...")
        app = QApplication(sys.argv)
        app.setApplicationName("Scada Scout")
        
        # Load Core Components
        from src.core.device_manager import DeviceManager
        from src.core.app_controller import AppController
        from src.ui.main_window import MainWindow
        from src.core.logging_handler import QtLogHandler
        
        print("Initializing core...")
        device_manager = DeviceManager()
        controller = AppController(device_manager)
        
        print("Creating window...")
        window = MainWindow(device_manager, event_logger=controller.event_logger)
        
        # Connect Logging
        qt_handler = QtLogHandler()
        if hasattr(window, 'event_log_widget'):
            qt_handler.new_record.connect(window.event_log_widget.log_event)
        logging.getLogger().addHandler(qt_handler)
        
        controller.event_logger.info("Application", "SCADA Scout started successfully")
        
        # Start Controller
        print("Starting controller...")
        controller.start_application()
        
        # Ensure cleanup
        app.aboutToQuit.connect(controller.shutdown)
        
        # Apply Settings
        try:
            window._apply_settings()
        except Exception:
            pass
            
        print("Showing window...")
        window.show()
        
        # Keep-alive
        def heart_beat():
            pass
        timer = QTimer()
        timer.timeout.connect(heart_beat)
        timer.start(1000)
        
        print("Starting app.exec()...")
        res = app.exec()
        print(f"app.exec() returned {res}")
        sys.exit(res)
        
    except Exception as e:
        print(f"CRASH: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
