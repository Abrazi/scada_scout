"""
Professional styling for SCADA Scout application.
Dynamic QSS stylesheet generation with Epic Dark and Bright themes.
"""

from typing import Dict
from .theme_presets import ThemeType, ColorRole


def generate_stylesheet(theme_type: ThemeType, colors: Dict[ColorRole, str]) -> str:
    """
    Generate complete QSS stylesheet for the application.
    
    Args:
        theme_type: Active theme type
        colors: Dictionary of ColorRole to hex color mappings
        
    Returns:
        Complete QSS stylesheet string
    """
    
    # Extract commonly used colors
    bg = colors[ColorRole.BACKGROUND]
    surface = colors[ColorRole.SURFACE]
    surface_var = colors[ColorRole.SURFACE_VARIANT]
    text_primary = colors[ColorRole.TEXT_PRIMARY]
    text_secondary = colors[ColorRole.TEXT_SECONDARY]
    text_disabled = colors[ColorRole.TEXT_DISABLED]
    primary = colors[ColorRole.PRIMARY]
    primary_hover = colors[ColorRole.PRIMARY_HOVER]
    primary_pressed = colors[ColorRole.PRIMARY_PRESSED]
    border = colors[ColorRole.BORDER]
    border_focus = colors[ColorRole.BORDER_FOCUS]
    selection = colors[ColorRole.SELECTION]
    selection_text = colors[ColorRole.SELECTION_TEXT]
    hover = colors[ColorRole.HOVER]
    button_bg = colors[ColorRole.BUTTON_BACKGROUND]
    button_hover = colors[ColorRole.BUTTON_HOVER]
    button_pressed = colors[ColorRole.BUTTON_PRESSED]
    button_disabled = colors[ColorRole.BUTTON_DISABLED]
    input_bg = colors[ColorRole.INPUT_BACKGROUND]
    input_border = colors[ColorRole.INPUT_BORDER]
    input_focus = colors[ColorRole.INPUT_FOCUS_BORDER]
    toolbar_bg = colors[ColorRole.TOOLBAR_BACKGROUND]
    menu_bg = colors[ColorRole.MENU_BACKGROUND]
    menu_hover = colors[ColorRole.MENU_HOVER]
    success = colors[ColorRole.SUCCESS]
    warning = colors[ColorRole.WARNING]
    error = colors[ColorRole.ERROR]
    shadow = colors[ColorRole.SHADOW]
    disabled_bg = colors[ColorRole.DISABLED_BACKGROUND]
    
    # SCADA-specific colors
    alarm_critical = colors[ColorRole.ALARM_CRITICAL]
    alarm_high = colors[ColorRole.ALARM_HIGH]
    quality_good = colors[ColorRole.QUALITY_GOOD]
    quality_bad = colors[ColorRole.QUALITY_BAD]
    device_connected = colors[ColorRole.DEVICE_CONNECTED]
    device_disconnected = colors[ColorRole.DEVICE_DISCONNECTED]
    
    # Tree colors
    tree_row_odd = colors[ColorRole.TREE_ROW_ODD]
    tree_row_even = colors[ColorRole.TREE_ROW_EVEN]
    tree_row_selected = colors[ColorRole.TREE_ROW_SELECTED]
    
    return f"""
/* ==================== Global Styles ==================== */
QMainWindow, QDialog, QWidget {{
    background-color: {bg};
    color: {text_primary};
    font-family: "Segoe UI", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
}}

QWidget {{
    selection-background-color: {selection};
    selection-color: {selection_text};
}}

/* ==================== Menu Bar ==================== */
QMenuBar {{
    background-color: {toolbar_bg};
    color: {text_primary};
    padding: 6px;
    border-bottom: 1px solid {border};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 8px 14px;
    border-radius: 4px;
    color: {text_primary};
    font-size: 10pt;
}}

QMenuBar::item:selected {{
    background-color: {hover};
}}

QMenuBar::item:pressed {{
    background-color: {primary};
    color: {selection_text};
}}

/* ==================== Menus ==================== */
QMenu {{
    background-color: {menu_bg};
    color: {text_primary};
    border: 1px solid {border};
    padding: 4px;
    border-radius: 4px;
}}

QMenu::item {{
    padding: 8px 24px 8px 8px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {menu_hover};
}}

QMenu::item:disabled {{
    color: {text_disabled};
}}

QMenu::separator {{
    height: 1px;
    background-color: {border};
    margin: 4px 8px;
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    margin-left: 6px;
}}

QMenu::indicator:checked {{
    background-color: {primary};
    border: 1px solid {primary};
    border-radius: 3px;
}}

/* ==================== Toolbar ==================== */
QToolBar {{
    background-color: {toolbar_bg};
    border: none;
    padding: 4px;
    spacing: 4px;
}}

QToolBar::separator {{
    width: 1px;
    background-color: {border};
    margin: 4px 8px;
}}

QToolButton {{
    background-color: transparent;
    color: {text_primary};
    padding: 6px 10px;
    border: 1px solid transparent;
    border-radius: 4px;
    min-width: 40px;
    min-height: 32px;
}}

QToolButton:hover {{
    background-color: {hover};
    border: 1px solid {border};
}}

QToolButton:pressed {{
    background-color: {primary};
    color: {selection_text};
}}

QToolButton:checked {{
    background-color: {surface_var};
    border: 1px solid {border_focus};
}}

QToolButton:disabled {{
    color: {text_disabled};
    background-color: transparent;
}}

/* ==================== Buttons ==================== */
QPushButton {{
    background-color: {button_bg};
    color: {selection_text};
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 500;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {button_hover};
}}

QPushButton:pressed {{
    background-color: {button_pressed};
}}

QPushButton:disabled {{
    background-color: {button_disabled};
    color: {text_disabled};
}}

QPushButton:focus {{
    border: 2px solid {border_focus};
    outline: none;
}}

/* Danger button */
QPushButton[class="danger"] {{
    background-color: {error};
}}

QPushButton[class="danger"]:hover {{
    background-color: {alarm_high};
}}

/* Secondary button */
QPushButton[class="secondary"] {{
    background-color: {surface_var};
    color: {text_primary};
    border: 1px solid {border};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {hover};
}}

/* Success button */
QPushButton[class="success"] {{
    background-color: {success};
}}

/* ==================== Input Fields ==================== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {input_bg};
    color: {text_primary};
    border: 1px solid {input_border};
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: {selection};
    selection-color: {selection_text};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, 
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {input_focus};
    outline: none;
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {disabled_bg};
    color: {text_disabled};
}}

/* ==================== Combo Boxes ==================== */
QComboBox {{
    background-color: {input_bg};
    color: {text_primary};
    border: 1px solid {input_border};
    border-radius: 4px;
    padding: 6px 30px 6px 8px;
    min-height: 24px;
}}

QComboBox:hover {{
    border: 1px solid {border_focus};
}}

QComboBox:focus {{
    border: 2px solid {input_focus};
}}

QComboBox:disabled {{
    background-color: {disabled_bg};
    color: {text_disabled};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid {input_border};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}}

QComboBox::down-arrow {{
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {menu_bg};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    selection-background-color: {selection};
    selection-color: {selection_text};
    outline: none;
}}

/* ==================== Spin Boxes ==================== */
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {input_border};
    border-bottom: 1px solid {input_border};
    border-top-right-radius: 4px;
    background-color: {surface_var};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: {hover};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid {input_border};
    border-bottom-right-radius: 4px;
    background-color: {surface_var};
}}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {hover};
}}

/* ==================== Check Boxes & Radio Buttons ==================== */
QCheckBox, QRadioButton {{
    color: {text_primary};
    spacing: 8px;
    padding: 4px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {input_border};
    background-color: {input_bg};
}}

QCheckBox::indicator {{
    border-radius: 3px;
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border: 2px solid {border_focus};
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {primary};
    border: 2px solid {primary};
}}

QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background-color: {disabled_bg};
    border: 2px solid {text_disabled};
}}

/* ==================== Sliders ==================== */
QSlider::groove:horizontal {{
    border: 1px solid {border};
    height: 6px;
    background-color: {surface_var};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {primary};
    border: 1px solid {primary};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {primary_hover};
}}

/* ==================== Progress Bars ==================== */
QProgressBar {{
    background-color: {surface_var};
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
    color: {text_primary};
    height: 20px;
}}

QProgressBar::chunk {{
    background-color: {primary};
    border-radius: 3px;
}}

/* ==================== Tree & Table Widgets ==================== */
QTreeView, QTableView, QListView {{
    background-color: {surface};
    alternate-background-color: {surface_var};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    selection-background-color: {tree_row_selected};
    selection-color: {selection_text};
    outline: none;
    show-decoration-selected: 1;
}}

QTreeView::item, QTableView::item, QListView::item {{
    padding: 6px;
    border: none;
}}

QTreeView::item:hover, QTableView::item:hover, QListView::item:hover {{
    background-color: {hover};
}}

QTreeView::item:selected, QTableView::item:selected, QListView::item:selected {{
    background-color: {tree_row_selected};
    color: {selection_text};
}}

QTreeView::branch {{
    background-color: transparent;
}}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{
    border-image: none;
    image: url(none);
}}

QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{
    border-image: none;
    image: url(none);
}}

/* Header */
QHeaderView::section {{
    background-color: {surface_var};
    color: {text_primary};
    padding: 8px 12px;
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    font-weight: 600;
}}

QHeaderView::section:hover {{
    background-color: {hover};
}}

/* ==================== Tab Widget ==================== */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 4px;
    background-color: {surface};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {surface_var};
    color: {text_secondary};
    padding: 10px 16px;
    border: 1px solid {border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}

QTabBar::tab:hover {{
    background-color: {hover};
    color: {text_primary};
}}

QTabBar::tab:selected {{
    background-color: {surface};
    color: {primary};
    border-bottom: 2px solid {primary};
}}

QTabBar::tab:!selected {{
    margin-top: 2px;
}}

/* ==================== Scroll Bars ==================== */
QScrollBar:vertical {{
    background-color: {surface_var};
    width: 12px;
    border-radius: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {text_disabled};
    border-radius: 5px;
    min-height: 20px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {text_secondary};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {surface_var};
    height: 12px;
    border-radius: 6px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {text_disabled};
    border-radius: 5px;
    min-width: 20px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {text_secondary};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ==================== Group Box ==================== */
QGroupBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 4px 8px;
    background-color: {surface};
    color: {text_primary};
}}

/* ==================== Splitter ==================== */
QSplitter::handle {{
    background-color: {border};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {primary};
}}

/* ==================== Dock Widget ==================== */
QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    color: {text_primary};
}}

QDockWidget::title {{
    background-color: {surface_var};
    text-align: left;
    padding: 8px;
    border: 1px solid {border};
    border-radius: 4px 4px 0 0;
    font-weight: 600;
}}

QDockWidget::close-button, QDockWidget::float-button {{
    background-color: transparent;
    border: none;
    padding: 4px;
}}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background-color: {hover};
    border-radius: 3px;
}}

/* ==================== Status Bar ==================== */
QStatusBar {{
    background-color: {toolbar_bg};
    color: {text_secondary};
    border-top: 1px solid {border};
    padding: 4px 8px;
}}

QStatusBar::item {{
    border: none;
}}

QStatusBar QLabel {{
    color: {text_secondary};
    padding: 0 8px;
}}

/* ==================== Tool Tips ==================== */
QToolTip {{
    background-color: {surface_var};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 6px 8px;
}}

/* ==================== SCADA-Specific Status Colors ==================== */

/* Device Status Labels */
QLabel[device_status="connected"] {{
    color: {device_connected};
    font-weight: bold;
}}

QLabel[device_status="disconnected"] {{
    color: {device_disconnected};
    font-weight: bold;
}}

QLabel[device_status="connecting"] {{
    color: {primary};
    font-weight: bold;
}}

QLabel[device_status="error"] {{
    color: {error};
    font-weight: bold;
}}

/* Signal Quality Labels */
QLabel[quality="good"] {{
    color: {quality_good};
    font-weight: bold;
}}

QLabel[quality="bad"] {{
    color: {quality_bad};
    font-weight: bold;
}}

QLabel[quality="questionable"] {{
    color: {warning};
    font-weight: bold;
}}

/* Alarm Labels */
QLabel[alarm="critical"] {{
    color: {alarm_critical};
    font-weight: bold;
    background-color: {surface_var};
    padding: 4px 8px;
    border-radius: 3px;
}}

QLabel[alarm="high"] {{
    color: {alarm_high};
    font-weight: bold;
    background-color: {surface_var};
    padding: 4px 8px;
    border-radius: 3px;
}}

QLabel[alarm="medium"] {{
    color: {warning};
    font-weight: bold;
}}

/* Status Colors */
QLabel[status="success"] {{
    color: {success};
    font-weight: 600;
}}

QLabel[status="warning"] {{
    color: {warning};
    font-weight: 600;
}}

QLabel[status="error"] {{
    color: {error};
    font-weight: 600;
}}

QLabel[status="info"] {{
    color: {primary};
    font-weight: 600;
}}

/* Code/Monospace Text */
QLabel[class="code"], QTextEdit[class="code"], QPlainTextEdit[class="code"] {{
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    background-color: {surface_var};
    border: 1px solid {border};
    border-radius: 3px;
    padding: 4px 6px;
}}

/* ==================== Dialog Windows ==================== */
QDialog {{
    background-color: {surface};
}}

QMessageBox {{
    background-color: {surface};
}}

QMessageBox QLabel {{
    color: {text_primary};
}}

/* ==================== Custom Widget Classes ==================== */

/* Event log items */
QTextEdit#eventLog {{
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    font-size: 9pt;
}}

/* PLC Ladder Logic (if applicable) */
QWidget[class="ladder_rung"] {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 3px;
}}

/* Chart/Graph widgets */
QWidget[class="chart_widget"] {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
}}

/* Focus indicators - 3px width for accessibility */
*:focus {{
    outline: 3px solid {border_focus};
    outline-offset: 2px;
}}

/* Disabled state - 40% opacity */
*:disabled {{
    opacity: 0.4;
}}
"""


# Legacy support - export PROFESSIONAL_STYLE as the default dark theme
# This allows existing code to continue working
def _get_default_stylesheet() -> str:
    """Get default stylesheet for backward compatibility."""
    from .theme_presets import ThemeType, get_theme_colors
    colors = get_theme_colors(ThemeType.DARK)
    return generate_stylesheet(ThemeType.DARK, colors)


PROFESSIONAL_STYLE = _get_default_stylesheet()
