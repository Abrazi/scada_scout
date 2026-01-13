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
        
        # Auto-Refresh Checkbox
        from PySide6.QtWidgets import QCheckBox
        self.chk_auto_refresh = QCheckBox("Auto-Refresh (3s)")
        self.chk_auto_refresh.setChecked(True)
        self.chk_auto_refresh.stateChanged.connect(self._on_auto_refresh_toggled)
        toolbar.addWidget(self.chk_auto_refresh)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
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
        
        # No Signals Overlay
        from PySide6.QtWidgets import QLabel
        self.lbl_no_signals = QLabel("No signals found (Select a node)", self.table_view)
        self.lbl_no_signals.setAlignment(Qt.AlignCenter)
        self.lbl_no_signals.setStyleSheet("font-size: 16px; color: gray; background: rgba(255, 255, 255, 128);")
        self.lbl_no_signals.hide()
        
        self.tabs.addTab(self.table_tab, "Live Data")
        
        # Timer for Auto-Refresh
        from PySide6.QtCore import QTimer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._on_refresh_clicked)
        # self.refresh_timer.start(3000)

    def _on_auto_refresh_toggled(self, state):
        if state == Qt.Checked:
            self.refresh_timer.start(3000)
        else:
            self.refresh_timer.stop()

    def _on_refresh_clicked(self):
        """Manually trigger a refresh for the currently shown signals."""
        # Check if we have a current node, if not try to set one
        if not self.current_node:
            self._try_auto_select_node()
            
        if self.current_node:
            device_name = self._get_current_device_name()
            if device_name:
                signals = self._collect_signals(self.current_node)
                if signals:
                    self._trigger_background_read(device_name, signals)

    def _try_auto_select_node(self):
        """Attempt to select the first available device if nothing is selected."""
        devices = self.device_manager.get_all_devices()
        for device in devices:
            if device.root_node:
                self.set_filter_node(device.root_node)
                self.current_device_name = device.config.name
                return

    def set_filter_node(self, node):
        """Updates the view to show signals from the given node."""
        self.current_node = node
        if node is None:
            self.current_device_name = None
        else:
            # Try to determine device name from node
            # This is tricky if node doesn't have backlinks.
            # We rely on _get_current_device_name heuristic or explicit set
            pass

    def resizeEvent(self, event):
        """Ensure overlay stays centered."""
        if hasattr(self, 'lbl_no_signals') and self.lbl_no_signals.isVisible():
             self.lbl_no_signals.resize(self.table_view.size())
             self.lbl_no_signals.move(0, 0) # Relative to table view if parented? 
             # Actually parent is table_view, so 0,0 covers it.
        super().resizeEvent(event)

    def set_filter_node(self, node):
        """Updates the view to show signals from the given node."""
        self.current_node = node
        if node is None:
            self.current_device_name = None
        
        self.table_model.set_node_filter(node)
        self.table_view.resizeColumnsToContents()
        
        # Toggle Overlay
        if self.table_model.rowCount() == 0:
            self.lbl_no_signals.show()
            self.lbl_no_signals.resize(self.table_view.size())
        else:
            self.lbl_no_signals.hide()
        
        # Auto-trigger disabled per user request
        # self._on_refresh_clicked()

    def _trigger_background_read(self, device_name, signals):
        """Execute signal reads in a background thread to prevent UI freeze."""
        import threading
        from src.core.workers import BulkReadWorker
        
        # Cancel previous if needed? 
        # For valid keep-it-simple, just fire and forget, but maybe verify worker not already running?
        
        worker = BulkReadWorker(self.device_manager, device_name, signals)
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
        if not signal:
            return
        
        # We need device_name - try to get from current context
        device_name = self._get_current_device_name()
        if not device_name:
            return
        
        menu = QMenu()
        if self.watch_list_manager:
            add_action = QAction("Add to Watch List", self)
            add_action.triggered.connect(lambda: self.watch_list_manager.add_signal(device_name, signal))
            menu.addAction(add_action)
        
        # Control option
        menu.addSeparator()
        control_action = QAction("Control...", self)
        
        # Enable if RW or explicitly controllable
        is_controllable = getattr(signal, 'access', 'RO') == "RW" or ".Oper" in signal.address or ".ctlVal" in signal.address
        
        if is_controllable:
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
        
        # Fallback 2: get any device
        if devices:
            return devices[0].config.name
            
        return None

    def _on_control_clicked(self, device_name, signal):
        from src.ui.dialogs.control_dialog import ControlDialog
        
        dialog = ControlDialog(device_name, signal, self.device_manager, self)
        dialog.exec()


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
        # import logging
        # logger = logging.getLogger("SignalsView")
        # logger.debug(f"Signal Update received: {signal.address} = {signal.value}")
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
