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
        
        # Raw Data View
        group_raw = QGroupBox("Raw Registers (Hex)")
        raw_layout = QHBoxLayout(group_raw)
        self.lbl_raw = QLabel("Waiting for data...")
        self.lbl_raw.setStyleSheet("font-family: monospace; font-size: 14px; font-weight: bold;")
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
        """Reads 4 registers starting from signal address."""
        try:
            protocol = self.device_manager.get_protocol(self.device_name)
            if not protocol:
                self.lbl_raw.setText("Error: Device not connected")
                return

            # Parse address
            parts = self.signal.address.split(':')
            if len(parts) != 3:
                self.lbl_raw.setText("Error: Invalid address format")
                return
                
            unit_id = int(parts[0])
            func_code = int(parts[1])
            start_addr = int(parts[2])
            
            # Decide function code for reading. 
            # If FC is 1 or 2 (Coils), we can't really do "register" inspection properly 
            # unless we read 16 coils? Let's stick to registers if possible.
            # If original was FC 3 or 4, use that.
            read_fc = func_code
            if func_code not in [3, 4]:
                # Attempt to use FC3 (Holding) by default if it was a Coil signal
                # This might fail if device doesn't support it, but Inspector is usually for registers.
                read_fc = 3
            
            # Use internal client if available to read block
            # Assuming ModbusTCPAdapter
            client = getattr(protocol, 'client', None)
            if not client or not protocol.connected:
                self.lbl_raw.setText("Error: Not connected to device")
                return

            # Read 4 registers (64 bits)
            count = 4
            result = None
            if read_fc == 4:
                result = client.read_input_registers(start_addr, count=count, device_id=unit_id)
            else:
                result = client.read_holding_registers(start_addr, count=count, device_id=unit_id)
            
            if result.isError():
                self.lbl_raw.setText(f"Read Error: {result}")
                return
            
            self.raw_registers = result.registers
            
            # Update Raw Display
            hex_strs = [f"[{i:04X}]" for i in self.raw_registers]
            self.lbl_raw.setText(" ".join(hex_strs))
            
            self._update_interpretations()
            
        except Exception as e:
            self.lbl_raw.setText(f"Error: {e}")

    def _update_interpretations(self):
        regs = self.raw_registers
        # Pad if we got fewer than 4 (e.g. end of memory)
        while len(regs) < 4:
            regs.append(0)
            
        # 16-BIT TAB
        # Only look at first register (Reg 0)
        r0 = regs[0]
        rows16 = []
        rows16.append(["UInt16", f"{r0}", "0 ... 65535"])
        rows16.append(["Int16", f"{self._to_signed(r0, 16)}", "-32768 ... 32767"])
        rows16.append(["Hex", f"0x{r0:04X}", ""])
        rows16.append(["Binary", f"{r0:016b}", "Bit mask"])
        # BCD
        rows16.append(["BCD (16-bit)", self._decode_bcd(r0), "0x1234 -> 1234"])
        self._fill_table(self.tab_16.table, rows16)

        # 32-BIT TAB
        # Uses Reg 0 and Reg 1
        r0, r1 = regs[0], regs[1]
        
        # Combinations
        # ABCD (Big Endian): High=r0, Low=r1
        # CDAB (Word Swap): High=r1, Low=r0
        # BADC (Byte Swap): Swap bytes in r0 and r1, then High=r0, Low=r1
        # DCBA (Byte+Word Swap): Swap bytes, then High=r1, Low=r0
        
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

        # 64-BIT TAB
        # Uses Reg 0, 1, 2, 3
        # Standard Big Endian: r0 r1 r2 r3
        val64_be = (regs[0] << 48) | (regs[1] << 32) | (regs[2] << 16) | regs[3]
        rows64 = []
        
        # Just creating a few common ones for brevity
        # Big Endian
        rows64.append(["UInt64", "Big-Endian", f"{val64_be}", ""])
        rows64.append(["Int64", "Big-Endian", f"{self._to_signed(val64_be, 64)}", ""])
        rows64.append(["Float64", "Big-Endian", f"{self._to_double(val64_be):.10g}", "IEEE-754 Double"])
        
        # Word Swapped (CDAB GHEF -> r1 r0 r3 r2) usually? 
        # Actually standard modbus "Word Swap" for 64 bit usually implies 32-bit words swapped?
        # Let's simple support Big Endian and "Little Endian" (reverse all registers) for now to hit main cases.
        
        val64_le = (regs[3] << 48) | (regs[2] << 32) | (regs[1] << 16) | regs[0]
        rows64.append(["UInt64", "Little-Endian", f"{val64_le}", ""])
        rows64.append(["Float64", "Little-Endian", f"{self._to_double(val64_le):.10g}", ""])

        self._fill_table(self.tab_64.table, rows64)
        
        # STRINGS / OTHERS TAB
        rows_other = []
        
        # ASCII (2 chars per register)
        chars = []
        for r in regs:
            chars.append(chr((r >> 8) & 0xFF))
            chars.append(chr(r & 0xFF))
            
        full_str = "".join([c if 32 <= ord(c) <= 126 else '.' for c in chars])
        rows_other.append(["String (ASCII)", full_str, "Regs interpret as chars"])
        
        # UNIX Timestamp (if 32-bit valid)
        # Try Big Endian UInt32 from first 2 regs
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
