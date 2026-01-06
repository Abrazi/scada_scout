from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox, QPushButton, QHBoxLayout, QFileDialog, QListWidget, QLabel, QMenu
from PySide6.QtCore import QSettings, Qt
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
        
        # self.name_input is removed from UI but we keep it internally if needed or auto-gen
        
        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("102") # Default IEC 61850 port
        
        self.type_input = QComboBox()
        self.type_input.addItem(DeviceType.IEC61850_IED.value, DeviceType.IEC61850_IED)
        self.type_input.addItem(DeviceType.IEC104_RTU.value, DeviceType.IEC104_RTU)
        
        # Update default port based on selection
        # Update default port based on selection
        self.type_input.currentIndexChanged.connect(self._on_type_changed)
        
        # SCD File Selection
        self.scd_layout = QHBoxLayout()
        self.scd_input = QLineEdit()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_scd)
        self.scd_layout.addWidget(self.scd_input)
        self.scd_layout.addWidget(self.browse_btn)

        # Name is not asked anymore
        self.form.addRow("IP Address:", self.ip_input)
        self.form.addRow("Port:", self.port_input)
        self.form.addRow("Protocol:", self.type_input)
        self.form.addRow("SCD File (Optional):", self.scd_layout)
        
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
        ip = self.ip_input.text().strip()
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

    def _on_type_changed(self):
        # Auto-set standard ports
        dt = self.type_input.currentData()
        if dt == DeviceType.IEC104_RTU:
            self.port_input.setText("2404")
        else:
            self.port_input.setText("102")

    def _browse_scd(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open SCD/SCL File", "", "SCL Files (*.scd *.cid *.icd *.xml)")
        if fname:
            self.scd_input.setText(fname)

    def set_config(self, config: DeviceConfig):
        """Pre-fills the dialog with existing config."""
        # self.name_input.setText(config.name) # Removed
        self.ip_input.setText(config.ip_address)
        self.port_input.setText(str(config.port))
        if config.scd_file_path:
            self.scd_input.setText(config.scd_file_path)
        
        index = self.type_input.findData(config.device_type)
        if index >= 0:
            self.type_input.setCurrentIndex(index)
            
        # Store original name to preserve it if editing
        self._original_name = config.name

    def get_config(self) -> DeviceConfig:
        try:
            port = int(self.port_input.text())
        except ValueError:
            port = 102
            
        # Generate name if not existing
        name = getattr(self, '_original_name', None)
        if not name:
            name = f"IED_{self.ip_input.text().replace('.', '_')}"
            
        return DeviceConfig(
            name=name,
            ip_address=self.ip_input.text(),
            port=port,
            device_type=self.type_input.currentData(),
            scd_file_path=self.scd_input.text() if self.scd_input.text() else None
        )
