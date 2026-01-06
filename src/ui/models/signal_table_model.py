from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from typing import List, Dict, Optional
from src.models.device_models import Signal

class SignalTableModel(QAbstractTableModel):
    """
    Table Model for displaying a list of Signals.
    Optimized for frequent updates.
    """
    COLUMNS = ["Name", "Address", "Type", "Value", "Quality", "Timestamp"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signals: List[Signal] = []
        self._signal_map: Dict[str, int] = {} # Map signal unique ID to row index

    def set_node_filter(self, node):
        """Sets the current node to display signals for."""
        self.beginResetModel()
        self._signals = []
        if node:
            self._collect_signals_recursive(node)
        
        # Rebuild map
        self._signal_map = {self._get_key(s): i for i, s in enumerate(self._signals)}
        self.endResetModel()

    def _collect_signals_recursive(self, node):
        if hasattr(node, "signals"):
             self._signals.extend(node.signals)
        
        if hasattr(node, "children"):
            for child in node.children:
                self._collect_signals_recursive(child)
        # If node is a Device object, it has root_node
        if hasattr(node, "root_node") and node.root_node:
             self._collect_signals_recursive(node.root_node)

    def set_signals(self, signals: List[Signal]):
        """Legacy: Resets the model with a new list of signals."""
        self.beginResetModel()
        self._signals = signals
        self._signal_map = {self._get_key(s): i for i, s in enumerate(signals)}
        self.endResetModel()

    def update_signal(self, signal: Signal):
        """Updates a single signal's data."""
        key = self._get_key(signal)
        row = self._signal_map.get(key)
        
        if row is not None:
            # Update the stored object
            # Note: In a real app we might want to copy values to avoid threading issues,
            # but since Signal is a dataclass and we are replacing fields, it's mostly fine for this scale.
            self._signals[row] = signal
            
            # Notify view that Value(3), Quality(4), Timestamp(5) changed
            top_left = self.index(row, 3)
            bottom_right = self.index(row, 5)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])

    def get_signal_at_row(self, row: int) -> Optional[Signal]:
        if 0 <= row < len(self._signals):
            return self._signals[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._signals)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        signal = self._signals[index.row()]
        col = index.column()

        if col == 0: return signal.name
        elif col == 1: return signal.address
        elif col == 2: 
            if hasattr(signal, 'signal_type') and signal.signal_type:
                return signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
            return "Unknown"
        elif col == 3: return str(signal.value) if signal.value is not None else "-"
        elif col == 4: return signal.quality.value if hasattr(signal.quality, 'value') else str(signal.quality)
        elif col == 5: 
            return signal.timestamp.strftime("%H:%M:%S.%f")[:-3] if signal.timestamp else "-"
        
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def _get_key(self, signal: Signal) -> str:
        """Generates a unique key for the signal (Address is usually unique per device)."""
        # Ideally should include Device Name too if this table shows multiple devices.
        # For now, assuming address is unique enough for the demo scope.
        return signal.address
