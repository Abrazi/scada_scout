from typing import Optional
import logging
from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Signal, Node
from src.protocols.modbus.slave_server import ModbusSlaveServer, ModbusSlaveConfig

logger = logging.getLogger(__name__)

class ModbusServerAdapter(BaseProtocol):
    """
    Adapter that manages a local Modbus Slave Server instance.
    Treats the server as a "Device" that can be connected (started) and disconnected (stopped).
    """
    def __init__(self, config: DeviceConfig, event_logger=None):
        self.config = config
        self.event_logger = event_logger
        self.server: Optional[ModbusSlaveServer] = None
        self._data_callback = None
        
        # Initialize the server instance using configured blocks
        slave_config = ModbusSlaveConfig(
            listen_address=config.ip_address,
            port=config.port,
            unit_id=config.modbus_unit_id,
            register_blocks=getattr(config, 'modbus_slave_blocks', [])
        )
        self.server = ModbusSlaveServer(slave_config, event_logger)
        
        # Load existing mappings from config
        for mapping in getattr(config, 'modbus_slave_mappings', []):
            self.server.mappings[mapping.address] = mapping

    def connect(self) -> bool:
        """Starts the Modbus Server."""
        if not self.server:
            return False
            
        try:
            # Re-apply config in case it changed in UI before connect
            # The UI might have updated config.modbus_slave_blocks
            self.server.config.port = self.config.port
            self.server.config.listen_address = self.config.ip_address
            self.server.config.unit_id = self.config.modbus_unit_id
            
            # If register blocks changed, we theoretically need to recreate the server 
            # or re-init the blocks. ModbusSlaveServer initializes blocks in __init__.
            # So let's re-instantiate if blocks differ?
            # For robustness, let's just re-init the server instance here if not running.
            if not self.server.running:
                 slave_config = ModbusSlaveConfig(
                    listen_address=self.config.ip_address,
                    port=self.config.port,
                    unit_id=self.config.modbus_unit_id,
                    register_blocks=getattr(self.config, 'modbus_slave_blocks', [])
                 )
                 # Preserve stats or events? Maybe not critical.
                 # But we must preserve mappings.
                 mappings = self.server.mappings
                 self.server = ModbusSlaveServer(slave_config, self.event_logger)
                 self.server.mappings = mappings

            logger.info(f"Starting Modbus Server on {self.config.ip_address}:{self.config.port}")
            success = self.server.start()
            return success
        except Exception as e:
            logger.error(f"Failed to start Modbus Server: {e}")
            return False

    def disconnect(self):
        """Stops the Modbus Server."""
        if self.server and self.server.running:
            logger.info("Stopping Modbus Server...")
            self.server.stop()

    def is_connected(self) -> bool:
        """Checks if the server is running."""
        return self.server.running if self.server else False

    def discover(self) -> Node:
        """
        Returns a Node representing the server structure based on configured blocks.
        """
        root = Node(name=self.config.name, description="Modbus Slave Server")
        
        # Create categories for registers
        holding = Node(name="Holding Registers", description="RW Registers (4x)")
        input_regs = Node(name="Input Registers", description="RO Registers (3x)")
        coils = Node(name="Coils", description="RW Coils (0x)")
        discrete = Node(name="Discrete Inputs", description="RO Inputs (1x)")
        
        cat_map = {
            "holding": holding,
            "input": input_regs,
            "coils": coils,
            "discrete": discrete
        }
        
        # Populate from blocks
        if hasattr(self.config, 'modbus_slave_blocks'):
            for block in self.config.modbus_slave_blocks:
                parent = cat_map.get(block.register_type)
                if not parent:
                    continue
                
                # Create a group node for the block
                block_node = Node(
                    name=block.name,
                    description=f"Address {block.start_address} - {block.start_address + block.count - 1}"
                )
                
                # Create signals for each register in the block
                for i in range(block.count):
                    addr = block.start_address + i
                    sig_name = f"Reg {addr}"
                    
                    # Create Signal
                    sig = Signal(
                        name=sig_name,
                        address=f"{block.register_type}:{addr}",
                        description=f"{block.register_type} at {addr}",
                        access="RW" if block.register_type in ["holding", "coils"] else "RO"
                    )
                    block_node.signals.append(sig)
                
                parent.children.append(block_node)
        
        # Only add categories that have children
        for cat in [holding, input_regs, coils, discrete]:
            if cat.children:
                root.children.append(cat)
        
        return root

    def read_signal(self, signal: Signal) -> Optional[Signal]:
        """
        Reads value directly from the server's data store.
        Signal address format: "type:address"
        """
        if not self.server or not self.server.running:
            return None
            
        try:
            type_str, addr_str = signal.address.split(':')
            address = int(addr_str)
            
            val = None
            if type_str == "holding":
                val = self.server.read_register(address)
            elif type_str == "input":
                # Server usually doesn't have read_input_register equivalent exposed publicly same way
                # It uses read_register internally for 3x if mapped?
                # No, slave_server has input_registers_block.
                # We need to access the block directly or add a getter.
                # slave_server.py has 'get_all_registers(type)' or internal blocks.
                # Let's check available methods.
                # We added `read_register` (holding) and `read_coil` in slave_server.py but missed input?
                # Check slave_server.py again.
                # It has `read_register` (holding) and `read_coil`.
                # We should use `input_registers_block.getValues`.
                
                # Let's access blocks directly for speed or add helpers?
                # Accessing internal blocks is fine for adapter.
                if self.server.input_registers_block:
                    vals = self.server.input_registers_block.getValues(address, 1)
                    val = vals[0] if vals else None
            
            elif type_str == "coils":
                val = self.server.read_coil(address)
            
            elif type_str == "discrete":
                if self.server.discrete_inputs_block:
                    vals = self.server.discrete_inputs_block.getValues(address, 1)
                    val = bool(vals[0]) if vals else None

            if val is not None:
                signal.value = val
                return signal
            else:
                return None
                
        except Exception as e:
            logger.debug(f"Read error for {signal.address}: {e}")
            return None

    def set_data_callback(self, callback):
        self._data_callback = callback
