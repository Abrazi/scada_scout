from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QMessageBox, QLineEdit, QWidget
from PySide6.QtCore import Qt, QTimer
import threading
import logging

logger = logging.getLogger(__name__)


class ModbusControlDialog(QDialog):
    """Dialog to view and control Modbus register mappings for a device."""
    def __init__(self, device_name: str, device_manager, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.device_manager = device_manager
        self.setWindowTitle(f"Modbus Control - {device_name}")
        self.resize(700, 400)

        self.layout = QVBoxLayout(self)

        # Info + toolbar
        top = QHBoxLayout()
        top.addWidget(QLabel(f"Device: {device_name}"))
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        top.addWidget(self.btn_refresh)
        top.addStretch()
        self.layout.addLayout(top)

        # Table of mappings
        self.table = QTableWidget()
        # Columns: Address, Name, Type, Endianness, Value, Hex, Write
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Address", "Name", "Type", "Endianness", "Value", "Hex", "Write"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)

        # Loader
        self.loading = False

        # Initial load
        self.refresh()

    def refresh(self):
        if self.loading:
            return
        self.loading = True
        self.btn_refresh.setEnabled(False)

        # Do refresh in background
        t = threading.Thread(target=self._load_mappings)
        t.daemon = True
        t.start()

    def _load_mappings(self):
        try:
            device = self.device_manager.get_device(self.device_name)
            proto = self.device_manager.get_or_create_protocol(self.device_name)

            mappings = []
            # Server adapter exposes server.mappings
            if proto and hasattr(proto, 'server') and proto.server:
                for addr, m in sorted(proto.server.mappings.items()):
                    mappings.append({
                        'addr': addr,
                        'name': m.name,
                        'type': getattr(m.data_type, 'value', str(m.data_type)),
                        'endian': getattr(m.endianness, 'value', str(m.endianness)),
                        'value': proto.server.get_mapped_value(addr)
                    })
            else:
                # For RTU/master devices, get signals from device root node
                if device and device.root_node:
                    def collect_modbus_signals(node):
                        signals = []
                        if hasattr(node, 'signals') and node.signals:
                            for sig in node.signals:
                                # Only include Modbus signals (with address format unit:function:address)
                                if hasattr(sig, 'address') and sig.address and ':' in sig.address:
                                    parts = sig.address.split(':')
                                    if len(parts) == 3:
                                        try:
                                            unit_id = int(parts[0])
                                            func_code = int(parts[1])
                                            address = int(parts[2])
                                            signals.append({
                                                'addr': address,
                                                'name': getattr(sig, 'name', f"Reg_{address}"),
                                                'type': getattr(sig, 'modbus_data_type', None),
                                                'endian': getattr(sig, 'modbus_endianness', None),
                                                'value': getattr(sig, 'value', None),
                                                'access': getattr(sig, 'access', 'RO'),
                                                'signal': sig  # Keep reference to signal object
                                            })
                                        except (ValueError, IndexError):
                                            pass
                        if hasattr(node, 'children') and node.children:
                            for child in node.children:
                                signals.extend(collect_modbus_signals(child))
                        return signals
                    
                    mappings = collect_modbus_signals(device.root_node)
                    # Sort by address
                    mappings.sort(key=lambda x: x['addr'])

            # Use device config: try several common config attributes for all Modbus devices
            # First collect configured mappings
            configured_mappings = []
            
            # 1) modbus_slave_mappings (explicit mapping objects)
            if device and device.config and getattr(device.config, 'modbus_slave_mappings', None):
                for m in device.config.modbus_slave_mappings:
                    configured_mappings.append({
                        'addr': m.address,
                        'name': getattr(m, 'name', f"Map_{m.address}"),
                        'type': getattr(m, 'data_type', str(getattr(m, 'data_type', ''))),
                        'endian': getattr(m, 'endianness', None),
                        'value': None,
                        'signal': None  # No signal object for configured mappings
                    })
            
            # 2) modbus_register_maps (legacy mapping)
            if device and device.config and getattr(device.config, 'modbus_register_maps', None):
                for reg_map in device.config.modbus_register_maps:
                    start = reg_map.start_address
                    count = reg_map.count
                    for i in range(count):
                        addr = start + i
                        configured_mappings.append({
                            'addr': addr,
                            'name': f"{reg_map.name_prefix or 'Map'}_{addr}",
                            'type': str(reg_map.data_type.value if hasattr(reg_map.data_type, 'value') else reg_map.data_type),
                            'endian': str(reg_map.endianness.value if hasattr(reg_map.endianness, 'value') else reg_map.endianness),
                            'value': None,
                            'signal': None  # No signal object for configured mappings
                        })
            
            # 3) modbus_slave_blocks (server blocks)
            if device and device.config and getattr(device.config, 'modbus_slave_blocks', None):
                for block in device.config.modbus_slave_blocks:
                    for i in range(block.count):
                        addr = block.start_address + i
                        configured_mappings.append({
                            'addr': addr,
                            'name': f"{block.name}_{addr}",
                            'type': str(getattr(block, 'data_type', '-')),
                            'endian': str(getattr(block, 'endianness', '-')),
                            'value': None,
                            'signal': None  # No signal object for configured mappings
                        })
            
            # Merge configured mappings with discovered signals
            # Use a dict to avoid duplicates, preferring discovered signals
            all_mappings = {}
            
            # Add discovered signals first (they have priority)
            for mapping in mappings:
                all_mappings[mapping['addr']] = mapping
            
            # Add configured mappings (only if not already present)
            for mapping in configured_mappings:
                if mapping['addr'] not in all_mappings:
                    all_mappings[mapping['addr']] = mapping
            
            # Convert back to list and sort
            mappings = list(all_mappings.values())
            mappings.sort(key=lambda x: x['addr'])

            # Update UI on main thread
            def update_ui():
                self.table.blockSignals(True)
                self.table.setRowCount(0)
                import logging
                logging.getLogger("ModbusControlDialog").info(f"Updating UI with {len(mappings)} mappings")
                for row_idx, m in enumerate(mappings):
                    self.table.insertRow(row_idx)
                    self.table.setItem(row_idx, 0, QTableWidgetItem(str(m['addr'])))
                    self.table.setItem(row_idx, 1, QTableWidgetItem(str(m['name'])))
                    self.table.setItem(row_idx, 2, QTableWidgetItem(str(m['type'])))
                    self.table.setItem(row_idx, 3, QTableWidgetItem(str(m['endian'])))
                    # Value cell (editable display)
                    val_text = str(m['value']) if m['value'] is not None else "-"
                    val_item = QTableWidgetItem(val_text)
                    val_item.setFlags(val_item.flags() | Qt.ItemIsEditable)
                    self.table.setItem(row_idx, 4, val_item)

                    # Hex display column
                    try:
                        if isinstance(m['value'], int):
                            hex_text = f"0x{m['value']:04X}"
                        else:
                            hex_text = "-"
                    except Exception:
                        hex_text = "-"
                    hex_item = QTableWidgetItem(hex_text)
                    hex_item.setFlags(hex_item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row_idx, 5, hex_item)

                    # Write widgets: spinbox + button
                    # Determine sensible range based on reported type
                    spin = QSpinBox()
                    dtype = str(m.get('type') or '').upper()
                    if 'INT16' in dtype:
                        spin.setRange(-32768, 32767)
                    elif 'UINT16' in dtype or 'UINT' in dtype or 'UINT32' in dtype:
                        spin.setRange(0, 0xFFFFFFFF)
                    elif 'INT32' in dtype:
                        spin.setRange(-2147483648, 2147483647)
                    else:
                        # Default to 16-bit unsigned range
                        spin.setRange(0, 65535)
                    btn = QPushButton("Write")
                    def make_write(addr, spinbox, sig=None):
                        def do_write():
                            v = spinbox.value()
                            self._write_address(addr, v, sig)
                        return do_write
                    btn.clicked.connect(make_write(m['addr'], spin, m.get('signal')))
                    container = QHBoxLayout()
                    container_widget = QWidget()
                    container.addWidget(spin)
                    container.addWidget(btn)
                    container_widget.setLayout(container)
                    self.table.setCellWidget(row_idx, 6, container_widget)

                # Connect item changes to update hex display when user edits Value cell
                def on_item_changed(item):
                    try:
                        col = item.column()
                        row = item.row()
                        if col == 4:
                            # Update hex column
                            val_str = item.text()
                            hex_text = "-"
                            write_val = None
                            try:
                                # Try int first
                                write_val = int(val_str)
                                hex_text = f"0x{write_val:04X}"
                            except Exception:
                                try:
                                    write_val = float(val_str)
                                    # Represent float as hex of its int bits if desired
                                    hex_text = "-"
                                except Exception:
                                    write_val = None

                            self.table.blockSignals(True)
                            self.table.setItem(row, 5, QTableWidgetItem(hex_text))
                            self.table.blockSignals(False)

                            # If we successfully parsed a value, commit it to server immediately
                            if write_val is not None:
                                try:
                                    addr_item = self.table.item(row, 0)
                                    if addr_item:
                                        addr = int(addr_item.text())
                                        # If float, pass as float to write; the server adapter will handle encoding
                                        sig = self.mappings[row].get('signal') if row < len(self.mappings) else None
                                        self._write_address(addr, write_val, sig)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                self.table.itemChanged.connect(on_item_changed)

                self.table.blockSignals(False)
                self.loading = False
                self.btn_refresh.setEnabled(True)

            QTimer.singleShot(0, update_ui)

        except Exception as e:
            logger.exception(f"Failed loading modbus mappings: {e}")
            def fail_ui():
                QMessageBox.warning(self, "Error", f"Failed to load mappings: {e}")
                self.loading = False
                self.btn_refresh.setEnabled(True)
            QTimer.singleShot(0, fail_ui)

    def _write_address(self, address, value, signal=None):
        try:
            proto = self.device_manager.get_or_create_protocol(self.device_name)
            if not proto:
                QMessageBox.warning(self, "Error", "Protocol not available")
                return

            # Use the actual signal if provided, otherwise build a temporary one
            if signal:
                sig = signal
            else:
                # Build a temporary Signal-like object expected by protocol.write_signal
                from types import SimpleNamespace
                sig = SimpleNamespace()
                # Attempt to use unit:function:addr format; assume function 3 (holding registers)
                unit = getattr(proto, 'unit_id', 1)
                sig.address = f"{unit}:3:{address}"
                sig.modbus_data_type = None
                sig.modbus_endianness = None

            # Call write (in background)
            def do_write():
                ok = False
                try:
                    ok = proto.write_signal(sig, value)
                except Exception as e:
                    logger.error(f"Write error: {e}")
                def ui_done():
                    if ok:
                        QMessageBox.information(self, "Write", f"Wrote {value} to {address}")
                        self.refresh()
                    else:
                        QMessageBox.warning(self, "Write Failed", f"Failed to write {address}")
                QTimer.singleShot(0, ui_done)
            threading.Thread(target=do_write, daemon=True).start()

        except Exception as e:
            logger.exception(f"Error writing address {address}: {e}")
            QMessageBox.warning(self, "Error", f"Write failed: {e}")
