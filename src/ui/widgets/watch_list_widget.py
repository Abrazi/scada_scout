from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                QTableWidgetItem, QPushButton, QSpinBox, QLabel,
                                QHeaderView, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtGui import QBrush, QColor
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
    
    def __init__(self, watch_list_manager: WatchListManager, device_manager=None, parent=None):
        super().__init__(parent)
        self.watch_manager = watch_list_manager
        self.device_manager = device_manager
        
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
        # Add one column for RTT (ms) after Value
        self.table.setColumnCount(14)
        self.table.setHorizontalHeaderLabels([
            "Name", "Address", "Access", "Type",
            "Modbus Type", "Endianness", "Scale", "Offset",
            "Value", "RTT (ms)", "Quality", "Timestamp", "Last Changed", "Error"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)  # Enable Ctrl/Shift multi-selection
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Context menu for table
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        from PySide6.QtCore import Qt
        if event.key() == Qt.Key_Delete:
            self._remove_selected_signals()
        else:
            super().keyPressEvent(event)
        
    def _connect_signals(self):
        """Connect watch manager signals."""
        self.watch_manager.signal_updated.connect(self._on_signal_updated)
        self.watch_manager.watch_list_changed.connect(self._refresh_table)
        
    def _refresh_table(self):
        """Rebuild the table from watch list."""
        self.table.setRowCount(0)
        
        for watched in self.watch_manager.get_all_watched():
            self._add_signal_row(watched)
        
        self.table.resizeColumnsToContents()

    def _ensure_item(self, row: int, col: int) -> QTableWidgetItem:
        """Ensure a QTableWidgetItem exists at (row, col) and return it."""
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, col, item)
        return item
    
    def _add_signal_row(self, watched: WatchedSignal):
        """Add a row for a watched signal."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        signal = watched.signal
        
        # Column 0: Name
        self.table.setItem(row, 0, QTableWidgetItem(signal.name))
        
        # Column 1: Address
        self.table.setItem(row, 1, QTableWidgetItem(signal.address))
        
        # Column 2: Access
        access = getattr(signal, 'access', 'RO')
        self.table.setItem(row, 2, QTableWidgetItem(access))
        
        # Column 3: Type
        if hasattr(signal, 'signal_type') and signal.signal_type:
            type_str = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
        else:
            type_str = "Unknown"
        self.table.setItem(row, 3, QTableWidgetItem(type_str))
        
        # Column 4: Modbus Type
        modbus_type = signal.modbus_data_type.value if signal.modbus_data_type else "-"
        self.table.setItem(row, 4, QTableWidgetItem(modbus_type))
        
        # Column 5: Endianness
        endianness = signal.modbus_endianness.value if signal.modbus_endianness else "-"
        self.table.setItem(row, 5, QTableWidgetItem(endianness))
        
        # Column 6: Scale
        self.table.setItem(row, 6, QTableWidgetItem(str(signal.modbus_scale)))
        
        # Column 7: Offset
        self.table.setItem(row, 7, QTableWidgetItem(str(signal.modbus_offset)))
        
        # Column 8: Value
        value_str = str(signal.value) if signal.value is not None else "--"
        self.table.setItem(row, 8, QTableWidgetItem(value_str))

        # Column 9: RTT (ms)
        rtt_display = str(watched.last_response_ms) if watched.last_response_ms is not None else "--"
        self.table.setItem(row, 9, QTableWidgetItem(rtt_display))

        # Column 10: Quality
        try:
            qual_text = signal.quality.value if getattr(signal, 'quality', None) is not None else "--"
        except Exception:
            qual_text = "--"

        quality_item = QTableWidgetItem(qual_text)
        # Color code by quality (use QBrush/QColor to avoid conversion surprises)
        if getattr(signal, 'quality', None) == SignalQuality.GOOD:
            quality_item.setBackground(QBrush(QColor('darkgreen')))
        elif getattr(signal, 'quality', None) == SignalQuality.INVALID:
            quality_item.setBackground(QBrush(QColor('red')))
        else:
            quality_item.setBackground(QBrush(QColor('gray')))
        self.table.setItem(row, 10, quality_item)
        
        # Column 11: Timestamp
        ts_str = signal.timestamp.strftime("%H:%M:%S") if signal.timestamp else "--"
        self.table.setItem(row, 11, QTableWidgetItem(ts_str))

        # Column 12: Last Changed
        lc_str = signal.last_changed.strftime("%H:%M:%S") if signal.last_changed else "--"
        self.table.setItem(row, 12, QTableWidgetItem(lc_str))

        # Column 13: Error
        error_str = signal.error or "-"
        self.table.setItem(row, 13, QTableWidgetItem(error_str))
        
        # Store watch_id in row data (column 0)
        self.table.item(row, 0).setData(Qt.UserRole, watched.watch_id)
    
    def _on_signal_updated(self, watch_id: str, signal: Signal, response_ms: int):
        """Update a signal's display when its value changes."""
        # Find the row
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == watch_id:
                # Update all columns
                # Column 0: Name (usually doesn't change)
                # Column 1: Address (usually doesn't change)
                # Column 2: Access (usually doesn't change)
                # Column 3: Type (usually doesn't change)
                # Column 4: Modbus Type (usually doesn't change)
                # Column 5: Endianness (usually doesn't change)
                # Column 6: Scale (usually doesn't change)
                # Column 7: Offset (usually doesn't change)
                
                try:
                    # Column 8: Value
                    value_str = str(signal.value) if signal.value is not None else "--"
                    self._ensure_item(row, 8).setText(value_str)

                    # Column 9: RTT (ms)
                    rtt_text = str(response_ms) if response_ms is not None else "--"
                    self._ensure_item(row, 9).setText(rtt_text)

                    # Column 10: Quality
                    quality_item = self._ensure_item(row, 10)
                    qual_text = signal.quality.value if getattr(signal, 'quality', None) is not None else "--"
                    quality_item.setText(qual_text)
                    if getattr(signal, 'quality', None) == SignalQuality.GOOD:
                        quality_item.setBackground(QBrush(QColor('darkgreen')))
                    elif getattr(signal, 'quality', None) == SignalQuality.INVALID:
                        quality_item.setBackground(QBrush(QColor('red')))
                    else:
                        quality_item.setBackground(QBrush(QColor('gray')))

                    # Column 11: Timestamp
                    ts_str = signal.timestamp.strftime("%H:%M:%S") if signal.timestamp else "--"
                    self._ensure_item(row, 11).setText(ts_str)

                    # Column 12: Last Changed
                    lc_str = signal.last_changed.strftime("%H:%M:%S") if signal.last_changed else "--"
                    self._ensure_item(row, 12).setText(lc_str)

                    # Column 13: Error
                    error_str = signal.error or "-"
                    self._ensure_item(row, 13).setText(error_str)
                except Exception as e:
                    logger.exception(f"Error updating watch list row {row} for {watch_id}: {e}")
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
        from PySide6.QtWidgets import QMenu, QApplication
        from PySide6.QtGui import QAction
        from src.models.device_models import DeviceType
        
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        
        # Get all selected rows
        selected_rows = list(set(idx.row() for idx in self.table.selectedIndexes()))
        
        if not selected_rows:
            return
        
        menu = QMenu()
        
        # If multiple rows selected, show batch remove option
        if len(selected_rows) > 1:
            remove_action = QAction(f"Remove {len(selected_rows)} Signals from Watch List", self)
            remove_action.triggered.connect(self._remove_selected_signals)
            menu.addAction(remove_action)
        else:
            # Single selection - show full menu
            row = selected_rows[0]
            
            # [Added] Copy clicked cell text
            if index.isValid():
                clicked_text = str(index.data() or "").strip()
                if clicked_text:
                    copy_cell_action = QAction(f"Copy '{clicked_text}'", self)
                    copy_cell_action.triggered.connect(lambda: self._copy_to_clipboard(clicked_text))
                    menu.addAction(copy_cell_action)
                    menu.addSeparator()

            # Get watch_id and signal info
            watch_id = self.table.item(row, 0).data(Qt.UserRole)
            
            # Get the watched signal object
            watched = None
            for w in self.watch_manager.get_all_watched():
                if w.watch_id == watch_id:
                    watched = w
                    break
            
            if not watched:
                return
            
            signal = watched.signal
            device_name = watched.device_name
            
            # Control option (if device_manager is available)
            if self.device_manager:
                control_action = QAction("Control...", self)
                # Enable control if access indicates RW or address looks like a control
                if getattr(signal, 'access', 'RO') == "RW" or ".Oper" in getattr(signal, 'address', '') or ".ctlVal" in getattr(signal, 'address', ''):
                    control_action.setEnabled(True)
                    control_action.triggered.connect(lambda: self._invoke_control_dialog(device_name, signal))
                else:
                    control_action.setEnabled(False)
                    control_action.setToolTip("This signal is Read-Only")
                menu.addAction(control_action)
                
                # Read Now option
                read_action = QAction("Read Value Now", self)
                read_action.triggered.connect(lambda: self._manual_read_signal(device_name, signal))
                menu.addAction(read_action)
                
                # Inspect Data
                inspect_action = QAction("Data Inspector...", self)
                inspect_action.triggered.connect(lambda: self._show_data_inspector(signal, device_name))
                menu.addAction(inspect_action)
                
                menu.addSeparator()
            
            # Copy Address
            copy_action = QAction("Copy Signal Address", self)
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(signal.address))
            menu.addAction(copy_action)
            
            menu.addSeparator()
            
            # Remove from watch list
            remove_action = QAction("Remove from Watch List", self)
            remove_action.triggered.connect(lambda: self.watch_manager.remove_signal(watch_id))
            menu.addAction(remove_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def _remove_selected_signals(self):
        """Remove all selected signals from watch list."""
        selected_rows = list(set(idx.row() for idx in self.table.selectedIndexes()))
        
        if not selected_rows:
            return
        
        # Collect watch_ids from selected rows
        watch_ids = []
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item:
                watch_id = item.data(Qt.UserRole)
                if watch_id:
                    watch_ids.append(watch_id)
        
        # Remove all selected signals
        for watch_id in watch_ids:
            self.watch_manager.remove_signal(watch_id)
    
    def _invoke_control_dialog(self, device_name, signal):
        """Open control dialog for a signal."""
        try:
            from src.models.device_models import DeviceType
            device = self.device_manager.get_device(device_name)
            if device and device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
                from src.ui.widgets.modbus_write_dialog import ModbusWriteDialog
                dlg = ModbusWriteDialog(signal, self.device_manager, device_name, self)
                dlg.exec()
            else:
                from src.ui.dialogs.control_dialog import ControlDialog
                dlg = ControlDialog(device_name, signal, self.device_manager, self)
                dlg.exec()
        except Exception:
            logger.exception("Failed to open control dialog from watch list")
    
    def _manual_read_signal(self, device_name, signal):
        """Manually triggers a read for a single signal and shows result."""
        from PySide6.QtWidgets import QMessageBox
        
        try:
            # Force read via device manager
            updated_signal = self.device_manager.read_signal(device_name, signal)

            # If read was enqueued to IEC worker, perform a blocking read for manual request
            if updated_signal is None:
                # Best-effort synchronous read via protocol adapter
                proto = self.device_manager.get_protocol(device_name)
                if proto and hasattr(proto, 'read_signal'):
                    updated_signal = proto.read_signal(signal)

            if updated_signal:
                val = updated_signal.value
                qual = updated_signal.quality.value if hasattr(updated_signal.quality, 'value') else str(updated_signal.quality)
                QMessageBox.information(self, "Read Result", f"Signal: {signal.name}\nValue: {val}\nQuality: {qual}\nTimestamp: {updated_signal.timestamp}")
            else:
                QMessageBox.warning(self, "Read Failed", f"Could not read signal {signal.name}")
        except Exception as e:
            QMessageBox.critical(self, "Read Error", f"Error reading signal: {e}")
    
    def _copy_to_clipboard(self, text):
        """Copies given text to system clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _show_data_inspector(self, signal, device_name):
        """Shows the Data Inspector dialog."""
        from src.ui.dialogs.data_inspector_dialog import DataInspectorDialog
        # Pass full context so inspector can read adjacent registers
        dlg = DataInspectorDialog(signal, device_name, self.device_manager, self)
        dlg.exec()

