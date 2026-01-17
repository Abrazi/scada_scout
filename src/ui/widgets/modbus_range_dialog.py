from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                                 QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, 
                                 QDialogButtonBox, QLabel, QGroupBox, QTableWidget, 
                                 QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFileDialog)
import csv
from PySide6.QtCore import Qt
from src.models.device_models import ModbusDataType, ModbusEndianness, ModbusRegisterMap, DeviceType

class ModbusRangeDialog(QDialog):
    """
    Dialog for defining Modbus register ranges (Register Maps)
    """
    def __init__(self, device_config, parent=None):
        super().__init__(parent)
        self.device_config = device_config
        self.setWindowTitle(f"Configure Modbus Ranges - {device_config.name}")
        self.resize(600, 450)
        
        self.register_maps = list(device_config.modbus_register_maps)
        
        self._setup_ui()
        self._load_maps()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tools
        tools_layout = QHBoxLayout()
        btn_import = QPushButton("Import CSV...")
        btn_import.clicked.connect(self._import_csv)
        btn_export = QPushButton("Export CSV...")
        btn_export.clicked.connect(self._export_csv)
        tools_layout.addWidget(btn_import)
        tools_layout.addWidget(btn_export)
        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        layout.addWidget(QLabel("Defined Ranges:"))
        
        # Current maps table
        self.table_maps = QTableWidget()
        self.table_maps.setColumnCount(5)
        self.table_maps.setHorizontalHeaderLabels(["Group Name", "Function", "Start", "Count", "Type"])
        self.table_maps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_maps.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table_maps)
        
        # General Settings
        settings_group = QGroupBox("General Settings")
        settings_layout = QFormLayout(settings_group)
        
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 60.0)
        self.spin_interval.setValue(self.device_config.poll_interval)
        self.spin_interval.setSuffix(" sec")
        settings_layout.addRow("Poll Interval:", self.spin_interval)
        
        layout.addWidget(settings_group)
        
        # New Range Group
        new_group = QGroupBox("Add/Edit Range")
        new_layout = QFormLayout(new_group)
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Group name (e.g. Temperatures)")
        new_layout.addRow("Group Name:", self.txt_name)
        
        self.combo_function = QComboBox()
        self.combo_function.addItem("1: Read Coils", 1)
        self.combo_function.addItem("2: Read Discrete Inputs", 2)
        self.combo_function.addItem("3: Read Holding Registers", 3)
        self.combo_function.addItem("4: Read Input Registers", 4)
        new_layout.addRow("Function:", self.combo_function)
        
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 65535)
        new_layout.addRow("Start Address:", self.spin_start)
        
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 125) # Modbus limit for registers
        self.spin_count.setValue(10)
        new_layout.addRow("Count:", self.spin_count)
        
        self.combo_type = QComboBox()
        for dtype in ModbusDataType:
            self.combo_type.addItem(dtype.value, dtype)
        self.combo_type.setCurrentText("UINT16")
        new_layout.addRow("Data Type:", self.combo_type)
        
        self.combo_endian = QComboBox()
        for endian in ModbusEndianness:
            self.combo_endian.addItem(endian.value, endian)
        new_layout.addRow("Endianness:", self.combo_endian)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Range")
        self.btn_add.clicked.connect(self._add_map)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._remove_map)
        btn_layout.addWidget(self.btn_remove)
        
        new_layout.addRow(btn_layout)
        layout.addWidget(new_group)
        
        # Dialog Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _load_maps(self):
        self.table_maps.setRowCount(0)
        for m in self.register_maps:
            row = self.table_maps.rowCount()
            self.table_maps.insertRow(row)
            
            func_text = {1: "Coils", 2: "Discrete", 3: "Holding", 4: "Input"}.get(m.function_code, str(m.function_code))
            
            self.table_maps.setItem(row, 0, QTableWidgetItem(m.name_prefix))
            self.table_maps.setItem(row, 1, QTableWidgetItem(func_text))
            self.table_maps.setItem(row, 2, QTableWidgetItem(str(m.start_address)))
            self.table_maps.setItem(row, 3, QTableWidgetItem(str(m.count)))
            self.table_maps.setItem(row, 4, QTableWidgetItem(m.data_type.value))

    def _add_map(self):
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a group name")
            return
            
        new_map = ModbusRegisterMap(
            start_address=self.spin_start.value(),
            count=self.spin_count.value(),
            function_code=self.combo_function.currentData(),
            data_type=self.combo_type.currentData(),
            name_prefix=name,
            endianness=self.combo_endian.currentData(),
            description=f"{self.combo_function.currentText()} range"
        )
        
        self.register_maps.append(new_map)
        self._load_maps()
        self.txt_name.clear()

    def _remove_map(self):
        current_row = self.table_maps.currentRow()
        if current_row >= 0:
            self.register_maps.pop(current_row)
            self._load_maps()

    def get_register_maps(self):
        return self.register_maps

    def _export_csv(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Export Register Map", "modbus_map.csv", "CSV Files (*.csv)")
        if not fname: return

        try:
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Group Name", "Function Code", "Start Address", "Count", "Data Type", "Endianness", "Scale", "Offset"])
                
                for m in self.register_maps:
                    writer.writerow([
                        m.name_prefix,
                        m.function_code,
                        m.start_address,
                        m.count,
                        m.data_type.value,
                        m.endianness.value,
                        m.scale,
                        m.offset
                    ])
            QMessageBox.information(self, "Success", f"Exported {len(self.register_maps)} ranges.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _import_csv(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Import Register Map", "", "CSV Files (*.csv)")
        if not fname: return

        try:
            new_maps = []
            with open(fname, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Parse Enum values
                    dtype = ModbusDataType.UINT16
                    for d in ModbusDataType:
                        if d.value == row["Data Type"]:
                            dtype = d
                            break
                    
                    endian = ModbusEndianness.BIG_ENDIAN
                    for e in ModbusEndianness:
                        if e.value == row["Endianness"]:
                            endian = e
                            break
                            
                    new_maps.append(ModbusRegisterMap(
                        name_prefix=row["Group Name"],
                        function_code=int(row["Function Code"]),
                        start_address=int(row["Start Address"]),
                        count=int(row["Count"]),
                        data_type=dtype,
                        endianness=endian,
                        scale=float(row.get("Scale", 1.0)),
                        offset=float(row.get("Offset", 0.0))
                    ))
            
            if new_maps:
                reply = QMessageBox.question(self, "Import", "Replace existing maps?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.register_maps = new_maps
                else:
                    self.register_maps.extend(new_maps)
                self._load_maps()
                QMessageBox.information(self, "Success", f"Imported {len(new_maps)} ranges.")
                
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")

    def accept(self):
        """Save settings and close"""
        self.device_config.poll_interval = self.spin_interval.value()
        self.device_config.modbus_register_maps = self.register_maps
        super().accept()
