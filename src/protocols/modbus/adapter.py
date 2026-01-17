"""
Modbus TCP Protocol Adapter
Supports reading and writing Modbus TCP devices
"""
import logging
import struct
from datetime import datetime
from typing import List, Optional, Any, Tuple
from enum import Enum

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import (
    DeviceConfig, Node, Signal, SignalType, SignalQuality,
    ModbusDataType, ModbusEndianness
)
from src.protocols.modbus.register_mapping import encode_mapped_value, decode_mapped_value, get_register_count

# Try to import pymodbus 3.x
try:
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException, ConnectionException
    HAS_PYMODBUS = True
except ImportError:
    HAS_PYMODBUS = False
    ModbusTcpClient = None
    ModbusException = Exception
    ConnectionException = Exception

logger = logging.getLogger(__name__)

MODBUS_EXCEPTIONS = {
    1: "Illegal Function",
    2: "Illegal Data Address",
    3: "Illegal Data Value",
    4: "Slave Device Failure",
    5: "Acknowledge",
    6: "Slave Device Busy",
    8: "Memory Parity Error",
    10: "Gateway Path Unavailable",
    11: "Gateway Target Device Failed to Respond"
}



class ModbusTCPAdapter(BaseProtocol):
    """
    Modbus TCP Protocol Implementation
    Supports all standard Modbus function codes
    """
    
    def __init__(self, config: DeviceConfig, event_logger=None):
        super().__init__(config)
        self.client = None
        self.connected = False
        self.event_logger = event_logger
        self.unit_id = config.modbus_unit_id
        self.timeout = config.modbus_timeout
        
        if not HAS_PYMODBUS:
            logger.error("pymodbus library not installed. Install with: pip install pymodbus")
            if event_logger:
                event_logger.error("Modbus", "pymodbus library not installed")
    
    def connect(self) -> bool:
        """Establish connection to Modbus TCP device"""
        if not HAS_PYMODBUS:
            logger.error("Cannot connect: pymodbus not available")
            return False
        
        if self.event_logger:
            self.event_logger.info(self.config.name, f"Connecting to {self.config.ip_address}:{self.config.port}")
        
        try:
            # Ensure clean state - disconnect any existing connection
            if self.client:
                self.disconnect()
            
            # Create client (pymodbus 3.x auto-connects on first request)
            self.client = ModbusTcpClient(
                host=self.config.ip_address,
                port=self.config.port,
                timeout=self.timeout
            )
            
            # Attempt connection
            if self.event_logger:
                self.event_logger.transaction(self.config.name, f"→ TCP Connect to {self.config.ip_address}:{self.config.port}")
            
            # In pymodbus 3.x, connect() returns None
            self.client.connect()
            
            if self.client.connected:
                # Test connection with a simple read
                test_result = self.client.read_holding_registers(0, count=1, device_id=self.unit_id)
                if test_result.isError():
                    # Connection OK but device returned error (might be normal)
                    if self.event_logger:
                        self.event_logger.warning(self.config.name, f"Connection OK but device returned error: {test_result}")
                else:
                    if self.event_logger:
                        self.event_logger.transaction(self.config.name, "← Connection SUCCESS")
                        self.event_logger.info(self.config.name, f"✓ Connected to Unit ID {self.unit_id}")
                    logger.info(f"Connected to Modbus device at {self.config.ip_address}")
                
                self.connected = True
                return True
            else:
                self.connected = False
                return False
                    
        except ConnectionException as e:
            if self.event_logger:
                self.event_logger.error(self.config.name, f"← Connection FAILED: {e}")
            logger.error(f"Failed to connect to Modbus device: {e}")
            self.connected = False
            return False
                
        except Exception as e:
            logger.error(f"Modbus connection error: {e}")
            if self.event_logger:
                self.event_logger.error(self.config.name, f"Connection exception: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close Modbus connection"""
        if self.client:
            try:
                self.client.close()
                if self.event_logger:
                    self.event_logger.info(self.config.name, "Disconnected")
            except Exception as e:
                logger.debug(f"Error closing modbus client: {e}")
            finally:
                self.client = None  # Ensure clean state for reconnection
        self.connected = False
        logger.info("Modbus disconnected")
    
    def discover(self) -> Node:
        """
        Discover Modbus device structure by scanning configured register maps
        """
        if self.event_logger:
            self.event_logger.info(self.config.name, "Starting Modbus device discovery")
        
        root = Node(
            name=self.config.name,
            description=f"Modbus TCP Unit {self.unit_id}"
        )
        
        # If register maps are configured, use them
        if self.config.modbus_register_maps:
            for reg_map in self.config.modbus_register_maps:
                node = self._create_node_from_map(reg_map)
                if node:
                    root.children.append(node)
        else:
            # Default discovery: scan common register ranges
            if self.event_logger:
                self.event_logger.info(self.config.name, "No register maps configured, using default scan")
            
            root.children.extend(self._default_discovery())
        
        if self.event_logger:
            total_signals = sum(len(child.signals) for child in root.children)
            self.event_logger.info(self.config.name, f"✓ Discovery complete: {len(root.children)} groups, {total_signals} signals")
        
        return root
    
    def _create_node_from_map(self, reg_map) -> Optional[Node]:
        """Create a node from a register map configuration"""
        func_names = {
            1: "Coils",
            2: "Discrete Inputs",
            3: "Holding Registers",
            4: "Input Registers"
        }
        
        node_name = reg_map.name_prefix or func_names.get(reg_map.function_code, "Registers")
        node = Node(
            name=node_name,
            description=reg_map.description or f"FC{reg_map.function_code}: {reg_map.start_address}-{reg_map.start_address + reg_map.count - 1}"
        )
        
        # Calculate register increment based on data type
        reg_size = self._get_register_size(reg_map.data_type)
        
        for i in range(0, reg_map.count, reg_size):
            addr = reg_map.start_address + i
            signal_name = f"{node_name}_{addr}"
            
            # Determine signal type
            if reg_map.function_code in [1, 2]:
                sig_type = SignalType.COIL if reg_map.function_code == 1 else SignalType.DISCRETE_INPUT
            else:
                sig_type = SignalType.HOLDING_REGISTER if reg_map.function_code == 3 else SignalType.INPUT_REGISTER
            
            # Determine access
            access = "RW" if reg_map.function_code in [1, 3] else "RO"
            
            signal = Signal(
                name=signal_name,
                address=f"{self.unit_id}:{reg_map.function_code}:{addr}",
                signal_type=sig_type,
                description=f"Modbus {func_names.get(reg_map.function_code)} @ {addr}",
                access=access,
                modbus_data_type=reg_map.data_type,
                modbus_scale=reg_map.scale,
                modbus_offset=reg_map.offset,
                modbus_endianness=reg_map.endianness,
                fc=str(reg_map.function_code)
            )
            
            node.signals.append(signal)
        
        return node
    
    def _default_discovery(self) -> List[Node]:
        """Perform default register scan when no maps configured"""
        nodes = []
        
        # Scan small ranges of each register type
        scan_configs = [
            (3, 0, 10, "Holding Registers 0-9", SignalType.HOLDING_REGISTER, "RW"),
            (4, 0, 10, "Input Registers 0-9", SignalType.INPUT_REGISTER, "RO"),
            (1, 0, 16, "Coils 0-15", SignalType.COIL, "RW"),
            (2, 0, 16, "Discrete Inputs 0-15", SignalType.DISCRETE_INPUT, "RO"),
        ]
        
        for func_code, start, count, desc, sig_type, access in scan_configs:
            node = Node(name=desc.split()[0] + " " + desc.split()[1], description=desc)
            
            for addr in range(start, start + count):
                signal = Signal(
                    name=f"{desc.split()[0]}_{addr}",
                    address=f"{self.unit_id}:{func_code}:{addr}",
                    signal_type=sig_type,
                    description=f"Modbus {desc.split()[0]} @ {addr}",
                    access=access,
                    modbus_data_type=ModbusDataType.UINT16
                )
                node.signals.append(signal)
            
            nodes.append(node)
        
        return nodes
    
    def poll(self) -> List[Signal]:
        """Poll all signals from this device's root node recursively"""
        if not self.connected or not self.client:
            return []
            
        updated_signals = []
        
        # We need a way to get all signals. 
        # One way is to store them or traverse the root node if it was discovered.
        # Let's assume the DeviceManager or AppController provides the signals to poll.
        # Or we traverse the config maps if we want to be protocol-driven.
        
        # If we have a discovered root_node, traverse it.
        # But wait, the adapter doesn't store the root_node, it just creates it in discover().
        # Let's add a list of all defined signals to the adapter for convenience.
        return updated_signals

    def read_signal(self, signal: Signal) -> Signal:
        """Read a single Modbus signal"""
        if not self.connected or not self.client:
            signal.quality = SignalQuality.NOT_CONNECTED
            self._emit_update(signal)
            return signal
        
        try:
            # Parse address: "unit:function:address"
            parts = signal.address.split(':')
            if len(parts) != 3:
                signal.quality = SignalQuality.INVALID
                signal.error = "Invalid address format"
                return signal
            
            unit_id = int(parts[0])
            func_code = int(parts[1])
            address = int(parts[2])
            
            # Determine read count based on data type
            count = self._get_register_size(signal.modbus_data_type or ModbusDataType.UINT16)
            
            if self.event_logger:
                self.event_logger.transaction(self.config.name, f"→ READ FC{func_code} Unit={unit_id} Addr={address} Count={count}")
            
            # Execute read based on function code
            result = None
            if func_code == 1:  # Read Coils
                result = self.client.read_coils(address, count=count, device_id=unit_id)
            elif func_code == 2:  # Read Discrete Inputs
                result = self.client.read_discrete_inputs(address, count=count, device_id=unit_id)
            elif func_code == 3:  # Read Holding Registers
                result = self.client.read_holding_registers(address, count=count, device_id=unit_id)
            elif func_code == 4:  # Read Input Registers
                result = self.client.read_input_registers(address, count=count, device_id=unit_id)
            else:
                signal.quality = SignalQuality.INVALID
                signal.error = f"Unsupported function code: {func_code}"
                self._emit_update(signal)
                return signal
            
            # Check for errors (pymodbus 3.x)
            # Check for errors (pymodbus 3.x)
            if result.isError():
                # Extract exception code
                exc_code = getattr(result, 'exception_code', None)
                exc_desc = MODBUS_EXCEPTIONS.get(exc_code, "Unknown Exception") if exc_code else str(result)
                
                signal.quality = SignalQuality.INVALID
                signal.error = f"Modbus Error: {exc_desc} (Code {exc_code})"
                
                if self.event_logger:
                    if exc_code == 1:
                        self.event_logger.warning(self.config.name, f"← Device returned 'Illegal Function' (FC{func_code}). This usually means the device does not support this register type. Please remove this range in 'Define Address Ranges'.")
                    else:
                        self.event_logger.error(self.config.name, f"← READ ERROR: {exc_desc} (Code {exc_code})")
                
                self._emit_update(signal)
                return signal
            
            # Parse value based on type
            new_value = None
            if func_code in [1, 2]:  # Coils/Discrete Inputs
                new_value = result.bits[0] if result.bits else False
            else:  # Registers
                raw_value = result.registers
                new_value = self._decode_registers(
                    raw_value,
                    signal.modbus_data_type or ModbusDataType.UINT16,
                    signal.modbus_endianness,
                    signal.modbus_scale,
                    signal.modbus_offset
                )
            
            # Update last_changed if value changed
            now = datetime.now()
            if signal.value != new_value:
                signal.value = new_value
                signal.last_changed = now
            
            signal.quality = SignalQuality.GOOD
            signal.timestamp = now
            signal.error = ""
            
            if self.event_logger:
                self.event_logger.transaction(self.config.name, f"← READ OK: {signal.value}")
            
            # Emit update for live data subscribers
            self._emit_update(signal)
            
            return signal
        
        except ConnectionException:
            signal.quality = SignalQuality.NOT_CONNECTED
            signal.error = "Connection lost"
            self.connected = False
            if self.event_logger:
                self.event_logger.error(self.config.name, "← Connection lost during read")
            self._emit_update(signal)
        except Exception as e:
            signal.quality = SignalQuality.INVALID
            signal.error = str(e)
            if self.event_logger:
                self.event_logger.error(self.config.name, f"← READ EXCEPTION: {e}")
            logger.error(f"Error reading Modbus signal {signal.address}: {e}")
            self._emit_update(signal)
        
        return signal
    
    def write_signal(self, signal: Signal, value: Any) -> bool:
        """Write value to a Modbus signal"""
        if not self.connected or not self.client:
            if self.event_logger:
                self.event_logger.error(self.config.name, "Cannot write: not connected")
            return False
        
        try:
            # Parse address
            parts = signal.address.split(':')
            if len(parts) != 3:
                return False
            
            unit_id = int(parts[0])
            func_code = int(parts[1])
            address = int(parts[2])
            
            if self.event_logger:
                self.event_logger.transaction(self.config.name, f"→ WRITE FC{func_code} Unit={unit_id} Addr={address} Value={value}")
            try:
                # FC 05: Write Single Coil, FC 06: Write Single Register, FC 15: Write Multiple Coils, FC 16: Write Multiple Registers
                if func_code == 1:  # Write Single Coil (mapped to internally as FC 05)
                    bool_value = bool(value)
                    result = self.client.write_coil(address, bool_value, device_id=unit_id)
                
                elif func_code == 3:  # Write Holding Register(s) (mapped to internally as FC 06 or 16)
                    # Encode value based on data type
                    registers = self._encode_value(
                        value,
                        signal.modbus_data_type or ModbusDataType.UINT16,
                        signal.modbus_endianness,
                        signal.modbus_scale,
                        signal.modbus_offset
                    )
                    
                    if len(registers) == 1:
                        result = self.client.write_register(address, registers[0], device_id=unit_id)
                    else:
                        result = self.client.write_registers(address, registers, device_id=unit_id)
                
                else:
                    if self.event_logger:
                        self.event_logger.error(self.config.name, f"Cannot write to FC{func_code} (read-only)")
                    signal.error = "Read-Only"
                    signal.quality = SignalQuality.INVALID
                    return False
            except Exception as e:
                err_msg = f"Write Exception: {e}"
                if self.event_logger:
                    self.event_logger.error("Modbus", f"← {err_msg}")
                logger.error(f"Error writing Modbus signal: {e}")
                signal.error = str(e)
                signal.quality = SignalQuality.INVALID
                return False
            
            if result and not result.isError():
                if self.event_logger:
                    self.event_logger.transaction(self.config.name, f"← WRITE SUCCESS")
                signal.error = ""
                signal.quality = SignalQuality.GOOD
                return True
            else:
                err_msg = f"Write Error: {result}"
                if self.event_logger:
                    self.event_logger.error(self.config.name, f"← {err_msg}")
                signal.error = str(result)
                signal.quality = SignalQuality.INVALID
                return False
        
        except Exception as e:
            if self.event_logger:
                self.event_logger.error(self.config.name, f"← WRITE EXCEPTION: {e}")
            logger.error(f"Error writing Modbus signal: {e}")
            signal.error = str(e)
            signal.quality = SignalQuality.INVALID
            return False
    
    def _get_register_size(self, data_type: ModbusDataType) -> int:
        """Get number of registers needed for data type"""
        return get_register_count(data_type)
    
    def _decode_registers(self, registers: List[int], data_type: ModbusDataType,
                         endianness: ModbusEndianness, scale: float, offset: float) -> Any:
        """Decode register values to native Python type using shared logic"""
        return decode_mapped_value(registers, data_type, endianness, scale, offset)
    
    def _encode_value(self, value: Any, data_type: ModbusDataType,
                     endianness: ModbusEndianness, scale: float, offset: float) -> List[int]:
        """Encode native Python value to Modbus register values using shared logic"""
        return encode_mapped_value(value, data_type, endianness, scale, offset)

    def select(self, signal: Signal) -> bool:
        """
        Modbus Direct Operate usually doesn't require Select.
        Return True to allow Operate to proceed.
        """
        return True

    def operate(self, signal: Signal, value: Any) -> bool:
        """
        Execute the control command.
        For Modbus, this maps to writing the signal.
        """
        return self.write_signal(signal, value)

    def cancel(self, signal: Signal) -> bool:
        """
        Cancel selection. No-op for Modbus.
        """
        return True    
    # Device Properties Retrieval Methods
    
    def get_device_info(self) -> dict:
        """Get comprehensive device information for properties dialog."""
        info = {
            "unit_id": self.unit_id,
            "timeout": self.timeout,
            "connected": self.connected,
            "register_maps_count": len(self.config.modbus_register_maps),
            "total_registers": 0,
            "function_codes_used": set()
        }
        
        # Calculate total registers and function codes
        for reg_map in self.config.modbus_register_maps:
            info["total_registers"] += reg_map.count
            info["function_codes_used"].add(reg_map.function_code)
        
        info["function_codes_used"] = list(info["function_codes_used"])
        
        return info
    
    def get_register_map_details(self) -> list:
        """Get detailed information about register mappings."""
        details = []
        
        for reg_map in self.config.modbus_register_maps:
            map_info = {
                "name": reg_map.name,
                "function_code": reg_map.function_code,
                "start_address": reg_map.start_address,
                "count": reg_map.count,
                "data_type": reg_map.data_type.value if hasattr(reg_map, 'data_type') else "Default",
                "endianness": reg_map.endianness.value if hasattr(reg_map, 'endianness') else "Big-endian",
                "scale": getattr(reg_map, 'scale', 1.0),
                "offset": getattr(reg_map, 'offset', 0.0),
                "description": getattr(reg_map, 'description', "")
            }
            details.append(map_info)
        
        return details
    
    def get_connection_stats(self) -> dict:
        """Get connection statistics."""
        stats = {
            "connected": self.connected,
            "ip_address": self.config.ip_address,
            "port": self.config.port,
            "unit_id": self.unit_id,
            "timeout": self.timeout,
            "pymodbus_available": HAS_PYMODBUS
        }
        
        return stats