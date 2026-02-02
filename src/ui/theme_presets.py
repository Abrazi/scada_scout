"""
Theme color presets for SCADA Scout application.
Provides Epic Dark and Epic Bright themes optimized for SCADA visualization.
"""

from enum import Enum
from typing import Dict


class ThemeType(Enum):
    """Available theme types."""
    DARK = "dark"
    BRIGHT = "bright"


class ColorRole(Enum):
    """Semantic color roles for UI components."""
    # Base colors
    BACKGROUND = "background"
    SURFACE = "surface"
    SURFACE_VARIANT = "surface_variant"
    
    # Text colors
    TEXT_PRIMARY = "text_primary"
    TEXT_SECONDARY = "text_secondary"
    TEXT_DISABLED = "text_disabled"
    
    # Primary accent
    PRIMARY = "primary"
    PRIMARY_HOVER = "primary_hover"
    PRIMARY_PRESSED = "primary_pressed"
    
    # Status colors
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    
    # SCADA-specific colors
    ALARM_CRITICAL = "alarm_critical"
    ALARM_HIGH = "alarm_high"
    ALARM_MEDIUM = "alarm_medium"
    ALARM_LOW = "alarm_low"
    ALARM_ACKNOWLEDGED = "alarm_acknowledged"
    
    QUALITY_GOOD = "quality_good"
    QUALITY_BAD = "quality_bad"
    QUALITY_QUESTIONABLE = "quality_questionable"
    QUALITY_NOT_CONNECTED = "quality_not_connected"
    
    DEVICE_CONNECTED = "device_connected"
    DEVICE_DISCONNECTED = "device_disconnected"
    DEVICE_CONNECTING = "device_connecting"
    DEVICE_ERROR = "device_error"
    
    # UI element colors
    BORDER = "border"
    BORDER_FOCUS = "border_focus"
    SELECTION = "selection"
    SELECTION_TEXT = "selection_text"
    HOVER = "hover"
    DISABLED_BACKGROUND = "disabled_background"
    
    # Button colors
    BUTTON_BACKGROUND = "button_background"
    BUTTON_HOVER = "button_hover"
    BUTTON_PRESSED = "button_pressed"
    BUTTON_DISABLED = "button_disabled"
    
    # Input colors
    INPUT_BACKGROUND = "input_background"
    INPUT_BORDER = "input_border"
    INPUT_FOCUS_BORDER = "input_focus_border"
    
    # Toolbar/Menu
    TOOLBAR_BACKGROUND = "toolbar_background"
    MENU_BACKGROUND = "menu_background"
    MENU_HOVER = "menu_hover"
    
    # Chart/Graph colors
    CHART_BACKGROUND = "chart_background"
    CHART_GRID = "chart_grid"
    CHART_LINE1 = "chart_line1"
    CHART_LINE2 = "chart_line2"
    CHART_LINE3 = "chart_line3"
    CHART_LINE4 = "chart_line4"
    
    # Tree/Table
    TREE_ROW_ODD = "tree_row_odd"
    TREE_ROW_EVEN = "tree_row_even"
    TREE_ROW_SELECTED = "tree_row_selected"
    
    # Shadow/Elevation
    SHADOW = "shadow"


# Epic Dark Theme - Optimized for 24/7 control room operation
EPIC_DARK_THEME: Dict[ColorRole, str] = {
    # Base colors - Deep charcoal with subtle blue undertone
    ColorRole.BACKGROUND: "#0D1117",  # Deep space background
    ColorRole.SURFACE: "#161B22",  # Card/panel surface
    ColorRole.SURFACE_VARIANT: "#21262D",  # Elevated surfaces
    
    # Text colors - High contrast for readability
    ColorRole.TEXT_PRIMARY: "#E6EDF3",  # Near white
    ColorRole.TEXT_SECONDARY: "#8B949E",  # Muted gray
    ColorRole.TEXT_DISABLED: "#484F58",  # Dimmed
    
    # Primary accent - Electric cyan for SCADA feel
    ColorRole.PRIMARY: "#00D9FF",  # Electric cyan
    ColorRole.PRIMARY_HOVER: "#33E1FF",  # Lighter cyan
    ColorRole.PRIMARY_PRESSED: "#00B8D9",  # Deeper cyan
    
    # Status colors - High visibility
    ColorRole.SUCCESS: "#39FF14",  # Neon green
    ColorRole.WARNING: "#FFB300",  # Amber
    ColorRole.ERROR: "#FF1744",  # Crimson red
    ColorRole.INFO: "#2196F3",  # Blue
    
    # SCADA-specific alarm colors (high contrast, distinct)
    ColorRole.ALARM_CRITICAL: "#FF1744",  # Bright red - flashing
    ColorRole.ALARM_HIGH: "#FF6B35",  # Safety orange
    ColorRole.ALARM_MEDIUM: "#FFB300",  # Amber
    ColorRole.ALARM_LOW: "#FDD835",  # Yellow
    ColorRole.ALARM_ACKNOWLEDGED: "#757575",  # Gray (solid)
    
    # Quality indicators
    ColorRole.QUALITY_GOOD: "#00C853",  # Green
    ColorRole.QUALITY_BAD: "#FF1744",  # Red
    ColorRole.QUALITY_QUESTIONABLE: "#FFB300",  # Amber
    ColorRole.QUALITY_NOT_CONNECTED: "#757575",  # Gray
    
    # Device status
    ColorRole.DEVICE_CONNECTED: "#00C853",  # Green
    ColorRole.DEVICE_DISCONNECTED: "#FF1744",  # Red
    ColorRole.DEVICE_CONNECTING: "#2196F3",  # Blue (pulsing)
    ColorRole.DEVICE_ERROR: "#FF6B35",  # Orange
    
    # UI elements
    ColorRole.BORDER: "#30363D",  # Subtle border
    ColorRole.BORDER_FOCUS: "#00D9FF",  # Cyan focus ring
    ColorRole.SELECTION: "#1F6FEB",  # Blue selection
    ColorRole.SELECTION_TEXT: "#FFFFFF",  # White text
    ColorRole.HOVER: "#2D333B",  # Hover state
    ColorRole.DISABLED_BACKGROUND: "#21262D",  # Disabled bg
    
    # Buttons
    ColorRole.BUTTON_BACKGROUND: "#238636",  # Green button
    ColorRole.BUTTON_HOVER: "#2EA043",  # Hover green
    ColorRole.BUTTON_PRESSED: "#1A7F37",  # Pressed green
    ColorRole.BUTTON_DISABLED: "#21262D",  # Disabled
    
    # Inputs
    ColorRole.INPUT_BACKGROUND: "#0D1117",  # Dark input
    ColorRole.INPUT_BORDER: "#30363D",  # Border
    ColorRole.INPUT_FOCUS_BORDER: "#00D9FF",  # Focus cyan
    
    # Toolbar/Menu
    ColorRole.TOOLBAR_BACKGROUND: "#161B22",  # Toolbar bg
    ColorRole.MENU_BACKGROUND: "#161B22",  # Menu bg
    ColorRole.MENU_HOVER: "#2D333B",  # Menu hover
    
    # Charts - Phosphor green inspired
    ColorRole.CHART_BACKGROUND: "#0D1117",  # Dark chart bg
    ColorRole.CHART_GRID: "#21262D",  # Subtle grid
    ColorRole.CHART_LINE1: "#39FF14",  # Neon green
    ColorRole.CHART_LINE2: "#00D9FF",  # Cyan
    ColorRole.CHART_LINE3: "#FFB300",  # Amber
    ColorRole.CHART_LINE4: "#FF6B35",  # Orange
    
    # Tree/Table
    ColorRole.TREE_ROW_ODD: "#0D1117",  # Odd row
    ColorRole.TREE_ROW_EVEN: "#161B22",  # Even row
    ColorRole.TREE_ROW_SELECTED: "#1F6FEB",  # Selected
    
    # Shadow
    ColorRole.SHADOW: "#00000080",  # Semi-transparent black
}


# Epic Bright Theme - Professional, anti-glare for daylight operation
EPIC_BRIGHT_THEME: Dict[ColorRole, str] = {
    # Base colors - Soft white with warm undertone (anti-glare)
    ColorRole.BACKGROUND: "#F6F8FA",  # Soft white
    ColorRole.SURFACE: "#FFFFFF",  # Pure white surface
    ColorRole.SURFACE_VARIANT: "#F0F2F5",  # Slightly gray
    
    # Text colors - High contrast on light
    ColorRole.TEXT_PRIMARY: "#24292F",  # Near black
    ColorRole.TEXT_SECONDARY: "#57606A",  # Medium gray
    ColorRole.TEXT_DISABLED: "#8C959F",  # Light gray
    
    # Primary accent - Professional blue
    ColorRole.PRIMARY: "#0969DA",  # Professional blue
    ColorRole.PRIMARY_HOVER: "#1F75DB",  # Lighter blue
    ColorRole.PRIMARY_PRESSED: "#0550AE",  # Deeper blue
    
    # Status colors - Clear and distinct
    ColorRole.SUCCESS: "#1A7F37",  # Forest green
    ColorRole.WARNING: "#9A6700",  # Dark amber
    ColorRole.ERROR: "#CF222E",  # Bright red
    ColorRole.INFO: "#0969DA",  # Blue
    
    # SCADA-specific alarm colors (high visibility on light)
    ColorRole.ALARM_CRITICAL: "#CF222E",  # Bright red
    ColorRole.ALARM_HIGH: "#D73A49",  # Light red
    ColorRole.ALARM_MEDIUM: "#FB8500",  # Orange
    ColorRole.ALARM_LOW: "#DBAB09",  # Yellow-orange
    ColorRole.ALARM_ACKNOWLEDGED: "#6E7781",  # Gray
    
    # Quality indicators
    ColorRole.QUALITY_GOOD: "#1A7F37",  # Green
    ColorRole.QUALITY_BAD: "#CF222E",  # Red
    ColorRole.QUALITY_QUESTIONABLE: "#9A6700",  # Amber
    ColorRole.QUALITY_NOT_CONNECTED: "#6E7781",  # Gray
    
    # Device status
    ColorRole.DEVICE_CONNECTED: "#1A7F37",  # Green
    ColorRole.DEVICE_DISCONNECTED: "#CF222E",  # Red
    ColorRole.DEVICE_CONNECTING: "#0969DA",  # Blue
    ColorRole.DEVICE_ERROR: "#D73A49",  # Light red
    
    # UI elements
    ColorRole.BORDER: "#D0D7DE",  # Light border
    ColorRole.BORDER_FOCUS: "#0969DA",  # Blue focus ring
    ColorRole.SELECTION: "#0969DA",  # Blue selection
    ColorRole.SELECTION_TEXT: "#FFFFFF",  # White text
    ColorRole.HOVER: "#F6F8FA",  # Hover state
    ColorRole.DISABLED_BACKGROUND: "#F6F8FA",  # Disabled bg
    
    # Buttons
    ColorRole.BUTTON_BACKGROUND: "#1A7F37",  # Green button
    ColorRole.BUTTON_HOVER: "#2DA44E",  # Hover green
    ColorRole.BUTTON_PRESSED: "#1A7F37",  # Pressed
    ColorRole.BUTTON_DISABLED: "#8C959F",  # Disabled gray
    
    # Inputs
    ColorRole.INPUT_BACKGROUND: "#FFFFFF",  # White input
    ColorRole.INPUT_BORDER: "#D0D7DE",  # Border
    ColorRole.INPUT_FOCUS_BORDER: "#0969DA",  # Focus blue
    
    # Toolbar/Menu
    ColorRole.TOOLBAR_BACKGROUND: "#F6F8FA",  # Toolbar bg
    ColorRole.MENU_BACKGROUND: "#FFFFFF",  # Menu bg
    ColorRole.MENU_HOVER: "#F6F8FA",  # Menu hover
    
    # Charts - Vibrant but not overwhelming
    ColorRole.CHART_BACKGROUND: "#FFFFFF",  # White chart bg
    ColorRole.CHART_GRID: "#E1E4E8",  # Light grid
    ColorRole.CHART_LINE1: "#1A7F37",  # Green
    ColorRole.CHART_LINE2: "#0969DA",  # Blue
    ColorRole.CHART_LINE3: "#9A6700",  # Amber
    ColorRole.CHART_LINE4: "#D73A49",  # Red
    
    # Tree/Table
    ColorRole.TREE_ROW_ODD: "#FFFFFF",  # Odd row
    ColorRole.TREE_ROW_EVEN: "#F6F8FA",  # Even row
    ColorRole.TREE_ROW_SELECTED: "#0969DA",  # Selected
    
    # Shadow
    ColorRole.SHADOW: "#00000020",  # Light shadow
}


def get_theme_colors(theme_type: ThemeType) -> Dict[ColorRole, str]:
    """
    Get color dictionary for the specified theme.
    
    Args:
        theme_type: Type of theme to retrieve
        
    Returns:
        Dictionary mapping ColorRole to hex color strings
    """
    if theme_type == ThemeType.DARK:
        return EPIC_DARK_THEME.copy()
    elif theme_type == ThemeType.BRIGHT:
        return EPIC_BRIGHT_THEME.copy()
    else:
        # Default to dark theme
        return EPIC_DARK_THEME.copy()


def get_color(theme_type: ThemeType, role: ColorRole) -> str:
    """
    Get a specific color for a role in the given theme.
    
    Args:
        theme_type: Type of theme
        role: Color role to retrieve
        
    Returns:
        Hex color string
    """
    colors = get_theme_colors(theme_type)
    return colors.get(role, "#FF00FF")  # Magenta as fallback for missing colors
