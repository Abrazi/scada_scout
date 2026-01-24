from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, 
    QMessageBox, QWidget, QGroupBox, QFormLayout, QCheckBox,
    QLineEdit, QDateTimeEdit, QApplication
)
from PySide6.QtCore import Qt, QDateTime
import logging
from datetime import datetime
from typing import Optional
import re

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
        self.lbl_ref.setProperty("class", "subheading")
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
        self._set_field_state(self.txt_control_model, None)
        model_row.addWidget(self.txt_control_model)
        
        self.btn_read_model = QPushButton("Read Model")
        self.btn_read_model.clicked.connect(self._detect_control_model)
        model_row.addWidget(self.btn_read_model)
        model_layout.addRow("Control Model:", model_row)
        
        # Current Value Row
        val_row = QHBoxLayout()
        self.lbl_current_val = QLabel("Reading...")
        self.lbl_current_val.setProperty("class", "status")
        self._set_label_status(self.lbl_current_val, "info")
        val_row.addWidget(self.lbl_current_val)
        
        # smaller refresh button (consistent with other compact refresh buttons)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setFixedWidth(80)
        self.btn_refresh.setToolTip("Refresh current status (shows Hex / Decimal / Enum)")
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
        
        # SBO Timeout
        self.num_sbo_timeout = QSpinBox()
        self.num_sbo_timeout.setRange(10, 10000)
        self.num_sbo_timeout.setValue(100)  # Default 100ms like iedexplorer
        self.num_sbo_timeout.setSuffix(" ms")
        form_extras.addRow("SBO Timeout:", self.num_sbo_timeout)
        
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
        self.lbl_status.setProperty("class", "status")
        self._set_label_status(self.lbl_status, "info")
        status_layout.addWidget(self.lbl_status)
        
        main_layout.addWidget(status_group)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_select = QPushButton("1. Select (SBO)")
        self.btn_select.clicked.connect(self._on_select)
        self.btn_select.setEnabled(False)
        
        self.btn_operate = QPushButton("2. Operate")
        self.btn_operate.clicked.connect(self._on_operate)
        self.btn_operate.setEnabled(False)
        
        self.btn_direct = QPushButton("Direct Control")
        self.btn_direct.clicked.connect(self._on_direct)
        self.btn_direct.setEnabled(False)
        
        self.btn_abort = QPushButton("Abort Selection (Cancel)")
        self.btn_abort.clicked.connect(self._on_abort)
        self.btn_abort.setEnabled(False)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_select)
        btn_layout.addWidget(self.btn_operate)
        btn_layout.addWidget(self.btn_direct)
        btn_layout.addWidget(self.btn_abort)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        
        main_layout.addLayout(btn_layout)

    def _set_label_status(self, label: QLabel, status: Optional[str]):
        if status:
            label.setProperty("status", status)
        else:
            label.setProperty("status", "")
        label.style().unpolish(label)
        label.style().polish(label)

    def _set_field_state(self, field: QLineEdit, state: Optional[str]):
        if state:
            field.setProperty("state", state)
        else:
            field.setProperty("state", "")
        field.style().unpolish(field)
        field.style().polish(field)

    # --- Value formatting helpers (mirror watch-list behavior) ---
    def _format_status_value(self, signal) -> str:
        """Format a Signal.value as: 0xHEX (DEC) [EnumLabel] or fallback to str(value)."""
        if getattr(signal, "value", None) is None:
            return "--"

        num, enum_label = self._extract_numeric_and_enum(signal)
        if num is not None:
            hex_str = f"0x{num:X}"
            if enum_label:
                return f"{hex_str} ({num}) {enum_label}"
            return f"{hex_str} ({num})"

        return str(signal.value)

    def _is_pos_stval(self, signal) -> bool:
        addr = (getattr(signal, 'address', '') or "").lower()
        name = (getattr(signal, 'name', '') or "").lower()
        return "pos.stval" in addr or "pos$stval" in addr or ("pos" in addr and name == "stval")

    def _extract_numeric_and_enum(self, signal) -> tuple[int | None, str | None]:
        """Try to extract an integer value and an optional enum label from a Signal-like object."""
        num = None
        enum_label = None

        mapping = getattr(signal, "enum_map", None)
        if not mapping and self._is_pos_stval(signal):
            mapping = {0: "intermediate", 1: "open", 2: "closed", 3: "bad"}

        val = getattr(signal, 'value', None)
        # booleans
        if isinstance(val, bool):
            num = int(val)
        elif isinstance(val, int):
            num = val
        elif isinstance(val, float) and val.is_integer():
            num = int(val)
        elif isinstance(val, str):
            text = val.strip()
            try:
                if text.lower().startswith("0x"):
                    num = int(text.split()[0], 16)
                else:
                    m = re.search(r"\(([-]?\d+)\)", text)
                    if m:
                        num = int(m.group(1))
                    elif re.fullmatch(r"-?\d+", text):
                        num = int(text)
            except Exception:
                num = None

            if num is None and mapping:
                for k, v in mapping.items():
                    if str(v).lower() == text.lower():
                        num = int(k)
                        break

            if num is not None and not enum_label:
                m = re.match(r"(.+?)\s*\(\s*[-]?\d+\s*\)", text)
                if m:
                    enum_label = m.group(1).strip()

        if num is not None and mapping and num in mapping:
            enum_label = mapping[num]

        return num, enum_label

    def _get_adapter(self):
        """Get the protocol adapter for this device."""
        return self.device_manager.get_protocol(self.device_name)

    def _detect_control_model(self):
        """
        JIT Initialization: Calls adapter.init_control_context().
        Step 1 of the strict control lifecycle.
        """
        self.lbl_status.setText("Initializing control context...")
        self._set_label_status(self.lbl_status, "info")
        
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
                    
                    # Sync UI with Context (Parameters)
                    self.num_ctl_num.setValue(ctx.ctl_num)
                    self.txt_origin_ident.setText(ctx.originator_id)
                    self.cmb_origin_cat.setCurrentIndex(ctx.originator_cat)
                    
                    # Capability flags (for debugging/info)
                    caps = []
                    if ctx.supports_sbo: caps.append("SBO")
                    if ctx.supports_sbOw: caps.append("SBOw")
                    if ctx.supports_direct: caps.append("Oper")
                    cap_str = f" [{', '.join(caps)}]" if caps else ""
                    
                    names = {
                        0: "Status Only (0)",
                        1: "Direct Normal (1)",
                        2: "SBO Normal (2)",
                        3: "Direct Enhanced (3)",
                        4: "SBO Enhanced (4)"
                    }
                    name = names.get(self.detected_control_model, f"Unknown ({self.detected_control_model})")
                    self.txt_control_model.setText(f"{name}{cap_str}")
                    
                    if self.detected_control_model == 0:
                        self._set_field_state(self.txt_control_model, "error")
                    else:
                        self._set_field_state(self.txt_control_model, "ok")
                    
                    self._update_button_states()
                    self.lbl_status.setText(f"Context Initialized: {name}")
                    self._set_label_status(self.lbl_status, "success")
                else:
                    self.lbl_status.setText("Control NOT support (ctlModel=0 or missing)")
                    self.txt_control_model.setText("Not Supported")
                    self._set_field_state(self.txt_control_model, "error")
            else:
                self.lbl_status.setText("Error: Adapter does not support JIT Context")

        except Exception as e:
            self.lbl_status.setText(f"Error initializing context: {e}")
            self._set_label_status(self.lbl_status, "error")

    def _update_button_states(self):
        model = self.detected_control_model
        is_sbo = model in [2, 4]
        is_direct = model in [1, 3]
        
        self.btn_select.setEnabled(is_sbo and not self.selected)
        self.btn_operate.setEnabled(is_sbo and self.selected)
        self.btn_direct.setEnabled(is_direct)
        self.btn_abort.setEnabled(is_sbo and self.selected)
        
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
                    formatted = self._format_status_value(res)
                    self.lbl_current_val.setText(formatted)
                    # keep raw value handy on hover
                    try:
                        self.lbl_current_val.setToolTip(repr(res.value))
                    except Exception:
                        self.lbl_current_val.setToolTip(str(res.value))
                    self._set_label_status(self.lbl_current_val, "info")
                else:
                    self.lbl_current_val.setText("NULL (Read Failed)")
                    self.lbl_current_val.setToolTip("")
                    self._set_label_status(self.lbl_current_val, "error")
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
        
        # SBO Timeout
        params['sbo_timeout'] = self.num_sbo_timeout.value()
        
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

            # Update Context from UI
            params = self._get_params()
            object_ref = adapter._get_control_object_reference(self.signal.address)
            ctx = adapter.controls.get(object_ref)
            if ctx:
                ctx.originator_cat = params['originator_category']
                ctx.originator_id = params['originator_identity']
                ctx.ctl_num = self.num_ctl_num.value()

            val = self._get_value()
            
            self.lbl_status.setText("Selecting Module...")
            self._set_label_status(self.lbl_status, "info")
            QApplication.processEvents()

            if adapter.select(self.signal, value=val, params=params):
                self.lbl_status.setText("SELECT Successful (Ready to Operate)")
                self._set_label_status(self.lbl_status, "success")
                self.selected = True 
                self._update_button_states()
            else:
                self.lbl_status.setText("SELECT FAILED (Check device logs)")
                self._set_label_status(self.lbl_status, "error")
        except Exception as e:
            self.lbl_status.setText(f"Select Error: {e}")
            self._set_label_status(self.lbl_status, "error")

    def _on_operate(self):
        self.lbl_status.setText("Operating...")
        self._set_label_status(self.lbl_status, "info")
        QApplication.processEvents()
        
        try:
            adapter = self._get_adapter()
            params = self._get_params()
            
            # Update Context from UI
            object_ref = adapter._get_control_object_reference(self.signal.address)
            ctx = adapter.controls.get(object_ref)
            if ctx:
                ctx.originator_cat = params['originator_category']
                ctx.originator_id = params['originator_identity']
                ctx.ctl_num = self.num_ctl_num.value()

            val = self._get_value()
            
            # Use automatic SBO workflow if SBO model and not already selected
            if ctx and ctx.ctl_model.is_sbo and not self.selected:
                # Full SBO sequence: SELECT -> wait -> OPERATE
                success = adapter.send_command(self.signal, val, params=params)
                if success:
                    self.lbl_status.setText("SBO SEQUENCE SUCCESSFUL")
                    self._set_label_status(self.lbl_status, "success")
                    self.selected = False  # Reset selection state
                    
                    # Update ctlNum in UI for next time (auto-incremented in adapter)
                    if ctx:
                        self.num_ctl_num.setValue(ctx.ctl_num)
                        
                    self._update_button_states()
                    self._load_current_value()
                else:
                    # If adapter provided a specific control error, show it to the user
                    err = getattr(adapter, '_last_control_error', None)
                    if err:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "Operate Aborted", f"Operation aborted: {err}")
                        self.lbl_status.setText(err)
                    else:
                        self.lbl_status.setText("SBO SEQUENCE FAILED")
                    self._set_label_status(self.lbl_status, "error")
            else:
                # Direct operate or already selected SBO
                success = adapter.operate(self.signal, val, params=params)
                
                if success:
                    self.lbl_status.setText("OPERATE SUCCESSFUL")
                    self._set_label_status(self.lbl_status, "success")
                    self.selected = False 
                    
                    # Update ctlNum in UI for next time (auto-incremented in adapter)
                    if ctx:
                        self.num_ctl_num.setValue(ctx.ctl_num)
                        
                    self._update_button_states()
                    self._load_current_value()
                else:
                    self.lbl_status.setText("OPERATE FAILED")
                    self._set_label_status(self.lbl_status, "error")
        except Exception as e:
            self.lbl_status.setText(f"Error: {e}")
            self._set_label_status(self.lbl_status, "error")

    def _on_direct(self):
        # Same as operate, but without selection check (adapter handles it)
        self._on_operate()

    def _on_abort(self):
        """Submit Cancel command to deselect."""
        try:
            adapter = self._get_adapter()
            if not adapter: return
            
            self.lbl_status.setText("Aborting Selection...")
            self._set_label_status(self.lbl_status, "info")
            QApplication.processEvents()
            
            if adapter.cancel(self.signal):
                self.lbl_status.setText("Selection Aborted Successfully")
                self._set_label_status(self.lbl_status, "success")
                self.selected = False
                self._update_button_states()
            else:
                self.lbl_status.setText("Abort Failed")
                self._set_label_status(self.lbl_status, "error")
        except Exception as e:
            self.lbl_status.setText(f"Abort Error: {e}")

    def _on_cancel(self):
        # Deprecated: use btn_close or reject() directly
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
