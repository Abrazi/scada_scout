import struct
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                QTableWidgetItem, QLabel, QPushButton, QHeaderView, 
                                QGroupBox, QFormLayout, QComboBox, QTabWidget, QWidget, QMessageBox)
from PySide6.QtCore import Qt
from src.models.device_models import SignalType

class DataInspectorDialog(QDialog):
    """
    Advanced Data Inspector for Modbus Registers.
    Reads a block of 4 registers (64-bit) and interprets them in all common formats.
    """
    def __init__(self, signal, device_name, device_manager, parent=None):
        super().__init__(parent)
        self.signal = signal
        self.device_name = device_name
        self.device_manager = device_manager
        
        self.setWindowTitle(f"Data Inspector - {signal.name} ({signal.address})")
        self.resize(800, 600)
        
        self.raw_registers = [0, 0, 0, 0] # 4 registers default
        
        # Set default register selection based on signal data type
        self._update_register_selection_default()
        
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header / Controls
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(f"<b>Address:</b> {self.signal.address}"))
        top_layout.addStretch()

        btn_refresh = QPushButton("Read Again")
        btn_refresh.clicked.connect(self._load_data)
        top_layout.addWidget(btn_refresh)
        layout.addLayout(top_layout)

        # Register Range Selection Controls
        register_group = QGroupBox("Register Range Selection")
        register_layout = QHBoxLayout(register_group)
        register_layout.addWidget(QLabel("Registers to inspect:"))

        self.combo_range = QComboBox()
        self.combo_range.addItem("Current (1 register)", 1)
        self.combo_range.addItem("Current + Next (2 registers, 32-bit)", 2)
        self.combo_range.addItem("Current + Previous (2 registers, 32-bit)", 5)
        self.combo_range.addItem("Prev + Current + Next (3 registers)", 3)
        self.combo_range.addItem("Prev + Current + Next + Next2 (4 registers, 64-bit)", 4)
        # Set default based on signal type
        default_range = 1
        data_type = getattr(self.signal, 'modbus_data_type', '') or getattr(self.signal, 'data_type', '')
        if isinstance(data_type, str):
            data_type = data_type.upper()
        else:
            data_type = str(data_type).upper()
        if '64' in data_type or 'DOUBLE' in data_type:
            default_range = 4
        elif '32' in data_type or 'FLOAT' in data_type:
            default_range = 2
        self.combo_range.setCurrentIndex(default_range - 1)
        self.combo_range.currentIndexChanged.connect(self._on_range_selection_changed)
        register_layout.addWidget(self.combo_range)
        register_layout.addStretch()
        layout.addWidget(register_group)

        # Raw Data View
        group_raw = QGroupBox("Raw Registers (Hex)")
        raw_layout = QHBoxLayout(group_raw)
        self.lbl_raw = QLabel("Waiting for data...")
        self.lbl_raw.setProperty("class", "code-strong")
        raw_layout.addWidget(self.lbl_raw)
        layout.addWidget(group_raw)

        # Interpretations Tabs
        self.tabs = QTabWidget()
        self.tab_16 = self._create_table_tab(["Type", "Value", "Description"])
        self.tabs.addTab(self.tab_16, "16-Bit")
        self.tab_32 = self._create_table_tab(["Type", "Endianness", "Value", "Notes"])
        self.tabs.addTab(self.tab_32, "32-Bit")
        self.tab_64 = self._create_table_tab(["Type", "Endianness", "Value", "Notes"])
        self.tabs.addTab(self.tab_64, "64-Bit")
        self.tab_other = self._create_table_tab(["Type", "Value", "Notes"])
        self.tabs.addTab(self.tab_other, "Strings/Time")
        layout.addWidget(self.tabs)

        # Close
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _on_range_selection_changed(self):
        self._load_data()

    def _update_register_selection_default(self):
        """Set default register selection based on signal data type."""
        data_type = getattr(self.signal, 'modbus_data_type', '') or getattr(self.signal, 'data_type', '')
        if isinstance(data_type, str):
            data_type = data_type.upper()
        else:
            data_type = str(data_type).upper()
        
        # For 32-bit types, default to current + next register
        if '32' in data_type or 'FLOAT' in data_type:
            self.register_selection = "current_next"
        # For 64-bit types, default to previous + current + next
        elif '64' in data_type or 'DOUBLE' in data_type:
            self.register_selection = "prev_current_next"
        else:
            # For 16-bit and other types, default to current only
            self.register_selection = "current"
        
        # Update combo box selection if it exists
        if hasattr(self, 'chk_base'):
            index = self.chk_base.findData(self.register_selection)
            if index >= 0:
                self.chk_base.setCurrentIndex(index)
    
    def _on_register_selection_changed(self):
        """Handle register selection change."""
        self.register_selection = self.chk_base.currentData()
        # Reload data with new selection
        self._load_data()

    def _create_table_tab(self, headers):
        widget = QWidget()
        lay = QVBoxLayout(widget)
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # table.verticalHeader().setVisible(False)
        lay.addWidget(table)
        widget.table = table # store ref
        return widget

    def _load_data(self):
        """Reads N registers starting from signal address, where N is user-selected (1-4)."""
        try:
            protocol = self.device_manager.get_protocol(self.device_name)
            if not protocol:
                self.lbl_raw.setText("Error: Device not connected")
                return

            # Check connection status
            connected = getattr(protocol, "connected", None)
            if connected is None and hasattr(protocol, "is_connected"):
                try:
                    connected = bool(protocol.is_connected())
                except Exception:
                    connected = None
            if connected is False:
                self.lbl_raw.setText("Error: Not connected to device")
                return

            # Parse address
            parts = self.signal.address.split(':')
            unit_id = None
            func_code = None
            start_addr = None

            if len(parts) == 3:
                unit_id = int(parts[0])
                func_code = int(parts[1])
                start_addr = int(parts[2])
            elif len(parts) == 2:
                func_map = {"coils": 1, "discrete": 2, "holding": 3, "input": 4}
                func_code = func_map.get(parts[0].lower())
                start_addr = int(parts[1])
                unit_id = getattr(protocol, "unit_id", 1)
            else:
                self.lbl_raw.setText("Error: Invalid address format")
                return

            # Decide function code for reading
            read_fc = func_code
            if func_code not in [3, 4]:
                read_fc = 3

            # Determine register range from combo
            num_regs = self.combo_range.currentData()
            # 1: current, 2: current+next, 5: current+previous,
            # 3: prev+current+next, 4: prev+current+next+next2
            if num_regs == 1:
                read_start = start_addr
                read_count = 1
            elif num_regs == 2:
                read_start = start_addr
                read_count = 2
            elif num_regs == 5:
                read_start = max(0, start_addr - 1)
                read_count = 2
            elif num_regs == 3:
                read_start = max(0, start_addr - 1)
                read_count = 3
            elif num_regs == 4:
                read_start = max(0, start_addr - 1)
                read_count = 4
            else:
                read_start = start_addr
                read_count = 1

            regs = None

            # --- Path 1: Modbus TCP via pymodbus client ---
            client = getattr(protocol, 'client', None)
            if client is not None and getattr(protocol, "connected", True):
                result = None
                if read_fc == 4:
                    result = client.read_input_registers(read_start, count=read_count, device_id=unit_id)
                else:
                    result = client.read_holding_registers(read_start, count=read_count, device_id=unit_id)
                if result is not None and not result.isError():
                    regs = result.registers
                else:
                    self.lbl_raw.setText(f"Read Error: {result}")
                    return

            # --- Path 2: Modbus RTU (or any adapter with direct read methods) ---
            elif hasattr(protocol, "read_holding_registers") or hasattr(protocol, "read_input_registers"):
                if read_fc == 4 and hasattr(protocol, "read_input_registers"):
                    regs = protocol.read_input_registers(unit_id, read_start, read_count)
                elif hasattr(protocol, "read_holding_registers"):
                    regs = protocol.read_holding_registers(unit_id, read_start, read_count)
                
                if regs is None:
                    self.lbl_raw.setText("Read Error: Device returned no data (timeout or exception)")
                    return

            # --- Path 3: Generic read_signal fallback ---
            else:
                # Build a temporary signal to call read_signal
                from src.models.device_models import Signal, ModbusDataType
                import copy
                temp_signal = copy.copy(self.signal)
                temp_signal.address = f"{unit_id}:{read_fc}:{read_start}"
                temp_signal.modbus_data_type = ModbusDataType.UINT16
                # Read read_count registers one by one
                regs = []
                for i in range(read_count):
                    temp_signal.address = f"{unit_id}:{read_fc}:{read_start + i}"
                    result = protocol.read_signal(temp_signal)
                    raw = result.value if result and result.value is not None else 0
                    try:
                        regs.append(int(raw) & 0xFFFF)
                    except Exception:
                        regs.append(0)

            if not regs:
                self.lbl_raw.setText("Read Error: Empty response")
                return

            self.raw_registers = regs
            hex_strs = [f"[{i:04X}]" for i in self.raw_registers]
            self.lbl_raw.setText(" ".join(hex_strs))
            self._update_interpretations()

        except Exception as e:
            import traceback
            self.lbl_raw.setText(f"Error: {e}")



    def _update_interpretations(self):
        regs = self.raw_registers
        num_regs = len(regs)
        
        # Clear all tabs if we have no data
        if num_regs == 0:
            self._fill_table(self.tab_16.table, [])
            self._fill_table(self.tab_32.table, [])
            self._fill_table(self.tab_64.table, [])
            self._fill_table(self.tab_other.table, [])
            return
        
        # 16-BIT TAB - Always available for first register
        r0 = regs[0]
        rows16 = []
        rows16.append(["UInt16", f"{r0}", "0 ... 65535"])
        rows16.append(["Int16", f"{self._to_signed(r0, 16)}", "-32768 ... 32767"])
        rows16.append(["Hex", f"0x{r0:04X}", ""])
        rows16.append(["Binary", f"{r0:016b}", "Bit mask"])
        rows16.append(["BCD (16-bit)", self._decode_bcd(r0), "0x1234 -> 1234"])
        self._fill_table(self.tab_16.table, rows16)

        # 32-BIT TAB - Available if we have at least 2 registers
        if num_regs >= 2:
            r0, r1 = regs[0], regs[1]
            
            variants32 = [
                ("ABCD (Big-Endian)", r0, r1),
                ("CDAB (Word-Swap)", r1, r0),
                ("BADC (Byte-Swap)", self._swap_bytes(r0), self._swap_bytes(r1)),
                ("DCBA (All-Swap)", self._swap_bytes(r1), self._swap_bytes(r0))
            ]
            
            rows32 = []
            for name, high, low in variants32:
                val32 = (high << 16) | low
                # Float
                fval = self._to_float(val32)
                rows32.append(["Float32", name, f"{fval:.6g}", "IEEE-754 Single"])
                
                # Int32
                i32 = self._to_signed(val32, 32)
                rows32.append(["Int32", name, f"{i32}", ""])
                
                # UInt32
                rows32.append(["UInt32", name, f"{val32}", ""])
            
            self._fill_table(self.tab_32.table, rows32)
        else:
            # Not enough registers for 32-bit
            self._fill_table(self.tab_32.table, [["", "Not enough registers", "", ""]])

        # 64-BIT TAB - Available if we have at least 4 registers, or show partial for 3
        if num_regs >= 4:
            # Full 64-bit interpretation
            val64_be = (regs[0] << 48) | (regs[1] << 32) | (regs[2] << 16) | regs[3]
            rows64 = []
            
            rows64.append(["UInt64", "Big-Endian", f"{val64_be}", ""])
            rows64.append(["Int64", "Big-Endian", f"{self._to_signed(val64_be, 64)}", ""])
            rows64.append(["Float64", "Big-Endian", f"{self._to_double(val64_be):.10g}", "IEEE-754 Double"])
            
            val64_le = (regs[3] << 48) | (regs[2] << 32) | (regs[1] << 16) | regs[0]
            rows64.append(["UInt64", "Little-Endian", f"{val64_le}", ""])
            rows64.append(["Float64", "Little-Endian", f"{self._to_double(val64_le):.10g}", ""])
            
            self._fill_table(self.tab_64.table, rows64)
        elif num_regs == 3:
            # Partial 64-bit - can show some interpretations
            rows64 = [["", "Partial 64-bit data", "", ""], ["", f"Available: {num_regs}/4 registers", "", ""]]
            self._fill_table(self.tab_64.table, rows64)
        else:
            # Not enough registers for 64-bit
            self._fill_table(self.tab_64.table, [["", "Not enough registers", "", ""]])

        # STRINGS / OTHERS TAB
        rows_other = []
        
        # ASCII (2 chars per register)
        chars = []
        for r in regs:
            chars.append(chr((r >> 8) & 0xFF))
            chars.append(chr(r & 0xFF))
            
        full_str = "".join([c if 32 <= ord(c) <= 126 else '.' for c in chars])
        rows_other.append(["String (ASCII)", full_str, "Regs interpret as chars"])
        
        # UNIX Timestamp (if we have at least 2 registers)
        if num_regs >= 2:
            ts_val = (regs[0] << 16) | regs[1]
            import datetime
            try:
                # Sane range for timestamp (1970 to 2100)
                if 0 < ts_val < 4102444800: 
                    dt = datetime.datetime.utcfromtimestamp(ts_val)
                    rows_other.append(["UNIX Timestamp", dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + " UTC", "Ref: 32-bit BE"])
            except:
                pass

        self._fill_table(self.tab_other.table, rows_other)


    def _fill_table(self, table, rows):
        table.setRowCount(0)
        table.setRowCount(len(rows))
        for i, row_data in enumerate(rows):
            for j, val in enumerate(row_data):
                table.setItem(i, j, QTableWidgetItem(str(val)))

    def _swap_bytes(self, u16):
        return ((u16 & 0xFF) << 8) | ((u16 >> 8) & 0xFF)

    def _to_signed(self, val, bits):
        if val & (1 << (bits - 1)):
            val -= (1 << bits)
        return val

    def _to_float(self, u32):
        import struct
        try:
            return struct.unpack('>f', u32.to_bytes(4, 'big'))[0]
        except:
            return 0.0

    def _to_double(self, u64):
        import struct
        try:
            return struct.unpack('>d', u64.to_bytes(8, 'big'))[0]
        except:
            return 0.0

    def _decode_bcd(self, val):
        # 0x1234 -> 1234
        # Just print hex basically, but check if valid digits
        s = f"{val:04X}"
        for c in s:
            if c not in "0123456789":
                return "Invalid BCD"
        return str(int(s))
