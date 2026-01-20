from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any
from datetime import datetime

class DeviceType(Enum):
    IEC104_RTU = "IEC 60870-5-104 RTU"
    IEC61850_IED = "IEC 61850 IED"
    IEC61850_SERVER = "IEC 61850 Simulator (Server)"
    MODBUS_TCP = "Modbus TCP"
    MODBUS_SERVER = "Modbus Slave Server"
    UNKNOWN = "Unknown"

class SignalType(Enum):
    ANALOG = "Analog"
    BINARY = "Binary"
    DOUBLE_BINARY = "Double Binary"
    COUNTER = "Counter"
    COMMAND = "Command"
    TIMESTAMP = "Timestamp"
    STATE = "State/Enum"
    # Modbus-specific types
    HOLDING_REGISTER = "Holding Register"
    INPUT_REGISTER = "Input Register"
    COIL = "Coil"
    DISCRETE_INPUT = "Discrete Input"

class SignalQuality(Enum):
    GOOD = "Good"
    INVALID = "Invalid"
    NOT_CONNECTED = "Not Connected"
    BLOCKED = "Blocked"

class ModbusDataType(Enum):
    """Data types for Modbus register interpretation"""
    INT16 = "Signed 16-bit"
    UINT16 = "Unsigned 16-bit"
    HEX16 = "Hex 16-bit"
    BINARY16 = "Binary 16-bit"
    INT32 = "Signed 32-bit"
    UINT32 = "Unsigned 32-bit"
    FLOAT32 = "Float 32-bit"
    INT64 = "Signed 64-bit"
    UINT64 = "Unsigned 64-bit"
    FLOAT64 = "Double 64-bit"
    STRING = "ASCII (Packed)"
    BOOL = "Boolean"
    BIT = "Bit"
    BCD16 = "BCD 16-bit"
    BCD32 = "BCD 32-bit"

class ModbusEndianness(Enum):
    """Byte and word order for multi-register values (Standard naming)"""
    BIG_ENDIAN = "Big-endian (ABCD)"
    LITTLE_ENDIAN = "Little-endian (CDAB)"      # Word Swap
    BIG_ENDIAN_BYTE_SWAP = "Big-endian byte swap (BADC)"
    LITTLE_ENDIAN_BYTE_SWAP = "Little-endian byte swap (DCBA)"
    
    # Aliases for internal use
    BIG_BIG = "ABCD"
    LITTLE_LITTLE = "DCBA"
    CDAB = "CDAB"
    BADC = "BADC"

class RTTState(Enum):
    IDLE = "Idle"
    SENT = "Sent"
    RECEIVED = "Received"
    TIMEOUT = "Timeout"

@dataclass
class Signal:
    """Represents a single data point (Telemetry)."""
    name: str
    address: str  # IOA for 104, ObjectRef for 61850, "unit:func:addr" for Modbus
    unique_address: str = ""  # Global unique tag address: "Device::Address[#n]"
    signal_type: Any = None
    value: Any = None
    quality: SignalQuality = SignalQuality.NOT_CONNECTED
    timestamp: Optional[datetime] = None
    last_changed: Optional[datetime] = None
    description: str = ""
    access: str = "RO"  # RO, WO, RW
    fc: str = ""  # Functional Constraint (IEC 61850)
    enum_map: Dict[int, str] = field(default_factory=dict)
    error: str = ""
    
    # RTT Tracking
    last_rtt: float = -1.0
    rtt_state: RTTState = RTTState.IDLE
    
    # Modbus-specific fields
    modbus_data_type: Optional[ModbusDataType] = None
    modbus_scale: float = 1.0
    modbus_offset: float = 0.0
    modbus_endianness: ModbusEndianness = ModbusEndianness.BIG_BIG

    def __setattr__(self, name, value):
        if name == 'value':
            if hasattr(self, 'value') and self.value != value:
                super().__setattr__('last_changed', datetime.now())
        super().__setattr__(name, value)

@dataclass
class Node:
    """Represents a Logical Node or Grouping."""
    name: str
    description: str = ""
    signals: List[Signal] = field(default_factory=list)
    children: List['Node'] = field(default_factory=list)

@dataclass
class ModbusSignalMapping:
    """Definition for mapping higher-level values to raw registers on a slave"""
    address: int
    name: str = ""
    description: str = ""
    data_type: ModbusDataType = ModbusDataType.UINT16
    endianness: ModbusEndianness = ModbusEndianness.BIG_ENDIAN
    scale: float = 1.0
    offset: float = 0.0
    writable: bool = True
    # For strings
    string_length: int = 10 

    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'name': self.name,
            'description': self.description,
            'data_type': self.data_type.value,
            'endianness': self.endianness.value,
            'scale': self.scale,
            'offset': self.offset,
            'writable': self.writable,
            'string_length': self.string_length
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModbusSignalMapping':
        # Handle Enum conversion
        data_type = ModbusDataType.UINT16
        for dt in ModbusDataType:
            if dt.value == data.get('data_type'):
                data_type = dt
                break
        
        endianness = ModbusEndianness.BIG_ENDIAN
        for en in ModbusEndianness:
            if en.value == data.get('endianness'):
                endianness = en
                break
                
        return cls(
            address=data['address'],
            name=data.get('name', ""),
            description=data.get('description', ""),
            data_type=data_type,
            endianness=endianness,
            scale=data.get('scale', 1.0),
            offset=data.get('offset', 0.0),
            writable=data.get('writable', True),
            string_length=data.get('string_length', 10)
        )

@dataclass
class ModbusRegisterMap:
    """Configuration for Modbus register mapping"""
    start_address: int
    count: int
    function_code: int  # 1, 2, 3, 4
    data_type: ModbusDataType
    name_prefix: str = ""
    description: str = ""
    scale: float = 1.0
    offset: float = 0.0
    endianness: ModbusEndianness = ModbusEndianness.BIG_BIG

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_address': self.start_address,
            'count': self.count,
            'function_code': self.function_code,
            'data_type': self.data_type.value,
            'name_prefix': self.name_prefix,
            'description': self.description,
            'scale': self.scale,
            'offset': self.offset,
            'endianness': self.endianness.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModbusRegisterMap':
        # Handle Enum conversion
        data_type = ModbusDataType.UINT16
        for dt in ModbusDataType:
            if dt.value == data.get('data_type'):
                data_type = dt
                break
        
        endianness = ModbusEndianness.BIG_BIG
        for en in ModbusEndianness:
            if en.value == data.get('endianness'):
                endianness = en
                break
                
        return cls(
            start_address=data['start_address'],
            count=data['count'],
            function_code=data['function_code'],
            data_type=data_type,
            name_prefix=data.get('name_prefix', ""),
            description=data.get('description', ""),
            scale=data.get('scale', 1.0),
            offset=data.get('offset', 0.0),
            endianness=endianness
        )

@dataclass
class SlaveRegisterBlock:
    """Defines a contiguous block of registers for the Modbus Slave."""
    name: str
    register_type: str  # "coils", "discrete", "holding", "input"
    start_address: int
    count: int
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'register_type': self.register_type,
            'start_address': self.start_address,
            'count': self.count,
            'description': self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SlaveRegisterBlock':
        return cls(
            name=data['name'],
            register_type=data.get('register_type', 'holding'),
            start_address=data['start_address'],
            count=data['count'],
            description=data.get('description', "")
        )

@dataclass
class DeviceConfig:
    """Configuration required to connect to a device."""
    name: str
    ip_address: str
    port: int
    folder: str = ""
    description: str = ""
    device_type: DeviceType = DeviceType.IEC61850_IED
    enabled: bool = True
    scd_file_path: Optional[str] = None
    use_scd_discovery: bool = True
    protocol_params: Dict[str, Any] = field(default_factory=dict)
    polling_enabled: bool = False
    poll_interval: float = 1.0  # seconds
    
    # Modbus-specific parameters
    modbus_unit_id: int = 1
    modbus_timeout: float = 3.0
    modbus_register_maps: List[ModbusRegisterMap] = field(default_factory=list)
    modbus_slave_mappings: List[ModbusSignalMapping] = field(default_factory=list)
    modbus_slave_blocks: List[SlaveRegisterBlock] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'ip_address': self.ip_address,
            'port': self.port,
            'folder': self.folder,
            'description': self.description,
            'device_type': self.device_type.value,
            'enabled': self.enabled,
            'scd_file_path': self.scd_file_path,
            'use_scd_discovery': self.use_scd_discovery,
            'protocol_params': self.protocol_params,
            'polling_enabled': self.polling_enabled,
            'poll_interval': self.poll_interval,
            'modbus_unit_id': self.modbus_unit_id,
            'modbus_timeout': self.modbus_timeout,
            'modbus_register_maps': [rm.to_dict() for rm in self.modbus_register_maps],
            'modbus_slave_mappings': [sm.to_dict() for sm in self.modbus_slave_mappings],
            'modbus_slave_blocks': [sb.to_dict() for sb in self.modbus_slave_blocks]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceConfig':
        # Handle Enum conversion
        device_type = DeviceType.UNKNOWN
        for dt in DeviceType:
            if dt.value == data.get('device_type'):
                device_type = dt
                break
        
        config = cls(
            name=data['name'],
            ip_address=data['ip_address'],
            port=data['port'],
            folder=data.get('folder', ""),
            description=data.get('description', ""),
            device_type=device_type,
            enabled=data.get('enabled', True),
            scd_file_path=data.get('scd_file_path'),
            use_scd_discovery=data.get('use_scd_discovery', True),
            protocol_params=data.get('protocol_params', {}),
            polling_enabled=data.get('polling_enabled', False),
            poll_interval=data.get('poll_interval', 1.0),
            modbus_unit_id=data.get('modbus_unit_id', 1),
            modbus_timeout=data.get('modbus_timeout', 3.0)
        )
        
        # Load nested objects
        config.modbus_register_maps = [
            ModbusRegisterMap.from_dict(rm) for rm in data.get('modbus_register_maps', [])
        ]
        config.modbus_slave_mappings = [
            ModbusSignalMapping.from_dict(sm) for sm in data.get('modbus_slave_mappings', [])
        ]
        config.modbus_slave_blocks = [
            SlaveRegisterBlock.from_dict(sb) for sb in data.get('modbus_slave_blocks', [])
        ]
        
        return config

@dataclass
class Device:
    """Runtime representation of a connected Device."""
    config: DeviceConfig
    connected: bool = False
    root_node: Optional[Node] = None
    last_update: Optional[datetime] = None
