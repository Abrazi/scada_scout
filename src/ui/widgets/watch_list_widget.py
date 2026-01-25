from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                                QTableWidgetItem, QPushButton, QSpinBox, QLabel,
                                QHeaderView, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtGui import QBrush, QColor
from src.core.watch_list_manager import WatchListManager, WatchedSignal
import datetime
from src.models.device_models import Signal, SignalQuality
import logging
import re

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
        # Add columns for RTT and Max RTT after Value
        self.table.setColumnCount(15)
        self.table.setHorizontalHeaderLabels([
            "Name", "Address", "Access", "Type",
            "Modbus Type", "Endianness", "Scale", "Offset",
            "Value", "RTT (ms)", "Max RTT (ms)", "Quality", "Timestamp", "Last Changed", "Error"
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
        # Accept drops from Device Tree
        try:
            self.setAcceptDrops(True)
        except Exception:
            pass

    def dragEnterEvent(self, event):
        mimetype = 'application/x-scadascout-signals'
        if event.mimeData().hasFormat(mimetype) or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        try:
            data = None
            mimetype = 'application/x-scadascout-signals'
            md = event.mimeData()
            if md.hasFormat(mimetype):
                raw = md.data(mimetype)
                try:
                    data = json.loads(bytes(raw).decode('utf-8'))
                except Exception:
                    data = None
            elif md.hasText():
                try:
                    data = json.loads(md.text())
                except Exception:
                    data = None

            if not data:
                event.ignore()
                return

            added = 0
            for entry in data:
                device_name = entry.get('device')
                address = entry.get('address')
                if not device_name or not address:
                    continue
                # Find device and resolve Signal object
                device = None
                if hasattr(self, 'device_manager') and self.device_manager:
                    device = self.device_manager.get_device(device_name)
                if not device or not getattr(device, 'root_node', None):
                    continue

                # Use watch_manager helper to find signal
                try:
                    sig = self.watch_manager._find_signal_in_node(device.root_node, address)
                except Exception:
                    # Fallback search
                    sig = None
                    def _search(n):
                        if hasattr(n, 'signals'):
                            for s in n.signals:
                                if s.address == address:
                                    return s
                        if hasattr(n, 'children'):
                            for c in n.children:
                                r = _search(c)
                                if r: return r
                        return None
                    sig = _search(device.root_node)

                if sig:
                    self.watch_manager.add_signal(device_name, sig)
                    added += 1

            if added:
                try:
                    evt = getattr(self.device_manager, 'event_logger', None)
                    if evt:
                        evt.info("Watch List", f"Drag-and-drop added {added} signal(s)")
                except Exception:
                    pass
                event.acceptProposedAction()
            else:
                event.ignore()
        except Exception:
            event.ignore()
        
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
        # Listen for variables (DeviceManager bridges core variable events to Qt signals)
        try:
            if hasattr(self, 'device_manager') and getattr(self.device_manager, 'variable_added', None):
                self.device_manager.variable_added.connect(self._on_variable_added)
            if hasattr(self, 'device_manager') and getattr(self.device_manager, 'variable_removed', None):
                self.device_manager.variable_removed.connect(self._on_variable_removed)
            if hasattr(self, 'device_manager') and getattr(self.device_manager, 'variable_updated', None):
                self.device_manager.variable_updated.connect(self._on_variable_updated)
        except Exception:
            # Non-fatal if DeviceManager doesn't expose variable signals
            pass
        
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
        value_str = self._format_value(signal)
        self.table.setItem(row, 8, QTableWidgetItem(value_str))

        # Column 9: RTT (ms)
        rtt_value = watched.last_response_ms
        if rtt_value is None and hasattr(signal, 'last_rtt') and signal.last_rtt > 0:
            rtt_value = int(round(signal.last_rtt))
        rtt_display = str(rtt_value) if rtt_value is not None else "--"
        self.table.setItem(row, 9, QTableWidgetItem(rtt_display))

        # Column 10: Max RTT (ms)
        max_rtt_display = str(watched.max_response_ms) if watched.max_response_ms is not None else "--"
        self.table.setItem(row, 10, QTableWidgetItem(max_rtt_display))

        # Column 11: Quality
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
        self.table.setItem(row, 11, quality_item)
        
        # Column 12: Timestamp
        if signal.timestamp:
            try:
                ts_str = signal.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                if getattr(signal.timestamp, 'tzinfo', None) is not None and signal.timestamp.tzinfo == datetime.timezone.utc:
                    ts_str += ' UTC'
            except Exception:
                ts_str = str(signal.timestamp)
        else:
            ts_str = "--"
        self.table.setItem(row, 12, QTableWidgetItem(ts_str))

        # Column 13: Last Changed
        if signal.last_changed:
            try:
                lc_str = signal.last_changed.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                if getattr(signal.last_changed, 'tzinfo', None) is not None and signal.last_changed.tzinfo == datetime.timezone.utc:
                    lc_str += ' UTC'
            except Exception:
                lc_str = str(signal.last_changed)
        else:
            lc_str = "--"
        self.table.setItem(row, 13, QTableWidgetItem(lc_str))

        # Column 14: Error
        error_str = signal.error or "-"
        self.table.setItem(row, 14, QTableWidgetItem(error_str))
        
        # Store watch_id in row data (column 0)
        self.table.item(row, 0).setData(Qt.UserRole, watched.watch_id)
    
    def _on_signal_updated(self, watch_id: str, signal: Signal, response_ms: int | None):
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
                    value_str = self._format_value(signal)
                    self._ensure_item(row, 8).setText(value_str)

                    # Column 9: RTT (ms)
                    rtt_value = response_ms
                    if rtt_value is None:
                        watched = self.watch_manager.get_watched(watch_id)
                        if watched and watched.last_response_ms is not None:
                            rtt_value = watched.last_response_ms
                        elif hasattr(signal, 'last_rtt') and signal.last_rtt > 0:
                            rtt_value = int(round(signal.last_rtt))
                    rtt_text = str(rtt_value) if rtt_value is not None else "--"
                    self._ensure_item(row, 9).setText(rtt_text)

                    # Column 10: Max RTT (ms)
                    watched = self.watch_manager.get_watched(watch_id)
                    max_rtt = watched.max_response_ms if watched else None
                    max_rtt_text = str(max_rtt) if max_rtt is not None else "--"
                    self._ensure_item(row, 10).setText(max_rtt_text)

                    # Column 11: Quality
                    quality_item = self._ensure_item(row, 11)
                    qual_text = signal.quality.value if getattr(signal, 'quality', None) is not None else "--"
                    quality_item.setText(qual_text)
                    if getattr(signal, 'quality', None) == SignalQuality.GOOD:
                        quality_item.setBackground(QBrush(QColor('darkgreen')))
                    elif getattr(signal, 'quality', None) == SignalQuality.INVALID:
                        quality_item.setBackground(QBrush(QColor('red')))
                    else:
                        quality_item.setBackground(QBrush(QColor('gray')))

                    # Column 12: Timestamp
                    if signal.timestamp:
                        try:
                            ts_str = signal.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            if getattr(signal.timestamp, 'tzinfo', None) is not None and signal.timestamp.tzinfo == datetime.timezone.utc:
                                ts_str += ' UTC'
                        except Exception:
                            ts_str = str(signal.timestamp)
                    else:
                        ts_str = "--"
                    self._ensure_item(row, 12).setText(ts_str)

                    # Column 13: Last Changed
                    if signal.last_changed:
                        try:
                            lc_str = signal.last_changed.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            if getattr(signal.last_changed, 'tzinfo', None) is not None and signal.last_changed.tzinfo == datetime.timezone.utc:
                                lc_str += ' UTC'
                        except Exception:
                            lc_str = str(signal.last_changed)
                    else:
                        lc_str = "--"
                    self._ensure_item(row, 13).setText(lc_str)

                    # Column 14: Error
                    error_str = signal.error or "-"
                    self._ensure_item(row, 14).setText(error_str)
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

                # Create variable from this signal (global scope)
                try:
                    create_var_action = QAction("Create variable from signal...", self)
                    create_var_action.triggered.connect(lambda: self._create_variable_from_row(row))
                    menu.addAction(create_var_action)
                except Exception:
                    pass

            # Copy Address (raw) and Tokenized for scripts
            copy_action = QAction("Copy Signal Address", self)
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(signal.address))
            menu.addAction(copy_action)

            # Provide tokenized copy suitable for Python scripts
            try:
                unique_address = getattr(signal, 'unique_address', '') or f"{device_name}::{signal.address}"
                copy_token_action = QAction("Copy Tag Address (Token)", self)
                def _copy_token(addr=unique_address, dev=device_name, sig=signal):
                    try:
                        from PySide6.QtCore import QSettings
                        qs = QSettings("ScadaScout", "UI")
                        raw = qs.value("copy_tag_tokenized", None)
                        if raw is None:
                            tokenized = True
                        elif isinstance(raw, bool):
                            tokenized = raw
                        elif isinstance(raw, str):
                            tokenized = raw.lower() in ("1", "true", "yes", "on")
                        else:
                            try:
                                tokenized = bool(int(raw))
                            except Exception:
                                tokenized = bool(raw)
                    except Exception:
                        tokenized = True
                    # Ensure we have a sensible string unique address; fallback to device::signal.address
                    final_addr = addr
                    try:
                        if not final_addr:
                            final_addr = f"{dev}::{getattr(sig, 'address', '')}"
                    except Exception:
                        final_addr = str(addr)

                    if tokenized:
                        try:
                            token = self.device_manager.make_tag_token(final_addr)
                        except Exception:
                            token = f"{{{{TAG:{final_addr}}}}}"
                        self._copy_to_clipboard(token)
                    else:
                        self._copy_to_clipboard(final_addr)
                copy_token_action.triggered.connect(_copy_token)
                menu.addAction(copy_token_action)
            except Exception:
                pass
            
            menu.addSeparator()
            
            # Remove from watch list
            remove_action = QAction("Remove from Watch List", self)
            remove_action.triggered.connect(lambda: self.watch_manager.remove_signal(watch_id))
            menu.addAction(remove_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def _remove_selected_signals(self):
        """Remove all selected signals or variables from watch list/UI."""
        selected_rows = list(set(idx.row() for idx in self.table.selectedIndexes()))
        
        if not selected_rows:
            return
        
        # Collect identifiers from selected rows
        ids = []
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item:
                ident = item.data(Qt.UserRole)
                if ident:
                    ids.append(ident)
        
        # Remove items — support both watched-signals and variables
        for ident in ids:
            try:
                if isinstance(ident, str) and ident.startswith('var:'):
                    # ident format: var:{owner}:{name}
                    parts = ident.split(':', 2)
                    if len(parts) == 3:
                        owner = parts[1] or None
                        name = parts[2]
                        if self.device_manager:
                            try:
                                self.device_manager.remove_variable(owner, name)
                            except Exception:
                                logger.exception(f"Failed to remove variable {name}")
                else:
                    # treat as watch_id for watch_manager
                    self.watch_manager.remove_signal(ident)
            except Exception:
                logger.exception(f"Error removing item {ident}")

    # ---------------- Variable UI integration ----------------
    def _create_variable_from_row(self, row: int):
        """Prompt user and create a global variable bound to the selected signal."""
        try:
            item = self.table.item(row, 0)
            if not item:
                return
            # Extract address from Address column
            addr_item = self.table.item(row, 1)
            if not addr_item:
                return
            unique_address = addr_item.text().strip()
            if not unique_address:
                return

            # Ask for variable name
            from PySide6.QtWidgets import QInputDialog, QMessageBox
            default_name = unique_address.split('::')[-1].replace('.', '_').replace('/', '_')
            name, ok = QInputDialog.getText(self, 'Create Variable', 'Variable name:', text=default_name)
            if not ok or not name:
                return

            # Ask whether continuous
            resp = QMessageBox.question(self, 'Update mode', 'Start in continuous update mode?', QMessageBox.Yes | QMessageBox.No)
            mode = 'continuous' if resp == QMessageBox.Yes else 'on_demand'
            interval_ms = None
            if mode == 'continuous':
                interval_ms, ok2 = QInputDialog.getInt(self, 'Interval (ms)', 'Update interval (ms):', 250, 10, 60000)
                if not ok2:
                    return

            # Create variable via DeviceManager (global owner=None)
            if not self.device_manager:
                QMessageBox.warning(self, 'Create Variable', 'Device manager not available')
                return

            try:
                self.device_manager.create_variable(None, name, unique_address, mode=mode, interval_ms=interval_ms)
                evt = getattr(self.device_manager, 'event_logger', None)
                if evt:
                    evt.info('Variable', f"Created variable '{name}' -> {unique_address} ({mode}{'' if not interval_ms else f', {interval_ms}ms'})")
            except Exception as e:
                QMessageBox.critical(self, 'Create Variable', f'Failed to create variable: {e}')
        except Exception:
            logger.exception('Failed to create variable from row')

    def _add_variable_row(self, owner, name, unique_address, value=None, ts=None):
        """Add a variable row to the watch table (visual-only)."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        # Column 0: Name
        it = QTableWidgetItem(name)
        it.setData(Qt.UserRole, f"var:{owner or ''}:{name}")
        self.table.setItem(row, 0, it)
        # Column 1: Address
        self.table.setItem(row, 1, QTableWidgetItem(unique_address))
        # Columns 2-7: metadata not applicable
        for c in range(2, 8):
            self.table.setItem(row, c, QTableWidgetItem("--"))
        # Column 8: Value
        val_text = str(value) if value is not None else "--"
        self.table.setItem(row, 8, QTableWidgetItem(val_text))
        # RTT/Max RTT
        self.table.setItem(row, 9, QTableWidgetItem("--"))
        self.table.setItem(row, 10, QTableWidgetItem("--"))
        # Quality
        qit = QTableWidgetItem("VAR")
        qit.setBackground(QBrush(QColor('#DDEEFF')))
        self.table.setItem(row, 11, qit)
        # Timestamp
        ts_text = str(ts) if ts else "--"
        self.table.setItem(row, 12, QTableWidgetItem(ts_text))
        # Last changed / Error
        self.table.setItem(row, 13, QTableWidgetItem("--"))
        self.table.setItem(row, 14, QTableWidgetItem("--"))

    def _on_variable_added(self, owner, name, unique_address):
        try:
            # Add a lightweight row for the variable
            self._add_variable_row(owner, name, unique_address)
            self.table.resizeColumnsToContents()
        except Exception:
            logger.exception('Failed to add variable row')

    def _on_variable_removed(self, owner, name):
        # Find and remove matching variable row
        ident = f"var:{owner or ''}:{name}"
        for row in range(self.table.rowCount() - 1, -1, -1):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == ident:
                self.table.removeRow(row)
                break

    def _on_variable_updated(self, owner, name, value, ts):
        ident = f"var:{owner or ''}:{name}"
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == ident:
                try:
                    self._ensure_item(row, 8).setText(str(value) if value is not None else "--")
                    self._ensure_item(row, 12).setText(str(ts) if ts else "--")
                except Exception:
                    logger.exception('Failed to update variable row')
                break
    
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
                val = self._format_value(updated_signal)
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

    def _format_value(self, signal: Signal) -> str:
        if signal.value is None:
            return "--"

        # Try to format as Hex/Decimal/Enum
        num, enum_label = self._extract_numeric_and_enum(signal)
        if num is not None:
            hex_str = f"0x{num:X}"
            if enum_label:
                return f"{hex_str} ({num}) {enum_label}"
            return f"{hex_str} ({num})"

        return str(signal.value)

    def _is_pos_stval(self, signal: Signal) -> bool:
        addr = (signal.address or "").lower()
        name = (signal.name or "").lower()
        return "pos.stval" in addr or "pos$stval" in addr or ("pos" in addr and name == "stval")

    def _extract_numeric_and_enum(self, signal: Signal) -> tuple[int | None, str | None]:
        num = None
        enum_label = None

        mapping = getattr(signal, "enum_map", None)
        if not mapping and self._is_pos_stval(signal):
            mapping = {0: "intermediate", 1: "open", 2: "closed", 3: "bad"}

        val = signal.value
        if isinstance(val, bool):
            num = int(val)
        elif isinstance(val, int):
            num = val
        elif isinstance(val, float) and val.is_integer():
            num = int(val)
        elif isinstance(val, str):
            text = val.strip()
            try:
                if text.lower().startswith("0x"):
                    num = int(text.split()[0], 16)
                else:
                    m = re.search(r"\(([-]?\d+)\)", text)
                    if m:
                        num = int(m.group(1))
                    elif re.fullmatch(r"-?\d+", text):
                        num = int(text)
            except Exception:
                num = None

            if num is None:
                if mapping:
                    for k, v in mapping.items():
                        if str(v).lower() == text.lower():
                            num = int(k)
                            break

            if num is not None and not enum_label:
                m = re.match(r"(.+?)\s*\(\s*[-]?\d+\s*\)", text)
                if m:
                    enum_label = m.group(1).strip()

        if num is not None and mapping and num in mapping:
            enum_label = mapping[num]

        return num, enum_label

