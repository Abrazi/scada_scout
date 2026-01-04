from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QDialogButtonBox, QLabel, QPushButton, QDoubleSpinBox, QHBoxLayout, QRadioButton, QButtonGroup
from PySide6.QtCore import Qt
from src.models.device_models import Signal, SignalType

class ControlDialog(QDialog):
    """
    Dialog for issuing IEC 61850 Control Commands.
    Supports SBO and Direct Operate.
    """
    def __init__(self, signal: Signal, parent=None):
        super().__init__(parent)
        self.signal = signal
        self.setWindowTitle(f"Control: {signal.name}")
        self.resize(400, 300)
        
        self.layout = QVBoxLayout(self)
        
        # Signal Info
        info_layout = QFormLayout()
        info_layout.addRow("Signal:", QLabel(signal.name))
        info_layout.addRow("Address:", QLabel(signal.address))
        self.layout.addLayout(info_layout)
        
        # Control Model Selection
        self.ctl_model_group = QButtonGroup(self)
        self.rb_sbo = QRadioButton("Select Before Operate (SBO)")
        self.rb_direct = QRadioButton("Direct Operate")
        self.rb_sbo.setChecked(True)
        self.ctl_model_group.addButton(self.rb_sbo)
        self.ctl_model_group.addButton(self.rb_direct)
        
        ctl_layout = QHBoxLayout()
        ctl_layout.addWidget(self.rb_sbo)
        ctl_layout.addWidget(self.rb_direct)
        self.layout.addWidget(QLabel("Control Model:"))
        self.layout.addLayout(ctl_layout)
        
        # Value Input
        self.value_input = QComboBox()
        self.value_input.addItems(["False (0)", "True (1)"])
        # TODO: Add Analog input support if signal is analog
        
        self.layout.addWidget(QLabel("Value:"))
        self.layout.addWidget(self.value_input)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("Select")
        self.btn_operate = QPushButton("Operate")
        self.btn_cancel = QPushButton("Cancel")
        
        self.btn_select.clicked.connect(self.accept_select)
        self.btn_operate.clicked.connect(self.accept_operate)
        self.btn_cancel.clicked.connect(self.accept_cancel)
        
        # Logic: Direct operate disables Select button
        self.rb_direct.toggled.connect(lambda: self.btn_select.setEnabled(not self.rb_direct.isChecked()))
        
        btn_layout.addWidget(self.btn_select)
        btn_layout.addWidget(self.btn_operate)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)
        
        self.command = None # 'SELECT', 'OPERATE', 'CANCEL'
        self.value = False

    def accept_select(self):
        self.command = 'SELECT'
        self.accept()

    def accept_operate(self):
        self.command = 'OPERATE'
        self.value = bool(self.value_input.currentIndex()) # 0 or 1
        self.accept()

    def accept_cancel(self):
        self.command = 'CANCEL'
        self.accept()
        
    def get_command(self):
        return self.command, self.value
