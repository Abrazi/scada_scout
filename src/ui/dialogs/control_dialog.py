from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, 
    QMessageBox, QWidget, QGroupBox, QFormLayout, QCheckBox,
    QLineEdit, QDateTimeEdit, QApplication
)
from PySide6.QtCore import Qt, QDateTime
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ControlDialog(QDialog):
    """
    Advanced Control Dialog for IEC 61850.
    Matches the design of SboWriteDialog.cs.
    """
    def __init__(self, device_name, signal, device_manager, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.signal = signal
        self.device_manager = device_manager
        
        self.setWindowTitle("IEC 61850 Control Operation")
        self.resize(700, 720) # Match C# size
        
        self.is_sbo = False
        self.selected = False
        self.detected_control_model = -1
        
        self._setup_ui()
        
        # Auto-detect on open
        self._detect_control_model()
        self._load_current_value()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- 1. Reference Information ---
        info_group = QGroupBox("Reference Information")
        info_layout = QFormLayout(info_group)
        
        # Extract Object Reference (DO)
        self.obj_ref = self.signal.address
        if "." in self.obj_ref:
            parts = self.obj_ref.split('.')
            if len(parts) > 1:
                # Basic heuristic to get DO path
                # Recursively remove last part if it looks like an attribute (stVal, ctlVal, Oper, etc)
                # This ensures we get to the DO (e.g. CSWI1.Pos) even from Pos.Oper.ctlVal
                while parts and parts[-1] in ["ctlVal", "Oper", "SBO", "SBOw", "Cancel", "stVal", "q", "t"]:
                    parts.pop()
                
                self.obj_ref = ".".join(parts)
        
        self.lbl_ref = QLabel(self.obj_ref)
        self.lbl_ref.setStyleSheet("font-weight: bold")
        info_layout.addRow("Control Object:", self.lbl_ref)
        
        self.lbl_full_ref = QLabel(self.signal.address)
        info_layout.addRow("Full Reference:", self.lbl_full_ref)
        
        fc = getattr(self.signal, 'description', '')
        self.lbl_fc = QLabel(fc if fc else "FC=CO (Assumed)")
        info_layout.addRow("Functional Constraint:", self.lbl_fc)
        
        main_layout.addWidget(info_group)
        
        # --- 2. Control Model & Status ---
        model_group = QGroupBox("Control Model & Current Status")
        model_layout = QFormLayout(model_group)
        
        # Control Model Row
        model_row = QHBoxLayout()
        self.txt_control_model = QLineEdit()
        self.txt_control_model.setReadOnly(True)
        self.txt_control_model.setStyleSheet("background-color: lightgray")
        model_row.addWidget(self.txt_control_model)
        
        self.btn_read_model = QPushButton("Read Model")
        self.btn_read_model.clicked.connect(self._detect_control_model)
        model_row.addWidget(self.btn_read_model)
        model_layout.addRow("Control Model:", model_row)
        
        # Current Value Row
        val_row = QHBoxLayout()
        self.lbl_current_val = QLabel("Reading...")
        self.lbl_current_val.setStyleSheet("color: blue")
        val_row.addWidget(self.lbl_current_val)
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._load_current_value)
        val_row.addWidget(self.btn_refresh)
        model_layout.addRow("Current Status Value:", val_row)
        
        main_layout.addWidget(model_group)
        
        # --- 3. Control Parameters ---
        params_group = QGroupBox("Control Parameters")
        params_layout = QVBoxLayout(params_group)
        form_params = QFormLayout()
        
        # Value Input
        self.input_widget = None
        sig_type = str(self.signal.signal_type).upper() if self.signal.signal_type else ""
        
        # Determine Input Widget
        if "BOOL" in sig_type or "SPC" in self.signal.address or "ctlVal" in self.signal.name: 
            self.input_widget = QComboBox()
            self.input_widget.addItems(["False (0) (Off)", "True (1) (On)"])
        elif "FLOAT" in sig_type:
            self.input_widget = QDoubleSpinBox()
            self.input_widget.setRange(-1e9, 1e9)
            self.input_widget.setDecimals(4)
        else:
            self.input_widget = QSpinBox()
            self.input_widget.setRange(-2147483648, 2147483647)
            
        form_params.addRow("Control Value (ctlVal):", self.input_widget)
        params_layout.addLayout(form_params)
        
        # Checkboxes
        self.chk_test = QCheckBox("Test Mode (test=TRUE) - Command will not affect equipment")
        params_layout.addWidget(self.chk_test)
        
        self.chk_interlock = QCheckBox("Interlock Check - Verify interlocking conditions")
        params_layout.addWidget(self.chk_interlock)
        
        self.chk_synchro = QCheckBox("Synchro Check - Verify synchronization conditions")
        params_layout.addWidget(self.chk_synchro)
        
        # Control Number & Timestamp
        form_extras = QFormLayout()
        
        self.num_ctl_num = QSpinBox()
        self.num_ctl_num.setRange(0, 255)
        form_extras.addRow("Control Number (ctlNum):", self.num_ctl_num)
        
        # Timestamp
        ts_layout = QHBoxLayout()
        self.chk_use_ts = QCheckBox("Use Timestamp (T):")
        self.chk_use_ts.toggled.connect(lambda c: self.dt_ts.setEnabled(c))
        ts_layout.addWidget(self.chk_use_ts)
        
        self.dt_ts = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_ts.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")
        self.dt_ts.setEnabled(False)
        ts_layout.addWidget(self.dt_ts)
        
        form_extras.addRow(ts_layout)
        params_layout.addLayout(form_extras)
        
        main_layout.addWidget(params_group)
        
        # --- 4. Originator Information ---
        origin_group = QGroupBox("Origin (Originator Information)")
        origin_layout = QFormLayout(origin_group)
        
        self.cmb_origin_cat = QComboBox()
        self.cmb_origin_cat.addItems([
            "0 - Not supported", "1 - Bay control", "2 - Station control", 
            "3 - Remote control", "4 - Automatic bay", "5 - Automatic station", 
            "6 - Automatic remote", "7 - Maintenance", "8 - Process"
        ])
        self.cmb_origin_cat.setCurrentIndex(2) # Default Station Control
        origin_layout.addRow("Originator Category:", self.cmb_origin_cat)
        
        self.txt_origin_ident = QLineEdit("Station")
        origin_layout.addRow("Originator Identity:", self.txt_origin_ident)
        
        main_layout.addWidget(origin_group)
        
        # --- 5. Status & Actions ---
        status_group = QGroupBox("Operation Status")
        status_layout = QVBoxLayout(status_group)
        
        self.lbl_status = QLabel("Ready. Please read control model first.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size: 14px; padding: 5px;")
        status_layout.addWidget(self.lbl_status)
        
        main_layout.addWidget(status_group)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_select = QPushButton("1. Select (SBO)")
        self.btn_select.setFixedHeight(40)
        self.btn_select.clicked.connect(self._on_select)
        self.btn_select.setEnabled(False)
        
        self.btn_operate = QPushButton("2. Operate")
        self.btn_operate.setFixedHeight(40)
        self.btn_operate.clicked.connect(self._on_operate)
        self.btn_operate.setEnabled(False)
        
        self.btn_direct = QPushButton("Direct Control")
        self.btn_direct.setFixedHeight(40)
        self.btn_direct.clicked.connect(self._on_direct)
        self.btn_direct.setEnabled(False)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.clicked.connect(self._on_cancel) # Close dialog or IEC Cancel?
        # The C# "Cancel" button closes the dialog. 
        # But we also need an IEC Cancel operation potentially?
        # C# "Cancel" is DialogResult.Cancel (close).
        # We can add a separate "Abort Selection" button if SBO.
        
        btn_layout.addWidget(self.btn_select)
        btn_layout.addWidget(self.btn_operate)
        btn_layout.addWidget(self.btn_direct)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(btn_layout)

    def _get_adapter(self):
        """Get the protocol adapter for this device."""
        return self.device_manager.get_protocol(self.device_name)

    def _detect_control_model(self):
        """
        JIT Initialization: Calls adapter.init_control_context().
        Step 1 of the strict control lifecycle.
        """
        self.lbl_status.setText("Initializing control context...")
        self.lbl_status.setStyleSheet("color: blue")
        
        try:
            adapter = self._get_adapter()
            if not adapter:
                self.lbl_status.setText("Error: No connection")
                return

            if hasattr(adapter, 'init_control_context'):
                # JIT Initialize
                ctx = adapter.init_control_context(self.signal.address)
                
                if ctx:
                    self.detected_control_model = ctx.ctl_model.value
                    
                    names = {
                        0: "Status Only (0)",
                        1: "Direct Normal (1)",
                        2: "SBO Normal (2)",
                        3: "Direct Enhanced (3)",
                        4: "SBO Enhanced (4)"
                    }
                    name = names.get(self.detected_control_model, f"Unknown ({self.detected_control_model})")
                    self.txt_control_model.setText(name)
                    
                    if self.detected_control_model == 0:
                        self.txt_control_model.setStyleSheet("background-color: #ffcccc") # Red
                    else:
                        self.txt_control_model.setStyleSheet("background-color: #ccffcc") # Green
                    
                    self._update_button_states()
                    self.lbl_status.setText(f"Context Initialized: {name}")
                    self.lbl_status.setStyleSheet("color: green")
                else:
                    self.lbl_status.setText("Error: Failed to initialize context (Not a control?)")
                    self.txt_control_model.setText("Error")
            else:
                self.lbl_status.setText("Error: Adapter does not support JIT Context")

        except Exception as e:
            self.lbl_status.setText(f"Error initializing context: {e}")
            self.lbl_status.setStyleSheet("color: red")

    def _update_button_states(self):
        model = self.detected_control_model
        is_sbo = model in [2, 4]
        is_direct = model in [1, 3]
        
        self.btn_select.setEnabled(is_sbo and not self.selected)
        self.btn_operate.setEnabled(is_sbo and self.selected)
        self.btn_direct.setEnabled(is_direct)
        
        if is_sbo:
            if self.selected:
                self.lbl_status.setText("Selection Successful. Ready to Operate.")
            else:
                self.lbl_status.setText("SBO Mode: Please Select first.")
        elif is_direct:
            self.lbl_status.setText("Direct Control Mode. Ready.")
        elif model == 0:
            self.lbl_status.setText("Status Only - Control not allowed.")

    def _load_current_value(self):
        try:
            adapter = self._get_adapter()
            if adapter:
                # Determine stVal path
                # obj_ref is DO path. stVal is usually DO.stVal
                # But for some signals it might be different.
                # Let's try to construct it.
                st_path = f"{self.obj_ref}.stVal"
                
                # We need to do a manual read.
                # Using lower level read if possible or create a dummy signal
                from src.models.device_models import Signal
                dummy = Signal(name="stVal", address=st_path)
                res = adapter.read_signal(dummy)
                
                if res.value is not None:
                    self.lbl_current_val.setText(str(res.value))
                    self.lbl_current_val.setStyleSheet("color: blue")
                else:
                    self.lbl_current_val.setText("NULL (Read Failed)")
                    self.lbl_current_val.setStyleSheet("color: red")
        except Exception as e:
            self.lbl_current_val.setText(str(e))

    def _get_params(self):
        params = {}
        # Originator
        params['originator_category'] = self.cmb_origin_cat.currentIndex()
        params['originator_identity'] = self.txt_origin_ident.text()
        
        # Checks
        params['interlock_check'] = self.chk_interlock.isChecked()
        params['synchro_check'] = self.chk_synchro.isChecked()
        params['test'] = self.chk_test.isChecked()
        
        return params

    def _get_value(self):
        if isinstance(self.input_widget, QComboBox):
            return self.input_widget.currentIndex() == 1
        elif isinstance(self.input_widget, (QSpinBox, QDoubleSpinBox)):
            return self.input_widget.value()
        return 0

    def _on_select(self):
        """Submit Select command."""
        try:
            adapter = self._get_adapter()
            if not adapter: return

            params = self._get_params() # Use existing param builder
            
            # Get value for SBO (required by JIT/Strict IEDs)
            val = self._get_value()
            # _get_value might not be enough if we need to handle "None" cases explicitly
            # But the logic above seems mostly safe.
            
            self.lbl_status.setText("Selecting...")
            self.lbl_status.setStyleSheet("color: blue")
            QApplication.processEvents()

            if adapter.select(self.signal, value=val, params=params):
                self.lbl_status.setText("Selection Successful (Selected)")
                self.lbl_status.setStyleSheet("color: green")
                self.selected = True # Track state locally as fallback
                self.btn_select.setEnabled(False)
                self.btn_operate.setEnabled(True)
                self.btn_cancel.setEnabled(True)
            else:
                self.lbl_status.setText("Selection Failed")
                self.lbl_status.setStyleSheet("color: red")
        except Exception as e:
            self.lbl_status.setText(f"Select Error: {e}")
            self.lbl_status.setStyleSheet("color: red")

    def _on_operate(self):
        self.lbl_status.setText("Operating...")
        self.lbl_status.setStyleSheet("color: blue")
        
        try:
            adapter = self._get_adapter()
            params = self._get_params()
            val = self._get_value()
            
            success = adapter.operate(self.signal, val, params=params)
            
            if success:
                self.lbl_status.setText("OPERATE Successful!")
                self.lbl_status.setStyleSheet("color: green")
                self.selected = False # Reset selection after operate
                self._update_button_states()
                self._load_current_value()
            else:
                self.lbl_status.setText("OPERATE Failed.")
                self.lbl_status.setStyleSheet("color: red")
        except Exception as e:
            self.lbl_status.setText(f"Error: {e}")

    def _on_direct(self):
        # Same as operate, but without selection check (adapter handles it)
        self._on_operate()

    def _on_cancel(self):
        # Close handles cleanup
        self.reject()

    def done(self, result):
        """Override done to ensure context is cleared when dialog closes."""
        try:
            adapter = self._get_adapter()
            if adapter and hasattr(adapter, 'clear_control_context'):
                adapter.clear_control_context(self.signal.address)
        except Exception:
            pass
        super().done(result)
