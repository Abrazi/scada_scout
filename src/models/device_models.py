from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any
from datetime import datetime

class DeviceType(Enum):
    IEC104_RTU = "IEC 60870-5-104 RTU"
    IEC61850_IED = "IEC 61850 IED"
    UNKNOWN = "Unknown"

class SignalType(Enum):
    ANALOG = "Analog"
    BINARY = "Binary"
    DOUBLE_BINARY = "Double Binary"
    COUNTER = "Counter"
    COMMAND = "Command"

    TIMESTAMP = "Timestamp"
    STATE = "State/Enum"

class SignalQuality(Enum):
    GOOD = "Good"
    INVALID = "Invalid"
    NOT_CONNECTED = "Not Connected"
    BLOCKED = "Blocked"

@dataclass
class Signal:
    """Represents a single data point (Telemetry)."""
    name: str
    address: str  # IOA for 104, ObjectRef for 61850
    signal_type: Any = None # Allow None/String during discovery
    value: Any = None
    quality: SignalQuality = SignalQuality.NOT_CONNECTED
    timestamp: Optional[datetime] = None
    description: str = ""
    access: str = "RO" 
    fc: str = "" # Functional Constraint
    enum_map: Dict[int, str] = field(default_factory=dict) # Mapping for integer values
    error: str = "" # Error message if read/write failed

@dataclass
class Node:
    """Represents a Logical Node or Grouping."""
    name: str
    description: str = ""
    signals: List[Signal] = field(default_factory=list)
    children: List['Node'] = field(default_factory=list)

@dataclass
class DeviceConfig:
    """Configuration required to connect to a device."""
    name: str
    ip_address: str
    port: int
    device_type: DeviceType = DeviceType.IEC61850_IED
    enabled: bool = True
    scd_file_path: Optional[str] = None
    use_scd_discovery: bool = True # Prefer SCD by default if available
    # Protocol specific extras (e.g. Common Address for 104)
    protocol_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Device:
    """Runtime representation of a connected Device."""
    config: DeviceConfig
    connected: bool = False
    root_node: Optional[Node] = None
    last_update: Optional[datetime] = None
