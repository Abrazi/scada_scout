from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QMenu, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QColor, QBrush
from PySide6.QtCore import Qt, Signal as QtSignal, QItemSelectionModel
from typing import Optional
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.modbus_inspector_dialog import ModbusInspectorDialog
import logging

logger = logging.getLogger(__name__)

class DeviceTreeWidget(QWidget):
    """
    Widget containing the Device Tree View.
    Displays a hierarchy of Connections -> Devices -> Logical Nodes.
    """
    # Signals
    # Emits the selected Node object (or list of signals if we want)
    # For now, let's emit the Node object so the SignalsView can filter.
    selection_changed = QtSignal(object, str) # Node or Device or Signal, device_name

    def __init__(self, device_manager, watch_list_manager=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.watch_list_manager = watch_list_manager
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Filter Bar
        from PySide6.QtWidgets import QLineEdit, QHBoxLayout
        filter_layout = QHBoxLayout()
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Search devices...")
        self.txt_filter.textChanged.connect(self._filter_tree)
        filter_layout.addWidget(self.txt_filter)
        self.layout.addLayout(filter_layout)
        
        self.tree_view = QTreeView()
        self.layout.addWidget(self.tree_view)
        
        self._setup_view()
        self.folder_items = {}  # folder_name -> QStandardItem
        self.device_items = {}  # device_name -> QStandardItem 
        self._setup_model()
        self._connect_signals()
        
        # Selection and Editing
        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.model.itemChanged.connect(self._on_item_changed)

    def _filter_tree(self, text):
        """Filter the tree view based on text."""
        search = text.lower()
        
        def filter_recursive(item):
            visible = False
            # Check self
            if search in item.text().lower():
                visible = True
            
            # Check children
            for i in range(item.rowCount()):
                child = item.child(i)
                child_visible = filter_recursive(child)
                if child_visible:
                    visible = True
            
            # If visible, hide/show using view (if using proxy) or set row hidden
            # Ideally with QStandardItemModel, we might want Proxy, but hiding rows works too.
            # QTreeView.setRowHidden needs visual index.
            # Easier: Use Proxy? Or manual traversal.
            # Let's try manual traversal of the View for simplicity if not using Proxy.
            # Wait, hiding requires mapping indices.
            
            # Better approach for QStandardItemModel: Loop visible rows?
            return visible

        # If text is empty, show all
        if not search:
            self._show_all_items(self.model.invisibleRootItem())
            return

        # Recompute visibility for every top-level child
        root = self.model.invisibleRootItem()
        for i in range(root.rowCount()):
            child = root.child(i)
            visible = self._filter_item_visibility(child, search)
            self.tree_view.setRowHidden(i, root.index(), not visible)
            if visible:
                self.tree_view.expand(child.index())

    def _show_all_items(self, parent):
        for i in range(parent.rowCount()):
            self.tree_view.setRowHidden(i, parent.index(), False)
            child = parent.child(i)
            if child:
                self._show_all_items(child)

    def _filter_item_visibility(self, parent, search):
        # Determine if any child or this parent matches
        branch_visible = False
        for i in range(parent.rowCount()):
            child = parent.child(i)
            if not child:
                continue

            # Check text of this item (and col 2 desc)
            try:
                txt = child.text().lower()
            except Exception:
                txt = ""

            desc = child.index().siblingAtColumn(2).data() if child.index().isValid() else None
            if desc:
                try:
                    txt += " " + str(desc).lower()
                except Exception:
                    pass

            should_show = (search in txt)

            # Recursively check children
            children_visible = False
            if child.rowCount() > 0:
                children_visible = self._filter_item_visibility(child, search)

            visible = should_show or children_visible
            # Set row hidden state relative to parent
            self.tree_view.setRowHidden(i, parent.index(), not visible)

            if visible:
                branch_visible = True
                # Expand to reveal matches
                try:
                    self.tree_view.expand(child.index())
                except Exception:
                    pass

        return branch_visible

    # Revised Filter Logic
    def _filter_tree_revised(self, text):
        pass # Placeholder, replacing logic in _filter_tree directly


    def _on_selection_changed(self, selected, deselected):
        try:
            indexes = self.tree_view.selectionModel().selectedIndexes()
            logger.info(f"DeviceTreeWidget: Selection changed. Index count: {len(indexes)}")
            
            if not indexes:
                self.selection_changed.emit(None, "")
                return
                
            # Get the first selected row's Name column (logical column 0)
            index = indexes[0].siblingAtColumn(0)
            item = self.model.itemFromIndex(index)
            
            if not item:
                 logger.warning("DeviceTreeWidget: Item is None for index.")
                 return

            node_data = item.data(Qt.UserRole)
            device_name = self._find_device_for_item(item) or ""
            
            logger.info(f"DeviceTreeWidget: Selected Device='{device_name}', Data Type={type(node_data)}")

            if isinstance(node_data, str):
                # It's a device name, get the device object
                device = self.device_manager.get_device(node_data)
                self.selection_changed.emit(device, device_name)
            else:
                self.selection_changed.emit(node_data, device_name)
        except Exception as e:
            logger.error(f"DeviceTreeWidget: Error in selection handling: {e}")

    def _setup_view(self):
        """Configures the TreeView appearance."""
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSelectionBehavior(QTreeView.SelectRows)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)  # Enable Ctrl/Shift multi-selection
        self.tree_view.setEditTriggers(QTreeView.DoubleClicked | QTreeView.EditKeyPressed)
        self.tree_view.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # Context Menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        
        # UI Polish: Move Status column (logical 1) to visual position 0
        header = self.tree_view.header()
        header.setSectionsMovable(True)
        # We need to wait for the model to be set or move it after?
        # Let's move it here, it usually persists.
        header.moveSection(1, 0)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        
    def _setup_model(self):
        """Initializes the model and populates with existing devices."""
        self.model = QStandardItemModel()
        # Logical order: Name, Status, Description, FC, Type
        self.model.setHorizontalHeaderLabels(["Name", "Status", "Description", "FC", "Type"])
        self.tree_view.setModel(self.model)
        
        # After setting model, ensure Status is moved to start
        self.tree_view.header().moveSection(1, 0)
        
        self.folder_items.clear()
        self.device_items.clear()
        
        # Populate existing devices
        for device in self.device_manager.get_all_devices():
            self._add_device_node(device)

    def _connect_signals(self):
        """Connects to DeviceManager signals."""
        self.device_manager.device_added.connect(self._add_device_node)
        self.device_manager.device_removed.connect(self._remove_device_node)
        self.device_manager.device_updated.connect(self._refresh_device_node)
        self.device_manager.project_cleared.connect(self._setup_model)
        self.device_manager.device_status_changed.connect(self._update_status_indicator)
        # Live signal updates (device_name, Signal)
        try:
            self.device_manager.signal_updated.connect(self._on_signal_updated)
        except Exception:
            # Older versions may not have the signal; ignore
            pass
        
    def _refresh_device_node(self, device_name):
        """Refreshes a device node (re-adds children)."""
        item = self.device_items.get(device_name)
        if item:
            # 1. Capture current selection (if inside this device)
            selected_path = None
            selection_model = self.tree_view.selectionModel()
            current_idx = selection_model.currentIndex()
            
            # Check if current selection is a child of this item (or the item itself)
            # This is complex with QStandardItemModel indices. 
            # Simplified: Just check if we selected something in this device
            
            # 2. Clear children
            if item.rowCount() > 0:
                item.removeRows(0, item.rowCount())
            
            # 3. Re-populate
            device = self.device_manager.get_device(device_name)
            if device and device.root_node:
                for child in device.root_node.children:
                    self._add_node_recursive(item, child)
            
            # 4. Auto-expand
            self.tree_view.expand(item.index())
            
            # 5. Restore selection?
            # If the user had the Device itself selected, re-select it.
            # If they had a child selected, it's harder to match by name, but we can try.
            # For now, just re-selecting the Device Item is a good default if nothing else.
            # But wait, SignalsView handles re-filtering to Root if we don't change selection.
            # QTreeView keeps selection on the 'item' if 'item' itself wasn't removed.
            # 'item' is the Device Node, which we kept! We only removed rows.
            # So if the user selected the DEVICE node, selection is preserved!
            # If the user selected a CHILD, that child is gone. Selection is lost.
            
            # Let's try to re-select the device node if we lost selection.
            if not selection_model.hasSelection():
                 selection_model.select(item.index(), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                 # This triggers _on_selection_changed -> SignalsView.set_filter_node(device)
            
            for i in range(5):
                self.tree_view.resizeColumnToContents(i)
        
    def _get_folder_node(self, folder_name: str) -> QStandardItem:
        """Gets or creates a folder node."""
        if not folder_name:
            return self.model.invisibleRootItem()
            
        if folder_name in self.folder_items:
            return self.folder_items[folder_name]
            
        # Create new folder
        folder_item = QStandardItem(folder_name)
        folder_item.setData(folder_name, Qt.UserRole) # Store original name
        folder_item.setData("FOLDER", Qt.UserRole + 1) # Mark as folder
        folder_item.setEditable(True)
        
        folder_desc = self.device_manager.folder_descriptions.get(folder_name, "Folder")
        desc_item = QStandardItem(folder_desc)
        desc_item.setEditable(True)
        
        # Add to root
        # Row layout: [Name, Status, Description, FC, Type]
        self.model.invisibleRootItem().appendRow([folder_item, QStandardItem(""), desc_item, QStandardItem(""), QStandardItem("")])
        self.folder_items[folder_name] = folder_item
        return folder_item

    def _add_device_node(self, device):
        """Adds a device to the tree."""
        parent = self._get_folder_node(device.config.folder)
        
        name_item = QStandardItem(device.config.name)
        name_item.setEditable(True)
        
        # Connection status dot (logical column 1)
        status_text = "🟢" if device.connected else "🔴"
        status_item = QStandardItem(status_text)
        status_item.setEditable(False)
        status_item.setTextAlignment(Qt.AlignCenter)
        
        desc_text = device.config.description or device.config.device_type.value
        desc_item = QStandardItem(desc_text)
        desc_item.setEditable(True)
        fc_item = QStandardItem("")
        type_item = QStandardItem("Device")
        
        # Store device name in data for easy retrieval on the name_item (logical col 0)
        name_item.setData(device.config.name, Qt.UserRole)
        
        parent.appendRow([name_item, status_item, desc_item, fc_item, type_item])
        self.device_items[device.config.name] = name_item
        
        # Recursively add children if discovery happened
        if device.root_node:
            for child in device.root_node.children:
                self._add_node_recursive(name_item, child)

    def _add_node_recursive(self, parent_item: QStandardItem, node):
        """Recursively adds nodes to the tree."""
        # Col 0: Name (Hierarchy parent)
        item_name = QStandardItem(node.name)
        item_name.setEditable(True)
        item_name.setData(node, Qt.UserRole)
        
        # Col 1: Status (Empty for nodes)
        status_item = QStandardItem("")
        status_item.setEditable(False)
        
        # Col 2: Description
        item_desc = QStandardItem(node.description or "")
        item_desc.setEditable(True)
        
        fc_text = ""
        type_text = "Node"
        
        # Parse FC/Type from description if present
        if node.description and "FC=" in node.description:
            import re
            m_fc = re.search(r"FC=([A-Z]+)", node.description)
            if m_fc: fc_text = m_fc.group(1)
            
            m_type = re.search(r"Type=([A-Za-z0-9_]+)", node.description)
            if m_type: type_text = m_type.group(1)
        
        item_fc = QStandardItem(fc_text)
        item_fc.setEditable(False)
        
        item_type = QStandardItem(type_text)
        item_type.setEditable(False)

        parent_item.appendRow([item_name, status_item, item_desc, item_fc, item_type])
        
        # Add Children Nodes
        for child in node.children:
            self._add_node_recursive(item_name, child)
            
        # Add Signals as Leaf Nodes
        if hasattr(node, "signals") and node.signals:
            for sig in node.signals:
                self._add_signal_node(item_name, sig)
    
    def _add_signal_node(self, parent_item: QStandardItem, sig):
        """Adds a signal as a child row."""
        sig_name_item = QStandardItem(sig.name)
        sig_name_item.setEditable(True)
        sig_name_item.setData(sig, Qt.UserRole)
        
        sig_desc_item = QStandardItem(sig.description or "")
        sig_desc_item.setEditable(True)
        
        # FC/Type Extraction
        # Try explicit attribute first
        s_fc = getattr(sig, 'fc', '')
        if not s_fc and hasattr(sig, 'access'):
             # Fallback for Modbus without FC attr (if adapter update failed)
             s_fc = sig.access
             
        # Fallback to description regex if still empty (legacy IEC61850)
        if not s_fc and sig.description and "FC=" in sig.description:
             import re
             m_fc = re.search(r"FC=([A-Z]+)", sig.description)
             if m_fc: s_fc = m_fc.group(1)
        
        s_type = ""
        if hasattr(sig, 'modbus_data_type') and sig.modbus_data_type:
             s_type = str(sig.modbus_data_type).split('.')[-1]
        elif hasattr(sig, 'signal_type') and sig.signal_type:
             s_type = str(sig.signal_type).split('.')[-1]
        
        if not s_type and sig.description and "Type=" in sig.description:
             import re
             m_type = re.search(r"Type=([A-Za-z0-9_]+)", sig.description)
             if m_type: s_type = m_type.group(1)

        sig_fc_item = QStandardItem(s_fc)
        sig_fc_item.setEditable(False)
        
        sig_type_item = QStandardItem(s_type)
        sig_type_item.setEditable(False)
        
        parent_item.appendRow([sig_name_item, QStandardItem(""), sig_desc_item, sig_fc_item, sig_type_item])
        
    def _update_status_indicator(self, device_name, connected):
        """Updates the status dot for a device."""
        item = self.device_items.get(device_name)
        if item:
            status_item = item.index().siblingAtColumn(1).model().itemFromIndex(item.index().siblingAtColumn(1))
            status_item.setText("🟢" if connected else "🔴")

    def _on_signal_updated(self, device_name: str, signal):
        """Update the tree row for a signal when live data arrives.

        Finds the QStandardItem for the signal (matching by address) and updates
        the description/value and visual quality indicator.
        """
        try:
            device_item = self.device_items.get(device_name)
            if not device_item:
                return

            # Recursive search for the signal item under the device node
            def _search_item(qitem):
                # Check current item's stored data
                data = qitem.data(Qt.UserRole)
                if data and hasattr(data, 'address'):
                    try:
                        if data.address == signal.address:
                            return qitem
                    except Exception:
                        pass

                # Recurse children
                for row in range(qitem.rowCount()):
                    child = qitem.child(row, 0)
                    if not child:
                        continue
                    found = _search_item(child)
                    if found:
                        return found
                return None

            item = _search_item(device_item)
            if not item:
                return

            # Update description column (2) to include live value
            desc_idx = item.index().siblingAtColumn(2)
            desc_item = self.model.itemFromIndex(desc_idx)
            if desc_item is None:
                desc_item = QStandardItem("")

            val_text = str(getattr(signal, 'value', ''))
            base_desc = getattr(signal, 'description', '') or ''
            desc_item.setText(f"{base_desc}  Value: {val_text}")

            # Color by quality
            quality = getattr(signal, 'quality', None)
            brush = None
            if quality is not None:
                try:
                    from src.models.device_models import SignalQuality
                    if quality == SignalQuality.GOOD:
                        brush = QBrush(QColor('darkgreen'))
                    elif quality == SignalQuality.NOT_CONNECTED:
                        brush = QBrush(QColor('grey'))
                    else:
                        brush = QBrush(QColor('darkorange'))
                except Exception:
                    brush = None

            if brush:
                desc_item.setForeground(brush)
            else:
                desc_item.setForeground(QBrush(QColor('black')))

            # Apply back to model (respect hierarchical parent)
            parent_index = desc_idx.parent()
            if parent_index.isValid():
                parent_item = self.model.itemFromIndex(parent_index)
                if parent_item:
                    parent_item.setChild(desc_idx.row(), 2, desc_item)
            else:
                self.model.setItem(desc_idx.row(), 2, desc_item)
            # Resize columns for clarity
            for i in range(5):
                self.tree_view.resizeColumnToContents(i)

        except Exception as e:
            logger.debug(f"DeviceTreeWidget: Failed to update signal in tree: {e}")

    def _remove_device_node(self, device_name):
        """Removes a device from the tree."""
        item = self.device_items.get(device_name)
        if item:
            parent = item.parent() or self.model.invisibleRootItem()
            parent.removeRow(item.row())
            del self.device_items[device_name]
            
            # Cleanup empty folder
            if parent != self.model.invisibleRootItem() and parent.rowCount() == 0:
                folder_name = parent.text()
                if folder_name in self.folder_items:
                    self.model.invisibleRootItem().removeRow(parent.row())
                    del self.folder_items[folder_name]

    def _on_item_changed(self, item):
        """Handles in-place editing of item names and descriptions."""
        col = item.column()
        if col not in [0, 2]: # Name (0) or Description (2)
            return
            
        # Get the primary item in column 0 (Name)
        name_item = item.index().siblingAtColumn(0).model().itemFromIndex(item.index().siblingAtColumn(0))
        data = name_item.data(Qt.UserRole)
        is_folder = name_item.data(Qt.UserRole + 1) == "FOLDER"
        
        new_text = item.text().strip()
        
        if is_folder:
            old_name = name_item.data(Qt.UserRole)
            if col == 0:  # Rename folder
                if not new_text or new_text == old_name:
                    item.setText(old_name)
                    return
                # Update all devices in this folder
                devices_to_move = []
                for device in self.device_manager.get_all_devices():
                    if device.config.folder == old_name:
                        devices_to_move.append(device)
                
                # Move them
                for dev in devices_to_move:
                    dev.config.folder = new_text
                
                if old_name in self.folder_items:
                    del self.folder_items[old_name]
                self.folder_items[new_text] = name_item
                name_item.setData(new_text, Qt.UserRole)
                
                # Move description too
                if old_name in self.device_manager.folder_descriptions:
                    self.device_manager.folder_descriptions[new_text] = self.device_manager.folder_descriptions.pop(old_name)
                
                logger.info(f"Renamed folder '{old_name}' to '{new_text}' ({len(devices_to_move)} devices updated)")
                self.device_manager.save_configuration()
            else:
                # Folder description
                self.device_manager.folder_descriptions[old_name] = new_text
                logger.debug(f"Updated description for folder '{old_name}': {new_text}")
                self.device_manager.save_configuration()
                
        elif isinstance(data, str):
            # It's a device name (key)
            device_name = data
            device = self.device_manager.get_device(device_name)
            if device:
                if col == 0:  # Rename device
                    if not new_text or new_text == device_name:
                        item.setText(device_name)
                        return
                    # Check if new name exists
                    if self.device_manager.get_device(new_text):
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "Rename Error", f"A device with name '{new_text}' already exists.")
                        item.setText(device_name)
                        return
                    
                    # Update internal tracking before manager triggers signals
                    if device_name in self.device_items:
                        del self.device_items[device_name]
                    
                    # Update config and trigger refresh
                    old_config = device.config
                    import copy
                    new_config = copy.deepcopy(old_config)
                    new_config.name = new_text
                    self.device_manager.update_device(device_name, new_config)
                else:
                    # Update description
                    device.config.description = new_text
                    logger.info(f"Updated description for device '{device_name}'")
                    self.device_manager.save_configuration()
                    
        elif data and hasattr(data, 'name'):
            # Signal or Node
            if col == 0:
                data.name = new_text
            else:
                data.description = new_text
            logger.debug(f"Updated {type(data).__name__} in-place: {new_text}")

    def _on_context_menu(self, position):
        """Shows context menu for device nodes, signal nodes and background."""
        index = self.tree_view.indexAt(position)
        
        if not index.isValid():
            # Background click (kept existing logic but moved into a block if needed, 
            # or we can check index validity for copy first)
            pass

        # === NEW: Get clicked text ===
        clicked_text = str(index.data() or "").strip()
        
        if not index.isValid():
            # Background click
            menu = QMenu()
            add_dev_action = QAction("Add New Device...", self)
            add_dev_action.triggered.connect(self._add_new_device)
            menu.addAction(add_dev_action)
            
            add_folder_action = QAction("Add New Folder...", self)
            add_folder_action.triggered.connect(self._show_add_folder_dialog)
            menu.addAction(add_folder_action)
            
            menu.exec(self.tree_view.viewport().mapToGlobal(position))
            return
        
        # Get the item from column 0 (Name)
        root_item = self.model.itemFromIndex(index.siblingAtColumn(0))
        data = root_item.data(Qt.UserRole)
        
        # Check if it's a folder node
        folder_marker = root_item.data(Qt.UserRole + 1)
        if folder_marker == "FOLDER":
            menu = QMenu()
            
            # [Added] Copy option
            if clicked_text:
                copy_action = QAction(f"Copy '{clicked_text}'", self)
                copy_action.triggered.connect(lambda: self._copy_to_clipboard(clicked_text))
                menu.addAction(copy_action)
                menu.addSeparator()

            add_dev_action = QAction("Add Device to this Folder...", self)
            add_dev_action.triggered.connect(lambda: self._add_new_device(folder=root_item.text()))
            menu.addAction(add_dev_action)
            
            remove_folder_action = QAction("Remove Folder", self)
            remove_folder_action.triggered.connect(lambda: self._remove_folder(root_item.text()))
            menu.addAction(remove_folder_action)
            
            menu.exec(self.tree_view.viewport().mapToGlobal(position))
            return

        menu = QMenu()
        
        # [Added] Copy option for regular items
        if clicked_text:
            copy_action = QAction(f"Copy '{clicked_text}'", self)
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(clicked_text))
            menu.addAction(copy_action)
            menu.addSeparator()
        
        # Check if it's a device node (string) or signal node (Signal object)
        from src.models.device_models import Signal, DeviceType
        
        # Avoid noisy logging of full node/signal objects on right-click
        logger.debug(f"Context menu invoked on item type: {type(data)}")
        
        if isinstance(data, str):
            # Device node
            device_name = data
            device = self.device_manager.get_device(device_name)
            if device:
                # Discovery mode toggle (existing functionality)
                online_action = QAction("Use Online Discovery", self)
                scd_action = QAction("Use SCD Discovery", self)
                
                scd_action.setCheckable(True)
                online_action.setCheckable(True)
                
                if device.config.use_scd_discovery:
                    scd_action.setChecked(True)
                else:
                    online_action.setChecked(True)
                
                online_action.triggered.connect(lambda: self.device_manager.set_discovery_mode(device_name, False))
                scd_action.triggered.connect(lambda: self.device_manager.set_discovery_mode(device_name, True))
                
                menu.addAction(online_action)
                menu.addAction(scd_action)
                
                # Connect/Disconnect
                menu.addSeparator()
                if device.connected:
                    disc_action = QAction("Disconnect", self)
                    disc_action.triggered.connect(lambda: self.device_manager.disconnect_device(device_name))
                    menu.addAction(disc_action)
                else:
                    conn_action = QAction("Connect", self)
                    conn_action.triggered.connect(lambda: self.device_manager.connect_device(device_name))
                    menu.addAction(conn_action)
                
                # Polling toggle
                menu.addSeparator()
                poll_action = QAction("Enable Continuous Polling", self)
                poll_action.setCheckable(True)
                poll_action.setChecked(device.config.polling_enabled)
                poll_action.triggered.connect(lambda: self._toggle_polling(device_name))
                menu.addAction(poll_action)

                # Modbus specific: Range configuration
                if device.config.device_type == DeviceType.MODBUS_TCP:
                    range_action = QAction("Define Address Ranges...", self)
                    range_action.triggered.connect(lambda: self._show_modbus_range_dialog(device_name))
                    menu.addAction(range_action)
                    
                    inspect_action = QAction("Inspect Modbus Data...", self)
                    inspect_action.triggered.connect(lambda: self._show_modbus_inspector(device_name))
                    menu.addAction(inspect_action)
                elif device.config.device_type == DeviceType.MODBUS_SERVER:
                    server_action = QAction("Configure Registers...", self)
                    server_action.triggered.connect(lambda: self._show_modbus_slave_dialog(device_name))
                    menu.addAction(server_action)

                # Edit and Remove
                menu.addSeparator()
                edit_action = QAction("Edit Connection", self)
                edit_action.triggered.connect(lambda: self._edit_device(device_name))
                menu.addAction(edit_action)
                
                remove_action = QAction("Remove Device", self)
                remove_action.triggered.connect(lambda: self._confirm_remove_device(device_name))
                menu.addAction(remove_action)
                
                # Copy Address for device
                menu.addSeparator()
                copy_action = QAction("Copy Device Name", self)
                copy_action.triggered.connect(lambda: self._copy_to_clipboard(device_name))
                menu.addAction(copy_action)
                # Expand/Collapse subtree
                menu.addSeparator()
                expand_action = QAction("Expand All", self)
                expand_action.triggered.connect(lambda: self._expand_subtree(root_item))
                menu.addAction(expand_action)

                collapse_action = QAction("Collapse All", self)
                collapse_action.triggered.connect(lambda: self._collapse_subtree(root_item))
                menu.addAction(collapse_action)
        
        elif isinstance(data, Signal) or (hasattr(data, 'name') and hasattr(data, 'address')):
            # Signal node (strict check or duck typing)
            signal = data
            
            # Find the device name by traversing up the tree
            device_name = self._find_device_for_item(root_item)
            
            # Check if multiple signals are selected
            selected_indexes = self.tree_view.selectionModel().selectedIndexes()
            # Get unique rows (since each row has multiple columns)
            selected_rows = list(set(idx.row() for idx in selected_indexes if idx.column() == 0))
            
            # Collect all selected signals
            selected_signals = []
            for idx in selected_indexes:
                if idx.column() == 0:  # Only process column 0 to avoid duplicates
                    item = self.model.itemFromIndex(idx)
                    if item:
                        item_data = item.data(Qt.UserRole)
                        if isinstance(item_data, Signal) or (hasattr(item_data, 'name') and hasattr(item_data, 'address')):
                            selected_signals.append(item_data)
            
            if device_name and self.watch_list_manager:
                # Show different menu options based on selection count
                if len(selected_signals) > 1:
                    watch_action = QAction(f"Add {len(selected_signals)} Signals to Watch List", self)
                    def add_multiple_watch():
                        for sig in selected_signals:
                            self.watch_list_manager.add_signal(device_name, sig)
                    watch_action.triggered.connect(add_multiple_watch)
                    menu.addAction(watch_action)
                else:
                    watch_action = QAction("Add to Watch List", self)
                    # Use closure to capture variables
                    def add_watch():
                        self.watch_list_manager.add_signal(device_name, signal)
                        
                    watch_action.triggered.connect(add_watch)
                    menu.addAction(watch_action)

                # Copy Address (only for single selection)
                if len(selected_signals) == 1:
                    copy_action = QAction("Copy Signal Address", self)
                    copy_action.triggered.connect(lambda: self._copy_to_clipboard(signal.address))
                    menu.addAction(copy_action)
                
                # Control option (only for single selection)
                if len(selected_signals) == 1:
                    menu.addSeparator()
                    control_action = QAction("Control...", self)
                    # Enable control if access indicates RW or address looks like a control (Oper/ctlVal)
                    if getattr(signal, 'access', 'RO') == "RW" or ".Oper" in getattr(signal, 'address', '') or ".ctlVal" in getattr(signal, 'address', ''):
                        control_action.setEnabled(True)
                        # Hook up control action
                        control_action.triggered.connect(lambda: self._invoke_control_dialog(device_name, signal))
                    else:
                        control_action.setEnabled(False)
                        control_action.setToolTip("This signal is Read-Only")
                    menu.addAction(control_action)
                    
                    # Diagnostics: Read Now
                    read_action = QAction("Read Value Now", self)
                    # Single connection only (avoid duplicate triggers causing dialog to reopen)
                    read_action.triggered.connect(lambda: self._manual_read_signal(device_name, signal))
                    menu.addAction(read_action)
                    
                    # Data Inspector (for Modbus signals only)
                    device = self.device_manager.get_device(device_name)
                    if device and device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
                        inspector_action = QAction("Data Inspector...", self)
                        inspector_action.triggered.connect(lambda: self._show_data_inspector(signal, device_name))
                        menu.addAction(inspector_action)

                    # Enumeration Inspection
                    enum_action = QAction("Show Enumeration", self)
                    enum_action.triggered.connect(lambda: self._show_enumeration_dialog(signal))
                    menu.addAction(enum_action)
        
        
        else:
            # Generic Node (LD, LN, DO)
            node = data
            if hasattr(node, 'name'):
                # Build address by traversing parents
                full_address = self._build_node_address(root_item)
                
                copy_action = QAction("Copy node Address", self)
                copy_action.triggered.connect(lambda: self._copy_to_clipboard(full_address))
                menu.addAction(copy_action)
                # Expand/Collapse for generic node
                menu.addSeparator()
                expand_action = QAction("Expand All", self)
                expand_action.triggered.connect(lambda: self._expand_subtree(root_item))
                menu.addAction(expand_action)

                collapse_action = QAction("Collapse All", self)
                collapse_action.triggered.connect(lambda: self._collapse_subtree(root_item))
                menu.addAction(collapse_action)
        
        if menu.actions():
            menu.exec(self.tree_view.viewport().mapToGlobal(position))
    
    def _find_device_for_item(self, item: QStandardItem) -> Optional[str]:
        """Find the device name by traversing up to the root, skipping folders."""
        current = item
        while current:
            data = current.data(Qt.UserRole)
            is_folder = current.data(Qt.UserRole + 1) == "FOLDER"
            
            if isinstance(data, str) and not is_folder:
                # Found device name
                return data
            current = current.parent()
        return None

    def _confirm_remove_device(self, device_name):
        """Asks user for confirmation before removing device."""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, 
            "Remove Device",
            f"Are you sure you want to remove device '{device_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.device_manager.remove_device(device_name)

    def _edit_device(self, device_name):
        """Opens dialog to edit device."""
        device = self.device_manager.get_device(device_name)
        if not device:
            return
        
        # We need to import ConnectionDialog here to avoid circular imports if any
        # Assuming it's imported at top, but if not:
        from src.ui.widgets.connection_dialog import ConnectionDialog
            
        dialog = ConnectionDialog(self)
        dialog.set_config(device.config)
        
        if dialog.exec():
            new_config = dialog.get_config()
            self.device_manager.update_device_config(new_config)

    def _copy_to_clipboard(self, text):
        """Copies given text to system clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _invoke_control_dialog(self, device_name, signal):
        """Open control dialog for a signal (separated to avoid lambda closure issues)."""
        try:
            # Use Modbus-specific control UI for Modbus devices
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
            logger.exception("Failed to open control dialog")

    def _show_modbus_slave_dialog(self, device_name):
        """Shows the Modbus Slave configuration dialog (register editor)."""
        device = self.device_manager.get_device(device_name)
        # Ensure protocol exists even if not "connected" (started)
        protocol = self.device_manager.get_protocol(device_name)
        
        if not device or not protocol:
            logger.error(f"Cannot configure registers: Device or Protocol missing for {device_name}")
            return
            
        from src.ui.widgets.modbus_slave_widget import ModbusSlaveWidget
        
        # Pass the correct event logger from device manager
        event_logger = getattr(self.device_manager, 'event_logger', None)
        dlg = ModbusSlaveWidget(event_logger=event_logger, device_config=device.config, server_adapter=protocol)
        
        def on_slave_update():
            self.device_manager.save_configuration()
            # Force re-discovery to update tree structure with new blocks or status
            device.root_node = protocol.discover()
            self._refresh_device_node(device_name)
            # Ensure connection status is synced
            if protocol.is_connected():
                device.connected = True
                self._update_status_indicator(device_name, True)

        dlg.config_updated.connect(on_slave_update)
        dlg.server_started.connect(on_slave_update)
        dlg.server_stopped.connect(lambda: self._update_status_indicator(device_name, False))
    
        # Important: Keep reference to prevent GC if not using exec()
        # If we want a non-blocking window:
        dlg.setWindowTitle(f"Modbus Slave Configuration - {device_name}")
        dlg.setWindowModality(Qt.NonModal) 
        dlg.show()
        self._slave_dialogs = getattr(self, '_slave_dialogs', {})
        self._slave_dialogs[device_name] = dlg

    def _expand_subtree(self, item: QStandardItem):
        """Recursively expand the given QStandardItem and all its children in the view."""
        if item is None:
            return

        def recurse(it: QStandardItem):
            try:
                idx = it.index()
                if idx.isValid():
                    self.tree_view.expand(idx)
            except Exception:
                pass
            for i in range(it.rowCount()):
                child = it.child(i)
                if child:
                    recurse(child)

        recurse(item)

    def _collapse_subtree(self, item: QStandardItem):
        """Recursively collapse the given QStandardItem and all its children in the view."""
        if item is None:
            return

        def recurse(it: QStandardItem):
            for i in range(it.rowCount()):
                child = it.child(i)
                if child:
                    recurse(child)
            try:
                idx = it.index()
                if idx.isValid():
                    self.tree_view.collapse(idx)
            except Exception:
                pass

        recurse(item)

    def _show_modbus_inspector(self, device_name):
        """Show the Modbus Data Inspector dialog"""
        from src.protocols.modbus.adapter import ModbusTCPAdapter
        
        adapter = self.device_manager.get_protocol(device_name)
        if not adapter or not isinstance(adapter, ModbusTCPAdapter):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Inspector only available for Modbus TCP devices.")
            return
            
        dialog = ModbusInspectorDialog(device_name, adapter, self)
        dialog.show() # Non-modal is better so user can look at other things
        # Store reference to prevent GC
        if not hasattr(self, '_inspector_dialogs'):
            self._inspector_dialogs = []
        self._inspector_dialogs.append(dialog)

    def _show_modbus_range_dialog(self, device_name):
        """Shows the dialog to configure Modbus address ranges."""
        device = self.device_manager.get_device(device_name)
        if not device: return
        
        from src.ui.widgets.modbus_range_dialog import ModbusRangeDialog
        dialog = ModbusRangeDialog(device.config, self)
        if dialog.exec():
            # Update config
            device.config.modbus_register_maps = dialog.get_register_maps()
            self.device_manager.save_configuration()
            # Re-discover (it's internal for Modbus, just rebuilds nodes)
            protocol = self.device_manager.get_protocol(device_name)
            if protocol:
                device.root_node = protocol.discover()
                self._refresh_device_node(device_name)
            else:
                # If not connected, we can still update via offline (mimic)
                self.device_manager.load_offline_scd(device_name)

    def _toggle_polling(self, device_name):
        """Toggles continuous polling for a device."""
        device = self.device_manager.get_device(device_name)
        if device:
            device.config.polling_enabled = not device.config.polling_enabled
            self.device_manager.save_configuration()
            logger.info(f"Polling {'enabled' if device.config.polling_enabled else 'disabled'} for {device_name}")

    def _add_new_device(self, folder: str = ""):
        """Shows connection dialog to add a new device."""
        from src.ui.widgets.connection_dialog import ConnectionDialog
        dialog = ConnectionDialog(self)
        if folder:
            # We need to add a way to set folder in ConnectionDialog if we want to pre-fill
            # For now, let's assume we can pre-set it if we modify ConnectionDialog.
            # I added folder_input to ConnectionDialog, so I can set it.
            dialog.folder_input.setText(folder)
            
        if dialog.exec():
            config = dialog.get_config()
            try:
                self.device_manager.add_device(config)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Could not add device: {e}")

    def _show_add_folder_dialog(self):
        """Simple dialog to get folder name."""
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Folder", "Folder Name:")
        if ok and name.strip():
            self._get_folder_node(name.strip())

    def _remove_folder(self, folder_name: str):
        """Asks to remove folder and its contents."""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Remove Folder", 
            f"Are you sure you want to remove folder '{folder_name}' and all devices inside?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Get all devices in this folder
            folder_node = self.folder_items.get(folder_name)
            if folder_node:
                devices_to_remove = []
                for row in range(folder_node.rowCount()):
                    child = folder_node.child(row, 0)
                    dev_name = child.data(Qt.UserRole)
                    if isinstance(dev_name, str):
                        devices_to_remove.append(dev_name)
                
                for dev_name in devices_to_remove:
                    self.device_manager.remove_device(dev_name)
            
            # The _remove_device_node should handle empty folder cleanup, 
            # but if it was already empty or had no devices:
            if folder_name in self.folder_items:
                node = self.folder_items[folder_name]
                self.model.invisibleRootItem().removeRow(node.row())
                del self.folder_items[folder_name]

    def _build_node_address(self, item):
        """Builds address string from tree hierarchy."""
        path_parts = []
        current = item
        while current:
            data = current.data(Qt.UserRole)
            # Stop if we hit Device or Folder
            if isinstance(data, str) or current.data(Qt.UserRole + 1) == "FOLDER":
                break
            
            path_parts.insert(0, current.text())
            current = current.parent()
            
        if not path_parts:
            return ""
            
        # Format: LD/LN.DO...
        if len(path_parts) > 1:
            return f"{path_parts[0]}/{'.'.join(path_parts[1:])}"
        return path_parts[0]

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

    def _show_data_inspector(self, signal, device_name):
        """Shows the Data Inspector dialog for a Modbus signal."""
        from src.ui.dialogs.data_inspector_dialog import DataInspectorDialog
        dlg = DataInspectorDialog(signal, device_name, self.device_manager, self)
        dlg.exec()
    
    def _show_enumeration_dialog(self, signal):
        """Shows the enumeration mapping for a signal."""
        from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QLabel
        
        # 1. Determine Enum Type
        # Heuristics based on attribute name or CDC
        # Standard IEC 61850 Enums (simplified)
        STANDARD_ENUMS = {
            "Beh": {1: "on", 2: "blocked", 3: "test", 4: "test/blocked", 5: "off"},
            "Mod": {1: "on", 2: "blocked", 3: "test", 4: "test/blocked", 5: "off"},
            "Health": {1: "Ok", 2: "Warning", 3: "Alarm"},
            "ctlModel": {0: "status-only", 1: "direct-with-normal-security", 2: "sbo-with-normal-security", 3: "direct-with-enhanced-security", 4: "sbo-with-enhanced-security"},
            "sboClass": {0: "operate-once", 1: "operate-many"},
            "orCat": {1: "not-supported", 2: "bay-control", 3: "station-control", 4: "remote-control", 5: "automatic-bay", 6: "automatic-station", 7: "automatic-remote", 8: "maintenance"},
            "CmdBlk": {0: "none", 1: "block-select", 2: "block-operate", 3: "block-select-and-operate"},
            "Pos": {0: "intermediate", 1: "off", 2: "on", 3: "bad"}, # Double Point
            "dirGeneral": {0: "unknown", 1: "forward", 2: "backward", 3: "both"},
            "multiplier": {-24: "y", -21: "z", -18: "a", -15: "f", -12: "p", -9: "n", -6: "micro", -3: "m", -2: "c", -1: "d", 0: "", 1: "da", 2: "h", 3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E", 21: "Z", 24: "Y"}
        }

        # Match logic
        mapping = {}
        enum_name = "Unknown"
        
        # Explicit mapping in signal?
        if getattr(signal, 'enum_map', None):
             mapping = signal.enum_map
             enum_name = "Custom / SCD"
        else:
            # Check by name suffix
            name = signal.name
            if name in STANDARD_ENUMS:
                mapping = STANDARD_ENUMS[name]
                enum_name = name
            elif name == "stVal" or name == "ctlVal":
                 # Depends on parent... hard to know without context.
                 # Check access/type?
                 # If Double Binary (Dbpos)
                 if str(signal.modbus_data_type) == "DOUBLE_BINARY" or getattr(signal, 'signal_type', None) == "DOUBLE_BINARY":
                      mapping = STANDARD_ENUMS["Pos"]
                      enum_name = "Dbpos (Double Point)"
        
        if not mapping:
             # Just show a message
             from PySide6.QtWidgets import QMessageBox
             QMessageBox.information(self, "Enumeration", f"No known enumeration for '{signal.name}'.\n\n(Standard enums supported: Beh, Mod, Health, Pos, ctlModel, etc.)")
             return

        # Show Table
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Enumeration: {enum_name}")
        dlg.resize(300, 400)
        
        layout = QVBoxLayout(dlg)
        
        lbl = QLabel(f"Enumeration values for {signal.name} ({enum_name}):")
        layout.addWidget(lbl)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Value", "Label"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        
        layout.addWidget(table)
        
        # Populate
        # mapping can be dict of int->str
        row = 0
        sorted_keys = sorted(mapping.keys())
        table.setRowCount(len(sorted_keys))
        
        for key in sorted_keys:
            val_str = str(mapping[key])
            
            key_item = QTableWidgetItem(str(key))
            key_item.setFlags(key_item.flags() ^ Qt.ItemIsEditable)
            table.setItem(row, 0, key_item)
            
            val_item = QTableWidgetItem(val_str)
            val_item.setFlags(val_item.flags() ^ Qt.ItemIsEditable)
            table.setItem(row, 1, val_item)
            
            row += 1
            
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)
        
        dlg.exec()
