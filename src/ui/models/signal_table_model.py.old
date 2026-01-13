from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QBrush
from typing import List, Dict, Optional
from src.models.device_models import Signal

class SignalTableModel(QAbstractTableModel):
    """
    Table Model for displaying a list of Signals.
    Optimized for frequent updates.
    """
    COLUMNS = ["Name", "Address", "Access", "Type", "Value", "Quality", "Timestamp", "Error", "Enum Options"]

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
            self._signals[row] = signal
            
            # Notify view that Type(3), Value(4), Quality(5), Timestamp(6), Error(7), Enum(8) changed
            top_left = self.index(row, 3)
            bottom_right = self.index(row, 8)
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
        if not index.isValid():
            return None

        signal = self._signals[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return signal.name
            elif col == 1: return signal.address
            elif col == 2: return getattr(signal, 'access', 'RO')
            elif col == 3: 
                if hasattr(signal, 'signal_type') and signal.signal_type:
                    return signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
                return "Unknown"
            elif col == 4: return str(signal.value) if signal.value is not None else "-"
            elif col == 5: return signal.quality.value if hasattr(signal.quality, 'value') else str(signal.quality)
            elif col == 6: 
                return signal.timestamp.strftime("%H:%M:%S.%f")[:-3] if signal.timestamp else "-"
            elif col == 7:
                # Error column
                return getattr(signal, 'error', '') or "-"
            elif col == 8:
                # Enum Options column - highlight current value
                if hasattr(signal, 'enum_map') and signal.enum_map:
                    # Sort by key (ordinal) and return comma-separated values
                    sorted_items = sorted(signal.enum_map.items())
                    
                    # Try to extract current ordinal value from signal.value
                    current_ord = None
                    if signal.value is not None:
                        # Value might be int, or "text (int)", or just text
                        if isinstance(signal.value, int):
                            current_ord = signal.value
                        elif isinstance(signal.value, str):
                            # Try to extract from "text (int)" format
                            import re
                            match = re.search(r'\((\d+)\)', signal.value)
                            if match:
                                current_ord = int(match.group(1))
                    
                    # Build display string with current value highlighted
                    parts = []
                    for ord_val, text_val in sorted_items:
                        if ord_val == current_ord:
                            parts.append(f"*{text_val} ({ord_val})*")  # Highlight current
                        else:
                            parts.append(f"{text_val} ({ord_val})")
                    
                    return ", ".join(parts)
                return "-"
        
        # Color coding based on quality
        if role == Qt.BackgroundRole and col == 5:  # Quality column
            if hasattr(signal, 'quality'):
                from src.models.device_models import SignalQuality
                if signal.quality == SignalQuality.INVALID:
                    return QBrush(QColor(255, 200, 200))  # Light red
                elif signal.quality == SignalQuality.NOT_CONNECTED:
                    return QBrush(QColor(220, 220, 220))  # Gray
        
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def _get_key(self, signal: Signal) -> str:
        """Generates a unique key for the signal (Address is usually unique per device)."""
        return signal.address
