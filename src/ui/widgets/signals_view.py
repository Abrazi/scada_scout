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
    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
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
        
        # Init Model
        self.table_model = SignalTableModel()
        self.table_view.setModel(self.table_model)
        
        layout.addWidget(self.table_view)
        
        self.tabs.addTab(self.table_tab, "Live Data")

    def set_filter_node(self, node):
        """Updates the view to show signals from the given node."""
        self.table_model.set_node_filter(node)

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
