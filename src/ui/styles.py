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

/* Titlebar / Menu container (custom) */
QWidget[class="titlebar"] {
    background-color: #2c3e50;
    padding: 8px 12px;
}

QLabel[class="title"] {
    color: #e6e6e6;
    font-weight: 700;
    font-size: 12pt;
    padding-left: 6px;
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
    border: 1px solid rgba(0,0,0,0.06);
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 600;
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

QLineEdit:read-only, QTextEdit:read-only, QPlainTextEdit:read-only {
    background-color: #f0f2f4;
    color: #7f8c8d;
}

QLineEdit[state="ok"] {
    border: 2px solid #27ae60;
    background-color: #eafaf1;
}

QLineEdit[state="error"] {
    border: 2px solid #e74c3c;
    background-color: #fdecea;
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

/* Dialog-specific headings for clearer hierarchy */
QDialog QLabel[class="heading"] {
    font-size: 13pt;
    font-weight: 700;
    color: #2c3e50;
    padding: 6px 0 8px 0;
}

QDialog QLabel[class="subheading"] {
    font-size: 10.5pt;
    font-weight: 600;
    color: #34495e;
    margin-bottom: 6px;
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

QLabel[class="status"] {
    font-size: 11pt;
    font-weight: 600;
    padding: 6px;
}

QLabel[status="info"] {
    color: #3498db;
}

QLabel[status="success"] {
    color: #27ae60;
}

QLabel[status="warning"] {
    color: #f39c12;
}

QLabel[status="error"] {
    color: #e74c3c;
}

QLabel[class="note"] {
    color: #6c757d;
    font-size: 9pt;
}

QLabel[class="code"], QLabel[class="code-strong"] {
    font-family: "Consolas", "Monaco", "Courier New", monospace;
}

QLabel[class="code"] {
    background-color: #f0f0f0;
    padding: 8px;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
}

QLabel[class="code-strong"] {
    font-weight: 600;
    font-size: 11pt;
}

QTextEdit[class="code"], QPlainTextEdit[class="code"] {
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    background-color: #f8f9fb;
    border: 1px solid #bdc3c7;
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

/* Titlebar / Menu container (dark theme) */
QWidget[class="titlebar"] {
    background-color: #2d2d30;
    padding: 8px 12px;
}

QLabel[class="title"] {
    color: #e0e0e0;
    font-weight: 700;
    font-size: 12pt;
    padding-left: 6px;
}

QPushButton {
    background-color: #0e639c;
    color: white;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 6px;
    padding: 8px 14px;
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

QLineEdit:read-only, QTextEdit:read-only, QPlainTextEdit:read-only {
    background-color: #252526;
    color: #9da0a2;
}

QLineEdit[state="ok"] {
    border: 2px solid #27ae60;
    background-color: #1e2f24;
}

QLineEdit[state="error"] {
    border: 2px solid #e74c3c;
    background-color: #3a1f1f;
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

QDialog {
    background-color: #1e1e1e;
}

QGroupBox {
    color: #e0e0e0;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}

QGroupBox::title {
    color: #e0e0e0;
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    background-color: #2d2d30;
    border-radius: 3px;
}

QLabel[class="status"] {
    font-size: 11pt;
    font-weight: 600;
    padding: 6px;
}

QLabel[status="info"] {
    color: #4aa3ff;
}

QLabel[status="success"] {
    color: #2ecc71;
}

QLabel[status="warning"] {
    color: #f1c40f;
}

QLabel[status="error"] {
    color: #e74c3c;
}

QLabel[class="note"] {
    color: #a0a4a8;
    font-size: 9pt;
}

QLabel[class="code"], QLabel[class="code-strong"] {
    font-family: "Consolas", "Monaco", "Courier New", monospace;
}

QLabel[class="code"] {
    background-color: #252526;
    padding: 8px;
    border: 1px solid #3e3e42;
    border-radius: 4px;
}

QLabel[class="code-strong"] {
    font-weight: 600;
    font-size: 11pt;
}

QTextEdit[class="code"], QPlainTextEdit[class="code"] {
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    background-color: #252526;
    border: 1px solid #3e3e42;
    color: #d4d4d4;
}
"""

IED_SCOUT_STYLE = """
/* ==================== IED Scout-like Theme ==================== */
/* Elegant, professional, Omicron-inspired blue and white theme */

QMainWindow {
    background-color: #ffffff;
}

QWidget {
    font-family: "Segoe UI", "Tahoma", "Ubuntu", Arial, sans-serif;
    font-size: 10pt;
    color: #333333;
}

/* ==================== Menu Bar ==================== */
QMenuBar {
    background-color: #f0f0f0;
    color: #000000;
    border-bottom: 1px solid #cccccc;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 10px;
    color: #000000;
    border-radius: 2px;
}

QMenuBar::item:selected {
    background-color: #005baa; /* Omicron Blue */
    color: white;
}

QMenu {
    background-color: white;
    border: 1px solid #a0a0a0;
    color: #000000;
}

QMenu::item {
    padding: 6px 25px 6px 12px;
}

QMenu::item:selected {
    background-color: #005baa;
    color: white;
}

/* ==================== Tool Bar ==================== */
QToolBar {
    background-color: #f8f8f8;
    border-bottom: 1px solid #d0d0d0;
    spacing: 4px;
    padding: 2px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 2px;
    padding: 4px;
    color: #333333;
}

QToolButton:hover {
    background-color: #e6f1f9;
    border: 1px solid #a0cfee;
}

QToolButton:pressed {
    background-color: #cce4f7;
    border: 1px solid #005baa;
}

/* ==================== Dock Widgets ==================== */
QDockWidget {
    border: 1px solid #d0d0d0;
}

QDockWidget::title {
    background-color: #005baa;
    color: white;
    padding: 6px;
    font-weight: bold;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
}

QDockWidget::close-button, QDockWidget::float-button {
    background-color: transparent;
    border: none;
    padding: 2px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: rgba(255, 255, 255, 0.3);
    border-radius: 2px;
}

/* ==================== Tree View ==================== */
QTreeView {
    background-color: white;
    border: 1px solid #c0c0c0;
    alternate-background-color: #f9f9f9;
    selection-background-color: #005baa;
    selection-color: white;
}

QTreeView::item {
    padding: 2px;
}

QTreeView::item:selected {
    background-color: #005baa;
    color: white;
}

QTreeView::item:hover:!selected {
    background-color: #e6f3ff;
}

QHeaderView::section {
    background-color: #e0e0e0;
    color: #333333;
    padding: 5px;
    border: none;
    border-right: 1px solid #c0c0c0;
    border-bottom: 1px solid #c0c0c0;
    font-weight: bold;
}

/* ==================== Table View ==================== */
QTableView {
    background-color: white;
    border: 1px solid #c0c0c0;
    gridline-color: #e0e0e0;
    alternate-background-color: #fcfcfc;
    selection-background-color: #005baa;
    selection-color: white;
}

QTableView::item {
    padding: 4px;
}

QTableView::item:selected {
    background-color: #005baa;
    color: white;
}

QTableView::item:hover:!selected {
    background-color: #e6f3ff;
}

/* ==================== Buttons ==================== */
QPushButton {
    background-color: #f0f0f0;
    border: 1px solid #adadad;
    border-radius: 3px;
    padding: 6px 14px;
    min-height: 22px;
    color: #333333;
}

QPushButton:hover {
    background-color: #e1e1e1;
    border-color: #005baa;
}

QPushButton:pressed {
    background-color: #cfe6fb;
    border-color: #005baa;
}

QPushButton[class="primary"] {
    background-color: #005baa;
    color: white;
    border: 1px solid #004a8b;
}

QPushButton[class="primary"]:hover {
    background-color: #006bcb;
}

/* ==================== Splitter ==================== */
QSplitter::handle {
    background-color: #d0d0d0;
}

QSplitter::handle:hover {
    background-color: #005baa;
}

/* ==================== Status Bar ==================== */
QStatusBar {
    background-color: #f0f0f0;
    color: #333333;
    border-top: 1px solid #cccccc;
}

/* ==================== Tab Widget ==================== */
QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background-color: white;
    top: -1px;
}

QTabBar::tab {
    background-color: #e0e0e0;
    border: 1px solid #c0c0c0;
    border-bottom: none;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    padding: 6px 12px;
    margin-right: 2px;
    color: #333333;
}

QTabBar::tab:selected {
    background-color: white;
    border-bottom: 1px solid white; 
    /* Make selected tab blend with pane */
    color: #005baa;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #d0d0d0;
}

/* ==================== Input Fields ==================== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 5px;
    background-color: white;
    selection-background-color: #005baa;
    color: #333333;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #005baa;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #555555;
}

/* ==================== Scroll Bars ==================== */
QScrollBar:vertical {
    background-color: #f0f0f0;
    width: 14px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    min-height: 20px;
    margin: 2px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}

QScrollBar:horizontal {
    background-color: #f0f0f0;
    height: 14px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #c0c0c0;
    min-width: 20px;
    margin: 2px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a0a0a0;
}

/* ==================== Status & Utility Classes ==================== */
QLabel[class="status-good"] {
    color: #008000;
    font-weight: bold;
}

QLabel[class="status-warning"] {
    color: #e67e22;
    font-weight: bold;
}

QLabel[class="status-error"] {
    color: #c0392b;
    font-weight: bold;
}

QLabel[class="code"], QLabel[class="code-strong"] {
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    background-color: #f5f5f5;
    padding: 4px;
    border: 1px solid #d0d0d0;
    border-radius: 2px;
}

QTextEdit[class="code"] {
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    background-color: #f5f5f5;
    border: 1px solid #d0d0d0;
}
"""

WINDOWS_11_STYLE = """
/* ==================== Windows 11 Style ==================== */
/* Mica-inspired, rounded corners, clean lines */

QMainWindow {
    background-color: #f3f3f3;
}

QWidget {
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: #202020;
}

/* ==================== Menu Bar ==================== */
QMenuBar {
    background-color: #f3f3f3;
    border-bottom: 1px solid #e5e5e5;
}

QMenuBar::item {
    background-color: transparent;
    padding: 8px 12px;
    border-radius: 4px;
    color: #202020;
    margin: 2px;
}

QMenuBar::item:selected {
    background-color: rgba(0, 0, 0, 0.04);
}

QMenuBar::item:pressed {
    background-color: rgba(0, 0, 0, 0.08);
}

QMenu {
    background-color: #ffffff; /* Acrylic-like solid for Qt */
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    padding: 6px;
    color: #202020;
}

QMenu::item {
    padding: 8px 30px 8px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0067c0; /* Accent color */
    color: white;
}

/* ==================== Dock Widgets ==================== */
QDockWidget {
    border: 1px solid #e5e5e5;
    /* titlebar-close-icon: url(none); */
    /* titlebar-normal-icon: url(none); */
}

QDockWidget::title {
    background-color: #ffffff;
    padding: 8px;
    border-radius: 8px 8px 0 0;
    font-weight: 600;
}

/* ==================== Buttons ==================== */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d1d1d1;
    border-bottom: 1px solid #bbbbbb; /* Slight depth */
    border-radius: 4px;
    padding: 6px 16px;
    color: #202020;
}

QPushButton:hover {
    background-color: #fbfbfb;
    border: 1px solid #d1d1d1;
}

QPushButton:pressed {
    background-color: #f0f0f0;
    border: 1px solid #d1d1d1;
    color: #555555;
}

QPushButton[class="primary"] {
    background-color: #0067c0;
    color: white;
    border: 1px solid #005a9e;
}

QPushButton[class="primary"]:hover {
    background-color: #0074d9;
}

/* ==================== Input Fields ==================== */
QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #d1d1d1;
    border-bottom: 2px solid #8e8e8e; /* Accent hint */
    border-radius: 4px;
    padding: 5px 8px;
    color: #202020;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-bottom: 2px solid #0067c0;
    background-color: #ffffff;
    color: #000000;
}

/* ==================== Tree/Table View ==================== */
QTreeView, QTableView, QListWidget {
    background-color: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    alternate-background-color: #fafafa;
    color: #202020;
}

QHeaderView::section {
    background-color: #ffffff;
    border: none;
    border-bottom: 1px solid #e5e5e5;
    padding: 6px;
    font-weight: 600;
    color: #202020;
}

QTreeView::item, QTableView::item {
    padding: 6px;
    border-radius: 4px;
}

QTreeView::item:selected, QTableView::item:selected {
    background-color: rgba(0, 103, 192, 0.1);
    color: #202020;
    border-left: 3px solid #0067c0;
}

QTreeView::item:hover:!selected, QTableView::item:hover:!selected {
    background-color: rgba(0, 0, 0, 0.03);
}

/* ==================== Tabs ==================== */
QTabWidget::pane {
    border: 1px solid #e5e5e5;
    background-color: #ffffff;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: transparent;
    padding: 8px 16px;
    margin: 4px;
    border-radius: 4px;
    color: #202020;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0067c0;
    font-weight: 600;
    border-bottom: 2px solid #0067c0;
}

QTabBar::tab:hover:!selected {
    background-color: rgba(0, 0, 0, 0.03);
}
"""

IOS_STYLE = """
/* ==================== iOS Style ==================== */
/* Flat, blurred/translucent feel, large touch targets, Apple-like fonts */

QMainWindow {
    background-color: #f2f2f7; /* System grouped background */
}

QWidget {
    font-family: -apple-system, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11pt; /* Slightly larger for readability */
    color: #000000;
}

/* ==================== Group Box (Card style) ==================== */
QGroupBox {
    background-color: #ffffff;
    border-radius: 10px;
    border: 1px solid #e5e5ea;
    margin-top: 10px;
    font-weight: 600;
    color: #000000;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 5px 10px;
    color: #8e8e93; /* System gray */
    font-size: 10pt;
    text-transform: uppercase;
}

/* ==================== Buttons ==================== */
QPushButton {
    background-color: #007aff; /* System Blue */
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 11pt;
}

QPushButton:pressed {
    background-color: #0051a8;
}

QPushButton[class="secondary"] {
    background-color: #e5e5ea;
    color: #007aff;
}

QPushButton:disabled {
    background-color: #d1d1d6;
    color: #8e8e93;
}

/* ==================== Lists/Trees (Table view style) ==================== */
QTreeView, QTableView, QListWidget {
    background-color: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    selection-background-color: #e5e5ea; /* Table selection gray */
    selection-color: #000000;
    outline: none;
    color: #000000;
}

QTreeView::item, QTableView::item {
    padding: 10px;
    border-bottom: 1px solid #c6c6c8; /* Separator lines */
}

QTreeView::item:selected, QTableView::item:selected {
    background-color: #d1d1d6;
    color: #000000;
}

QHeaderView::section {
    background-color: #f2f2f7;
    color: #8e8e93;
    padding: 8px;
    border: none;
    font-size: 10pt;
    text-transform: uppercase;
}

/* ==================== Inputs ==================== */
QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d1d1d1;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #007aff;
    color: #000000;
}

QLineEdit:focus {
    background-color: #ffffff;
    border: 1px solid #007aff;
    color: #000000;
}

/* ==================== Menu/Nav ==================== */
QMenuBar {
    background-color: #ffffff; /* Translucent bar normally */
    border-bottom: 1px solid #c6c6c8;
    color: #000000;
}

QMenuBar::item {
    background-color: transparent;
    padding: 10px 15px;
    color: #007aff;
}

QMenu {
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    padding: 8px;
    border: 1px solid #c6c6c8;
    color: #000000;
}

QMenu::item {
    padding: 10px 20px;
    border-radius: 6px;
    color: #000000;
}

QMenu::item:selected {
    background-color: #007aff;
    color: white;
}

/* ==================== Switch/Check ==================== */
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 10px;
    border: 2px solid #c6c6c8;
    background-color: white;
}

QCheckBox::indicator:checked {
    background-color: #34c759; /* System Green */
    border-color: #34c759;
}

/* ==================== Tab Bar ==================== */
QTabWidget::pane {
    border: none;
    background-color: #f2f2f7;
}

QTabBar::tab {
    background-color: transparent;
    color: #8e8e93;
    padding: 10px;
    font-weight: 600;
}

QTabBar::tab:selected {
    color: #007aff;
    border-bottom: 2px solid #007aff;
}
"""

def apply_professional_style(app):
    """Apply the professional style to the application"""
    app.setStyleSheet(PROFESSIONAL_STYLE)

def apply_dark_theme(app):
    """Apply the dark theme to the application"""
    app.setStyleSheet(DARK_THEME)

def apply_ied_scout_style(app):
    """Apply the IED Scout-like theme to the application"""
    app.setStyleSheet(IED_SCOUT_STYLE)

def apply_windows_11_style(app):
    """Apply the Windows 11 style to the application"""
    app.setStyleSheet(WINDOWS_11_STYLE)

def apply_ios_style(app):
    """Apply the iOS style to the application"""
    app.setStyleSheet(IOS_STYLE)

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

QLineEdit:read-only {{
    background-color: #f0f2f4;
    color: #7f8c8d;
}}

QLineEdit[state="ok"] {{
    border: 2px solid {success_color};
    background-color: rgba(39, 174, 96, 0.12);
}}

QLineEdit[state="error"] {{
    border: 2px solid {error_color};
    background-color: rgba(231, 76, 60, 0.12);
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

QLabel[class="status"] {{
    font-size: 11pt;
    font-weight: 600;
    padding: 6px;
}}

QLabel[status="info"] {{
    color: {primary_color};
}}

QLabel[status="success"] {{
    color: {success_color};
}}

QLabel[status="warning"] {{
    color: {warning_color};
}}

QLabel[status="error"] {{
    color: {error_color};
}}

QLabel[class="note"] {{
    color: {text_color};
    font-size: 9pt;
}}

QLabel[class="code"], QLabel[class="code-strong"] {{
    font-family: "Consolas", "Monaco", "Courier New", monospace;
}}

QLabel[class="code"] {{
    background-color: #f0f0f0;
    padding: 8px;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
}}

QLabel[class="code-strong"] {{
    font-weight: 600;
    font-size: 11pt;
}}

QTextEdit[class="code"], QPlainTextEdit[class="code"] {{
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    background-color: #f8f9fb;
    border: 1px solid #bdc3c7;
}}
"""
