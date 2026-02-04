"""
Modbus RTU Simulator
In-memory slave device simulation for testing and development
"""
import logging
import threading
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SimulatorConfig:
    """Configuration for Modbus RTU simulator"""
    slave_address: int = 1
    
    # Memory ranges
    coils_start: int = 0
    coils_count: int = 100
    discrete_inputs_start: int = 0
    discrete_inputs_count: int = 100
    input_registers_start: int = 0
    input_registers_count: int = 100
    holding_registers_start: int = 0
    holding_registers_count: int = 100
    
    # Initial values
    coils_initial: bool = False
    discrete_inputs_initial: bool = False
    input_registers_initial: int = 0
    holding_registers_initial: int = 0
    
    # Behavior
    allow_broadcast: bool = True
    process_delay: float = 0.0  # Artificial processing delay (seconds)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'slave_address': self.slave_address,
            'coils_start': self.coils_start,
            'coils_count': self.coils_count,
            'discrete_inputs_start': self.discrete_inputs_start,
            'discrete_inputs_count': self.discrete_inputs_count,
            'input_registers_start': self.input_registers_start,
            'input_registers_count': self.input_registers_count,
            'holding_registers_start': self.holding_registers_start,
            'holding_registers_count': self.holding_registers_count,
            'allow_broadcast': self.allow_broadcast,
            'process_delay': self.process_delay
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SimulatorConfig':
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class SimulatorStats:
    """Statistics for simulator operation"""
    total_requests: int = 0
    successful_responses: int = 0
    exception_responses: int = 0
    broadcast_requests: int = 0
    invalid_requests: int = 0
    
    read_coils: int = 0
    read_discrete_inputs: int = 0
    read_holding_registers: int = 0
    read_input_registers: int = 0
    write_single_coil: int = 0
    write_single_register: int = 0
    write_multiple_coils: int = 0
    write_multiple_registers: int = 0
    
    started_at: Optional[datetime] = None
    last_request_at: Optional[datetime] = None
    
    def reset(self):
        """Reset all statistics"""
        self.total_requests = 0
        self.successful_responses = 0
        self.exception_responses = 0
        self.broadcast_requests = 0
        self.invalid_requests = 0
        self.read_coils = 0
        self.read_discrete_inputs = 0
        self.read_holding_registers = 0
        self.read_input_registers = 0
        self.write_single_coil = 0
        self.write_single_register = 0
        self.write_multiple_coils = 0
        self.write_multiple_registers = 0
        self.started_at = datetime.now()
        self.last_request_at = None


class ModbusRTUSimulator:
    """
    Software-based Modbus RTU slave simulator
    
    Simulates a complete Modbus slave device with:
    - Coils (00001-09999) - Read/Write
    - Discrete Inputs (10001-19999) - Read Only
    - Input Registers (30001-39999) - Read Only
    - Holding Registers (40001-49999) - Read/Write
    """
    
    def __init__(self, config: SimulatorConfig):
        """Initialize simulator with configuration"""
        self.config = config
        self._lock = threading.RLock()
        
        # Initialize memory spaces
        self._coils: Dict[int, bool] = {}
        self._discrete_inputs: Dict[int, bool] = {}
        self._input_registers: Dict[int, int] = {}
        self._holding_registers: Dict[int, int] = {}
        
        # Statistics
        self.stats = SimulatorStats()
        self.stats.started_at = datetime.now()
        
        # Change callbacks
        self._change_callbacks: List[Callable] = []
        
        # Initialize memory
        self._initialize_memory()
        
        logger.info(f"Modbus RTU Simulator initialized (Slave {config.slave_address})")
    
    def _initialize_memory(self):
        """Initialize all memory spaces with default values"""
        with self._lock:
            # Coils
            for addr in range(self.config.coils_start,
                            self.config.coils_start + self.config.coils_count):
                self._coils[addr] = self.config.coils_initial
            
            # Discrete Inputs
            for addr in range(self.config.discrete_inputs_start,
                            self.config.discrete_inputs_start + self.config.discrete_inputs_count):
                self._discrete_inputs[addr] = self.config.discrete_inputs_initial
            
            # Input Registers
            for addr in range(self.config.input_registers_start,
                            self.config.input_registers_start + self.config.input_registers_count):
                self._input_registers[addr] = self.config.input_registers_initial
            
            # Holding Registers
            for addr in range(self.config.holding_registers_start,
                            self.config.holding_registers_start + self.config.holding_registers_count):
                self._holding_registers[addr] = self.config.holding_registers_initial
            
            logger.debug(f"Memory initialized: {len(self._coils)} coils, "
                        f"{len(self._discrete_inputs)} discrete inputs, "
                        f"{len(self._input_registers)} input registers, "
                        f"{len(self._holding_registers)} holding registers")
    
    def register_change_callback(self, callback: Callable):
        """Register callback for memory changes"""
        self._change_callbacks.append(callback)
    
    def _notify_change(self, memory_type: str, address: int, value):
        """Notify callbacks of memory change"""
        for callback in self._change_callbacks:
            try:
                callback(memory_type, address, value)
            except Exception as e:
                logger.error(f"Error in change callback: {e}")
    
    # ========================================================================
    # Coil Operations (FC01, FC05, FC15)
    # ========================================================================
    
    def read_coils(self, start_address: int, count: int) -> Optional[List[bool]]:
        """Read coils (FC01)"""
        with self._lock:
            self.stats.read_coils += 1
            
            # Validate range
            if not self._validate_coil_range(start_address, count):
                logger.warning(f"Coil read out of range: {start_address}+{count}")
                return None
            
            # Read values
            values = []
            for addr in range(start_address, start_address + count):
                values.append(self._coils.get(addr, False))
            
            logger.debug(f"Read {count} coils from {start_address}")
            return values
    
    def write_single_coil(self, address: int, value: bool) -> bool:
        """Write single coil (FC05)"""
        with self._lock:
            self.stats.write_single_coil += 1
            
            # Validate address
            if address not in self._coils:
                logger.warning(f"Coil write to invalid address: {address}")
                return False
            
            # Write value
            self._coils[address] = value
            self._notify_change('coil', address, value)
            
            logger.debug(f"Wrote coil {address} = {value}")
            return True
    
    def write_multiple_coils(self, start_address: int, values: List[bool]) -> bool:
        """Write multiple coils (FC15)"""
        with self._lock:
            self.stats.write_multiple_coils += 1
            
            # Validate range
            if not self._validate_coil_range(start_address, len(values)):
                logger.warning(f"Coil write out of range: {start_address}+{len(values)}")
                return False
            
            # Write values
            for i, value in enumerate(values):
                addr = start_address + i
                self._coils[addr] = value
                self._notify_change('coil', addr, value)
            
            logger.debug(f"Wrote {len(values)} coils from {start_address}")
            return True
    
    def _validate_coil_range(self, start: int, count: int) -> bool:
        """Validate coil address range"""
        end = start + count - 1
        return (start >= self.config.coils_start and
                end < self.config.coils_start + self.config.coils_count)
    
    # ========================================================================
    # Discrete Input Operations (FC02)
    # ========================================================================
    
    def read_discrete_inputs(self, start_address: int, count: int) -> Optional[List[bool]]:
        """Read discrete inputs (FC02)"""
        with self._lock:
            self.stats.read_discrete_inputs += 1
            
            # Validate range
            if not self._validate_discrete_input_range(start_address, count):
                logger.warning(f"Discrete input read out of range: {start_address}+{count}")
                return None
            
            # Read values
            values = []
            for addr in range(start_address, start_address + count):
                values.append(self._discrete_inputs.get(addr, False))
            
            logger.debug(f"Read {count} discrete inputs from {start_address}")
            return values
    
    def set_discrete_input(self, address: int, value: bool):
        """Set discrete input value (internal API, not Modbus function)"""
        with self._lock:
            if address in self._discrete_inputs:
                self._discrete_inputs[address] = value
                self._notify_change('discrete_input', address, value)
                logger.debug(f"Set discrete input {address} = {value}")
    
    def _validate_discrete_input_range(self, start: int, count: int) -> bool:
        """Validate discrete input address range"""
        end = start + count - 1
        return (start >= self.config.discrete_inputs_start and
                end < self.config.discrete_inputs_start + self.config.discrete_inputs_count)
    
    # ========================================================================
    # Input Register Operations (FC04)
    # ========================================================================
    
    def read_input_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """Read input registers (FC04)"""
        with self._lock:
            self.stats.read_input_registers += 1
            
            # Validate range
            if not self._validate_input_register_range(start_address, count):
                logger.warning(f"Input register read out of range: {start_address}+{count}")
                return None
            
            # Read values
            values = []
            for addr in range(start_address, start_address + count):
                values.append(self._input_registers.get(addr, 0))
            
            logger.debug(f"Read {count} input registers from {start_address}")
            return values
    
    def set_input_register(self, address: int, value: int):
        """Set input register value (internal API, not Modbus function)"""
        with self._lock:
            if address in self._input_registers:
                # Clamp to 16-bit range
                value = max(0, min(0xFFFF, value))
                self._input_registers[address] = value
                self._notify_change('input_register', address, value)
                logger.debug(f"Set input register {address} = {value}")
    
    def _validate_input_register_range(self, start: int, count: int) -> bool:
        """Validate input register address range"""
        end = start + count - 1
        return (start >= self.config.input_registers_start and
                end < self.config.input_registers_start + self.config.input_registers_count)
    
    # ========================================================================
    # Holding Register Operations (FC03, FC06, FC16)
    # ========================================================================
    
    def read_holding_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """Read holding registers (FC03)"""
        with self._lock:
            self.stats.read_holding_registers += 1
            
            # Validate range
            if not self._validate_holding_register_range(start_address, count):
                logger.warning(f"Holding register read out of range: {start_address}+{count}")
                return None
            
            # Read values
            values = []
            for addr in range(start_address, start_address + count):
                values.append(self._holding_registers.get(addr, 0))
            
            logger.debug(f"Read {count} holding registers from {start_address}")
            return values
    
    def write_single_register(self, address: int, value: int) -> bool:
        """Write single holding register (FC06)"""
        with self._lock:
            self.stats.write_single_register += 1
            
            # Validate address
            if address not in self._holding_registers:
                logger.warning(f"Holding register write to invalid address: {address}")
                return False
            
            # Clamp to 16-bit range
            value = max(0, min(0xFFFF, value))
            
            # Write value
            self._holding_registers[address] = value
            self._notify_change('holding_register', address, value)
            
            logger.debug(f"Wrote holding register {address} = {value}")
            return True
    
    def write_multiple_registers(self, start_address: int, values: List[int]) -> bool:
        """Write multiple holding registers (FC16)"""
        with self._lock:
            self.stats.write_multiple_registers += 1
            
            # Validate range
            if not self._validate_holding_register_range(start_address, len(values)):
                logger.warning(f"Holding register write out of range: {start_address}+{len(values)}")
                return False
            
            # Write values
            for i, value in enumerate(values):
                addr = start_address + i
                # Clamp to 16-bit range
                value = max(0, min(0xFFFF, value))
                self._holding_registers[addr] = value
                self._notify_change('holding_register', addr, value)
            
            logger.debug(f"Wrote {len(values)} holding registers from {start_address}")
            return True
    
    def _validate_holding_register_range(self, start: int, count: int) -> bool:
        """Validate holding register address range"""
        end = start + count - 1
        return (start >= self.config.holding_registers_start and
                end < self.config.holding_registers_start + self.config.holding_registers_count)
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def reset_memory(self):
        """Reset all memory to initial values"""
        with self._lock:
            self._initialize_memory()
            logger.info("Simulator memory reset")
    
    def reset_stats(self):
        """Reset statistics"""
        with self._lock:
            self.stats.reset()
            logger.info("Simulator statistics reset")
    
    def get_memory_snapshot(self) -> dict:
        """Get snapshot of all memory"""
        with self._lock:
            return {
                'coils': dict(self._coils),
                'discrete_inputs': dict(self._discrete_inputs),
                'input_registers': dict(self._input_registers),
                'holding_registers': dict(self._holding_registers)
            }
    
    def load_memory_snapshot(self, snapshot: dict):
        """Load memory from snapshot"""
        with self._lock:
            if 'coils' in snapshot:
                self._coils.update(snapshot['coils'])
            if 'discrete_inputs' in snapshot:
                self._discrete_inputs.update(snapshot['discrete_inputs'])
            if 'input_registers' in snapshot:
                self._input_registers.update(snapshot['input_registers'])
            if 'holding_registers' in snapshot:
                self._holding_registers.update(snapshot['holding_registers'])
            logger.info("Simulator memory loaded from snapshot")
    
    def import_from_csv(self, csv_data: str):
        """
        Import register values from CSV
        Format: type,address,value,name,description
        """
        import csv
        import io
        
        reader = csv.DictReader(io.StringIO(csv_data))
        count = 0
        
        with self._lock:
            for row in reader:
                try:
                    mem_type = row.get('type', '').lower()
                    address = int(row.get('address', 0))
                    value_str = row.get('value', '0')
                    
                    if mem_type == 'coil':
                        value = value_str.lower() in ['true', '1', 'on', 'yes']
                        if address in self._coils:
                            self._coils[address] = value
                            count += 1
                    
                    elif mem_type == 'discrete_input':
                        value = value_str.lower() in ['true', '1', 'on', 'yes']
                        if address in self._discrete_inputs:
                            self._discrete_inputs[address] = value
                            count += 1
                    
                    elif mem_type == 'input_register':
                        value = int(value_str)
                        if address in self._input_registers:
                            self._input_registers[address] = value
                            count += 1
                    
                    elif mem_type == 'holding_register':
                        value = int(value_str)
                        if address in self._holding_registers:
                            self._holding_registers[address] = value
                            count += 1
                
                except Exception as e:
                    logger.error(f"Error importing CSV row: {e}")
        
        logger.info(f"Imported {count} values from CSV")
        return count
    
    def export_to_csv(self) -> str:
        """Export all memory to CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['type', 'address', 'value', 'name', 'description'])
        
        with self._lock:
            # Coils
            for addr, value in sorted(self._coils.items()):
                writer.writerow(['coil', addr, 1 if value else 0, f'Coil_{addr}', ''])
            
            # Discrete Inputs
            for addr, value in sorted(self._discrete_inputs.items()):
                writer.writerow(['discrete_input', addr, 1 if value else 0, 
                               f'DI_{addr}', ''])
            
            # Input Registers
            for addr, value in sorted(self._input_registers.items()):
                writer.writerow(['input_register', addr, value, f'IR_{addr}', ''])
            
            # Holding Registers
            for addr, value in sorted(self._holding_registers.items()):
                writer.writerow(['holding_register', addr, value, f'HR_{addr}', ''])
        
        return output.getvalue()
    
    def get_stats_summary(self) -> str:
        """Get human-readable statistics summary"""
        with self._lock:
            uptime = (datetime.now() - self.stats.started_at).total_seconds() if self.stats.started_at else 0
            
            return f"""
Modbus RTU Simulator Statistics
================================
Slave Address: {self.config.slave_address}
Uptime: {uptime:.1f} seconds
Last Request: {self.stats.last_request_at or 'Never'}

Total Requests: {self.stats.total_requests}
Successful: {self.stats.successful_responses}
Exceptions: {self.stats.exception_responses}
Broadcast: {self.stats.broadcast_requests}
Invalid: {self.stats.invalid_requests}

Function Code Breakdown:
  Read Coils (01): {self.stats.read_coils}
  Read Discrete Inputs (02): {self.stats.read_discrete_inputs}
  Read Holding Registers (03): {self.stats.read_holding_registers}
  Read Input Registers (04): {self.stats.read_input_registers}
  Write Single Coil (05): {self.stats.write_single_coil}
  Write Single Register (06): {self.stats.write_single_register}
  Write Multiple Coils (15): {self.stats.write_multiple_coils}
  Write Multiple Registers (16): {self.stats.write_multiple_registers}

Memory Usage:
  Coils: {len(self._coils)}
  Discrete Inputs: {len(self._discrete_inputs)}
  Input Registers: {len(self._input_registers)}
  Holding Registers: {len(self._holding_registers)}
"""
