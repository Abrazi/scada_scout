from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QMenu, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QColor, QBrush, QDrag
from PySide6.QtCore import Qt, Signal as QtSignal, QItemSelectionModel, QMimeData, QByteArray
import fnmatch
import json
from typing import Optional, List
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.modbus_inspector_dialog import ModbusInspectorDialog
from src.models.device_models import DeviceType, DeviceRole, infer_device_role
import logging

logger = logging.getLogger(__name__)

class DraggableTreeView(QTreeView):
    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._owner = owner

    def startDrag(self, supportedActions):
        indexes = self.selectionModel().selectedIndexes()
        # Use only column-0 indexes to avoid duplicates
        seen = set()
        items = []
        for idx in indexes:
            if idx.column() != 0:
                continue
            # Avoid processing the same index twice
            key = (idx.row(), idx.parent())
            if key in seen:
                continue
            seen.add(key)

            item = self.model().itemFromIndex(idx)
            if not item:
                continue
            data = item.data(Qt.UserRole)
            # Use _owner to access DeviceTreeWidget methods
            device_name = self._owner._find_device_for_item(item)

            if data and hasattr(data, 'address'):
                unique_address = getattr(data, 'unique_address', '')
                if not unique_address and device_name and getattr(data, 'address', ''):
                    unique_address = f"{device_name}::{getattr(data, 'address', '')}"
                items.append({
                    'device': device_name,
                    'address': getattr(data, 'address', ''),
                    'signal_name': getattr(data, 'name', ''),
                    'unique_address': unique_address
                })
            else:
                # For non-signal items, include node identifier path
                items.append({
                    'device': device_name,
                    'node_name': item.text(),
                    'type': 'node'
                })

        if not items:
            return

        mime = QMimeData()
        payload = json.dumps(items)
        mime.setData('application/x-scadascout-signals', QByteArray(payload.encode('utf-8')))
        mime.setText(payload)

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

class DeviceTreeWidget(QWidget):
    """
    Widget containing the Device Tree View.
    Displays a hierarchy of Connections -> Devices -> Logical Nodes.
    """
    # Signals
    # Emits the selected Node object (or list of signals if we want)
    # For now, let's emit the Node object so the SignalsView can filter.
    selection_changed = QtSignal(object, str) # Node or Device or Signal, device_name
    add_to_live_data_requested = QtSignal(object) # Emits signal definition payload (allow node objects)
    show_event_log_requested = QtSignal() # Requests bringing Event Log to focus

    def __init__(self, device_manager, watch_list_manager=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.watch_list_manager = watch_list_manager
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Filter Bar
        from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QToolButton, QLabel
        filter_layout = QHBoxLayout()
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Search devices...")
        self.txt_filter.textChanged.connect(self._filter_tree)
        self.txt_filter.returnPressed.connect(self._select_next_match)
        filter_layout.addWidget(self.txt_filter)
        self.btn_next_match = QToolButton()
        self.btn_next_match.setText("Next")
        self.btn_next_match.setEnabled(False)
        self.btn_next_match.clicked.connect(self._select_next_match)
        filter_layout.addWidget(self.btn_next_match)
        self.lbl_filter_count = QLabel("")
        filter_layout.addWidget(self.lbl_filter_count)
        self.layout.addLayout(filter_layout)
        
        # from PySide6.QtWidgets import QTreeView
        # self.tree_view = QTreeView()
        self.tree_view = DraggableTreeView(self)
        self.layout.addWidget(self.tree_view)
        
        # Initialize attributes needed by methods
        self._open_control_dialogs = []
        self._suppress_selection_changed = False
        self._batch_loading = False
        self._pending_devices = []
        
        self._setup_view()
        
        self.folder_items = {}
        self.device_items = {}
        self._setup_model()
        self._connect_signals()
        
        # Connect batch load signals
        self.device_manager.batch_load_started.connect(self.start_batch_load)
        self.device_manager.batch_load_finished.connect(self.finish_batch_load)
        self.device_manager.batch_clear_started.connect(self._on_batch_clear_started)
        
        # Selection and Editing
        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.model.itemChanged.connect(self._on_item_changed)
        
        # Filter tracking
        self._filter_matches = []
        self._filter_match_index = -1

    def clear(self):
        """Clears all devices and folders from the tree."""
        self._setup_model(populate=False)

    def add_device(self, device):
        """Public method to add a device node to the tree."""
        self._add_device_node(device)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Delete:
            self._remove_selected_devices()
        else:
            super().keyPressEvent(event)
    
    def _filter_tree(self, text):
        """Find matches and jump to them without hiding any rows."""
        search = text.strip().lower()
        self._filter_matches = []
        self._filter_match_index = -1

        if not search:
            self.lbl_filter_count.setText("")
            self.btn_next_match.setEnabled(False)
            return

        root = self.model.invisibleRootItem()
        self._collect_filter_matches(root, search, self._filter_matches)

        if self._filter_matches:
            self._filter_match_index = 0
            self._select_match(self._filter_match_index)
            self.btn_next_match.setEnabled(len(self._filter_matches) > 1)
            self.lbl_filter_count.setText(f"1/{len(self._filter_matches)}")
        else:
            self.btn_next_match.setEnabled(False)
            self.lbl_filter_count.setText("0/0")

    def _collect_filter_matches(self, parent, search, matches):
        for row in range(parent.rowCount()):
            item = parent.child(row, 0)
            if not item:
                continue

            txt = item.text().lower() if item.text() else ""
            path_txt = self._item_path(item).lower()
            desc_item = parent.child(row, 2)
            if desc_item and desc_item.text():
                txt += " " + desc_item.text().lower()

            if self._matches_filter(txt, search) or self._matches_filter(path_txt, search):
                matches.append(item)

            if item.rowCount() > 0:
                self._collect_filter_matches(item, search, matches)

    def _matches_filter(self, text, search):
        if not search:
            return False

        if "*" in search or "?" in search:
            return fnmatch.fnmatch(text, search)

        return search in text

    def _item_path(self, item):
        parts = []
        current = item
        while current is not None:
            try:
                parts.append(current.text())
            except Exception:
                pass
            current = current.parent()
        parts.reverse()
        return ".".join(p for p in parts if p)

    def _select_next_match(self):
        if not self._filter_matches:
            return

        self._filter_match_index = (self._filter_match_index + 1) % len(self._filter_matches)
        self._select_match(self._filter_match_index)
        self.lbl_filter_count.setText(f"{self._filter_match_index + 1}/{len(self._filter_matches)}")

    def _select_match(self, match_index):
        try:
            item = self._filter_matches[match_index]
        except Exception:
            return

        # Expand to reveal match
        parent = item.parent()
        while parent is not None:
            try:
                self.tree_view.expand(parent.index())
            except Exception:
                pass
            parent = parent.parent()

        index = item.index()
        selection_model = self.tree_view.selectionModel()
        self._suppress_selection_changed = True
        selection_model.select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        selection_model.setCurrentIndex(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        self._suppress_selection_changed = False
        self.tree_view.scrollTo(index)

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
            if getattr(self, "_suppress_selection_changed", False):
                return
            indexes = self.tree_view.selectionModel().selectedIndexes()
            logger.debug(f"DeviceTreeWidget: Selection changed. Index count: {len(indexes)}")
            
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
            
            logger.debug(f"DeviceTreeWidget: Selected Device='{device_name}', Data Type={type(node_data)}")

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
        # Core tree functionality - MUST be set before other settings
        self.tree_view.setRootIsDecorated(True)  # Show branch lines and expand/collapse icons
        self.tree_view.setItemsExpandable(True)  # Allow items to be expanded
        self.tree_view.setExpandsOnDoubleClick(True)  # Double-click to expand
        self.tree_view.setIndentation(20)  # Set proper indentation for hierarchy
        self.tree_view.setAnimated(True)  # Smooth expand/collapse animation
        
        # Visual settings
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setUniformRowHeights(False)  # Allow variable row heights
        
        # Selection and editing
        self.tree_view.setSelectionBehavior(QTreeView.SelectRows)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)  # Enable Ctrl/Shift multi-selection
        self.tree_view.setEditTriggers(QTreeView.DoubleClicked | QTreeView.EditKeyPressed)
        
        # Header configuration
        self.tree_view.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree_view.header().setMinimumSectionSize(120)  # Make cells bigger by default
        self.tree_view.header().setSectionsMovable(True)
        self.tree_view.header().setStretchLastSection(True)
        
        # Context Menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        
        # Double-click handler for status column
        self.tree_view.doubleClicked.connect(self._on_double_click)
        
        # NO stylesheet - use default Qt styling to ensure branch decorations work
        # Any custom styling can hide the +/- icons
        
    def _setup_model(self, populate=True):
        """Initializes the model and optionally populates with existing devices."""
        self.model = QStandardItemModel()
        # Column order: Name, Status, Description, FC, Type
        # Name MUST be first (column 0) for tree decorations to show
        self.model.setHorizontalHeaderLabels(["Name", "Status", "Description", "FC", "Type"])
        self.tree_view.setModel(self.model)

        # Do NOT move columns - tree decorations only appear on first visual column
        # The tree hierarchy is in column 0 (Name), so it must stay first visually
        
        # Explicitly ensure the tree is configured properly
        self.tree_view.reset()  # Reset view state
        
        self.folder_items.clear()
        self.device_items.clear()
        
        # Re-enable updates after clearing (in case batch clear disabled them)
        self.tree_view.setUpdatesEnabled(True)
        
        # Populate existing devices if requested
        if populate:
            for device in self.device_manager.get_all_devices():
                self._add_device_node(device)

    def start_batch_load(self):
        """Start batch loading mode - defers tree updates."""
        self._batch_loading = True
        self._pending_devices = []
        self.tree_view.setUpdatesEnabled(False)
    
    def finish_batch_load(self):
        """Finish batch loading - process all pending devices."""
        if not self._batch_loading:
            return
        
        self._batch_loading = False
        
        # Process pending devices in chunks to keep UI responsive
        from PySide6.QtCore import QTimer
        
        def process_batch():
            if not self._pending_devices:
                self.tree_view.setUpdatesEnabled(True)
                # Expand folders after load
                for i in range(self.model.rowCount()):
                    idx = self.model.index(i, 0)
                    self.tree_view.expand(idx)
                return
            
            # Process 5 devices at a time
            batch = self._pending_devices[:5]
            self._pending_devices = self._pending_devices[5:]
            
            for device in batch:
                self._suppress_selection_changed = True
                try:
                    parent = self._get_folder_node(device.config.folder)
                    
                    # Name (column 0)
                    name_item = QStandardItem(device.config.name)
                    name_item.setEditable(True)
                    name_item.setData(device.config.name, Qt.UserRole)

                    # Status (column 1)
                    status_text = "🟢" if device.connected else "🔴"
                    status_item = QStandardItem(status_text)
                    status_item.setEditable(False)
                    status_item.setTextAlignment(Qt.AlignCenter)
                    
                    desc_text = device.config.description or device.config.device_type.value
                    desc_item = QStandardItem(desc_text)
                    desc_item.setEditable(True)
                    fc_item = QStandardItem("")
                    role = getattr(device.config, 'device_role', None) or infer_device_role(device.config.device_type)
                    type_item = QStandardItem(role.value)
                    
                    parent.appendRow([name_item, status_item, desc_item, fc_item, type_item])
                    self.device_items[device.config.name] = name_item
                    
                    # If device was added to a folder, expand the folder to show it
                    if device.config.folder and parent != self.model.invisibleRootItem():
                        self.tree_view.expand(parent.index())
                    
                    # Add children if discovery happened
                    if device.root_node:
                        for child in device.root_node.children:
                            self._add_node_recursive(name_item, child)
                        
                        # Expand the device node to show its children
                        self.tree_view.expand(name_item.index())
                finally:
                    self._suppress_selection_changed = False
            
            # Schedule next batch
            QTimer.singleShot(0, process_batch)
        
        # Start processing
        QTimer.singleShot(0, process_batch)
    
    def _on_batch_clear_started(self):
        """Disable updates during batch device removal."""
        self.tree_view.setUpdatesEnabled(False)
    
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
            # pass
        except Exception:
            # Older versions may not have the signal; ignore
            pass
        
    def _refresh_device_node(self, device_name):
        """Refreshes a device node (re-adds children)."""
        logger.info(f"Refreshing device '{device_name}'")
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
                logger.info(f"  Clearing {item.rowCount()} existing children")
                item.removeRows(0, item.rowCount())
            
            # 3. Re-populate
            device = self.device_manager.get_device(device_name)
            if device:
                # Update status/description/type to reflect role changes
                status_item = item.index().siblingAtColumn(1).model().itemFromIndex(item.index().siblingAtColumn(1))
                desc_item = item.index().siblingAtColumn(2).model().itemFromIndex(item.index().siblingAtColumn(2))
                type_item = item.index().siblingAtColumn(4).model().itemFromIndex(item.index().siblingAtColumn(4))
                if status_item:
                    status_item.setText("🟢" if device.connected else "🔴")
                if desc_item:
                    desc_item.setText(device.config.description or device.config.device_type.value)
                if type_item:
                    role = getattr(device.config, 'device_role', None) or infer_device_role(device.config.device_type)
                    type_item.setText(role.value)

            if device and device.root_node:
                child_count = len(device.root_node.children)
                logger.info(f"  Adding {child_count} children to '{device_name}'")
                for child in device.root_node.children:
                    self._add_node_recursive(item, child)
            
            # 4. Auto-expand and update view
            self.tree_view.expand(item.index())
            self.tree_view.update(item.index())  # Force view refresh
            logger.info(f"  Expanded and refreshed device '{device_name}'")
            
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
                  self._suppress_selection_changed = True
                  selection_model.select(item.index(), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                  self._suppress_selection_changed = False
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
        
        logger.info(f"Created folder '{folder_name}' in tree")
        return folder_item

    def _add_device_node(self, device):
        """Adds a device to the tree."""
        # Queue for batch processing if in batch mode
        if self._batch_loading:
            self._pending_devices.append(device)
            return
        
        logger.info(f"Adding device '{device.config.name}' to tree (folder='{device.config.folder}', has_root_node={device.root_node is not None})")
        
        # Suppress selection events while programmatically adding device
        self._suppress_selection_changed = True
        try:
            parent = self._get_folder_node(device.config.folder)
            
            # Name (column 0)
            name_item = QStandardItem(device.config.name)
            name_item.setEditable(True)
            # Store device name in data for easy retrieval on the name_item
            name_item.setData(device.config.name, Qt.UserRole)

            # Connection status dot (column 1)
            status_text = "🟢" if device.connected else "🔴"
            status_item = QStandardItem(status_text)
            status_item.setEditable(False)
            status_item.setTextAlignment(Qt.AlignCenter)
            
            desc_text = device.config.description or device.config.device_type.value
            desc_item = QStandardItem(desc_text)
            desc_item.setEditable(True)
            fc_item = QStandardItem("")
            role = getattr(device.config, 'device_role', None) or infer_device_role(device.config.device_type)
            type_item = QStandardItem(role.value)
            
            # Row layout: [Name, Status, Description, FC, Type]
            parent.appendRow([name_item, status_item, desc_item, fc_item, type_item])
            self.device_items[device.config.name] = name_item
            
            # If device was added to a folder, expand the folder to show it
            if device.config.folder and parent != self.model.invisibleRootItem():
                logger.info(f"  Expanding folder '{device.config.folder}' to show device")
                self.tree_view.expand(parent.index())
            
            # Verify item was added
            logger.info(f"  Device item has {name_item.rowCount()} rows (children)")
            
            # Recursively add children if discovery happened
            if device.root_node:
                child_count = len(device.root_node.children)
                logger.info(f"  Adding {child_count} children to device '{device.config.name}'")
                for child in device.root_node.children:
                    self._add_node_recursive(name_item, child)
                
                logger.info(f"  After adding children, device item has {name_item.rowCount()} rows")
                
                # Expand the device node to show its children
                self.tree_view.expand(name_item.index())
                logger.info(f"  Expanded device '{device.config.name}' to show children")
                
                # Force viewport update to ensure decorations appear
                self.tree_view.viewport().update()
            else:
                logger.info(f"  Device '{device.config.name}' has no root_node yet")
                
            # Log tree state
            logger.info(f"Tree now has {self.model.rowCount()} top-level items")
        finally:
            self._suppress_selection_changed = False

    def _add_node_recursive(self, parent_item: QStandardItem, node):
        """Recursively adds nodes to the tree."""
        # Col 0: Name (Hierarchy parent)
        item_name = QStandardItem(node.name)
        item_name.setEditable(True)
        item_name.setData(node, Qt.UserRole)
        
        # Ensure item is selectable and enabled
        item_name.setFlags(item_name.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)

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
        
        # If this item has children, make sure Qt knows it's expandable
        if item_name.hasChildren():
            # This shouldn't be necessary, but let's be explicit
            pass
    
    def _add_signal_node(self, parent_item: QStandardItem, sig):
        """Adds a signal as a child row."""
        # Col 0: Name
        sig_name_item = QStandardItem(sig.name)
        sig_name_item.setEditable(True)
        sig_name_item.setData(sig, Qt.UserRole)

        # Col 1: Status (empty for signals)
        sig_status_item = QStandardItem("")
        sig_status_item.setEditable(False)
        
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
        
        parent_item.appendRow([sig_name_item, sig_status_item, sig_desc_item, sig_fc_item, sig_type_item])
        
    def _update_status_indicator(self, device_name, connected):
        """Updates the status dot for a device."""
        item = self.device_items.get(device_name)
        if item:
            # Status is column 1, name is column 0
            status_item = item.index().siblingAtColumn(1).model().itemFromIndex(item.index().siblingAtColumn(1))
            if status_item:
                status_item.setText("🟢" if connected else "🔴")
    
    def _on_double_click(self, index):
        """Handle double-click on tree items."""
        # Check if user double-clicked the status column (logical column 1)
        if index.column() != 1:
            return
        
        # Get the name item (column 0) to identify the device
        name_index = index.siblingAtColumn(0)
        if not name_index.isValid():
            return
        
        name_item = self.model.itemFromIndex(name_index)
        if not name_item:
            return
        
        data = name_item.data(Qt.UserRole)
        
        # Check if this is a device node (data is device name string)
        if isinstance(data, str):
            device_name = data
            device = self.device_manager.get_device(device_name)
            if not device:
                return
            
            # Toggle connection
            if device.connected:
                self.device_manager.disconnect_device(device_name)
            else:
                role = getattr(device.config, 'device_role', None) or infer_device_role(device.config.device_type)
                if role == DeviceRole.OFFLINE:
                    self._prompt_go_online(device_name, connect_after=True)
                else:
                    self.device_manager.connect_device(device_name)
                
            # Bring Event Log to focus to show connection progress
            self.show_event_log_requested.emit()

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

            val_text = self._format_signal_value(signal)
            base_desc = getattr(signal, 'description', '') or ''
            desc_item.setText(f"{base_desc}  Value: {val_text}")

            # Color by quality
            quality = getattr(signal, 'quality', None)
            brush = None
            if quality is not None:
                try:
                    from src.models.device_models import SignalQuality
                    from src.ui.theme_manager import get_theme_manager
                    from src.ui.theme_presets import ColorRole
                    
                    theme = get_theme_manager()
                    
                    if quality == SignalQuality.GOOD:
                        brush = QBrush(QColor(theme.get_color(ColorRole.QUALITY_GOOD)))
                    elif quality == SignalQuality.NOT_CONNECTED:
                        brush = QBrush(QColor(theme.get_color(ColorRole.QUALITY_NOT_CONNECTED)))
                    else:
                        brush = QBrush(QColor(theme.get_color(ColorRole.QUALITY_BAD)))
                except Exception:
                    brush = None

            if brush:
                desc_item.setForeground(brush)

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

    def _format_signal_value(self, signal) -> str:
        if signal is None or getattr(signal, "value", None) is None:
            return ""

        num, enum_label = self._extract_numeric_and_enum(signal)
        if num is not None:
            hex_str = f"0x{num:X}"
            if enum_label:
                return f"{hex_str} ({num}) {enum_label}"
            return f"{hex_str} ({num})"

        return str(getattr(signal, "value", ""))

    def _is_pos_stval(self, signal) -> bool:
        addr = (getattr(signal, "address", "") or "").lower()
        name = (getattr(signal, "name", "") or "").lower()
        return "pos.stval" in addr or "pos$stval" in addr or ("pos" in addr and name == "stval")

    def _extract_numeric_and_enum(self, signal) -> tuple[Optional[int], Optional[str]]:
        num = None
        enum_label = None

        mapping = getattr(signal, "enum_map", None)
        if not mapping and self._is_pos_stval(signal):
            mapping = {0: "intermediate", 1: "open", 2: "closed", 3: "bad"}

        val = getattr(signal, "value", None)
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
                    import re
                    m = re.search(r"\(([-]?\d+)\)", text)
                    if m:
                        num = int(m.group(1))
                    elif re.fullmatch(r"-?\d+", text):
                        num = int(text)
            except Exception:
                num = None

            if num is None and mapping:
                for k, v in mapping.items():
                    if str(v).lower() == text.lower():
                        num = int(k)
                        break

            if num is not None and not enum_label:
                import re
                m = re.match(r"(.+?)\s*\(\s*[-]?\d+\s*\)", text)
                if m:
                    enum_label = m.group(1).strip()

        if num is not None and mapping and num in mapping:
            enum_label = mapping[num]

        return num, enum_label

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
                    # Use the wrapper method to update config
                    try:
                        self.device_manager.update_device_config(new_config)
                    except Exception:
                        # Fallback to core call
                        try:
                            self.device_manager._core.update_device_config(new_config)
                        except Exception:
                            logger.exception("Failed to update device config during rename")
                else:
                    # Update description
                    device.config.description = new_text
                    logger.info(f"Updated description for device '{device_name}'")
                    self.device_manager.save_configuration()
                    
        elif data and hasattr(data, 'name'):
            # Signal or Node
            # Preserve old address/name for propagation
            try:
                old_unique = getattr(data, 'unique_address', None)
            except Exception:
                old_unique = None

            if col == 0:
                data.name = new_text
            else:
                data.description = new_text
            logger.debug(f"Updated {type(data).__name__} in-place: {new_text}")

            # If the user edited a signal/node, refresh unique addresses for the containing device
            try:
                device_name = self._find_device_for_item(name_item)
                if device_name:
                    dev = self.device_manager.get_device(device_name)
                    if dev and dev.root_node:
                        # Recalculate unique addresses
                        try:
                            self.device_manager._core._assign_unique_addresses(device_name, dev.root_node)
                        except Exception:
                            pass
                        # Emit device_updated so script editors and other listeners can react
                        try:
                            self.device_manager._core.emit('device_updated', device_name)
                        except Exception:
                            pass
            except Exception:
                pass

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
            add_dev_action = QAction("Add Device...", self)
            add_dev_action.triggered.connect(self._add_new_device)
            menu.addAction(add_dev_action)

            # Quick add OPC UA shortcuts (convenience)
            add_opc_client = QAction("Add OPC UA Client...", self)
            add_opc_client.triggered.connect(lambda: self._add_new_device_preselected('opc_client'))
            menu.addAction(add_opc_client)
            add_opc_server = QAction("Add OPC UA Server...", self)
            add_opc_server.triggered.connect(lambda: self._add_new_device_preselected('opc_server'))
            menu.addAction(add_opc_server)
            
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
            
            # ... folder actions ...
            if clicked_text:
                copy_action = QAction(f"Copy '{clicked_text}'", self)
                copy_action.triggered.connect(lambda: self._copy_to_clipboard(clicked_text))
                menu.addAction(copy_action)
                menu.addSeparator()

            add_dev_action = QAction("Add Device to Folder...", self)
            add_dev_action.triggered.connect(lambda: self._add_new_device(folder=root_item.text()))
            menu.addAction(add_dev_action)

            # Folder-scoped quick OPC actions
            add_opc_client = QAction("Add OPC UA Client to Folder...", self)
            add_opc_client.triggered.connect(lambda: self._add_new_device_preselected('opc_client', folder=root_item.text()))
            menu.addAction(add_opc_client)
            add_opc_server = QAction("Add OPC UA Server to Folder...", self)
            add_opc_server.triggered.connect(lambda: self._add_new_device_preselected('opc_server', folder=root_item.text()))
            menu.addAction(add_opc_server)
            
            remove_folder_action = QAction("Remove Folder", self)
            remove_folder_action.triggered.connect(lambda: self._remove_folder(root_item.text()))
            menu.addAction(remove_folder_action)
            
            menu.exec(self.tree_view.viewport().mapToGlobal(position))
            return

        menu = QMenu()
        
        # Identify what data object we have
        # data could be: str (Device), Signal, or Node (Generic container)
        
        is_device_node = isinstance(data, str)
        from src.models.device_models import Signal, Node, DeviceType
        is_signal_node = isinstance(data, Signal) or (hasattr(data, 'name') and hasattr(data, 'address') and not hasattr(data, 'children'))
        is_container_node = isinstance(data, Node) or (hasattr(data, 'children') and not is_device_node)

        # Common actions
        if clicked_text:
            copy_action = QAction(f"Copy '{clicked_text}'", self)
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(clicked_text))
            menu.addAction(copy_action)
            menu.addSeparator()

        # RECURSIVE ADD FOR CONTAINERS (Device or Node)
        if is_device_node or is_container_node:
            add_recursive_action = QAction("Add All to Live Data", self)
            
            def request_add_recursive():
                # For Device Node (str), we need the object
                if is_device_node:
                    device_name = data
                    device = self.device_manager.get_device(device_name)
                    target_node = device.root_node if device else None
                else:
                    # Generic Node
                    # Find device name
                    device_name = self._find_device_for_item(root_item)
                    target_node = data
                
                if target_node:
                    payload = {
                        "device": device_name,
                        "node": target_node
                    }
                    self.add_to_live_data_requested.emit(payload)
                    # Event log
                    try:
                        evt = getattr(self.device_manager, 'event_logger', None)
                        if evt:
                            node_name = getattr(target_node, 'name', 'Device')
                            evt.info(device_name or "Live Data", f"Add All to Live Data requested for {node_name}")
                    except Exception:
                        pass
            
            add_recursive_action.triggered.connect(request_add_recursive)
            menu.addAction(add_recursive_action)
            menu.addSeparator()

            # Add all signals under this node/device to Watch List
            add_recursive_watch = QAction("Add All to Watch List", self)

            def request_add_recursive_watch():
                if not self.watch_list_manager:
                    return

                # Resolve target node
                if is_device_node:
                    device_name = data
                    device = self.device_manager.get_device(device_name)
                    target_node = device.root_node if device else None
                else:
                    device_name = self._find_device_for_item(root_item)
                    target_node = data

                if not target_node or not device_name:
                    return

                # Collect all signals under target node (including subnodes)
                def _collect(node_obj):
                    collected = []
                    if hasattr(node_obj, 'signals') and node_obj.signals:
                        collected.extend(node_obj.signals)
                    if hasattr(node_obj, 'children') and node_obj.children:
                        for child in node_obj.children:
                            collected.extend(_collect(child))
                    if hasattr(node_obj, 'root_node') and node_obj.root_node:
                        collected.extend(_collect(node_obj.root_node))
                    return collected

                signals = _collect(target_node)
                for sig in signals:
                    try:
                        self.watch_list_manager.add_signal(device_name, sig)
                    except Exception:
                        continue

                # Event log
                try:
                    evt = getattr(self.device_manager, 'event_logger', None)
                    if evt:
                        node_name = getattr(target_node, 'name', 'Device')
                        evt.info(device_name or "Watch List", f"Added {len(signals)} signals to Watch List from {node_name}")
                except Exception:
                    pass

            add_recursive_watch.triggered.connect(request_add_recursive_watch)
            menu.addAction(add_recursive_watch)

        if is_device_node:
            # Device specific actions
            device_name = data
            device = self._resolve_device(device_name, root_item)
            if device:
                # Automation scripts (Python / IEC 61131)
                scripts_menu = menu.addMenu("Automation Scripts")

                python_scripts_action = QAction("Python Scripts...", self)
                python_scripts_action.triggered.connect(lambda: self._open_python_scripts_for_device(device_name))
                scripts_menu.addAction(python_scripts_action)

                iec61131_scripts_action = QAction("IEC 61131 Scripts...", self)
                iec61131_scripts_action.triggered.connect(lambda: self._open_iec61131_scripts_for_device(device_name))
                scripts_menu.addAction(iec61131_scripts_action)

                scripts_menu.addSeparator()

                stop_python_action = QAction("Stop Python Scripts for Device", self)
                stop_python_action.triggered.connect(lambda: self._stop_device_python_scripts(device_name))
                scripts_menu.addAction(stop_python_action)

                stop_iec_action = QAction("Stop IEC 61131 Scripts for Device", self)
                stop_iec_action.triggered.connect(lambda: self._stop_device_iec61131_scripts(device_name))
                scripts_menu.addAction(stop_iec_action)

                menu.addSeparator()

                # PLC IDE for program development
                plc_ide_action = QAction("Open PLC IDE...", self)
                plc_ide_action.triggered.connect(lambda: self._open_plc_ide(device_name))
                menu.addAction(plc_ide_action)

                menu.addSeparator()

                # IEC 61850: Add switchgear status (XCBR/CSWI/XSWI Pos.stVal) to Watch List
                if device.config.device_type in (DeviceType.IEC61850_IED, DeviceType.IEC61850_SERVER):
                    switchgear_action = QAction("Add All Switchgear Status to Watch List", self)

                    def request_add_switchgear_status():
                        if not self.watch_list_manager:
                            return
                        if not device.root_node:
                            return

                        def _collect_switchgear(node_obj):
                            collected = []
                            if hasattr(node_obj, 'signals') and node_obj.signals:
                                for sig in node_obj.signals:
                                    addr = (sig.address or "").lower()
                                    name = (sig.name or "").lower()
                                    has_class = any(cls in addr or cls in name for cls in ("xcbr", "cswi", "xswi"))
                                    has_pos = "pos" in addr or "pos" in name
                                    has_stval = "stval" in addr or "stval" in name or "st$" in addr
                                    if has_class and has_pos and has_stval:
                                        collected.append(sig)
                            if hasattr(node_obj, 'children') and node_obj.children:
                                for child in node_obj.children:
                                    collected.extend(_collect_switchgear(child))
                            if hasattr(node_obj, 'root_node') and node_obj.root_node:
                                collected.extend(_collect_switchgear(node_obj.root_node))
                            return collected

                        signals = _collect_switchgear(device.root_node)
                        for sig in signals:
                            try:
                                self.watch_list_manager.add_signal(device_name, sig)
                            except Exception:
                                continue

                        # Event log
                        try:
                            evt = getattr(self.device_manager, 'event_logger', None)
                            if evt:
                                evt.info(device_name or "Watch List", f"Added {len(signals)} switchgear status signals to Watch List")
                        except Exception:
                            pass

                    switchgear_action.triggered.connect(request_add_switchgear_status)
                    menu.addAction(switchgear_action)
                    
                    # Control Switchgear (Global search)
                    control_all_action = QAction("Control Switchgear (Global Discovery)...", self)
                    control_all_action.triggered.connect(lambda checked=False, d=device_name, n=device.root_node: self._invoke_switchgear_control_flow(d, n))
                    menu.addAction(control_all_action)
                    
                    menu.addSeparator()

                # IEC 61850 simulation shortcut for existing devices
                if device.config.device_type in (DeviceType.IEC61850_IED, DeviceType.IEC61850_SERVER):
                    if device.config.device_type == DeviceType.IEC61850_IED:
                        sim_label = "Simulate Device..."
                    else:
                        sim_label = "Start Simulation"
                    simulate_action = QAction(sim_label, self)
                    simulate_action.triggered.connect(lambda: self._simulate_existing_device(device_name))
                    if device.config.device_type == DeviceType.IEC61850_SERVER and device.connected:
                        simulate_action.setEnabled(False)
                    menu.addAction(simulate_action)
                    menu.addSeparator()

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
                role = getattr(device.config, 'device_role', None) or infer_device_role(device.config.device_type)
                if device.connected:
                    disc_action = QAction("Disconnect", self)
                    disc_action.triggered.connect(lambda: self.device_manager.disconnect_device(device_name))
                    menu.addAction(disc_action)
                elif role == DeviceRole.OFFLINE:
                    go_online_action = QAction("Go Online (Switch to Client)", self)
                    go_online_action.triggered.connect(lambda: self._prompt_go_online(device_name, connect_after=True))
                    menu.addAction(go_online_action)
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
                elif device.config.device_type in (DeviceType.MODBUS_RTU_MASTER, DeviceType.MODBUS_RTU_SLAVE, DeviceType.MODBUS_RTU_SIMULATOR):
                    # RTU devices: Define Address Ranges
                    range_action = QAction("Define Address Ranges...", self)
                    range_action.triggered.connect(lambda: self._show_modbus_range_dialog(device_name))
                    menu.addAction(range_action)

                # Edit and Remove
                menu.addSeparator()
                if device.config.device_type == DeviceType.IEC61850_IED:
                    export_ied_action = QAction("Export Selected IED (.iid/.icd/.scd)...", self)
                    export_ied_action.triggered.connect(lambda: self._trigger_export_selected_ied(device_name))
                    menu.addAction(export_ied_action)

                    menu.addSeparator()

                # Properties
                properties_action = QAction("Properties...", self)
                properties_action.triggered.connect(lambda: self._show_device_properties(device_name))
                menu.addAction(properties_action)
                
                menu.addSeparator()
                
                edit_action = QAction("Edit Connection", self)
                edit_action.triggered.connect(lambda: self._edit_device(device_name))
                menu.addAction(edit_action)
                
                remove_action = QAction("Remove Device", self)
                remove_action.triggered.connect(lambda: self._confirm_remove_device(device_name))
                menu.addAction(remove_action)
                
                # Modbus Export
                if device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
                    menu.addSeparator()
                    export_action = QAction("Export Configuration...", self)
                    export_action.triggered.connect(lambda: self._export_device_config(device))
                    menu.addAction(export_action)
                
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
                    # Generic "Add to Live Data" (New Implementation)
                    add_live_action = QAction("Add to Live Data", self)
                    def request_add_live():
                        unique_address = getattr(signal, 'unique_address', '')
                        if not unique_address and device_name and getattr(signal, 'address', ''):
                            unique_address = f"{device_name}::{signal.address}"
                        # Construct payload
                        payload = {
                            "device": device_name,
                            "signal_name": signal.name,
                            "address": signal.address, # This is the key unique identifier
                            "unique_address": unique_address,
                            "description": signal.description,
                            "fc": getattr(signal, 'fc', getattr(signal, 'access', '')) 
                        }
                        self.add_to_live_data_requested.emit(payload)

                    add_live_action.triggered.connect(request_add_live)
                    menu.addAction(add_live_action)

                    # Legacy Direct Watch List Add (keep for now as backup/alternative)
                    watch_action = QAction("Add to Watch List (Legacy)", self)
                    # Use closure to capture variables
                    def add_watch():
                        self.watch_list_manager.add_signal(device_name, signal)
                        
                    watch_action.triggered.connect(add_watch)
                    menu.addAction(watch_action)

                # Add All to Live Data (for a selected signal: add its containing branch)
                # This emits the same payload shape as the container/device recursive action
                branch_recursive_action = QAction("Add All to Live Data", self)
                def request_add_all_from_signal():
                    # Find nearest ancestor node object (not the device string or folder)
                    parent = root_item.parent()
                    target_node = None
                    while parent is not None:
                        pdata = parent.data(Qt.UserRole)
                        is_folder = parent.data(Qt.UserRole + 1) == "FOLDER"
                        # Skip folders and device-name strings
                        if pdata and not isinstance(pdata, str) and not is_folder:
                            # Heuristic: node objects have 'children' or 'signals'
                            if hasattr(pdata, 'children') or hasattr(pdata, 'signals'):
                                target_node = pdata
                                break
                        parent = parent.parent()

                    # Fallback: if no parent node found, try device root_node
                    if target_node is None:
                        dev_name = self._find_device_for_item(root_item)
                        if dev_name:
                            dev = self.device_manager.get_device(dev_name)
                            if dev and hasattr(dev, 'root_node'):
                                target_node = dev.root_node

                    if target_node:
                        payload = {
                            "device": device_name,
                            "node": target_node
                        }
                        self.add_to_live_data_requested.emit(payload)

                branch_recursive_action.triggered.connect(request_add_all_from_signal)
                menu.addAction(branch_recursive_action)

                # Copy Address (only for single selection)
                if len(selected_signals) == 1:
                    unique_address = getattr(signal, 'unique_address', '')
                    if not unique_address and device_name and getattr(signal, 'address', ''):
                        unique_address = f"{device_name}::{signal.address}"
                    copy_unique_action = QAction("Copy Tag Address", self)
                    # Copy as tokenized form so it's ready for insertion into Python scripts
                    def _copy_tokenized(addr=unique_address, dev=device_name, sig=signal):
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
                    copy_unique_action.triggered.connect(_copy_tokenized)
                    menu.addAction(copy_unique_action)

                    copy_raw_action = QAction("Copy Raw Address", self)
                    copy_raw_action.triggered.connect(lambda: self._copy_to_clipboard(signal.address))
                    menu.addAction(copy_raw_action)
                
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
                    
                    # Context menu for manual ST injection on simulated servers
                    device = self._resolve_device(device_name, root_item)
                    if device and getattr(device.config, 'device_type', None) == DeviceType.IEC61850_SERVER:
                        inject_action = QAction("Set Value / Inject...", self)
                        # We use signal as target_node and construct full_address
                        full_address_sig = f"{device_name}::{signal.address}"
                        inject_action.triggered.connect(lambda checked=False, d=device_name, n=signal, a=full_address_sig: self._prompt_inject_value(d, n, a))
                        menu.addAction(inject_action)
                    
                    # Data Inspector (for Modbus signals only)
                    device = self._resolve_device(device_name, root_item)
                    if device and device.config.device_type in (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER):
                        inspector_action = QAction("Data Inspector...", self)
                        inspector_action.triggered.connect(lambda: self._show_data_inspector(signal, device_name))
                        menu.addAction(inspector_action)
                    elif device and device.config.device_type in (DeviceType.MODBUS_RTU_MASTER, DeviceType.MODBUS_RTU_SLAVE, DeviceType.MODBUS_RTU_SIMULATOR):
                        # For RTU signals: Define Address Range
                        range_action = QAction("Define Address Range...", self)
                        range_action.triggered.connect(lambda: self._show_modbus_range_dialog(device_name))
                        menu.addAction(range_action)

                    # Enumeration Inspection
                    enum_action = QAction("Show Enumeration", self)
                    enum_action.triggered.connect(lambda: self._show_enumeration_dialog(signal))
                    menu.addAction(enum_action)
        
        
        else:
            # Generic Node (LD, LN, DO)
            node = data
            if hasattr(node, 'name'):
                # Find the device name by traversing up the tree
                device_name = self._find_device_for_item(root_item)
                

                # Build address by traversing parents
                full_address = self._build_node_address(root_item)

                # Logical Device specific: Control Switchgear (CSWI Pos.Oper.ctlVal)
                is_logical_device = bool(device_name and full_address and "/" not in full_address)
                device = self._resolve_device(device_name, root_item) if device_name else None
                
                if is_logical_device:
                    if device and device.config.device_type in (DeviceType.IEC61850_IED, DeviceType.IEC61850_SERVER):
                        control_switchgear_action = QAction("Control Switchgear...", self)
                        control_switchgear_action.triggered.connect(lambda checked=False, d=device_name, n=node: self._invoke_switchgear_control_flow(d, n))
                        menu.addAction(control_switchgear_action)
                        menu.addSeparator()
                
                copy_action = QAction("Copy node Address", self)
                copy_action.triggered.connect(lambda: self._copy_to_clipboard(full_address))
                menu.addAction(copy_action)
                
                # Context menu for manual ST injection on simulated servers
                if device and getattr(device.config, 'device_type', None) == DeviceType.IEC61850_SERVER:
                    inject_action = QAction("Set Value / Inject...", self)
                    inject_action.triggered.connect(lambda checked=False, d=device_name, n=node, a=full_address: self._prompt_inject_value(d, n, a))
                    # Optionally only enable if we think it's a DA/ST node or DO, but typically any node address is fine
                    menu.addAction(inject_action)

                # Add to Live Data
                if hasattr(self, 'signals_view') and self.signals_view and device_name:
                    menu.addSeparator()
                    live_data_action = QAction("Add to Live Data", self)
                    live_data_action.triggered.connect(lambda checked=False, n=node, d=device_name: self._add_node_to_live_data(n, d))
                    menu.addAction(live_data_action)
                
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

    def _prompt_inject_value(self, device_name: str, target_node, full_address: str):
        """Prompt user for a value and manually inject it into the simulated server attribute."""
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        # Determine the signal to write to (assume the node itself if it's an attribute)
        signal = None
        
        # If target_node is already a Signal object
        if hasattr(target_node, 'address') and hasattr(target_node, 'value') and not hasattr(target_node, 'signals'):
            signal = target_node
        elif hasattr(target_node, 'signals') and target_node.signals:
            if len(target_node.signals) == 1:
                signal = target_node.signals[0]
            else:
                # Find the stVal signal if it's a DO
                signal = next((s for s in target_node.signals if ".stVal" in s.address), None)
                if not signal and full_address.endswith(".stVal"):
                    signal = next((s for s in target_node.signals if s.address == full_address.split("::")[-1]), None)

        if not signal:
            QMessageBox.warning(self, "Injection Error", "Could not determine target signal for injection. Select an attribute node (like stVal).")
            return

        current_val = getattr(signal, 'value', '')
        val_str, ok = QInputDialog.getText(self, "Set Value", f"Inject value for {signal.address}:", text=str(current_val))
        
        if ok and val_str:
            success = self.device_manager.write_signal(device_name, signal, val_str)
            if success:
                # Immediately poll the value back to reflect UI
                self._manual_read_signal(device_name, signal)
            else:
                QMessageBox.critical(self, "Injection Failed", f"Failed to inject value '{val_str}' into {signal.address}.")

    def _invoke_switchgear_control_flow(self, device_name: str, target_node):
        """
        Comprehensive switchgear discovery and control flow.
        Scans the provided node (Logical Device or entire Device) for control tags.
        """
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        
        if not target_node:
            return
            
        targets = []
        all_signals = []

        def _collect(n):
            if hasattr(n, 'signals') and n.signals:
                for sig in n.signals:
                    all_signals.append(sig)
                    addr = (sig.address or "")
                    addr_l = addr.lower()
                    
                    # Higher-permissivity matching for switchgear control
                    # Format: LD/LN.Pos.Oper.ctlVal or LD/LN$Pos$Oper$ctlVal
                    # Key attributes: ctlVal (write point)
                    has_ctlval = "ctlval" in addr_l
                    
                    # Check if it's a switchgear-related logical node
                    # ln_part is the part after the LD/ prefix
                    ln_part = ""
                    if "/" in addr_l:
                        ln_part = addr_l.split('/', 1)[1].split('.', 1)[0].split('$', 1)[0]
                    else:
                        ln_part = addr_l.split('.', 1)[0].split('$', 1)[0]
                        
                    is_switchgear_ln = any(cls in ln_part for cls in ["cswi", "xcbr", "xswi"])
                    
                    if has_ctlval and (is_switchgear_ln or "pos" in addr_l):
                        targets.append(sig)

            if hasattr(n, 'children') and n.children:
                for child in n.children:
                    _collect(child)

        _collect(target_node)
        
        if not targets:
            msg = f"No switchgear control points (.ctlVal) found in '{target_node.name}'.\n"
            msg += f"Signals scanned: {len(all_signals)}\n\n"
            msg += "Suggestions:\n"
            msg += "- Ensure the IED is connected and discovery is complete.\n"
            msg += "- Check if Logical Nodes contain CSWI, XCBR, or XSWI."
            QMessageBox.information(self, "Control Switchgear", msg)
            return

        # Sort targets by address for cleaner list
        targets.sort(key=lambda t: (t.address or ""))

        if len(targets) == 1:
            self._invoke_control_dialog(device_name, targets[0])
            return

        # Show selection dialog for multiple control points
        items = [t.address for t in targets]
        selected, ok = QInputDialog.getItem(
            self, 
            "Control Switchgear", 
            f"Discovered {len(targets)} control points. Select one:", 
            items, 
            0, 
            False
        )
        
        if ok and selected:
            chosen = next((t for t in targets if t.address == selected), None)
            if chosen:
                self._invoke_control_dialog(device_name, chosen)

    def _trigger_export_selected_ied(self, device_name: str):
        """Trigger export of a specific IED via main window."""
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, "_export_ied_scl_by_device"):
                main_window._export_ied_scl_by_device(device_name)
        except Exception as e:
            logger.error(f"DeviceTreeWidget: Failed to trigger IED export: {e}")
    
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

    def _resolve_device(self, device_name: str, item: Optional[QStandardItem] = None):
        """Robust device lookup: try exact name, fallback to text on the item, then case-insensitive search.

        This helps when the stored user-role data is out-of-sync with the DeviceManager keys
        (e.g., after an in-place rename or round-trip serialization).
        """
        if not device_name:
            device_name = ""

        # Try exact match first
        try:
            dev = self.device_manager.get_device(device_name)
            if dev:
                return dev
        except Exception:
            pass

        # Try using the item's visible text
        try:
            if item is not None:
                visible = item.text()
                if visible and visible != device_name:
                    dev = self.device_manager.get_device(visible)
                    if dev:
                        return dev
        except Exception:
            pass

        # Last resort: case-insensitive search through all devices
        try:
            for d in self.device_manager.get_all_devices():
                if d and d.config and d.config.name and d.config.name.lower() == str(device_name).lower():
                    return d
                if item is not None and d and d.config and d.config.name and d.config.name.lower() == item.text().lower():
                    return d
        except Exception:
            pass

        return None

    def get_selected_device_names(self) -> List[str]:
        """Return unique device names from the current tree selection."""
        selected = []
        try:
            selection_model = self.tree_view.selectionModel()
            if not selection_model:
                return selected

            for index in selection_model.selectedRows(0):
                item = self.model.itemFromIndex(index)
                if not item:
                    continue
                device_name = self._find_device_for_item(item)
                if device_name and device_name not in selected:
                    selected.append(device_name)
        except Exception as e:
            logger.error(f"DeviceTreeWidget: Failed to get selected devices: {e}")
        return selected

    def _remove_selected_devices(self):
        """Remove all selected devices after confirmation."""
        device_names = self.get_selected_device_names()
        if not device_names:
            return
        
        from PySide6.QtWidgets import QMessageBox
        if len(device_names) == 1:
            msg = f"Are you sure you want to remove device '{device_names[0]}'?"
            title = "Remove Device"
        else:
            msg = f"Are you sure you want to remove {len(device_names)} devices?\n\n" + "\n".join(f"• {name}" for name in device_names)
            title = "Remove Devices"
        
        reply = QMessageBox.question(
            self, 
            title,
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if len(device_names) == 1:
                self.device_manager.remove_device(device_names[0])
            else:
                try:
                     # Use efficient bulk removal
                     self.device_manager.remove_devices_bulk(device_names)
                except AttributeError:
                     # Fallback
                     for device_name in device_names:
                        self.device_manager.remove_device(device_name)
    
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
    
    def _show_device_properties(self, device_name):
        """Opens device properties dialog."""
        device = self.device_manager.get_device(device_name)
        if not device:
            return
        
        from src.ui.dialogs.device_properties_dialog import DevicePropertiesDialog
        dialog = DevicePropertiesDialog(device, self.device_manager, self.watch_list_manager, self)
        dialog.exec()

    def _copy_to_clipboard(self, text):
        """Copies given text to system clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _open_python_scripts_for_device(self, device_name: str):
        try:
            from src.ui.dialogs.python_script_dialog import PythonScriptDialog
            from shiboken6 import isValid
            
            dlg = getattr(self, '_python_script_dialog', None)
            if dlg is None or not isValid(dlg):
                dlg = PythonScriptDialog(self.device_manager, self)
                self._python_script_dialog = dlg
            if not dlg.txt_name.text().strip():
                dlg.txt_name.setText(f"{device_name}::Script")
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            logger.exception("Failed to open Python Scripts dialog")

    def _open_iec61131_scripts_for_device(self, device_name: str):
        try:
            from src.ui.dialogs.iec61131_script_dialog import IEC61131ScriptDialog
            from shiboken6 import isValid
            
            dlg = getattr(self, '_iec61131_script_dialog', None)
            if dlg is None or not isValid(dlg):
                dlg = IEC61131ScriptDialog(self.device_manager, self)
                self._iec61131_script_dialog = dlg
            if not dlg.txt_name.text().strip():
                dlg.txt_name.setText(f"{device_name}::Script")
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            logger.exception("Failed to open IEC 61131 Scripts dialog")

    def _stop_device_python_scripts(self, device_name: str):
        try:
            prefix = f"{device_name}::"
            running = self.device_manager.list_user_scripts()
            for name in running:
                if name.startswith(prefix):
                    self.device_manager.stop_user_script(name)
        except Exception:
            logger.exception("Failed to stop Python scripts for device")

    def _stop_device_iec61131_scripts(self, device_name: str):
        try:
            prefix = f"{device_name}::"
            running = self.device_manager.list_iec61131_scripts()
            for name in running:
                if name.startswith(prefix):
                    self.device_manager.stop_iec61131_script(name)
        except Exception:
            logger.exception("Failed to stop IEC 61131 scripts for device")

    def _open_plc_ide(self, device_name: str):
        """Open PLC IDE for device program development."""
        try:
            from src.ui.dialogs.plc_ide_window import PLCIDEWindow
            from shiboken6 import isValid
            
            # Check if IDE is already open for this device
            ide_attr = f'_plc_ide_{device_name}'
            dlg = getattr(self, ide_attr, None)
            
            if dlg is None or not isValid(dlg):
                dlg = PLCIDEWindow(self.device_manager, device_name, self)
                setattr(self, ide_attr, dlg)
            
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            logger.exception(f"Failed to open PLC IDE for device {device_name}")

    def _add_node_to_live_data(self, node, device_name):
        """Add a node and all its signals to the Live Data view."""
        # Be resilient to being passed a QStandardItem, an index-like object,
        # a device name (str) or the actual domain node object.
        try:
            from PySide6.QtGui import QStandardItem
        except Exception:
            QStandardItem = None

        resolved_node = node

        # If a QStandardItem was passed, unwrap the stored domain object
        if QStandardItem and isinstance(node, QStandardItem):
            try:
                resolved_node = node.data(Qt.UserRole)
            except Exception:
                resolved_node = node

        # If a device name string was passed, resolve to device object
        if isinstance(resolved_node, str):
            try:
                dev = self.device_manager.get_device(resolved_node)
                if dev:
                    resolved_node = dev
            except Exception:
                pass

        # Ensure we have a signals_view to receive the node
        if not (hasattr(self, 'signals_view') and self.signals_view):
            logger.warning("_add_node_to_live_data: No SignalsView connected")
            return

        # Ask the SignalsView to add signals. If it finds none, inform the user.
        prev_count = 0
        try:
            prev_count = self.signals_view.table_model.rowCount()
        except Exception:
            prev_count = 0

        self.signals_view.add_node_to_live(resolved_node, device_name)

        try:
            new_count = self.signals_view.table_model.rowCount()
        except Exception:
            new_count = prev_count

        if new_count == prev_count:
            # No new signals were appended — notify the user quietly
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Add to Live Data", "No signals were found in the selected node.")
            except Exception:
                logger.info("_add_node_to_live_data: No signals were added for node")


    def _invoke_control_dialog(self, device_name, signal):
        """Open control dialog for a signal (separated to avoid lambda closure issues)."""
        try:
            # Use Modbus-specific control UI for Modbus devices
            from src.models.device_models import DeviceType
            device = self.device_manager.get_device(device_name)
            modbus_types = (DeviceType.MODBUS_TCP, DeviceType.MODBUS_SERVER, 
                          DeviceType.MODBUS_RTU_MASTER, DeviceType.MODBUS_RTU_SLAVE, 
                          DeviceType.MODBUS_RTU_SIMULATOR)
            if device and device.config.device_type in modbus_types:
                from src.ui.widgets.modbus_write_dialog import ModbusWriteDialog
                dlg = ModbusWriteDialog(signal, self.device_manager, device_name, self)
                dlg.exec()
            else:
                from src.ui.dialogs.control_dialog import ControlDialog
                dlg = ControlDialog(device_name, signal, self.device_manager, self)
                dlg.setWindowModality(Qt.NonModal)
                dlg.setAttribute(Qt.WA_DeleteOnClose, True)
                self._open_control_dialogs.append(dlg)
                dlg.destroyed.connect(lambda: self._open_control_dialogs.remove(dlg) if dlg in self._open_control_dialogs else None)
                dlg.show()
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

        self.tree_view.setUpdatesEnabled(False)
        try:
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
        finally:
            self.tree_view.setUpdatesEnabled(True)

    def _collapse_subtree(self, item: QStandardItem):
        """Recursively collapse the given QStandardItem and all its children in the view."""
        if item is None:
            return

        self.tree_view.setUpdatesEnabled(False)
        try:
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
        finally:
            self.tree_view.setUpdatesEnabled(True)

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

    def _start_ied_simulator(self, device_name):
        """Start an IEC 61850 simulator for an imported IED"""
        from PySide6.QtWidgets import QMessageBox, QDialog
        from src.ui.dialogs.simulate_ied_dialog import SimulateIEDDialog
        
        device = self.device_manager.get_device(device_name)
        if not device:
            QMessageBox.warning(self, "Error", "Device not found")
            return
        
        if device.config.device_type != DeviceType.IEC61850_IED:
            QMessageBox.warning(self, "Error", "Simulation only available for IEC 61850 IED devices")
            return
        
        if not device.config.scd_file_path:
            QMessageBox.warning(
                self, 
                "No SCD File",
                "This IED was not imported from an SCD/ICD file.\n"
                "Simulation requires an SCD or ICD file."
            )
            return
        
        # Show dialog to configure simulator
        dialog = SimulateIEDDialog(device.config, self)
        if dialog.exec() == QDialog.Accepted:
            sim_config = dialog.get_simulator_config()

            # Ensure unique simulator name to avoid overwriting existing device
            base_name = sim_config.name
            if self.device_manager.get_device(base_name):
                idx = 1
                while self.device_manager.get_device(f"{base_name}_{idx}"):
                    idx += 1
                sim_config.name = f"{base_name}_{idx}"
            
            # Add the simulator as a new device
            try:
                self.device_manager.add_device(sim_config)
                
                # Start the server (this is async via worker thread)
                self.device_manager.connect_device(sim_config.name)
                
                # Show success message - the Event Log will show detailed status
                # Note: Connection happens asynchronously, so we show this immediately
                bind_msg = "on all network interfaces" if sim_config.ip_address == "0.0.0.0" else f"on {sim_config.ip_address}"
                QMessageBox.information(
                    self,
                    "Simulator Starting",
                    f"✅ IEC 61850 simulator is starting...\n\n"
                    f"Simulator Name: {sim_config.name}\n"
                    f"Listen Port: {sim_config.port} {bind_msg}\n\n"
                    f"Clients can connect to:\n"
                    f"  • Localhost: 127.0.0.1:{sim_config.port}\n"
                    f"  • Network: <your-ip>:{sim_config.port}\n\n"
                    f"Check the Event Log panel for detailed startup status."
                )
                    
            except Exception as e:
                error_msg = str(e)
                # Provide more helpful guidance for common IEC61850 library loading errors
                if "Could not load iec61850" in error_msg or "iec61850" in error_msg.lower():
                    detailed_msg = (
                        f"❌ Failed to start IEC 61850 simulator:\n\n"
                        f"Error: {error_msg}\n\n"
                        f"📌 Solution: The native libiec61850 library is not installed.\n\n"
                        f"Quick Fix Options:\n"
                        f"1️⃣ Download pre-built DLL from libiec61850 releases:\n"
                        f"   • Place iec61850.dll in: {os.path.abspath('lib')}\n"
                        f"   • Or add to System32 or PATH\n\n"
                        f"2️⃣ Build from source (see IEC61850_SETUP.md):\n"
                        f"   • Use MSYS2/MinGW or Visual Studio\n"
                        f"   • Follow step-by-step guide in project root\n\n"
                        f"3️⃣ Verify installation:\n"
                        f"   python -c \"from src.protocols.iec61850 import iec61850_wrapper; print('Loaded:', iec61850_wrapper.is_library_loaded())\"\n\n"
                        f"See IEC61850_SETUP.md in the project root for detailed instructions."
                    )
                else:
                    detailed_msg = f"Failed to start simulator:\n{error_msg}"
                    
                QMessageBox.critical(
                    self,
                    "Simulation Failed",
                    detailed_msg
                )

    def _simulate_existing_device(self, device_name):
        """Simulate an existing IEC 61850 device from the Device Explorer."""
        from PySide6.QtWidgets import QMessageBox

        device = self.device_manager.get_device(device_name)
        if not device:
            QMessageBox.warning(self, "Error", "Device not found")
            return

        if device.config.device_type == DeviceType.IEC61850_SERVER:
            if device.connected:
                QMessageBox.information(self, "Simulator", "Simulation is already running for this device.")
                return
            try:
                self.device_manager.connect_device(device_name)
                QMessageBox.information(
                    self,
                    "Simulator Starting",
                    f"Starting IEC 61850 simulator for {device_name}..."
                )
            except Exception as e:
                QMessageBox.critical(self, "Simulation Failed", f"Failed to start simulator:\n{e}")
            return

        if device.config.device_type != DeviceType.IEC61850_IED:
            QMessageBox.warning(self, "Error", "Simulation is only available for IEC 61850 devices")
            return

        self._start_ied_simulator(device_name)

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

    def _prompt_go_online(self, device_name: str, connect_after: bool = True):
        """Switch Offline devices to Client role before live communication."""
        from PySide6.QtWidgets import QMessageBox
        import copy

        device = self.device_manager.get_device(device_name)
        if not device:
            return

        reply = QMessageBox.question(
            self,
            "Go Online",
            f"'{device_name}' is Offline. Switch to Client role and connect?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        new_config = copy.deepcopy(device.config)
        new_config.device_role = DeviceRole.CLIENT
        self.device_manager.update_device_config(new_config)
        self.device_manager.save_configuration()

        if connect_after:
            self.device_manager.connect_device(device_name)

    def _add_new_device(self, folder: str = ""):
        """Shows unified Add Device dialog."""
        from src.ui.widgets.add_device_workflow import add_device_via_dialog

        add_device_via_dialog(
            self,
            self.device_manager,
            connect_immediately_default=False,
            folder=folder,
        )

    def _add_new_device_preselected(self, preset: str, folder: str = ""):
        """Open ConnectionDialog with a preset selection (used by quick-actions).

        preset: 'opc_client' | 'opc_server' currently supported.
        """
        from src.models.device_models import DeviceType as _DT
        from src.ui.widgets.add_device_workflow import add_device_via_dialog

        preset_device_type = None
        if preset == 'opc_client':
            preset_device_type = _DT.OPC_UA_CLIENT
        elif preset == 'opc_server':
            preset_device_type = _DT.OPC_UA_SERVER

        add_device_via_dialog(
            self,
            self.device_manager,
            connect_immediately_default=False,
            preset_device_type=preset_device_type,
            folder=folder,
        )

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

    def _export_device_config(self, device):
        """Export device configuration to JSON or CSV file."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json
        import csv
        
        fname, selected_filter = QFileDialog.getSaveFileName(
            self, 
            "Export Configuration", 
            f"{device.config.name}_config", 
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if not fname:
            return
            
        try:
            if fname.lower().endswith('.csv') or "csv" in selected_filter.lower():
                if not fname.lower().endswith('.csv'):
                    fname += ".csv"
                    
                # Export Register List to CSV
                # Export Register List to CSV
                with open(fname, 'w', newline='') as f:
                    writer = csv.writer(f)
                    # Standard Headers
                    headers = ["start_address", "count", "function_code", "data_type", "name_prefix", "description", "scale", "offset"]
                    writer.writerow(headers)
                    
                    if device.config.modbus_register_maps:
                         # Export Maps
                         for rmap in device.config.modbus_register_maps:
                             writer.writerow([
                                rmap.start_address, 
                                rmap.count,
                                rmap.function_code, 
                                rmap.data_type.name if hasattr(rmap.data_type, 'name') else str(rmap.data_type),
                                rmap.name_prefix,
                                rmap.description,
                                rmap.scale, 
                                rmap.offset
                            ])
                    else:
                         # Fallback: Export Discovered Signals as single-register maps
                         # Collect all signals recursively
                         signals = []
                         def collect_signals(node):
                             if hasattr(node, 'signals'):
                                 signals.extend(node.signals)
                             for child in node.children:
                                 collect_signals(child)
                                 
                         if device.root_node:
                             collect_signals(device.root_node)
                             
                         for sig in signals:
                             # Try to infer type
                             dtype = "UINT16" # Default
                             if hasattr(sig, 'modbus_data_type'): dtype = str(sig.modbus_data_type)
                             elif hasattr(sig, 'type'): dtype = str(sig.type)
                             
                             # Extract Function Code
                             fc = 3
                             if hasattr(sig, 'fc') and str(sig.fc).isdigit():
                                 fc = int(sig.fc)
                             
                             writer.writerow([
                                 sig.address,
                                 1, # Count
                                 fc,
                                 dtype,
                                 sig.name,
                                 sig.description or "",
                                 1.0, # Scale
                                 0.0  # Offset
                             ])
                        
                QMessageBox.information(self, "Export Successful", f"Exported to {fname}")
                
            else:
                if not fname.lower().endswith('.json'):
                    fname += ".json"
                    
                config_dict = device.config.to_dict()
                # Ensure name is up-to-date from the device object, not just staled config
                config_dict['name'] = device.config.name
                
                with open(fname, 'w') as f:
                    json.dump(config_dict, f, indent=2)
                
                QMessageBox.information(self, "Export Successful", f"Configuration exported to {fname}")
                
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            QMessageBox.critical(self, "Export Failed", f"Failed to export configuration:\n{e}")
