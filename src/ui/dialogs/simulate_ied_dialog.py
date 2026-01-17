from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QPushButton, QDialogButtonBox, QGroupBox, QFormLayout,
    QFileDialog
)
from PySide6.QtCore import Qt
from src.models.device_models import DeviceConfig, DeviceType


class SimulateIEDDialog(QDialog):
    """
    Dialog to configure simulation parameters for an already imported IED.
    Allows converting a client IED connection to a server simulator.
    """
    
    def __init__(self, device_config: DeviceConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Simulate IED: {device_config.name}")
        self.resize(500, 250)
        
        self.original_config = device_config
        self.layout = QVBoxLayout(self)
        
        # Info Label
        info_label = QLabel(
            f"<b>Convert {device_config.name} to IEC 61850 Server Simulator</b><br>"
            "This will create a simulated IED that other clients can connect to."
        )
        info_label.setWordWrap(True)
        self.layout.addWidget(info_label)
        
        # Configuration Group
        config_group = QGroupBox("Server Configuration")
        config_layout = QFormLayout()
        
        # IED Name (read-only)
        self.txt_ied_name = QLineEdit(device_config.name)
        self.txt_ied_name.setReadOnly(True)
        config_layout.addRow("IED Name:", self.txt_ied_name)

        # Simulator Name (editable to avoid conflicts)
        default_sim_name = f"{device_config.name}_sim"
        self.txt_sim_name = QLineEdit(default_sim_name)
        self.txt_sim_name.setPlaceholderText(default_sim_name)
        config_layout.addRow("Simulator Name:", self.txt_sim_name)
        
        # IP Address (default to 0.0.0.0 for network accessibility)
        self.txt_ip = QLineEdit("0.0.0.0")  # Listen on all interfaces by default
        self.txt_ip.setPlaceholderText("0.0.0.0 (all interfaces)")
        self.txt_ip.setToolTip(
            "0.0.0.0 = Listen on all network interfaces (recommended)\n"
            "127.0.0.1 = Localhost only (not accessible from network)\n"
            "Specific IP = Bind to that interface only"
        )
        config_layout.addRow("Listen IP:", self.txt_ip)
        
        # Port
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(device_config.port or 102)
        config_layout.addRow("Listen Port:", self.spin_port)
        
        # SCD/ICD File Path
        scd_path = device_config.scd_file_path
        self.txt_scd = QLineEdit(scd_path or "")
        self.txt_scd.setPlaceholderText("Select SCD/ICD file")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_scd)

        scd_row = QHBoxLayout()
        scd_row.addWidget(self.txt_scd)
        scd_row.addWidget(browse_btn)
        config_layout.addRow("SCD/ICD File:", scd_row)
        
        config_group.setLayout(config_layout)
        self.layout.addWidget(config_group)
        
        # Note
        note_label = QLabel(
            "<i>Note: The simulator will use the IED model from the SCD/ICD file. "
            "Using 0.0.0.0 makes the server accessible from any network interface. "
            "Clients can connect using any of your machine's IP addresses with the specified port.</i>"
        )
        note_label.setWordWrap(True)
        note_label.setProperty("class", "note")
        self.layout.addWidget(note_label)
        
        # Buttons
        self.layout.addStretch()
        button_layout = QHBoxLayout()
        
        self.btn_check_ip = QPushButton("Check/Configure IP")
        self.btn_check_ip.clicked.connect(self._check_ip)
        button_layout.addWidget(self.btn_check_ip)
        
        button_layout.addStretch()
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        button_layout.addWidget(self.buttons)
        
        self.layout.addLayout(button_layout)
    
    def _check_ip(self):
        """Check if IP is configured and offer to configure it"""
        from src.utils.network_utils import NetworkUtils
        from src.ui.dialogs.ip_config_dialog import IPConfigDialog
        
        ip = self.txt_ip.text().strip()
        if not ip or not NetworkUtils.validate_ip_address(ip):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid IP", "Please enter a valid IP address")
            return
        
        # Check if IP is configured locally
        interfaces = NetworkUtils.get_network_interfaces()
        local_ips = {iface.ip_address for iface in interfaces}
        
        if ip in local_ips:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "IP Available",
                f"IP address {ip} is already configured on a local interface."
            )
        else:
            # Offer to configure it
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "IP Not Configured",
                f"IP address {ip} is not configured on any local interface.\n\n"
                "Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                dlg = IPConfigDialog(ip, self)
                dlg.exec()

    def _browse_scd(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SCD/ICD File",
            "",
            "SCL Files (*.scd *.icd *.cid *.xml)"
        )
        if file_path:
            self.txt_scd.setText(file_path)
    
    def get_simulator_config(self) -> DeviceConfig:
        """
        Create a new DeviceConfig for the simulator based on the original.
        """
        sim_name = self.txt_sim_name.text().strip() or f"{self.original_config.name}_sim"
        return DeviceConfig(
            name=sim_name,
            description=f"Simulator: {self.original_config.description}" if self.original_config.description else "IEC 61850 Simulator",
            ip_address=self.txt_ip.text().strip() or "0.0.0.0",  # Default to all interfaces
            port=self.spin_port.value(),
            device_type=DeviceType.IEC61850_SERVER,  # Convert to server
            scd_file_path=self.txt_scd.text().strip() or None,
            protocol_params={"ied_name": self.original_config.name}
        )
