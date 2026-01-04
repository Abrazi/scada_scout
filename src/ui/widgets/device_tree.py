from PySide6.QtWidgets import QTreeView, QWidget, QVBoxLayout, QHeaderView, QMenu
from PySide6.QtGui import QAction, QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, Signal as QtSignal
from src.ui.widgets.connection_dialog import ConnectionDialog

class DeviceTreeWidget(QWidget):
    """
    Widget containing the Device Tree View.
    Displays a hierarchy of Connections -> Devices -> Logical Nodes.
    """
    # Signals
    # Emits the selected Node object (or list of signals if we want)
    # For now, let's emit the Node object so the SignalsView can filter.
    selection_changed = QtSignal(object) # Node or Device or None

    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tree_view = QTreeView()
        self.layout.addWidget(self.tree_view)
        
        self._setup_view()
        self._setup_model()
        self._connect_signals()
        
        # Selection
        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, selected, deselected):
        indexes = self.tree_view.selectionModel().selectedIndexes()
        if not indexes:
            self.selection_changed.emit(None)
            return
            
        # Get the first selected row (column 0)
        index = indexes[0]
        item = self.model.itemFromIndex(index)
        
        # We need to retrieve the Node object associated with this item.
        # We didn't store the Node object in UserRole! We only stored device_name on root.
        # We should modify _add_node_recursive to store the Node object.
        node_data = item.data(Qt.UserRole)
        
        # If it's a device root, it's a string (device_name).
        # We should standardize.
        
        if isinstance(node_data, str):
            # It's a device name, get the device object
            device = self.device_manager.get_device(node_data)
            self.selection_changed.emit(device) # Device is kinda like a Node (has root_node)
        else:
            # Assume it's a Node object (we need to update _add_node_recursive)
            self.selection_changed.emit(node_data)

    def _setup_view(self):
        """Configures the TreeView appearance."""
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSelectionBehavior(QTreeView.SelectRows)
        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_view.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # Context Menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        
    def _setup_model(self):
        """Initializes the model and populates with existing devices."""
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Name", "Description", "FC", "Type"])
        self.tree_view.setModel(self.model)
        
        # Populate existing devices
        for device in self.device_manager.get_all_devices():
            self._add_device_node(device)

    def _connect_signals(self):
        """Connects to DeviceManager signals."""
        self.device_manager.device_added.connect(self._add_device_node)
        self.device_manager.device_removed.connect(self._remove_device_node)
        self.device_manager.device_updated.connect(self._refresh_device_node)
        
    def _refresh_device_node(self, device_name):
        """Refreshes a device node (re-adds children)."""
        # Find the node
        root = self.model.invisibleRootItem()
        for row in range(root.rowCount()):
            item = root.child(row, 0)
            if item.data(Qt.UserRole) == device_name:
                if item.rowCount() > 0:
                    item.removeRows(0, item.rowCount())
                
                # Re-populate
                device = self.device_manager.get_device(device_name)
                if device and device.root_node:
                    for child in device.root_node.children:
                        self._add_node_recursive(item, child)
                break
        
    def _add_device_node(self, device):
        """Adds a device to the tree."""
        root = self.model.invisibleRootItem()
        
        name_item = QStandardItem(device.config.name)
        desc_item = QStandardItem(device.config.device_type.value)
        fc_item = QStandardItem("")
        type_item = QStandardItem("Device")
        
        # Store device name in data for easy retrieval
        name_item.setData(device.config.name, Qt.UserRole)
        
        root.appendRow([name_item, desc_item, fc_item, type_item])
        
        # Recursively add children if discovery happened
        if device.root_node:
            for child in device.root_node.children:
                self._add_node_recursive(name_item, child)

    def _add_node_recursive(self, parent_item: QStandardItem, node):
        """Recursively adds nodes to the tree."""
        # Col 0: Name
        item_name = QStandardItem(node.name)
        item_name.setEditable(False)
        item_name.setData(node, Qt.UserRole) # Store Node object
        
        # Col 1: Description
        item_desc = QStandardItem(node.description)
        item_desc.setEditable(False)
        
        # Col 2: FC (Functional Constraint) - Extract if available
        # Currently Node doesn't store FC directly, usually in description or we need to add field.
        # But description currently says "FC=XX Type=YY" for signals maybe?
        # Nodes are usually LD, LN, DO. DOs have signals.
        # Let's see if we can extract "FC" from description if formatted nicely.
        
        fc_text = ""
        type_text = ""
        
        # Heuristic: Parse description if it contains key-value pairs or just use description
        # If node has 'signals', it might be a DO. DOs don't have single FC, Signals (DA) do.
        # But wait, IEC 61850 structure: LD -> LN -> DO -> DA.
        # DA has FC.
        # The tree shows Nodes.
        # If the Node represents a DA (Signal), then it has FC.
        # But our current Node model separates Signals into a list `node.signals`.
        # So the tree shows DOs, but not DAs as children nodes?
        # Wait, if `node.signals` is populated, these are DAs.
        # Does the tree show signals as nodes?
        # Let's check `_add_node_recursive`. It iterates `node.children`.
        # Does `IEC61850Adapter` add Signals as children Nodes?
        # In `adapter.py` discover(): 
        #   It builds Nodes.
        #   It seems `Node` has `signals` list.
        #   If we want to see Signals in the tree, we should add them as children items too?
        #   User requested "FC TYPE SHOULD BE SHOWN". FC applies to Attributes (Signals).
        #   If tree assumes DO level, FC is mixed.
        #   However, maybe the user wants to see DAs in the tree?
        #   Currently DAs are in the "Live Data" table.
        #   If the user means "Show FC for DOs", DOs don't have FC.
        #   Unless the user sees "Signals" in tree?
        #   Let's check if the previous implementation added signals to tree.
        #   No, `_add_node_recursive` only iterates `node.children`.
        #   So the tree stops at DO level? or LN level?
        #   Let's check `scd_parser.py`.
        #   `get_structure`: IED -> LD -> LN -> DO.
        #   DO has `signals` appended.
        #   It does NOT add Signal as a child Node.
        #   So the Tree ends at DO.
        #   DO has a Type (DOType).
        
        #   So column "Type" can be DOType.
        #   Column "FC" is not applicable to DO, unless we show DAs.
        #   BUT, maybe the user WANTS to see DAs in the tree?
        #   "all the tree view column should be auto fit . also FC TYPE SGOULD BE SHOWN ."
        #   If I add DAs to the tree, it becomes very large.
        #   Maybe I should add DAs to the tree?
        
        #   Alternatively, maybe they mean the Type of the DO?
        
        #   Let's try to extract Type from description if possible, or add Type field to Node.
        #   SCDParser stores "Data Object" in description.
        
        if "FC=" in node.description:
             import re
             m_fc = re.search(r"FC=([A-Z]+)", node.description)
             if m_fc: fc_text = m_fc.group(1)
             
             m_type = re.search(r"Type=([A-Za-z0-9_]+)", node.description)
             if m_type: type_text = m_type.group(1)
        
        item_fc = QStandardItem(fc_text)
        item_fc.setEditable(False)
        
        item_type = QStandardItem(type_text)
        item_type.setEditable(False)

        parent_item.appendRow([item_name, item_desc, item_fc, item_type])
        
        # Add Children Nodes
        for child in node.children:
            self._add_node_recursive(item_name, child)
            
        # Add Signals as Leaf Nodes (so we can see them in tree too)
        for sig in node.signals:
             sig_name_item = QStandardItem(sig.name)
             sig_name_item.setEditable(False)
             sig_name_item.setData(sig, Qt.UserRole) # Store Signal object
             
             sig_desc_item = QStandardItem(sig.description)
             sig_desc_item.setEditable(False)
             
             # Extract FC/Type from description if parser put it there
             # Parser puts "FC=XX Type=YY" in description
             s_fc = ""
             s_type = ""
             if "FC=" in sig.description:
                 import re
                 m_fc = re.search(r"FC=([A-Z]+)", sig.description)
                 if m_fc: s_fc = m_fc.group(1)
                 m_type = re.search(r"Type=([A-Za-z0-9_]+)", sig.description)
                 if m_type: s_type = m_type.group(1)
             
             sig_fc_item = QStandardItem(s_fc)
             sig_fc_item.setEditable(False)
             
             sig_type_item = QStandardItem(s_type)
             sig_type_item.setEditable(False)
             
             item_name.appendRow([sig_name_item, sig_desc_item, sig_fc_item, sig_type_item])

    def _remove_device_node(self, device_name):
        """Removes a device from the tree."""
        root = self.model.invisibleRootItem()
        for row in range(root.rowCount()):
            item = root.child(row, 0)
            if item.data(Qt.UserRole) == device_name:
                root.removeRow(row)
                break

    def _on_context_menu(self, position):
        """Shows context menu for device nodes."""
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return
            
        # Check if we clicked on a Device Root Node
        # Device nodes have UserRole data set to their name
        item = self.model.itemFromIndex(index)
        # Note: Columns other than 0 might not have the data, navigate to col 0
        root_item = self.model.itemFromIndex(index.siblingAtColumn(0))
        device_name = root_item.data(Qt.UserRole)
        
        if device_name:
            menu = QMenu()
            edit_action = QAction("Edit Connection", self)
            edit_action.triggered.connect(lambda: self._edit_device(device_name))
            menu.addAction(edit_action)
            
            # Could add Connect/Disconnect here too
            
            menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def _edit_device(self, device_name):
        """Opens dialog to edit device."""
        device = self.device_manager.get_device(device_name)
        if not device:
            return
            
        dialog = ConnectionDialog(self)
        dialog.set_config(device.config)
        
        if dialog.exec():
            new_config = dialog.get_config()
            self.device_manager.update_device_config(new_config)
