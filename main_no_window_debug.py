import sys
import os
import logging
import traceback

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("NO_WINDOW_DEBUG")

def main():
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        
        app = QApplication(sys.argv)
        
        from src.core.device_manager import DeviceManager
        from src.core.app_controller import AppController
        from src.ui.main_window import MainWindow
        
        print("Initializing app...")
        device_manager = DeviceManager()
        controller = AppController(device_manager)
        
        # Create but don't show the window
        print("Creating window...")
        window = MainWindow(device_manager, event_logger=controller.event_logger)
        
        # Quit after 10 seconds
        QTimer.singleShot(10000, lambda: (print("Success: App stayed alive for 10s"), app.quit()))
        
        print("Starting app.exec()...")
        res = app.exec()
        print(f"app.exec() returned {res}")
        sys.exit(res)
        
    except Exception as e:
        print(f"CRASH in main: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
