from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                QTableWidgetItem, QPushButton, QSpinBox, QLabel,
                                QHeaderView, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal as QtSignal
from src.core.watch_list_manager import WatchListManager, WatchedSignal
from src.models.device_models import Signal, SignalQuality
import logging

logger = logging.getLogger(__name__)

class WatchListWidget(QWidget):
    """
    Widget for displaying and managing watched signals.
    """
    # Signals
    export_requested = QtSignal()
    
    def __init__(self, watch_list_manager: WatchListManager, parent=None):
        super().__init__(parent)
        self.watch_manager = watch_list_manager
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        
        # Controls row
        controls_layout = QHBoxLayout()
        
        # Poll interval control
        controls_layout.addWidget(QLabel("Poll Interval (ms):"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(100, 60000)
        self.interval_spinbox.setValue(self.watch_manager.get_poll_interval())
        self.interval_spinbox.setSingleStep(100)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        controls_layout.addWidget(self.interval_spinbox)
        
        controls_layout.addStretch()
        
        # Clear button
        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        controls_layout.addWidget(self.btn_clear)
        
        # Export button
        self.btn_export = QPushButton("Export to Excel...")
        self.btn_export.clicked.connect(self._on_export_clicked)
        controls_layout.addWidget(self.btn_export)
        
        layout.addLayout(controls_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Device", "Signal Name", "Address", "Value", "Quality", "Timestamp"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Context menu for table
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
    def _connect_signals(self):
        """Connect watch manager signals."""
        self.watch_manager.signal_updated.connect(self._on_signal_updated)
        self.watch_manager.watch_list_changed.connect(self._refresh_table)
        
    def _refresh_table(self):
        """Rebuild the table from watch list."""
        self.table.setRowCount(0)
        
        for watched in self.watch_manager.get_all_watched():
            self._add_signal_row(watched)
    
    def _add_signal_row(self, watched: WatchedSignal):
        """Add a row for a watched signal."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Device
        self.table.setItem(row, 0, QTableWidgetItem(watched.device_name))
        
        # Signal Name
        self.table.setItem(row, 1, QTableWidgetItem(watched.signal.name))
        
        # Address
        self.table.setItem(row, 2, QTableWidgetItem(watched.signal.address))
        
        # Value
        value_str = str(watched.signal.value) if watched.signal.value is not None else "--"
        self.table.setItem(row, 3, QTableWidgetItem(value_str))
        
        # Quality
        quality_item = QTableWidgetItem(watched.signal.quality.value)
        # Color code by quality
        if watched.signal.quality == SignalQuality.GOOD:
            quality_item.setBackground(Qt.green)
        elif watched.signal.quality == SignalQuality.INVALID:
            quality_item.setBackground(Qt.red)
        else:
            quality_item.setBackground(Qt.gray)
        self.table.setItem(row, 4, quality_item)
        
        # Timestamp
        ts_str = watched.signal.timestamp.strftime("%H:%M:%S") if watched.signal.timestamp else "--"
        self.table.setItem(row, 5, QTableWidgetItem(ts_str))
        
        # Store watch_id in row data
        self.table.item(row, 0).setData(Qt.UserRole, watched.watch_id)
    
    def _on_signal_updated(self, watch_id: str, signal: Signal):
        """Update a signal's display when its value changes."""
        # Find the row
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == watch_id:
                # Update value
                value_str = str(signal.value) if signal.value is not None else "--"
                self.table.item(row, 3).setText(value_str)
                
                # Update quality
                quality_item = self.table.item(row, 4)
                quality_item.setText(signal.quality.value)
                if signal.quality == SignalQuality.GOOD:
                    quality_item.setBackground(Qt.green)
                elif signal.quality == SignalQuality.INVALID:
                    quality_item.setBackground(Qt.red)
                else:
                    quality_item.setBackground(Qt.gray)
                
                # Update timestamp
                ts_str = signal.timestamp.strftime("%H:%M:%S") if signal.timestamp else "--"
                self.table.item(row, 5).setText(ts_str)
                break
    
    def _on_interval_changed(self, value: int):
        """Handle poll interval change."""
        self.watch_manager.set_poll_interval(value)
    
    def _on_clear_clicked(self):
        """Handle clear all button."""
        reply = QMessageBox.question(
            self, 
            "Clear Watch List",
            "Remove all signals from watch list?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.watch_manager.clear_all()
    
    def _on_export_clicked(self):
        """Handle export button."""
        self.export_requested.emit()
    
    def _show_context_menu(self, position):
        """Show context menu for table rows."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        
        # Get watch_id
        watch_id = self.table.item(index.row(), 0).data(Qt.UserRole)
        
        menu = QMenu()
        remove_action = QAction("Remove from Watch List", self)
        remove_action.triggered.connect(lambda: self.watch_manager.remove_signal(watch_id))
        menu.addAction(remove_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
