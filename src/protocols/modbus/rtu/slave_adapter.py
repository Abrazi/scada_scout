"""
Modbus RTU Slave Adapter
Implements Modbus RTU slave role for responding to master requests
Includes simulation mode for testing
"""
import logging
import threading
import time
from typing import Optional
from datetime import datetime

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import (
    DeviceConfig, Node, Signal, SignalType, SignalQuality
)

from .transport import SerialTransport, RTUoverTCPTransport, SerialConfig
from .frame_handler import (
    ModbusRTUFrameHandler, ModbusFunctionCode, ModbusExceptionCode
)
from .timing import ModbusRTUTiming
from .simulator import ModbusRTUSimulator, SimulatorConfig

logger = logging.getLogger(__name__)


class ModbusRTUSlaveAdapter(BaseProtocol):
    """
    Modbus RTU Slave Protocol Implementation
    
    Acts as a Modbus RTU slave device, responding to master requests
    Can operate in simulation mode for testing
    """
    
    def __init__(self, config: DeviceConfig, event_logger=None, simulation=False):
        super().__init__(config)
        self.event_logger = event_logger
        self.connected = False
        self.simulation = simulation
        
        # Transport and protocol components
        self.transport = None
        self.frame_handler = ModbusRTUFrameHandler()
        self.timing = None
        
        # Simulator (if simulation mode)
        self.simulator = None
        
        # Configuration
        self.slave_address = config.rtu_slave_address
        
        # Request processing thread
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        logger.info(f"ModbusRTU Slave initialized (address={self.slave_address}, simulation={simulation})")
    
    def connect(self) -> bool:
        """Start slave service"""
        if self.event_logger:
            mode = "Simulator" if self.simulation else "Slave"
            self.event_logger.info(self.config.name, f"Starting Modbus RTU {mode}")
        
        try:
            # Create transport
            if self.config.rtu_transport == "serial":
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
                self.transport = RTUoverTCPTransport(
                    host=self.config.ip_address or "0.0.0.0",
                    port=self.config.port,
                    timeout=self.config.serial_timeout
                )
                self.timing = ModbusRTUTiming(baudrate=9600)
                
                if self.event_logger:
                    self.event_logger.transaction(
                        self.config.name,
                        f"→ Binding to {self.config.ip_address}:{self.config.port}"
                    )
            
            else:
                raise ValueError(f"Unknown transport type: {self.config.rtu_transport}")
            
            # Open transport
            if not self.transport.open():
                if self.event_logger:
                    self.event_logger.error(self.config.name, "Failed to open transport")
                return False
            
            # Initialize simulator if in simulation mode
            if self.simulation:
                sim_config = self._create_simulator_config()
                self.simulator = ModbusRTUSimulator(sim_config)
                
                # Register change callback to notify UI
                self.simulator.register_change_callback(self._on_memory_change)
                
                if self.event_logger:
                    self.event_logger.info(
                        self.config.name,
                        f"Simulator initialized with {sim_config.holding_registers_count} registers"
                    )
            
            # Start request processing thread
            self._running = True
            self._thread = threading.Thread(
                target=self._request_processing_loop,
                name=f"RTU_Slave_{self.slave_address}",
                daemon=True
            )
            self._thread.start()
            
            self.connected = True
            
            if self.event_logger:
                self.event_logger.info(
                    self.config.name,
                    f"✓ Slave active on address {self.slave_address}"
                )
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start slave: {e}")
            if self.event_logger:
                self.event_logger.error(self.config.name, f"Startup failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Stop slave service"""
        self._running = False
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        # Close transport
        if self.transport:
            self.transport.close()
            self.transport = None
        
        self.connected = False
        
        if self.event_logger:
            self.event_logger.info(self.config.name, "Slave stopped")
        
        logger.info("Modbus RTU Slave disconnected")
    
    def discover(self) -> Node:
        """
        Build device model from simulator configuration
        """
        root = Node(
            name=self.config.name,
            description=f"Modbus RTU Slave {self.slave_address}"
        )
        
        if self.simulator:
            # Create nodes from simulator memory
            config = self.simulator.config
            
            # Coils node
            if config.coils_count > 0:
                coils_node = Node(name="Coils", description="Read/Write Coils")
                for addr in range(config.coils_start, config.coils_start + config.coils_count):
                    signal = Signal(
                        name=f"Coil_{addr}",
                        address=f"{self.slave_address}:1:{addr}",
                        signal_type=SignalType.COIL,
                        access="RW",
                        value=self.simulator._coils.get(addr, False),
                        quality=SignalQuality.GOOD
                    )
                    coils_node.signals.append(signal)
                root.children.append(coils_node)
            
            # Discrete Inputs node
            if config.discrete_inputs_count > 0:
                di_node = Node(name="Discrete Inputs", description="Read-Only Inputs")
                for addr in range(config.discrete_inputs_start,
                                config.discrete_inputs_start + config.discrete_inputs_count):
                    signal = Signal(
                        name=f"DI_{addr}",
                        address=f"{self.slave_address}:2:{addr}",
                        signal_type=SignalType.DISCRETE_INPUT,
                        access="RO",
                        value=self.simulator._discrete_inputs.get(addr, False),
                        quality=SignalQuality.GOOD
                    )
                    di_node.signals.append(signal)
                root.children.append(di_node)
            
            # Input Registers node
            if config.input_registers_count > 0:
                ir_node = Node(name="Input Registers", description="Read-Only Registers")
                for addr in range(config.input_registers_start,
                                config.input_registers_start + config.input_registers_count):
                    signal = Signal(
                        name=f"IR_{addr}",
                        address=f"{self.slave_address}:4:{addr}",
                        signal_type=SignalType.INPUT_REGISTER,
                        access="RO",
                        value=self.simulator._input_registers.get(addr, 0),
                        quality=SignalQuality.GOOD
                    )
                    ir_node.signals.append(signal)
                root.children.append(ir_node)
            
            # Holding Registers node
            if config.holding_registers_count > 0:
                hr_node = Node(name="Holding Registers", description="Read/Write Registers")
                for addr in range(config.holding_registers_start,
                                config.holding_registers_start + config.holding_registers_count):
                    signal = Signal(
                        name=f"HR_{addr}",
                        address=f"{self.slave_address}:3:{addr}",
                        signal_type=SignalType.HOLDING_REGISTER,
                        access="RW",
                        value=self.simulator._holding_registers.get(addr, 0),
                        quality=SignalQuality.GOOD
                    )
                    hr_node.signals.append(signal)
                root.children.append(hr_node)
        
        return root
    
    def read_signal(self, signal: Signal) -> Signal:
        """Read signal from simulator"""
        if not self.simulator:
            signal.quality = SignalQuality.NOT_CONNECTED
            signal.error = "No simulator available"
            return signal
        
        try:
            parts = signal.address.split(':')
            if len(parts) != 3:
                raise ValueError(f"Invalid address format: {signal.address}")
            
            func_code = int(parts[1])
            reg_addr = int(parts[2])
            
            if func_code == 1:  # Coil
                signal.value = self.simulator._coils.get(reg_addr, False)
                signal.quality = SignalQuality.GOOD
            
            elif func_code == 2:  # Discrete Input
                signal.value = self.simulator._discrete_inputs.get(reg_addr, False)
                signal.quality = SignalQuality.GOOD
            
            elif func_code == 3:  # Holding Register
                signal.value = self.simulator._holding_registers.get(reg_addr, 0)
                signal.quality = SignalQuality.GOOD
            
            elif func_code == 4:  # Input Register
                signal.value = self.simulator._input_registers.get(reg_addr, 0)
                signal.quality = SignalQuality.GOOD
            
            signal.timestamp = datetime.now()
        
        except Exception as e:
            logger.error(f"Error reading signal: {e}")
            signal.quality = SignalQuality.INVALID
            signal.error = str(e)
        
        return signal
    
    def send_command(self, signal: Signal, value, params: dict = None) -> bool:
        """Write signal to simulator"""
        if not self.simulator:
            return False
        
        try:
            parts = signal.address.split(':')
            if len(parts) != 3:
                return False
            
            func_code = int(parts[1])
            reg_addr = int(parts[2])
            
            if func_code == 1:  # Coil
                return self.simulator.write_single_coil(reg_addr, bool(value))
            
            elif func_code == 3:  # Holding Register
                return self.simulator.write_single_register(reg_addr, int(value))
            
            else:
                logger.warning(f"Cannot write to read-only signal: {signal.address}")
                return False
        
        except Exception as e:
            logger.error(f"Error writing signal: {e}")
            return False
    
    # ========================================================================
    # Request Processing
    # ========================================================================
    
    def _request_processing_loop(self):
        """Main loop for processing incoming requests"""
        logger.info(f"Slave {self.slave_address} request processing started")
        
        while self._running:
            try:
                # Receive request
                request_bytes = self.transport.receive_frame(timeout=0.1)
                
                if not request_bytes:
                    continue  # Timeout, check _running flag
                
                if self.event_logger:
                    self.event_logger.transaction(
                        self.config.name,
                        f"← RX: {request_bytes.hex()}"
                    )
                
                # Parse request
                request_frame = self.frame_handler.parse_frame(request_bytes)
                
                if not request_frame:
                    # CRC error - discard frame, no response
                    if self.event_logger:
                        self.event_logger.error(
                            self.config.name,
                            "CRC validation failed - frame discarded"
                        )
                    if self.simulator:
                        self.simulator.stats.invalid_requests += 1
                    continue
                
                # Check if request is for us
                if request_frame.slave_address == 0:
                    # Broadcast - process but don't respond
                    if self.simulator:
                        self.simulator.stats.broadcast_requests += 1
                    self._process_request(request_frame, is_broadcast=True)
                    if self.event_logger:
                        self.event_logger.info(
                            self.config.name,
                            "Broadcast request processed (no response)"
                        )
                    continue
                
                elif request_frame.slave_address != self.slave_address:
                    # Not for us - ignore
                    continue
                
                # Process request and generate response
                if self.simulator:
                    self.simulator.stats.total_requests += 1
                    self.simulator.stats.last_request_at = datetime.now()
                
                response = self._process_request(request_frame, is_broadcast=False)
                
                if response:
                    # Wait turnaround delay
                    if self.timing:
                        time.sleep(self.timing.get_turnaround_delay())
                    
                    # Send response
                    if self.transport.send_frame(response):
                        if self.event_logger:
                            self.event_logger.transaction(
                                self.config.name,
                                f"→ TX: {response.hex()}"
                            )
                    else:
                        logger.error("Failed to send response")
            
            except Exception as e:
                logger.error(f"Error in request processing loop: {e}")
                time.sleep(0.1)  # Avoid tight loop on persistent error
        
        logger.info(f"Slave {self.slave_address} request processing stopped")
    
    def _process_request(self, request_frame, is_broadcast: bool = False) -> Optional[bytes]:
        """
        Process a request and generate response
        Returns response frame bytes or None
        """
        func_code = request_frame.function_code
        
        try:
            # FC01: Read Coils
            if func_code == ModbusFunctionCode.READ_COILS:
                return self._handle_read_coils(request_frame, is_broadcast)
            
            # FC02: Read Discrete Inputs
            elif func_code == ModbusFunctionCode.READ_DISCRETE_INPUTS:
                return self._handle_read_discrete_inputs(request_frame, is_broadcast)
            
            # FC03: Read Holding Registers
            elif func_code == ModbusFunctionCode.READ_HOLDING_REGISTERS:
                return self._handle_read_holding_registers(request_frame, is_broadcast)
            
            # FC04: Read Input Registers
            elif func_code == ModbusFunctionCode.READ_INPUT_REGISTERS:
                return self._handle_read_input_registers(request_frame, is_broadcast)
            
            # FC05: Write Single Coil
            elif func_code == ModbusFunctionCode.WRITE_SINGLE_COIL:
                return self._handle_write_single_coil(request_frame, is_broadcast)
            
            # FC06: Write Single Register
            elif func_code == ModbusFunctionCode.WRITE_SINGLE_REGISTER:
                return self._handle_write_single_register(request_frame, is_broadcast)
            
            # FC15: Write Multiple Coils
            elif func_code == ModbusFunctionCode.WRITE_MULTIPLE_COILS:
                return self._handle_write_multiple_coils(request_frame, is_broadcast)
            
            # FC16: Write Multiple Registers
            elif func_code == ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS:
                return self._handle_write_multiple_registers(request_frame, is_broadcast)
            
            else:
                # Unsupported function code
                logger.warning(f"Unsupported function code: {func_code}")
                if not is_broadcast:
                    if self.simulator:
                        self.simulator.stats.exception_responses += 1
                    return self.frame_handler.build_exception_response(
                        self.slave_address,
                        func_code,
                        ModbusExceptionCode.ILLEGAL_FUNCTION
                    )
                return None
        
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            if not is_broadcast:
                if self.simulator:
                    self.simulator.stats.exception_responses += 1
                return self.frame_handler.build_exception_response(
                    self.slave_address,
                    func_code,
                    ModbusExceptionCode.SLAVE_DEVICE_FAILURE
                )
            return None
    
    def _handle_read_coils(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC01: Read Coils"""
        if not self.simulator or is_broadcast:
            return None
        
        import struct
        start_addr, count = struct.unpack('>HH', request_frame.data)
        
        coils = self.simulator.read_coils(start_addr, count)
        
        if coils is None:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.READ_COILS,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        self.simulator.stats.successful_responses += 1
        return self.frame_handler.build_read_coils_response(self.slave_address, coils)
    
    def _handle_read_discrete_inputs(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC02: Read Discrete Inputs"""
        if not self.simulator or is_broadcast:
            return None
        
        import struct
        start_addr, count = struct.unpack('>HH', request_frame.data)
        
        inputs = self.simulator.read_discrete_inputs(start_addr, count)
        
        if inputs is None:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.READ_DISCRETE_INPUTS,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        self.simulator.stats.successful_responses += 1
        return self.frame_handler.build_read_coils_response(self.slave_address, inputs)
    
    def _handle_read_holding_registers(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC03: Read Holding Registers"""
        if not self.simulator or is_broadcast:
            return None
        
        import struct
        start_addr, count = struct.unpack('>HH', request_frame.data)
        
        registers = self.simulator.read_holding_registers(start_addr, count)
        
        if registers is None:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.READ_HOLDING_REGISTERS,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        self.simulator.stats.successful_responses += 1
        return self.frame_handler.build_read_registers_response(
            self.slave_address,
            ModbusFunctionCode.READ_HOLDING_REGISTERS,
            registers
        )
    
    def _handle_read_input_registers(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC04: Read Input Registers"""
        if not self.simulator or is_broadcast:
            return None
        
        import struct
        start_addr, count = struct.unpack('>HH', request_frame.data)
        
        registers = self.simulator.read_input_registers(start_addr, count)
        
        if registers is None:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.READ_INPUT_REGISTERS,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        self.simulator.stats.successful_responses += 1
        return self.frame_handler.build_read_registers_response(
            self.slave_address,
            ModbusFunctionCode.READ_INPUT_REGISTERS,
            registers
        )
    
    def _handle_write_single_coil(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC05: Write Single Coil"""
        if not self.simulator:
            return None
        
        import struct
        address, value = struct.unpack('>HH', request_frame.data)
        coil_value = value == 0xFF00
        
        success = self.simulator.write_single_coil(address, coil_value)
        
        if not success and not is_broadcast:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_SINGLE_COIL,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        if not is_broadcast:
            self.simulator.stats.successful_responses += 1
            return self.frame_handler.build_write_single_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_SINGLE_COIL,
                address,
                value
            )
        return None
    
    def _handle_write_single_register(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC06: Write Single Register"""
        if not self.simulator:
            return None
        
        import struct
        address, value = struct.unpack('>HH', request_frame.data)
        
        success = self.simulator.write_single_register(address, value)
        
        if not success and not is_broadcast:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_SINGLE_REGISTER,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        if not is_broadcast:
            self.simulator.stats.successful_responses += 1
            return self.frame_handler.build_write_single_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_SINGLE_REGISTER,
                address,
                value
            )
        return None
    
    def _handle_write_multiple_coils(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC15: Write Multiple Coils"""
        if not self.simulator:
            return None
        
        import struct
        start_addr, count, byte_count = struct.unpack('>HHB', request_frame.data[:5])
        coil_bytes = request_frame.data[5:]
        
        # Unpack coils from bytes
        coils = []
        for i in range(count):
            byte_index = i // 8
            bit_index = i % 8
            if byte_index < len(coil_bytes):
                coils.append((coil_bytes[byte_index] & (1 << bit_index)) != 0)
        
        success = self.simulator.write_multiple_coils(start_addr, coils)
        
        if not success and not is_broadcast:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_MULTIPLE_COILS,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        if not is_broadcast:
            self.simulator.stats.successful_responses += 1
            return self.frame_handler.build_write_multiple_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_MULTIPLE_COILS,
                start_addr,
                count
            )
        return None
    
    def _handle_write_multiple_registers(self, request_frame, is_broadcast) -> Optional[bytes]:
        """Handle FC16: Write Multiple Registers"""
        if not self.simulator:
            return None
        
        import struct
        start_addr, count, byte_count = struct.unpack('>HHB', request_frame.data[:5])
        register_bytes = request_frame.data[5:]
        
        # Unpack registers
        registers = []
        for i in range(count):
            offset = i * 2
            if offset + 1 < len(register_bytes):
                value = struct.unpack('>H', register_bytes[offset:offset+2])[0]
                registers.append(value)
        
        success = self.simulator.write_multiple_registers(start_addr, registers)
        
        if not success and not is_broadcast:
            return self.frame_handler.build_exception_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS,
                ModbusExceptionCode.ILLEGAL_DATA_ADDRESS
            )
        
        if not is_broadcast:
            self.simulator.stats.successful_responses += 1
            return self.frame_handler.build_write_multiple_response(
                self.slave_address,
                ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS,
                start_addr,
                count
            )
        return None
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _create_simulator_config(self) -> SimulatorConfig:
        """Create simulator configuration from device config"""
        if self.config.rtu_simulator_config:
            # Load from config
            cfg_dict = self.config.rtu_simulator_config
            return SimulatorConfig(
                slave_address=self.slave_address,
                coils_start=cfg_dict.get('coils', {}).get('start', 0),
                coils_count=cfg_dict.get('coils', {}).get('count', 100),
                discrete_inputs_start=cfg_dict.get('discrete_inputs', {}).get('start', 0),
                discrete_inputs_count=cfg_dict.get('discrete_inputs', {}).get('count', 100),
                input_registers_start=cfg_dict.get('input_registers', {}).get('start', 0),
                input_registers_count=cfg_dict.get('input_registers', {}).get('count', 100),
                holding_registers_start=cfg_dict.get('holding_registers', {}).get('start', 0),
                holding_registers_count=cfg_dict.get('holding_registers', {}).get('count', 100),
            )
        else:
            # Default configuration
            return SimulatorConfig(
                slave_address=self.slave_address,
                coils_count=100,
                discrete_inputs_count=100,
                input_registers_count=100,
                holding_registers_count=100
            )
    
    def _on_memory_change(self, memory_type: str, address: int, value):
        """Callback when simulator memory changes"""
        # Emit update via callback if configured
        if self._callback:
            # Create signal for the changed value
            if memory_type == 'coil':
                func_code = 1
                sig_type = SignalType.COIL
            elif memory_type == 'discrete_input':
                func_code = 2
                sig_type = SignalType.DISCRETE_INPUT
            elif memory_type == 'input_register':
                func_code = 4
                sig_type = SignalType.INPUT_REGISTER
            else:  # holding_register
                func_code = 3
                sig_type = SignalType.HOLDING_REGISTER
            
            signal = Signal(
                name=f"{memory_type}_{address}",
                address=f"{self.slave_address}:{func_code}:{address}",
                signal_type=sig_type,
                value=value,
                quality=SignalQuality.GOOD,
                timestamp=datetime.now()
            )
            
            self._emit_update(signal)
    
    def get_simulator_stats(self) -> str:
        """Get simulator statistics summary"""
        if self.simulator:
            return self.simulator.get_stats_summary()
        return "No simulator available"
