from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                                 QDialogButtonBox, QMessageBox, QPushButton, QHBoxLayout, 
                                 QFileDialog, QListWidget, QLabel, QMenu, QStackedWidget, 
                                 QCheckBox, QDoubleSpinBox, QSpinBox)
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication
import platform
import psutil
import socket
import os
import tempfile
import logging
from src.models.device_models import DeviceConfig, DeviceType
from src.utils.archive_utils import ArchiveExtractor

logger = logging.getLogger(__name__)

class ConnectionDialog(QDialog):
    """
    Dialog to input connection details (IP, Port, Protocol).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔌 Connect to Device")
        # Scale dialog size for Windows DPI and available screen size
        base_width, base_height = 850, 650
        min_width, min_height = 750, 580
        scale = 1.0
        try:
            if platform.system() == "Windows":
                screen = QGuiApplication.primaryScreen()
                if screen:
                    scale = screen.logicalDotsPerInch() / 96.0
        except Exception:
            scale = 1.0

        width = int(base_width * scale)
        height = int(base_height * scale)
        min_w = int(min_width * scale)
        min_h = int(min_height * scale)

        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                width = min(width, int(avail.width() * 0.85))
                height = min(height, int(avail.height() * 0.85))
                min_w = min(min_w, max(700, int(avail.width() * 0.55)))
                min_h = min(min_h, max(520, int(avail.height() * 0.55)))
        except Exception:
            pass

        self.resize(width, height)
        self.setMinimumSize(min_w, min_h)
        
        self.layout = QVBoxLayout(self)
        self.form = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Modbus_RTU_1")
        
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Optional description")
        
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("e.g. Substation A (Optional)")
        
        # IP Input with stacking for switching between text and selection
        self.ip_container = QStackedWidget()
        from PySide6.QtWidgets import QSizePolicy
        self.ip_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ip_input = QLineEdit("127.0.0.1")
        self.ip_select = QComboBox()
        self.ip_select.setEditable(True)
        self.ip_select.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._populate_local_ips()
        
        self.ip_container.addWidget(self.ip_input)
        self.ip_container.addWidget(self.ip_select)
        
        self.port_input = QLineEdit("102") # Default IEC 61850 port
        
        self.type_input = QComboBox()
        self.type_input.addItem(DeviceType.IEC61850_IED.value, DeviceType.IEC61850_IED)
        self.type_input.addItem(DeviceType.IEC104_RTU.value, DeviceType.IEC104_RTU)
        self.type_input.addItem(DeviceType.MODBUS_TCP.value, DeviceType.MODBUS_TCP)
        self.type_input.addItem(DeviceType.MODBUS_SERVER.value, DeviceType.MODBUS_SERVER)
        # OPC (opt-in) — appears in the Connect dialog so users can add OPC UA devices
        from src.models.device_models import DeviceType as _DT
        try:
            self.type_input.addItem(DeviceType.OPC_UA_CLIENT.value, DeviceType.OPC_UA_CLIENT)
            self.type_input.addItem(DeviceType.OPC_UA_SERVER.value, DeviceType.OPC_UA_SERVER)
        except Exception:
            # If DeviceType wasn't updated for some reason, ignore silently
            pass

        # Update default port based on selection
        self.type_input.currentTextChanged.connect(self._on_type_changed)
        self.type_input.currentTextChanged.connect(self._update_form_labels)
        
        
        # SCD File Selection
        self.scd_layout = QHBoxLayout()
        self.scd_input = QLineEdit()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_scd)
        
        self.scd_layout.addWidget(self.scd_input)
        self.scd_layout.addWidget(self.browse_btn)

        # OPC UA Endpoint (optional) — visible when OPC is selected
        self.opc_endpoint_input = QLineEdit()
        self.opc_endpoint_input.setPlaceholderText("opc.tcp://hostname:4840 or opc.tcp://host:port/path")
        self.opc_endpoint_label = QLabel("OPC Endpoint:")
        # hidden by default until OPC is selected
        self.opc_endpoint_input.setVisible(False)
        self.opc_endpoint_label.setVisible(False)
        
        # Modbus Configuration File Selection (matching SCD layout style)
        self.modbus_config_layout = QHBoxLayout()
        self.modbus_config_input = QLineEdit()
        self.modbus_config_input.setPlaceholderText("Select Modbus config file...")
        self.modbus_config_input.setReadOnly(True)
        self.modbus_browse_btn = QPushButton("Browse...")
        self.modbus_browse_btn.clicked.connect(self._load_modbus_config)
        self.modbus_config_layout.addWidget(self.modbus_config_input)
        self.modbus_config_layout.addWidget(self.modbus_browse_btn)

        # Modbus Unit ID (Slave ID)
        self.unit_id_input = QSpinBox()
        self.unit_id_input.setRange(1, 255)
        self.unit_id_input.setValue(1)
        self.unit_id_label = QLabel("Slave ID (Unit ID):")

        # Polling Settings
        self.poll_layout = QHBoxLayout()
        self.chk_polling = QCheckBox("Enable Live Polling")
        self.chk_polling.setChecked(True) # Default to True for now
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 3600.0)
        self.spin_interval.setValue(1.0)
        self.spin_interval.setSuffix(" s")
        self.poll_layout.addWidget(self.chk_polling)
        self.poll_layout.addWidget(QLabel("Interval:"))
        self.poll_layout.addWidget(self.spin_interval)
        self.poll_layout.addStretch()

        # Form Rows
        self.form.addRow("Device Name:", self.name_input)
        self.form.addRow("Description:", self.desc_input)
        self.form.addRow("Folder:", self.folder_input)
        
        # Store label reference to avoid layout.labelForField issues
        self.ip_label = QLabel("IP Address:")
        self.form.addRow(self.ip_label, self.ip_container)
        
        
        self.form.addRow("Port:", self.port_input)
        self.form.addRow("Protocol:", self.type_input)
        self.form.addRow(self.unit_id_label, self.unit_id_input)
        
        # Store label reference for Modbus Config
        self.modbus_config_row_label = QLabel("Modbus Config (Optional):")
        self.form.addRow(self.modbus_config_row_label, self.modbus_config_layout)
        
        self.form.addRow("SCD File (Optional):", self.scd_layout)
        # OPC endpoint row (inserted near SCD since it's protocol-specific)
        self.form.addRow(self.opc_endpoint_label, self.opc_endpoint_input)
        self.form.addRow("Polling:", self.poll_layout)
        
        self.layout.addLayout(self.form)
        
        # IP History
        self.layout.addWidget(QLabel("Recent Connections:"))
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(200)
        self.history_list.setMinimumHeight(100)
        font = self.history_list.font()
        font.setPointSize(10)
        self.history_list.setFont(font)
        self.history_list.setToolTip("Double-click to select, Right-click to remove")
        self.history_list.itemDoubleClicked.connect(self._on_history_double_click)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._on_history_context_menu)
        self.layout.addWidget(self.history_list)
        
        self.settings = QSettings("ScadaScout", "ConnectionHistory")
        self._load_history()
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
        # Internal state
        self.modbus_register_maps = []
        
        # Initialize labels/visibility
        self._update_form_labels(self.type_input.currentText())

    def _load_history(self):
        history = self.settings.value("ip_history", [])
        if not isinstance(history, list):
            history = []
        
        # De-duplicate
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
        # Save current IP to history
        ip = self.ip_select.currentText() if self.ip_select.isVisible() else self.ip_input.text()
        ip = ip.strip()
        if ip:
            # Check if exists to avoid dupes at top
            items = [self.history_list.item(i).text() for i in range(self.history_list.count())]
            if ip in items:
                # Move to top? ignoring for now, just ensure it exists
                pass
            else:
                self.history_list.insertItem(0, ip)
            
            # Limit history size?
            if self.history_list.count() > 10:
                self.history_list.takeItem(self.history_list.count() - 1)
                
            self._save_history()
            
        self.accept()

    def _on_history_double_click(self, item):
        ip = item.text()
        if self.ip_select.isVisible():
            index = self.ip_select.findText(ip)
            if index >= 0:
                self.ip_select.setCurrentIndex(index)
            else:
                self.ip_select.setEditText(ip)
        else:
            self.ip_input.setText(ip)
        
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

    def _populate_local_ips(self):
        """Discovers all local IP addresses."""
        ips = ["0.0.0.0", "127.0.0.1"]
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET: # IPv4
                        if addr.address not in ips:
                            ips.append(addr.address)
        except Exception as e:
            print(f"Error getting local IPs: {e}")
            
        self.ip_select.addItems(ips)

    def _on_type_changed(self):
        # Auto-set standard ports
        dt = self.type_input.currentData()
        if dt == DeviceType.IEC104_RTU:
            self.port_input.setText("2404")
        elif dt == DeviceType.MODBUS_TCP:
            self.port_input.setText("502")
        elif dt == DeviceType.MODBUS_SERVER:
            self.port_input.setText("5020")
        else:
            self.port_input.setText("102")

    def _browse_scd(self):
        # Accept both direct SCD files and compressed archives
        filter_str = ("All Supported Files (*.scd *.cid *.icd *.xml *.zip *.rar *.sz *.7z *.tar *.tar.gz *.tgz);;"
                     "SCL Files (*.scd *.cid *.icd *.xml);;"
                     "Compressed Archives (*.zip *.rar *.sz *.7z *.tar *.tar.gz *.tgz);;"
                     "All Files (*.*)")
        fname, _ = QFileDialog.getOpenFileName(self, "Open SCD/SCL File or Archive", "", filter_str)
        if fname:
            # Check if it's a compressed file
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
                    
                    # If multiple, let user select
                    selected_file = scd_files[0]
                    if len(scd_files) > 1:
                        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
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
                            QMessageBox.information(self, "Success", f"Extracted: {os.path.basename(selected_file)}")
                        else:
                            QMessageBox.warning(self, "Extraction Failed", f"Failed to extract {selected_file} from archive.")

                    self.extract_worker.progress.connect(on_progress)
                    self.extract_worker.finished.connect(on_finished)
                    progress.canceled.connect(lambda: self.extract_worker.cancel())
                    self.extract_worker.start()
                except Exception as e:
                    logger.exception("Error extracting archive")
                    QMessageBox.critical(self, "Extraction Error", f"Failed to extract archive:\n{e}")
                    return
            else:
                # Direct SCD file
                self.scd_input.setText(fname)

    def set_config(self, config: DeviceConfig):
        """Pre-fills the dialog with existing config."""
        self.blockSignals(True)
        self.type_input.blockSignals(True)
        
        index = self.type_input.findData(config.device_type)
        if index >= 0:
            self.type_input.setCurrentIndex(index)
            # Manually update container visibility and labels since signals are blocked
            self._update_form_labels(self.type_input.currentText())
            
        self.name_input.setText(config.name)
        self.desc_input.setText(config.description)
        self.folder_input.setText(config.folder or "")
        
        # Set IP based on widget type
        if config.device_type == DeviceType.MODBUS_SERVER:
            self.ip_container.setCurrentWidget(self.ip_select)
            index = self.ip_select.findText(config.ip_address)
            if index >= 0:
                self.ip_select.setCurrentIndex(index)
            else:
                self.ip_select.setEditText(config.ip_address)
        else:
            self.ip_container.setCurrentWidget(self.ip_input)
            self.ip_input.setText(config.ip_address)
            
        self.port_input.setText(str(config.port))
        if config.scd_file_path:
            self.scd_input.setText(config.scd_file_path)
        # Prefill OPC endpoint if present
        try:
            ep = config.protocol_params.get('endpoint')
            if ep:
                self.opc_endpoint_input.setText(ep)
        except Exception:
            pass            
        self.chk_polling.setChecked(config.polling_enabled)
        self.spin_interval.setValue(config.poll_interval)
        self.unit_id_input.setValue(config.modbus_unit_id)
        
        self.type_input.blockSignals(False)
        self.blockSignals(False)

    def get_config(self) -> DeviceConfig:
        try:
            port = int(self.port_input.text())
        except ValueError:
            port = 102
            
        # Get IP from active widget
        if self.ip_container.currentWidget() == self.ip_select:
            ip = self.ip_select.currentText()
        else:
            ip = self.ip_input.text()
            
        # Get name from input or generate if empty
        name = self.name_input.text().strip()
        if not name:
            name = f"IED_{ip.replace('.', '_')}"
            
        return DeviceConfig(
            name=name,
            description=self.desc_input.text(),
            folder=self.folder_input.text(),
            ip_address=ip,
            port=port,
            device_type=self.type_input.currentData(),
            scd_file_path=self.scd_input.text() if self.scd_input.text() else None,
            polling_enabled=self.chk_polling.isChecked(),
            poll_interval=self.spin_interval.value(),
            modbus_unit_id=self.unit_id_input.value()
        )

    def _update_form_labels(self, type_text):
        """Dynamic label updates based on device type."""
        device_type = self.type_input.currentData()
        label_ip = "IP Address:"
        if device_type == DeviceType.MODBUS_SERVER:
             label_ip = "Listen Interface:"
             self.port_input.setText("5020")
             # Sync values
             current_ip = self.ip_input.text()
             index = self.ip_select.findText(current_ip)
             if index >= 0:
                 self.ip_select.setCurrentIndex(index)
             else:
                 self.ip_select.setEditText(current_ip)
             
             self.ip_container.setCurrentWidget(self.ip_select)
        else:
             # Sync back
             if self.ip_container.currentWidget() == self.ip_select:
                self.ip_input.setText(self.ip_select.currentText())
             
             self.ip_container.setCurrentWidget(self.ip_input)
        
        # Show/Hide Unit ID based on protocol
        is_modbus = device_type in [DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER]
        self.unit_id_input.setVisible(is_modbus)
        self.unit_id_label.setVisible(is_modbus)
        
        # Show/Hide Modbus Config based on protocol
        self.modbus_config_row_label.setVisible(is_modbus)
        self.modbus_config_input.setVisible(is_modbus)
        self.modbus_browse_btn.setVisible(is_modbus)
        
        # Show/Hide SCD File based on protocol
        is_iec61850 = device_type == DeviceType.IEC61850_IED
        self.scd_input.setVisible(is_iec61850)
        self.browse_btn.setVisible(is_iec61850)

        # OPC specific: show endpoint input for client/server modes
        is_opc = device_type in [DeviceType.OPC_UA_CLIENT, DeviceType.OPC_UA_SERVER]
        self.opc_endpoint_input.setVisible(is_opc)
        self.opc_endpoint_label.setVisible(is_opc)

        # When OPC selected, allow endpoint to be primary; keep IP/port editable for convenience
        if is_opc:
            label_ip = "(Optional) IP Address:"
        self.ip_label.setText(label_ip)

    def _load_modbus_config(self):
        """Load Modbus configuration from JSON or CSV."""
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
            
            # Set the file path in the text field
            self.modbus_config_input.setText(fname)
            QMessageBox.information(self, "Config Loaded", f"Configuration loaded from {os.path.basename(fname)}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load configuration:\n{e}")

    def _load_csv_config(self, fname):
        """Load register map from CSV."""
        from src.models.device_models import ModbusRegisterMap, ModbusDataType, ModbusEndianness
        import csv
        maps = []
        try:
            with open(fname, 'r', encoding='utf-8-sig') as f: # Handle BOM
                reader = csv.DictReader(f)
                fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]
                
                # Helper to safely get value from row
                def get_val(row, keys, default=None):
                    for k in keys:
                         if k in row and row[k]: return row[k]
                    return default
    
                for row in reader:
                     # Check for Standard Schema (start_address, count)
                     if 'start_address' in fieldnames:
                         try:
                             dtype_str = get_val(row, ['data_type', 'type'], 'UINT16')
                             try: dtype = ModbusDataType[dtype_str]
                             except: dtype = ModbusDataType.UINT16
                             
                             end_str = get_val(row, ['endianness'], 'BIG_BIG')
                             try: end = ModbusEndianness[end_str]
                             except: end = ModbusEndianness.BIG_BIG
                             
                             maps.append(ModbusRegisterMap(
                                start_address=int(row['start_address']),
                                count=int(row.get('count', 1)),
                                function_code=int(row.get('function_code', 3)),
                                data_type=dtype,
                                name_prefix=row.get('name_prefix', ''),
                                description=row.get('description', ''),
                                scale=float(row.get('scale', 1.0)),
                                offset=float(row.get('offset', 0.0)),
                                endianness=end
                            ))
                         except Exception as e:
                             logger.warning(f"Skipping invalid CSV row: {row} ({e})")
                     
                     # Fallback: Simple Register List (Address, Name)
                     elif 'Address' in fieldnames or 'address' in fieldnames:
                         try:
                             addr = int(get_val(row, ['Address', 'address']))
                             name = get_val(row, ['Name', 'name', 'name_prefix'], f"Reg_{addr}")
                             desc = get_val(row, ['Description', 'description'], '')
                             dtype_str = get_val(row, ['Type', 'type', 'data_type'], 'UINT16')
                             
                             # Try to match ModbusDataType
                             try: dtype = ModbusDataType[dtype_str]
                             except: dtype = ModbusDataType.UINT16
                             
                             maps.append(ModbusRegisterMap(
                                 start_address=addr,
                                 count=1,
                                 function_code=int(get_val(row, ['FunctionCode', 'fc', 'function_code'], 3)),
                                 data_type=dtype,
                                 name_prefix=name,
                                 description=desc,
                                 scale=float(get_val(row, ['Scale', 'scale'], 1.0)),
                                 offset=float(get_val(row, ['Offset', 'offset'], 0.0))
                             ))
                         except Exception:
                             continue
            
            self.modbus_register_maps = maps
            if not maps:
                QMessageBox.warning(self, "Import Warning", "No valid registers found in CSV file.")
                
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to load CSV file:\n{e}")

    def _apply_loaded_config(self, data):
        """Apply loaded dict config."""
        from src.models.device_models import ModbusRegisterMap
        # IP/Port
        if 'ip_address' in data:
            if self.ip_container.currentWidget() == self.ip_select:
                self.ip_select.setEditText(data['ip_address'])
            else:
                self.ip_input.setText(data['ip_address'])
        if 'port' in data:
            self.port_input.setText(str(data['port']))
        if 'name' in data:
            self.name_input.setText(data['name'])
        if 'modbus_unit_id' in data:
            self.unit_id_input.setValue(int(data['modbus_unit_id']))
            
        if 'modbus_register_maps' in data:
            self.modbus_register_maps = [ModbusRegisterMap.from_dict(m) for m in data['modbus_register_maps']]

    def get_config(self) -> DeviceConfig:
        try:
            port = int(self.port_input.text())
        except ValueError:
            port = 102
            
        # Get IP from active widget
        if self.ip_container.currentWidget() == self.ip_select:
            ip = self.ip_select.currentText()
        else:
            ip = self.ip_input.text()
            
        # Get name from input or generate if empty
        name = self.name_input.text().strip()
        if not name:
            name = f"IED_{ip.replace('.', '_')}"
            
        config = DeviceConfig(
            name=name,
            description=self.desc_input.text(),
            folder=self.folder_input.text(),
            ip_address=ip,
            port=port,
            device_type=self.type_input.currentData(),
            scd_file_path=self.scd_input.text() if self.scd_input.text() else None,
            polling_enabled=self.chk_polling.isChecked(),
            poll_interval=self.spin_interval.value(),
            modbus_unit_id=self.unit_id_input.value()
        )
        
        # OPC: include endpoint in protocol_params if provided
        if config.device_type in [DeviceType.OPC_UA_CLIENT, DeviceType.OPC_UA_SERVER]:
            endpoint_text = self.opc_endpoint_input.text().strip()
            if endpoint_text:
                config.protocol_params['endpoint'] = endpoint_text

        # Attach register maps if available and Modbus
        if config.device_type in [DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER] and self.modbus_register_maps:
            config.modbus_register_maps = self.modbus_register_maps
            
        return config
