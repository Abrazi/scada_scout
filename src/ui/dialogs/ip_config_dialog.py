from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
import platform
import subprocess
from src.utils.network_utils import NetworkUtils


class IPConfigDialog(QDialog):
    """
    Dialog to configure IP address on a network interface.
    Provides platform-specific commands to add IP aliases.
    """
    
    def __init__(self, ip_address: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure IP Address")
        self.resize(500, 300)
        self.ip_address = ip_address
        
        self.layout = QVBoxLayout(self)
        
        # Info Label
        info_label = QLabel(f"The IP address <b>{ip_address}</b> is not configured on any local interface.")
        info_label.setWordWrap(True)
        self.layout.addWidget(info_label)
        
        # Interface Selection
        interface_group = QGroupBox("Network Interface")
        interface_layout = QFormLayout()
        
        self.combo_interface = QComboBox()
        self._populate_interfaces()
        interface_layout.addRow("Interface:", self.combo_interface)
        
        self.txt_netmask = QLineEdit("255.255.255.0")
        interface_layout.addRow("Netmask:", self.txt_netmask)
        
        interface_group.setLayout(interface_layout)
        self.layout.addWidget(interface_group)
        
        # Command Preview
        cmd_group = QGroupBox("Command to Execute")
        cmd_layout = QVBoxLayout()
        
        self.lbl_command = QLabel()
        self.lbl_command.setWordWrap(True)
        self.lbl_command.setStyleSheet("font-family: monospace; background-color: #f0f0f0; padding: 10px;")
        cmd_layout.addWidget(self.lbl_command)
        
        cmd_group.setLayout(cmd_layout)
        self.layout.addWidget(cmd_group)
        
        # Update command preview when interface changes
        self.combo_interface.currentIndexChanged.connect(self._update_command_preview)
        self.txt_netmask.textChanged.connect(self._update_command_preview)
        self._update_command_preview()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_copy = QPushButton("Copy Command")
        self.btn_copy.clicked.connect(self._copy_command)
        btn_layout.addWidget(self.btn_copy)
        
        self.btn_execute = QPushButton("Execute (Requires Sudo/Admin)")
        self.btn_execute.clicked.connect(self._execute_command)
        btn_layout.addWidget(self.btn_execute)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        
        self.layout.addLayout(btn_layout)
    
    def _populate_interfaces(self):
        """Populate the interface combo box"""
        interfaces = NetworkUtils.get_network_interfaces()
        
        for iface in interfaces:
            if iface.is_up and iface.ip_address != '127.0.0.1':
                display = f"{iface.name} ({iface.ip_address}/{iface.netmask})"
                self.combo_interface.addItem(display, iface)
        
        if self.combo_interface.count() == 0:
            self.combo_interface.addItem("No network interfaces found", None)
            self.btn_execute.setEnabled(False)
    
    def _update_command_preview(self):
        """Update the command preview based on selected interface"""
        iface_data = self.combo_interface.currentData()
        if not iface_data:
            self.lbl_command.setText("No interface selected")
            return
        
        system = platform.system()
        netmask = self.txt_netmask.text().strip() or "255.255.255.0"
        
        if system == "Linux":
            cmd = f"sudo ip addr add {self.ip_address}/{self._netmask_to_cidr(netmask)} dev {iface_data.name}"
        elif system == "Darwin":  # macOS
            cmd = f"sudo ifconfig {iface_data.name} alias {self.ip_address} netmask {netmask}"
        elif system == "Windows":
            cmd = f"netsh interface ip add address \"{iface_data.name}\" {self.ip_address} {netmask}"
        else:
            cmd = "Unsupported platform"
        
        self.lbl_command.setText(cmd)
        self.current_command = cmd
    
    def _netmask_to_cidr(self, netmask: str) -> int:
        """Convert netmask to CIDR notation"""
        try:
            return sum([bin(int(x)).count('1') for x in netmask.split('.')])
        except:
            return 24
    
    def _copy_command(self):
        """Copy command to clipboard"""
        from PySide6.QtGui import QClipboard
        from PySide6.QtWidgets import QApplication
        
        clipboard = QApplication.clipboard()
        clipboard.setText(self.current_command)
        QMessageBox.information(self, "Copied", "Command copied to clipboard!")
    
    def _execute_command(self):
        """Execute the command"""
        iface_data = self.combo_interface.currentData()
        if not iface_data:
            QMessageBox.warning(self, "Error", "No interface selected")
            return
        
        system = platform.system()
        
        reply = QMessageBox.question(
            self, 
            "Confirm Execution",
            f"This will execute the following command:\n\n{self.current_command}\n\n"
            "This requires administrator/sudo privileges. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            if system == "Linux" or system == "Darwin":
                # Use pkexec or sudo
                if system == "Linux":
                    # Try pkexec first (GUI sudo), fallback to terminal sudo
                    try:
                        result = subprocess.run(
                            ["pkexec", "ip", "addr", "add", 
                             f"{self.ip_address}/{self._netmask_to_cidr(self.txt_netmask.text())}", 
                             "dev", iface_data.name],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            QMessageBox.information(
                                self, 
                                "Success", 
                                f"IP address {self.ip_address} configured on {iface_data.name}"
                            )
                            self.accept()
                            return
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        pass
                
                # Fallback: Show instructions
                QMessageBox.information(
                    self,
                    "Manual Execution Required",
                    f"Please open a terminal and run:\n\n{self.current_command}\n\n"
                    "Then click OK to continue."
                )
                self.accept()
                
            elif system == "Windows":
                # On Windows, need to run as admin
                QMessageBox.information(
                    self,
                    "Admin Rights Required",
                    f"Please open Command Prompt as Administrator and run:\n\n{self.current_command}\n\n"
                    "Then click OK to continue."
                )
                self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute command:\n{str(e)}")
