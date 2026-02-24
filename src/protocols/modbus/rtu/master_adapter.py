"""
Modbus RTU Master Adapter
Implements Modbus RTU master role for communicating with slave devices
"""
import logging
import time
from typing import List, Optional, Union
from datetime import datetime

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import (
    DeviceConfig, Node, Signal, SignalType, SignalQuality,
    ModbusDataType, ModbusEndianness
)

from src.protocols.modbus.register_mapping import get_register_count, decode_mapped_value
from .transport import SerialTransport, RTUoverTCPTransport, SerialConfig
from .frame_handler import (
    ModbusRTUFrameHandler, ModbusFunctionCode, ModbusExceptionCode
)
from .timing import ModbusRTUTiming

logger = logging.getLogger(__name__)

EXCEPTION_NAMES = {
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


class ModbusRTUMasterAdapter(BaseProtocol):
    """
    Modbus RTU Master Protocol Implementation
    
    Connects to Modbus RTU slave devices via:
    - RS-485 serial port
    - USB-to-RS-485 adapter
    - RTU-over-TCP
    
    Supports all standard function codes with proper CRC validation and timing
    """
    
    def __init__(self, config: DeviceConfig, event_logger=None):
        super().__init__(config)
        self.event_logger = event_logger
        self.connected = False
        
        # Transport and protocol components
        self.transport: Optional[Union[SerialTransport, RTUoverTCPTransport]] = None
        self.frame_handler = ModbusRTUFrameHandler()
        self.timing: Optional[ModbusRTUTiming] = None
        
        # Configuration
        self.slave_address = config.rtu_slave_address
        self.max_retries = 3
        self.response_timeout = 1.0
        
        # Statistics
        self.transaction_count = 0
        self.error_count = 0
        
        logger.info(f"ModbusRTU Master initialized for slave {self.slave_address}")
    
    def connect(self) -> bool:
        """Establish connection to RTU slave device"""
        if self.event_logger:
            self.event_logger.info(self.config.name, "Connecting to Modbus RTU device")
        
        try:
            # Create transport based on configuration
            if self.config.rtu_transport == "serial":
                # Serial RS-485 transport
                serial_config = SerialConfig(
                    port=self.config.serial_port,
                    baudrate=self.config.serial_baudrate,
                    bytesize=self.config.serial_bytesize,
                    parity=self.config.serial_parity,
                    stopbits=self.config.serial_stopbits,
                    timeout=self.config.serial_timeout
                )
                
                self.transport = SerialTransport(serial_config)
                self.timing = ModbusRTUTiming(
                    baudrate=serial_config.baudrate,
                    bytesize=serial_config.bytesize,
                    parity=serial_config.parity,
                    stopbits=serial_config.stopbits
                )
                
                if self.event_logger:
                    self.event_logger.transaction(
                        self.config.name,
                        f"→ Opening {serial_config.port} at {serial_config.baudrate} baud"
                    )
                
            elif self.config.rtu_transport == "rtu_over_tcp":
                # RTU-over-TCP transport
                self.transport = RTUoverTCPTransport(
                    host=self.config.ip_address,
                    port=self.config.port,
                    timeout=self.config.serial_timeout
                )
                # Use default timing for typical baud rate
                self.timing = ModbusRTUTiming(baudrate=9600)
                
                if self.event_logger:
                    self.event_logger.transaction(
                        self.config.name,
                        f"→ Connecting to {self.config.ip_address}:{self.config.port}"
                    )
            
            else:
                raise ValueError(f"Unknown transport type: {self.config.rtu_transport}")
            
            # Open transport
            if not self.transport.open():
                if self.event_logger:
                    self.event_logger.error(self.config.name, "Failed to open transport")
                return False
            
            # Test connection with a simple read
            test_signal = Signal(
                name="test",
                address=f"{self.slave_address}:3:0",
                signal_type=SignalType.HOLDING_REGISTER
            )
            
            try:
                self.read_signal(test_signal)
                # If we got here without exception, connection is good
                self.connected = True
                if self.event_logger:
                    self.event_logger.info(
                        self.config.name,
                        f"✓ Connected to slave {self.slave_address}"
                    )
                return True
                
            except Exception as e:
                logger.warning(f"Connection test failed: {e}")
                # Connection might still be valid, slave might not have register 0
                self.connected = True
                if self.event_logger:
                    self.event_logger.warning(
                        self.config.name,
                        f"Connected but test read failed: {e}"
                    )
                return True
        
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            if self.event_logger:
                self.event_logger.error(self.config.name, f"Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close connection to RTU slave"""
        if self.transport:
            self.transport.close()
            self.transport = None
        
        self.connected = False
        
        if self.event_logger:
            self.event_logger.info(self.config.name, "Disconnected")
        
        logger.info("Modbus RTU disconnected")
    
    def discover(self) -> Node:
        """
        Discover device structure by scanning configured register maps
        """
        if self.event_logger:
            self.event_logger.info(self.config.name, "Starting RTU device discovery")
        
        root = Node(
            name=self.config.name,
            description=f"Modbus RTU Slave {self.slave_address}"
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
                self.event_logger.info(
                    self.config.name,
                    "No register maps configured, using default scan"
                )
            
            root.children.extend(self._default_discovery())
        
        if self.event_logger:
            total_signals = sum(len(child.signals) for child in root.children)
            self.event_logger.info(
                self.config.name,
                f"✓ Discovery complete: {len(root.children)} groups, {total_signals} signals"
            )
        
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
        
        # Create signals for each register
        for i in range(reg_map.count):
            addr = reg_map.start_address + i
            signal_name = f"{node_name}_{addr}"
            
            # Determine signal type
            if reg_map.function_code == 1:
                sig_type = SignalType.COIL
            elif reg_map.function_code == 2:
                sig_type = SignalType.DISCRETE_INPUT
            elif reg_map.function_code == 3:
                sig_type = SignalType.HOLDING_REGISTER
            else:  # 4
                sig_type = SignalType.INPUT_REGISTER
            
            # Determine access
            access = "RW" if reg_map.function_code in [1, 3] else "RO"
            
            signal = Signal(
                name=signal_name,
                address=f"{self.slave_address}:{reg_map.function_code}:{addr}",
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
            node = Node(name=f"{desc.split()[0]} {desc.split()[1]}", description=desc)
            
            for addr in range(start, start + count):
                signal = Signal(
                    name=f"{desc.split()[0]}_{addr}",
                    address=f"{self.slave_address}:{func_code}:{addr}",
                    signal_type=sig_type,
                    description=f"Modbus {desc.split()[0]} @ {addr}",
                    access=access,
                    modbus_data_type=ModbusDataType.UINT16,
                    fc=str(func_code)
                )
                node.signals.append(signal)
            
            nodes.append(node)
        
        return nodes
    
    def read_signal(self, signal: Signal) -> Signal:
        """Read a specific signal synchronously.
        
        Reads the correct number of registers for the signal's data type
        (e.g. 2 registers for FLOAT32/INT32, 4 for INT64) and decodes them
        using the configured endianness, scale, and offset.
        """
        if not self.connected or not self.transport:
            signal.quality = SignalQuality.NOT_CONNECTED
            signal.error = "Not connected"
            self._emit_update(signal)
            return signal
        
        try:
            # Parse address: "slave:function:address"
            parts = signal.address.split(':')
            if len(parts) != 3:
                raise ValueError(f"Invalid address format: {signal.address}")
            
            slave_addr = int(parts[0])
            func_code = int(parts[1])
            reg_addr = int(parts[2])
            
            # Determine how many registers this data type requires
            data_type = signal.modbus_data_type or ModbusDataType.UINT16
            count = get_register_count(data_type)
            
            if self.event_logger:
                self.event_logger.transaction(
                    self.config.name,
                    f"→ READ FC{func_code} Slave={slave_addr} Addr={reg_addr} Count={count} Type={data_type.value}"
                )

            raw_values = None

            if func_code == 1:  # Read Coils (bit, always 1)
                values = self.read_coils(slave_addr, reg_addr, count)
                if values is not None:
                    signal.value = values[0]
                    signal.quality = SignalQuality.GOOD
                    signal.timestamp = datetime.now()
                    signal.error = ""
                    self._emit_update(signal)
                    return signal

            elif func_code == 2:  # Read Discrete Inputs (bit, always 1)
                values = self.read_discrete_inputs(slave_addr, reg_addr, count)
                if values is not None:
                    signal.value = values[0]
                    signal.quality = SignalQuality.GOOD
                    signal.timestamp = datetime.now()
                    signal.error = ""
                    self._emit_update(signal)
                    return signal

            elif func_code == 3:  # Read Holding Registers
                raw_values = self.read_holding_registers(slave_addr, reg_addr, count)

            elif func_code == 4:  # Read Input Registers
                raw_values = self.read_input_registers(slave_addr, reg_addr, count)

            else:
                raise ValueError(f"Unsupported function code: {func_code}")

            # Decode the raw register words into a typed value
            if raw_values is not None:
                decoded = decode_mapped_value(
                    raw_values,
                    data_type,
                    signal.modbus_endianness,
                    signal.modbus_scale  if signal.modbus_scale  is not None else 1.0,
                    signal.modbus_offset if signal.modbus_offset is not None else 0.0
                )
                # Track last_changed
                if signal.value != decoded:
                    signal.last_changed = datetime.now()
                signal.value = decoded
                signal.quality = SignalQuality.GOOD
            else:
                signal.quality = SignalQuality.INVALID
                signal.error = "No response from device"

            signal.timestamp = datetime.now()
            if signal.quality == SignalQuality.GOOD:
                signal.error = ""
        
        except Exception as e:
            logger.error(f"Error reading signal {signal.address}: {e}")
            signal.quality = SignalQuality.INVALID
            signal.error = str(e)
        
        # Notify subscribers (WatchList, UI)
        self._emit_update(signal)
        return signal
    
    # ========================================================================
    # Modbus RTU Function Code Implementations
    # ========================================================================
    
    def read_coils(self, slave_address: int, start_address: int, count: int) -> Optional[List[bool]]:
        """FC01: Read Coils"""
        request = self.frame_handler.build_read_coils_request(slave_address, start_address, count)
        response_frame = self._execute_request(request)
        
        if response_frame and not response_frame.is_exception:
            coils = self.frame_handler.parse_read_coils_response(response_frame)
            return coils[:count] if coils else None
        return None
    
    def read_discrete_inputs(self, slave_address: int, start_address: int, 
                            count: int) -> Optional[List[bool]]:
        """FC02: Read Discrete Inputs"""
        request = self.frame_handler.build_read_discrete_inputs_request(
            slave_address, start_address, count
        )
        response_frame = self._execute_request(request)
        
        if response_frame and not response_frame.is_exception:
            inputs = self.frame_handler.parse_read_coils_response(response_frame)
            return inputs[:count] if inputs else None
        return None
    
    def read_holding_registers(self, slave_address: int, start_address: int,
                               count: int) -> Optional[List[int]]:
        """FC03: Read Holding Registers"""
        request = self.frame_handler.build_read_holding_registers_request(
            slave_address, start_address, count
        )
        response_frame = self._execute_request(request)
        
        if response_frame and not response_frame.is_exception:
            return self.frame_handler.parse_read_registers_response(response_frame)
        return None
    
    def read_input_registers(self, slave_address: int, start_address: int,
                            count: int) -> Optional[List[int]]:
        """FC04: Read Input Registers"""
        request = self.frame_handler.build_read_input_registers_request(
            slave_address, start_address, count
        )
        response_frame = self._execute_request(request)
        
        if response_frame and not response_frame.is_exception:
            return self.frame_handler.parse_read_registers_response(response_frame)
        return None
    
    def write_single_coil(self, slave_address: int, address: int, value: bool) -> bool:
        """FC05: Write Single Coil"""
        request = self.frame_handler.build_write_single_coil_request(
            slave_address, address, value
        )
        response_frame = self._execute_request(request)
        
        return response_frame is not None and not response_frame.is_exception
    
    def write_single_register(self, slave_address: int, address: int, value: int) -> bool:
        """FC06: Write Single Register"""
        request = self.frame_handler.build_write_single_register_request(
            slave_address, address, value
        )
        response_frame = self._execute_request(request)
        
        return response_frame is not None and not response_frame.is_exception
    
    def write_multiple_coils(self, slave_address: int, start_address: int,
                            values: List[bool]) -> bool:
        """FC15: Write Multiple Coils"""
        request = self.frame_handler.build_write_multiple_coils_request(
            slave_address, start_address, values
        )
        response_frame = self._execute_request(request)
        
        return response_frame is not None and not response_frame.is_exception
    
    def write_multiple_registers(self, slave_address: int, start_address: int,
                                 values: List[int]) -> bool:
        """FC16: Write Multiple Registers"""
        request = self.frame_handler.build_write_multiple_registers_request(
            slave_address, start_address, values
        )
        response_frame = self._execute_request(request)
        
        return response_frame is not None and not response_frame.is_exception
    
    # ========================================================================
    # Request/Response Handling
    # ========================================================================
    
    def _execute_request(self, request: bytes, retries: Optional[int] = None):
        """
        Execute a Modbus request with retry logic
        Returns parsed response frame or None
        """
        if retries is None:
            retries = self.max_retries
        
        if self.transport is None:
            logger.error("Transport not initialized")
            return None
        
        for attempt in range(retries + 1):
            try:
                # Send request
                if not self.transport.send_frame(request):
                    logger.warning(f"Failed to send request (attempt {attempt + 1})")
                    continue
                
                self.transaction_count += 1
                
                if self.event_logger:
                    self.event_logger.transaction(
                        self.config.name,
                        f"→ TX: {request.hex()}"
                    )
                
                # Wait inter-frame gap before expecting response
                if self.timing:
                    time.sleep(self.timing.inter_frame_gap)
                
                # Receive response
                response_bytes = self.transport.receive_frame(timeout=self.response_timeout)
                
                if not response_bytes:
                    logger.warning(f"No response received (attempt {attempt + 1})")
                    if self.event_logger:
                        self.event_logger.warning(
                            self.config.name,
                            f"← Timeout (attempt {attempt + 1})"
                        )
                    continue
                
                if self.event_logger:
                    self.event_logger.transaction(
                        self.config.name,
                        f"← RX: {response_bytes.hex()}"
                    )
                
                # Parse response
                response_frame = self.frame_handler.parse_frame(response_bytes)
                
                if not response_frame:
                    logger.error("Failed to parse response (CRC error)")
                    self.error_count += 1
                    if self.event_logger:
                        self.event_logger.error(
                            self.config.name,
                            "CRC validation failed"
                        )
                    continue
                
                # Check for exception response
                if response_frame.is_exception:
                    exception_code = response_frame.exception_code if response_frame.exception_code is not None else 0
                    exception_name = EXCEPTION_NAMES.get(
                        exception_code,
                        "Unknown Exception"
                    )
                    logger.error(f"Modbus exception: {exception_name}")
                    self.error_count += 1
                    if self.event_logger:
                        self.event_logger.error(
                            self.config.name,
                            f"Exception {response_frame.exception_code:02X}: {exception_name}"
                        )
                    return response_frame  # Return exception frame
                
                # Success
                return response_frame
            
            except Exception as e:
                logger.error(f"Request execution error: {e}")
                self.error_count += 1
                if self.event_logger:
                    self.event_logger.error(self.config.name, f"Error: {e}")
        
        # All retries exhausted
        logger.error(f"Request failed after {retries + 1} attempts")
        return None
    
    def send_command(self, signal: Signal, value, params: Optional[dict] = None) -> bool:
        """High-level command interface for writing signals"""
        if params is None:
            params = {}
        try:
            # Parse address
            parts = signal.address.split(':')
            if len(parts) != 3:
                raise ValueError(f"Invalid address format: {signal.address}")
            
            slave_addr = int(parts[0])
            func_code = int(parts[1])
            reg_addr = int(parts[2])
            
            # Write based on function code/signal type
            if func_code == 1 or signal.signal_type == SignalType.COIL:
                return self.write_single_coil(slave_addr, reg_addr, bool(value))
            
            elif func_code == 3 or signal.signal_type == SignalType.HOLDING_REGISTER:
                return self.write_single_register(slave_addr, reg_addr, int(value))
            
            else:
                raise ValueError(f"Signal type {signal.signal_type} is read-only")
        
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
