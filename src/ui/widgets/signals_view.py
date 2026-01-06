from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QTabWidget, QPushButton, QSizePolicy
from PySide6.QtGui import QStandardItemModel, QStandardItem, QPainter
from PySide6.QtCharts import QChart, QChartView, QLineSeries
from PySide6.QtCore import Qt
from src.ui.models.signal_table_model import SignalTableModel

class SignalsViewWidget(QWidget):
    """
    Widget containing the Data Grid and Live Chart.
    Uses tabs to switch between Table View and Chart View.
    """
    def __init__(self, device_manager, watch_list_manager=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.watch_list_manager = watch_list_manager
        self.current_device_name = None  # Track which device's signals we're showing
        self.current_node = None        # Track current node for manual refresh
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self._setup_table_tab()
        self._setup_chart_tab()
        
        self._connect_signals()

    def _setup_table_tab(self):
        """Create the Signals Table tab."""
        self.table_tab = QWidget()
        layout = QVBoxLayout(self.table_tab)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh All")
        self.btn_refresh.setFixedWidth(100)
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        # Allow user to resize columns and auto-fit to contents initially
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True) 
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        
        # Enable context menu
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        
        # Init Model
        self.table_model = SignalTableModel()
        self.table_view.setModel(self.table_model)
        
        layout.addWidget(self.table_view)
        
        self.tabs.addTab(self.table_tab, "Live Data")

    def _on_refresh_clicked(self):
        """Manually trigger a refresh for the currently shown signals."""
        if self.current_node:
            device_name = self._get_current_device_name()
            if device_name:
                signals = self._collect_signals(self.current_node)
                if signals:
                    self._trigger_background_read(device_name, signals)

    def set_filter_node(self, node):
        """Updates the view to show signals from the given node."""
        self.current_node = node
        if node is None:
            self.current_device_name = None
        
        self.table_model.set_node_filter(node)
        self.table_view.resizeColumnsToContents()

    def _trigger_background_read(self, device_name, signals):
        """Execute signal reads in a background thread to prevent UI freeze."""
        import threading
        from src.core.workers import BulkReadWorker
        
        worker = BulkReadWorker(self.device_manager, device_name, signals)
        # Use a simple thread for now. In a larger app, use QThreadPool.
        t = threading.Thread(target=worker.run)
        t.daemon = True
        t.start()

    def _on_table_context_menu(self, position):
        """Handle right-click context menu in signals table."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        index = self.table_view.indexAt(position)
        if not index.isValid():
            return
        
        # Get the signal from the model
        signal = self.table_model.get_signal_at_row(index.row())
        if not signal or not self.watch_list_manager:
            return
        
        # We need device_name - try to get from current context
        # This is a limitation - we need to track which device's signals are shown
        # For now, try to get from first connected device or require explicit tracking
        device_name = self._get_current_device_name()
        if not device_name:
            return
        
        menu = QMenu()
        add_action = QAction("Add to Watch List", self)
        add_action.triggered.connect(lambda: self.watch_list_manager.add_signal(device_name, signal))
        menu.addAction(add_action)
        
        # Control option
        menu.addSeparator()
        control_action = QAction("Control...", self)
        if getattr(signal, 'access', 'RO') == "RW":
            control_action.setEnabled(True)
            control_action.triggered.connect(lambda: self._on_control_clicked(device_name, signal))
        else:
            control_action.setEnabled(False)
            control_action.setToolTip("This signal is Read-Only")
        menu.addAction(control_action)
        
        menu.exec(self.table_view.viewport().mapToGlobal(position))
    
    def _get_current_device_name(self):
        """Get the device name for current signals view."""
        # Try to use tracked device name
        if hasattr(self, 'current_device_name') and self.current_device_name:
            return self.current_device_name
        
        # Fallback: get first connected device
        devices = self.device_manager.get_all_devices()
        for device in devices:
            if device.connected:
                return device.config.name
        return None

    def _on_control_clicked(self, device_name, signal):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        
        # User requested command
        # For ctVal (INT32), we usually send an integer.
        # Should we assume Integer?
        val, ok = QInputDialog.getInt(self, "Send Control", f"Enter value for {signal.name}:", 0)
        
        if ok:
             try:
                 self.device_manager.send_control_command(device_name, signal, 'OPERATE', val)
                 QMessageBox.information(self, "Success", f"Command sent to {signal.name}")
             except Exception as e:
                 QMessageBox.critical(self, "Error", f"Failed to send command: {e}")

    def _setup_chart_tab(self):
        """Create the Chart tab."""
        self.chart_tab = QWidget()
        layout = QVBoxLayout(self.chart_tab)
        
        self.chart = QChart()
        self.chart.setTitle("Live Telemetry")
        
        # We will dynamically add series later
        self.chart.createDefaultAxes()
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        
        layout.addWidget(self.chart_view)
        # self.tabs.addTab(self.chart_tab, "Trend Chart") # Hide Chart for now until implemented

    def _connect_signals(self):
        """Connect to DeviceManager."""
        self.device_manager.device_added.connect(self._on_device_added)
        self.device_manager.signal_updated.connect(self._on_signal_update)

    def _on_device_added(self, device):
        """When a device is added, we don't necessarily update view until selected."""
        pass

    def _on_signal_update(self, device_name, signal):
        """Handle live update."""
        self.table_model.update_signal(signal)
        
    def _collect_signals(self, node) -> list:
        """Recursively collect all signals from a node tree (supports Node, Signal, or Device)."""
        if node is None:
            return []
            
        signals = []
        
        # 1. If it's a Signal (leaf)
        if hasattr(node, 'address') and not hasattr(node, 'signals'):
            return [node]
            
        # 2. If it's a Node (branch)
        if hasattr(node, "signals") and node.signals:
            signals.extend(node.signals)
        
        if hasattr(node, "children") and node.children:
            for child in node.children:
                signals.extend(self._collect_signals(child))
                
        # 3. If it's a Device (root)
        if hasattr(node, "root_node") and node.root_node:
            signals.extend(self._collect_signals(node.root_node))
            
        return signals
