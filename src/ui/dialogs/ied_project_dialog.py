"""
IED Project Dialog - UI for loading SCD files and MSS projects.

Provides a user-friendly interface for:
- Loading SCD files and extracting IEDs
- Configuring instantiation options
- Saving/loading MSS projects
"""

import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QLineEdit, QCheckBox, QGroupBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressDialog
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from typing import Optional

logger = logging.getLogger(__name__)


class IEDProjectWorker(QThread):
    """Worker thread for loading/processing IED projects."""
    progress_update = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(self, orchestrator, operation, **kwargs):
        super().__init__()
        self.orchestrator = orchestrator
        self.operation = operation
        self.kwargs = kwargs
        
    def run(self):
        try:
            if self.operation == 'load_scd':
                self.progress_update.emit("Parsing SCD file...")
                success = self.orchestrator.load_from_scd(
                    self.kwargs['scd_path'],
                    self.kwargs.get('project_name'),
                    self.kwargs.get('subnet_name')
                )
                if success:
                    self.finished.emit(True, f"Loaded {len(self.orchestrator.ied_definitions)} IED(s)")
                else:
                    self.finished.emit(False, "Failed to load SCD")
                    
            elif self.operation == 'instantiate':
                self.progress_update.emit("Instantiating IED servers...")
                success = self.orchestrator.instantiate_all_ieds(
                    auto_connect=self.kwargs.get('auto_connect', True),
                    start_plc=self.kwargs.get('start_plc', True)
                )
                if success:
                    self.finished.emit(True, "All IEDs instantiated successfully")
                else:
                    self.finished.emit(False, "Some IEDs failed to instantiate")
                    
            elif self.operation == 'load_project':
                self.progress_update.emit("Loading MSS project...")
                success = self.orchestrator.load_project(
                    self.kwargs['mss_path'],
                    auto_connect=self.kwargs.get('auto_connect', True),
                    start_plc=self.kwargs.get('start_plc', True)
                )
                if success:
                    self.finished.emit(True, "Project loaded successfully")
                else:
                    self.finished.emit(False, "Failed to load project")
                    
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            self.finished.emit(False, str(e))


class IEDProjectDialog(QDialog):
    """
    Dialog for IED project management.
    
    Allows users to:
    - Load SCD files
    - Preview extracted IEDs
    - Configure instantiation options
    - Create IED servers with PLC programs
    - Save/load MSS projects
    """
    
    def __init__(self, orchestrator, parent=None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.worker = None
        
        self.setWindowTitle("IED Project Manager")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("IED Project Manager")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Load IEC 61850 SCD files to automatically create IED servers with PLC programs.\n"
            "Or load existing .mss project files to restore complete simulation scenarios."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # SCD/MSS File Selection Group
        file_group = QGroupBox("1. Select File")
        file_layout = QVBoxLayout()
        
        # SCD file row
        scd_row = QHBoxLayout()
        scd_row.addWidget(QLabel("SCD File:"))
        self.scd_path_edit = QLineEdit()
        self.scd_path_edit.setPlaceholderText("Path to .scd file...")
        scd_row.addWidget(self.scd_path_edit, 1)
        browse_scd_btn = QPushButton("Browse...")
        browse_scd_btn.clicked.connect(self._browse_scd)
        scd_row.addWidget(browse_scd_btn)
        load_scd_btn = QPushButton("Load SCD")
        load_scd_btn.clicked.connect(self._load_scd)
        scd_row.addWidget(load_scd_btn)
        file_layout.addLayout(scd_row)
        
        # MSS file row
        mss_row = QHBoxLayout()
        mss_row.addWidget(QLabel("MSS Project:"))
        self.mss_path_edit = QLineEdit()
        self.mss_path_edit.setPlaceholderText("Path to .mss project file...")
        mss_row.addWidget(self.mss_path_edit, 1)
        browse_mss_btn = QPushButton("Browse...")
        browse_mss_btn.clicked.connect(self._browse_mss)
        mss_row.addWidget(browse_mss_btn)
        load_mss_btn = QPushButton("Load Project")
        load_mss_btn.clicked.connect(self._load_mss)
        mss_row.addWidget(load_mss_btn)
        file_layout.addLayout(mss_row)
        
        # SubNetwork selection row (initially hidden)
        self.subnet_row = QHBoxLayout()
        self.subnet_row.addWidget(QLabel("SubNetwork:"))
        
        from PySide6.QtWidgets import QComboBox
        self.subnet_combo = QComboBox()
        self.subnet_combo.setToolTip("Select which SubNetwork to use for IP addresses")
        self.subnet_row.addWidget(self.subnet_combo, 1)
        
        reload_btn = QPushButton("Reload with Selected Subnet")
        reload_btn.clicked.connect(self._reload_with_subnet)
        self.subnet_row.addWidget(reload_btn)
        
        self.subnet_widget = QWidget()
        self.subnet_widget.setLayout(self.subnet_row)
        self.subnet_widget.setVisible(False)
        file_layout.addWidget(self.subnet_widget)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # IED Preview Group
        preview_group = QGroupBox("2. Preview IEDs")
        preview_layout = QVBoxLayout()
        
        self.ied_table = QTableWidget()
        self.ied_table.setColumnCount(4)
        self.ied_table.setHorizontalHeaderLabels(["IED Name", "Description", "IP Address", "Port"])
        self.ied_table.horizontalHeader().setStretchLastSection(False)
        self.ied_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ied_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ied_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ied_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.ied_table.setSelectionBehavior(QTableWidget.SelectRows)
        preview_layout.addWidget(self.ied_table)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Options Group
        options_group = QGroupBox("3. Instantiation Options")
        options_layout = QVBoxLayout()
        
        self.auto_connect_check = QCheckBox("Auto-connect IED servers after creation")
        self.auto_connect_check.setChecked(True)
        options_layout.addWidget(self.auto_connect_check)
        
        self.start_plc_check = QCheckBox("Auto-start PLC programs")
        self.start_plc_check.setChecked(True)
        options_layout.addWidget(self.start_plc_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        self.instantiate_btn = QPushButton("Create IED Servers")
        self.instantiate_btn.setEnabled(False)
        self.instantiate_btn.clicked.connect(self._instantiate_ieds)
        button_layout.addWidget(self.instantiate_btn)
        
        button_layout.addStretch()
        
        self.save_project_btn = QPushButton("Save as MSS Project...")
        self.save_project_btn.setEnabled(False)
        self.save_project_btn.clicked.connect(self._save_mss)
        button_layout.addWidget(self.save_project_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
    def _browse_scd(self):
        """Browse for SCD file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SCD File",
            "",
            "SCD Files (*.scd);;All Files (*)"
        )
        if file_path:
            self.scd_path_edit.setText(file_path)
            
    def _browse_mss(self):
        """Browse for MSS project file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MSS Project",
            "",
            "MSS Project Files (*.mss);;All Files (*)"
        )
        if file_path:
            self.mss_path_edit.setText(file_path)
            
    def _load_scd(self):
        """Load and parse SCD file."""
        scd_path = self.scd_path_edit.text().strip()
        if not scd_path:
            QMessageBox.warning(self, "No File", "Please select an SCD file")
            return
            
        if not Path(scd_path).exists():
            QMessageBox.warning(self, "File Not Found", f"File not found: {scd_path}")
            return
        
        # Get selected subnet (if any)
        selected_subnet = None
        if self.subnet_widget.isVisible() and self.subnet_combo.currentIndex() >= 0:
            selected_subnet = self.subnet_combo.currentData()
            
        # Show progress dialog
        progress = QProgressDialog("Loading SCD file...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        # Create worker
        project_name = Path(scd_path).stem
        self.worker = IEDProjectWorker(
            self.orchestrator,
            'load_scd',
            scd_path=scd_path,
            project_name=project_name,
            subnet_name=selected_subnet
        )
        self.worker.progress_update.connect(lambda msg: progress.setLabelText(msg))
        self.worker.finished.connect(lambda success, msg: self._on_scd_loaded(success, msg, progress))
        self.worker.start()
        
    def _reload_with_subnet(self):
        """Reload SCD with selected subnet."""
        if not self.scd_path_edit.text().strip():
            QMessageBox.warning(self, "No File", "Please load an SCD file first")
            return
        self._load_scd()
        
    def _on_scd_loaded(self, success: bool, message: str, progress: QProgressDialog):
        """Handle SCD load completion."""
        progress.close()
        
        if success:
            self.status_label.setText(f"✓ {message}")
            
            # Check for multiple SubNetworks
            subnets = self.orchestrator.get_available_subnets()
            
            if len(subnets) > 1:
                # Multiple subnets - show selection UI
                self.subnet_combo.clear()
                for subnet_name, ied_count in subnets:
                    self.subnet_combo.addItem(
                        f"{subnet_name} ({ied_count} IEDs)", 
                        subnet_name
                    )
                self.subnet_widget.setVisible(True)
                
                # Show info message
                QMessageBox.information(
                    self,
                    "Multiple SubNetworks Detected",
                    f"This SCD file contains {len(subnets)} SubNetworks.\n\n"
                    "Please select which SubNetwork to use for IP addresses.\n"
                    "Each IED may have different IPs in different SubNetworks."
                )
            else:
                # Single or no subnet - hide selection
                self.subnet_widget.setVisible(False)
            
            self._update_ied_table()
            self.instantiate_btn.setEnabled(True)
        else:
            QMessageBox.critical(self, "Load Failed", message)
            self.status_label.setText(f"✗ {message}")
            
    def _update_ied_table(self):
        """Update IED preview table."""
        ieds = self.orchestrator.ied_definitions
        
        self.ied_table.setRowCount(len(ieds))
        
        for row, ied in enumerate(ieds):
            # IED Name
            self.ied_table.setItem(row, 0, QTableWidgetItem(ied.name))
            
            # Description
            desc = f"{ied.desc} [{ied.manufacturer}]" if ied.manufacturer else ied.desc
            self.ied_table.setItem(row, 1, QTableWidgetItem(desc))
            
            # IP Address (with subnet name if available)
            if ied.network_config:
                ip_text = ied.network_config.ip_address
                if ied.network_config.subnet_name:
                    ip_text += f" ({ied.network_config.subnet_name})"
                self.ied_table.setItem(row, 2, QTableWidgetItem(ip_text))
            else:
                self.ied_table.setItem(row, 2, QTableWidgetItem("NO_IP"))
            
            # Port
            port = str(ied.network_config.port) if ied.network_config else "102"
            self.ied_table.setItem(row, 3, QTableWidgetItem(port))
            
    def _instantiate_ieds(self):
        """Instantiate all IEDs as servers."""
        if not self.orchestrator.ied_definitions:
            QMessageBox.warning(self, "No IEDs", "No IEDs loaded")
            return
            
        # Confirm
        count = len(self.orchestrator.ied_definitions)
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Create {count} IED server(s) with PLC programs?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Show progress
        progress = QProgressDialog("Creating IED servers...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        # Create worker
        self.worker = IEDProjectWorker(
            self.orchestrator,
            'instantiate',
            auto_connect=self.auto_connect_check.isChecked(),
            start_plc=self.start_plc_check.isChecked()
        )
        self.worker.progress_update.connect(lambda msg: progress.setLabelText(msg))
        self.worker.finished.connect(lambda success, msg: self._on_instantiation_done(success, msg, progress))
        self.worker.start()
        
    def _on_instantiation_done(self, success: bool, message: str, progress: QProgressDialog):
        """Handle instantiation completion."""
        progress.close()
        
        if success:
            self.status_label.setText(f"✓ {message}")
            self.save_project_btn.setEnabled(True)
            QMessageBox.information(
                self,
                "Success",
                f"{message}\n\nIED servers are now running in Device Explorer.\n"
                "PLC programs can be edited in the PLC IDE."
            )
        else:
            QMessageBox.warning(self, "Partial Success", message)
            self.status_label.setText(f"⚠ {message}")
            self.save_project_btn.setEnabled(True)  # Allow saving partial results
            
    def _load_mss(self):
        """Load MSS project file."""
        mss_path = self.mss_path_edit.text().strip()
        if not mss_path:
            QMessageBox.warning(self, "No File", "Please select an MSS project file")
            return
            
        if not Path(mss_path).exists():
            QMessageBox.warning(self, "File Not Found", f"File not found: {mss_path}")
            return
            
        # Show progress
        progress = QProgressDialog("Loading MSS project...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        # Create worker
        self.worker = IEDProjectWorker(
            self.orchestrator,
            'load_project',
            mss_path=mss_path,
            auto_connect=self.auto_connect_check.isChecked(),
            start_plc=self.start_plc_check.isChecked()
        )
        self.worker.progress_update.connect(lambda msg: progress.setLabelText(msg))
        self.worker.finished.connect(lambda success, msg: self._on_project_loaded(success, msg, progress))
        self.worker.start()
        
    def _on_project_loaded(self, success: bool, message: str, progress: QProgressDialog):
        """Handle project load completion."""
        progress.close()
        
        if success:
            self.status_label.setText(f"✓ {message}")
            QMessageBox.information(
                self,
                "Success",
                f"{message}\n\nAll devices have been restored."
            )
            self.accept()  # Close dialog
        else:
            QMessageBox.critical(self, "Load Failed", message)
            self.status_label.setText(f"✗ {message}")
            
    def _save_mss(self):
        """Save project as MSS file."""
        if not self.orchestrator.mss_manager.current_project:
            QMessageBox.warning(self, "No Project", "No project to save")
            return
            
        # Suggest filename
        suggested_name = self.orchestrator.mss_manager.current_project.metadata.project_name
        if self.orchestrator.current_scd_path:
            suggested_name = Path(self.orchestrator.current_scd_path).stem
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save MSS Project",
            f"{suggested_name}.mss",
            "MSS Project Files (*.mss);;All Files (*)"
        )
        
        if file_path:
            if self.orchestrator.save_project(file_path):
                self.status_label.setText(f"✓ Project saved: {Path(file_path).name}")
                QMessageBox.information(
                    self,
                    "Success",
                    f"Project saved successfully:\n{file_path}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Save Failed",
                    "Failed to save project. Check logs for details."
                )
