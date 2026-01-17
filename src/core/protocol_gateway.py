"""
Protocol Gateway
Bridges data between different SCADA protocols
Example: Read from IEC 61850 device and expose as Modbus slave
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal as QtSignal, QTimer

logger = logging.getLogger(__name__)


@dataclass
class GatewayMapping:
    """Maps a source signal to destination register"""
    source_device: str
    source_signal_address: str
    dest_register_type: str  # "holding", "input", "coils", "discrete"
    dest_address: int
    scale: float = 1.0
    offset: float = 0.0
    enabled: bool = True


class ProtocolGateway(QObject):
    """
    Bridges protocols by reading from one device and writing to Modbus slave
    """
    
    mapping_updated = QtSignal(str)  # mapping_id
    error_occurred = QtSignal(str)   # error_message
    
    def __init__(self, device_manager, modbus_slave_server, event_logger=None):
        super().__init__()
        self.device_manager = device_manager
        self.modbus_slave = modbus_slave_server
        self.event_logger = event_logger
        
        self.mappings: Dict[str, GatewayMapping] = {}
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_all_mappings)
        self.update_interval = 1000  # 1 second default
        
        self.enabled = False
    
    def add_mapping(self, mapping: GatewayMapping) -> str:
        """Add a new gateway mapping"""
        mapping_id = f"{mapping.source_device}::{mapping.source_signal_address}->MB:{mapping.dest_address}"
        self.mappings[mapping_id] = mapping
        
        if self.event_logger:
            self.event_logger.info("Gateway", f"Added mapping: {mapping_id}")
        
        return mapping_id
    
    def remove_mapping(self, mapping_id: str):
        """Remove a gateway mapping"""
        if mapping_id in self.mappings:
            del self.mappings[mapping_id]
            
            if self.event_logger:
                self.event_logger.info("Gateway", f"Removed mapping: {mapping_id}")
    
    def start(self):
        """Start gateway operation"""
        if not self.modbus_slave or not self.modbus_slave.running:
            logger.error("Cannot start gateway: Modbus slave not running")
            self.error_occurred.emit("Modbus slave server must be running")
            return False
        
        self.enabled = True
        self.update_timer.start(self.update_interval)
        
        if self.event_logger:
            self.event_logger.info("Gateway", f"Started with {len(self.mappings)} mappings")
        
        return True
    
    def stop(self):
        """Stop gateway operation"""
        self.enabled = False
        self.update_timer.stop()
        
        if self.event_logger:
            self.event_logger.info("Gateway", "Stopped")
    
    def set_update_interval(self, interval_ms: int):
        """Set update interval in milliseconds"""
        self.update_interval = max(100, interval_ms)
        
        if self.update_timer.isActive():
            self.update_timer.stop()
            self.update_timer.start(self.update_interval)
    
    def _update_all_mappings(self):
        """Update all enabled mappings"""
        for mapping_id, mapping in self.mappings.items():
            if mapping.enabled:
                self._update_single_mapping(mapping_id, mapping)
    
    def _update_single_mapping(self, mapping_id: str, mapping: GatewayMapping):
        """Update a single mapping"""
        try:
            # Get source device
            device = self.device_manager.get_device(mapping.source_device)
            if not device or not device.connected:
                return
            
            # Find signal in device tree
            signal = self._find_signal(device, mapping.source_signal_address)
            if not signal:
                return
            
            # Read current value
            updated_signal = self.device_manager.read_signal(mapping.source_device, signal)
            if not updated_signal or updated_signal.value is None:
                return
            
            # Apply transformation
            value = updated_signal.value
            
            # Convert to numeric if needed
            if isinstance(value, bool):
                value = 1 if value else 0
            elif isinstance(value, str):
                try:
                    value = float(value)
                except:
                    return
            
            # Apply scale and offset
            transformed_value = int((value * mapping.scale) + mapping.offset)
            
            # Write to Modbus slave
            if mapping.dest_register_type == "holding":
                self.modbus_slave.write_register(mapping.dest_address, transformed_value)
            elif mapping.dest_register_type == "input":
                self.modbus_slave.write_input_register(mapping.dest_address, transformed_value)
            elif mapping.dest_register_type == "coils":
                self.modbus_slave.write_coil(mapping.dest_address, bool(transformed_value))
            elif mapping.dest_register_type == "discrete":
                self.modbus_slave.write_discrete_input(mapping.dest_address, bool(transformed_value))
            
            self.mapping_updated.emit(mapping_id)
            
        except Exception as e:
            logger.debug(f"Gateway mapping error ({mapping_id}): {e}")
    
    def _find_signal(self, device, address: str):
        """Find signal by address in device tree"""
        if not device.root_node:
            return None
        
        return self._find_signal_recursive(device.root_node, address)
    
    def _find_signal_recursive(self, node, address: str):
        """Recursively search for signal"""
        # Check signals in current node
        for signal in node.signals:
            if signal.address == address:
                return signal
        
        # Check children
        for child in node.children:
            found = self._find_signal_recursive(child, address)
            if found:
                return found
        
        return None
    
    def get_mapping_status(self, mapping_id: str) -> Dict:
        """Get status of a specific mapping"""
        if mapping_id not in self.mappings:
            return {}
        
        mapping = self.mappings[mapping_id]
        
        status = {
            'mapping_id': mapping_id,
            'enabled': mapping.enabled,
            'source_device': mapping.source_device,
            'source_address': mapping.source_signal_address,
            'dest_address': mapping.dest_address,
            'dest_type': mapping.dest_register_type,
            'last_value': None,
            'last_update': None
        }
        
        # Try to get current value from Modbus slave
        try:
            if mapping.dest_register_type == "holding":
                status['last_value'] = self.modbus_slave.read_register(mapping.dest_address)
            elif mapping.dest_register_type == "coils":
                status['last_value'] = self.modbus_slave.read_coil(mapping.dest_address)
        except:
            pass
        
        return status
    
    def export_mappings(self, filepath: str):
        """Export mappings to CSV"""
        import csv
        
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'source_device', 'source_signal', 'dest_register_type',
                    'dest_address', 'scale', 'offset', 'enabled'
                ])
                
                for mapping in self.mappings.values():
                    writer.writerow([
                        mapping.source_device,
                        mapping.source_signal_address,
                        mapping.dest_register_type,
                        mapping.dest_address,
                        mapping.scale,
                        mapping.offset,
                        mapping.enabled
                    ])
            
            return True
        except Exception as e:
            logger.error(f"Export error: {e}")
            return False
    
    def import_mappings(self, filepath: str) -> int:
        """Import mappings from CSV"""
        import csv
        
        try:
            count = 0
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mapping = GatewayMapping(
                        source_device=row['source_device'],
                        source_signal_address=row['source_signal'],
                        dest_register_type=row['dest_register_type'],
                        dest_address=int(row['dest_address']),
                        scale=float(row.get('scale', 1.0)),
                        offset=float(row.get('offset', 0.0)),
                        enabled=row.get('enabled', 'True').lower() == 'true'
                    )
                    self.add_mapping(mapping)
                    count += 1
            
            return count
        except Exception as e:
            logger.error(f"Import error: {e}")
            return 0
