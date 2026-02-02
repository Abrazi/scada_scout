"""
Epic Dark & Bright Theme System - Usage Guide
==============================================

The SCADA Scout application now includes a professional theming system with
Epic Dark and Epic Bright themes optimized for SCADA visualization.

## Features

✅ Two professionally designed themes:
   - Epic Dark: Optimized for 24/7 control room operation
   - Epic Bright: Optimized for daylight operation
   
✅ SCADA-specific color roles:
   - Alarm colors (Critical, High, Medium, Low)
   - Quality indicators (Good, Bad, Questionable, Not Connected)
   - Device status (Connected, Disconnected, Connecting, Error)
   
✅ Persistent settings using QSettings
✅ Live theme switching without restart
✅ Keyboard shortcuts (Ctrl+Shift+T to toggle)
✅ Smooth color transitions (200ms)
✅ High contrast for readability

## How to Use

### 1. Switch Themes via Menu

Go to: **View → Theme → [Epic Dark | Epic Bright | Toggle Theme]**

Or use keyboard shortcut: **Ctrl+Shift+T** to toggle

### 2. Programmatically Use Theme Colors in Widgets

```python
from src.ui.theme_manager import get_theme_manager
from src.ui.theme_presets import ColorRole

# Get theme manager instance
theme = get_theme_manager()

# Get specific colors
alarm_color = theme.get_color(ColorRole.ALARM_CRITICAL)
success_color = theme.get_color(ColorRole.SUCCESS)
primary_color = theme.get_color(ColorRole.PRIMARY)

# Apply to widget
widget.setStyleSheet(f"color: {alarm_color};")

# Or use convenience methods
status_color = theme.get_status_color("connected")  # Returns green
alarm_color = theme.get_alarm_color("critical")    # Returns red

# Check current theme
if theme.is_dark_theme():
    print("Dark mode is active")
```

### 3. Use Property-Based Styling (Recommended)

For consistent styling across the app, use Qt properties instead of
direct styling:

```python
# Set properties on QLabel
status_label = QLabel("Connected")
status_label.setProperty("device_status", "connected")

# The stylesheet will automatically apply the correct color:
# QLabel[device_status="connected"] { color: #00C853; }

# For alarms
alarm_label = QLabel("Critical Alarm")
alarm_label.setProperty("alarm", "critical")

# For quality indicators
quality_label = QLabel("Good")
quality_label.setProperty("quality", "good")
```

### 4. Create Theme-Aware Custom Widgets

```python
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from src.ui.theme_manager import get_theme_manager
from src.ui.theme_presets import ColorRole

class StatusIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        
        # Connect to theme changes
        self.theme.theme_changed.connect(self._on_theme_changed)
        
        # Create UI
        self.layout = QVBoxLayout(self)
        self.status_label = QLabel("Status: OK")
        self.layout.addWidget(self.status_label)
        
        # Apply initial theme
        self._apply_theme()
    
    def _apply_theme(self):
        # Use theme colors
        bg_color = self.theme.get_color(ColorRole.SURFACE)
        text_color = self.theme.get_color(ColorRole.TEXT_PRIMARY)
        success_color = self.theme.get_color(ColorRole.SUCCESS)
        
        self.setStyleSheet(f'''
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLabel {{
                color: {success_color};
                font-weight: bold;
            }}
        ''')
    
    def _on_theme_changed(self, theme_name):
        # Reapply theme when user switches
        self._apply_theme()
```

## Available Color Roles

### Base Colors
- BACKGROUND, SURFACE, SURFACE_VARIANT

### Text Colors
- TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED

### Status Colors
- SUCCESS, WARNING, ERROR, INFO

### SCADA-Specific Colors
- ALARM_CRITICAL, ALARM_HIGH, ALARM_MEDIUM, ALARM_LOW, ALARM_ACKNOWLEDGED
- QUALITY_GOOD, QUALITY_BAD, QUALITY_QUESTIONABLE, QUALITY_NOT_CONNECTED
- DEVICE_CONNECTED, DEVICE_DISCONNECTED, DEVICE_CONNECTING, DEVICE_ERROR

### UI Elements
- PRIMARY, PRIMARY_HOVER, PRIMARY_PRESSED
- BORDER, BORDER_FOCUS
- SELECTION, SELECTION_TEXT
- BUTTON_BACKGROUND, BUTTON_HOVER, BUTTON_PRESSED

### Chart Colors
- CHART_BACKGROUND, CHART_GRID
- CHART_LINE1, CHART_LINE2, CHART_LINE3, CHART_LINE4

## Theme Persistence

Themes are automatically saved to QSettings when changed and restored
on application startup. No configuration needed!

## Accessibility Features

✅ High contrast ratios (4.5:1 minimum for text)
✅ 3px focus indicators for keyboard navigation
✅ Touch-friendly spacing (44px minimum targets)
✅ Disabled states clearly indicated (40% opacity)
✅ No color-only indicators (always use icons + text)

## Files Structure

```
src/ui/
├── theme_manager.py       - Core theme management (singleton)
├── theme_presets.py       - Color definitions for both themes
├── styles.py              - Dynamic QSS stylesheet generator
└── main_window.py         - Theme menu integration
```

## Testing Checklist

✅ Switch between Dark and Bright themes using menu
✅ Verify toggle keyboard shortcut (Ctrl+Shift+T)
✅ Check device status colors in device tree
✅ Check signal quality indicators
✅ Verify theme persists after restart
✅ Ensure all text is readable in both themes
✅ Check alarm colors are distinct and visible
✅ Verify focus indicators are visible

## Example: Adding a New Danger Button

```python
from PySide6.QtWidgets import QPushButton

# Create button
danger_button = QPushButton("Emergency Stop")

# Apply danger class (defined in styles.py)
danger_button.setProperty("class", "danger")

# Force style update
danger_button.style().unpolish(danger_button)
danger_button.style().polish(danger_button)

# Button will now use error color from theme
```

## Example: Custom Alarm Widget with Flashing

```python
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, QPropertyAnimation, Qt
from src.ui.theme_manager import get_theme_manager
from src.ui.theme_presets import ColorRole

class AlarmLabel(QLabel):
    def __init__(self, text, severity="critical", parent=None):
        super().__init__(text, parent)
        self.theme = get_theme_manager()
        self.severity = severity
        
        # Set property for stylesheet
        self.setProperty("alarm", severity)
        
        # Create flash animation for critical alarms
        if severity == "critical":
            self._setup_flash_animation()
    
    def _setup_flash_animation(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._toggle_flash)
        self.timer.start(1000)  # 1Hz flash
        self.flash_state = True
    
    def _toggle_flash(self):
        self.flash_state = not self.flash_state
        if self.flash_state:
            self.setProperty("alarm", self.severity)
        else:
            self.setProperty("alarm", "acknowledged")
        
        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
```

## Troubleshooting

**Q: Theme doesn't apply after changing?**
A: Try calling `QApplication.instance().processEvents()` to force a repaint.

**Q: Custom colors not showing?**
A: Make sure you're using theme colors from ColorRole enum, not hardcoded values.

**Q: Widget not updating on theme change?**
A: Connect to `theme_manager.theme_changed` signal and reapply styles.

**Q: Stylesheet conflicts?**
A: Theme-aware stylesheets take precedence. Remove hardcoded widget.setStyleSheet()
   calls and use properties instead.

## Performance Notes

- Theme manager is a singleton (one instance for entire app)
- Theme switching is optimized with 200ms color transitions
- No performance impact on signal updates or device polling
- QSettings persistence is async and non-blocking

## Future Enhancements

Potential future additions:
- System theme detection (follow OS dark/light mode)
- Custom color picker for user-defined themes
- High contrast mode for accessibility
- Color blindness-friendly palettes
- Theme import/export

---

Enjoy the Epic Dark and Bright themes! 🎨
"""
