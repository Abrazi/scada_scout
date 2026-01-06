from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QLabel, QMessageBox, QLineEdit
from PySide6.QtCore import Qt
from typing import List
import fnmatch
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
        
        # Filter Search
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter by Name, IP, or AP (use * for wildcard)")
        self.txt_filter.textChanged.connect(self._filter_table)
        self.layout.addWidget(self.txt_filter)

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
            self._parse_and_list_with_progress(fname)
    
    def _parse_and_list_with_progress(self, path):
        """Parse SCD file with progress feedback."""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        # Show progress dialog
        progress = QProgressDialog("Parsing SCD file...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Loading SCD")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        
        try:
            progress.setLabelText("Reading XML file...")
            progress.setValue(30)
            
            parser = SCDParser(path)
            
            progress.setLabelText("Extracting IED information...")
            progress.setValue(60)
            
            self.parsed_ieds = parser.extract_ieds_info()
            
            progress.setLabelText("Populating table...")
            progress.setValue(80)
            
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
                chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_item.setCheckState(Qt.Checked) 
                self.table.setItem(row, 3, chk_item)
            
            progress.setValue(100)
            
        except Exception as e:
            progress.close()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Parse Error", f"Failed to parse SCD file:\n{str(e)}")
        finally:
            progress.close()


    def _select_all(self):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 3).setCheckState(Qt.Checked)

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 3).setCheckState(Qt.Unchecked)

    def _filter_table(self, text):
        """Hides rows that do not match the filter text (glob)."""
        search = text.strip().lower()
        if not search:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return
            
        # User request: "* would be used for part of the search"
        # If user types "IED", checks if "ied" is in string.
        # If user types "*IED", checks if string ends with IED.
        # If user types "IED*", checks if string starts with IED.
        # If user types "*IED*", checks if IED is in string.
        
        # Check if explicit wildcard used
        use_glob = '*' in search or '?' in search
        
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            ip_item = self.table.item(row, 1)
            ap_item = self.table.item(row, 2)
            
            name = name_item.text().lower() if name_item else ""
            ip = ip_item.text().lower() if ip_item else ""
            ap = ap_item.text().lower() if ap_item else ""
            
            match = False
            if use_glob:
                # fnmatch requires the pattern to match the ENTIRE string
                if fnmatch.fnmatch(name, search) or fnmatch.fnmatch(ip, search) or fnmatch.fnmatch(ap, search):
                    match = True
            else:
                # Standard substring search
                if search in name or search in ip or search in ap:
                    match = True
                    
            self.table.setRowHidden(row, not match)

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
