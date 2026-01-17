"""
Dialog for writing values to Modbus registers and coils
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                                QComboBox, QDialogButtonBox, QLabel, QSpinBox,
                                QDoubleSpinBox, QCheckBox, QGroupBox, QHBoxLayout,
                                QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from typing import Optional
from src.models.device_models import Signal, SignalType, ModbusDataType

class ModbusWriteDialog(QDialog):
    """
    Dialog for writing values to Modbus signals
    Supports all Modbus data types with proper validation
    """
    def __init__(self, signal: Signal, device_manager, device_name: str, parent=None):
        super().__init__(parent)
        self.signal = signal
        self.device_manager = device_manager
        self.device_name = device_name
        
        self.setWindowTitle(f"Write to {signal.name}")
        self.resize(450, 350)
        
        self._setup_ui()
        self._load_current_value()
    
    def _setup_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        
        # Signal info group
        info_group = QGroupBox("Signal Information")
        info_layout = QFormLayout(info_group)
        
        info_layout.addRow("Name:", QLabel(self.signal.name))
        info_layout.addRow("Address:", QLabel(self.signal.address))
        info_layout.addRow("Type:", QLabel(self.signal.signal_type.value if hasattr(self.signal.signal_type, 'value') else str(self.signal.signal_type)))
        
        # Current value
        current_val = str(self.signal.value) if self.signal.value is not None else "N/A"
        self.lbl_current = QLabel(current_val)
        self.lbl_current.setProperty("class", "status")
        self._set_label_status(self.lbl_current, "info")
        info_layout.addRow("Current Value:", self.lbl_current)
        
        layout.addWidget(info_group)
        
        # Value input group
        value_group = QGroupBox("New Value")
        value_layout = QVBoxLayout(value_group)
        
        # Determine input widget based on signal type
        self.value_widget = self._create_value_widget()
        value_layout.addWidget(self.value_widget)
        
        # Data type selector (for holding registers)
        if self.signal.signal_type in [SignalType.HOLDING_REGISTER, SignalType.INPUT_REGISTER]:
            data_type_layout = QFormLayout()
            
            self.data_type_combo = QComboBox()
            for dtype in ModbusDataType:
                self.data_type_combo.addItem(dtype.value, dtype)
            
            # Set current data type if specified
            if self.signal.modbus_data_type:
                idx = self.data_type_combo.findData(self.signal.modbus_data_type)
                if idx >= 0:
                    self.data_type_combo.setCurrentIndex(idx)
            
            self.data_type_combo.currentIndexChanged.connect(self._on_data_type_changed)
            data_type_layout.addRow("Data Type:", self.data_type_combo)
            
            value_layout.addLayout(data_type_layout)
        
        layout.addWidget(value_group)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.chk_verify = QCheckBox("Read back after write to verify")
        self.chk_verify.setChecked(True)
        options_layout.addWidget(self.chk_verify)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Refresh Current Value")
        self.btn_refresh.clicked.connect(self._load_current_value)
        button_layout.addWidget(self.btn_refresh)
        
        button_layout.addStretch()
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_write)
        self.buttons.rejected.connect(self.reject)
        button_layout.addWidget(self.buttons)
        
        layout.addLayout(button_layout)

    def _set_label_status(self, label: QLabel, status: Optional[str]):
        if status:
            label.setProperty("status", status)
        else:
            label.setProperty("status", "")
        label.style().unpolish(label)
        label.style().polish(label)
    
    def _create_value_widget(self):
        """Create appropriate input widget based on signal type"""
        if self.signal.signal_type in [SignalType.COIL, SignalType.DISCRETE_INPUT]:
            # Checkbox for boolean values
            widget = QCheckBox("Set to TRUE (ON)")
            if self.signal.value:
                widget.setChecked(True)
            return widget
        
        elif self.signal.signal_type in [SignalType.HOLDING_REGISTER, SignalType.INPUT_REGISTER]:
            # Determine widget based on data type
            data_type = self.signal.modbus_data_type or ModbusDataType.UINT16
            
            if data_type in [ModbusDataType.FLOAT32, ModbusDataType.FLOAT64]:
                widget = QDoubleSpinBox()
                widget.setRange(-1e9, 1e9)
                widget.setDecimals(6)
                if self.signal.value is not None:
                    try:
                        widget.setValue(float(self.signal.value))
                    except (ValueError, TypeError):
                        pass
            else:
                widget = QSpinBox()
                if data_type == ModbusDataType.UINT16:
                    widget.setRange(0, 65535)
                elif data_type == ModbusDataType.INT16:
                    widget.setRange(-32768, 32767)
                elif data_type == ModbusDataType.UINT32:
                    widget.setRange(0, 2**32 - 1)
                elif data_type == ModbusDataType.INT32:
                    widget.setRange(-2**31, 2**31 - 1)
                else:
                    widget.setRange(-2**31, 2**31 - 1)
                
                if self.signal.value is not None:
                    try:
                        widget.setValue(int(self.signal.value))
                    except (ValueError, TypeError):
                        pass
            
            return widget
        
        else:
            # Default to line edit
            widget = QLineEdit()
            if self.signal.value is not None:
                widget.setText(str(self.signal.value))
            return widget
    
    def _on_data_type_changed(self):
        """Recreate value widget when data type changes"""
        # Update signal data type temporarily
        old_value = self._get_value()
        self.signal.modbus_data_type = self.data_type_combo.currentData()
        
        # Recreate widget
        old_widget = self.value_widget
        self.value_widget = self._create_value_widget()
        
        # Replace in layout
        layout = old_widget.parent().layout()
        layout.replaceWidget(old_widget, self.value_widget)
        old_widget.deleteLater()
        
        # Try to preserve value
        try:
            self._set_value(old_value)
        except Exception as e:
            logger.debug(f"Failed to preserve value: {e}")
    
    def _get_value(self):
        """Get value from input widget"""
        if isinstance(self.value_widget, QCheckBox):
            return self.value_widget.isChecked()
        elif isinstance(self.value_widget, (QSpinBox, QDoubleSpinBox)):
            return self.value_widget.value()
        elif isinstance(self.value_widget, QLineEdit):
            return self.value_widget.text()
        return None
    
    def _set_value(self, value):
        """Set value in input widget"""
        if isinstance(self.value_widget, QCheckBox):
            self.value_widget.setChecked(bool(value))
        elif isinstance(self.value_widget, (QSpinBox, QDoubleSpinBox)):
            self.value_widget.setValue(float(value) if isinstance(self.value_widget, QDoubleSpinBox) else int(value))
        elif isinstance(self.value_widget, QLineEdit):
            self.value_widget.setText(str(value))
    
    def _load_current_value(self):
        """Read current value from device"""
        try:
            updated_signal = self.device_manager.read_signal(self.device_name, self.signal)
            if updated_signal and updated_signal.value is not None:
                self.signal = updated_signal
                self.lbl_current.setText(str(updated_signal.value))
                self._set_value(updated_signal.value)
        except Exception as e:
            QMessageBox.warning(self, "Read Error", f"Failed to read current value:\n{e}")
    
    def _on_write(self):
        """Execute write operation"""
        value = self._get_value()
        
        # Confirm write
        reply = QMessageBox.question(
            self,
            "Confirm Write",
            f"Write value '{value}' to {self.signal.name}?\n\n"
            f"Address: {self.signal.address}\n"
            f"Current: {self.signal.value}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Get protocol adapter
        protocol = self.device_manager.get_protocol(self.device_name)
        if not protocol:
            QMessageBox.critical(self, "Error", "Device not connected")
            return
        
        # Execute write
        try:
            success = protocol.write_signal(self.signal, value)
            
            if success:
                # Verify if requested
                if self.chk_verify.isChecked():
                    import time
                    time.sleep(0.1)  # Small delay
                    self._load_current_value()
                    
                    # Check if value matches
                    if str(self.signal.value) != str(value):
                        QMessageBox.warning(
                            self,
                            "Verification Failed",
                            f"Write succeeded but verification failed!\n\n"
                            f"Expected: {value}\n"
                            f"Read back: {self.signal.value}"
                        )
                    else:
                        QMessageBox.information(self, "Success", f"Write successful and verified!\n\nNew value: {self.signal.value}")
                else:
                    QMessageBox.information(self, "Success", "Write command sent successfully")
                
                self.accept()
            else:
                QMessageBox.critical(self, "Write Failed", "Device returned error for write operation")
        
        except Exception as e:
            QMessageBox.critical(self, "Write Error", f"Failed to write value:\n{e}")
