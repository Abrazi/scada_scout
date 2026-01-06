from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QHeaderView, QTabWidget
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
        
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        
        # Enable context menu
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        
        # Init Model
        self.table_model = SignalTableModel()
        self.table_view.setModel(self.table_model)
        
        layout.addWidget(self.table_view)
        
        self.tabs.addTab(self.table_tab, "Live Data")

    def set_filter_node(self, node):
        """Updates the view to show signals from the given node."""
        if node is None:
            self.current_device_name = None
        
        self.table_model.set_node_filter(node)
        
        # Trigger background read for these signals to update status from 'Not Connected'
        if node:
            # We need to find the device name for this node
            # For simplicity, if we don't have it, we'll try to get it
            device_name = self._get_current_device_name()
            if device_name:
                from PySide6.QtCore import QTimer
                # Get all signals in this view
                signals = self._collect_signals(node)
                # Read them one by one in the background (very basic implementation)
                for i, sig in enumerate(signals):
                    # Delay slightly to avoid flooding
                    QTimer.singleShot(i * 10, lambda s=sig: self.device_manager.read_signal(device_name, s))

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
        """Recursively collect all signals from a node tree."""
        signals = list(node.signals)
        for child in node.children:
            signals.extend(self._collect_signals(child))
        return signals
