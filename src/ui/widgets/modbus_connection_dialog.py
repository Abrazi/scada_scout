from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                                QComboBox, QDialogButtonBox, QMessageBox, QPushButton, 
                                QHBoxLayout, QFileDialog, QListWidget, QLabel, QMenu,
                                QSpinBox, QDoubleSpinBox, QStackedWidget, QWidget, QGroupBox)
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication
import os
import tempfile
import logging
from src.models.device_models import DeviceConfig, DeviceType, ModbusDataType, ModbusEndianness, ModbusRegisterMap
from src.utils.archive_utils import ArchiveExtractor

logger = logging.getLogger(__name__)

class ConnectionDialog(QDialog):
    """
    Enhanced dialog to input connection details for all protocols
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Device")
        self.resize(500, 600)
        
        self.layout = QVBoxLayout(self)
        
        # Common connection parameters
        self.form = QFormLayout()
        
        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("502")  # Default Modbus TCP port
        
        self.type_input = QComboBox()
        self.type_input.addItem(DeviceType.MODBUS_TCP.value, DeviceType.MODBUS_TCP)
        self.type_input.addItem(DeviceType.IEC61850_IED.value, DeviceType.IEC61850_IED)
        self.type_input.addItem(DeviceType.IEC104_RTU.value, DeviceType.IEC104_RTU)
        
        # Update port and show protocol-specific options when type changes
        self.type_input.currentIndexChanged.connect(self._on_type_changed)
        
        self.form.addRow("IP Address:", self.ip_input)
        self.form.addRow("Port:", self.port_input)
        self.form.addRow("Protocol:", self.type_input)
        
        self.layout.addLayout(self.form)
        
        # Protocol-specific settings (stacked widget)
        self.protocol_stack = QStackedWidget()
        
        # Modbus-specific settings
        self.modbus_widget = self._create_modbus_settings()
        self.protocol_stack.addWidget(self.modbus_widget)
        
        # IEC 61850-specific settings
        self.iec61850_widget = self._create_iec61850_settings()
        self.protocol_stack.addWidget(self.iec61850_widget)
        
        # IEC 104-specific settings
        self.iec104_widget = self._create_iec104_settings()
        self.protocol_stack.addWidget(self.iec104_widget)
        
        self.layout.addWidget(self.protocol_stack)
        
        # Recent connections history
        self.layout.addWidget(QLabel("Recent Connections:"))
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(100)
        self.history_list.setToolTip("Double-click to select, Right-click to remove")
        self.history_list.itemDoubleClicked.connect(self._on_history_double_click)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._on_history_context_menu)
        self.layout.addWidget(self.history_list)
        
        self.settings = QSettings("ScadaScout", "ConnectionHistory")
        self._load_history()
        
        # Dialog buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
        # Set initial protocol view
        self._on_type_changed()
    
    def _create_modbus_settings(self) -> QWidget:
        """Create Modbus-specific configuration panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Modbus TCP Settings")
        form = QFormLayout(group)
        
        self.modbus_unit_id = QSpinBox()
        self.modbus_unit_id.setRange(1, 247)
        self.modbus_unit_id.setValue(1)
        form.addRow("Unit ID (Slave):", self.modbus_unit_id)
        
        self.modbus_timeout = QDoubleSpinBox()
        self.modbus_timeout.setRange(0.5, 30.0)
        self.modbus_timeout.setValue(3.0)
        self.modbus_timeout.setSuffix(" s")
        form.addRow("Timeout:", self.modbus_timeout)
        
        layout.addWidget(group)
        
        # Configuration Import/Export
        config_btn_layout = QHBoxLayout()
        self.btn_load_config = QPushButton("Load Config (JSON/CSV)...")
        self.btn_load_config.clicked.connect(self._load_config_file)
        config_btn_layout.addWidget(self.btn_load_config)
        config_btn_layout.addStretch()
        layout.addLayout(config_btn_layout)

        # Register map configuration
        map_group = QGroupBox("Register Mapping (Optional)")
        map_layout = QVBoxLayout(map_group)
        
        btn_layout = QHBoxLayout()
        self.btn_import_map = QPushButton("Import Map (CSV)...")
        self.btn_import_map.clicked.connect(self._import_register_map)
        btn_layout.addWidget(self.btn_import_map)
        
        self.btn_edit_map = QPushButton("Edit Map...")
        self.btn_edit_map.clicked.connect(self._edit_register_map)
        btn_layout.addWidget(self.btn_edit_map)
        
        map_layout.addLayout(btn_layout)
        
        self.lbl_map_status = QLabel("No register map configured (will use default scan)")
        self.lbl_map_status.setWordWrap(True)
        map_layout.addWidget(self.lbl_map_status)
        
        layout.addWidget(map_group)
        layout.addStretch()
        
        self.modbus_register_maps = []
        
        return widget

    def _load_config_file(self):
        """Load configuration from JSON or CSV file."""
        fname, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Configuration", 
            "", 
            "Config Files (*.json *.csv);;JSON Files (*.json);;CSV Files (*.csv)"
        )
        if not fname:
            return
            
        try:
            if fname.lower().endswith('.csv'):
                self._load_csv_config(fname)
            else:
                import json
                with open(fname, 'r') as f:
                    data = json.load(f)
                self._apply_loaded_config(data)
                
            QMessageBox.information(self, "Config Loaded", f"Configuration loaded from {os.path.basename(fname)}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load configuration:\n{e}")

    def _load_csv_config(self, fname):
        """Load register map from CSV and apply to dialog."""
        import csv
        maps = []
        with open(fname, 'r') as f:
            reader = csv.DictReader(f)
            # Check headers to decide if it's a register list or map definition
            fieldnames = reader.fieldnames or []
            
            # Case 1: Register Map Definition (Start, Count, FC...)
            if 'start_address' in fieldnames and 'count' in fieldnames:
                for row in reader:
                     maps.append(ModbusRegisterMap(
                        start_address=int(row['start_address']),
                        count=int(row['count']),
                        function_code=int(row['function_code']),
                        data_type=ModbusDataType[row['data_type']],
                        name_prefix=row.get('name_prefix', ''),
                        description=row.get('description', ''),
                        scale=float(row.get('scale', 1.0)),
                        offset=float(row.get('offset', 0.0)),
                        endianness=ModbusEndianness[row.get('endianness', 'BIG_BIG')]
                    ))
            
            # Case 2: Simple Register List (Address, Name, Type...)
            # We must aggregate these into maps, or create one-to-one maps
            elif 'Address' in fieldnames or 'address' in fieldnames:
                 # Simplified logic: Create single-register maps for each row
                 # Real implementation should try to group contiguous registers
                 addr_col = 'Address' if 'Address' in fieldnames else 'address'
                 name_col = 'Name' if 'Name' in fieldnames else 'name'
                 type_col = 'Type' if 'Type' in fieldnames else 'type'
                 
                 for row in reader:
                     addr = int(row[addr_col])
                     dtype = ModbusDataType.UINT16
                     try:
                         if row.get(type_col):
                             dtype = ModbusDataType[row.get(type_col)]
                     except: pass
                     
                     # Simple heuristic for FC based on address (if 40001 -> FC3, etc is not provided)
                     # Defaulting to Holding Registers (FC3)
                     fc = 3
                     
                     maps.append(ModbusRegisterMap(
                         start_address=addr,
                         count=1, # Todo: handle types size
                         function_code=fc,
                         data_type=dtype,
                         name_prefix=row.get(name_col, f"Reg_{addr}"),
                         description=row.get('Description', '') or row.get('description', '')
                     ))
        
        self.modbus_register_maps = maps
        self.lbl_map_status.setText(f"✓ Loaded {len(maps)} register maps from CSV")

    def _apply_loaded_config(self, data):
        """Apply loaded configuration data to the dialog."""
        # Top-level fields
        if 'ip_address' in data:
            self.ip_input.setText(data['ip_address'])
        if 'port' in data:
            self.port_input.setText(str(data['port']))
        
        # Modbus specific
        if 'modbus_unit_id' in data:
            self.modbus_unit_id.setValue(int(data['modbus_unit_id']))
        if 'modbus_timeout' in data:
            self.modbus_timeout.setValue(float(data['modbus_timeout']))
            
        # Register Maps
        if 'modbus_register_maps' in data:
            maps = []
            for map_data in data['modbus_register_maps']:
                maps.append(ModbusRegisterMap.from_dict(map_data))
            
            self.modbus_register_maps = maps
            self.lbl_map_status.setText(f"✓ Loaded {len(maps)} register map(s) from config")
    
    def _create_iec61850_settings(self) -> QWidget:
        """Create IEC 61850-specific configuration panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("IEC 61850 Settings")
        form = QFormLayout(group)
        
        # SCD File Selection
        scd_layout = QHBoxLayout()
        self.scd_input = QLineEdit()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_scd)
        scd_layout.addWidget(self.scd_input)
        scd_layout.addWidget(self.browse_btn)
        
        form.addRow("SCD File (Optional):", scd_layout)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_iec104_settings(self) -> QWidget:
        """Create IEC 104-specific configuration panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("IEC 60870-5-104 Settings")
        form = QFormLayout(group)
        
        self.iec104_ca = QSpinBox()
        self.iec104_ca.setRange(1, 65535)
        self.iec104_ca.setValue(1)
        form.addRow("Common Address (CA):", self.iec104_ca)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _on_type_changed(self):
        """Handle protocol type change"""
        protocol_type = self.type_input.currentData()
        
        # Set default port
        if protocol_type == DeviceType.MODBUS_TCP:
            self.port_input.setText("502")
            self.protocol_stack.setCurrentIndex(0)
        elif protocol_type == DeviceType.IEC61850_IED:
            self.port_input.setText("102")
            self.protocol_stack.setCurrentIndex(1)
        elif protocol_type == DeviceType.IEC104_RTU:
            self.port_input.setText("2404")
            self.protocol_stack.setCurrentIndex(2)
    
    def _browse_scd(self):
        filter_str = ("All Supported Files (*.scd *.cid *.icd *.xml *.zip *.rar *.sz *.7z *.tar *.tar.gz *.tgz);;"
                     "SCL Files (*.scd *.cid *.icd *.xml);;"
                     "Compressed Archives (*.zip *.rar *.sz *.7z *.tar *.tar.gz *.tgz);;"
                     "All Files (*.*)")
        fname, _ = QFileDialog.getOpenFileName(self, "Open SCD/SCL File or Archive", "", filter_str)
        if fname:
            if ArchiveExtractor.is_archive(fname):
                try:
                    # List files in archive
                    files_in_archive = ArchiveExtractor.list_files(fname)
                    scd_files = [f for f in files_in_archive 
                                if f.lower().endswith(('.scd', '.cid', '.icd', '.xml'))]
                    
                    if not scd_files and files_in_archive:
                        scd_files = files_in_archive
                    
                    if not scd_files:
                        QMessageBox.warning(self, "No SCD File",
                                          "No .scd, .cid, .icd, or .xml file found in the archive.")
                        return
                    
                    # Pick first or let user choose if multiple
                    selected_file = scd_files[0]
                    if len(scd_files) > 1:
                        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
                        # Simple selection dialog
                        dialog = QDialog(self)
                        dialog.setWindowTitle("Select file from archive")
                        dlg_layout = QVBoxLayout(dialog)
                        dlg_layout.addWidget(QLabel("Select file to extract:"))
                        lw = QListWidget()
                        for f in scd_files:
                            lw.addItem(f)
                        lw.setCurrentRow(0)
                        dlg_layout.addWidget(lw)
                        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                        btns.accepted.connect(dialog.accept)
                        btns.rejected.connect(dialog.reject)
                        dlg_layout.addWidget(btns)
                        if dialog.exec() == QDialog.Accepted:
                            selected_file = lw.currentItem().text()
                        else:
                            return
                    
                    # Run extraction in background
                    from PySide6.QtWidgets import QProgressDialog, QApplication
                    from src.core.workers import ExtractWorker
                    temp_dir = tempfile.mkdtemp(prefix="scada_scout_scd_")
                    self.extract_worker = ExtractWorker(fname, selected_file, temp_dir)

                    progress = QProgressDialog(f"Extracting {os.path.basename(selected_file)}...", "Cancel", 0, 100, self)
                    progress.setWindowTitle("Extracting")
                    progress.setWindowModality(Qt.WindowModal)
                    progress.setMinimumDuration(0)
                    progress.setValue(0)

                    def on_progress(msg_text, val):
                        try:
                            progress.setLabelText(msg_text)
                            progress.setValue(max(0, min(100, val)))
                            QApplication.processEvents()
                        except Exception:
                            pass

                    def on_finished(extracted_path, error_msg):
                        progress.close()
                        if error_msg:
                            if error_msg == 'cancelled':
                                QMessageBox.information(self, "Cancelled", "Extraction cancelled by user.")
                                return
                            logger.error(f"Extraction error: {error_msg}")
                            QMessageBox.critical(self, "Extraction Error", f"Failed to extract file:\n{error_msg}")
                            return

                        if os.path.exists(extracted_path):
                            self.scd_input.setText(extracted_path)
                            logger.info(f"Extracted {selected_file} from {fname} to {extracted_path}")
                        else:
                            QMessageBox.warning(self, "Extraction Failed", f"Failed to extract {selected_file} from archive.")

                    self.extract_worker.progress.connect(on_progress)
                    self.extract_worker.finished.connect(on_finished)
                    progress.canceled.connect(lambda: self.extract_worker.cancel())
                    self.extract_worker.start()
                        
                except Exception as e:
                    logger.error(f"Failed to extract archive {fname}: {e}")
                    QMessageBox.critical(self, "Extraction Error", f"Failed to extract archive:\n{str(e)}")
            else:
                self.scd_input.setText(fname)
    
    def _import_register_map(self):
        """Import Modbus register map from CSV"""
        fname, _ = QFileDialog.getOpenFileName(self, "Import Register Map", "", "CSV Files (*.csv)")
        if fname:
            try:
                import csv
                maps = []
                with open(fname, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        reg_map = ModbusRegisterMap(
                            start_address=int(row['start_address']),
                            count=int(row['count']),
                            function_code=int(row['function_code']),
                            data_type=ModbusDataType[row['data_type']],
                            name_prefix=row.get('name_prefix', ''),
                            description=row.get('description', ''),
                            scale=float(row.get('scale', 1.0)),
                            offset=float(row.get('offset', 0.0)),
                            endianness=ModbusEndianness[row.get('endianness', 'BIG_BIG')]
                        )
                        maps.append(reg_map)
                
                self.modbus_register_maps = maps
                self.lbl_map_status.setText(f"✓ Loaded {len(maps)} register map(s)")
                
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import register map:\n{e}")
    
    def _edit_register_map(self):
        """Open register map editor dialog"""
        # TODO: Implement full register map editor
        QMessageBox.information(self, "Register Map Editor", 
                               "Register map editor coming soon!\n\n"
                               "For now, create a CSV with columns:\n"
                               "start_address, count, function_code, data_type, name_prefix, "
                               "description, scale, offset, endianness")
    
    def _load_history(self):
        history = self.settings.value("ip_history", [])
        if not isinstance(history, list):
            history = []
        
        seen = set()
        unique_history = []
        for ip in history:
            if ip not in seen and ip:
                unique_history.append(ip)
                seen.add(ip)
        
        self.history_list.addItems(unique_history)
    
    def _save_history(self):
        items = []
        for i in range(self.history_list.count()):
            items.append(self.history_list.item(i).text())
        self.settings.setValue("ip_history", items)
    
    def _on_accept(self):
        ip = self.ip_input.text().strip()
        if ip:
            items = [self.history_list.item(i).text() for i in range(self.history_list.count())]
            if ip not in items:
                self.history_list.insertItem(0, ip)
            
            if self.history_list.count() > 10:
                self.history_list.takeItem(self.history_list.count() - 1)
            
            self._save_history()
        
        self.accept()
    
    def _on_history_double_click(self, item):
        self.ip_input.setText(item.text())
    
    def _on_history_context_menu(self, position):
        item = self.history_list.itemAt(position)
        if item:
            menu = QMenu()
            remove_action = menu.addAction("Remove from History")
            remove_action.triggered.connect(lambda: self._remove_history_item(item))
            menu.exec(self.history_list.mapToGlobal(position))
    
    def _remove_history_item(self, item):
        row = self.history_list.row(item)
        self.history_list.takeItem(row)
        self._save_history()
    
    def set_config(self, config: DeviceConfig):
        """Pre-fill dialog with existing config"""
        self.ip_input.setText(config.ip_address)
        self.port_input.setText(str(config.port))
        
        # Set protocol type
        index = self.type_input.findData(config.device_type)
        if index >= 0:
            self.type_input.setCurrentIndex(index)
        
        # Protocol-specific settings
        if config.device_type == DeviceType.MODBUS_TCP:
            self.modbus_unit_id.setValue(config.modbus_unit_id)
            self.modbus_timeout.setValue(config.modbus_timeout)
            if config.modbus_register_maps:
                self.modbus_register_maps = config.modbus_register_maps
                self.lbl_map_status.setText(f"✓ {len(config.modbus_register_maps)} register map(s) configured")
        
        elif config.device_type == DeviceType.IEC61850_IED:
            if config.scd_file_path:
                self.scd_input.setText(config.scd_file_path)
        
        self._original_name = config.name
    
    def get_config(self) -> DeviceConfig:
        """Create DeviceConfig from dialog inputs"""
        try:
            port = int(self.port_input.text())
        except ValueError:
            port = 502
        
        name = getattr(self, '_original_name', None)
        if not name:
            name = f"Device_{self.ip_input.text().replace('.', '_')}"
        
        protocol_type = self.type_input.currentData()
        
        config = DeviceConfig(
            name=name,
            ip_address=self.ip_input.text(),
            port=port,
            device_type=protocol_type
        )
        
        # Add protocol-specific parameters
        if protocol_type == DeviceType.MODBUS_TCP:
            config.modbus_unit_id = self.modbus_unit_id.value()
            config.modbus_timeout = self.modbus_timeout.value()
            config.modbus_register_maps = self.modbus_register_maps
        
        elif protocol_type == DeviceType.IEC61850_IED:
            config.scd_file_path = self.scd_input.text() if self.scd_input.text() else None
        
        elif protocol_type == DeviceType.IEC104_RTU:
            config.protocol_params['common_address'] = self.iec104_ca.value()
        
        return config
