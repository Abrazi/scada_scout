import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QMenuBar, QToolBar, QStatusBar, QTreeView, QTableView, 
    QSplitter, QLabel, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon

class MainWindow(QMainWindow):
    """
    Main Application Window for SCADA Scout.
    Layout:
        - Menu Bar
        - Tool Bar
        - Central Widget:
            - Splitter (Horizontal):
                - Left: Device Tree (QTreeView)
                - Right: Splitter (Vertical):
                    - Top: Signal List (QTableView)
                    - Bottom: Live Chart (Placeholder)
        - Status Bar
    """
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SCADA Scout - Industrial Protocol Analyzer")
        self.resize(1200, 800)

        # -- Core Layout Components --
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # -- UI Setup --
        self._create_actions()
        self._create_menubar()
        self._create_toolbar()
        self._create_statusbar()
        self._create_panels()

    def _create_actions(self):
        """Initialize QActions for menus and toolbar."""
        # File Actions
        self.act_exit = QAction("Exit", self)
        self.act_exit.setShortcut("Ctrl+Q")
        self.act_exit.triggered.connect(self.close)

        # Connection Actions
        self.act_connect = QAction("Connect...", self)
        self.act_connect.setStatusTip("Open connection dialog")
        
        self.act_disconnect = QAction("Disconnect", self)
        self.act_disconnect.setStatusTip("Close current connection")
        self.act_disconnect.setEnabled(False)

        # View Actions
        self.act_toggle_log = QAction("Toggle Log", self)
        self.act_toggle_log.setCheckable(True)

        # Help Actions
        self.act_about = QAction("About", self)

    def _create_menubar(self):
        """Create the Main Menu Bar."""
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.act_exit)

        # Connection Menu
        conn_menu = menu_bar.addMenu("&Connection")
        conn_menu.addAction(self.act_connect)
        conn_menu.addAction(self.act_disconnect)

        # View Menu
        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(self.act_toggle_log)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.act_about)

    def _create_toolbar(self):
        """Create the Main Toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        toolbar.addAction(self.act_connect)
        toolbar.addAction(self.act_disconnect)
        toolbar.addSeparator()

    def _create_statusbar(self):
        """Create the Status Bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Permanent widgets
        self.lbl_connection_state = QLabel("Disconnected")
        self.lbl_connection_state.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.lbl_connection_state)

        self.status_bar.showMessage("Ready")

    def _create_panels(self):
        """Create the Dockable-like layout using QSplitter."""
        
        # Main Horizontal Splitter (Left vs Right)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)

        # -- Left Panel: Device Tree --
        self.device_tree = QTreeView()
        self.device_tree.setHeaderHidden(False)
        self.device_tree.setRootIsDecorated(True)
        # Mock model capability would go here
        
        # Wrap in a frame or container if needed, adding directly for now
        self.main_splitter.addWidget(self.device_tree)

        # -- Right Panel: Vertical Splitter (Signals vs Chart) --
        self.right_splitter = QSplitter(Qt.Vertical)
        
        # Top Right: Signal Table
        self.signal_table = QTableView()
        self.signal_table.setAlternatingRowColors(True)
        self.right_splitter.addWidget(self.signal_table)

        # Bottom Right: Chart Placeholder
        # In Stage 5 we will replace this with a real Chart View
        self.chart_placeholder = QLabel("Live Chart Area")
        self.chart_placeholder.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setStyleSheet("background-color: #2b2b2b; color: #aaaaaa;")
        self.right_splitter.addWidget(self.chart_placeholder)

        self.main_splitter.addWidget(self.right_splitter)

        # Set initial sizes (ratio 1:3 for Tree:Content)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)

        # Set initial sizes for right splitter (ratio 2:1 for Table:Chart)
        self.right_splitter.setStretchFactor(0, 2)
        self.right_splitter.setStretchFactor(1, 1)
