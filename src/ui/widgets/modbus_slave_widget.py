"""
Widget for controlling Modbus Slave/Server
Allows starting/stopping server and managing virtual registers
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                                QPushButton, QLabel, QSpinBox, QLineEdit,
                                QTableWidget, QTableWidgetItem, QHeaderView,
                                QComboBox, QCheckBox, QFormLayout, QTabWidget,
                                QFileDialog, QMessageBox, QTextEdit)
from PySide6.QtCore import Qt, QTimer, Signal as QtSignal
from PySide6.QtGui import QColor
import logging
from src.models.device_models import ModbusDataType, ModbusEndianness, ModbusSignalMapping

logger = logging.getLogger(__name__)


class ModbusSlaveWidget(QWidget):
    """
    Widget for Modbus Slave/Server control and monitoring
    """
    
    server_stopped = QtSignal()
    server_started = QtSignal() # New signal
    config_updated = QtSignal()  # Emitted when mappings or config change
    
    def __init__(self, event_logger=None, parent=None, device_config=None, server_adapter=None):
        super().__init__(parent)
        self.event_logger = event_logger
        self.device_config = device_config
        self.server_adapter = server_adapter
        
        # Use existing server if provided
        if self.server_adapter and self.server_adapter.server:
            self.server = self.server_adapter.server
        else:
            self.server = None
            
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        
        self._setup_ui()
        
        # Load initial data if server is already running
        if self.server and self.server.running:
            self._load_registers()
            self._load_mappings()
            self._update_display()
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.lbl_status.setText(f"Server: Running on port {self.server.config.port}")
            self.lbl_status.setStyleSheet("font-weight: bold; color: green; padding: 5px;")
            self.update_timer.start(1000)
    
    def _setup_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        
        # Server control group
        control_group = QGroupBox("Server Control")
        control_layout = QVBoxLayout(control_group)
        
        # Configuration
        config_form = QFormLayout()
        
        ip_default = "0.0.0.0"
        port_default = 5020
        
        if self.device_config:
             ip_default = self.device_config.ip_address
             port_default = self.device_config.port

        self.txt_listen_address = QLineEdit(ip_default)
        self.txt_listen_address.setToolTip("0.0.0.0 = listen on all interfaces")
        config_form.addRow("Listen Address:", self.txt_listen_address)
        
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(port_default)
        self.spin_port.setToolTip("Use non-standard port to avoid conflicts with real devices")
        config_form.addRow("Port:", self.spin_port)
        
        self.spin_unit_id = QSpinBox()
        self.spin_unit_id.setRange(1, 255)
        self.spin_unit_id.setValue(1)
        if self.device_config:
            self.spin_unit_id.setValue(self.device_config.modbus_unit_id)
        config_form.addRow("Slave ID (Unit ID):", self.spin_unit_id)
        
        control_layout.addLayout(config_form)
        
        # Start/Stop buttons
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("Start Server")
        self.btn_start.clicked.connect(self._start_server)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("Stop Server")
        self.btn_stop.clicked.connect(self._stop_server)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        btn_layout.addWidget(self.btn_stop)
        
        control_layout.addLayout(btn_layout)
        
        # Status display
        self.lbl_status = QLabel("Server: Stopped")
        self.lbl_status.setStyleSheet("font-weight: bold; color: red; padding: 5px;")
        control_layout.addWidget(self.lbl_status)
        
        layout.addWidget(control_group)
        
        # Tabs for different views
        self.tabs = QTabWidget()
        
        # Memory Layout Tab (New)
        self.tabs.addTab(self._create_memory_layout_panel(), "Memory Layout")

        # Register editor tab
        self.tabs.addTab(self._create_register_editor(), "Register Editor")
        
        # Simulation tab
        self.tabs.addTab(self._create_simulation_panel(), "Simulation")
        
        # Value mapping tab
        self.tabs.addTab(self._create_mapping_panel(), "Value Mapping")
        
        # Statistics tab
        self.tabs.addTab(self._create_statistics_panel(), "Statistics")
        
        layout.addWidget(self.tabs)
    
    def _create_memory_layout_panel(self) -> QWidget:
        """Create memory layout configuration panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        btn_add = QPushButton("Add Block")
        btn_add.clicked.connect(self._add_register_block)
        toolbar.addWidget(btn_add)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Table
        self.table_blocks = QTableWidget()
        self.table_blocks.setColumnCount(5)
        self.table_blocks.setHorizontalHeaderLabels(["Name", "Type", "Start Address", "Count", "Actions"])
        self.table_blocks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_blocks.setAlternatingRowColors(True)
        # Connect item changed for editing
        self.table_blocks.itemChanged.connect(self._on_block_changed)
        
        layout.addWidget(self.table_blocks)
        
        # Load initial blocks if available
        self._load_blocks()
        
        return widget

    def _load_blocks(self):
        """Load register blocks into table"""
        if not self.device_config:
            return
            
        self.table_blocks.blockSignals(True)
        self.table_blocks.setRowCount(0)
        
        for i, block in enumerate(self.device_config.modbus_slave_blocks):
            row = self.table_blocks.rowCount()
            self.table_blocks.insertRow(row)
            
            # Name
            self.table_blocks.setItem(row, 0, QTableWidgetItem(block.name))
            
            # Type (ComboBox would be better but QTableWidgetItem for now)
            # Actually let's use ComboBox for Type
            combo_type = QComboBox()
            combo_type.addItems(["holding", "input", "coils", "discrete"])
            combo_type.setCurrentText(block.register_type)
            combo_type.currentTextChanged.connect(lambda t, r=row: self._update_block_type(r, t))
            self.table_blocks.setCellWidget(row, 1, combo_type)

            # Start Address
            self.table_blocks.setItem(row, 2, QTableWidgetItem(str(block.start_address)))
            
            # Count
            self.table_blocks.setItem(row, 3, QTableWidgetItem(str(block.count)))
            
            # Actions
            btn_del = QPushButton("Delete")
            btn_del.clicked.connect(lambda checked=False, idx=i: self._delete_block(idx))
            self.table_blocks.setCellWidget(row, 4, btn_del)
            
        self.table_blocks.blockSignals(False)

    def _add_register_block(self):
        """Add a new register block"""
        if not self.device_config:
            return
            
        from src.models.device_models import SlaveRegisterBlock
        
        # Default new block
        new_block = SlaveRegisterBlock(
            name=f"Block {len(self.device_config.modbus_slave_blocks) + 1}",
            register_type="holding",
            start_address=0,
            count=100
        )
        
        self.device_config.modbus_slave_blocks.append(new_block)
        self._load_blocks()
        self.config_updated.emit() # Persist

    def _delete_block(self, index):
        """Delete a register block"""
        if not self.device_config or index >= len(self.device_config.modbus_slave_blocks):
            return
            
        del self.device_config.modbus_slave_blocks[index]
        self._load_blocks()
        self.config_updated.emit()

    def _update_block_type(self, row, new_type):
        """Update block type from combobox"""
        if not self.device_config: 
            return
        self.device_config.modbus_slave_blocks[row].register_type = new_type
        self.config_updated.emit()

    def _on_block_changed(self, item):
        """Handle block table edits"""
        if not self.device_config:
            return
            
        row = item.row()
        col = item.column()
        
        # If row is out of range of blocks list, ignore (race condition during reload)
        if row >= len(self.device_config.modbus_slave_blocks):
            return

        block = self.device_config.modbus_slave_blocks[row]
        
        try:
            if col == 0: # Name
                block.name = item.text()
            elif col == 2: # Start Address
                block.start_address = int(item.text())
            elif col == 3: # Count
                block.count = int(item.text())
            
            self.config_updated.emit()
            
        except ValueError:
            # Revert on invalid input
            self._load_blocks()
    
    def _create_register_editor(self) -> QWidget:
        """Create register editing interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.combo_register_type = QComboBox()
        self.combo_register_type.addItems([
            "Holding Registers",
            "Input Registers",
            "Coils",
            "Discrete Inputs"
        ])
        self.combo_register_type.currentTextChanged.connect(self._load_registers)
        toolbar.addWidget(QLabel("Type:"))
        toolbar.addWidget(self.combo_register_type)
        
        toolbar.addStretch()
        
        btn_import = QPushButton("Import CSV...")
        btn_import.clicked.connect(self._import_registers)
        toolbar.addWidget(btn_import)
        
        btn_export = QPushButton("Export CSV...")
        btn_export.clicked.connect(self._export_registers)
        toolbar.addWidget(btn_export)
        
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._clear_registers)
        toolbar.addWidget(btn_clear)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table_registers = QTableWidget()
        self.table_registers.setColumnCount(3)
        self.table_registers.setHorizontalHeaderLabels(["Address", "Value", "Hex"])
        self.table_registers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_registers.setAlternatingRowColors(True)
        self.table_registers.itemChanged.connect(self._on_register_changed)
        
        layout.addWidget(self.table_registers)
        
        # Quick write
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Quick Write:"))
        
        self.spin_address = QSpinBox()
        self.spin_address.setRange(0, 9999)
        self.spin_address.setPrefix("Addr: ")
        quick_layout.addWidget(self.spin_address)
        
        self.spin_value = QSpinBox()
        self.spin_value.setRange(0, 65535)
        self.spin_value.setPrefix("Value: ")
        quick_layout.addWidget(self.spin_value)
        
        btn_write = QPushButton("Write")
        btn_write.clicked.connect(self._quick_write)
        quick_layout.addWidget(btn_write)
        
        quick_layout.addStretch()
        
        layout.addLayout(quick_layout)
        
        return widget

    def _create_mapping_panel(self) -> QWidget:
        """Create structured value mapping interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add mapping toolbar
        add_layout = QHBoxLayout()
        
        self.spin_map_addr = QSpinBox()
        self.spin_map_addr.setRange(0, 65535)
        self.spin_map_addr.setPrefix("Addr: ")
        add_layout.addWidget(self.spin_map_addr)
        
        self.combo_map_type = QComboBox()
        for dtype in ModbusDataType:
            self.combo_map_type.addItem(dtype.value, dtype)
        add_layout.addWidget(self.combo_map_type)
        
        self.combo_map_endian = QComboBox()
        for end in ModbusEndianness:
            self.combo_map_endian.addItem(end.value, end)
        add_layout.addWidget(self.combo_map_endian)
        
        btn_add_map = QPushButton("Add Mapping")
        btn_add_map.clicked.connect(self._add_mapping)
        add_layout.addWidget(btn_add_map)
        
        layout.addLayout(add_layout)
        
        # Mapping table
        self.table_mappings = QTableWidget()
        self.table_mappings.setColumnCount(7)
        self.table_mappings.setHorizontalHeaderLabels([
            "Address", "Name", "Type", "Endianness", "Scale", "Value", "Actions"
        ])
        self.table_mappings.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_mappings.itemChanged.connect(self._on_mapping_item_changed)
        
        layout.addWidget(self.table_mappings)
        
        return widget
    
    def _add_mapping(self):
        """Add a new signal mapping to the server"""
        if not self.server:
            QMessageBox.warning(self, "Error", "Server must be initialized (Add device or start server)")
            return
            
        addr = self.spin_map_addr.value()
        dtype = self.combo_map_type.currentData()
        endian = self.combo_map_endian.currentData()
        
        # Create mapping
        name = f"Point_{addr}"
        mapping = ModbusSignalMapping(address=addr, name=name, data_type=dtype, endianness=endian)
        
        # Add to server
        self.server.mappings[addr] = mapping
        
        # Refresh table
        self._load_mappings()
        self._sync_config()
        
    def _sync_config(self):
        """Sync server mappings back to device config for persistence"""
        if self.device_config and self.server:
            self.device_config.modbus_slave_mappings = list(self.server.mappings.values())
            self.config_updated.emit()
        
    def _load_mappings(self):
        """Load mappings from server into table"""
        if not self.server:
            return
            
        self.table_mappings.blockSignals(True)
        self.table_mappings.setRowCount(0)
        
        for addr, mapping in sorted(self.server.mappings.items()):
            row = self.table_mappings.rowCount()
            self.table_mappings.insertRow(row)
            
            # Address (ReadOnly)
            addr_item = QTableWidgetItem(str(addr))
            addr_item.setFlags(addr_item.flags() & ~Qt.ItemIsEditable)
            self.table_mappings.setItem(row, 0, addr_item)
            
            # Name
            self.table_mappings.setItem(row, 1, QTableWidgetItem(mapping.name))
            
            # Type (ReadOnly for now in table, maybe use cell widget later)
            type_item = QTableWidgetItem(mapping.data_type.value)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.table_mappings.setItem(row, 2, type_item)
            
            # Endianness (ReadOnly)
            end_item = QTableWidgetItem(mapping.endianness.value)
            end_item.setFlags(end_item.flags() & ~Qt.ItemIsEditable)
            self.table_mappings.setItem(row, 3, end_item)
            
            # Scale
            self.table_mappings.setItem(row, 4, QTableWidgetItem(str(mapping.scale)))
            
            # Value
            val = self.server.get_mapped_value(addr)
            val_str = str(val if val is not None else "Error")
            self.table_mappings.setItem(row, 5, QTableWidgetItem(val_str))
            
            # Actions
            btn_del = QPushButton("Delete")
            btn_del.clicked.connect(lambda checked=False, a=addr: self._delete_mapping(a))
            self.table_mappings.setCellWidget(row, 6, btn_del)
            
        self.table_mappings.blockSignals(False)
        
    def _delete_mapping(self, address):
        if self.server and address in self.server.mappings:
            del self.server.mappings[address]
            self._load_mappings()
            self._sync_config()
            
    def _on_mapping_item_changed(self, item):
        """Handle editing individual fields in the mapping table"""
        if not self.server:
            return
            
        row = item.row()
        col = item.column()
        
        try:
            addr = int(self.table_mappings.item(row, 0).text())
            mapping = self.server.mappings.get(addr)
            if not mapping:
                return
                
            if col == 1: # Name
                mapping.name = item.text()
                self._sync_config()
            elif col == 4: # Scale
                mapping.scale = float(item.text())
                self._sync_config()
            elif col == 5: # Value
                try:
                    val = item.text()
                    # Handle boolean strings
                    if mapping.data_type in [ModbusDataType.BOOL, ModbusDataType.BIT]:
                        val = val.lower() in ['true', '1', 't', 'y', 'yes']
                    else:
                        val = float(val) if '.' in val else int(val)
                        
                    self.server.write_mapped_value(addr, val)
                    # Refresh because scale might affect it or multi-registers might change
                    QTimer.singleShot(100, self._load_mappings)
                    QTimer.singleShot(100, self._load_registers) # Raw sync
                except Exception as e:
                    logger.error(f"Value update error: {e}")
                    
        except Exception as e:
            logger.error(f"Mapping edit error: {row}:{col} - {e}")
    
    def _create_simulation_panel(self) -> QWidget:
        """Create simulation controls"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        sim_group = QGroupBox("Automatic Sensor Simulation")
        sim_layout = QVBoxLayout(sim_group)
        
        self.chk_simulate = QCheckBox("Enable sensor simulation")
        self.chk_simulate.setToolTip(
            "Automatically update input registers with random sensor data"
        )
        self.chk_simulate.stateChanged.connect(self._toggle_simulation)
        sim_layout.addWidget(self.chk_simulate)
        
        info = QLabel(
            "When enabled, the following will be simulated:\n"
            "• Input Register 0: Temperature sensor (20.0-30.0°C)\n"
            "• Input Register 1: Pressure sensor (1000-1100)\n"
            "• Discrete Inputs 0-7: Random state changes"
        )
        info.setWordWrap(True)
        sim_layout.addWidget(info)
        
        layout.addWidget(sim_group)
        
        # Custom patterns
        pattern_group = QGroupBox("Custom Patterns")
        pattern_layout = QVBoxLayout(pattern_group)
        
        btn_ramp = QPushButton("Generate Ramp (Registers 0-99)")
        btn_ramp.clicked.connect(lambda: self._generate_pattern("ramp"))
        pattern_layout.addWidget(btn_ramp)
        
        btn_sine = QPushButton("Generate Sine Wave (Registers 0-99)")
        btn_sine.clicked.connect(lambda: self._generate_pattern("sine"))
        pattern_layout.addWidget(btn_sine)
        
        btn_random = QPushButton("Randomize All Registers")
        btn_random.clicked.connect(lambda: self._generate_pattern("random"))
        pattern_layout.addWidget(btn_random)
        
        layout.addWidget(pattern_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_statistics_panel(self) -> QWidget:
        """Create statistics display"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.txt_stats = QTextEdit()
        self.txt_stats.setReadOnly(True)
        self.txt_stats.setStyleSheet("font-family: monospace;")
        
        layout.addWidget(self.txt_stats)
        
        btn_refresh = QPushButton("Refresh Statistics")
        btn_refresh.clicked.connect(self._update_statistics)
        layout.addWidget(btn_refresh)
        
        return widget
    
    def _start_server(self):
        """Start the Modbus slave server"""
        try:
            from src.protocols.modbus.slave_server import ModbusSlaveServer, ModbusSlaveConfig
            
            # Use adapter if available
            if self.server_adapter:
                # Update adapter's internal config from UI fields before connecting
                self.server_adapter.config.ip_address = self.txt_listen_address.text()
                try:
                    self.server_adapter.config.port = int(self.spin_port.value())
                except: pass
                
                # Re-initialize server if it hasn't been created yet or config changed
                # Actually server_adapter.__init__ already created one.
                # If we want to change IP/Port on an existing adapter, we may need to recreate the server instance.
                slave_config = ModbusSlaveConfig(
                    listen_address=self.server_adapter.config.ip_address,
                    port=self.server_adapter.config.port,
                    unit_id=self.spin_unit_id.value(),
                    register_blocks=self.device_config.modbus_slave_blocks if self.device_config else []
                )
                self.server_adapter.server = ModbusSlaveServer(slave_config, self.event_logger)

                if self.server_adapter.connect():
                    self.server = self.server_adapter.server
                else:
                    raise Exception("Adapter failed to start server")
            else:
                # Standalone mode
                config = ModbusSlaveConfig(
                    listen_address=self.txt_listen_address.text(),
                    port=self.spin_port.value(),
                    unit_id=self.spin_unit_id.value(),
                    register_blocks=self.device_config.modbus_slave_blocks if self.device_config else []
                )
                
                self.server = ModbusSlaveServer(config, self.event_logger)
                if not self.server.start():
                    raise Exception("Failed to start server")
            
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            port = self.spin_port.value()
            self.lbl_status.setText(f"Server: Running on port {port}")
            self.lbl_status.setStyleSheet("font-weight: bold; color: green; padding: 5px;")
            
            # Start update timer
            self.update_timer.start(1000)
            
            # Load initial registers
            self._load_registers()
            self._load_mappings()
            
            self.server_started.emit()
            
            if not self.server_adapter: # Only show message in standalone
                QMessageBox.information(
                    self,
                    "Server Started",
                    f"Modbus slave server is now running.\nPort: {port}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server:\n{e}")
            logger.error(f"Server start error: {e}")
    
    def _stop_server(self):
        """Stop the Modbus slave server"""
        if self.server_adapter:
            self.server_adapter.disconnect()
        elif self.server:
            self.server.stop()
            
        self.update_timer.stop()
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Server: Stopped")
        self.lbl_status.setStyleSheet("font-weight: bold; color: red; padding: 5px;")
        
        self.server_stopped.emit()
    
    def _load_registers(self):
        """Load current register values into table"""
        if not self.server:
            return
        
        reg_type_map = {
            "Holding Registers": "holding",
            "Input Registers": "input",
            "Coils": "coils",
            "Discrete Inputs": "discrete"
        }
        
        reg_type = reg_type_map[self.combo_register_type.currentText()]
        data = self.server.get_all_registers(reg_type)
        
        # Block signals to avoid triggering itemChanged
        self.table_registers.blockSignals(True)
        
        self.table_registers.setRowCount(0)
        
        # Show registers from configured blocks
        if self.device_config and self.device_config.modbus_slave_blocks:
            # Filter blocks by type
            matching_blocks = [b for b in self.device_config.modbus_slave_blocks if b.register_type == reg_type]
            
            for block in matching_blocks:
                # Add a header row or just list them? Listing is simpler for now.
                for i in range(block.count):
                    addr = block.start_address + i
                    value = data.get(addr, 0)
                    
                    row = self.table_registers.rowCount()
                    self.table_registers.insertRow(row)
                    
                    # Address
                    addr_item = QTableWidgetItem(str(addr))
                    addr_item.setFlags(addr_item.flags() & ~Qt.ItemIsEditable)
                    self.table_registers.setItem(row, 0, addr_item)
                    
                    # Value
                    value_item = QTableWidgetItem(str(value))
                    self.table_registers.setItem(row, 1, value_item)
                    
                    # Hex
                    hex_item = QTableWidgetItem(f"0x{value:04X}")
                    hex_item.setFlags(hex_item.flags() & ~Qt.ItemIsEditable)
                    self.table_registers.setItem(row, 2, hex_item)
        else:
            # Fallback for legacy/default 0-100 if no blocks defined
            for addr in range(100):
                value = data.get(addr, 0)
                
                row = self.table_registers.rowCount()
                self.table_registers.insertRow(row)
                
                # Address
                addr_item = QTableWidgetItem(str(addr))
                addr_item.setFlags(addr_item.flags() & ~Qt.ItemIsEditable)
                self.table_registers.setItem(row, 0, addr_item)
                
                # Value
                value_item = QTableWidgetItem(str(value))
                self.table_registers.setItem(row, 1, value_item)
                
                # Hex
                hex_item = QTableWidgetItem(f"0x{value:04X}")
                hex_item.setFlags(hex_item.flags() & ~Qt.ItemIsEditable)
                self.table_registers.setItem(row, 2, hex_item)
        
        self.table_registers.blockSignals(False)
    
    def _on_register_changed(self, item):
        """Handle register value change in table"""
        if not self.server or item.column() != 1:
            return
        
        try:
            row = item.row()
            address = int(self.table_registers.item(row, 0).text())
            value = int(item.text())
            
            reg_type = self.combo_register_type.currentText()
            
            if reg_type == "Holding Registers":
                self.server.write_register(address, value)
            elif reg_type == "Input Registers":
                self.server.write_input_register(address, value)
            elif reg_type == "Coils":
                self.server.write_coil(address, bool(value))
            elif reg_type == "Discrete Inputs":
                self.server.write_discrete_input(address, bool(value))
            
            # Update hex display
            self.table_registers.item(row, 2).setText(f"0x{value:04X}")
            
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Please enter a valid integer")
            self._load_registers()
    
    def _quick_write(self):
        """Quick write to register"""
        if not self.server:
            QMessageBox.warning(self, "Server Not Running", "Start the server first")
            return
        
        address = self.spin_address.value()
        value = self.spin_value.value()
        
        reg_type = self.combo_register_type.currentText()
        
        if reg_type == "Holding Registers":
            self.server.write_register(address, value)
        elif reg_type == "Input Registers":
            self.server.write_input_register(address, value)
        
        self._load_registers()
    
    def _toggle_simulation(self, state):
        """Enable/disable sensor simulation"""
        if self.server:
            self.server.simulate_sensor_updates(state == Qt.Checked)
    
    def _generate_pattern(self, pattern_type):
        """Generate test patterns in registers"""
        if not self.server:
            return
        
        import math
        import random
        
        values = []
        
        if pattern_type == "ramp":
            values = list(range(100))
        elif pattern_type == "sine":
            values = [int(50 + 49 * math.sin(i * 0.1)) for i in range(100)]
        elif pattern_type == "random":
            values = [random.randint(0, 65535) for _ in range(100)]
        
        self.server.bulk_write_registers(0, values)
        self._load_registers()
    
    def _import_registers(self):
        """Import register values from CSV"""
        fname, _ = QFileDialog.getOpenFileName(self, "Import Registers", "", "CSV Files (*.csv)")
        if not fname or not self.server:
            return
        
        try:
            import csv
            data = {}
            
            with open(fname, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    addr = int(row['address'])
                    value = int(row['value'])
                    data[addr] = value
            
            reg_type_map = {
                "Holding Registers": "holding",
                "Input Registers": "input",
                "Coils": "coils",
                "Discrete Inputs": "discrete"
            }
            
            reg_type = reg_type_map[self.combo_register_type.currentText()]
            self.server.import_register_data(data, reg_type)
            self._load_registers()
            
            QMessageBox.information(self, "Success", f"Imported {len(data)} registers")
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")
    
    def _export_registers(self):
        """Export register values to CSV"""
        fname, _ = QFileDialog.getSaveFileName(self, "Export Registers", "", "CSV Files (*.csv)")
        if not fname or not self.server:
            return
        
        try:
            import csv
            
            reg_type_map = {
                "Holding Registers": "holding",
                "Input Registers": "input",
                "Coils": "coils",
                "Discrete Inputs": "discrete"
            }
            
            reg_type = reg_type_map[self.combo_register_type.currentText()]
            data = self.server.get_all_registers(reg_type)
            
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['address', 'value', 'hex'])
                
                for addr, value in sorted(data.items()):
                    writer.writerow([addr, value, f"0x{value:04X}"])
            
            QMessageBox.information(self, "Success", f"Exported {len(data)} registers")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")
    
    def _clear_registers(self):
        """Clear all registers"""
        if not self.server:
            return
        
        reply = QMessageBox.question(
            self,
            "Clear Registers",
            "Clear all registers to zero?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            zeros = {i: 0 for i in range(1000)}
            
            reg_type_map = {
                "Holding Registers": "holding",
                "Input Registers": "input",
                "Coils": "coils",
                "Discrete Inputs": "discrete"
            }
            
            reg_type = reg_type_map[self.combo_register_type.currentText()]
            self.server.import_register_data(zeros, reg_type)
            self._load_registers()
    
    def _update_display(self):
        """Periodic update of display (when server running)"""
        if self.server and self.server.running:
            # Reload current view if visible
            if self.tabs.currentIndex() == 0:  # Register editor
                current_row = self.table_registers.currentRow()
                self._load_registers()
                if current_row >= 0:
                    self.table_registers.setCurrentCell(current_row, 1)
    
    def _update_statistics(self):
        """Update statistics display"""
        if not self.server:
            self.txt_stats.setText("Server not running")
            return
        
        stats = self.server.get_statistics()
        
        text = "=== Modbus Slave Server Statistics ===\n\n"
        text += f"Status: {'Running' if self.server.running else 'Stopped'}\n"
        text += f"Listen Address: {self.server.config.listen_address}:{self.server.config.port}\n"
        text += f"Uptime: {stats.get('uptime', 'N/A')}\n"
        text += f"\nData Blocks:\n"
        text += f"  Coils: 0-{self.server.config.coils_count-1}\n"
        text += f"  Discrete Inputs: 0-{self.server.config.discrete_inputs_count-1}\n"
        text += f"  Holding Registers: 0-{self.server.config.holding_registers_count-1}\n"
        text += f"  Input Registers: 0-{self.server.config.input_registers_count-1}\n"
        
        self.txt_stats.setText(text)
    
    def closeEvent(self, event):
        """Stop server on widget close"""
        if self.server and self.server.running:
            self._stop_server()
        event.accept()
