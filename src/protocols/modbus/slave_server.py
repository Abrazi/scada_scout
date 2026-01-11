"""
Modbus TCP Slave/Server Implementation
Allows application to act as a Modbus device for testing and simulation
"""
import logging
import threading
from typing import Dict, Callable, Optional, Any, List
from datetime import datetime
from dataclasses import dataclass, field

try:
    # pymodbus 3.x imports (verified for 3.11.x)
    from pymodbus.server import StartTcpServer, StartAsyncTcpServer, ServerAsyncStop
    from pymodbus.pdu.device import ModbusDeviceIdentification
    from src.models.device_models import (
        ModbusDataType, ModbusEndianness, ModbusSignalMapping
    )
    from src.protocols.modbus.register_mapping import (
        encode_mapped_value, decode_mapped_value, get_register_count
    )
    from pymodbus.datastore import (
        ModbusSequentialDataBlock, 
        ModbusDeviceContext, 
        ModbusServerContext
    )
    from pymodbus.datastore.store import BaseModbusDataBlock
    HAS_PYMODBUS_SERVER = True
except ImportError as e:
    logger.debug(f"Pymodbus 3.x import failed: {e}")
    HAS_PYMODBUS_SERVER = False
    StartTcpServer = None
    ServerAsyncStop = None
    ModbusDeviceIdentification = None
    ModbusDeviceContext = None
    ModbusServerContext = None
    BaseModbusDataBlock = object

logger = logging.getLogger(__name__)


@dataclass
class ModbusSlaveConfig:
    """Configuration for Modbus slave/server"""
    name: str = "SCADA Scout Simulator"
    listen_address: str = "0.0.0.0"  # Listen on all interfaces
    port: int = 5020  # Use non-standard port to avoid conflicts
    unit_id: int = 1  # Standard Modbus unit ID
    
    # Register blocks (sparse memory allocation)
    # If empty, defaults to 0-1000 for all types
    register_blocks: List = field(default_factory=list) 
    
    # Legacy fallbacks (used if blocks not defined)
    coils_count: int = 1000
    discrete_inputs_count: int = 1000
    holding_registers_count: int = 1000
    input_registers_count: int = 1000
    
    # Device identification
    vendor_name: str = "SCADA Scout"
    product_code: str = "SS-SIMULATOR-1"
    vendor_url: str = "https://github.com/scadascout"
    product_name: str = "SCADA Scout Modbus Simulator"
    model_name: str = "Virtual Device"
    
    # Server settings
    allow_reuse_address: bool = True
    ignore_missing_slaves: bool = False


class CallbackDataBlock(BaseModbusDataBlock):
    """
    Custom data block that triggers callbacks on read/write
    Allows external code to respond to Modbus operations
    """
    def __init__(self, values, event_logger=None):
        super().__init__()
        # In pymodbus 3, values can be a dictionary mapping address -> value
        # This supports sparse data blocks efficiently
        self.values = values if isinstance(values, dict) else {i: v for i, v in enumerate(values)}
        self.default_value = 0
        self.event_logger = event_logger
        
        # Callbacks
        self.read_callback: Optional[Callable] = None
        self.write_callback: Optional[Callable] = None
    
    def validate(self, address, count=1):
        """Validate address range"""
        # With sparse block, we validate if ALL requested addresses exist
        for i in range(address, address + count):
            if i not in self.values:
                return False
        return True
    
    def getValues(self, address, count=1):
        """Read values with callback"""
        if not self.validate(address, count):
             # Return empty/default if invalid, though validate should catch it
             pass

        if self.read_callback:
            try:
                self.read_callback(address, count)
            except Exception as e:
                logger.error(f"Read callback error: {e}")
        
        result = []
        for i in range(address, address + count):
            result.append(self.values.get(i, self.default_value))
        
        if self.event_logger:
            self.event_logger.transaction("ModbusSlave", f"← READ Addr={address} Count={count} Values={result[:5]}...")
        
        return result
    
    def setValues(self, address, values):
        """Write values with callback"""
        # Validate existence
        if not self.validate(address, len(values)):
             return # Or raise error? pymodbus handles validation failure

        if self.event_logger:
            self.event_logger.transaction("ModbusSlave", f"→ WRITE Addr={address} Count={len(values)} Values={values[:5]}...")
        
        for i, value in enumerate(values):
            self.values[address + i] = value
        
        if self.write_callback:
            try:
                self.write_callback(address, values)
            except Exception as e:
                logger.error(f"Write callback error: {e}")


class ModbusSlaveServer:
    """
    Modbus TCP Slave/Server
    Simulates a Modbus device that can be queried by clients
    """
    
    def __init__(self, config: ModbusSlaveConfig = None, event_logger=None):
        self.config = config or ModbusSlaveConfig()
        self.event_logger = event_logger
        self.running = False
        self.server_thread = None
        self.context = None
        
        # Initialize Memory dictionaries
        coils_map = {}
        discrete_map = {}
        holding_map = {}
        input_map = {}
        
        # Populate from blocks if defined
        if self.config.register_blocks:
            for block in self.config.register_blocks:
                # Determine target map
                target_map = None
                if block.register_type == "coils":
                    target_map = coils_map
                elif block.register_type == "discrete":
                    target_map = discrete_map
                elif block.register_type == "holding":
                    target_map = holding_map
                elif block.register_type == "input":
                    target_map = input_map
                
                if target_map is not None:
                     for i in range(block.start_address, block.start_address + block.count):
                         target_map[i] = 0
            
            # If a type has NO blocks, it stays empty (access will fail)
            logger.info(f"Initialized sparse memory: HR={len(holding_map)} IR={len(input_map)}")
            
        else:
            # Legacy/Default mode
            coils_map = {i: 0 for i in range(self.config.coils_count)}
            discrete_map = {i: 0 for i in range(self.config.discrete_inputs_count)}
            holding_map = {i: 0 for i in range(self.config.holding_registers_count)}
            input_map = {i: 0 for i in range(self.config.input_registers_count)}

        # Data blocks with callbacks
        self.coils_block = CallbackDataBlock(coils_map, self.event_logger)
        self.discrete_inputs_block = CallbackDataBlock(discrete_map, self.event_logger)
        self.holding_registers_block = CallbackDataBlock(holding_map, self.event_logger)
        self.input_registers_block = CallbackDataBlock(input_map, self.event_logger)
        
        # Signal mappings for structured data
        self.mappings: Dict[int, ModbusSignalMapping] = {}
        
        # Statistics
        self.stats = {
            'start_time': None,
            'read_count': 0,
            'write_count': 0,
            'error_count': 0,
            'client_connections': 0
        }
        
        if not HAS_PYMODBUS_SERVER:
            logger.error("pymodbus server not available")
    
    def set_callbacks(self, 
                     on_read: Optional[Callable] = None,
                     on_write: Optional[Callable] = None):
        """Set callbacks for read/write operations"""
        if self.coils_block:
            self.coils_block.read_callback = on_read
            self.coils_block.write_callback = on_write
        
        if self.holding_registers_block:
            self.holding_registers_block.read_callback = on_read
            self.holding_registers_block.write_callback = on_write
    
    def start(self) -> bool:
        """Start the Modbus server"""
        if not HAS_PYMODBUS_SERVER:
            logger.error("Cannot start server: pymodbus not available")
            return False
        
        if self.running:
            logger.warning("Server already running")
            return False
        
        try:
            # Blocks are already initialized in __init__
            
            # Create slave context (Unit ID 1) - ModbusSlaveContext is ModbusDeviceContext in 3.x
            store = ModbusDeviceContext(
                di=self.discrete_inputs_block,  # Discrete Inputs
                co=self.coils_block,            # Coils
                hr=self.holding_registers_block, # Holding Registers
                ir=self.input_registers_block    # Input Registers
            )
            
            # Create server context (supports multiple slaves)
            # Use the specified unit_id from config
            # FIX: Use 'devices' instead of 'slaves' for pymodbus 3.x
            self.context = ModbusServerContext(devices={self.config.unit_id: store}, single=True)
            
            # Device identification
            identity = ModbusDeviceIdentification()
            identity.VendorName = self.config.vendor_name
            identity.ProductCode = self.config.product_code
            identity.VendorUrl = self.config.vendor_url
            identity.ProductName = self.config.product_name
            identity.ModelName = self.config.model_name
            identity.MajorMinorRevision = '1.0.0'
            
            # Start server in separate thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                args=(self.context, identity),
                daemon=True
            )
            self.server_thread.start()
            
            self.running = True
            self.stats['start_time'] = datetime.now()
            
            if self.event_logger:
                self.event_logger.info("ModbusSlave", 
                    f"✓ Server started on {self.config.listen_address}:{self.config.port}")
            
            logger.info(f"Modbus slave server started on {self.config.listen_address}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Modbus server: {e}")
            if self.event_logger:
                self.event_logger.error("ModbusSlave", f"Failed to start: {e}")
            return False
    
    def _run_server(self, context, identity):
        """Run server (called in thread) - pymodbus 3.x async version"""
        try:
            import asyncio
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async server
            loop.run_until_complete(
                StartAsyncTcpServer(
                    context=context,
                    identity=identity,
                    address=(self.config.listen_address, self.config.port),
                    ignore_missing_devices=self.config.ignore_missing_slaves
                )
            )
        except Exception as e:
            logger.error(f"Server thread error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the Modbus server"""
        if not self.running:
            return
        
        try:
            # pymodbus 3.x: ServerAsyncStop is deprecated, just set running flag
            self.running = False
            
            if self.event_logger:
                uptime = datetime.now() - self.stats['start_time']
                self.event_logger.info("ModbusSlave", 
                    f"Server stopped. Uptime: {uptime}")
            
            logger.info("Modbus slave server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
    
    def write_coil(self, address: int, value: bool) -> bool:
        """Programmatically write to coil"""
        try:
            self.coils_block.setValues(address, [1 if value else 0])
            return True
        except Exception as e:
            logger.error(f"Error writing coil: {e}")
            return False
    
    def write_register(self, address: int, value: int) -> bool:
        """Programmatically write to holding register"""
        try:
            self.holding_registers_block.setValues(address, [value])
            return True
        except Exception as e:
            logger.error(f"Error writing register: {e}")
            return False
    
    def write_input_register(self, address: int, value: int) -> bool:
        """Programmatically write to input register"""
        try:
            self.input_registers_block.setValues(address, [value])
            return True
        except Exception as e:
            logger.error(f"Error writing input register: {e}")
            return False
            
    def write_mapped_value(self, address: int, value: Any, register_type: str = "holding") -> bool:
        """Writes a structured value using its mapping definition."""
        mapping = self.mappings.get(address)
        if not mapping:
            # Fallback to default UINT16 if no mapping exists
            if register_type == "holding":
                return self.write_register(address, int(value))
            return self.write_input_register(address, int(value))
            
        try:
            registers = encode_mapped_value(
                value, 
                mapping.data_type, 
                mapping.endianness, 
                mapping.scale, 
                mapping.offset
            )
            
            if register_type == "holding":
                self.holding_registers_block.setValues(address, registers)
            else:
                self.input_registers_block.setValues(address, registers)
            return True
        except Exception as e:
            logger.error(f"Error writing mapped value at {address}: {e}")
            return False

    def get_mapped_value(self, address: int, register_type: str = "holding") -> Any:
        """Reads a structured value using its mapping definition."""
        mapping = self.mappings.get(address)
        if not mapping:
            # Fallback to default UINT16
            return self.read_register(address) if register_type == "holding" else None
            
        try:
            count = get_register_count(mapping.data_type, mapping.string_length)
            block = self.holding_registers_block if register_type == "holding" else self.input_registers_block
            registers = block.getValues(address, count)
            
            return decode_mapped_value(
                registers, 
                mapping.data_type, 
                mapping.endianness, 
                mapping.scale, 
                mapping.offset
            )
        except Exception as e:
            logger.error(f"Error reading mapped value at {address}: {e}")
            return None
    
    def write_discrete_input(self, address: int, value: bool) -> bool:
        """Programmatically write to discrete input"""
        try:
            self.discrete_inputs_block.setValues(address, [1 if value else 0])
            return True
        except Exception as e:
            logger.error(f"Error writing discrete input: {e}")
            return False
    
    def read_coil(self, address: int) -> Optional[bool]:
        """Read coil value"""
        try:
            values = self.coils_block.getValues(address, 1)
            return bool(values[0]) if values else None
        except:
            return None
    
    def read_register(self, address: int) -> Optional[int]:
        """Read holding register value"""
        try:
            values = self.holding_registers_block.getValues(address, 1)
            return values[0] if values else None
        except:
            return None
    
    def bulk_write_registers(self, start_address: int, values: list) -> bool:
        """Write multiple registers at once"""
        try:
            self.holding_registers_block.setValues(start_address, values)
            return True
        except Exception as e:
            logger.error(f"Error bulk writing registers: {e}")
            return False
    
    def bulk_write_coils(self, start_address: int, values: list) -> bool:
        """Write multiple coils at once"""
        try:
            int_values = [1 if v else 0 for v in values]
            self.coils_block.setValues(start_address, int_values)
            return True
        except Exception as e:
            logger.error(f"Error bulk writing coils: {e}")
            return False
    
    def get_all_registers(self, register_type: str = "holding") -> Dict[int, int]:
        """Get all register values for export/inspection"""
        if register_type == "holding":
            return self.holding_registers_block.values.copy()
        elif register_type == "input":
            return self.input_registers_block.values.copy()
        elif register_type == "coils":
            return self.coils_block.values.copy()
        elif register_type == "discrete":
            return self.discrete_inputs_block.values.copy()
        return {}
    
    def import_register_data(self, data: Dict[int, int], register_type: str = "holding"):
        """Import register data from dictionary"""
        try:
            if register_type == "holding":
                self.holding_registers_block.values.update(data)
            elif register_type == "input":
                self.input_registers_block.values.update(data)
            elif register_type == "coils":
                self.coils_block.values.update(data)
            elif register_type == "discrete":
                self.discrete_inputs_block.values.update(data)
            
            if self.event_logger:
                self.event_logger.info("ModbusSlave", 
                    f"Imported {len(data)} values to {register_type}")
            
            return True
        except Exception as e:
            logger.error(f"Error importing data: {e}")
            return False
    
    def simulate_sensor_updates(self, enable: bool = True):
        """Start/stop automatic sensor simulation"""
        if enable:
            # Start simulation thread
            self.simulation_thread = threading.Thread(
                target=self._simulate_sensors,
                daemon=True
            )
            self.simulation_active = True
            self.simulation_thread.start()
            
            if self.event_logger:
                self.event_logger.info("ModbusSlave", "Sensor simulation started")
        else:
            self.simulation_active = False
            if self.event_logger:
                self.event_logger.info("ModbusSlave", "Sensor simulation stopped")
    
    def _simulate_sensors(self):
        """Simulate changing sensor values"""
        import random
        import time
        
        address = 0
        while self.simulation_active:
            try:
                # Simulate temperature sensor (0.1°C resolution)
                temp = int(random.uniform(200, 300))  # 20.0 - 30.0°C
                self.write_input_register(address, temp)
                
                # Simulate pressure sensor
                pressure = int(random.uniform(1000, 1100))
                self.write_input_register(address + 1, pressure)
                
                # Simulate binary inputs (random state changes)
                for i in range(8):
                    if random.random() > 0.95:  # 5% chance to flip
                        current = self.read_coil(i)
                        self.write_discrete_input(i, not current if current is not None else True)
                
                time.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Simulation error: {e}")
                break
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics"""
        stats = self.stats.copy()
        if stats['start_time']:
            stats['uptime'] = str(datetime.now() - stats['start_time'])
        return stats
