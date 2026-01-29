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
        if "." in self.obj_ref or "$" in self.obj_ref:
            # Handle both . and $ as separators
            parts = re.split(r'[\.\$]', self.obj_ref)
            if len(parts) > 1:
                # Basic heuristic to get DO path
                # Recursively remove last part if it looks like an attribute (stVal, ctlVal, Oper, etc)
                # This ensures we get to the DO (e.g. CSWI1.Pos) even from Pos.Oper.ctlVal
                while parts and parts[-1] in ["ctlVal", "Oper", "SBO", "SBOw", "Cancel", "stVal", "q", "t"]:
                    parts.pop()
                
                # Reconstruct first part (LD/LN) properly if it was split
                # But wait, re.split replaces all separators. 
                # Let's try a safer way that preserves original structure as much as possible
                # Actually, the adapter handles reconstruction from DO path.
                # Let's just use the adapter's helper if possible or mimic it.
                suffixes = [
                    ".Oper.ctlVal", "$Oper$ctlVal", 
                    ".SBO.ctlVal", "$SBO$ctlVal", 
                    ".SBOw.ctlVal", "$SBOw$ctlVal", 
                    ".Cancel.ctlVal", "$Cancel$ctlVal",
                    ".Oper", "$Oper", 
                    ".SBO", "$SBO", 
                    ".SBOw", "$SBOw", 
                    ".Cancel", "$Cancel", 
                    ".ctlVal", "$ctlVal", 
                    ".stVal", "$stVal", 
                    ".q", "$q", 
                    ".t", "$t"
                ]
                for suffix in suffixes:
                    if self.obj_ref.endswith(suffix):
                        self.obj_ref = self.obj_ref[:-len(suffix)]
                        break
        
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
            # User reports False(0) Closes the breaker. 
            # Standard logic: False=0, True=1.
            # So "Close" -> 0, "Open" -> 1.
            self.input_widget.addItems(["Close / On (False / 0)", "Open / Off (True / 1)"])
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
        self.cmb_origin_cat.setCurrentIndex(3) # Default Remote Control
        origin_layout.addRow("Originator Category:", self.cmb_origin_cat)
        
        self.txt_origin_ident = QLineEdit("SCADA Scout")
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
                    return
                
                # ctx is None - try offline fallback
                offline_model = self._read_offline_ctrlmodel()
                if offline_model is not None:
                    self.detected_control_model = offline_model
                    names = {
                        0: "Status Only (0)",
                        1: "Direct Normal (1)",
                        2: "SBO Normal (2)",
                        3: "Direct Enhanced (3)",
                        4: "SBO Enhanced (4)"
                    }
                    name = names.get(self.detected_control_model, f"Unknown ({self.detected_control_model})")
                    self.txt_control_model.setText(f"{name} [from SCD]")
                    
                    if self.detected_control_model == 0:
                        self._set_field_state(self.txt_control_model, "error")
                    else:
                        self._set_field_state(self.txt_control_model, "ok")
                    
                    self._update_button_states()
                    self.lbl_status.setText(f"Offline Mode: {name} (from SCD file)")
                    self._set_label_status(self.lbl_status, "info")
                else:
                    self.lbl_status.setText("Control NOT supported (ctlModel=0 or missing)")
                    self.txt_control_model.setText("Not Supported")
                    self._set_field_state(self.txt_control_model, "error")
            else:
                self.lbl_status.setText("Error: Adapter does not support JIT Context")

        except Exception as e:
            self.lbl_status.setText(f"Error initializing context: {e}")
            self._set_label_status(self.lbl_status, "error")

    def _sync_ui_from_context(self):
        """Sync UI fields from the underlying protocol context."""
        try:
            adapter = self._get_adapter()
            if not adapter: return
            
            object_ref = adapter._get_control_object_reference(self.signal.address)
            ctx = adapter.controls.get(object_ref)
            if ctx:
                self.num_ctl_num.setValue(ctx.ctl_num)
                self.txt_origin_ident.setText(ctx.originator_id)
                self.cmb_origin_cat.setCurrentIndex(ctx.originator_cat)
                
                # Update button states based on new context state
                self._update_button_states()
        except Exception as e:
            logger.warning(f"Failed to sync UI from context: {e}")

    
    def _read_offline_ctrlmodel(self) -> Optional[int]:
        """Try to read ctrlModel from device tree structure (offline fallback)."""
        try:
            device = self.device_manager.get_device(self.device_name)
            if not device or not hasattr(device, 'root_node'):
                logger.info(f"Offline ctrlModel: No device or root_node for {self.device_name}")
                return None
            
            # Try to find ctrlModel signal in the tree
            # Format: LD/LN.DO.ctlModel
            ctl_model_paths = [
                f"{self.obj_ref}.ctlModel",
                f"{self.obj_ref}$ctlModel"
            ]
            
            logger.info(f"Offline ctrlModel: Searching for paths: {ctl_model_paths}")
            logger.info(f"Offline ctrlModel: obj_ref={self.obj_ref}, signal.address={self.signal.address}")
            
            # Log available signals for debugging
            all_addrs = self._collect_all_signal_addresses(device.root_node)
            matching = [a for a in all_addrs if 'ctlmodel' in a.lower()]
            if matching:
                logger.info(f"Offline ctrlModel: Found {len(matching)} ctlModel signals: {matching[:5]}")
            
            for ctl_path in ctl_model_paths:
                signal = self._find_signal_in_tree(device.root_node, ctl_path)
                if signal:
                    logger.info(f"Offline ctrlModel: Found signal at {ctl_path}, value={signal.value}")
                    if signal.value is not None:
                        try:
                            return int(signal.value)
                        except (ValueError, TypeError):
                            pass
            
            logger.info(f"Offline ctrlModel: No ctrlModel found")
            return None
        except Exception as e:
            logger.error(f"Failed to read offline ctrlModel: {e}", exc_info=True)
            return None
    
    def _collect_all_signal_addresses(self, node, addresses=None):
        """Collect all signal addresses in the tree for debugging."""
        if addresses is None:
            addresses = []
        
        if hasattr(node, 'signals'):
            for sig in node.signals:
                if sig.address:
                    addresses.append(sig.address)
        
        if hasattr(node, 'children'):
            for child in node.children:
                self._collect_all_signal_addresses(child, addresses)
        
        return addresses
    
    def _find_signal_in_tree(self, node, address: str):
        """Recursively search for a signal by address in the device tree."""
        if hasattr(node, 'signals'):
            for sig in node.signals:
                if sig.address == address:
                    return sig
        
        if hasattr(node, 'children'):
            for child in node.children:
                result = self._find_signal_in_tree(child, address)
                if result:
                    return result
        
        return None

    def _update_button_states(self):
        model = self.detected_control_model
        is_sbo = model in [2, 4]
        is_direct = model in [1, 3]
        
        self.btn_select.setEnabled(is_sbo and not self.selected)
        self.btn_operate.setEnabled(is_sbo and self.selected)
        self.btn_direct.setEnabled(is_direct)
        self.btn_abort.setEnabled(is_sbo and self.selected)
        
        # Lock input widget if selected (SBO) to prevent value mismatch between Select and Operate
        if self.input_widget:
            self.input_widget.setEnabled(not (is_sbo and self.selected))
        
        # Disable control buttons if adapter not connected
        adapter = self._get_adapter()
        if not adapter or not getattr(adapter, 'connected', False):
            self.btn_select.setEnabled(False)
            self.btn_operate.setEnabled(False)
            self.btn_direct.setEnabled(False)
            self.btn_abort.setEnabled(False)
        
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
            res = None
            
            # Try live device first if connected
            if adapter and getattr(adapter, 'connected', False):
                logger.info(f"Control Dialog: Attempting live read for stVal")
                # Determine stVal path
                # Try both . and $ separators
                st_paths = [f"{self.obj_ref}.stVal", f"{self.obj_ref}$stVal"]
                
                from src.models.device_models import Signal
                for st_path in st_paths:
                    dummy = Signal(name="stVal", address=st_path)
                    res = adapter.read_signal(dummy)
                    if res and res.value is not None:
                        logger.info(f"Control Dialog: Live read successful, value={res.value}")
                        break
                
                if res and res.value is not None:
                    formatted = self._format_status_value(res)
                    self.lbl_current_val.setText(formatted)
                    # keep raw value handy on hover
                    try:
                        self.lbl_current_val.setToolTip(repr(res.value))
                    except Exception:
                        self.lbl_current_val.setToolTip(str(res.value))
                    self._set_label_status(self.lbl_current_val, "info")
                    return
                else:
                    logger.info(f"Control Dialog: Live read failed or returned None, trying offline fallback")
            
            # Offline fallback: read from device tree structure
            # This runs when device is offline OR when live read failed
            logger.info(f"Control Dialog: Trying offline fallback for stVal")
            offline_stval = self._read_offline_stval()
            if offline_stval is not None:
                formatted = self._format_status_value(offline_stval)
                # Check if value is actually populated
                if offline_stval.value is not None:
                    self.lbl_current_val.setText(f"{formatted} [from SCD]")
                else:
                    # Signal exists but value is None
                    self.lbl_current_val.setText("-- [from SCD, no default value]")
                try:
                    self.lbl_current_val.setToolTip(repr(offline_stval.value) if offline_stval.value is not None else "No value in SCD")
                except Exception:
                    self.lbl_current_val.setToolTip(str(offline_stval.value) if offline_stval.value is not None else "No value")
                self._set_label_status(self.lbl_current_val, "info")
            else:
                logger.info(f"Control Dialog: Offline fallback also failed")
                self.lbl_current_val.setText("NULL (Not found in device or SCD)")
                self.lbl_current_val.setToolTip("")
                self._set_label_status(self.lbl_current_val, "error")
        except Exception as e:
            logger.error(f"Control Dialog: Error in _load_current_value: {e}", exc_info=True)
            self.lbl_current_val.setText(str(e))
    
    def _read_offline_stval(self):
        """Try to read stVal from device tree structure (offline fallback)."""
        try:
            device = self.device_manager.get_device(self.device_name)
            if not device or not hasattr(device, 'root_node'):
                logger.info(f"Offline stVal: No device or root_node for {self.device_name}")
                return None
            
            # Try to find stVal signal in the tree
            st_paths = [
                f"{self.obj_ref}.stVal",
                f"{self.obj_ref}$stVal"
            ]
            
            logger.info(f"Offline stVal: Searching for paths: {st_paths}")
            logger.info(f"Offline stVal: obj_ref={self.obj_ref}, signal.address={self.signal.address}")
            
            # Log available signals for debugging
            all_addrs = self._collect_all_signal_addresses(device.root_node)
            matching = [a for a in all_addrs if 'stval' in a.lower() and any(p.replace('.stVal', '').replace('$stVal', '') in a for p in st_paths)]
            if matching:
                logger.info(f"Offline stVal: Found {len(matching)} stVal signals near obj_ref: {matching[:5]}")
            
            for st_path in st_paths:
                signal = self._find_signal_in_tree(device.root_node, st_path)
                if signal:
                    logger.info(f"Offline stVal: Found signal at {st_path}, value={signal.value}")
                    return signal
            
            logger.info(f"Offline stVal: No stVal found")
            return None
        except Exception as e:
            logger.error(f"Failed to read offline stVal: {e}", exc_info=True)
            return None

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
                self._sync_ui_from_context()
            else:
                err = getattr(adapter, '_last_control_error', "SELECT FAILED (Check device logs)")
                self.lbl_status.setText(err)
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
                ctx.originator_cat = params['originator_category']
                ctx.originator_id = params['originator_identity']
                
                # Only update ctlNum from UI if it was manually changed or if context is 0
                # If context has a valid non-zero ctlNum (captured from Select), preserve it!
                if ctx.ctl_num == 0 or self.num_ctl_num.value() != 0:
                     # This logic is tricky. If UI shows 0 and ctx has index 2, we should trust ctx?
                     # Better: trust UI only if user specifically touched it?
                     # Let's say: If UI is 0 AND ctx has value > 0, KEEP ctx value.
                     if self.num_ctl_num.value() == 0 and ctx.ctl_num > 0:
                         logger.debug(f"Preserving context ctlNum={ctx.ctl_num} despite UI=0")
                     else:
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
                    
                    import time
                    time.sleep(0.5)
                    QApplication.processEvents()
                    
                    self._sync_ui_from_context()
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
                logger.info(f"ControlDialog: Calling operate with val={val}, ctlNum={ctx.ctl_num if ctx else '?'}")
                success = adapter.operate(self.signal, val, params=params)
                
                if success:
                    self.lbl_status.setText("OPERATE SUCCESSFUL")
                    self._set_label_status(self.lbl_status, "success")
                    self.selected = False 
                    
                    import time
                    time.sleep(0.5)
                    QApplication.processEvents()
                    
                    self._sync_ui_from_context()
                    self._load_current_value()
                else:
                    err = getattr(adapter, '_last_control_error', "OPERATE FAILED")
                    self.lbl_status.setText(err)
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
                self._sync_ui_from_context()
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
