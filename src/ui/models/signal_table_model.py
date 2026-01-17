from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QBrush
from typing import List, Dict, Optional, Any
from src.models.device_models import Signal
import logging
import datetime

logger = logging.getLogger(__name__)

class SignalTableModel(QAbstractTableModel):
    """
    Table Model for displaying a list of Signals.
    Optimized for frequent updates.
    """
    COLUMNS = [
        "Name", "Address", "Access", "Type", 
        "Modbus Type", "Endianness", "Scale", "Offset",
        "Value", "Quality", "Timestamp", "Last Changed", "Error", "RTT (ms)"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signals: List[Signal] = []
        self._signal_map: Dict[str, int] = {} # Map signal unique ID to row index
        self._updates_suspended = False

    def suspend_updates(self, suspend: bool):
        """
        If True, signals are updated in background but Views are NOT notified (prevents event flood).
        If False, immediately triggers a full view refresh.
        """
        self._updates_suspended = suspend
        if not suspend:
            # Replaced bulk reset to layoutChanged to keep selection if possible, 
            # but for bulk updates reset is safer/cleaner visually?
            # dataChanged for all range is better.
            if self._signals:
                tl = self.index(0, 0)
                br = self.index(len(self._signals)-1, 13)
                self.dataChanged.emit(tl, br, [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])
            # self.layoutChanged.emit()

    def set_node_filter(self, node):
        """Sets the current node to display signals for."""
        self.beginResetModel()
        self._signals = []
        if node:
            self._collect_signals_recursive(node)
        
        # Rebuild map
        self._signal_map = {self._get_key(s): i for i, s in enumerate(self._signals)}
        logger.info(f"SignalTableModel: Reset filter. Collected {len(self._signals)} signals.")
        self.endResetModel()

    def _collect_signals_recursive(self, node):
        # 1. If it's a Signal object (identify by existence of unique address)
        if hasattr(node, 'address') and not hasattr(node, 'signals'):
            self._signals.append(node)
            return

        # 2. If it's a Node object (identify by signals or children)
        if hasattr(node, "signals") and node.signals:
             self._signals.extend(node.signals)
        
        if hasattr(node, "children") and node.children:
            for child in node.children:
                self._collect_signals_recursive(child)
        
        # 3. If it's a Device object (identify by root_node)
        if hasattr(node, "root_node") and node.root_node:
             self._collect_signals_recursive(node.root_node)
        elif hasattr(node, "config") and hasattr(node.config, "name"):
             pass

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
            
            # Optimization: If suspended, DO NOT emit dataChanged
            if not self._updates_suspended:
                # Notify view that the entire row might have changed for safety
                top_left = self.index(row, 0)
                bottom_right = self.index(row, 13)
                self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])

    def get_signals(self) -> List[Signal]:
        """Returns the current list of signals in the model."""
        return self._signals

    def get_signal_at_row(self, row: int) -> Optional[Signal]:
        if 0 <= row < len(self._signals):
            return self._signals[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._signals)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
            
        base_flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        # Editable: Name(0), Modbus Type(4), Endianness(5), Scale(6), Offset(7), Value(8)
        if index.column() in [0, 4, 5, 6, 7, 8]:
             return base_flags | Qt.ItemIsEditable
             
        return base_flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
            
        row = index.row()
        col = index.column()
        signal = self._signals[row]
        
        try:
            from src.models.device_models import ModbusDataType, ModbusEndianness
            if col == 0: # Name
                signal.name = str(value)
            elif col == 4: # Modbus Type
                for d in ModbusDataType:
                    if d.value == value or d.name == value:
                        signal.modbus_data_type = d
                        break
            elif col == 5: # Endianness
                for e in ModbusEndianness:
                    if e.value == value or e.name == value:
                        signal.modbus_endianness = e
                        break
            elif col == 6: # Scale
                signal.modbus_scale = float(value)
            elif col == 7: # Offset
                signal.modbus_offset = float(value)
            elif col == 8: # Value (Trigger Write)
                # Parse based on type
                if signal.modbus_data_type in [ModbusDataType.BOOL, ModbusDataType.BIT]:
                    parsed_val = value.lower() in ['true', '1', 't', 'y', 'yes', 'on']
                elif signal.modbus_data_type in [ModbusDataType.HEX16, ModbusDataType.BINARY16]:
                    parsed_val = int(value, 0)
                else:
                    parsed_val = float(value) if '.' in value else int(value)
                
                signal.value = parsed_val
            
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            return True
        except:
            return False

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
            elif col == 4: return signal.modbus_data_type.value if signal.modbus_data_type else "-"
            elif col == 5: return signal.modbus_endianness.value if signal.modbus_endianness else "-"
            elif col == 6: return str(signal.modbus_scale)
            elif col == 7: return str(signal.modbus_offset)
            elif col == 8: return str(signal.value) if signal.value is not None else "-"
            elif col == 9: return signal.quality.value if hasattr(signal.quality, 'value') else str(signal.quality)
            elif col == 10: 
                if signal.timestamp:
                    try:
                        ts = signal.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        if getattr(signal.timestamp, 'tzinfo', None) is not None and signal.timestamp.tzinfo == datetime.timezone.utc:
                            ts += ' UTC'
                        return ts
                    except Exception:
                        return str(signal.timestamp)
                return "-"
            elif col == 11:
                # Last Changed column
                if signal.last_changed:
                    try:
                        lc = signal.last_changed.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        if getattr(signal.last_changed, 'tzinfo', None) is not None and signal.last_changed.tzinfo == datetime.timezone.utc:
                            lc += ' UTC'
                        return lc
                    except Exception:
                        return str(signal.last_changed)
                return "-"
            elif col == 12: return signal.error or "-"
            elif col == 13: 
                # RTT Column
                if hasattr(signal, 'rtt_state'):
                    from src.models.device_models import RTTState
                    if signal.rtt_state == RTTState.RECEIVED:
                        return f"{signal.last_rtt:.1f}"
                    elif signal.rtt_state == RTTState.SENT:
                        return "Pending..."
                    elif signal.rtt_state == RTTState.TIMEOUT:
                        return "Timeout"
                return "N/A"
            return None
        
        # Color coding based on quality
        if role == Qt.BackgroundRole and col == 9:  # Quality column
            if hasattr(signal, 'quality'):
                from src.models.device_models import SignalQuality
                if signal.quality == SignalQuality.INVALID:
                    return QBrush(QColor(255, 200, 200))  # Light red
                elif signal.quality == SignalQuality.NOT_CONNECTED:
                    return QBrush(QColor(220, 220, 220))  # Gray

        if role == Qt.ForegroundRole and col == 12: # Error column
            if signal.error:
                return QBrush(QColor(255, 0, 0)) # Red text
        
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def _get_key(self, signal: Signal) -> str:
        """Generates a unique key for the signal (Address is usually unique per device)."""
        return signal.address

    def clear_signals(self):
        """Clear all signals from the model."""
        self.beginResetModel()
        self._signals = []
        self._signal_map = {}
        self.endResetModel()

    def add_signals(self, signals: List[Signal]):
        """Append signals to the model, avoiding duplicates.

        Emits the appropriate rowsInserted signals for views.
        """
        if not signals:
            return

        # Filter out duplicates based on key
        new_signals = []
        for s in signals:
            key = self._get_key(s)
            if key not in self._signal_map:
                new_signals.append(s)

        if not new_signals:
            return

        start_row = len(self._signals)
        end_row = start_row + len(new_signals) - 1
        self.beginInsertRows(QModelIndex(), start_row, end_row)
        for s in new_signals:
            self._signals.append(s)
        # Rebuild map incrementally
        for i in range(start_row, len(self._signals)):
            self._signal_map[self._get_key(self._signals[i])] = i
        self.endInsertRows()
