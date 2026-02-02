#!/usr/bin/env python3
"""
Theme System Test Script
Tests Epic Dark and Bright theme switching functionality
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt

from src.ui.theme_manager import get_theme_manager
from src.ui.theme_presets import ColorRole, ThemeType


class ThemeTestWindow(QMainWindow):
    """Test window for theme switching."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCADA Scout - Theme Test")
        self.resize(800, 600)
        
        # Get theme manager
        self.theme_manager = get_theme_manager()
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Epic Theme System Test")
        title.setStyleSheet(f"""
            font-size: 24pt;
            font-weight: bold;
            color: {self.theme_manager.get_color(ColorRole.PRIMARY)};
        """)
        layout.addWidget(title, alignment=Qt.AlignCenter)
        
        # Status indicators
        layout.addWidget(QLabel("Device Status Indicators:"))
        
        status_connected = QLabel("● Device Connected")
        status_connected.setProperty("device_status", "connected")
        layout.addWidget(status_connected)
        
        status_disconnected = QLabel("● Device Disconnected")
        status_disconnected.setProperty("device_status", "disconnected")
        layout.addWidget(status_disconnected)
        
        status_connecting = QLabel("● Device Connecting")
        status_connecting.setProperty("device_status", "connecting")
        layout.addWidget(status_connecting)
        
        # Quality indicators
        layout.addWidget(QLabel("\nSignal Quality Indicators:"))
        
        quality_good = QLabel("● Quality: Good")
        quality_good.setProperty("quality", "good")
        layout.addWidget(quality_good)
        
        quality_bad = QLabel("● Quality: Bad")
        quality_bad.setProperty("quality", "bad")
        layout.addWidget(quality_bad)
        
        # Alarm indicators
        layout.addWidget(QLabel("\nAlarm Indicators:"))
        
        alarm_critical = QLabel("⚠ CRITICAL ALARM")
        alarm_critical.setProperty("alarm", "critical")
        layout.addWidget(alarm_critical)
        
        alarm_high = QLabel("⚠ High Priority Alarm")
        alarm_high.setProperty("alarm", "high")
        layout.addWidget(alarm_high)
        
        alarm_medium = QLabel("⚠ Medium Priority Alarm")
        alarm_medium.setProperty("alarm", "medium")
        layout.addWidget(alarm_medium)
        
        # Theme toggle buttons
        layout.addStretch()
        layout.addWidget(QLabel("\nTheme Controls:"))
        
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        dark_btn = QPushButton("Switch to Epic Dark")
        dark_btn.clicked.connect(lambda: self._switch_theme(ThemeType.DARK))
        button_layout.addWidget(dark_btn)
        
        bright_btn = QPushButton("Switch to Epic Bright")
        bright_btn.clicked.connect(lambda: self._switch_theme(ThemeType.BRIGHT))
        button_layout.addWidget(bright_btn)
        
        toggle_btn = QPushButton("Toggle Theme (Ctrl+Shift+T)")
        toggle_btn.setShortcut("Ctrl+Shift+T")
        toggle_btn.clicked.connect(self.theme_manager.toggle_theme)
        button_layout.addWidget(toggle_btn)
        
        # Danger button example
        danger_btn = QPushButton("Emergency Stop (Danger Button)")
        danger_btn.setProperty("class", "danger")
        danger_btn.clicked.connect(lambda: print("Emergency stop activated!"))
        button_layout.addWidget(danger_btn)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Update initial status
        self._update_status()
    
    def _switch_theme(self, theme_type: ThemeType):
        """Switch to specified theme."""
        self.theme_manager.set_theme(theme_type)
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme change event."""
        self._update_status()
        print(f"Theme changed to: {theme_name}")
    
    def _update_status(self):
        """Update status label with current theme."""
        current = self.theme_manager.get_current_theme().value
        self.status_label.setText(f"Current Theme: {current.title()}")
        self.status_label.setProperty("status", "info")
        
        # Force style update
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


def main():
    """Run the theme test."""
    app = QApplication(sys.argv)
    
    # Initialize and apply theme
    theme_manager = get_theme_manager()
    theme_manager.apply_to_application(app)
    
    # Create and show window
    window = ThemeTestWindow()
    window.show()
    
    print("=== Theme System Test ===")
    print("- Click buttons to switch themes")
    print("- Use Ctrl+Shift+T to toggle")
    print("- Watch status indicators change colors")
    print("========================")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
