from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                                 QDialogButtonBox, QMessageBox, QPushButton, QHBoxLayout, 
                                 QFileDialog, QListWidget, QLabel, QMenu, QStackedWidget, 
                                 QCheckBox, QDoubleSpinBox, QSpinBox)
from PySide6.QtCore import QSettings, Qt
import psutil
import socket
from src.models.device_models import DeviceConfig, DeviceType

class ConnectionDialog(QDialog):
    """
    Dialog to input connection details (IP, Port, Protocol).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Device")
        self.resize(400, 200)
        
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
        self.ip_input = QLineEdit("127.0.0.1")
        self.ip_select = QComboBox()
        self.ip_select.setEditable(True)
        self._populate_local_ips()
        
        self.ip_container.addWidget(self.ip_input)
        self.ip_container.addWidget(self.ip_select)
        
        self.port_input = QLineEdit("102") # Default IEC 61850 port
        
        self.type_input = QComboBox()
        self.type_input.addItem(DeviceType.IEC61850_IED.value, DeviceType.IEC61850_IED)
        self.type_input.addItem(DeviceType.IEC104_RTU.value, DeviceType.IEC104_RTU)
        self.type_input.addItem(DeviceType.MODBUS_TCP.value, DeviceType.MODBUS_TCP)
        self.type_input.addItem(DeviceType.MODBUS_SERVER.value, DeviceType.MODBUS_SERVER)
        
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
        self.form.addRow("SCD File (Optional):", self.scd_layout)
        self.form.addRow("Polling:", self.poll_layout)
        
        self.layout.addLayout(self.form)
        
        # IP History
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
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
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
        fname, _ = QFileDialog.getOpenFileName(self, "Open SCD/SCL File", "", "SCL Files (*.scd *.cid *.icd *.xml)")
        if fname:
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
        
        self.ip_label.setText(label_ip)
