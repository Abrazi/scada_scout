from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                 QTableWidgetItem, QHeaderView, QSpinBox, QLabel, 
                                 QPushButton, QComboBox, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import logging
from typing import Optional
from src.models.device_models import ModbusDataType, ModbusEndianness
from src.protocols.modbus.register_mapping import decode_mapped_value

logger = logging.getLogger(__name__)

class ModbusInspectorDialog(QDialog):
    """
    Dialog to inspect Modbus registers in all possible formats simultaneously.
    Useful for figuring out data types of unknown devices.
    """
    def __init__(self, device_name, adapter, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.adapter = adapter
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._inspect_data)
        self.setWindowTitle(f"Modbus Data Inspector - {device_name}")
        self.resize(850, 700)
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Address controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Start Address:"))
        self.spin_address = QSpinBox()
        self.spin_address.setRange(0, 65535)
        self.spin_address.setValue(0)
        ctrl_layout.addWidget(self.spin_address)
        
        ctrl_layout.addWidget(QLabel("Function Code:"))
        self.combo_fc = QComboBox()
        self.combo_fc.addItem("1: Read Coils", 1)
        self.combo_fc.addItem("2: Read Discrete Inputs", 2)
        self.combo_fc.addItem("3: Read Holding Registers", 3)
        self.combo_fc.addItem("4: Read Input Registers", 4)
        self.combo_fc.setCurrentIndex(2) # Default to Holdings
        ctrl_layout.addWidget(self.combo_fc)
        
        self.btn_poll = QPushButton("Read & Inspect")
        self.btn_poll.clicked.connect(self._inspect_data)
        ctrl_layout.addWidget(self.btn_poll)
        
        self.btn_auto = QPushButton("Auto Update")
        self.btn_auto.setCheckable(True)
        self.btn_auto.toggled.connect(self._toggle_auto)
        ctrl_layout.addWidget(self.btn_auto)
        
        layout.addLayout(ctrl_layout)
        
        # Help label
        layout.addWidget(QLabel("Showing all possible interpretations for the registers starting at this address:"))
        
        # Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Data Type", "Endianness / Byte Order", "Interpreted Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Bottom info
        self.lbl_raw = QLabel("Raw Data: []")
        self.lbl_raw.setProperty("class", "code")
        layout.addWidget(self.lbl_raw)
        
        self.lbl_bits = QLabel("Bits: ")
        self.lbl_bits.setProperty("class", "code")
        layout.addWidget(self.lbl_bits)

    def _set_button_class(self, button: QPushButton, class_name: Optional[str]):
        if class_name:
            button.setProperty("class", class_name)
        else:
            button.setProperty("class", "")
        button.style().unpolish(button)
        button.style().polish(button)
        
    def _toggle_auto(self, checked):
        if checked:
            self.timer.start(1000)
            self.btn_auto.setText("Stop Auto")
            self._set_button_class(self.btn_auto, "danger")
        else:
            self.timer.stop()
            self.btn_auto.setText("Auto Update")
            self._set_button_class(self.btn_auto, None)

    def _inspect_data(self):
        """Poll raw registers and run all decoders"""
        if not self.adapter or not self.adapter.connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to the device first.")
            return
            
        addr = self.spin_address.value()
        fc = self.combo_fc.currentData()
        unit_id = self.adapter.unit_id
        
        # We need up to 4 registers for 64-bit types
        try:
            if fc == 1:
                result = self.adapter.client.read_coils(addr, count=16, device_id=unit_id)
            elif fc == 2:
                result = self.adapter.client.read_discrete_inputs(addr, count=16, device_id=unit_id)
            elif fc == 3:
                result = self.adapter.client.read_holding_registers(addr, count=4, device_id=unit_id)
            else:
                result = self.adapter.client.read_input_registers(addr, count=4, device_id=unit_id)
                
            if result.isError():
                if not self.timer.isActive():
                    QMessageBox.critical(self, "Read Error", f"Failed to read data: {result}")
                return
                
            if fc in [1, 2]:
                raw_data = result.bits[:16]
                self.lbl_raw.setText(f"Raw Bits: {raw_data}")
                self.lbl_bits.setText("")
                self._fill_bit_table(raw_data)
            else:
                raw_regs = result.registers
                self.lbl_raw.setText(f"Raw Registers: {raw_regs}")
                # Show binary for first register
                if raw_regs:
                    self.lbl_bits.setText(f"Reg {addr} Binary: {raw_regs[0]:016b}")
                self._fill_table(raw_regs)
            
        except Exception as e:
            logger.error(f"Inspector poll error: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def _fill_table(self, raw_regs):
        """Populate the table with all decodings"""
        self.table.setRowCount(0)
        
        # Types that use 1 register
        single_types = [ModbusDataType.INT16, ModbusDataType.UINT16, ModbusDataType.HEX16, ModbusDataType.BINARY16]
        # Types that use 2 registers
        double_types = [ModbusDataType.INT32, ModbusDataType.UINT32, ModbusDataType.FLOAT32, ModbusDataType.BCD32]
        # Types that use 4 registers
        quad_types = [ModbusDataType.INT64, ModbusDataType.UINT64, ModbusDataType.FLOAT64]
        
        # Standard Endianness patterns
        endianness_list = [
            ModbusEndianness.BIG_ENDIAN,
            ModbusEndianness.LITTLE_ENDIAN,
            ModbusEndianness.BIG_ENDIAN_BYTE_SWAP,
            ModbusEndianness.LITTLE_ENDIAN_BYTE_SWAP
        ]

        # 1-register types (endianness doesn't really apply to single word except byte swap, but we show raw)
        for dtype in single_types:
            self._add_row(dtype, ModbusEndianness.BIG_ENDIAN, raw_regs[:1])
            # Only 16-bit byte swap makes sense as variation
            self._add_row(dtype, ModbusEndianness.BIG_ENDIAN_BYTE_SWAP, raw_regs[:1])

        # 2-register types
        for dtype in double_types:
            for end in endianness_list:
                self._add_row(dtype, end, raw_regs[:2])

        # 4-register types
        for dtype in quad_types:
            for end in endianness_list:
                self._add_row(dtype, end, raw_regs[:4])

    def _add_row(self, dtype, end, subset_regs):
        if not subset_regs: return
        
        val = decode_mapped_value(subset_regs, dtype, end)
        
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(dtype.name))
        self.table.setItem(row, 1, QTableWidgetItem(end.value))
        
        val_item = QTableWidgetItem(str(val))
        if isinstance(val, (int, float)):
             font = val_item.font()
             font.setBold(True)
             val_item.setFont(font)
        self.table.setItem(row, 2, val_item)

    def _fill_bit_table(self, bits):
        """Populate table for bit-based function codes"""
        self.table.setRowCount(0)
        for i, b in enumerate(bits):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f"Bit {i}"))
            self.table.setItem(row, 1, QTableWidgetItem("N/A"))
            self.table.setItem(row, 2, QTableWidgetItem("ON" if b else "OFF"))
