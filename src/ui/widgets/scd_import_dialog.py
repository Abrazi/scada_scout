from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QLabel, QMessageBox, QLineEdit, QComboBox
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
        """Parse SCD file with progress feedback using background thread."""
        from PySide6.QtWidgets import QProgressDialog, QApplication
        from src.core.workers import SCDParseWorker
        
        # Setup Progress Dialog
        self.progress_dialog = QProgressDialog("Reading SCD file...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Loading SCD")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        # Force show immediately
        self.progress_dialog.show()
        QApplication.processEvents()
        
        # Setup Worker (SCDParseWorker is now a QThread)
        self.worker = SCDParseWorker(path)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished_parsing.connect(self._on_parse_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        
        self.worker.start()
        
    def _update_progress(self, msg, val):
        self.progress_dialog.setLabelText(msg)
        self.progress_dialog.setValue(val)

    def _on_parse_finished(self, ieds, error_msg):
        self.progress_dialog.close()
        
        if error_msg:
             QMessageBox.critical(self, "Parse Error", f"Failed to parse SCD file:\n{error_msg}")
             return

        self.parsed_ieds = ieds
        self._populate_table()

    def _populate_table(self):
        from PySide6.QtWidgets import QComboBox
        
        self.table.setRowCount(0)
        # We need to sort or filter?
        
        for ied in self.parsed_ieds:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Name
            self.table.setItem(row, 0, QTableWidgetItem(ied['name']))
            
            # IP / Access Point Selection
            # If multiple IPs, use ComboBox
            ips = ied.get('ips', [])
            
            if not ips:
                 self.table.setItem(row, 1, QTableWidgetItem("N/A"))
                 self.table.setItem(row, 2, QTableWidgetItem("N/A"))
            elif len(ips) == 1:
                 # Simple Text
                 ip_info = ips[0]
                 self.table.setItem(row, 1, QTableWidgetItem(ip_info['ip']))
                 self.table.setItem(row, 2, QTableWidgetItem(f"{ip_info['ap']} ({ip_info['subnetwork']})"))
            else:
                 # ComboBox
                 combo = QComboBox()
                 for ip_info in ips:
                     # Item Data: IP, Item Text: IP - AP (SubNet)
                     desc = f"{ip_info['ip']} - {ip_info['ap']} ({ip_info['subnetwork']})"
                     combo.addItem(desc, ip_info) # Store full dict in userData
                 
                 self.table.setCellWidget(row, 1, combo)
                 self.table.setItem(row, 2, QTableWidgetItem("Multiple (Select IP)"))

            # Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked) 
            self.table.setItem(row, 3, chk_item)


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
            
            ip_text = ""
            combo = self.table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                 ip_text = combo.currentText().lower()
            elif ip_item:
                 ip_text = ip_item.text().lower()
            
            name_text = name_item.text().lower() if name_item else ""
            ap_text = ap_item.text().lower() if ap_item else ""
            
            match = False
            if use_glob:
                import fnmatch
                if fnmatch.fnmatch(name_text, search): match = True
                elif fnmatch.fnmatch(ip_text, search): match = True
                elif fnmatch.fnmatch(ap_text, search): match = True
            else:
                if search in name_text: match = True
                elif search in ip_text: match = True
                elif search in ap_text: match = True
                
            self.table.setRowHidden(row, not match)


    def get_selected_configs(self) -> List[DeviceConfig]:
        configs = []
        rows = self.table.rowCount()
        
        for row in range(rows):
            chk_item = self.table.item(row, 3)
            state = chk_item.checkState()
            
            if state != Qt.Unchecked:
                name = self.table.item(row, 0).text()
                
                ip = "127.0.0.1"
                # Check if it's a combobox
                widget = self.table.cellWidget(row, 1)
                if widget and isinstance(widget, QComboBox): # Updated import check if needed
                     data = widget.currentData() # This is the ip_info dict
                     ip = data['ip']
                else:
                     ip_item = self.table.item(row, 1)
                     ip = ip_item.text() if ip_item else "127.0.0.1"

                configs.append(DeviceConfig(
                    name=name,
                    ip_address=ip,
                    port=102, 
                    device_type=DeviceType.IEC61850_IED,
                    scd_file_path=self.scd_path
                ))
        return configs
