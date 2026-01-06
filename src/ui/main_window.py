from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMenuBar, QToolBar, QDockWidget
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from src.ui.widgets.device_tree import DeviceTreeWidget
from src.ui.widgets.signals_view import SignalsViewWidget
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.scd_import_dialog import SCDImportDialog
from src.ui.widgets.scrollable_message_box import show_scrollable_error
from src.core.exporters import export_network_config_bat, export_device_list_csv, export_goose_details_csv
from PySide6.QtWidgets import QFileDialog, QMessageBox

class MainWindow(QMainWindow):
    """
    Main Application Window.
    Includes Menu Bar, Toolbar, Status Bar, and Docking areas for Panels.
    """
    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
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
        # Connection Menu
        conn_menu = menu_bar.addMenu("&Connection")
        
        # Connect Action
        connect_action = QAction("&Connect...", self)
        connect_action.setStatusTip("Connect to a new device")
        connect_action.triggered.connect(self._show_connection_dialog)
        conn_menu.addAction(connect_action)
        
        # Import SCD Action
        import_scd_action = QAction("&Import SCD...", self)
        import_scd_action.setStatusTip("Import IEDs from SCD file")
        import_scd_action.triggered.connect(self._show_scd_import_dialog)
        file_menu.addAction(import_scd_action)

        file_menu.addSeparator()

        # Export Menu
        export_menu = file_menu.addMenu("Export")
        
        export_bat = QAction("Network Config Script (.bat)...", self)
        export_bat.triggered.connect(self._export_bat)
        export_menu.addAction(export_bat)
        
        export_dev_csv = QAction("Device List (.csv)...", self)
        export_dev_csv.triggered.connect(self._export_device_csv)
        export_menu.addAction(export_dev_csv)
        
        export_goose = QAction("GOOSE Details (.csv)...", self)
        export_goose.triggered.connect(self._export_goose_csv)
        export_menu.addAction(export_goose)
                
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View Menu
        view_menu = menu_bar.addMenu("&View")
        
        # We will add dock visibility toggles in _create_dock_panels
        # because the docks need to exist first
        self.view_menu = view_menu
        
        reset_layout_action = QAction("&Reset Layout", self)
        reset_layout_action.setStatusTip("Restore default panel arrangement")
        reset_layout_action.triggered.connect(self._on_reset_layout)
        view_menu.addAction(reset_layout_action)
        view_menu.addSeparator()
        
        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        
    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        # TODO: Add actions
        
    def _create_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
    def _create_dock_panels(self):
        # Left Panel: Device Tree
        self.dock_left = QDockWidget("Device Explorer", self)
        self.dock_left.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Create watch list manager first (needed by device tree)
        from src.core.watch_list_manager import WatchListManager
        self.watch_list_manager = WatchListManager(self.device_manager)
        
        self.device_tree = DeviceTreeWidget(self.device_manager, self.watch_list_manager)
        self.dock_left.setWidget(self.device_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        
        
        # Connect Selection
        self.device_tree.selection_changed.connect(self._on_tree_selection_changed)
        
        # Connect Device Updates to Event Log Filter
        self.device_manager.device_added.connect(lambda d: self._update_event_log_devices())
        self.device_manager.device_removed.connect(lambda n: self._update_event_log_devices())
        # Also update on rename? (device_updated emits signal too)
        self.device_manager.device_updated.connect(lambda n: self._update_event_log_devices())

        # Right Panel: Signals & Charts
        self.dock_right = QDockWidget("Data Visualization", self)
        self.dock_right.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        
        self.signals_view = SignalsViewWidget(self.device_manager, self.watch_list_manager)
        self.dock_right.setWidget(self.signals_view)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)
        
        # Watch List panel  
        self.dock_bottom = QDockWidget("Watch List", self)
        self.dock_bottom.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        
        from src.ui.widgets.watch_list_widget import WatchListWidget
        self.watch_list_widget = WatchListWidget(self.watch_list_manager)
        self.dock_bottom.setWidget(self.watch_list_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        
        # Event Log panel (right side, tabified with Data Visualization)
        self.dock_events = QDockWidget("Event Log", self)
        self.dock_events.setAllowedAreas(Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        
        from src.ui.widgets.event_log_widget import EventLogWidget
        self.event_log_widget = EventLogWidget()
        self.dock_events.setWidget(self.event_log_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        
        # Tabify event log with signals view
        self.tabifyDockWidget(self.dock_right, self.dock_events)
        self.dock_right.raise_()  # Make signals view the active tab
        
        # Add toggle actions to View menu
        self.view_menu.addAction(self.dock_left.toggleViewAction())
        self.view_menu.addAction(self.dock_right.toggleViewAction())
        self.view_menu.addAction(self.dock_bottom.toggleViewAction())
        self.view_menu.addAction(self.dock_events.toggleViewAction())

    def _on_reset_layout(self):
        """Restores the default docking layout."""
        # Ensure all are visible
        self.dock_left.setVisible(True)
        self.dock_right.setVisible(True)
        self.dock_bottom.setVisible(True)
        self.dock_events.setVisible(True)
        
        # Move to default areas
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_events)
        
        # Re-tabify
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
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Error adding device: {e}")
    
    def _connect_with_progress(self, device_name: str):
        """Connect to device with progress dialog."""
        from src.ui.widgets.connection_progress_dialog import ConnectionProgressDialog
        
        # Show progress dialog
        progress_dialog = ConnectionProgressDialog(device_name, self)
        
        # Connect progress signal
        self.device_manager.connection_progress.connect(
            lambda name, msg, pct: progress_dialog.update_progress(msg, pct) if name == device_name else None
        )
        
        # Handle retry
        progress_dialog.retry_requested.connect(
            lambda: self.device_manager.connect_device(device_name)
        )
        
        # Start connection in background (for now, still blocking but with feedback)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.device_manager.connect_device(device_name))
        
        # Show dialog
        progress_dialog.exec()
        
    def _update_event_log_devices(self):
        """Updates the device filtering list in Event Log."""
        devices = [d.config.name for d in self.device_manager.get_all_devices()]
        # Sort for UX
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
                from src.ui.widgets.scrollable_message_box import show_scrollable_error
                show_scrollable_error(self, "Import Error", "Failed to retrieve selected devices configuration.", str(e))
                return

            if not configs:
                print("No devices selected.")
                return
            
            # Show Progress Dialog for Import
            from src.ui.widgets.import_progress_dialog import ImportProgressDialog
            progress = ImportProgressDialog(self)
            progress.set_progress(0, len(configs))
            progress.show()
            
            count = 0
            errors = []
            
            for i, config in enumerate(configs):
                try:
                    progress.add_log(f"Importing {config.name} ({config.ip_address})...")
                    self.device_manager.add_device(config)
                    # User requested to NOT auto-connect. 
                    # Devices are added in offline state.
                    
                    # But we populate the tree using offline SCD parsing
                    progress.add_log(f"Parsing SCD structure for {config.name}...")
                    self.device_manager.load_offline_scd(config.name)
                    
                    count += 1
                    progress.set_progress(i + 1)
                except Exception as e:
                     msg = f"Failed to add {config.name}: {e}"
                     progress.add_log(f"ERROR: {msg}")
                     print(msg)
                     errors.append(msg)
            
            progress.finish()
            
            if errors:
                show_scrollable_error(self, "Import Errors", "Some devices failed to import:", "\n".join(errors))
            else:
                self.status_bar.showMessage(f"Successfully imported {count} devices.", 5000)

    def _export_bat(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Export Network Config", "network_config.bat", "Batch Files (*.bat)")
        if fname:
            devices = self.device_manager.get_all_devices()
            success, msg = export_network_config_bat(devices, fname)
            if success:
                self.status_bar.showMessage("Export successful", 3000)
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export BAT file:", msg)

    def _export_device_csv(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Export Device List", "devices.csv", "CSV Files (*.csv)")
        if fname:
            devices = self.device_manager.get_all_devices()
            success, msg = export_device_list_csv(devices, fname)
            if success:
                self.status_bar.showMessage("Export successful", 3000)
            else:
                show_scrollable_error(self, "Export Failed", "Failed to export Device CSV:", msg)

    def _export_goose_csv(self):
        # We need an SCD file for this. 
        # If we imported from SCD, we might have the path stored in one of the devices?
        # Or we ask user to select SCD file? User request 4c implies exporting *based on current state*?
        # But GOOSE details are deep in SCD. 
        # Best approach: Check if any device has scd_file_path, picking the first valid one.
        # Or ask user to select SCD if not found.
        
        scd_path = None
        devices = self.device_manager.get_all_devices()
        for dev in devices:
            if dev.config.scd_file_path:
                scd_path = dev.config.scd_file_path
                break
        
        if not scd_path:
             # Ask user
             scd_path, _ = QFileDialog.getOpenFileName(self, "Select Source SCD for GOOSE Export", "", "SCD Files (*.scd *.cid *.xml)")
             if not scd_path: return

        fname, _ = QFileDialog.getSaveFileName(self, "Export GOOSE Details", "goose_details.csv", "CSV Files (*.csv)")
        if fname:
            success, msg = export_goose_details_csv(scd_path, fname)
            if success:
                 self.status_bar.showMessage("Export successful", 3000)
            else:
                 show_scrollable_error(self, "Export Failed", "Failed to export GOOSE CSV:", msg)

    def _on_tree_selection_changed(self, node):
        """Updates the signals view based on selected tree node."""
        self.signals_view.set_filter_node(node)
