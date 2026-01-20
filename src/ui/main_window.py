from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMenuBar, QToolBar, QDockWidget, QFileDialog, QMessageBox
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtCore import Qt, QTimer, QSettings
from typing import List
import os
import platform
import socket
import getpass

from src.ui.widgets.device_tree import DeviceTreeWidget
from src.ui.widgets.signals_view import SignalsViewWidget
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.scd_import_dialog import SCDImportDialog
from src.ui.widgets.scrollable_message_box import show_scrollable_error, ScrollableMessageBox
from src.models.device_models import DeviceType
from src.core.exporters import (
    export_network_config_script, 
    export_network_config_all_platforms, 
    export_device_list_csv, 
    export_goose_details_csv, 
    export_diagnostics_report,
    export_selected_ied_scl,
    export_ied_from_online_discovery
)
from src.core.watch_list_manager import WatchListManager
from src.ui.widgets.watch_list_widget import WatchListWidget
from src.ui.widgets.event_log_widget import EventLogWidget
from src.ui.widgets.title_bar import TitleBarWidget
from src.ui.widgets.modbus_slave_widget import ModbusSlaveWidget
from src.ui.widgets.iec61850_simulator_dialog import IEC61850SimulatorDialog
from src.ui.widgets.connection_progress_dialog import ConnectionProgressDialog
from src.ui.widgets.import_progress_dialog import ImportProgressDialog
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.core.workers import SCDImportWorker
from src.core.project_manager import ProjectManager
from src.utils.network_utils import NetworkUtils

class MainWindow(QMainWindow):
    """
    Main Application Window.
    Includes Menu Bar, Toolbar, Status Bar, and Docking areas for Panels.
    """
    def __init__(self, device_manager, event_logger=None):
        super().__init__()
        self.device_manager = device_manager
        self.event_logger = event_logger
        self.setWindowTitle("Scada Scout")
        
        # Scale initial size for Windows DPI and screen size
        base_width, base_height = 1280, 800
        min_width, min_height = 1200, 650
        scale = 1.0
        try:
            if platform.system() == "Windows":
                screen = QGuiApplication.primaryScreen()
                if screen:
                    scale = screen.logicalDotsPerInch() / 96.0
        except Exception:
            scale = 1.0

        scaled_width = int(base_width * scale)
        scaled_height = int(base_height * scale)
        scaled_min_width = int(min_width * scale)
        scaled_min_height = int(min_height * scale)

        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                scaled_width = min(scaled_width, int(avail.width() * 0.95))
                scaled_height = min(scaled_height, int(avail.height() * 0.90))
                scaled_min_width = min(scaled_min_width, max(800, int(avail.width() * 0.60)))
                scaled_min_height = min(scaled_min_height, max(500, int(avail.height() * 0.55)))
        except Exception:
            pass

        self.resize(scaled_width, scaled_height)
        # Set minimum size to ensure all controls fit in two-row layout
        self.setMinimumSize(scaled_min_width, scaled_min_height)
        
        # Use a frameless window so we can provide a custom title bar (VSCode-style)
        self.setWindowFlags((self.windowFlags() | Qt.Window) & ~Qt.WindowTitleHint)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        
        # Force window to be visible and get focus
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Enable VSCode-style dock behavior
        self.setDockNestingEnabled(True)
        # Remove empty central widget so docks fill the space proportionally
        self.setCentralWidget(None)
        
        # Initialize UI Components
        self._setup_ui()
        
        # Persistent Dialogs
        self.scd_dialog = None
        # Drag support for frameless title area
        self._drag_pos_main = None
        # Floating title bar (fallback) - sits above menu widget to ensure
        # controls are always visible and receive mouse events.
        try:
            self._floating_title = TitleBarWidget(self)
            self._floating_title.setObjectName("FloatingTitleBar")
            self._floating_title.move(0, 0)
            self._floating_title.show()
            self._floating_title.raise_()
        except Exception:
            self._floating_title = None
        
    def _setup_ui(self):
        # Initialize Managers first
        self.watch_list_manager = WatchListManager(self.device_manager)
        self.project_manager = ProjectManager(self.device_manager, self.watch_list_manager, self.event_logger, self)
        self._connect_project_signals()

        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        # Re-enable dock panels so Device Explorer, Signals, Watch List, and Event Log appear
        self._create_dock_panels()
        
    def _create_menus(self):
        # Replace the standard menu bar area with a container that includes
        # our custom TitleBarWidget above the QMenuBar so the app appears
        # frameless with a VSCode-like title area.
        from PySide6.QtWidgets import QMenuBar, QVBoxLayout

        menu_container = QWidget(self)
        # Mark menu container so stylesheet can match title/menu area
        menu_container.setProperty("class", "titlebar")
        vlayout = QVBoxLayout(menu_container)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(0)

        title_controls = TitleBarWidget(self)
        vlayout.addWidget(title_controls)

        menu_bar = QMenuBar(menu_container)
        vlayout.addWidget(menu_bar)

        # Set our composed widget as the menu area
        try:
            self.setMenuWidget(menu_container)
        except Exception:
            # Some platforms might not support setMenuWidget; fall back
            # to the default menu bar in that case.
            menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        
        # Project Actions
        new_project_action = QAction("&New Project", self)
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_project_action)
        
        open_project_action = QAction("&Open Project...", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_project_action)
        
        save_project_action = QAction("&Save Project", self)
        save_project_action.setShortcut("Ctrl+S")
        save_project_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_project_action)
        
        save_project_as_action = QAction("Save Project &As...", self)
        save_project_as_action.setShortcut("Ctrl+Shift+S")
        save_project_as_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(save_project_as_action)
        
        file_menu.addSeparator()

        # Import SCD Action
        import_scd_action = QAction("&Import SCD...", self)
        import_scd_action.setStatusTip("Import IEDs from SCD file")
        import_scd_action.triggered.connect(self._show_scd_import_dialog)
        file_menu.addAction(import_scd_action)

        file_menu.addSeparator()

        # Python Scripts
        run_script_once_action = QAction("Run Python Script (Once)...", self)
        run_script_once_action.setStatusTip("Run a Python script once")
        run_script_once_action.triggered.connect(self._run_script_once_from_file)
        file_menu.addAction(run_script_once_action)

        run_script_cont_action = QAction("Run Python Script (Continuously)...", self)
        run_script_cont_action.setStatusTip("Run a Python script on a timer")
        run_script_cont_action.triggered.connect(self._run_script_continuous_from_file)
        file_menu.addAction(run_script_cont_action)
        
        file_menu.addSeparator()

        # Export Menu
        export_menu = file_menu.addMenu("Export")
        
        # Network config (cross-platform)
        export_net_action = QAction("Network Config Script (Current Platform)...", self)
        export_net_action.triggered.connect(self._export_network_config)
        export_menu.addAction(export_net_action)
        
        # Network config (all platforms)
        export_net_all_action = QAction("Network Config Scripts (All Platforms)...", self)
        export_net_all_action.triggered.connect(self._export_network_config_all)
        export_menu.addAction(export_net_all_action)
        
        export_menu.addSeparator()
        
        # Device list
        export_dev_csv = QAction("Device List (.csv)...", self)
        export_dev_csv.triggered.connect(self._export_device_csv)
        export_menu.addAction(export_dev_csv)
        
        # GOOSE details
        export_goose = QAction("GOOSE Details (.csv)...", self)
        export_goose.triggered.connect(self._export_goose_csv)
        export_menu.addAction(export_goose)
        
        export_menu.addSeparator()
        
        # Diagnostics report
        export_diag = QAction("Diagnostics Report (.txt)...", self)
        export_diag.triggered.connect(self._export_diagnostics)
        export_menu.addAction(export_diag)
                
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Connection Menu
        conn_menu = menu_bar.addMenu("&Connection")
        
        # Connect Action
        connect_action = QAction("&Connect to Device...", self)
        connect_action.setStatusTip("Connect to a remote device as client")
        connect_action.triggered.connect(self._show_connection_dialog)
        conn_menu.addAction(connect_action)
        
        conn_menu.addSeparator()
        
        # Modbus Slave Server
        slave_server_action = QAction("&Modbus Slave Server...", self)
        slave_server_action.setStatusTip("Start Modbus slave/server for simulation")
        slave_server_action.triggered.connect(self._show_modbus_slave)
        conn_menu.addAction(slave_server_action)
        
        # IEC 61850 Simulator
        iec_simulator_action = QAction("&IEC 61850 Simulator...", self)
        iec_simulator_action.setStatusTip("Simulate IEDs from an SCD file")
        iec_simulator_action.triggered.connect(self._show_iec61850_simulator_dialog)
        conn_menu.addAction(iec_simulator_action)
        
        # View Menu
        self.view_menu = menu_bar.addMenu("&View")
        
        reset_layout_action = QAction("&Reset Layout", self)
        reset_layout_action.setStatusTip("Restore default panel arrangement")
        reset_layout_action.triggered.connect(self._on_reset_layout)
        self.view_menu.addAction(reset_layout_action)
        
        save_layout_action = QAction("&Save Layout as Default", self)
        save_layout_action.setStatusTip("Save current window size and positions as the default for next startup")
        save_layout_action.triggered.connect(self._on_save_default_layout)
        self.view_menu.addAction(save_layout_action)
        
        self.view_menu.addSeparator()

        python_scripts_action = QAction("Python &Scripts...", self)
        python_scripts_action.setStatusTip("Open the Python script editor")
        python_scripts_action.triggered.connect(self._open_python_script_dialog)
        self.view_menu.addAction(python_scripts_action)
        self.view_menu.addSeparator()
        
        # Settings action
        settings_action = QAction("⚙️ &Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.setStatusTip("Customize application appearance and behavior")
        settings_action.triggered.connect(self._show_settings_dialog)
        self.view_menu.addAction(settings_action)

        system_properties_action = QAction("System &Properties...", self)
        system_properties_action.setStatusTip("View system and network adapter details")
        system_properties_action.triggered.connect(self._show_system_properties)
        self.view_menu.addAction(system_properties_action)
        self.view_menu.addSeparator()
        
        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        
    def _create_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setObjectName("MainToolbar")
        self.addToolBar(self.toolbar)
        
    def _create_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Theme and font are applied from saved settings (or defaults) by MainWindow
        try:
            from PySide6.QtWidgets import QSizeGrip
            grip = QSizeGrip(self)
            self.status_bar.addPermanentWidget(grip)
        except Exception:
            pass
        
    def _create_dock_panels(self):
        from PySide6.QtWidgets import QSizePolicy
        
        self.dock_left = QDockWidget("Device Explorer", self)
        self.dock_left.setObjectName("DockDeviceExplorer")
        self.dock_left.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_left.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        self.device_tree = DeviceTreeWidget(self.device_manager, self.watch_list_manager)
        self.device_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_left.setWidget(self.device_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        
        # Connect Selection
        self.device_tree.selection_changed.connect(self._on_tree_selection_changed)
        
        # Connect Device Updates to Event Log Filter
        self.device_manager.device_added.connect(lambda d: self._update_event_log_devices())
        self.device_manager.device_removed.connect(lambda n: self._update_event_log_devices())
        self.device_manager.device_updated.connect(self._on_device_updated)

        # Right Panel: Signals & Charts (Data Visualization)
        self.dock_right = QDockWidget("Data Visualization", self)
        self.dock_right.setObjectName("DockDataVisualization")
        self.dock_right.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_right.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        self.signals_view = SignalsViewWidget(self.device_manager, self.watch_list_manager)
        self.signals_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_right.setWidget(self.signals_view)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)
        
        # Connect signals_view to device_tree for "Add to Live Data" functionality
        self.device_tree.signals_view = self.signals_view
        self.device_tree.add_to_live_data_requested.connect(self.signals_view.add_signal)
        
        # Watch List panel  
        self.dock_bottom = QDockWidget("Watch List", self)
        self.dock_bottom.setObjectName("DockWatchList")
        self.dock_bottom.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_bottom.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        self.watch_list_widget = WatchListWidget(self.watch_list_manager, self.device_manager)
        self.watch_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_bottom.setWidget(self.watch_list_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        
        # Event Log panel
        self.dock_events = QDockWidget("Event Log", self)
        self.dock_events.setObjectName("DockEventLog")
        self.dock_events.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_events.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        self.event_log_widget = EventLogWidget()
        if self.event_logger:
            self.event_log_widget.set_event_logger(self.event_logger)
        self.event_log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_events.setWidget(self.event_log_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        self.device_tree.show_event_log_requested.connect(self.dock_events.raise_)
        
        # Modbus Slave Server panel (hidden by default)
        self.dock_modbus_slave = QDockWidget("Modbus Slave Server", self)
        self.dock_modbus_slave.setObjectName("DockModbusSlaveServer")
        self.dock_modbus_slave.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_modbus_slave.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        self.modbus_slave_widget = ModbusSlaveWidget(
            event_logger=self.event_logger
        )
        self.modbus_slave_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_modbus_slave.setWidget(self.modbus_slave_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_modbus_slave)
        
        # Layout arrangement - tab event log and data viz together, watch list separate
        self.tabifyDockWidget(self.dock_right, self.dock_events)
        self.tabifyDockWidget(self.dock_bottom, self.dock_modbus_slave)
        self.dock_right.raise_()  # Show Data Visualization by default
        self.dock_modbus_slave.setVisible(False)
        
        # Apply initial layout with proper sizing
        # Attempt to load user-saved default layout first
        if not self._load_default_layout():
             # If no saved layout, use proportional starting defaults
             QTimer.singleShot(50, self._apply_initial_layout)
        else:
             # Ensure floating title is correctly positioned even after restore
             QTimer.singleShot(50, lambda: self.resizeEvent(None))
        
        # Add toggle actions to View menu
        self.view_menu.addAction(self.dock_left.toggleViewAction())
        self.view_menu.addAction(self.dock_right.toggleViewAction())
        self.view_menu.addAction(self.dock_bottom.toggleViewAction())
        self.view_menu.addAction(self.dock_events.toggleViewAction())
        self.view_menu.addAction(self.dock_modbus_slave.toggleViewAction())

    def _apply_initial_layout(self):
        """Apply flexible initial layout with proportional sizing."""
        # Get current window dimensions
        window_width = self.width()
        window_height = self.height()
        
        # Calculate proportional sizes (percentages of window size)
        left_panel_width = int(window_width * 0.22)    # 22% for device explorer
        right_panel_width = int(window_width * 0.78)   # 78% for data viz/event log
        bottom_panel_height = int(window_height * 0.35) # 35% for watch list
        
        # Apply minimum constraints only
        left_panel_width = max(200, left_panel_width)   # Minimum 200px
        right_panel_width = max(400, right_panel_width) # Minimum 400px
        bottom_panel_height = max(150, bottom_panel_height) # Minimum 150px
        
        # Set horizontal dock sizes proportionally (Qt uses these as relative weights)
        self.resizeDocks([self.dock_left, self.dock_right], [left_panel_width, right_panel_width], Qt.Horizontal)
        
        # Set vertical dock sizes  
        self.resizeDocks([self.dock_bottom], [bottom_panel_height], Qt.Vertical)

    def resizeEvent(self, event):
        # Keep floating title bar stretched across the top
        try:
            if hasattr(self, '_floating_title') and self._floating_title:
                self._floating_title.resize(self.width(), self._floating_title.height())
                self._floating_title.raise_()
        except Exception:
            pass
        return super().resizeEvent(event)

    # Window-level dragging: allow dragging when user clicks the title area
    def mousePressEvent(self, event):
        # Only begin drag on left button within title area region (top 40px)
        if event.button() == Qt.LeftButton and event.pos().y() <= 40:
            # Try native system move first (Wayland friendly)
            try:
                if self.windowHandle() and hasattr(self.windowHandle(), 'startSystemMove'):
                    if self.windowHandle().startSystemMove():
                        event.accept()
                        return
            except Exception:
                pass
                
            self._drag_pos_main = event.globalPosition().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos_main is None:
            return super().mouseMoveEvent(event)
        if event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint()
            delta = new_pos - self._drag_pos_main
            self._drag_pos_main = new_pos
            self.move(self.pos() + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos_main = None
        return super().mouseReleaseEvent(event)

    def _on_save_default_layout(self):
        """Saves current geometry and state as the user default."""
        settings = QSettings("ScadaScout", "Layout")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        self.status_bar.showMessage("Default layout saved.", 3000)

    def _load_default_layout(self):
        """Restores the user's saved default layout if it exists."""
        settings = QSettings("ScadaScout", "Layout")
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            return self.restoreState(state)
        return False

    def _on_reset_layout(self):
        """Restores the basic docking layout with flexible sizing."""
        self.dock_left.setVisible(True)
        self.dock_right.setVisible(True)
        self.dock_bottom.setVisible(True)
        self.dock_events.setVisible(True)
        
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        
        self.tabifyDockWidget(self.dock_right, self.dock_events)
        self.dock_right.raise_()
        
        # Reapply flexible initial sizing
        QTimer.singleShot(100, self._apply_initial_layout)

    def _show_settings_dialog(self):
        """Opens the Settings Dialog for appearance customization."""
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._apply_settings)
        dialog.exec()

    def _open_python_script_dialog(self):
        from src.ui.dialogs.python_script_dialog import PythonScriptDialog
        # Keep a reference on the main window so the dialog is not garbage-collected
        try:
            if getattr(self, '_python_script_dialog', None) is None:
                self._python_script_dialog = PythonScriptDialog(self.device_manager, self)
                self._python_script_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
            self._python_script_dialog.show()
            self._python_script_dialog.raise_()
            self._python_script_dialog.activateWindow()
        except Exception:
            # Fallback to creating a temporary dialog
            dlg = PythonScriptDialog(self.device_manager, self)
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.show()

    def _run_script_once_from_file(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "Run Python Script (Once)", "", "Python Files (*.py)")
        if not script_path:
            return
        try:
            with open(script_path, 'r') as f:
                code = f.read()
            self.device_manager.run_user_script_once(code)
        except Exception as e:
            QMessageBox.critical(self, "Script Error", str(e))

    def _run_script_continuous_from_file(self):
        from PySide6.QtWidgets import QInputDialog
        script_path, _ = QFileDialog.getOpenFileName(self, "Run Python Script (Continuously)", "", "Python Files (*.py)")
        if not script_path:
            return
        interval, ok = QInputDialog.getDouble(self, "Script Interval", "Interval (seconds):", 0.5, 0.05, 60.0, 2)
        if not ok:
            return
        try:
            with open(script_path, 'r') as f:
                code = f.read()
            name = os.path.splitext(os.path.basename(script_path))[0]
            self.device_manager.start_user_script(name, code, interval)
        except Exception as e:
            QMessageBox.critical(self, "Script Error", str(e))
    
    def _apply_settings(self):
        """Apply customized settings to the application."""
        from src.ui import styles
        settings = QSettings("ScadaScout", "UI")
        
        # Get theme
        # Get theme
        theme = settings.value("theme", "IED Scout-like")
        
        # Only apply custom colors when the theme is Custom or the checkbox is enabled,
        # otherwise keep the original theme color scheme intact.
        custom_colors = settings.value("use_custom_colors", False, type=bool)
        theme_is_custom = (settings.value("theme", "") == "Custom")

        if custom_colors or theme_is_custom:
            # Generate custom stylesheet based on saved colors (fall back to sensible defaults)
            primary_color = settings.value("primary_color", "#3498db")
            accent_color = settings.value("accent_color", "#2980b9")
            success_color = settings.value("success_color", "#27ae60")
            warning_color = settings.value("warning_color", "#f39c12")
            error_color = settings.value("error_color", "#e74c3c")
            # Prefer widget background for overall background, then main background
            bg_main = settings.value("bg_main", "#f5f6f7")
            bg_widget = settings.value("bg_widget", "#ffffff")
            bg_alternate = settings.value("bg_alternate", "#f8f9fa")
            bg_color = bg_widget
            text_color = settings.value("text_color", "#2c3e50")
            menu_bar_color = settings.value("menu_bar_color", "#2c3e50")
            dock_title_color = settings.value("dock_title_color", "#3498db")
            header_color = settings.value("header_color", "#34495e")
            status_bar_color = settings.value("status_bar_color", "#34495e")
            toolbar_color = settings.value("toolbar_color", "#34495e")
            selection_color = settings.value("selection_color", "#3498db")
            selection_text_color = settings.value("selection_text_color", "#ffffff")

            # Regenerate stylesheet with custom colors
            custom_style = styles.generate_custom_stylesheet(
                primary_color, accent_color, success_color, warning_color,
                error_color, bg_color, text_color
            )
            # Apply additional element-specific overrides for backgrounds and labels
            custom_overrides = f"""
QMainWindow {{ background-color: {bg_main}; }}
QWidget {{ color: {text_color}; }}
QLabel {{ color: {text_color}; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background-color: {bg_widget}; color: {text_color}; }}
QTreeView, QTableView, QListView {{ background-color: {bg_widget}; alternate-background-color: {bg_alternate}; color: {text_color}; }}
QGroupBox {{ color: {text_color}; }}
QTabWidget::pane {{ background-color: {bg_widget}; }}
QTabBar::tab:selected {{ color: {text_color}; }}
QMenuBar {{ background-color: {menu_bar_color}; }}
QDockWidget::title {{ background-color: {dock_title_color}; }}
QHeaderView::section {{ background-color: {header_color}; color: {text_color}; }}
QStatusBar {{ background-color: {status_bar_color}; color: {text_color}; }}
QToolBar {{ background-color: {toolbar_color}; }}
QTreeView, QTableView, QListView {{ selection-background-color: {selection_color}; selection-color: {selection_text_color}; }}
QLineEdit, QTextEdit, QPlainTextEdit {{ selection-background-color: {selection_color}; selection-color: {selection_text_color}; }}
"""
            base_style = custom_style + "\n" + custom_overrides
        else:
            # Use predefined theme
            if theme == "Dark":
                base_style = styles.DARK_THEME
            elif theme == "IED Scout-like":
                base_style = styles.IED_SCOUT_STYLE
            elif theme == "Windows 11":
                base_style = styles.WINDOWS_11_STYLE
            elif theme == "iOS Style":
                base_style = styles.IOS_STYLE
            else:
                base_style = styles.PROFESSIONAL_STYLE
        
        # Apply font settings
        font_family = settings.value("font_family", "Segoe UI")
        font_size = settings.value("font_size", 10, type=int)
        from PySide6.QtGui import QFont
        app_font = QFont(font_family, font_size)
        QApplication.instance().setFont(app_font)

        # Layout sizes
        widget_padding = settings.value("widget_padding", 8, type=int)
        button_padding = settings.value("button_padding", 8, type=int)
        border_radius = settings.value("border_radius", 4, type=int)
        button_height = settings.value("button_height", 32, type=int)
        input_height = settings.value("input_height", 32, type=int)
        icon_size = settings.value("icon_size", 24, type=int)

        # Windows DPI scaling: scale pixel-based sizes so controls aren't tiny
        try:
            if platform.system() == "Windows":
                screen = QApplication.primaryScreen()
                if screen:
                    scale = screen.logicalDotsPerInch() / 96.0
                    widget_padding = max(2, int(widget_padding * scale))
                    button_padding = max(2, int(button_padding * scale))
                    border_radius = max(2, int(border_radius * scale))
                    button_height = max(20, int(button_height * scale))
                    input_height = max(20, int(input_height * scale))
                    icon_size = max(16, int(icon_size * scale))
        except Exception:
            pass

        # Build overrides for sizes and fonts so QSS doesn't lock to defaults
        overrides = f"""
QWidget {{ font-size: {font_size}pt; }}
QPushButton {{ padding: {button_padding}px; min-height: {button_height}px; border-radius: {border_radius}px; }}
QToolButton {{ padding: {button_padding}px; border-radius: {border_radius}px; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ padding: {widget_padding}px; min-height: {input_height}px; border-radius: {border_radius}px; }}
QMenuBar::item {{ padding: {widget_padding}px {button_padding + 6}px; font-size: {font_size + 1}pt; }}
QTabBar::tab {{ padding: {widget_padding + 2}px {button_padding + 8}px; font-size: {font_size + 1}pt; }}
"""
        # Style variants (Modern / Classic / Flat) only add shape/layout tweaks, not color
        style_variant = settings.value("style", "Modern")
        style_extra = ""
        if style_variant == "Modern":
            style_extra = f"""
    QPushButton {{ border-radius: {max(4, border_radius)}px; padding: {button_padding + 2}px; }}
    QToolButton {{ border-radius: {max(4, border_radius)}px; }}
    QWidget {{ border-radius: {max(4, border_radius)}px; }}
    """
        elif style_variant == "Classic":
            style_extra = f"""
    QPushButton {{ border-radius: {max(2, border_radius // 2)}px; padding: {max(4, button_padding - 2)}px; }}
    QToolButton {{ border-radius: {max(2, border_radius // 2)}px; }}
    QWidget {{ border-radius: {max(2, border_radius // 2)}px; }}
    QWidget {{ font-size: {max(8, font_size - 1)}pt; }}
    """
        elif style_variant == "Flat":
            style_extra = f"""
    QPushButton {{ border-radius: {max(6, border_radius + 2)}px; padding: {button_padding + 4}px; border: none; }}
    QToolButton {{ border-radius: {max(6, border_radius + 2)}px; }}
    QWidget {{ border-radius: {max(6, border_radius + 2)}px; }}
    """
        # Only append style_extra if not already present in base_style
        overrides += "\n" + style_extra

        QApplication.instance().setStyleSheet(base_style + "\n" + overrides)

        # Apply icon size to toolbar if present
        try:
            if hasattr(self, 'toolbar') and self.toolbar:
                from PySide6.QtCore import QSize
                self.toolbar.setIconSize(QSize(icon_size, icon_size))
        except Exception:
            pass

        # Apply window opacity
        try:
            opacity = settings.value("window_opacity", 100, type=int)
            self.setWindowOpacity(max(0.5, min(1.0, opacity / 100.0)))
        except Exception:
            pass

        # Apply menu icon visibility
        try:
            show_icons = settings.value("show_icons", True, type=bool)
            QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, not show_icons)
        except Exception:
            pass

        # Apply basic UI animation toggles
        try:
            animations = settings.value("animations_enabled", True, type=bool)
            QApplication.setEffectEnabled(Qt.UI_AnimateCombo, animations)
            QApplication.setEffectEnabled(Qt.UI_AnimateTooltip, animations)
            QApplication.setEffectEnabled(Qt.UI_AnimateMenu, animations)
        except Exception:
            pass
        
        # Update console / monospace font for event log (use keys from SettingsDialog)
        monospace_font_family = settings.value("monospace_font", "Consolas")
        monospace_font_size = settings.value("monospace_size", 9, type=int)
        try:
            self.event_log_widget.update_font(monospace_font_family, monospace_font_size)
        except Exception:
            pass
        
        # Force repaint
        self.repaint()

    def _show_connection_dialog(self):
        """Opens the Connection Dialog."""
        dialog = ConnectionDialog(self)
        if dialog.exec():
            config = dialog.get_config()
            try:
                self.device_manager.add_device(config)
                self._connect_with_progress(config.name)
            except ValueError as e:
                QMessageBox.critical(self, "Error", f"Error adding device: {e}")
    
    def _connect_with_progress(self, device_name: str):
        """Connect to device with progress dialog."""
        progress_dialog = ConnectionProgressDialog(device_name, self)
        self.device_manager.connection_progress.connect(
            lambda name, msg, pct: progress_dialog.update_progress(msg, pct) if name == device_name else None
        )
        progress_dialog.retry_requested.connect(
            lambda: self.device_manager.connect_device(device_name)
        )
        QTimer.singleShot(100, lambda: self.device_manager.connect_device(device_name))
        progress_dialog.exec()
        
    def _update_event_log_devices(self):
        """Updates the device filtering list in Event Log."""
        devices = [d.config.name for d in self.device_manager.get_all_devices()]
        devices.sort()
        self.event_log_widget.update_device_list(devices)

    def _show_scd_import_dialog(self):
        """Opens the SCD Import Dialog."""
        if not self.scd_dialog:
            self.scd_dialog = SCDImportDialog(self, event_logger=self.event_logger)
            
        if self.scd_dialog.exec():
            try:
                configs = self.scd_dialog.get_selected_configs()
            except Exception as e:
                show_scrollable_error(self, "Import Error", "Failed to retrieve selected devices configuration.", str(e))
                return

            if not configs:
                return
            
            progress = ImportProgressDialog(self)
            progress.set_progress(0, len(configs))
            progress.show()
            
            # Pass core manager (not Qt wrapper) to avoid cross-thread issues
            self.scd_import_worker = SCDImportWorker(self.device_manager._core, configs, self.event_logger)
            self.scd_import_worker.log.connect(progress.add_log)
            self.scd_import_worker.progress.connect(progress.set_progress)
            # Handle device addition notifications to update UI tree
            self.scd_import_worker.device_added.connect(lambda name: self.device_manager.device_updated.emit(name))
            self.scd_import_worker.finished_import.connect(
                lambda count, errors: self._on_scd_import_finished(progress, count, errors)
            )
            self.scd_import_worker.finished.connect(self.scd_import_worker.deleteLater)
            self.scd_import_worker.start()

    def _on_scd_import_finished(self, progress_dialog, count: int, errors: List[str]):
        progress_dialog.finish()

        if errors:
            show_scrollable_error(self, "Import Errors", "Some devices failed to import:", "\n".join(errors))
        else:
            self.status_bar.showMessage(f"Successfully imported {count} devices.", 5000)
        
        # Refresh event log device list
        self._update_event_log_devices()

        # Collapse tree after multi-device import
        if count > 1:
            self.device_tree.tree_view.collapseAll()
             
        if count > 1:
            self.device_tree.tree_view.collapseAll()

    def _export_network_config(self):
        """Export network configuration script for current platform"""
        system = platform.system()
        if system == "Windows":
            default_name = "network_config.bat"
            filter_str = "Batch Files (*.bat)"
        else:
            default_name = "network_config.sh"
            filter_str = "Shell Scripts (*.sh)"
        
        fname, _ = QFileDialog.getSaveFileName(self, "Export Network Configuration", default_name, filter_str)
        
        if fname:
            devices = self.device_manager.get_all_devices()
            success, msg = export_network_config_script(devices, fname)
            
            if success:
                if system == "Windows":
                    instructions = f"Script created: {fname}\n\nTo use:\n1. Right-click the .bat file\n2. Select 'Run as Administrator'\n3. Follow on-screen prompts"
                else:
                    instructions = f"Script created: {fname}\n\nTo use:\n1. Open terminal in the script directory\n2. Run: sudo bash {os.path.basename(fname)}\n3. Enter your password when prompted"
                QMessageBox.information(self, "Export Successful", instructions)
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export network config:", msg)

    def _export_network_config_all(self):
        """Export network configuration scripts for all platforms"""
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory for Network Scripts", "", QFileDialog.ShowDirsOnly)
        
        if output_dir:
            devices = self.device_manager.get_all_devices()
            success, msg = export_network_config_all_platforms(devices, output_dir)
            if success:
                QMessageBox.information(self, "Export Successful", f"Network configuration scripts created in:\n{output_dir}\n\n{msg}\n\nSee README.txt in the output directory for usage instructions.")
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export scripts:", msg)

    def _export_device_csv(self):
        """Export device list to CSV"""
        fname, _ = QFileDialog.getSaveFileName(self, "Export Device List", "devices.csv", "CSV Files (*.csv)")
        if fname:
            devices = self.device_manager.get_all_devices()
            success, msg = export_device_list_csv(devices, fname)
            if success:
                self.status_bar.showMessage(f"Exported: {msg}", 3000)
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export device list:", msg)

    def _export_goose_csv(self):
        """Export GOOSE details to CSV"""
        scd_path = None
        devices = self.device_manager.get_all_devices()
        for dev in devices:
            if dev.config.scd_file_path:
                scd_path = dev.config.scd_file_path
                break
        
        if not scd_path:
            scd_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Source SCD for GOOSE Export",
                "",
                "SCL/Archive Files (*.scd *.cid *.icd *.xml *.zip *.tar *.tar.gz *.tgz *.7z *.rar *.sz)"
            )
            if not scd_path:
                return
        
        fname, _ = QFileDialog.getSaveFileName(self, "Export GOOSE Details", "goose_details.csv", "CSV Files (*.csv)")
        if fname:
            success, msg = export_goose_details_csv(scd_path, fname)
            if success:
                self.status_bar.showMessage(f"Exported: {msg}", 3000)
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export GOOSE details:", msg)

    def _export_selected_ied_scl(self):
        """Export selected IEC 61850 IED to IID/ICD/SCD"""
        selected_devices = self.device_tree.get_selected_device_names()
        if not selected_devices:
            QMessageBox.information(self, "No Selection", "Select an IEC 61850 IED in the Device Explorer first.")
            return

        if len(selected_devices) > 1:
            QMessageBox.information(self, "Multiple Selection", "Select a single IED to export.")
            return

        self._export_ied_scl_by_device(selected_devices[0])

    def _export_ied_scl_by_device(self, device_name: str):
        """Export a specific IEC 61850 IED by device name."""
        device = self.device_manager.get_device(device_name)
        if not device or device.config.device_type != DeviceType.IEC61850_IED:
            QMessageBox.information(self, "Invalid Selection", "Selected device is not an IEC 61850 IED.")
            return

        default_name = f"{device.config.name}.icd"
        filter_str = "SCL Files (*.iid *.icd *.scd)"
        fname, _ = QFileDialog.getSaveFileName(self, "Export Selected IED", default_name, filter_str)
        if not fname:
            return

        # Check if device has SCD file
        scd_path = device.config.scd_file_path
        
        if scd_path and os.path.exists(scd_path):
            # Export from SCD file
            success, msg = export_selected_ied_scl(scd_path, device.config.name, fname)
        else:
            # Generate from online discovery
            if not device.root_node or not device.root_node.children:
                QMessageBox.warning(
                    self,
                    "No Data Model",
                    f"Device '{device.config.name}' has not been discovered yet.\n\n"
                    "Please connect to the device first to discover its data model."
                )
                return
            
            success, msg = export_ied_from_online_discovery(device, fname)
        
        if success:
            self.status_bar.showMessage(f"Exported: {msg}", 3000)
        else:
            show_scrollable_error(self, "Export Failed", "Failed to export selected IED:", msg)

    def _export_diagnostics(self):
        """Export comprehensive diagnostics report"""
        fname, _ = QFileDialog.getSaveFileName(self, "Export Diagnostics Report", "diagnostics_report.txt", "Text Files (*.txt)")
        if fname:
            devices = self.device_manager.get_all_devices()
            success, msg = export_diagnostics_report(devices, fname)
            if success:
                QMessageBox.information(self, "Export Successful", f"Diagnostics report saved to:\n{fname}\n\nThis report includes:\n• System information\n• Network interfaces\n• Device status\n• Connectivity tests")
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export diagnostics:", msg)

    def _show_system_properties(self):
        """Show detailed system and network adapter properties."""
        try:
            import psutil
        except Exception:
            psutil = None

        details_lines = []

        platform_info = NetworkUtils.get_platform_info()
        details_lines.append("SYSTEM")
        details_lines.append(f"Hostname: {platform_info.get('hostname', 'unknown')}")
        details_lines.append(f"FQDN: {socket.getfqdn()}")
        details_lines.append(f"User: {getpass.getuser()}")
        details_lines.append(f"OS: {platform_info.get('system', '')} {platform_info.get('release', '')} ({platform_info.get('version', '')})")
        details_lines.append(f"Machine: {platform_info.get('machine', 'unknown')}")
        details_lines.append(f"Processor: {platform_info.get('processor', 'unknown') or 'unknown'}")
        details_lines.append(f"Python: {platform.python_version()}")
        details_lines.append(f"Local IP: {platform_info.get('local_ip', 'unknown')}")
        details_lines.append("")
        details_lines.append("NETWORK INTERFACES")

        if psutil:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            link_families = set(filter(None, [getattr(psutil, "AF_LINK", None), getattr(socket, "AF_PACKET", None)]))

            for name in sorted(addrs.keys()):
                stat = stats.get(name)
                status = "UP" if stat and stat.isup else "DOWN"
                speed = f"{stat.speed} Mbps" if stat and stat.speed else "unknown"
                mtu = f"{stat.mtu}" if stat and stat.mtu else "unknown"
                details_lines.append(f"{name}  [{status}]  speed={speed}  mtu={mtu}")

                addr_list = addrs.get(name, [])
                macs = []
                had_ip = False
                for addr in addr_list:
                    if addr.family in link_families:
                        if addr.address:
                            macs.append(addr.address)
                    elif addr.family == socket.AF_INET:
                        had_ip = True
                        details_lines.append(
                            f"  IPv4: {addr.address}  netmask={addr.netmask or 'n/a'}  broadcast={addr.broadcast or 'n/a'}"
                        )
                    elif addr.family == socket.AF_INET6:
                        had_ip = True
                        details_lines.append(
                            f"  IPv6: {addr.address}  netmask={addr.netmask or 'n/a'}  scope={getattr(addr, 'scope_id', 'n/a')}"
                        )

                if macs:
                    details_lines.append(f"  MAC: {', '.join(macs)}")
                if not had_ip:
                    details_lines.append("  IP: (none)")

                details_lines.append("")
        else:
            interfaces = NetworkUtils.get_network_interfaces()
            for iface in interfaces:
                status = "UP" if iface.is_up else "DOWN"
                details_lines.append(f"{iface.name}  [{status}]")
                details_lines.append(f"  IPv4: {iface.ip_address}  netmask={iface.netmask}")
                if iface.mac_address:
                    details_lines.append(f"  MAC: {iface.mac_address}")
                details_lines.append("")

        details = "\n".join(details_lines).strip()
        dlg = ScrollableMessageBox(
            "System Properties",
            "System and network adapter details",
            details,
            self
        )
        dlg.exec()

    def _show_modbus_slave(self):
        """Show and activate Modbus slave server dock"""
        self.dock_modbus_slave.setVisible(True)
        self.dock_modbus_slave.raise_()
        settings = QSettings("ScadaScout", "UI")
        if not settings.value("modbus_slave_info_shown", False):
            QMessageBox.information(self, "Modbus Slave Server", "This feature allows SCADA Scout to act as a Modbus TCP slave/server.\n\nUse cases:\n• Simulate devices for testing clients\n• Create virtual test environments\n• Act as a protocol gateway\n\nClick 'Start Server' to begin listening for connections.")
            settings.setValue("modbus_slave_info_shown", True)

    def _show_iec61850_simulator_dialog(self):
        """Open the IEC 61850 simulator configuration dialog"""
        from src.ui.widgets.iec61850_simulator_dialog import IEC61850SimulatorDialog
        from PySide6.QtWidgets import QDialog
        
        dialog = IEC61850SimulatorDialog(self, event_logger=self.event_logger)
        if dialog.exec() == QDialog.Accepted:
            configs = dialog.get_selected_configs()
            if not configs:
                return
                
            for config in configs:
                # Add to device manager
                self.device_manager.add_device(config)
                # Automatically start the server
                self.device_manager.connect_device(config.name)
                
                if self.event_logger:
                    self.event_logger.info("Simulator", f"Started simulation for {config.name} on {config.ip_address}:{config.port}")
            
            QMessageBox.information(
                self, 
                "Simulator Started", 
                f"Successfully started {len(configs)} IEC 61850 simulated IEDs.\nCheck the Device Explorer for status."
            )

    def _connect_project_signals(self):
        """Connect project manager signals for UI feedback."""
        self.project_manager.progress_updated.connect(self._on_project_progress)
        self.project_manager.project_loaded.connect(self._on_project_loaded)
        self.project_manager.project_saved.connect(self._on_project_saved)
        self.project_manager.error_occurred.connect(self._on_project_error)

    def _on_project_progress(self, percentage, message):
        self.status_bar.showMessage(f"{message} ({percentage}%)")
        if percentage == 100:
            QTimer.singleShot(3000, lambda: self.status_bar.showMessage("Ready"))

    def _on_project_loaded(self):
        # Restore UI state
        data = getattr(self.project_manager, 'ui_data', {})
        if data.get('window_state'):
            self.restoreState(data['window_state'])
        if data.get('window_geometry'):
            self.restoreGeometry(data['window_geometry'])
        
        # Clear/Refresh UI components
        self.device_tree.clear()
        for device in self.device_manager.get_all_devices():
            self.device_tree.add_device(device)
            
        self.status_bar.showMessage(f"Project loaded: {os.path.basename(self.project_manager.current_project_path)}", 5000)
        self.event_logger.info("Project", f"Successfully loaded project from {self.project_manager.current_project_path}")

    def _on_project_saved(self, filepath):
        self.status_bar.showMessage(f"Project saved to: {os.path.basename(filepath)}", 5000)
        self.event_logger.info("Project", f"Successfully saved project to {filepath}")

    def _on_project_error(self, message):
        QMessageBox.critical(self, "Project Error", message)

    # Project Management Handlers
    def _on_new_project(self):
        """Clears the workspace for a new project."""
        reply = QMessageBox.question(self, 'New Project', 
                                    "This will clear all current devices and signals. Continue?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.device_manager.clear_all_devices()
            self.watch_list_manager.clear_all()
            self.project_manager.current_project_path = None
            self.status_bar.showMessage("New project started", 3000)

    def _on_open_project(self):
        """Opens a project file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.mss);;All Files (*)")
        if file_path:
            self.project_manager.load_project(file_path)

    def _on_save_project(self):
        """Saves current project to the current file path."""
        if self.project_manager.current_project_path:
            self._save_project_to_path(self.project_manager.current_project_path)
        else:
            self._on_save_project_as()

    def _on_save_project_as(self):
        """Saves current state to a new project file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "Project Files (*.mss);;All Files (*)")
        if file_path:
            if not file_path.endswith('.mss'):
                file_path += '.mss'
            self._save_project_to_path(file_path)

    def _save_project_to_path(self, file_path):
        # Capture current UI state
        state = self.saveState().data()
        geometry = self.saveGeometry().data()
        
        # Get current settings
        app_settings = {
            'theme': QSettings().value("theme", "Professional"),
            'font_size': QSettings().value("font_size", 10)
        }
        
        self.project_manager.save_project(file_path, state, geometry, app_settings)

    def _on_tree_selection_changed(self, node, device_name):
        """Updates the signals view based on selected tree node."""
        import logging
        logger = logging.getLogger("MainWindow")
        logger.debug(f"MainWindow: Selection received for {device_name}. Node type: {type(node)}")
        # Only filter view on selection; do NOT auto-add to live data (avoids bulk DA adds during parsing)
        try:
            self.signals_view.set_filter_node(node, device_name)
        except Exception:
            logger.exception("MainWindow: Failed to update signals view on selection")

    def _on_device_updated(self, device_name):
        """Called when a device configuration or internal model changes."""
        self._update_event_log_devices()
        
        # If this device is currently selected in Signals View, refresh its signal list
        if device_name == self.signals_view.current_device_name:
            device = self.device_manager.get_device(device_name)
            if device:
                # Passing the device object tells SignalTableModel to use device.root_node
                self.signals_view.set_filter_node(device, device_name)

    def closeEvent(self, event):
        """Handle window close event."""
        # Auto-save layout if enabled in settings
        settings = QSettings("ScadaScout", "UI")
        if settings.value("auto_save_layout", True, type=bool):
            self._on_save_default_layout()
            
        super().closeEvent(event)
