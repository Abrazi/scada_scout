#!/usr/bin/env python3
"""
Simple diagnostic to verify event logger is working correctly
"""
from PySide6.QtCore import QCoreApplication
import sys

# Create Qt application (required for signals)
app = QCoreApplication(sys.argv)

from src.ui.widgets.event_log_widget import EventLogger

# Create event logger
event_logger = EventLogger()

received_events = []

def on_event(level, source, message):
    received_events.append((level, source, message))
    print(f"[{level}] {source}: {message}")

# Connect to signal
event_logger.event_logged.connect(on_event)

# Test various message types
print("Testing Event Logger:")
print("=" * 70)

event_logger.info("TestSource", "Test info message")
event_logger.warning("TestSource", "Test warning message")
event_logger.error("TestSource", "Test error message")
event_logger.info("TestSource", "✅ Success message with checkmark")

print("=" * 70)
print(f"\nTotal events received: {len(received_events)}")

for level, source, msg in received_events:
    print(f"  - [{level}] {source}: {msg[:50]}...")

print("\nEvent Logger is working correctly!" if len(received_events) == 4 else "\n❌ Event Logger NOT working!")
