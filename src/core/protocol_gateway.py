"""
Protocol Gateway
Bridges data between different SCADA protocols
Example: Read from IEC 61850 device and expose as Modbus slave
"""
import logging
from typing import Dict, List, Optional, Tuple
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
    Bridges protocols by listening to device updates and writing to Modbus slave.
    Event-driven architecture: Listens to DeviceManager.signal_updated.
    """
    
    mapping_updated = QtSignal(str)  # mapping_id
    error_occurred = QtSignal(str)   # error_message
    
    def __init__(self, device_manager, modbus_slave_server, event_logger=None):
        super().__init__()
        self.device_manager = device_manager
        self.modbus_slave = modbus_slave_server
        self.event_logger = event_logger
        
        self.mappings: Dict[str, GatewayMapping] = {}
        self.enabled = False
        
        # Cache for fast lookup: (source_device, source_signal) -> list[mapping_id]
        self._lookup_cache: Dict[Tuple[str, str], List[str]] = {}

    def add_mapping(self, mapping: GatewayMapping) -> str:
        """Add a new gateway mapping"""
        mapping_id = f"{mapping.source_device}::{mapping.source_signal_address}->MB:{mapping.dest_address}"
        self.mappings[mapping_id] = mapping
        
        # Update cache
        key = (mapping.source_device, mapping.source_signal_address)
        if key not in self._lookup_cache:
            self._lookup_cache[key] = []
        self._lookup_cache[key].append(mapping_id)
        
        if self.event_logger:
            self.event_logger.info("Gateway", f"Added mapping: {mapping_id}")
        
        return mapping_id
    
    def remove_mapping(self, mapping_id: str):
        """Remove a gateway mapping"""
        if mapping_id in self.mappings:
            mapping = self.mappings[mapping_id]
            
            # Remove from cache
            key = (mapping.source_device, mapping.source_signal_address)
            if key in self._lookup_cache:
                if mapping_id in self._lookup_cache[key]:
                    self._lookup_cache[key].remove(mapping_id)
                if not self._lookup_cache[key]:
                    del self._lookup_cache[key]

            del self.mappings[mapping_id]
            
            if self.event_logger:
                self.event_logger.info("Gateway", f"Removed mapping: {mapping_id}")
    
    def start(self):
        """Start gateway operation"""
        if not self.modbus_slave or not self.modbus_slave.running:
            logger.error("Cannot start gateway: Modbus slave not running")
            self.error_occurred.emit("Modbus slave server must be running")
            return False
        
        if not self.enabled:
            self.device_manager.signal_updated.connect(self._on_signal_updated)
            self.enabled = True
            
            if self.event_logger:
                self.event_logger.info("Gateway", f"Started with {len(self.mappings)} mappings")
        
        return True
    
    def stop(self):
        """Stop gateway operation"""
        if self.enabled:
            try:
                self.device_manager.signal_updated.disconnect(self._on_signal_updated)
            except Exception:
                pass
            self.enabled = False
        
        if self.event_logger:
            self.event_logger.info("Gateway", "Stopped")
            
    def _on_signal_updated(self, device_name: str, signal):
        """Handle signal update events from DeviceManager"""
        if not self.enabled:
            return
            
        key = (device_name, signal.address)
        ids = self._lookup_cache.get(key)
        
        if ids:
            for mapping_id in ids:
                mapping = self.mappings.get(mapping_id)
                if mapping and mapping.enabled:
                    self._process_mapping(mapping_id, mapping, signal.value)

    def _process_mapping(self, mapping_id: str, mapping: GatewayMapping, value):
        """Process a single mapping update"""
        try:
            if value is None:
                return

            # Convert to numeric if needed
            if isinstance(value, bool):
                value = 1 if value else 0
            elif isinstance(value, str):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    # logger.warning(f"Could not convert value '{value}' to float")
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
            
    # Polling methods removed as they are no longer needed
    
    def set_update_interval(self, interval_ms: int):
        """Legacy method for compatibility, no-op in event-driven mode"""
        pass
    
    def _find_signal(self, device, address: str):
        """Legacy helper"""
        pass

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
        except Exception as e:
            logger.debug(f"Error reading status for mapping {mapping.source_signal_address}: {e}")
        
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
