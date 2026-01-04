from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox, QPushButton, QHBoxLayout, QFileDialog
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
        
        self.name_input = QLineEdit("New_IED")
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

        self.form.addRow("Device Name:", self.name_input)
        self.form.addRow("IP Address:", self.ip_input)
        self.form.addRow("Port:", self.port_input)
        self.form.addRow("Protocol:", self.type_input)
        self.form.addRow("SCD File (Optional):", self.scd_layout)
        
        self.layout.addLayout(self.form)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

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
        self.name_input.setText(config.name)
        self.name_input.setReadOnly(True) # Prevent renaming for now
        self.ip_input.setText(config.ip_address)
        self.port_input.setText(str(config.port))
        if config.scd_file_path:
            self.scd_input.setText(config.scd_file_path)
        
        index = self.type_input.findData(config.device_type)
        if index >= 0:
            self.type_input.setCurrentIndex(index)

    def get_config(self) -> DeviceConfig:
        try:
            port = int(self.port_input.text())
        except ValueError:
            port = 102
            
        return DeviceConfig(
            name=self.name_input.text(),
            ip_address=self.ip_input.text(),
            port=port,
            device_type=self.type_input.currentData(),
            scd_file_path=self.scd_input.text() if self.scd_input.text() else None
        )
