"""
Professional styling for SCADA Scout application.
Provides modern, elegant themes with proper color schemes.
"""

PROFESSIONAL_STYLE = """
/* ==================== Global Styles ==================== */
QMainWindow {
    background-color: #f5f6f7;
}

QWidget {
    font-family: "Segoe UI", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: #2c3e50;
}

/* ==================== Menu Bar ==================== */
QMenuBar {
    background-color: #2c3e50;
    color: white;
    padding: 6px;
    border-bottom: 2px solid #34495e;
}

QMenuBar::item {
    background-color: transparent;
    padding: 8px 14px;
    border-radius: 4px;
    color: white;
    font-size: 11pt;
}

QMenuBar::item:selected {
    background-color: #34495e;
}

QMenuBar::item:pressed {
    background-color: #1abc9c;
}

QMenu {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 25px 6px 12px;
    border-radius: 3px;
}

QMenu::item:selected {
    background-color: #3498db;
    color: white;
}

QMenu::separator {
    height: 1px;
    background-color: #ecf0f1;
    margin: 4px 8px;
}

/* ==================== Tool Bar ==================== */
QToolBar {
    background-color: #34495e;
    border: none;
    spacing: 6px;
    padding: 6px;
}

QToolBar::separator {
    background-color: #7f8c8d;
    width: 1px;
    margin: 4px 6px;
}

QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px;
    color: white;
}

QToolButton:hover {
    background-color: #1abc9c;
}

QToolButton:pressed {
    background-color: #16a085;
}

/* ==================== Status Bar ==================== */
QStatusBar {
    background-color: #34495e;
    color: white;
    border-top: 1px solid #2c3e50;
    padding: 4px;
}

/* ==================== Dock Widgets ==================== */
QDockWidget {
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
    border: 1px solid #bdc3c7;
}

QDockWidget::title {
    background-color: #3498db;
    color: white;
    padding: 8px;
    border-radius: 4px 4px 0px 0px;
    font-weight: bold;
    text-align: left;
}

QDockWidget::close-button, QDockWidget::float-button {
    background-color: transparent;
    border: none;
    padding: 4px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
}

/* ==================== Buttons ==================== */
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2980b9;
}

QPushButton:pressed {
    background-color: #21618c;
}

QPushButton:disabled {
    background-color: #bdc3c7;
    color: #7f8c8d;
}

QPushButton[class="danger"] {
    background-color: #e74c3c;
}

QPushButton[class="danger"]:hover {
    background-color: #c0392b;
}

QPushButton[class="success"] {
    background-color: #27ae60;
}

QPushButton[class="success"]:hover {
    background-color: #229954;
}

QPushButton:checked {
    background-color: #27ae60;
}

/* ==================== Line Edits ==================== */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #3498db;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #3498db;
}

QLineEdit:disabled, QTextEdit:disabled {
    background-color: #ecf0f1;
    color: #95a5a6;
}

/* ==================== Combo Box ==================== */
QComboBox {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
    min-width: 100px;
}

QComboBox:hover {
    border: 1px solid #3498db;
}

QComboBox:focus {
    border: 2px solid #3498db;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #7f8c8d;
    margin-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    selection-background-color: #3498db;
    selection-color: white;
    padding: 4px;
}

/* ==================== Spin Box ==================== */
QSpinBox, QDoubleSpinBox {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #3498db;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: #ecf0f1;
    border-radius: 0px 4px 0px 0px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #ecf0f1;
    border-radius: 0px 0px 4px 0px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #3498db;
}

/* ==================== Check Box & Radio Button ==================== */
QCheckBox, QRadioButton {
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #bdc3c7;
    border-radius: 3px;
    background-color: white;
}

QCheckBox::indicator:checked {
    background-color: #3498db;
    border-color: #3498db;
}

QRadioButton::indicator {
    border-radius: 9px;
}

QRadioButton::indicator:checked {
    background-color: #3498db;
    border-color: #3498db;
}

/* ==================== Tree View ==================== */
QTreeView, QListView {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    alternate-background-color: #f8f9fa;
    selection-background-color: #3498db;
    selection-color: white;
}

QTreeView::item, QListView::item {
    padding: 4px;
    border-radius: 2px;
}

QTreeView::item:hover, QListView::item:hover {
    background-color: #e8f4f8;
}

QTreeView::item:selected, QListView::item:selected {
    background-color: #3498db;
    color: white;
}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {
    image: none;
    border: none;
}

QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {
    image: none;
    border: none;
}

QHeaderView::section {
    background-color: #34495e;
    color: white;
    padding: 8px;
    border: none;
    border-right: 1px solid #2c3e50;
    font-weight: bold;
}

QHeaderView::section:hover {
    background-color: #2c3e50;
}

/* ==================== Table View ==================== */
QTableView {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    gridline-color: #ecf0f1;
    selection-background-color: #3498db;
    selection-color: white;
}

QTableView::item {
    padding: 6px;
}

QTableView::item:hover {
    background-color: #e8f4f8;
}

QTableView::item:selected {
    background-color: #3498db;
    color: white;
}

/* ==================== Tab Widget ==================== */
QTabWidget::pane {
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    background-color: white;
    top: -1px;
}

QTabBar::tab {
    background-color: #ecf0f1;
    border: 1px solid #bdc3c7;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 10px 18px;
    margin-right: 2px;
    font-size: 11pt;
}

QTabBar::tab:selected {
    background-color: white;
    color: #3498db;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #d5dbdb;
}

/* ==================== Scroll Bar ==================== */
QScrollBar:vertical {
    background-color: #ecf0f1;
    width: 12px;
    border-radius: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #95a5a6;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #7f8c8d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #ecf0f1;
    height: 12px;
    border-radius: 6px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #95a5a6;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #7f8c8d;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ==================== Progress Bar ==================== */
QProgressBar {
    background-color: #ecf0f1;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    text-align: center;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #3498db;
    border-radius: 3px;
}

/* ==================== Group Box ==================== */
QGroupBox {
    border: 2px solid #bdc3c7;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    background-color: #3498db;
    color: white;
    border-radius: 4px;
    left: 10px;
}

/* ==================== Tool Tip ==================== */
QToolTip {
    background-color: #2c3e50;
    color: white;
    border: 1px solid #34495e;
    border-radius: 4px;
    padding: 6px;
}

/* ==================== Dialog ==================== */
QDialog {
    background-color: #f5f6f7;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* ==================== Splitter ==================== */
QSplitter::handle {
    background-color: #bdc3c7;
}

QSplitter::handle:hover {
    background-color: #3498db;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* ==================== Label Styling ==================== */
QLabel {
    color: #2c3e50;
}

QLabel[class="heading"] {
    font-size: 14pt;
    font-weight: bold;
    color: #2c3e50;
}

QLabel[class="subheading"] {
    font-size: 11pt;
    font-weight: 600;
    color: #34495e;
}

QLabel[class="error"] {
    color: #e74c3c;
}

QLabel[class="success"] {
    color: #27ae60;
}

QLabel[class="warning"] {
    color: #f39c12;
}

QLabel[class="info"] {
    color: #3498db;
}
"""

DARK_THEME = """
/* ==================== Dark Theme ==================== */
QMainWindow {
    background-color: #1e1e1e;
}

QWidget {
    font-family: "Segoe UI", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: #e0e0e0;
    background-color: #1e1e1e;
}

QMenuBar {
    background-color: #2d2d30;
    color: #e0e0e0;
    border-bottom: 1px solid #3e3e42;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
    color: #e0e0e0;
}

QMenuBar::item:selected {
    background-color: #3e3e42;
}

QMenu {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    color: #e0e0e0;
}

QMenu::item:selected {
    background-color: #007acc;
}

QDockWidget::title {
    background-color: #007acc;
    color: white;
}

QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
}

QPushButton:hover {
    background-color: #1177bb;
}

QPushButton:pressed {
    background-color: #007acc;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    color: #e0e0e0;
}

QComboBox {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    color: #e0e0e0;
}

QTreeView, QTableView, QListView {
    background-color: #252526;
    border: 1px solid #3e3e42;
    color: #e0e0e0;
}

QHeaderView::section {
    background-color: #2d2d30;
    color: #e0e0e0;
    border: none;
    border-right: 1px solid #3e3e42;
}

QTabBar::tab {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    color: #e0e0e0;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #007acc;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #424242;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #4e4e4e;
}
"""

def apply_professional_style(app):
    """Apply the professional style to the application"""
    app.setStyleSheet(PROFESSIONAL_STYLE)

def apply_dark_theme(app):
    """Apply the dark theme to the application"""
    app.setStyleSheet(DARK_THEME)

def generate_custom_stylesheet(primary_color="#3498db", accent_color="#2980b9", 
                                success_color="#27ae60", warning_color="#f39c12",
                                error_color="#e74c3c", bg_color="#ecf0f1", 
                                text_color="#2c3e50"):
    """
    Generate a custom stylesheet with user-defined colors.
    
    Args:
        primary_color: Main brand color (default: blue #3498db)
        accent_color: Darker shade for accents (default: #2980b9)
        success_color: Success state color (default: green #27ae60)
        warning_color: Warning state color (default: orange #f39c12)
        error_color: Error state color (default: red #e74c3c)
        bg_color: Background color (default: light gray #ecf0f1)
        text_color: Main text color (default: dark blue #2c3e50)
    
    Returns:
        str: Complete QSS stylesheet with custom colors
    """
    return f"""
/* ==================== Global Styles ==================== */
QMainWindow {{
    background-color: {bg_color};
}}

QWidget {{
    font-family: "Segoe UI", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: {text_color};
}}

/* ==================== Menu Bar ==================== */
QMenuBar {{
    background-color: {text_color};
    color: white;
    padding: 4px;
    border-bottom: 2px solid {accent_color};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
    color: white;
}}

QMenuBar::item:selected {{
    background-color: {accent_color};
}}

QMenuBar::item:pressed {{
    background-color: {primary_color};
}}

QMenu {{
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 25px 6px 12px;
    border-radius: 3px;
    color: {text_color};
}}

QMenu::item:selected {{
    background-color: {primary_color};
    color: white;
}}

/* ==================== Tool Bar ==================== */
QToolBar {{
    background-color: #ecf0f1;
    border: none;
    spacing: 3px;
    padding: 4px;
}}

QToolButton {{
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
    color: {text_color};
}}

QToolButton:hover {{
    background-color: {primary_color};
    border-color: {accent_color};
    color: white;
}}

QToolButton:pressed {{
    background-color: {accent_color};
}}

/* ==================== Push Buttons ==================== */
QPushButton {{
    background-color: {primary_color};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 500;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {accent_color};
}}

QPushButton:pressed {{
    background-color: #21618c;
}}

QPushButton:disabled {{
    background-color: #95a5a6;
    color: #bdc3c7;
}}

/* Success/Cancel button variants */
QPushButton[class="success"] {{
    background-color: {success_color};
}}

QPushButton[class="success"]:hover {{
    background-color: #229954;
}}

QPushButton[class="cancel"] {{
    background-color: #95a5a6;
}}

QPushButton[class="cancel"]:hover {{
    background-color: #7f8c8d;
}}

QPushButton[class="danger"] {{
    background-color: {error_color};
}}

QPushButton[class="danger"]:hover {{
    background-color: #c0392b;
}}

/* ==================== Line Edit ==================== */
QLineEdit {{
    background-color: white;
    border: 2px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: {primary_color};
    color: {text_color};
}}

QLineEdit:focus {{
    border-color: {primary_color};
}}

QLineEdit:disabled {{
    background-color: #ecf0f1;
    color: #95a5a6;
}}

/* ==================== Combo Box ==================== */
QComboBox {{
    background-color: white;
    border: 2px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
    min-width: 120px;
    color: {text_color};
}}

QComboBox:hover {{
    border-color: {primary_color};
}}

QComboBox:focus {{
    border-color: {primary_color};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {text_color};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: white;
    border: 2px solid {primary_color};
    selection-background-color: {primary_color};
    selection-color: white;
    outline: none;
}}

/* ==================== Spin Box ==================== */
QSpinBox, QDoubleSpinBox {{
    background-color: white;
    border: 2px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
    color: {text_color};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {primary_color};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background-color: transparent;
    border: none;
    width: 20px;
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: transparent;
    border: none;
    width: 20px;
}}

/* ==================== Table View ==================== */
QTableView {{
    background-color: white;
    alternate-background-color: #f8f9fa;
    gridline-color: #dee2e6;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    selection-background-color: {primary_color};
    selection-color: white;
    color: {text_color};
}}

QTableView::item {{
    padding: 4px;
}}

QTableView::item:hover {{
    background-color: #e3f2fd;
}}

QHeaderView::section {{
    background-color: #ecf0f1;
    color: {text_color};
    padding: 6px;
    border: none;
    border-right: 1px solid #bdc3c7;
    border-bottom: 2px solid {primary_color};
    font-weight: 600;
}}

QHeaderView::section:hover {{
    background-color: #d6dbdf;
}}

/* ==================== Tree View ==================== */
QTreeView {{
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    selection-background-color: {primary_color};
    selection-color: white;
    show-decoration-selected: 1;
    color: {text_color};
}}

QTreeView::item {{
    padding: 4px;
}}

QTreeView::item:hover {{
    background-color: #e3f2fd;
}}

QTreeView::item:selected {{
    background-color: {primary_color};
    color: white;
}}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{
    image: none;
    border-image: none;
}}

QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{
    image: none;
    border-image: none;
}}

/* ==================== Tab Widget ==================== */
QTabWidget::pane {{
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    background-color: white;
    top: -1px;
}}

QTabBar::tab {{
    background-color: #ecf0f1;
    color: {text_color};
    border: 1px solid #bdc3c7;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {primary_color};
    color: white;
}}

QTabBar::tab:hover:!selected {{
    background-color: #d6dbdf;
}}

/* ==================== Dock Widget ==================== */
QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    border: 1px solid #bdc3c7;
}}

QDockWidget::title {{
    background-color: {text_color};
    color: white;
    padding: 6px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 600;
}}

QDockWidget::close-button, QDockWidget::float-button {{
    background-color: transparent;
    border: none;
    padding: 3px;
}}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background-color: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
}}

/* ==================== Progress Bar ==================== */
QProgressBar {{
    border: 2px solid #bdc3c7;
    border-radius: 4px;
    background-color: white;
    text-align: center;
    color: {text_color};
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: {primary_color};
    border-radius: 2px;
}}

/* ==================== Scroll Bar ==================== */
QScrollBar:vertical {{
    background-color: #ecf0f1;
    width: 12px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: #bdc3c7;
    min-height: 20px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {primary_color};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: #ecf0f1;
    height: 12px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: #bdc3c7;
    min-width: 20px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {primary_color};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ==================== Status Bar ==================== */
QStatusBar {{
    background-color: {text_color};
    color: white;
    border-top: 2px solid {primary_color};
}}

QStatusBar::item {{
    border: none;
}}

/* ==================== Group Box ==================== */
QGroupBox {{
    border: 2px solid #bdc3c7;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    color: {text_color};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    background-color: {primary_color};
    color: white;
    border-radius: 4px;
    left: 10px;
}}

/* ==================== Check Box ==================== */
QCheckBox {{
    spacing: 6px;
    color: {text_color};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid #bdc3c7;
    border-radius: 3px;
    background-color: white;
}}

QCheckBox::indicator:checked {{
    background-color: {primary_color};
    border-color: {primary_color};
    image: none;
}}

QCheckBox::indicator:hover {{
    border-color: {primary_color};
}}

/* ==================== Radio Button ==================== */
QRadioButton {{
    spacing: 6px;
    color: {text_color};
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid #bdc3c7;
    border-radius: 9px;
    background-color: white;
}}

QRadioButton::indicator:checked {{
    background-color: {primary_color};
    border-color: {primary_color};
}}

QRadioButton::indicator:checked::after {{
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 4px;
    background-color: white;
}}

QRadioButton::indicator:hover {{
    border-color: {primary_color};
}}

/* ==================== Dialog Buttons ==================== */
QDialogButtonBox {{
    dialogbuttonbox-buttons-have-icons: 0;
}}

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ==================== Text Edit / Plain Text Edit ==================== */
QTextEdit, QPlainTextEdit {{
    background-color: white;
    border: 2px solid #bdc3c7;
    border-radius: 4px;
    selection-background-color: {primary_color};
    color: {text_color};
}}

QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {primary_color};
}}

/* ==================== Special Widget Classes ==================== */
/* Event Log Console Style */
QTextEdit#eventLog {{
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    border: none;
}}

/* Status indicators */
QLabel[class="status-good"] {{
    color: {success_color};
    font-weight: bold;
}}

QLabel[class="status-warning"] {{
    color: {warning_color};
    font-weight: bold;
}}

QLabel[class="status-error"] {{
    color: {error_color};
    font-weight: bold;
}}
"""
