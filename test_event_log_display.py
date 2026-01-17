#!/usr/bin/env python3
"""
Test script to demonstrate improved event log display with success messages.
Shows various message types with proper formatting and colors.
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from src.ui.widgets.event_log_widget import EventLogWidget

class EventLogTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Event Log - Success Message Display Test")
        self.setGeometry(100, 100, 1000, 600)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        self.event_log = EventLogWidget()
        layout.addWidget(self.event_log)
        
        # Simulate various events
        self.simulate_events()
    
    def simulate_events(self):
        # Application startup
        self.event_log.log_event("INFO", "Main", "SCADA Scout application started")
        
        # Device connection
        self.event_log.log_event("INFO", "DeviceManager", "Connecting to IEC 61850 device...")
        
        # Dynamic model creation messages
        self.event_log.log_event("INFO", "IEC61850Server", "Loading model for GPS01GPC01UPM01FCB01 from test.icd")
        self.event_log.log_event("INFO", "IEC61850Server", "Creating dynamic model from parsed SCD/ICD...")
        
        # Success message with statistics (NEW FORMAT)
        success_msg = (
            "✅ Successfully created dynamic model from SCD/ICD\n"
            "   IED: GPS01GPC01UPM01FCB01\n"
            "   Logical Devices: 33\n"
            "   Logical Nodes: 203\n"
            "   Total Attributes: 7898"
        )
        self.event_log.log_event("INFO", "IEC61850Server", success_msg)
        
        # Server start success
        self.event_log.log_event(
            "INFO",
            "IEC61850Server",
            "✅ Started IEC 61850 server 'GPS01GPC01UPM01FCB01' on 127.0.0.1:10002"
        )
        
        # Some normal operations
        self.event_log.log_event("INFO", "WatchList", "Added 5 signals to watch list")
        self.event_log.log_event("TRANSACTION", "IEC61850", "Read: GPS01GPC01UPM01FCB01/LLN0$ST$Mod$stVal = 1")
        
        # Warning example
        self.event_log.log_event("WARNING", "ModbusSlave", "Register 40001 requested but not mapped")
        
        # Error example (for contrast)
        self.event_log.log_event("ERROR", "Network", "Connection timeout after 5 seconds")
        
        # More success messages
        self.event_log.log_event(
            "INFO",
            "Gateway",
            "✅ Protocol gateway started: IEC61850 → Modbus TCP mapping active"
        )
        
        self.event_log.log_event("DEBUG", "Parser", "Parsed 203 logical nodes from SCD file")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EventLogTestWindow()
    window.show()
    sys.exit(app.exec())
