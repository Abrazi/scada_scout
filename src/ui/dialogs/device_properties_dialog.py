from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QLabel, QTableWidget, QTableWidgetItem, QPushButton, 
    QGroupBox, QGridLayout, QTextEdit, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from src.models.device_models import Device, DeviceType
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class DevicePropertiesDialog(QDialog):
    """
    Comprehensive device properties dialog showing protocol details,
    connection info, GOOSE, reports, datasets, and other IEC 61850 features.
    """
    
    def __init__(self, device: Device, device_manager, watch_list_manager=None, parent=None):
        super().__init__(parent)
        self.device = device
        self.device_manager = device_manager
        self.protocol = device_manager.get_protocol(device.config.name)
        self.watch_list_manager = watch_list_manager
        self.latest_rtt = -1.0  # Store the most recent RTT measurement
        
        self.setWindowTitle(f"Device Properties - {device.config.name}")
        self.resize(900, 700)
        
        self._setup_ui()
        self._populate_data()
    
    def _setup_ui(self):
        """Setup the main UI with tabs."""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel(f"<h2>{self.device.config.name}</h2>")
        layout.addWidget(title_label)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_connection_tab(), "Connection")
        
        # Protocol-specific tabs
        if self.device.config.device_type == DeviceType.IEC61850_IED:
            self.tabs.addTab(self._create_datasets_tab(), "DataSets")
            self.tabs.addTab(self._create_reports_tab(), "Reports")
            self.tabs.addTab(self._create_goose_tab(), "GOOSE")
            self.tabs.addTab(self._create_control_tab(), "Control Objects")
        elif self.device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
            self.tabs.addTab(self._create_modbus_tab(), "Modbus Info")
        
        self.tabs.addTab(self._create_statistics_tab(), "Statistics")
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
    
    def _create_general_tab(self):
        """Create general information tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Device info group
        group = QGroupBox("Device Information")
        grid = QGridLayout()
        
        row = 0
        self._add_property_row(grid, row, "Device Name:", self.device.config.name)
        row += 1
        self._add_property_row(grid, row, "Protocol:", self.device.config.device_type.value)
        row += 1
        self._add_property_row(grid, row, "Description:", self.device.config.description or "N/A")
        row += 1
        self._add_property_row(grid, row, "Folder:", self.device.config.folder or "Root")
        row += 1
        self._add_property_row(grid, row, "Enabled:", "Yes" if self.device.config.enabled else "No")
        row += 1
        
        if self.device.config.device_type == DeviceType.IEC61850_IED:
            discovery_mode = "SCD File" if self.device.config.use_scd_discovery else "Online Discovery"
            self._add_property_row(grid, row, "Discovery Mode:", discovery_mode)
            row += 1
            
            if self.device.config.scd_file_path:
                self._add_property_row(grid, row, "SCD File:", self.device.config.scd_file_path)
                row += 1
        
        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_connection_tab(self):
        """Create connection information tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Connection details group
        conn_group = QGroupBox("Connection Details")
        grid = QGridLayout()
        
        row = 0
        self._add_property_row(grid, row, "IP Address:", self.device.config.ip_address)
        row += 1
        self._add_property_row(grid, row, "Port:", str(self.device.config.port))
        row += 1
        
        connection_status = "🟢 Connected" if self.device.connected else "🔴 Disconnected"
        self._add_property_row(grid, row, "Connection Status:", connection_status)
        row += 1
        
        # Get VLAN info if available from protocol params
        vlan = self.device.config.protocol_params.get("vlan", "Not configured")
        self._add_property_row(grid, row, "VLAN:", str(vlan))
        row += 1
        
        # Polling settings
        self._add_property_row(grid, row, "Polling Enabled:", "Yes" if self.device.config.polling_enabled else "No")
        row += 1
        
        if self.device.config.polling_enabled:
            self._add_property_row(grid, row, "Poll Interval:", f"{self.device.config.poll_interval} seconds")
            row += 1
        
        # Protocol-specific params
        if self.device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
            self._add_property_row(grid, row, "Modbus Unit ID:", str(self.device.config.modbus_unit_id))
            row += 1
            self._add_property_row(grid, row, "Timeout:", f"{self.device.config.modbus_timeout} seconds")
            row += 1
        
        conn_group.setLayout(grid)
        layout.addWidget(conn_group)
        
        # Network info group
        net_group = QGroupBox("Network Information")
        net_grid = QGridLayout()
        
        # Try to get additional network info
        row = 0
        
        # Max RTT
        max_rtt = self._calculate_max_rtt()
        self._add_property_row(net_grid, row, "Max RTT:", f"{max_rtt:.2f} ms" if max_rtt >= 0 else "N/A")
        row += 1
        
        # Try to get MAC address, gateway, etc. if available
        # These would need to be implemented in the protocol adapters
        mac_address = self.device.config.protocol_params.get("mac_address", "N/A")
        self._add_property_row(net_grid, row, "MAC Address:", mac_address)
        row += 1
        
        net_group.setLayout(net_grid)
        layout.addWidget(net_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_datasets_tab(self):
        """Create datasets information tab (IEC 61850)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add refresh button at top
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh DataSets")
        refresh_btn.setMaximumWidth(150)
        refresh_btn.clicked.connect(lambda: self._refresh_datasets_tab(layout))
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Populate content
        self._populate_datasets_content(layout)
        
        return widget
    
    def _populate_datasets_content(self, layout):
        """Populate the datasets tab content."""
        # Clear existing content (except refresh button)
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        # Get dataset info - try protocol adapter first, then fall back to tree parsing
        datasets_info = self._get_datasets_from_protocol()
        if not datasets_info:
            datasets_info = self._extract_datasets_info()
        
        if not datasets_info:
            msg = "No datasets configured or discovered."
            if not self.device.connected:
                msg += "\n\nNote: Device is not connected. Connect the device to retrieve live dataset information."
            layout.addWidget(QLabel(msg))
        else:
            # Summary label
            summary = QLabel(f"<b>Total DataSets:</b> {len(datasets_info)}")
            layout.addWidget(summary)
            
            # Table of datasets
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Name", "Reference", "Entries", "Used By"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setRowCount(len(datasets_info))
            
            for idx, ds in enumerate(datasets_info):
                table.setItem(idx, 0, QTableWidgetItem(ds.get("name", "")))
                table.setItem(idx, 1, QTableWidgetItem(ds.get("ref", "")))
                table.setItem(idx, 2, QTableWidgetItem(str(ds.get("entry_count", 0))))
                table.setItem(idx, 3, QTableWidgetItem(ds.get("used_by", "N/A")))
            
            layout.addWidget(table)
            
            # Details text area
            details_label = QLabel("<b>DataSet Details:</b>")
            layout.addWidget(details_label)
            
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setMaximumHeight(200)
            
            details_content = self._format_datasets_details(datasets_info)
            details_text.setPlainText(details_content)
            
            layout.addWidget(details_text)
    
    def _refresh_datasets_tab(self, layout):
        """Refresh the datasets tab content."""
        # Measure RTT on refresh
        self._measure_rtt_on_refresh()
        self._populate_datasets_content(layout)
    
    def _create_reports_tab(self):
        """Create reports information tab (IEC 61850)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add refresh button at top
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Reports")
        refresh_btn.setMaximumWidth(150)
        refresh_btn.clicked.connect(lambda: self._refresh_reports_tab(layout))
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Get report info - try protocol adapter first, then fall back to tree parsing
        self._populate_reports_content(layout)
        
        return widget
    
    def _populate_reports_content(self, layout):
        """Populate the reports tab content."""
        # Clear existing content (except refresh button)
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        reports_info = self._get_reports_from_protocol()
        if not reports_info:
            reports_info = self._extract_reports_info()
        
        if not reports_info:
            msg = "No reports configured or discovered."
            if not self.device.connected:
                msg += "\n\nNote: Device is not connected. Connect the device to retrieve live report information."
            layout.addWidget(QLabel(msg))
        else:
            # Summary label
            urcb_count = len([r for r in reports_info if r.get("type") == "URCB"])
            brcb_count = len([r for r in reports_info if r.get("type") == "BRCB"])
            summary = QLabel(f"<b>Total Reports:</b> {len(reports_info)} (URCB: {urcb_count}, BRCB: {brcb_count})")
            layout.addWidget(summary)
            
            # Table of reports
            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(["Name", "Type", "RptID", "DataSet", "TrgOps", "IntgPd"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)
            table.setRowCount(len(reports_info))
            
            for idx, rpt in enumerate(reports_info):
                table.setItem(idx, 0, QTableWidgetItem(rpt.get("name", "")))
                table.setItem(idx, 1, QTableWidgetItem(rpt.get("type", "")))
                table.setItem(idx, 2, QTableWidgetItem(rpt.get("rpt_id", "")))
                table.setItem(idx, 3, QTableWidgetItem(rpt.get("dataset", "")))
                table.setItem(idx, 4, QTableWidgetItem(rpt.get("trgops", "")))
                table.setItem(idx, 5, QTableWidgetItem(str(rpt.get("intgpd", ""))))
            
            layout.addWidget(table)
            
            # Details text area
            details_label = QLabel("<b>Report Configuration Details:</b>")
            layout.addWidget(details_label)
            
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setMaximumHeight(200)
            
            details_content = self._format_reports_details(reports_info)
            details_text.setPlainText(details_content)
            
            layout.addWidget(details_text)
    
    def _refresh_reports_tab(self, layout):
        """Refresh the reports tab content."""
        # Measure RTT on refresh
        self._measure_rtt_on_refresh()
        self._populate_reports_content(layout)
    
    def _create_goose_tab(self):
        """Create GOOSE information tab (IEC 61850)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add refresh button at top
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh GOOSE")
        refresh_btn.setMaximumWidth(150)
        refresh_btn.clicked.connect(lambda: self._refresh_goose_tab(layout))
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Populate content
        self._populate_goose_content(layout)
        
        return widget
    
    def _populate_goose_content(self, layout):
        """Populate the GOOSE tab content."""
        # Clear existing content (except refresh button)
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        # Get GOOSE info - try protocol adapter first, then fall back to tree parsing
        goose_info = self._get_goose_from_protocol()
        if not goose_info:
            goose_info = self._extract_goose_info()
        
        if not goose_info:
            msg = "No GOOSE control blocks configured or discovered."
            if not self.device.connected:
                msg += "\n\nNote: Device is not connected. Connect the device to retrieve live GOOSE information."
            layout.addWidget(QLabel(msg))
        else:
            # Summary label
            summary = QLabel(f"<b>Total GOOSE Control Blocks:</b> {len(goose_info)}")
            layout.addWidget(summary)
            
            # Table of GOOSE CBs
            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(["Name", "GoID", "DataSet", "Signals", "MinTime", "MaxTime"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)
            table.setRowCount(len(goose_info))
            
            for idx, gse in enumerate(goose_info):
                table.setItem(idx, 0, QTableWidgetItem(gse.get("name", "")))
                table.setItem(idx, 1, QTableWidgetItem(gse.get("goid", "")))
                table.setItem(idx, 2, QTableWidgetItem(gse.get("dataset", "")))
                table.setItem(idx, 3, QTableWidgetItem(str(gse.get("signal_count", 0))))
                table.setItem(idx, 4, QTableWidgetItem(str(gse.get("mintime", ""))))
                table.setItem(idx, 5, QTableWidgetItem(str(gse.get("maxtime", ""))))
            
            layout.addWidget(table)
            
            # Subscriber info
            subscriber_label = QLabel("<b>GOOSE Subscribers:</b>")
            layout.addWidget(subscriber_label)
            
            subscriber_text = QTextEdit()
            subscriber_text.setReadOnly(True)
            subscriber_text.setMaximumHeight(150)
            
            subscriber_content = self._format_goose_subscribers(goose_info)
            subscriber_text.setPlainText(subscriber_content)
            
            layout.addWidget(subscriber_text)
            
            # Details text area
            details_label = QLabel("<b>GOOSE Details:</b>")
            layout.addWidget(details_label)
            
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setMaximumHeight(150)
            
            details_content = self._format_goose_details(goose_info)
            details_text.setPlainText(details_content)
            
            layout.addWidget(details_text)
    
    def _refresh_goose_tab(self, layout):
        """Refresh the GOOSE tab content."""
        # Measure RTT on refresh
        self._measure_rtt_on_refresh()
        self._populate_goose_content(layout)
    
    def _create_control_tab(self):
        """Create control objects information tab (IEC 61850)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Get control objects info
        control_info = self._extract_control_info()
        
        if not control_info:
            layout.addWidget(QLabel("No control objects discovered."))
        else:
            # Summary label
            summary = QLabel(f"<b>Total Control Objects:</b> {len(control_info)}")
            layout.addWidget(summary)
            
            # Table of control objects
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Name", "Control Model", "Activation", "Status"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setRowCount(len(control_info))
            
            for idx, ctrl in enumerate(control_info):
                table.setItem(idx, 0, QTableWidgetItem(ctrl.get("name", "")))
                table.setItem(idx, 1, QTableWidgetItem(ctrl.get("model", "")))
                table.setItem(idx, 2, QTableWidgetItem(ctrl.get("activation", "")))
                table.setItem(idx, 3, QTableWidgetItem(ctrl.get("status", "")))
            
            layout.addWidget(table)
            
            # Details
            details_label = QLabel("<b>Control Activation Information:</b>")
            layout.addWidget(details_label)
            
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            
            details_content = """Control Object Activation Methods:
            
SBO (Select-Before-Operate):
    1. Select the control object
    2. Operate within timeout period
    3. Ensures no conflicting operations
    
Direct Operate:
    - Immediate operation without selection
    - Used for simple on/off controls
    
Direct Operate with Enhanced Security:
    - Requires additional authentication
    - Used for critical controls
            """
            details_text.setPlainText(details_content)
            
            layout.addWidget(details_text)
        
        return widget
    
    def _create_modbus_tab(self):
        """Create Modbus-specific information tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Modbus Configuration")
        grid = QGridLayout()
        
        row = 0
        self._add_property_row(grid, row, "Unit ID:", str(self.device.config.modbus_unit_id))
        row += 1
        self._add_property_row(grid, row, "Timeout:", f"{self.device.config.modbus_timeout} seconds")
        row += 1
        self._add_property_row(grid, row, "Register Maps:", str(len(self.device.config.modbus_register_maps)))
        row += 1
        
        if self.device.config.device_type == DeviceType.MODBUS_SERVER:
            self._add_property_row(grid, row, "Slave Mappings:", str(len(self.device.config.modbus_slave_mappings)))
            row += 1
            self._add_property_row(grid, row, "Slave Blocks:", str(len(self.device.config.modbus_slave_blocks)))
            row += 1
        
        group.setLayout(grid)
        layout.addWidget(group)
        
        # Register map details
        if self.device.config.modbus_register_maps:
            map_group = QGroupBox("Register Maps")
            map_layout = QVBoxLayout()
            
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Name", "Function", "Start", "Count", "Data Type"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.setRowCount(len(self.device.config.modbus_register_maps))
            
            for idx, reg_map in enumerate(self.device.config.modbus_register_maps):
                table.setItem(idx, 0, QTableWidgetItem(reg_map.name))
                table.setItem(idx, 1, QTableWidgetItem(str(reg_map.function_code)))
                table.setItem(idx, 2, QTableWidgetItem(str(reg_map.start_address)))
                table.setItem(idx, 3, QTableWidgetItem(str(reg_map.count)))
                table.setItem(idx, 4, QTableWidgetItem(reg_map.data_type.value if hasattr(reg_map, 'data_type') else "N/A"))
            
            map_layout.addWidget(table)
            map_group.setLayout(map_layout)
            layout.addWidget(map_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_statistics_tab(self):
        """Create statistics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add refresh button at top
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh & Measure RTT")
        refresh_btn.setMaximumWidth(180)
        refresh_btn.clicked.connect(lambda: self._refresh_statistics_tab(layout))
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Populate content
        self._populate_statistics_content(layout)
        
        return widget
    
    def _populate_statistics_content(self, layout):
        """Populate the statistics tab content."""
        # Clear existing content (except refresh button)
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        group = QGroupBox("Device Statistics")
        grid = QGridLayout()
        
        row = 0
        
        # Count signals
        signal_count = self._count_signals()
        self._add_property_row(grid, row, "Total Signals:", str(signal_count))
        row += 1
        
        # Watch list info
        if self.watch_list_manager:
            watch_count = len(self.watch_list_manager.get_signals_for_device(self.device.config.name))
            self._add_property_row(grid, row, "Watch List Signals:", str(watch_count))
            row += 1
        
        # Last update time
        if self.device.last_update:
            last_update = self.device.last_update.strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_update = "Never"
        self._add_property_row(grid, row, "Last Update:", last_update)
        row += 1
        
        # Latest RTT measurement
        if self.latest_rtt > 0:
            self._add_property_row(grid, row, "Latest RTT:", f"{self.latest_rtt:.2f} ms")
            row += 1
        
        # Average RTT
        avg_rtt = self._calculate_avg_rtt()
        self._add_property_row(grid, row, "Average RTT:", f"{avg_rtt:.2f} ms" if avg_rtt >= 0 else "N/A")
        row += 1
        
        # Max RTT
        max_rtt = self._calculate_max_rtt()
        self._add_property_row(grid, row, "Max RTT:", f"{max_rtt:.2f} ms" if max_rtt >= 0 else "N/A")
        row += 1
        
        # Min RTT
        min_rtt = self._calculate_min_rtt()
        self._add_property_row(grid, row, "Min RTT:", f"{min_rtt:.2f} ms" if min_rtt >= 0 else "N/A")
        row += 1
        
        # Protocol-specific stats
        if self.device.config.device_type == DeviceType.IEC61850_IED:
            datasets_count = len(self._extract_datasets_info())
            reports_count = len(self._extract_reports_info())
            goose_count = len(self._extract_goose_info())
            control_count = len(self._extract_control_info())
            
            self._add_property_row(grid, row, "DataSets:", str(datasets_count))
            row += 1
            self._add_property_row(grid, row, "Reports:", str(reports_count))
            row += 1
            self._add_property_row(grid, row, "GOOSE CBs:", str(goose_count))
            row += 1
            self._add_property_row(grid, row, "Control Objects:", str(control_count))
            row += 1
        
        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
    
    def _refresh_statistics_tab(self, layout):
        """Refresh the statistics tab and measure RTT."""
        # Measure RTT
        self._measure_rtt_on_refresh()
        # Refresh display
        self._populate_statistics_content(layout)
    
    # Helper methods
    
    def _add_property_row(self, grid: QGridLayout, row: int, label: str, value: str):
        """Add a property row to a grid layout."""
        label_widget = QLabel(f"<b>{label}</b>")
        value_widget = QLabel(value)
        value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(label_widget, row, 0, Qt.AlignTop)
        grid.addWidget(value_widget, row, 1, Qt.AlignTop)
    
    def _measure_rtt_on_refresh(self) -> float:
        """Measure RTT by reading a signal from the device."""
        import time
        
        if not self.device.connected or not self.protocol:
            logger.debug("Device not connected, cannot measure RTT")
            return -1.0
        
        # First, try to get RTT from watch list if signals are being monitored
        if self.watch_list_manager:
            watch_signals = self.watch_list_manager.get_signals_for_device(self.device.config.name)
            if watch_signals:
                # Get RTT from watch list signals
                rtts = []
                for sig in watch_signals:
                    if hasattr(sig, 'last_rtt') and sig.last_rtt > 0:
                        rtts.append(sig.last_rtt)
                
                if rtts:
                    avg_rtt = sum(rtts) / len(rtts)
                    logger.info(f"Retrieved RTT from watch list: {avg_rtt:.2f} ms ({len(rtts)} signals)")
                    self.latest_rtt = avg_rtt
                    return avg_rtt
        
        # If no watch list signals, try to read a random stVal to measure RTT
        test_signal = self._find_stval_signal()
        if test_signal:
            try:
                logger.info(f"Measuring RTT by reading {test_signal.address}...")
                start_time = time.perf_counter()
                result = self.protocol.read_signal(test_signal)
                end_time = time.perf_counter()
                
                if result:
                    rtt = (end_time - start_time) * 1000  # Convert to ms
                    logger.info(f"Measured RTT: {rtt:.2f} ms")
                    self.latest_rtt = rtt
                    return rtt
                else:
                    logger.warning(f"Failed to read signal {test_signal.address}")
            except Exception as e:
                logger.error(f"Error measuring RTT: {e}")
        
        return -1.0
    
    def _find_stval_signal(self):
        """Find a random stVal signal to test RTT."""
        if not self.device.root_node:
            return None
        
        # Look for any signal with 'stVal' in the address (common in IEC 61850)
        signals = []
        self._collect_stval_signals_recursive(self.device.root_node, signals)
        
        if signals:
            # Return the first stVal signal found
            return signals[0]
        
        # If no stVal found, just return any readable signal
        all_signals = []
        self._collect_all_signals_recursive(self.device.root_node, all_signals)
        return all_signals[0] if all_signals else None
    
    def _collect_stval_signals_recursive(self, node, signals: list):
        """Recursively collect stVal signals."""
        if hasattr(node, 'signals'):
            for signal in node.signals:
                if 'stVal' in signal.address or 'ST$' in signal.address:
                    signals.append(signal)
                    if len(signals) >= 5:  # Limit collection
                        return
        
        if hasattr(node, 'children'):
            for child in node.children:
                self._collect_stval_signals_recursive(child, signals)
                if len(signals) >= 5:
                    return
    
    def _collect_all_signals_recursive(self, node, signals: list):
        """Recursively collect all signals."""
        if hasattr(node, 'signals'):
            for signal in node.signals:
                if signal.access in ('RO', 'RW'):  # Only readable signals
                    signals.append(signal)
                    if len(signals) >= 5:
                        return
        
        if hasattr(node, 'children'):
            for child in node.children:
                self._collect_all_signals_recursive(child, signals)
                if len(signals) >= 5:
                    return
    
    def _calculate_max_rtt(self) -> float:
        """Calculate maximum RTT from all signals and watch list."""
        max_rtt = -1.0
        
        # Check watch list first
        if self.watch_list_manager:
            watch_signals = self.watch_list_manager.get_signals_for_device(self.device.config.name)
            for sig in watch_signals:
                if hasattr(sig, 'last_rtt') and sig.last_rtt > max_rtt:
                    max_rtt = sig.last_rtt
        
        # Check device tree
        if self.device.root_node:
            tree_max = self._find_max_rtt_recursive(self.device.root_node)
            if tree_max > max_rtt:
                max_rtt = tree_max
        
        # Include latest measurement
        if self.latest_rtt > max_rtt:
            max_rtt = self.latest_rtt
        
        return max_rtt
    
    def _find_max_rtt_recursive(self, node) -> float:
        """Recursively find max RTT in node tree."""
        max_rtt = -1.0
        
        # Check signals
        if hasattr(node, 'signals'):
            for signal in node.signals:
                if hasattr(signal, 'last_rtt') and signal.last_rtt > max_rtt:
                    max_rtt = signal.last_rtt
        
        # Check children
        if hasattr(node, 'children'):
            for child in node.children:
                child_max = self._find_max_rtt_recursive(child)
                if child_max > max_rtt:
                    max_rtt = child_max
        
        return max_rtt
    
    def _calculate_avg_rtt(self) -> float:
        """Calculate average RTT from all signals and watch list."""
        rtts = []
        
        # Get RTTs from watch list
        if self.watch_list_manager:
            watch_signals = self.watch_list_manager.get_signals_for_device(self.device.config.name)
            for sig in watch_signals:
                if hasattr(sig, 'last_rtt') and sig.last_rtt > 0:
                    rtts.append(sig.last_rtt)
        
        # Get RTTs from device tree
        if self.device.root_node:
            self._collect_rtts_recursive(self.device.root_node, rtts)
        
        # Include latest measurement
        if self.latest_rtt > 0:
            rtts.append(self.latest_rtt)
        
        if rtts:
            return sum(rtts) / len(rtts)
        return -1.0
    
    def _calculate_min_rtt(self) -> float:
        """Calculate minimum RTT from all signals and watch list."""
        rtts = []
        
        # Get RTTs from watch list
        if self.watch_list_manager:
            watch_signals = self.watch_list_manager.get_signals_for_device(self.device.config.name)
            for sig in watch_signals:
                if hasattr(sig, 'last_rtt') and sig.last_rtt > 0:
                    rtts.append(sig.last_rtt)
        
        # Get RTTs from device tree
        if self.device.root_node:
            self._collect_rtts_recursive(self.device.root_node, rtts)
        
        # Include latest measurement
        if self.latest_rtt > 0:
            rtts.append(self.latest_rtt)
        
        if rtts:
            return min(rtts)
        return -1.0
    
    def _collect_rtts_recursive(self, node, rtts: list):
        """Recursively collect RTT values."""
        if hasattr(node, 'signals'):
            for signal in node.signals:
                if hasattr(signal, 'last_rtt') and signal.last_rtt > 0:
                    rtts.append(signal.last_rtt)
        
        if hasattr(node, 'children'):
            for child in node.children:
                self._collect_rtts_recursive(child, rtts)
    
    def _count_signals(self) -> int:
        """Count total signals in device tree."""
        if not self.device.root_node:
            return 0
        return self._count_signals_recursive(self.device.root_node)
    
    def _count_signals_recursive(self, node) -> int:
        """Recursively count signals."""
        count = 0
        
        if hasattr(node, 'signals'):
            count += len(node.signals)
        
        if hasattr(node, 'children'):
            for child in node.children:
                count += self._count_signals_recursive(child)
        
        return count
    
    def _extract_datasets_info(self) -> list:
        """Extract dataset information from device tree."""
        datasets = []
        
        if not self.device.root_node:
            return datasets
        
        self._find_datasets_recursive(self.device.root_node, datasets)
        return datasets
    
    def _find_datasets_recursive(self, node, datasets: list):
        """Recursively find DataSet nodes."""
        if hasattr(node, 'name') and node.name == "DataSets":
            # This is a datasets container
            if hasattr(node, 'children'):
                for ds_node in node.children:
                    ds_info = {
                        "name": ds_node.name,
                        "ref": "",
                        "entry_count": 0,
                        "entries": [],
                        "used_by": ""
                    }
                    
                    # Extract ref and entries
                    if hasattr(ds_node, 'children'):
                        for child in ds_node.children:
                            if hasattr(child, 'name'):
                                if child.name == "Ref" and hasattr(child, 'signals') and child.signals:
                                    ds_info["ref"] = str(child.signals[0].value) if child.signals else ""
                                elif child.name == "DataSetEntries":
                                    if hasattr(child, 'children'):
                                        ds_info["entry_count"] = len(child.children)
                                        for entry in child.children:
                                            ds_info["entries"].append(entry.name)
                    
                    datasets.append(ds_info)
        
        # Recurse to children
        if hasattr(node, 'children'):
            for child in node.children:
                self._find_datasets_recursive(child, datasets)
    
    def _extract_reports_info(self) -> list:
        """Extract report information from device tree."""
        reports = []
        
        if not self.device.root_node:
            return reports
        
        self._find_reports_recursive(self.device.root_node, reports)
        return reports
    
    def _get_datasets_from_protocol(self) -> list:
        """Get datasets directly from protocol adapter."""
        if self.protocol and hasattr(self.protocol, 'get_datasets_info'):
            try:
                logger.info("Getting datasets from protocol adapter...")
                datasets = self.protocol.get_datasets_info()
                logger.info(f"Protocol adapter returned {len(datasets)} datasets")
                # Convert to format expected by UI
                formatted = []
                for ds in datasets:
                    formatted.append({
                        "name": ds.get("name", ""),
                        "ref": ds.get("reference", ds.get("ref", "")),
                        "entry_count": ds.get("entry_count", 0),
                        "entries": ds.get("entries", []),
                        "used_by": ""
                    })
                return formatted
            except Exception as e:
                logger.error(f"Could not get datasets from protocol: {e}", exc_info=True)
        else:
            logger.debug(f"Protocol adapter not available or missing method. Protocol: {self.protocol}")
        return []
    
    def _get_reports_from_protocol(self) -> list:
        """Get reports directly from protocol adapter."""
        if self.protocol and hasattr(self.protocol, 'get_reports_info'):
            try:
                logger.info("Getting reports from protocol adapter...")
                reports = self.protocol.get_reports_info()
                logger.info(f"Protocol adapter returned {len(reports)} reports")
                # Convert to format expected by UI
                formatted = []
                for rpt in reports:
                    formatted.append({
                        "name": rpt.get("name", ""),
                        "type": rpt.get("type", ""),
                        "rpt_id": rpt.get("rpt_id", ""),
                        "dataset": rpt.get("dataset", ""),
                        "trgops": rpt.get("trg_ops", rpt.get("trgops", "")),
                        "intgpd": rpt.get("intg_pd", rpt.get("intgpd", "")),
                        "buftm": rpt.get("buf_time", rpt.get("buftm", "")),
                        "optflds": rpt.get("opt_flds", rpt.get("optflds", ""))
                    })
                return formatted
            except Exception as e:
                logger.error(f"Could not get reports from protocol: {e}", exc_info=True)
        else:
            logger.debug(f"Protocol adapter not available or missing method. Protocol: {self.protocol}")
        return []
    
    def _get_goose_from_protocol(self) -> list:
        """Get GOOSE directly from protocol adapter."""
        if self.protocol and hasattr(self.protocol, 'get_goose_info'):
            try:
                logger.info("Getting GOOSE from protocol adapter...")
                goose_list = self.protocol.get_goose_info()
                logger.info(f"Protocol adapter returned {len(goose_list)} GOOSE CBs")
                # Convert to format expected by UI
                formatted = []
                for gse in goose_list:
                    formatted.append({
                        "name": gse.get("name", ""),
                        "goid": gse.get("go_id", gse.get("goid", "")),
                        "dataset": gse.get("dataset", ""),
                        "appid": gse.get("app_id", gse.get("appid", "")),
                        "confrev": gse.get("conf_rev", gse.get("confrev", "")),
                        "mintime": gse.get("min_time", gse.get("mintime", "")),
                        "maxtime": gse.get("max_time", gse.get("maxtime", "")),
                        "signal_count": 0  # Will be populated if dataset info available
                    })
                return formatted
            except Exception as e:
                logger.error(f"Could not get GOOSE from protocol: {e}", exc_info=True)
        else:
            logger.debug(f"Protocol adapter not available or missing method. Protocol: {self.protocol}")
        return []
    
    def _find_reports_recursive(self, node, reports: list):
        """Recursively find Report nodes."""
        if hasattr(node, 'name') and node.name == "Reports":
            # This is a reports container
            if hasattr(node, 'children'):
                for rpt_node in node.children:
                    rpt_info = {
                        "name": rpt_node.name,
                        "type": "",
                        "rpt_id": "",
                        "dataset": "",
                        "trgops": "",
                        "intgpd": "",
                        "buftm": "",
                        "optflds": ""
                    }
                    
                    # Extract type from description
                    if hasattr(rpt_node, 'description'):
                        if "URCB" in rpt_node.description:
                            rpt_info["type"] = "URCB"
                        elif "BRCB" in rpt_node.description:
                            rpt_info["type"] = "BRCB"
                    
                    # Extract attributes
                    if hasattr(rpt_node, 'children'):
                        for child in rpt_node.children:
                            if hasattr(child, 'name') and hasattr(child, 'signals') and child.signals:
                                value = str(child.signals[0].value) if child.signals else ""
                                
                                if child.name == "RptID":
                                    rpt_info["rpt_id"] = value
                                elif child.name == "DatSet":
                                    rpt_info["dataset"] = value
                                elif child.name == "TrgOps":
                                    rpt_info["trgops"] = value
                                elif child.name == "IntgPd":
                                    rpt_info["intgpd"] = value
                                elif child.name == "BufTm":
                                    rpt_info["buftm"] = value
                                elif child.name == "OptFlds":
                                    rpt_info["optflds"] = value
                    
                    reports.append(rpt_info)
        
        # Recurse to children
        if hasattr(node, 'children'):
            for child in node.children:
                self._find_reports_recursive(child, reports)
    
    def _extract_goose_info(self) -> list:
        """Extract GOOSE information from device tree."""
        goose_cbs = []
        
        if not self.device.root_node:
            return goose_cbs
        
        self._find_goose_recursive(self.device.root_node, goose_cbs)
        return goose_cbs
    
    def _find_goose_recursive(self, node, goose_cbs: list):
        """Recursively find GOOSE nodes."""
        if hasattr(node, 'name') and node.name == "GOOSE":
            # This is a GOOSE container
            if hasattr(node, 'children'):
                for gse_node in node.children:
                    gse_info = {
                        "name": gse_node.name,
                        "goid": "",
                        "dataset": "",
                        "appid": "",
                        "confrev": "",
                        "mintime": "",
                        "maxtime": "",
                        "signal_count": 0
                    }
                    
                    # Extract attributes
                    if hasattr(gse_node, 'children'):
                        for child in gse_node.children:
                            if hasattr(child, 'name') and hasattr(child, 'signals') and child.signals:
                                value = str(child.signals[0].value) if child.signals else ""
                                
                                if child.name == "GoID":
                                    gse_info["goid"] = value
                                elif child.name == "DatSet":
                                    gse_info["dataset"] = value
                                elif child.name == "AppID":
                                    gse_info["appid"] = value
                                elif child.name == "ConfRev":
                                    gse_info["confrev"] = value
                                elif child.name == "MinTime":
                                    gse_info["mintime"] = value
                                elif child.name == "MaxTime":
                                    gse_info["maxtime"] = value
                                elif child.name == "DataSetEntries":
                                    if hasattr(child, 'children'):
                                        gse_info["signal_count"] = len(child.children)
                    
                    goose_cbs.append(gse_info)
        
        # Recurse to children
        if hasattr(node, 'children'):
            for child in node.children:
                self._find_goose_recursive(child, goose_cbs)
    
    def _extract_control_info(self) -> list:
        """Extract control object information."""
        controls = []
        
        # Try to get controls from protocol adapter
        if self.protocol and hasattr(self.protocol, 'controls'):
            for ctrl_ref, ctrl_obj in self.protocol.controls.items():
                ctrl_info = {
                    "name": ctrl_ref,
                    "model": str(ctrl_obj.control_model.name) if hasattr(ctrl_obj, 'control_model') else "Unknown",
                    "activation": "SBO" if "SBO" in str(ctrl_obj.control_model) else "Direct",
                    "status": str(ctrl_obj.state.name) if hasattr(ctrl_obj, 'state') else "Unknown"
                }
                controls.append(ctrl_info)
        
        return controls
    
    def _format_datasets_details(self, datasets: list) -> str:
        """Format dataset details as text."""
        if not datasets:
            return "No datasets available."
        
        lines = []
        for ds in datasets:
            lines.append(f"DataSet: {ds['name']}")
            lines.append(f"  Reference: {ds['ref']}")
            lines.append(f"  Entry Count: {ds['entry_count']}")
            
            if ds['entries']:
                lines.append(f"  Entries:")
                for entry in ds['entries'][:10]:  # Limit to first 10
                    lines.append(f"    - {entry}")
                if len(ds['entries']) > 10:
                    lines.append(f"    ... and {len(ds['entries']) - 10} more")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_reports_details(self, reports: list) -> str:
        """Format report details as text."""
        if not reports:
            return "No reports available."
        
        lines = []
        for rpt in reports:
            lines.append(f"Report: {rpt['name']} ({rpt['type']})")
            lines.append(f"  Report ID: {rpt['rpt_id']}")
            lines.append(f"  DataSet: {rpt['dataset']}")
            lines.append(f"  Trigger Options: {rpt['trgops']}")
            lines.append(f"  Integrity Period: {rpt['intgpd']} ms")
            lines.append(f"  Buffer Time: {rpt['buftm']} ms")
            lines.append(f"  Optional Fields: {rpt['optflds']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_goose_details(self, goose_cbs: list) -> str:
        """Format GOOSE details as text."""
        if not goose_cbs:
            return "No GOOSE control blocks available."
        
        lines = []
        for gse in goose_cbs:
            lines.append(f"GOOSE CB: {gse['name']}")
            lines.append(f"  GoID: {gse['goid']}")
            lines.append(f"  DataSet: {gse['dataset']}")
            lines.append(f"  AppID: {gse['appid']}")
            lines.append(f"  ConfRev: {gse['confrev']}")
            lines.append(f"  MinTime: {gse['mintime']} ms")
            lines.append(f"  MaxTime: {gse['maxtime']} ms")
            lines.append(f"  Signal Count: {gse['signal_count']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_goose_subscribers(self, goose_cbs: list) -> str:
        """Format GOOSE subscriber information."""
        # This would require parsing SCD file for GSE control blocks
        # For now, return placeholder
        
        lines = []
        lines.append("GOOSE Subscriber Information:")
        lines.append("")
        lines.append("Note: Subscriber information is typically configured in the SCD file.")
        lines.append("To view subscriber details:")
        lines.append("  1. Check the IED configuration file (.scd/.icd)")
        lines.append("  2. Look for <GSEControl> elements with subscriber references")
        lines.append("  3. Check the Communication section for multicast addresses")
        lines.append("")
        
        if self.device.config.scd_file_path:
            lines.append(f"SCD File: {self.device.config.scd_file_path}")
        else:
            lines.append("No SCD file configured for this device.")
        
        return "\n".join(lines)
    
    def _populate_data(self):
        """Populate initial data (can be extended for live updates)."""
        pass
