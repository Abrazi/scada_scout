from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMenuBar, QToolBar, QDockWidget
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from src.ui.widgets.device_tree import DeviceTreeWidget
from src.ui.widgets.signals_view import SignalsViewWidget
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.scd_import_dialog import SCDImportDialog

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
        
        # View Menu
        view_menu = menu_bar.addMenu("&View")
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
        
        self.device_tree = DeviceTreeWidget(self.device_manager)
        self.dock_left.setWidget(self.device_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)
        
        # Connect Selection
        self.device_tree.selection_changed.connect(self._on_tree_selection_changed)
        
        # Right Panel: Signals & Charts
        self.dock_right = QDockWidget("Data Visualization", self)
        self.dock_right.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        
        self.signals_view = SignalsViewWidget(self.device_manager)
        self.dock_right.setWidget(self.signals_view)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)

    def _show_connection_dialog(self):
        """Opens the Connection Dialog."""
        dialog = ConnectionDialog(self)
        if dialog.exec():
            config = dialog.get_config()
            try:
                self.device_manager.add_device(config)
                self.device_manager.connect_device(config.name)
            except ValueError as e:
                # TODO: Show error message
                print(f"Error adding device: {e}")

    def _show_scd_import_dialog(self):
        """Opens the SCD Import Dialog."""
        if not self.scd_dialog:
            self.scd_dialog = SCDImportDialog(self)
            
        if self.scd_dialog.exec():
            configs = self.scd_dialog.get_selected_configs()
            if not configs:
                print("No devices selected.")
                return

            count = 0
            errors = []
            for config in configs:
                try:
                    self.device_manager.add_device(config)
                    # Auto-connect to trigger discovery (which parses SCD)
                    self.device_manager.connect_device(config.name)
                    count += 1
                except Exception as e:
                     msg = f"Failed to add {config.name}: {e}"
                     print(msg)
                     errors.append(msg)
            
            if errors:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Import Errors", "\n".join(errors))
            else:
                print(f"Successfully imported {count} devices.")

    def _on_tree_selection_changed(self, node):
        """Updates the signals view based on selected tree node."""
        self.signals_view.set_filter_node(node)
