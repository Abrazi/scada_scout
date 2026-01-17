from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QTabWidget, QPushButton, QSizePolicy
from PySide6.QtGui import QStandardItemModel, QStandardItem, QPainter
from PySide6.QtCharts import QChart, QChartView, QLineSeries
from PySide6.QtCore import Qt
from src.ui.models.signal_table_model import SignalTableModel
from PySide6.QtCore import QRegularExpression
from PySide6.QtCore import QSortFilterProxyModel
import json

class SignalsViewWidget(QWidget):
    """
    Widget containing the Data Grid and Live Chart.
    Uses tabs to switch between Table View and Chart View.
    """
    def __init__(self, device_manager, watch_list_manager=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.watch_list_manager = watch_list_manager
        self.current_device_name = None  # Track which device's signals we're showing
        self.current_node = None        # Track current node for manual refresh
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self._setup_table_tab()
        self._setup_chart_tab()
        
        self._connect_signals()
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
                # If it's a node entry, call add_node_to_live via finding node object
                if entry.get('type') == 'node' or entry.get('node_name'):
                    # Try to locate device and node object
                    if device_name and hasattr(self, 'device_manager') and self.device_manager:
                        dev = self.device_manager.get_device(device_name)
                        if dev and getattr(dev, 'root_node', None):
                            # Find node by name (simple heuristic)
                            def _find_node_by_name(n, name):
                                if getattr(n, 'name', '') == name:
                                    return n
                                for c in getattr(n, 'children', []):
                                    r = _find_node_by_name(c, name)
                                    if r: return r
                                return None
                            node = _find_node_by_name(dev.root_node, entry.get('node_name'))
                            if node:
                                self.add_node_to_live(node, device_name)
                                added += 1
                                continue

                if device_name and address:
                    payload = {
                        'device': device_name,
                        'address': address,
                        'signal_name': entry.get('signal_name','')
                    }
                    # Use add_signal which subscribes and displays
                    try:
                        self.add_signal(payload)
                        added += 1
                    except Exception:
                        pass

            if added:
                try:
                    evt = getattr(self.device_manager, 'event_logger', None)
                    if evt:
                        evt.info("Live Data", f"Drag-and-drop added {added} signal(s)")
                except Exception:
                    pass
                event.acceptProposedAction()
            else:
                event.ignore()
        except Exception:
            event.ignore()

    def _setup_table_tab(self):
        """Create the Signals Table tab."""
        self.table_tab = QWidget()
        layout = QVBoxLayout(self.table_tab)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh All")
        self.btn_refresh.setFixedWidth(100)
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        toolbar.addWidget(self.btn_refresh)
        
        # Refresh only selected node
        self.btn_refresh_selected = QPushButton("Refresh Selected")
        self.btn_refresh_selected.setFixedWidth(130)
        self.btn_refresh_selected.clicked.connect(self._on_refresh_selected_clicked)
        self.btn_refresh_selected.setEnabled(False)
        toolbar.addWidget(self.btn_refresh_selected)

        # Clear Live Data
        self.btn_clear = QPushButton("Clear Live Data")
        self.btn_clear.setFixedWidth(120)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        toolbar.addWidget(self.btn_clear)
        
        # Auto-Refresh Checkbox
        from PySide6.QtWidgets import QCheckBox
        self.chk_auto_refresh = QCheckBox("Auto-Refresh (3s)")
        self.chk_auto_refresh.setChecked(True)
        self.chk_auto_refresh.stateChanged.connect(self._on_auto_refresh_toggled)
        toolbar.addWidget(self.chk_auto_refresh)

        # Filter controls: column selector + text
        from PySide6.QtWidgets import QLineEdit, QComboBox, QLabel
        self.cmb_filter_col = QComboBox()
        # Populate columns from model
        self.cmb_filter_col.addItems(SignalTableModel.COLUMNS)
        self.cmb_filter_col.setFixedWidth(160)
        toolbar.addWidget(QLabel("Filter:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter live data...")
        self.txt_filter.setFixedWidth(220)
        toolbar.addWidget(self.cmb_filter_col)
        toolbar.addWidget(self.txt_filter)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True) 
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        
        # Enable context menu
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        
        # Init Model and Proxy (for filtering)
        self.table_model = SignalTableModel()
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self.table_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)
        self.table_view.setModel(self._proxy_model)

        # Wire filter events
        self.txt_filter.textChanged.connect(self._on_filter_text_changed)
        self.cmb_filter_col.currentIndexChanged.connect(self._on_filter_column_changed)
        
        layout.addWidget(self.table_view)
        
        # No Signals Overlay
        from PySide6.QtWidgets import QLabel
        self.lbl_no_signals = QLabel("No signals found (Select a node)", self.table_view)
        self.lbl_no_signals.setAlignment(Qt.AlignCenter)
        # Use themed note/empty overlay style
        self.lbl_no_signals.setProperty("class", "note")
        self.lbl_no_signals.hide()
        
        self.tabs.addTab(self.table_tab, "Live Data")
        
        # Timer for Auto-Refresh
        from PySide6.QtCore import QTimer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._on_refresh_clicked)
        # self.refresh_timer.start(3000)

    def _on_auto_refresh_toggled(self, state):
        if state == Qt.Checked:
            self.refresh_timer.start(3000)
        else:
            self.refresh_timer.stop()

    def _on_filter_column_changed(self, idx):
        # Map visible column selection to proxy column
        self._proxy_model.setFilterKeyColumn(idx)
        # Reapply filter text to update
        self._on_filter_text_changed(self.txt_filter.text())

    def _on_filter_text_changed(self, text: str):
        # Use fixed string for substring matching; case-insensitive already set
        if not text:
            self._proxy_model.setFilterRegularExpression(QRegularExpression())
        else:
            # Build simple escaped regex to match substring
            rx = QRegularExpression(text, QRegularExpression.CaseInsensitiveOption)
            self._proxy_model.setFilterRegularExpression(rx)

    def _on_refresh_clicked(self):
        """Manually trigger a refresh for the currently shown signals."""
        # Check if we have a current node, if not try to set one
        if not self.current_node:
            self._try_auto_select_node()
            
        if self.current_node:
            device_name = self._get_current_device_name()
            if device_name:
                signals = self._collect_signals(self.current_node)
                if signals:
                    self._trigger_background_read(device_name, signals)

    def _on_refresh_selected_clicked(self):
        """Refresh only the currently selected node/subbranch (does not auto-select)."""
        if not self.current_node:
            return

        device_name = self._get_current_device_name()
        if not device_name:
            return

        signals = self._collect_signals(self.current_node)
        if signals:
            self._trigger_background_read(device_name, signals)

    def _on_clear_clicked(self):
        """Clear all live data currently shown in the table."""
        # Stop auto-refresh to prevent continued reading
        if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
            self.refresh_timer.stop()
            if hasattr(self, 'chk_auto_refresh'):
                self.chk_auto_refresh.setChecked(False)
        
        # Clear the current node reference to prevent manual refresh from working
        self.current_node = None
        self.current_device_name = None
        
        # Clear the table model
        try:
            self.table_model.clear_signals()
        except Exception:
            # Fallback: reset node filter to None
            try:
                self.table_model.set_node_filter(None)
            except Exception:
                pass

        # Update UI state
        self.lbl_no_signals.show()
        self.lbl_no_signals.resize(self.table_view.size())
        if hasattr(self, 'btn_refresh_selected'):
            self.btn_refresh_selected.setEnabled(False)

    def _try_auto_select_node(self):
        """Attempt to select the first available device if nothing is selected."""
        devices = self.device_manager.get_all_devices()
        for device in devices:
            if device.root_node:
                self.set_filter_node(device.root_node, device.config.name)
                return

    def set_filter_node(self, node, device_name=None):
        """Updates the view to show signals from the given node.

        Accepts optional device_name to scope live reads and UI labels.
        """
        self.current_node = node
        if device_name:
            self.current_device_name = device_name
        elif node is None:
            self.current_device_name = None

        self.table_model.set_node_filter(node)
        self.table_view.resizeColumnsToContents()
        # Enable/disable selected refresh button based on whether there are signals
        try:
            has_signals = bool(self._collect_signals(node))
        except Exception:
            has_signals = False
        if hasattr(self, 'btn_refresh_selected'):
            self.btn_refresh_selected.setEnabled(has_signals)
        # Toggle Overlay
        if self.table_model.rowCount() == 0:
            self.lbl_no_signals.show()
            self.lbl_no_signals.resize(self.table_view.size())
        else:
            self.lbl_no_signals.hide()

    def add_node_to_live(self, node, device_name=None):
        """Add signals from `node` into the live data table (append, no dedupe)."""
        if not node:
            return

        # Track device name for background reads
        if device_name:
            self.current_device_name = device_name
        # Track current node so "Refresh Selected" knows what to refresh
        self.current_node = node

        signals = self._collect_signals(node)
        import logging
        logger = logging.getLogger("SignalsView")
        try:
            logger.info(f"add_node_to_live: collected {len(signals)} signals from node type {type(node)}")
        except Exception:
            logger.info("add_node_to_live: collected signals (count unknown)")
        if not signals:
            import logging
            logging.getLogger("SignalsView").warning(f"add_node_to_live: No signals found in node {node}")
            return

        try:
            self.table_model.add_signals(signals)
        except Exception:
            import logging
            logging.getLogger("SignalsView").exception("Failed to add signals to model")
            return

        # Event log
        try:
            evt = getattr(self.device_manager, 'event_logger', None)
            if evt:
                node_name = getattr(node, 'name', 'Node')
                evt.info(device_name or "Live Data", f"Added {len(signals)} signals to Live Data from {node_name}")
        except Exception:
            pass

        # Update UI elements
        self.table_view.resizeColumnsToContents()
        self.lbl_no_signals.hide()
        if hasattr(self, 'btn_refresh_selected'):
            self.btn_refresh_selected.setEnabled(True)
            
        # Auto-start refresh if it was stopped
        if hasattr(self, 'chk_auto_refresh') and not self.chk_auto_refresh.isChecked():
            self.chk_auto_refresh.setChecked(True) # This triggers _on_auto_refresh_toggled -> starts timer
        
        # Trigger immediate read
        self._trigger_background_read(self.current_device_name, signals)

    def resizeEvent(self, event):
        """Ensure overlay stays centered."""
        if hasattr(self, 'lbl_no_signals') and self.lbl_no_signals.isVisible():
             self.lbl_no_signals.resize(self.table_view.size())
             self.lbl_no_signals.move(0, 0) # Relative to table view if parented? 
             # Actually parent is table_view, so 0,0 covers it.
        super().resizeEvent(event)
    # Note: `set_filter_node(node, device_name=None)` above is the canonical
    # method to set the current node and device. Avoid redefining it.

    def add_signal(self, signal_def: dict):
        """
        Adds signals to the live view based on a definition payload.
        Payload can be a single signal or a full node (recursive).
        
        Args:
            signal_def (dict): {
                'device': str,
                'address': str, # optional (single)
                'fc': str,      # optional
                'node_type': 'Single' | 'Node' | 'Device', # optional hint
                'node': object  # Logic Node object (if recursive)
            }
        """
        device_name = signal_def.get('device')
        if not device_name:
            return

        # Check for recursive add (Payload from DeviceTree usually has 'node' object now on Context Menu?)
        # Actually, in the plan, I said DeviceTree will emit a dict.
        # Let's support both the old single-signal payload and a new one.
        
        # If signal_def has a 'node' object, add all leaf signals under node/subnodes
        node_obj = signal_def.get('node')
        if node_obj:
            self.add_node_to_live(node_obj, device_name)
            return

        # Single signal fallback
        address = signal_def.get('address')
        fc = signal_def.get('fc', '')
        
        if not address:
             return

        # 1. Validation
        if fc in ['CO', 'CF', 'SG', 'SE']:
            import logging
            logging.getLogger("SignalsView").warning(f"Ignored non-monitoring signal: {address} (FC={fc})")
            return

        # 2. Subscribe via Manager (Authoritative)
        from src.models.subscription_models import IECSubscription, SubscriptionMode
        
        sub = IECSubscription(
            device=device_name,
            mms_path=address,
            fc=fc,
            mode=SubscriptionMode.READ_POLLING,
            source="live_data"
        )
        
        # Subscribe!
        self.device_manager.subscription_manager.subscribe(sub)

        # 3. Add to Display (Table)
        # We need the Signal object to display it.
        # Fetch it from device manager
        device = self.device_manager.get_device(device_name)
        if device and device.root_node:
             # Fast find or reconstruct
             found = self._find_signal_in_device(device, address)
             if found:
                 self.table_model.add_signals([found])
             else:
                 # Fallback ad-hoc
                 from src.models.device_models import Signal
                 s = Signal(name=signal_def.get('signal_name',''), address=address, description="Live Add")
                 self.table_model.add_signals([s])

        # Event log
        try:
            evt = getattr(self.device_manager, 'event_logger', None)
            if evt:
                evt.info(device_name, f"Added signal to Live Data: {address}")
        except Exception:
            pass
                 
        self.lbl_no_signals.hide()

    def _add_node_recursive(self, device_name, node):
        """Recursively subscribe to all ST/MX signals under this node."""
        signals_to_add = []
        
        def _recurse(n):
            # Add signals in this node
            if hasattr(n, 'signals') and n.signals:
                for sig in n.signals:
                    # Filter
                    fc = getattr(sig, 'fc', getattr(sig, 'access', ''))
                    # strict filter: must be ST or MX
                    if fc not in ['ST', 'MX']:
                        # Try to handle empty FC if it looks like measurement?
                        # Keep strict for now as per user request
                        continue
                    
                    signals_to_add.append(sig)
            
            # Recurse
            if hasattr(n, 'children'):
                for child in n.children:
                    _recurse(child)
            
            if hasattr(n, 'root_node'): # Device object case
                 _recurse(n.root_node)

        _recurse(node)
        
        if not signals_to_add:
            return

        # Bulk Subscribe
        from src.models.subscription_models import IECSubscription, SubscriptionMode
        count = 0
        for sig in signals_to_add:
            fc = getattr(sig, 'fc', getattr(sig, 'access', ''))
            sub = IECSubscription(
                device=device_name,
                mms_path=sig.address,
                fc=fc,
                mode=SubscriptionMode.READ_POLLING,
                source="live_data"
            )
            self.device_manager.subscription_manager.subscribe(sub)
            count += 1
            
        # Add to Table
        self.table_model.add_signals(signals_to_add)
        self.lbl_no_signals.hide()
        
        import logging
        logging.getLogger("SignalsView").info(f"Recursively added {count} signals from {node.name}")

    def _find_signal_in_device(self, device, address):
        # ... helper ...
        def _search(n):
            if hasattr(n, 'signals'):
                for s in n.signals:
                    if s.address == address: return s
            if hasattr(n, 'children'):
                for c in n.children:
                     r = _search(c)
                     if r: return r
            return None
        if device.root_node:
            return _search(device.root_node)
        return None

    def _trigger_background_read(self, device_name, signals):
        """Trigger a one-shot read for the provided signals."""
        if not device_name or not signals:
            return

        for sig in signals:
            try:
                self.device_manager.read_signal(device_name, sig)
            except Exception:
                # Ignore individual read failures
                continue

    def _get_current_device_name(self):
        """Get the device name for current signals view."""
        # Try to use tracked device name
        if hasattr(self, 'current_device_name') and self.current_device_name:
            return self.current_device_name
        
        # Fallback: get first connected device
        devices = self.device_manager.get_all_devices()
        for device in devices:
            if device.connected:
                return device.config.name
        
        # Fallback 2: get any device
        if devices:
            return devices[0].config.name
            
        return None

    def _on_table_context_menu(self, position):
        """Handle right-click context menu in signals table."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        index = self.table_view.indexAt(position)
        if not index.isValid():
            return

        # Map proxy index to source model index
        try:
            src_index = self._proxy_model.mapToSource(index)
            row = src_index.row()
        except Exception:
            row = index.row()

        # Get the signal from the model
        signal = self.table_model.get_signal_at_row(row)
        if not signal:
            return
        
        # We need device_name - try to get from current context
        device_name = self._get_current_device_name()
        if not device_name:
            return
        
        menu = QMenu()
        # Deprecated: WatchListManager is being phased out, but context menu is nice.
        # Maybe "Remove from Live Data" (Unsubscribe)?
        
        remove_action = QAction("Remove from Live Data", self)
        def remove_signal():
             from src.models.subscription_models import IECSubscription, SubscriptionMode
             # We need to construct the exact subscription to remove it.
             # Or we can add an unsubscribe_by_path in manager.
             # For now, let's create a matching subscription object.
             fc = getattr(signal, 'fc', getattr(signal, 'access', ''))
             sub = IECSubscription(
                device=device_name,
                mms_path=signal.address,
                fc=fc,
                mode=SubscriptionMode.READ_POLLING,
                source="live_data"
            )
             self.device_manager.subscription_manager.unsubscribe(sub)
             # Also remove from table?
             # Subscription removal stops polling.
             # Ideally manager emits change -> we react.
             # But for now manual removal from table.
             self.table_model.remove_signal(signal) # Need to verify this exists or use clear/refresh
             
        remove_action.triggered.connect(remove_signal)
        menu.addAction(remove_action)
        
        # Control option
        menu.addSeparator()
        control_action = QAction("Control...", self)
        
        # Enable if RW or explicitly controllable
        is_controllable = getattr(signal, 'access', 'RO') == "RW" or ".Oper" in signal.address or ".ctlVal" in signal.address
        
        if is_controllable:
            control_action.setEnabled(True)
            control_action.triggered.connect(lambda: self._on_control_clicked(device_name, signal))
        else:
            control_action.setEnabled(False)
            control_action.setToolTip("This signal is Read-Only")
        menu.addAction(control_action)
        
        menu.exec(self.table_view.viewport().mapToGlobal(position))

    def _on_control_clicked(self, device_name, signal):
        # For Modbus devices, open Modbus-specific control dialog
        from src.models.device_models import DeviceType
        device = self.device_manager.get_device(device_name)
        if device and device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
            from src.ui.dialogs.modbus_control_dialog import ModbusControlDialog
            dlg = ModbusControlDialog(device_name, self.device_manager, self)
            dlg.exec()
            return

        # Fallback to generic IEC control dialog
        from src.ui.dialogs.control_dialog import ControlDialog
        dialog = ControlDialog(device_name, signal, self.device_manager, self)
        dialog.exec()


    def _setup_chart_tab(self):
        """Create the Chart tab."""
        self.chart_tab = QWidget()
        layout = QVBoxLayout(self.chart_tab)
        
        self.chart = QChart()
        self.chart.setTitle("Live Telemetry")
        
        # We will dynamically add series later
        self.chart.createDefaultAxes()
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        
        layout.addWidget(self.chart_view)
        # self.tabs.addTab(self.chart_tab, "Trend Chart") # Hide Chart for now until implemented

    def _connect_signals(self):
        """Connect to DeviceManager."""
        self.device_manager.device_added.connect(self._on_device_added)
        self.device_manager.signal_updated.connect(self._on_signal_update)

    def _on_device_added(self, device):
        """When a device is added, we don't necessarily update view until selected."""
        pass

    def _on_signal_update(self, device_name, signal):
        """Handle live update."""
        # import logging
        # logger = logging.getLogger("SignalsView")
        # logger.debug(f"Signal Update received: {signal.address} = {signal.value}")
        self.table_model.update_signal(signal)
        
    def _collect_signals(self, node) -> list:
        """Recursively collect all signals from a node tree (supports Node, Signal, or Device)."""
        if node is None:
            return []
            
        signals = []
        
        # 1. If it's a Signal (leaf)
        if hasattr(node, 'address') and not hasattr(node, 'signals'):
            return [node]
            
        # 2. If it's a Node (branch)
        if hasattr(node, "signals") and node.signals:
            signals.extend(node.signals)
        
        if hasattr(node, "children") and node.children:
            for child in node.children:
                signals.extend(self._collect_signals(child))
                
        # 3. If it's a Device (root)
        if hasattr(node, "root_node") and node.root_node:
            signals.extend(self._collect_signals(node.root_node))
            
        return signals
