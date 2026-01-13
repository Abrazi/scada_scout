from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMenuBar, QToolBar, QDockWidget, QFileDialog, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer, QSettings
import os
import platform

from src.ui.widgets.device_tree import DeviceTreeWidget
from src.ui.widgets.signals_view import SignalsViewWidget
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.scd_import_dialog import SCDImportDialog
from src.ui.widgets.scrollable_message_box import show_scrollable_error
from src.core.exporters import (
    export_network_config_script, 
    export_network_config_all_platforms, 
    export_device_list_csv, 
    export_goose_details_csv, 
    export_diagnostics_report
)
from src.core.watch_list_manager import WatchListManager
from src.ui.widgets.watch_list_widget import WatchListWidget
from src.ui.widgets.event_log_widget import EventLogWidget
from src.ui.widgets.modbus_slave_widget import ModbusSlaveWidget
from src.ui.widgets.connection_progress_dialog import ConnectionProgressDialog
from src.ui.widgets.import_progress_dialog import ImportProgressDialog

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
        self.resize(1280, 800)
        
        # Central Widget (Placeholder for now)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Initialize UI Components
        self._setup_ui()
        
        # Persistent Dialogs
        self.scd_dialog = None
        
    def _setup_ui(self):
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        self._create_dock_panels()
        
    def _create_menus(self):
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
        
        save_project_action = QAction("&Save Project As...", self)
        save_project_action.setShortcut("Ctrl+Shift+S")
        save_project_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(save_project_action)
        
        file_menu.addSeparator()

        # Import SCD Action
        import_scd_action = QAction("&Import SCD...", self)
        import_scd_action.setStatusTip("Import IEDs from SCD file")
        import_scd_action.triggered.connect(self._show_scd_import_dialog)
        file_menu.addAction(import_scd_action)
        
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
        
        # View Menu
        self.view_menu = menu_bar.addMenu("&View")
        
        reset_layout_action = QAction("&Reset Layout", self)
        reset_layout_action.setStatusTip("Restore default panel arrangement")
        reset_layout_action.triggered.connect(self._on_reset_layout)
        self.view_menu.addAction(reset_layout_action)
        self.view_menu.addSeparator()
        
        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        
    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
    def _create_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
    def _create_dock_panels(self):
        # Left Panel: Device Tree
        self.dock_left = QDockWidget("Device Explorer", self)
        self.dock_left.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.watch_list_manager = WatchListManager(self.device_manager)
        
        self.device_tree = DeviceTreeWidget(self.device_manager, self.watch_list_manager)
        self.dock_left.setWidget(self.device_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        
        # Connect Selection
        self.device_tree.selection_changed.connect(self._on_tree_selection_changed)
        
        # Connect Device Updates to Event Log Filter
        self.device_manager.device_added.connect(lambda d: self._update_event_log_devices())
        self.device_manager.device_removed.connect(lambda n: self._update_event_log_devices())
        self.device_manager.device_updated.connect(self._on_device_updated)

        # Right Panel: Signals & Charts
        self.dock_right = QDockWidget("Data Visualization", self)
        self.dock_right.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        
        self.signals_view = SignalsViewWidget(self.device_manager, self.watch_list_manager)
        self.dock_right.setWidget(self.signals_view)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)
        
        # Watch List panel  
        self.dock_bottom = QDockWidget("Watch List", self)
        self.dock_bottom.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        
        self.watch_list_widget = WatchListWidget(self.watch_list_manager, self.device_manager)
        self.dock_bottom.setWidget(self.watch_list_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        
        # Event Log panel
        self.dock_events = QDockWidget("Event Log", self)
        self.dock_events.setAllowedAreas(Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        
        self.event_log_widget = EventLogWidget()
        self.dock_events.setWidget(self.event_log_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        
        # Modbus Slave Server panel (hidden by default)
        self.dock_modbus_slave = QDockWidget("Modbus Slave Server", self)
        self.dock_modbus_slave.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.modbus_slave_widget = ModbusSlaveWidget(
            event_logger=self.event_logger
        )
        self.dock_modbus_slave.setWidget(self.modbus_slave_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_modbus_slave)
        
        # Layout arrangement
        self.tabifyDockWidget(self.dock_right, self.dock_events)
        self.tabifyDockWidget(self.dock_bottom, self.dock_modbus_slave)
        self.dock_right.raise_()
        self.dock_modbus_slave.setVisible(False)
        
        # Add toggle actions to View menu
        self.view_menu.addAction(self.dock_left.toggleViewAction())
        self.view_menu.addAction(self.dock_right.toggleViewAction())
        self.view_menu.addAction(self.dock_bottom.toggleViewAction())
        self.view_menu.addAction(self.dock_events.toggleViewAction())
        self.view_menu.addAction(self.dock_modbus_slave.toggleViewAction())

    def _on_reset_layout(self):
        """Restores the default docking layout."""
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
            self.scd_dialog = SCDImportDialog(self)
            
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
            
            count = 0
            errors = []
            
            for i, config in enumerate(configs):
                try:
                    progress.add_log(f"Importing {config.name} ({config.ip_address})...")
                    self.device_manager.add_device(config)
                    self.device_manager.load_offline_scd(config.name)
                    count += 1
                    progress.set_progress(i + 1)
                except Exception as e:
                    msg = f"Failed to add {config.name}: {e}"
                    progress.add_log(f"ERROR: {msg}")
                    errors.append(msg)
            
            progress.finish()
            
            if errors:
                show_scrollable_error(self, "Import Errors", "Some devices failed to import:", "\n".join(errors))
            else:
                self.status_bar.showMessage(f"Successfully imported {count} devices.", 5000)

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
            scd_path, _ = QFileDialog.getOpenFileName(self, "Select Source SCD for GOOSE Export", "", "SCD Files (*.scd *.cid *.xml)")
            if not scd_path:
                return
        
        fname, _ = QFileDialog.getSaveFileName(self, "Export GOOSE Details", "goose_details.csv", "CSV Files (*.csv)")
        if fname:
            success, msg = export_goose_details_csv(scd_path, fname)
            if success:
                self.status_bar.showMessage(f"Exported: {msg}", 3000)
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export GOOSE details:", msg)

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

    def _show_modbus_slave(self):
        """Show and activate Modbus slave server dock"""
        self.dock_modbus_slave.setVisible(True)
        self.dock_modbus_slave.raise_()
        settings = QSettings("ScadaScout", "UI")
        if not settings.value("modbus_slave_info_shown", False):
            QMessageBox.information(self, "Modbus Slave Server", "This feature allows SCADA Scout to act as a Modbus TCP slave/server.\n\nUse cases:\n• Simulate devices for testing clients\n• Create virtual test environments\n• Act as a protocol gateway\n\nClick 'Start Server' to begin listening for connections.")
            settings.setValue("modbus_slave_info_shown", True)

    # Project Management Handlers
    def _on_new_project(self):
        """Clears the workspace for a new project."""
        reply = QMessageBox.question(self, 'New Project', 
                                    "This will clear all current devices and settings. Continue?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.device_manager.clear_all_devices()
            self.statusBar().showMessage("New project started", 3000)

    def _on_open_project(self):
        """Opens a project file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.json);;All Files (*)")
        if file_path:
            # We don't need to manually clear, device_manager.load_configuration emits project_cleared
            self.device_manager.load_configuration(file_path)
            self.statusBar().showMessage(f"Loaded project: {os.path.basename(file_path)}", 3000)

    def _on_save_project_as(self):
        """Saves current state to a new project file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "Project Files (*.json);;All Files (*)")
        if file_path:
            if not file_path.endswith('.json'):
                file_path += '.json'
            self.device_manager.save_configuration(file_path)
            self.statusBar().showMessage(f"Project saved to: {os.path.basename(file_path)}", 3000)

    def _on_tree_selection_changed(self, node, device_name):
        """Updates the signals view based on selected tree node."""
        import logging
        logger = logging.getLogger("MainWindow")
        logger.debug(f"MainWindow: Selection received for {device_name}. Node type: {type(node)}")
        # Instead of replacing the live data, append the selected node's signals
        try:
            self.signals_view.add_node_to_live(node, device_name)
        except Exception:
            # Fallback to replacing the filter
            self.signals_view.set_filter_node(node, device_name)

    def _on_device_updated(self, device_name):
        """Called when a device configuration or internal model changes."""
        self._update_event_log_devices()
        
        # If this device is currently selected in Signals View, refresh its signal list
        if device_name == self.signals_view.current_device_name:
            device = self.device_manager.get_device(device_name)
            if device:
                # Passing the device object tells SignalTableModel to use device.root_node
                self.signals_view.set_filter_node(device, device_name)
