from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMenuBar, QToolBar, QDockWidget, QFileDialog, QMessageBox
from PySide6.QtGui import QAction, QGuiApplication, QDesktopServices
from PySide6.QtCore import Qt, QTimer, QSettings, QUrl
from typing import List
import os
import platform
import socket
import getpass

from src.ui.widgets.device_tree import DeviceTreeWidget
from src.ui.widgets.signals_view import SignalsViewWidget
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
from src.ui.dialogs.ai_assistant_dialog import AIAssistantDialog
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
        
        # Initialize Theme Manager
        from src.ui.theme_manager import get_theme_manager
        self.theme_manager = get_theme_manager()
        self.theme_manager.apply_to_application(QApplication.instance())
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Store reference to title bar (will be set later)
        self._title_bar = None
        
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
        
        # Use frameless window with custom VSCode-style title bar
        self.setWindowFlags(Qt.Window)
        
        # Force window to be visible and get focus
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Enable VSCode-style dock behavior
        self.setDockNestingEnabled(True)
        
        # Initialize UI Components
        self._setup_ui()
        
        # Persistent Dialogs
        self.scd_dialog = None
        # Drag support for title area
        self._drag_pos_main = None
        # No floating title bar needed since we use standard menu bar
        self._floating_title = None
        
    def _setup_ui(self):
        # Initialize Managers first
        self.watch_list_manager = WatchListManager(self.device_manager)
        self.project_manager = ProjectManager(self.device_manager, self.watch_list_manager, self.event_logger, self)
        self._connect_project_signals()

        # Keep in-memory caches (watch list, subscriptions) in sync when devices are renamed
        try:
            if hasattr(self.device_manager, 'device_renamed'):
                self.device_manager.device_renamed.connect(self._on_device_renamed)
        except Exception:
            pass

        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        # Re-enable dock panels so Device Explorer, Signals, Watch List, and Event Log appear
        self._create_dock_panels()
        
        # Apply initial menu bar theme
        self._update_menu_bar_theme()
        
    def _create_menus(self):
        # Use classic OS title bar and standard menu bar
        from PySide6.QtWidgets import QMenuBar
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)
        
        # Provide a clean central widget for docking
        from PySide6.QtWidgets import QSizePolicy
        central_widget = QWidget()
        central_widget.setObjectName("CentralWorkspace")
        central_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(central_widget)

        # Central placeholder for an empty workspace (icon + short hint).
        # Keep this as a well-behaved child (prevents stray top-level floating widgets).
        from PySide6.QtWidgets import QVBoxLayout, QLabel
        placeholder_layout = QVBoxLayout(central_widget)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        self._central_placeholder = QLabel("\n\nNo project open — click Open or New", central_widget)
        self._central_placeholder.setObjectName('CentralPlaceholder')
        self._central_placeholder.setAlignment(Qt.AlignCenter)
        self._central_placeholder.setProperty('class', 'note')
        self._central_placeholder.setMinimumSize(120, 120)
        # Use theme icon when available but keep text visible for accessibility
        self._central_placeholder.setTextFormat(Qt.RichText)
        self._central_placeholder.setText('<div style="font-size:14pt; color:var(--text-muted)">📄</div><div style="margin-top:8px;">No project open — click <b>Open</b> or <b>New</b></div>')
        placeholder_layout.addWidget(self._central_placeholder)
        self._central_placeholder.hide()  # shown only when workspace truly empty
        
        # Standard menu bar
        menu_bar = self.menu_bar

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
        
        # Device Menu
        device_menu = menu_bar.addMenu("&Device")
        
        # Add Device Action
        add_device_action = QAction("&Add Device...", self)
        add_device_action.setStatusTip("Add a device definition (Offline/Client/Server)")
        add_device_action.triggered.connect(self._show_connection_dialog)
        device_menu.addAction(add_device_action)
        
        device_menu.addSeparator()
        
        # Modbus Slave Server
        slave_server_action = QAction("&Modbus Slave Server...", self)
        slave_server_action.setStatusTip("Start Modbus slave/server for simulation")
        slave_server_action.triggered.connect(self._show_modbus_slave)
        device_menu.addAction(slave_server_action)
        
        # IEC 61850 Simulator
        iec_simulator_action = QAction("&IEC 61850 Simulator...", self)
        iec_simulator_action.setStatusTip("Simulate IEDs from an SCD file")
        iec_simulator_action.triggered.connect(self._show_iec61850_simulator_dialog)
        device_menu.addAction(iec_simulator_action)
        
        device_menu.addSeparator()
        
        # IED Project Manager
        ied_project_action = QAction("📦 &IED Project Manager...", self)
        ied_project_action.setStatusTip("Load SCD files and create IED servers with PLC programs")
        ied_project_action.triggered.connect(self._show_ied_project_dialog)
        device_menu.addAction(ied_project_action)
        
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
        
        script_ide_action = QAction("Script &IDE (Debug)...", self)
        script_ide_action.setShortcut("Ctrl+Shift+D")
        script_ide_action.setStatusTip("Open the Script IDE with debugger")
        script_ide_action.triggered.connect(self._open_script_ide)
        self.view_menu.addAction(script_ide_action)
        
        plc_ide_action = QAction("&PLC IDE (IEC 61131-3)", self)
        plc_ide_action.setShortcut("Ctrl+Shift+P")
        plc_ide_action.setStatusTip("Open PLC IDE for IEC 61131-3 program development")
        plc_ide_action.triggered.connect(self._open_plc_ide_dialog)
        self.view_menu.addAction(plc_ide_action)
        
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
        
        # Help Index - Master documentation index
        help_index_action = QAction("📚 Help &Index...", self)
        help_index_action.setShortcut("F1")
        help_index_action.setStatusTip("Complete documentation index with quick access to all guides")
        help_index_action.triggered.connect(self._open_help_index)
        help_menu.addAction(help_index_action)
        
        help_menu.addSeparator()
        
        # AI Assistant
        ai_assistant_action = QAction("🤖 &AI Assistant...", self)
        ai_assistant_action.setShortcut("Ctrl+Shift+A")
        ai_assistant_action.setStatusTip("Ask AI for protocol analysis and troubleshooting")
        ai_assistant_action.triggered.connect(self._show_ai_assistant)
        help_menu.addAction(ai_assistant_action)
        
        help_menu.addSeparator()

        # Main Documentation
        open_docs_action = QAction("&Documentation (README)...", self)
        open_docs_action.setShortcut("Shift+F1")
        open_docs_action.setStatusTip("Open project documentation (README.md)")
        open_docs_action.triggered.connect(self._open_help_file)
        help_menu.addAction(open_docs_action)
        
        help_menu.addSeparator()
        
        # Scripting Guides
        scripting_guide_action = QAction("&Scripting Guide...", self)
        scripting_guide_action.setStatusTip("Open the Scripting Guide (Python automation)")
        scripting_guide_action.triggered.connect(self._open_scripting_guide)
        help_menu.addAction(scripting_guide_action)
        
        script_ide_guide_action = QAction("Script &IDE Guide...", self)
        script_ide_guide_action.setStatusTip("Open the Script IDE Advanced Guide")
        script_ide_guide_action.triggered.connect(self._open_script_ide_guide)
        help_menu.addAction(script_ide_guide_action)
        
        help_menu.addSeparator()
        
        # PLC IDE Documentation
        plc_quickstart_action = QAction("&PLC IDE Quick Start...", self)
        plc_quickstart_action.setStatusTip("Open PLC IDE Quick Start Guide (IEC 61131-3)")
        plc_quickstart_action.setShortcut("Ctrl+F1")
        plc_quickstart_action.triggered.connect(self._open_plc_quickstart)
        help_menu.addAction(plc_quickstart_action)
        
        plc_architecture_action = QAction("PLC IDE &Architecture...", self)
        plc_architecture_action.setStatusTip("Open PLC IDE Architecture Documentation")
        plc_architecture_action.triggered.connect(self._open_plc_architecture)
        help_menu.addAction(plc_architecture_action)
        
        plc_phase2_action = QAction("PLC IDE Phase &2 Features...", self)
        plc_phase2_action.setStatusTip("Open PLC IDE Phase 2 Implementation Summary")
        plc_phase2_action.triggered.connect(self._open_plc_phase2)
        help_menu.addAction(plc_phase2_action)
        
        plc_reference_action = QAction("PLC IDE Quick &Reference Card...", self)
        plc_reference_action.setStatusTip("Open PLC IDE Quick Reference Card (shortcuts & syntax)")
        plc_reference_action.setShortcut("F2")
        plc_reference_action.triggered.connect(self._open_plc_reference)
        help_menu.addAction(plc_reference_action)
        
        help_menu.addSeparator()
        
        # Protocol Guides
        modbus_guide_action = QAction("&Modbus Usage Guide...", self)
        modbus_guide_action.setStatusTip("Open Modbus Protocol Usage Guide")
        modbus_guide_action.triggered.connect(self._open_modbus_guide)
        help_menu.addAction(modbus_guide_action)
        
        modbus_slave_guide_action = QAction("Modbus S&lave Guide...", self)
        modbus_slave_guide_action.setStatusTip("Open Modbus Slave Server Guide")
        modbus_slave_guide_action.triggered.connect(self._open_modbus_slave_guide)
        help_menu.addAction(modbus_slave_guide_action)
        
    def _open_help_index(self):
        """Open the Help Index - comprehensive documentation master index."""
        self._open_doc_file("docs/HELP_INDEX.md", "Help Index")

    def _open_scripting_guide(self):
        """Open the local scripting user guide (docs/script_user_guide.md) in the user's default viewer."""
        try:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            doc_path = os.path.join(base, 'docs', 'script_user_guide.md')
            if not os.path.exists(doc_path):
                QMessageBox.information(self, 'Scripting Guide not found', f'Cannot find: {doc_path}')
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(doc_path))
            if self.event_logger:
                self.event_logger.info("Help", "Opened Scripting Guide")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Scripting Guide: {e}")
    
    def _open_script_ide_guide(self):
        """Open the Script IDE Guide."""
        self._open_doc_file('docs/SCRIPT_IDE_GUIDE.md', 'Script IDE Guide')
    
    def _open_plc_quickstart(self):
        """Open the PLC IDE Quick Start Guide."""
        self._open_doc_file('docs/PLC_IDE_QUICKSTART.md', 'PLC IDE Quick Start')
    
    def _open_plc_architecture(self):
        """Open the PLC IDE Architecture documentation."""
        self._open_doc_file('docs/PLC_IDE_ARCHITECTURE.md', 'PLC IDE Architecture')
    
    def _open_plc_phase2(self):
        """Open the PLC IDE Phase 2 Features summary."""
        self._open_doc_file('docs/PLC_IDE_PHASE2_SUMMARY.md', 'PLC IDE Phase 2 Features')
    
    def _open_plc_reference(self):
        """Open the PLC IDE Quick Reference Card."""
        self._open_doc_file('docs/PLC_IDE_QUICK_REFERENCE.md', 'PLC IDE Quick Reference')
    
    def _open_modbus_guide(self):
        """Open the Modbus Usage Guide."""
        self._open_doc_file('docs/modbus_usage_guide.md', 'Modbus Usage Guide')
    
    def _open_modbus_slave_guide(self):
        """Open the Modbus Slave Guide."""
        self._open_doc_file('docs/modbus_slave_guide.md', 'Modbus Slave Guide')
    
    def _open_doc_file(self, relative_path: str, doc_name: str):
        """Generic helper to open a documentation file."""
        try:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            doc_path = os.path.join(base, relative_path)
            if not os.path.exists(doc_path):
                QMessageBox.information(self, f'{doc_name} not found', 
                                       f'Cannot find: {doc_path}\n\nThe documentation may not have been installed.')
                return
            
            url = QUrl.fromLocalFile(doc_path)
            opened = QDesktopServices.openUrl(url)
            
            # Fallback to subprocess if desktop service fails
            if not opened:
                try:
                    import subprocess
                    opener = 'xdg-open' if subprocess.run(['which', 'xdg-open'], 
                                                         capture_output=True).returncode == 0 else 'open'
                    subprocess.Popen([opener, doc_path])
                    opened = True
                except Exception:
                    opened = False
            
            if opened and self.event_logger:
                self.event_logger.info("Help", f"Opened {doc_name}")
            elif not opened:
                QMessageBox.warning(self, "Error", f"Failed to open {doc_name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open {doc_name}: {e}")

    def _on_device_renamed(self, old_name: str, new_name: str):
        """Handler for device rename events to update in-memory caches."""
        try:
            # Update watch list entries
            try:
                if hasattr(self, 'watch_list_manager') and self.watch_list_manager:
                    self.watch_list_manager.rename_device(old_name, new_name)
            except Exception:
                pass

            # Update subscription manager (core)
            try:
                sub_mgr = getattr(self.device_manager, 'subscription_manager', None)
                if sub_mgr:
                    sub_mgr.rename_device(old_name, new_name)
            except Exception:
                pass

            # Let project manager update any persisted references if needed
            try:
                if hasattr(self, 'project_manager') and self.project_manager:
                    # ProjectManager currently doesn't expose a rename API; no-op for now
                    pass
            except Exception:
                pass

            # Inform user via event log
            try:
                if self.event_logger:
                    self.event_logger.info('DeviceManager', f"Device renamed: {old_name} -> {new_name}")
            except Exception:
                pass
        except Exception:
            pass
        
    def _create_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setObjectName("MainToolbar")
        # Keep toolbar below the menu/title bar and visually compact
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(self.toolbar)

        # Populate toolbar with primary actions (icons from theme where possible)
        from PySide6.QtGui import QIcon
        def _icon(name, fallback_text=None):
            ic = QIcon.fromTheme(name)
            if ic.isNull() and fallback_text:
                # Create a simple text-based icon substitute using QIcon.fromTheme fallback
                return QIcon()
            return ic

        new_action = QAction(_icon('document-new', 'New'), 'New', self)
        new_action.setStatusTip('Create new project')
        new_action.triggered.connect(self._on_new_project)
        self.toolbar.addAction(new_action)

        open_action = QAction(_icon('document-open', 'Open'), 'Open', self)
        open_action.setStatusTip('Open project')
        open_action.triggered.connect(self._on_open_project)
        self.toolbar.addAction(open_action)

        save_action = QAction(_icon('document-save', 'Save'), 'Save', self)
        save_action.setStatusTip('Save project')
        save_action.triggered.connect(self._on_save_project)
        self.toolbar.addAction(save_action)

        self.toolbar.addSeparator()

        connect_action = QAction(_icon('list-add', 'Add'), 'Add Device', self)
        connect_action.setStatusTip('Add a device definition (Offline/Client/Server)')
        connect_action.triggered.connect(lambda: self._show_connection_dialog())
        self.toolbar.addAction(connect_action)

        run_action = QAction(_icon('media-playback-start', 'Run'), 'Run', self)
        run_action.setStatusTip('Start runtime / simulation')
        run_action.triggered.connect(lambda: getattr(self, '_start_runtime', lambda: None)())
        self.toolbar.addAction(run_action)

        stop_action = QAction(_icon('media-playback-stop', 'Stop'), 'Stop', self)
        stop_action.setStatusTip('Stop runtime / simulation')
        stop_action.triggered.connect(lambda: getattr(self, '_stop_runtime', lambda: None)())
        self.toolbar.addAction(stop_action)

        self.toolbar.addSeparator()

        reset_action = QAction(_icon('view-refresh', 'Reset'), 'Reset Layout', self)
        reset_action.setStatusTip('Reset layout to default')
        reset_action.triggered.connect(self._on_reset_layout)
        self.toolbar.addAction(reset_action)

        settings_action = QAction(_icon('preferences-system', 'Settings'), 'Settings', self)
        settings_action.setStatusTip('Open settings')
        settings_action.triggered.connect(self._show_settings_dialog)
        self.toolbar.addAction(settings_action)

        # Small theme toggle on the far right
        self.toolbar.addSeparator()
        toggle_theme_action = QAction(_icon('color-management', 'Theme'), 'Toggle Theme', self)
        toggle_theme_action.setStatusTip('Toggle Epic Dark/Bright theme')
        toggle_theme_action.triggered.connect(self._toggle_theme)
        self.toolbar.addAction(toggle_theme_action)

        # Ensure toolbar is visible and set reasonable icon size (may be overridden by settings)
        try:
            from PySide6.QtCore import QSize
            icon_size = 24
            self.toolbar.setIconSize(QSize(icon_size, icon_size))
            self.toolbar.show()
        except Exception:
            pass

        # Log toolbar population for diagnostics
        try:
            import logging as _logging
            _logging.getLogger(__name__).info('Main toolbar populated with %d actions', len(self.toolbar.actions()))
        except Exception:
            pass
        
    def _create_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Theme and font are applied from saved settings (or defaults) by MainWindow
        try:
            from PySide6.QtWidgets import QSizeGrip, QProgressBar
            grip = QSizeGrip(self)
            self.status_bar.addPermanentWidget(grip)

            # Small status-bar progress for background SCD parsing
            self._scd_status_progress = QProgressBar(self)
            self._scd_status_progress.setMaximumHeight(14)
            self._scd_status_progress.setFixedWidth(140)
            self._scd_status_progress.setRange(0, 0)  # indeterminate
            self._scd_status_progress.setVisible(False)
            self.status_bar.addPermanentWidget(self._scd_status_progress)

            # Connect to device manager notifications
            try:
                self.device_manager.scd_parse_scheduled.connect(
                    lambda dev, path: (self._scd_status_progress.setVisible(True), self.status_bar.showMessage(f"Parsing SCD for {dev}...") )
                )
                self.device_manager.scd_parse_completed.connect(
                    lambda dev: (self._scd_status_progress.setVisible(False), self.status_bar.showMessage(f"SCD parsed: {dev}", 3000))
                )
            except Exception:
                pass
        except Exception:
            pass
        
    def _create_dock_panels(self):
        from PySide6.QtWidgets import QSizePolicy
        
        self.dock_left = QDockWidget("Device Explorer", self)
        self.dock_left.setObjectName("DockDeviceExplorer")
        self.dock_left.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_left.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        
        # Set size constraints for dock widget
        self.dock_left.setMinimumWidth(200)
        self.dock_left.setMaximumWidth(600)
        
        self.device_tree = DeviceTreeWidget(self.device_manager, self.watch_list_manager)
        # self.device_tree = QLabel("Device Tree Disabled")
        self.device_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_left.setWidget(self.device_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        
        # Connect Selection
        self.device_tree.selection_changed.connect(self._on_tree_selection_changed)
        
        # Connect Device Updates to Event Log Filter
        self.device_manager.device_added.connect(lambda d: self._update_event_log_devices())
        self.device_manager.device_removed.connect(lambda n: self._update_event_log_devices())
        self.device_manager.device_updated.connect(self._on_device_updated)

        # Data Visualization panel - moved to bottom area
        self.dock_right = QDockWidget("Data Visualization", self)
        self.dock_right.setObjectName("DockDataVisualization")
        self.dock_right.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_right.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        
        self.signals_view = SignalsViewWidget(self.device_manager, self.watch_list_manager)
        self.signals_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_right.setWidget(self.signals_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_right)
        
        # Connect signals_view to device_tree for "Add to Live Data" functionality
        self.device_tree.signals_view = self.signals_view
        self.device_tree.add_to_live_data_requested.connect(self.signals_view.add_signal)
        
        # Watch List panel  
        self.dock_bottom = QDockWidget("Watch List", self)
        self.dock_bottom.setObjectName("DockWatchList")
        self.dock_bottom.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_bottom.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        
        self.watch_list_widget = WatchListWidget(self.watch_list_manager, self.device_manager)
        self.watch_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_bottom.setWidget(self.watch_list_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        
        # Event Log panel
        self.dock_events = QDockWidget("Event Log", self)
        self.dock_events.setObjectName("DockEventLog")
        self.dock_events.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dock_events.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        
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
        self.dock_modbus_slave.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        
        self.modbus_slave_widget = ModbusSlaveWidget(
            event_logger=self.event_logger
        )
        # self.modbus_slave_widget = QWidget()
        self.modbus_slave_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dock_modbus_slave.setWidget(self.modbus_slave_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_modbus_slave)
        
        # Layout arrangement - Device Explorer on left, bottom panels tabbed
        # Remove and re-add for clean layout
        self.removeDockWidget(self.dock_bottom)
        self.removeDockWidget(self.dock_events)
        self.removeDockWidget(self.dock_modbus_slave)
        
        # Re-add to bottom area
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_right)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_modbus_slave)
        
        # Tab them together
        self.tabifyDockWidget(self.dock_right, self.dock_bottom)
        # Keep Event Log on the right (not tabbed with bottom panels)
        self.tabifyDockWidget(self.dock_right, self.dock_modbus_slave)
        
        # Show Data Visualization by default, hide Modbus Slave
        self.dock_right.raise_()
        self.dock_modbus_slave.setVisible(False)
        
        # Connect visibility signals to restore proper placement
        self.dock_left.visibilityChanged.connect(self._on_dock_visibility_changed)
        self.dock_right.visibilityChanged.connect(self._on_dock_visibility_changed)
        self.dock_bottom.visibilityChanged.connect(self._on_dock_visibility_changed)
        self.dock_events.visibilityChanged.connect(self._on_dock_visibility_changed)
        
        # Apply initial layout with proper sizing
        # Attempt to load user-saved default layout first
        if not self._load_default_layout():
             # If no saved layout, use proportional starting defaults
             QTimer.singleShot(50, self._apply_initial_layout)
        else:
             # Ensure floating title is correctly positioned even after restore
             QTimer.singleShot(50, lambda: self.resizeEvent(None))
        
        # Ensure View menu exists (some menu construction paths may skip creation)
        try:
            if not hasattr(self, 'view_menu') or self.view_menu is None:
                try:
                    self.view_menu = self.menuBar().addMenu("&View")
                except Exception:
                    from PySide6.QtWidgets import QMenu
                    self.view_menu = QMenu("&View", self)
                    try:
                        self.menuBar().addMenu(self.view_menu)
                    except Exception:
                        pass
        except Exception:
            # Last-resort: create an attribute so calls below won't fail
            self.view_menu = None

        # Add toggle actions to View menu (if available)
        if getattr(self, 'view_menu', None):
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
        left_panel_width = int(window_width * 0.20)    # 20% for device explorer
        bottom_panel_height = int(window_height * 0.35) # 35% for bottom panels
        
        # Apply minimum constraints
        left_panel_width = max(280, min(left_panel_width, 400))   # 280-400px
        bottom_panel_height = max(250, min(bottom_panel_height, 500)) # 250-500px
        right_panel_width = max(260, min(int(window_width * 0.22), 420))
        
        # Set dock sizes
        self.resizeDocks([self.dock_left], [left_panel_width], Qt.Horizontal)
        self.resizeDocks([self.dock_right], [bottom_panel_height], Qt.Vertical)
        if hasattr(self, 'dock_events'):
            self.resizeDocks([self.dock_events], [right_panel_width], Qt.Horizontal)
    
    def _on_dock_visibility_changed(self, visible):
        """Handle dock widget visibility changes to restore proper placement."""
        if not visible:
            return
        
        dock = self.sender()
        if not dock:
            return
        
        # Store current sizes before repositioning
        window_width = self.width()
        window_height = self.height()
        
        # When a dock becomes visible, ensure it's in the correct area
        if dock == self.dock_left:
            # Ensure Device Explorer is on the left
            current_area = self.dockWidgetArea(dock)
            if current_area != Qt.LeftDockWidgetArea:
                self.removeDockWidget(dock)
                self.addDockWidget(Qt.LeftDockWidgetArea, dock)
            
            # Restore size after short delay to ensure layout is ready
            left_width = max(280, min(int(window_width * 0.20), 400))
            QTimer.singleShot(50, lambda: self.resizeDocks(
                [self.dock_left], 
                [left_width], 
                Qt.Horizontal
            ))
        
        elif dock in (self.dock_right, self.dock_bottom):
            # Ensure bottom panels are in bottom area and tabbed
            current_area = self.dockWidgetArea(dock)
            if current_area != Qt.BottomDockWidgetArea:
                self.removeDockWidget(dock)
                self.addDockWidget(Qt.BottomDockWidgetArea, dock)
                
                # Re-establish tabbing
                if self.dock_right.isVisible() and dock != self.dock_right:
                    self.tabifyDockWidget(self.dock_right, dock)
                elif dock == self.dock_right:
                    if self.dock_bottom.isVisible():
                        self.tabifyDockWidget(self.dock_right, self.dock_bottom)
                    if self.dock_events.isVisible():
                        self.tabifyDockWidget(self.dock_right, self.dock_events)
                
                # Raise the newly shown panel
                dock.raise_()
            
            # Restore size after short delay
            bottom_height = max(250, min(int(window_height * 0.35), 500))
            QTimer.singleShot(50, lambda: self.resizeDocks(
                [self.dock_right], 
                [bottom_height], 
                Qt.Vertical
            ))

        elif dock == self.dock_events:
            # Ensure Event Log is on the right
            current_area = self.dockWidgetArea(dock)
            if current_area != Qt.RightDockWidgetArea:
                self.removeDockWidget(dock)
                self.addDockWidget(Qt.RightDockWidgetArea, dock)
                dock.raise_()
            right_width = max(260, min(int(window_width * 0.22), 420))
            QTimer.singleShot(50, lambda: self.resizeDocks(
                [self.dock_events],
                [right_width],
                Qt.Horizontal
            ))

    def resizeEvent(self, event):
        # Keep floating title bar stretched across the top
        try:
            if hasattr(self, '_floating_title') and self._floating_title:
                self._floating_title.resize(self.width(), self._floating_title.height())
                self._floating_title.raise_()
        except Exception:
            pass
        return super().resizeEvent(event)

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
        """Restore a reliable, centered default layout and clear saved state.

        This forces a known-good geometry, undocks any floating panels, re-docks
        widgets into their canonical areas and reapplies conservative sizes so
        the UI is predictable across screen sizes.
        """
        from PySide6.QtGui import QGuiApplication

        # Clear saved layout so restoreState won't reapply a broken layout
        settings = QSettings("ScadaScout", "Layout")
        settings.remove("geometry")
        settings.remove("windowState")

        # Ensure main window is in normal state and visible
        try:
            self.showNormal()
            self.raise_()
        except Exception:
            pass

        # Determine a sensible default size (centered, responsive to screen)
        screen = QGuiApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            default_w = max(1000, min(1400, int(sg.width() * 0.78)))
            default_h = max(700, min(900, int(sg.height() * 0.72)))
            default_x = sg.x() + (sg.width() - default_w) // 2
            default_y = sg.y() + (sg.height() - default_h) // 2
            self.setGeometry(default_x, default_y, default_w, default_h)
        else:
            # fallback
            self.resize(1200, 800)

        # Make sure title/menu bar remains visible
        try:
            if hasattr(self, 'vscode_title_bar'):
                self.vscode_title_bar.show()
        except Exception:
            pass

        # Undock any floating docks and re-dock them in canonical areas
        docks = [getattr(self, name) for name in ('dock_left', 'dock_right', 'dock_bottom', 'dock_events') if hasattr(self, name)]
        if hasattr(self, 'dock_modbus_slave'):
            docks.append(self.dock_modbus_slave)

        for d in docks:
            try:
                if d.isFloating():
                    d.setFloating(False)
                # Ensure docks are visible (but optional ones can stay hidden)
                d.setVisible(True)
                d.show()
            except Exception:
                pass

        # Remove and re-add to ensure correct areas (prevents weird tabbing/overlap)
        for d in docks:
            try:
                self.removeDockWidget(d)
            except Exception:
                pass

        # Re-add in canonical arrangement
        if hasattr(self, 'dock_left'):
            self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        if hasattr(self, 'dock_right'):
            self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_right)
        if hasattr(self, 'dock_bottom'):
            self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        if hasattr(self, 'dock_events'):
            self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        if hasattr(self, 'dock_modbus_slave'):
            # keep Modbus slave hidden by default
            self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_modbus_slave)
            self.dock_modbus_slave.setVisible(False)

        # Tab bottom panels together and raise primary panel
        try:
            if hasattr(self, 'dock_right') and hasattr(self, 'dock_bottom'):
                self.tabifyDockWidget(self.dock_right, self.dock_bottom)
            if hasattr(self, 'dock_modbus_slave'):
                self.tabifyDockWidget(self.dock_right, self.dock_modbus_slave)
            if hasattr(self, 'dock_right'):
                self.dock_right.raise_()
        except Exception:
            pass

        # Apply conservative size proportions after layout stabilizes
        def _apply_sizes():
            try:
                w = self.width()
                h = self.height()
                if hasattr(self, 'dock_left'):
                    left_w = max(220, min(420, int(w * 0.22)))
                    self.resizeDocks([self.dock_left], [left_w], Qt.Horizontal)
                if hasattr(self, 'dock_right'):
                    bottom_h = max(220, min(520, int(h * 0.36)))
                    self.resizeDocks([self.dock_right], [bottom_h], Qt.Vertical)
                if hasattr(self, 'dock_events'):
                    right_w = max(260, min(420, int(w * 0.22)))
                    self.resizeDocks([self.dock_events], [right_w], Qt.Horizontal)
            except Exception:
                pass

        QTimer.singleShot(120, _apply_sizes)

        # Persist a clean default layout so future restores are sane
        QTimer.singleShot(300, lambda: settings.setValue('windowState', self.saveState()))
        QTimer.singleShot(300, lambda: settings.setValue('geometry', self.saveGeometry()))

        # Make menu/titlebar top-most in stacking order and ensure visible
        try:
            mw = self.menuWidget()
            if mw:
                mw.show()
                mw.raise_()
        except Exception:
            pass

        # Ensure core panels are visible after reset
        try:
            if hasattr(self, 'dock_left'):
                self.dock_left.show()
                self.dock_left.raise_()
            if hasattr(self, 'dock_events'):
                self.dock_events.show()
            if hasattr(self, 'dock_right'):
                self.dock_right.show()
            if hasattr(self, 'dock_bottom'):
                self.dock_bottom.show()
        except Exception:
            pass

        # Hide central placeholder once panels are restored
        try:
            if hasattr(self, '_central_placeholder'):
                self._central_placeholder.hide()
        except Exception:
            pass

        # Defensive: hide any stray top-level, small, unparented widgets that
        # accidentally appear inside the main window (common source of the
        # 'floating icon in center' bug). Exclude known menus/titlebar.
        try:
            from PySide6.QtWidgets import QApplication, QMenu
            _hidden = []
            for tw in QApplication.topLevelWidgets():
                # skip the main window, menus, and our title bar
                if tw is self or isinstance(tw, QMenu) or getattr(tw, 'objectName', lambda: '')().startswith('VSCodeTitleBar'):
                    continue
                geom = tw.geometry()
                if 24 <= geom.width() <= 220 and 24 <= geom.height() <= 220:
                    # only hide widgets that lie (mostly) inside the main window
                    if self.geometry().intersects(geom):
                        try:
                            tw.hide()
                            _hidden.append(f"{tw.__class__.__name__}:{geom.getRect()}")
                        except Exception:
                            pass
            if _hidden:
                import logging as _logging
                _logging.getLogger(__name__).info('Layout reset hid stray widgets: %s', ','.join(_hidden))
        except Exception:
            pass

        # If device tree exists, restore a sensible selection (first device)
        device_selected = False
        try:
            if hasattr(self, 'device_tree') and getattr(self.device_tree, 'model', None) is not None:
                root = self.device_tree.model.invisibleRootItem()
                # find first non-folder child (device) if present
                first_index = None
                for r in range(root.rowCount()):
                    item = root.child(r, 0)
                    if item and item.text():
                        first_index = item.index()
                        break
                if first_index is not None:
                    sel = self.device_tree.tree_view.selectionModel()
                    from PySide6.QtCore import QItemSelectionModel
                    sel.setCurrentIndex(first_index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                    device_selected = True
        except Exception:
            device_selected = False

        # Emit a log summary so the user can quickly verify the reset behavior
        try:
            import logging as _logging
            _log = _logging.getLogger(__name__)
            _log.info('Layout reset summary: dock_left.floating=%s, dock_left.area=%s, menu_visible=%s, device_selected=%s',
                      getattr(self, 'dock_left').isFloating() if hasattr(self, 'dock_left') else None,
                      self.dockWidgetArea(self.dock_left) if hasattr(self, 'dock_left') else None,
                      bool(self.menuWidget()),
                      device_selected)
        except Exception:
            pass

        QApplication.instance().processEvents()
        self.status_bar.showMessage("Layout reset to default (centered).", 3000)

    def _show_settings_dialog(self):
        """Opens the Settings Dialog for appearance customization."""
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._apply_settings)
        dialog.exec()
    
    def _show_ai_assistant(self):
        """Opens the AI Assistant dialog for protocol analysis."""
        try:
            # Get watch list manager if available
            watch_list_mgr = getattr(self, 'watch_list_manager', None)
            
            # Get protocol gateway if available
            protocol_gateway = getattr(self.device_manager, 'protocol_gateway', None)
            
            dialog = AIAssistantDialog(
                device_manager=self.device_manager,
                watch_list_manager=watch_list_mgr,
                protocol_gateway=protocol_gateway,
                event_logger=self.event_logger,
                parent=self
            )
            
            # AI provider is now configured via Settings (⚙️ Settings → AI Assistant tab)
            # Users can configure OpenAI, Claude, Azure, Ollama, or custom providers
            
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to open AI Assistant:\n{e}"
            )

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
    
    def _open_script_ide(self):
        """Open the Script IDE with full debugger support."""
        from src.ui.dialogs.script_ide import ScriptIDEWindow
        from shiboken6 import isValid
        
        # Check if window exists and is still valid (not deleted by Qt)
        try:
            existing = getattr(self, '_script_ide_window', None)
            if existing is not None and isValid(existing):
                # Window exists and is valid - just show it
                existing.show()
                existing.raise_()
                existing.activateWindow()
                return
        except (RuntimeError, AttributeError):
            # Object was deleted or reference is stale
            pass
        
        # Create new window
        try:
            self._script_ide_window = ScriptIDEWindow(
                self.device_manager, 
                self.event_logger, 
                self
            )
            # Don't use WA_DeleteOnClose - keep the window around
            self._script_ide_window.show()
            self._script_ide_window.raise_()
            self._script_ide_window.activateWindow()
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to open Script IDE:\n{e}"
            )
    
    def _open_plc_ide_dialog(self):
        """Prompt user to select a device for PLC IDE."""
        from PySide6.QtWidgets import QInputDialog
        
        devices = self.device_manager.get_all_devices()
        if not devices:
            QMessageBox.warning(self, "No Devices", "Add a device first to open PLC IDE.")
            return
        
        device_names = [d.config.name for d in devices]
        device_name, ok = QInputDialog.getItem(
            self,
            "Select Device for PLC IDE",
            "Choose a device to develop PLC programs for:",
            device_names,
            0,
            False
        )
        
        if ok and device_name:
            self._open_plc_ide_for_device(device_name)
    
    def _open_plc_ide_for_device(self, device_name: str):
        """Open PLC IDE for specific device."""
        try:
            from src.ui.dialogs.plc_ide_window import PLCIDEWindow
            from shiboken6 import isValid
            
            # Check if IDE is already open for this device
            ide_attr = f'_plc_ide_{device_name}'
            existing = getattr(self, ide_attr, None)
            
            if existing is not None and isValid(existing):
                existing.show()
                existing.raise_()
                existing.activateWindow()
                return
            
            # Create new window
            ide_window = PLCIDEWindow(self.device_manager, device_name, self)
            setattr(self, ide_attr, ide_window)
            ide_window.show()
            ide_window.raise_()
            ide_window.activateWindow()
        except Exception as e:
            logger.exception(f"Failed to open PLC IDE for device {device_name}")
            QMessageBox.critical(self, "Error", f"Failed to open PLC IDE:\n{e}")

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
        # Theme is now managed by ThemeManager - stylesheet is applied automatically
        # No need to manually apply base_style here as theme_manager handles it
        
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

        # Theme is now managed by ThemeManager, so no need to apply base_style manually
        # Just apply the overrides on top of the current theme
        current_stylesheet = QApplication.instance().styleSheet()
        QApplication.instance().setStyleSheet(current_stylesheet + "\n" + overrides)

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

        # OPC Mirror runtime toggle (UI-driven). Start/stop mirror here so the
        # UI can enable exposure of the DeviceManager without requiring the
        # controller to change. This is opt-in and must never raise for users
        # who do not have optional OPC dependencies installed.
        try:
            opc_enabled = settings.value("opc_mirror_enabled", False, type=bool)
            opc_endpoint = settings.value("opc_mirror_endpoint", "opc.tcp://0.0.0.0:4843")
            if opc_enabled:
                if getattr(self, '_opc_mirror', None) is None:
                    try:
                        from src.core.opc_mirror import OPCMirror
                        self._opc_mirror = OPCMirror(self.device_manager)
                        self._opc_mirror.start(opc_endpoint, server_name="SCADAScout Mirror (UI)")
                        if hasattr(self, 'event_log_widget'):
                            self.event_log_widget.log_event('OPC', f'OPC mirror started on {opc_endpoint}')
                    except Exception:
                        import logging as _logging
                        _logging.getLogger(__name__).exception('Failed to start OPC mirror (opt-in)')
            else:
                if getattr(self, '_opc_mirror', None) is not None:
                    try:
                        self._opc_mirror.stop()
                    except Exception:
                        pass
                    self._opc_mirror = None
        except Exception:
            # must never break UI when optional features fail
            pass

        # Force repaint
        self.repaint()

    def _show_connection_dialog(self):
        """Opens the unified Add Device dialog."""
        from src.ui.widgets.add_device_workflow import add_device_via_dialog

        add_device_via_dialog(
            self,
            self.device_manager,
        )
    
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

    def _open_help_file(self):
        """Open the project's README or primary docs with the system default application.

        Use QDesktopServices.openUrl for portability; fall back to a subprocess-based opener
        only if the desktop service fails.
        """
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            candidates = [
                os.path.join(project_root, 'README.md'),
                os.path.join(project_root, 'docs', 'complete_project_structure.md'),
                os.path.join(project_root, 'docs', 'readme_crossplatform.md'),
            ]
            path_to_open = None
            for p in candidates:
                if p and os.path.exists(p):
                    path_to_open = p
                    break

            if not path_to_open:
                QMessageBox.information(self, "Documentation not found",
                    "Documentation files were not found in the project root.\nLook in the 'docs/' directory or open the repository README manually.")
                return

            url = QUrl.fromLocalFile(path_to_open)
            opened = QDesktopServices.openUrl(url)

            # Fallback to subprocess if desktop service fails (rare on Linux desktops)
            if not opened:
                try:
                    import subprocess
                    opener = 'xdg-open' if subprocess.run(['which', 'xdg-open'], capture_output=True).returncode == 0 else 'open'
                    subprocess.Popen([opener, path_to_open])
                    opened = True
                except Exception:
                    opened = False

            if not opened:
                QMessageBox.warning(self, "Open Documentation", f"Failed to open documentation: {path_to_open}")
                return

            try:
                if self.event_logger:
                    self.event_logger.info("Help", f"Opened documentation: {os.path.basename(path_to_open)}")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Open Documentation", f"Failed to open documentation: {e}")

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
    
    def _show_ied_project_dialog(self):
        """Open IED Project Manager dialog for SCD-based device instantiation"""
        from src.ui.dialogs.ied_project_dialog import IEDProjectDialog
        from src.core.ied_project_orchestrator import IEDProjectOrchestrator
        from PySide6.QtWidgets import QDialog
        
        # Create orchestrator if not exists
        if not hasattr(self, '_ied_orchestrator'):
            self._ied_orchestrator = IEDProjectOrchestrator(self.device_manager)
        
        dialog = IEDProjectDialog(self._ied_orchestrator, self)
        dialog.exec()


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
    
    def _set_theme(self, theme_name: str):
        """Set application theme."""
        from src.ui.theme_presets import ThemeType
        
        if theme_name == "dark":
            self.theme_manager.set_theme(ThemeType.DARK)
        elif theme_name == "bright":
            self.theme_manager.set_theme(ThemeType.BRIGHT)
        
        if self.event_logger:
            self.event_logger.info("Theme", f"Theme changed to {theme_name.title()}")
    
    def _toggle_theme(self):
        """Toggle between dark and bright themes."""
        self.theme_manager.toggle_theme()
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme changed event."""
        # Update VSCode title bar theme
        if hasattr(self, 'vscode_title_bar'):
            self.vscode_title_bar.update_theme()
        else:
            # Fallback to menu bar update for non-VSCode mode
            self._update_menu_bar_theme()
        
        # Force repaint to apply new theme immediately
        QApplication.instance().processEvents()
    
    def _update_menu_bar_theme(self):
        """Update menu bar colors based on current theme."""
        try:
            from src.ui.theme_presets import ColorRole
            
            bg_color = self.theme_manager.get_color(ColorRole.TOOLBAR_BACKGROUND)
            text_color = self.theme_manager.get_color(ColorRole.TEXT_PRIMARY)
            border_color = self.theme_manager.get_color(ColorRole.BORDER)
            
            # Apply to menu bar
            self.menuBar().setStyleSheet(f"""
                QMenuBar {{
                    background-color: {bg_color};
                    color: {text_color};
                    border-bottom: 1px solid {border_color};
                }}
                QMenuBar::item {{
                    color: {text_color};
                }}
            """)
            
            # Update window title in window title bar
            self.setWindowTitle(f"Scada Scout - {self.theme_manager.get_current_theme().value.title()} Theme")
            
        except Exception:
            pass
    
    def _update_title_bar_theme(self):
        """Update title bar widget theme if available."""
        if self._title_bar:
            self._title_bar._apply_theme()
        if hasattr(self, 'vscode_title_bar'):
            self.vscode_title_bar.update_theme()
    
    def _on_minimize(self):
        """Minimize window."""
        self.showMinimized()
    
    def _on_maximize_restore(self):
        """Toggle maximize/restore window."""
        if self.isMaximized():
            self.showNormal()
            if hasattr(self, 'vscode_title_bar'):
                self.vscode_title_bar.btn_max.setText("□")
        else:
            self.showMaximized()
            if hasattr(self, 'vscode_title_bar'):
                self.vscode_title_bar.btn_max.setText("❐")

    def closeEvent(self, event):
        """Handle window close event."""
        # Auto-save layout if enabled in settings
        settings = QSettings("ScadaScout", "UI")
        if settings.value("auto_save_layout", True, type=bool):
            self._on_save_default_layout()
            
        super().closeEvent(event)
