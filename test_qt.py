import sys
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
from PySide6.QtCore import QTimer

def test_gui():
    print("Starting minimal GUI test...")
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Minimal Test")
    window.setCentralWidget(QLabel("If you see this, Qt works."))
    window.resize(400, 300)
    window.show()
    
    def check_visibility():
        print(f"Window is visible: {window.isVisible()}")
        if not window.isVisible():
            print("Window became invisible! Quitting.")
            app.quit()
    
    timer = QTimer()
    timer.timeout.connect(check_visibility)
    timer.start(500)
    
    # Quit after 5 seconds automatically so it doesn't hang the agent
    QTimer.singleShot(5000, lambda: (print("Test timed out (success)"), app.quit()))

    print("Calling app.exec()...")
    res = app.exec()
    print(f"app.exec() returned {res}")

if __name__ == "__main__":
    test_gui()
