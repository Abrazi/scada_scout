"""
Theme Manager for SCADA Scout application.
Manages theme switching, persistence, and dynamic stylesheet application.
"""

import logging
from typing import Optional, Dict
from PySide6.QtCore import QObject, Signal, QSettings
from PySide6.QtWidgets import QApplication

from .theme_presets import ThemeType, ColorRole, get_theme_colors, get_color


logger = logging.getLogger(__name__)


class ThemeManager(QObject):
    """
    Central theme management system for the application.
    
    Features:
    - Dark and Bright theme switching
    - QSettings persistence
    - Dynamic stylesheet generation
    - Color accessor for custom widgets
    - Thread-safe operations
    
    Signals:
        theme_changed: Emitted when theme changes (theme_type: str)
    """
    
    theme_changed = Signal(str)  # Emits theme name when changed
    
    _instance: Optional['ThemeManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern to ensure one theme manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize theme manager (only once due to singleton)."""
        if ThemeManager._initialized:
            return
            
        super().__init__()
        ThemeManager._initialized = True
        
        self._current_theme: ThemeType = ThemeType.DARK
        self._colors: Dict[ColorRole, str] = {}
        self._settings = QSettings("scada_scout", "application")
        self._app: Optional[QApplication] = None
        
        # Load saved theme preference
        self._load_theme_preference()
        
        logger.info(f"ThemeManager initialized with {self._current_theme.value} theme")
    
    def _load_theme_preference(self) -> None:
        """Load theme preference from QSettings."""
        saved_theme = self._settings.value("theme/current", "dark")
        
        if saved_theme == "bright":
            self._current_theme = ThemeType.BRIGHT
        else:
            self._current_theme = ThemeType.DARK
        
        self._colors = get_theme_colors(self._current_theme)
        logger.debug(f"Loaded theme preference: {saved_theme}")
    
    def _save_theme_preference(self) -> None:
        """Save current theme to QSettings."""
        self._settings.setValue("theme/current", self._current_theme.value)
        self._settings.sync()
        logger.debug(f"Saved theme preference: {self._current_theme.value}")
    
    def get_current_theme(self) -> ThemeType:
        """
        Get the currently active theme type.
        
        Returns:
            Current ThemeType (DARK or BRIGHT)
        """
        return self._current_theme
    
    def get_color(self, role: ColorRole) -> str:
        """
        Get hex color for a specific role in the current theme.
        
        Args:
            role: ColorRole enum value
            
        Returns:
            Hex color string (e.g., "#0D1117")
            
        Example:
            alarm_color = theme_manager.get_color(ColorRole.ALARM_CRITICAL)
            widget.setStyleSheet(f"color: {alarm_color};")
        """
        return self._colors.get(role, "#FF00FF")  # Magenta fallback
    
    def get_color_by_name(self, role_name: str) -> str:
        """
        Get color by role name string (convenience method).
        
        Args:
            role_name: String name of ColorRole (e.g., "alarm_critical")
            
        Returns:
            Hex color string
        """
        try:
            role = ColorRole(role_name)
            return self.get_color(role)
        except ValueError:
            logger.warning(f"Unknown color role: {role_name}")
            return "#FF00FF"
    
    def set_theme(self, theme_type: ThemeType, apply_immediately: bool = True) -> None:
        """
        Change the active theme.
        
        Args:
            theme_type: New theme to apply
            apply_immediately: If True, applies stylesheet immediately
        """
        if theme_type == self._current_theme:
            logger.debug(f"Theme already set to {theme_type.value}")
            return
        
        logger.info(f"Changing theme from {self._current_theme.value} to {theme_type.value}")
        
        self._current_theme = theme_type
        self._colors = get_theme_colors(theme_type)
        self._save_theme_preference()
        
        if apply_immediately and self._app:
            self.apply_to_application(self._app)
        
        self.theme_changed.emit(theme_type.value)
    
    def toggle_theme(self) -> None:
        """Toggle between dark and bright themes."""
        new_theme = ThemeType.BRIGHT if self._current_theme == ThemeType.DARK else ThemeType.DARK
        self.set_theme(new_theme)
        logger.info(f"Theme toggled to {new_theme.value}")
    
    def apply_to_application(self, app: QApplication) -> None:
        """
        Apply current theme stylesheet to the entire application.
        
        Args:
            app: QApplication instance
        """
        self._app = app
        
        # Import stylesheet generator
        from .styles import generate_stylesheet
        
        stylesheet = generate_stylesheet(self._current_theme, self._colors)
        app.setStyleSheet(stylesheet)
        
        logger.info(f"Applied {self._current_theme.value} theme to application")
    
    def is_dark_theme(self) -> bool:
        """Check if current theme is dark."""
        return self._current_theme == ThemeType.DARK
    
    def is_bright_theme(self) -> bool:
        """Check if current theme is bright."""
        return self._current_theme == ThemeType.BRIGHT
    
    def get_status_color(self, status: str) -> str:
        """
        Get color for common status values (convenience method).
        
        Args:
            status: Status string like "connected", "disconnected", "error"
            
        Returns:
            Hex color string
        """
        status_map = {
            "connected": ColorRole.DEVICE_CONNECTED,
            "disconnected": ColorRole.DEVICE_DISCONNECTED,
            "connecting": ColorRole.DEVICE_CONNECTING,
            "error": ColorRole.DEVICE_ERROR,
            "good": ColorRole.QUALITY_GOOD,
            "bad": ColorRole.QUALITY_BAD,
            "questionable": ColorRole.QUALITY_QUESTIONABLE,
            "not_connected": ColorRole.QUALITY_NOT_CONNECTED,
        }
        
        role = status_map.get(status.lower())
        if role:
            return self.get_color(role)
        
        logger.warning(f"Unknown status: {status}")
        return self.get_color(ColorRole.TEXT_SECONDARY)
    
    def get_alarm_color(self, severity: str) -> str:
        """
        Get color for alarm severity (convenience method).
        
        Args:
            severity: Alarm severity like "critical", "high", "medium", "low"
            
        Returns:
            Hex color string
        """
        severity_map = {
            "critical": ColorRole.ALARM_CRITICAL,
            "high": ColorRole.ALARM_HIGH,
            "medium": ColorRole.ALARM_MEDIUM,
            "low": ColorRole.ALARM_LOW,
            "acknowledged": ColorRole.ALARM_ACKNOWLEDGED,
        }
        
        role = severity_map.get(severity.lower())
        if role:
            return self.get_color(role)
        
        logger.warning(f"Unknown alarm severity: {severity}")
        return self.get_color(ColorRole.ERROR)
    
    def get_chart_colors(self) -> list:
        """
        Get list of colors for chart lines.
        
        Returns:
            List of hex color strings
        """
        return [
            self.get_color(ColorRole.CHART_LINE1),
            self.get_color(ColorRole.CHART_LINE2),
            self.get_color(ColorRole.CHART_LINE3),
            self.get_color(ColorRole.CHART_LINE4),
        ]


# Global instance accessor
_theme_manager_instance: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """
    Get the global ThemeManager instance (singleton).
    
    Returns:
        ThemeManager instance
        
    Example:
        from src.ui.theme_manager import get_theme_manager
        theme = get_theme_manager()
        color = theme.get_color(ColorRole.PRIMARY)
    """
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()
    return _theme_manager_instance
