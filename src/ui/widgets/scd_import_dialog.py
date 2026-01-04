from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QLabel, QMessageBox
from PySide6.QtCore import Qt
from typing import List
from src.core.scd_parser import SCDParser
from src.models.device_models import DeviceConfig, DeviceType

class SCDImportDialog(QDialog):
    """
    Dialog to select an SCD file, list found IEDs, and select which to import.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from SCD/SCL")
        self.resize(600, 400)
        
        self.layout = QVBoxLayout(self)
        
        # File Selection Block
        file_layout = QHBoxLayout()
        self.lbl_file = QLabel("No file selected")
        btn_browse = QPushButton("Browse SCD...")
        btn_browse.clicked.connect(self._browse_file)
        file_layout.addWidget(btn_browse)
        file_layout.addWidget(self.lbl_file)
        file_layout.addStretch()
        self.layout.addLayout(file_layout)
        
        # Table of IEDs
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "IP Address", "Access Point", "Select"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)
        
        # Select/Deselect All
        sel_layout = QHBoxLayout()
        btn_sel_all = QPushButton("Select All")
        btn_desel_all = QPushButton("Deselect All")
        btn_sel_all.clicked.connect(self._select_all)
        btn_desel_all.clicked.connect(self._deselect_all)
        sel_layout.addWidget(btn_sel_all)
        sel_layout.addWidget(btn_desel_all)
        sel_layout.addStretch()
        self.layout.addLayout(sel_layout)
        
        # Dialog Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
        self.scd_path = None
        self.parsed_ieds = []

    def _browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open SCL File", "", "SCL Files (*.scd *.cid *.icd *.xml)")
        if fname:
            self.scd_path = fname
            self.lbl_file.setText(fname)
            self._parse_and_list(fname)

    def _parse_and_list(self, path):
        parser = SCDParser(path)
        self.parsed_ieds = parser.extract_ieds_info()
        
        self.table.setRowCount(0)
        for ied in self.parsed_ieds:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Name
            self.table.setItem(row, 0, QTableWidgetItem(ied['name']))
            
            # IP
            self.table.setItem(row, 1, QTableWidgetItem(ied['ip']))
            
            # AP
            self.table.setItem(row, 2, QTableWidgetItem(ied.get('ap', '')))
            
            # Checkbox
            chk_item = QTableWidgetItem()
            # use correct Qt enums
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked) 
            self.table.setItem(row, 3, chk_item)

    def _select_all(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 3).setCheckState(Qt.Checked)

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 3).setCheckState(Qt.Unchecked)

    def get_selected_configs(self) -> List[DeviceConfig]:
        configs = []
        rows = self.table.rowCount()
        print(f"DEBUG: get_selected_configs called. Rows={rows}")
        for row in range(rows):
            chk_item = self.table.item(row, 3)
            state = chk_item.checkState()
            print(f"DEBUG: Row {row}, CheckState={state}")
            
            # Relaxed check: Accept any checked state
            if state != Qt.Unchecked:
                name = self.table.item(row, 0).text()
                ip = self.table.item(row, 1).text()
                # Port? Defaulting to 102
                
                configs.append(DeviceConfig(
                    name=name,
                    ip_address=ip,
                    port=102, # Todo: Parse OSI-PSEL for custom port?
                    device_type=DeviceType.IEC61850_IED,
                    scd_file_path=self.scd_path
                ))
        return configs
