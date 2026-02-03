import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def main():
    print("Initializing QApplication...")
    app = QApplication(sys.argv)
    
    from src.ui.main_window import MainWindow
    # Mocking dependencies
    class Mock: pass
    dm = Mock()
    dm.device_added = Mock()
    dm.device_added.connect = lambda x: None
    dm.device_removed = Mock()
    dm.device_removed.connect = lambda x: None
    dm.device_updated = Mock()
    dm.device_updated.connect = lambda x: None
    dm.device_renamed = Mock()
    dm.device_renamed.connect = lambda x: None
    dm.get_all_devices = lambda: []
    
    print("Creating window...")
    try:
        window = MainWindow(dm)
        print("Showing window...")
        window.show()
        print("Starting app.exec()...")
        res = app.exec()
        print(f"app.exec() returned {res}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
