# Modbus RTU Architecture Design

## Executive Summary

This document describes the architecture for adding comprehensive Modbus RTU support to SCADA Scout, including master/slave modes, multiple transport options (RS-485, USB, RTU-over-TCP), simulation capabilities, and full compliance with the Modbus RTU specification.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SCADA Scout Application                     │
├─────────────────────────────────────────────────────────────────┤
│                         UI Layer (PySide6)                       │
│  - ModbusRTUConnectionDialog                                    │
│  - Device Explorer (shows RTU devices)                          │
│  - Register/Coil Editor                                         │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                    Device Manager Layer                          │
│  - DeviceManager / DeviceManagerCore                            │
│  - Protocol instantiation                                       │
│  - Event routing                                                │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                   Protocol Adapter Layer                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         ModbusRTUMasterAdapter (BaseProtocol)            │  │
│  │  - Master role implementation                            │  │
│  │  - Device discovery                                      │  │
│  │  - Signal reading/writing                                │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                              │
│  ┌────────────────▼─────────────────────────────────────────┐  │
│  │         ModbusRTUSlaveAdapter (BaseProtocol)             │  │
│  │  - Slave role implementation                             │  │
│  │  - Request processing                                    │  │
│  │  - Simulation mode                                       │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                              │
└───────────────────┼──────────────────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────────────────┐
│               Modbus RTU Protocol Core                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         ModbusRTUFrameHandler                            │  │
│  │  - Frame parsing and construction                        │  │
│  │  - CRC-16 validation                                     │  │
│  │  - Exception response handling                           │  │
│  │  - Function code implementations (1-16)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         ModbusRTUTiming                                  │  │
│  │  - Inter-frame gap calculation (3.5 char times)          │  │
│  │  - Timeout management                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         ModbusRTUSimulator                               │  │
│  │  - In-memory register storage                            │  │
│  │  - Coils, discrete inputs, input/holding registers       │  │
│  │  - Configurable behavior                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────┬──────────────────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────────────────┐
│                  Transport Abstraction Layer                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         BaseTransport (Abstract)                         │  │
│  │  - open() / close()                                      │  │
│  │  - send_frame() / receive_frame()                        │  │
│  │  - Timeout handling                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         SerialTransport                                  │  │
│  │  - pyserial for RS-485 / USB-RS-485                      │  │
│  │  - Configurable baud, parity, stop bits, data bits       │  │
│  │  - Cross-platform (Windows/Linux/macOS)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         RTUoverTCPTransport                              │  │
│  │  - TCP socket with RTU framing                           │  │
│  │  - No Modbus TCP/MBAP header                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### 1. Transport Layer

**Location:** `src/protocols/modbus/rtu/transport.py`

**Classes:**
- `BaseTransport` - Abstract interface for all transports
- `SerialTransport` - RS-485 / USB-to-RS-485 using pyserial
- `RTUoverTCPTransport` - RTU frames over TCP socket

**Responsibilities:**
- Low-level byte transmission/reception
- Timeout management
- Cross-platform serial port handling
- Transport-specific error handling

**Configuration:**
```python
@dataclass
class SerialConfig:
    port: str                    # e.g., COM3, /dev/ttyUSB0
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = 'N'           # N, E, O, M, S
    stopbits: float = 1.0       # 1, 1.5, 2
    timeout: float = 1.0
```

### 2. Frame Handler

**Location:** `src/protocols/modbus/rtu/frame_handler.py`

**Classes:**
- `ModbusRTUFrame` - Frame data structure
- `ModbusRTUFrameHandler` - Frame parsing/construction

**Responsibilities:**
- CRC-16 calculation and validation
- Frame parsing (slave_addr, function_code, data, crc)
- Frame construction for all function codes
- Exception response generation

**Function Codes Implemented:**
```
01 - Read Coils
02 - Read Discrete Inputs
03 - Read Holding Registers
04 - Read Input Registers
05 - Write Single Coil
06 - Write Single Register
07 - Read Exception Status
08 - Diagnostics
11 - Get Comm Event Counter
15 - Write Multiple Coils
16 - Write Multiple Registers
```

**Exception Codes:**
```
01 - Illegal Function
02 - Illegal Data Address
03 - Illegal Data Value
04 - Slave Device Failure
05 - Acknowledge
06 - Slave Device Busy
08 - Memory Parity Error
10 - Gateway Path Unavailable
11 - Gateway Target Device Failed to Respond
```

### 3. Timing Manager

**Location:** `src/protocols/modbus/rtu/timing.py`

**Class:** `ModbusRTUTiming`

**Responsibilities:**
- Calculate inter-frame gap (3.5 character times)
- Calculate character time based on baud rate
- Timeout calculation
- Silent interval detection

**Formula:**
```
char_time = (1 + data_bits + parity_bit + stop_bits) / baudrate
inter_frame_gap = 3.5 * char_time

For baudrates > 19200:
  Use fixed 1.75ms gap (as per spec)
```

### 4. Master Adapter

**Location:** `src/protocols/modbus/rtu/master_adapter.py`

**Class:** `ModbusRTUMasterAdapter(BaseProtocol)`

**Responsibilities:**
- Initiate Modbus requests
- Handle responses and timeouts
- Retry logic
- Device discovery (scan slave addresses)
- Signal reading/writing
- Broadcast support (address 0)

**Key Methods:**
```python
def connect() -> bool
def disconnect()
def discover() -> Node
def read_signal(signal: Signal) -> Signal
def write_signal(signal: Signal, value)
def read_coils(address: int, count: int) -> List[bool]
def read_holding_registers(address: int, count: int) -> List[int]
# ... etc for all function codes
```

### 5. Slave Adapter

**Location:** `src/protocols/modbus/rtu/slave_adapter.py`

**Class:** `ModbusRTUSlaveAdapter(BaseProtocol)`

**Responsibilities:**
- Listen for incoming requests
- Validate requests (CRC, address, function code)
- Process valid requests
- Generate responses or exceptions
- Handle broadcast requests (no response)
- Integration with simulator

**Request Processing Flow:**
```
1. Receive frame
2. Validate CRC
   - If invalid: discard, no response
3. Check slave address
   - If broadcast (0): process, no response
   - If mismatch: discard, no response
4. Validate function code
   - If invalid: send exception 01
5. Validate data address/range
   - If invalid: send exception 02
6. Validate data value
   - If invalid: send exception 03
7. Process request
   - If error: send exception 04
8. Send response
```

### 6. Simulator

**Location:** `src/protocols/modbus/rtu/simulator.py`

**Class:** `ModbusRTUSimulator`

**Responsibilities:**
- In-memory storage for all register types
- Configurable memory layout
- Editable values
- Event notifications on changes
- CSV/JSON import/export

**Data Structure:**
```python
class ModbusRTUSimulator:
    coils: Dict[int, bool]                  # 00001-09999
    discrete_inputs: Dict[int, bool]        # 10001-19999
    input_registers: Dict[int, int]         # 30001-39999
    holding_registers: Dict[int, int]       # 40001-49999
```

**Configuration:**
```python
@dataclass
class SimulatorConfig:
    slave_address: int = 1
    coils_start: int = 0
    coils_count: int = 100
    discrete_inputs_start: int = 0
    discrete_inputs_count: int = 100
    input_registers_start: int = 0
    input_registers_count: int = 100
    holding_registers_start: int = 0
    holding_registers_count: int = 100
```

### 7. Device Models Extension

**Location:** `src/models/device_models.py`

**Changes:**
```python
class DeviceType(Enum):
    # ... existing ...
    MODBUS_RTU_MASTER = "Modbus RTU Master"
    MODBUS_RTU_SLAVE = "Modbus RTU Slave"
    MODBUS_RTU_SIMULATOR = "Modbus RTU Simulator"

@dataclass
class DeviceConfig:
    # ... existing fields ...
    
    # RTU-specific fields
    rtu_transport: str = "serial"  # serial, rtu_over_tcp
    serial_port: str = ""
    serial_baudrate: int = 9600
    serial_bytesize: int = 8
    serial_parity: str = 'N'
    serial_stopbits: float = 1.0
    serial_timeout: float = 1.0
    rtu_slave_address: int = 1
    rtu_mode: str = "master"  # master, slave, simulator
    rtu_simulator_config: Optional[Dict] = None
```

### 8. UI Components

**Location:** `src/ui/dialogs/modbus_rtu_connection_dialog.py`

**Class:** `ModbusRTUConnectionDialog`

**Features:**
- Transport selection (RS-485, USB, RTU-over-TCP)
- Serial port enumeration (pyserial list_ports)
- Baud rate dropdown (standard rates + custom)
- Data bits, parity, stop bits selectors
- Timeout configuration
- Mode selection (Master/Slave/Simulator)
- Test connection button
- Simulator configuration button

**Location:** `src/ui/widgets/modbus_rtu_simulator_widget.py`

**Class:** `ModbusRTUSimulatorWidget`

**Features:**
- Tabbed interface (Coils, Discrete Inputs, Input Registers, Holding Registers)
- Table view with address, value, name, description
- In-place editing
- Bulk import from CSV
- Live update indicators
- Export to CSV/JSON

## Integration with Existing System

### DeviceManager Integration

**Location:** `src/core/device_manager_core.py`

**Changes:**
```python
def _create_protocol(self, config: DeviceConfig):
    # ... existing code ...
    elif config.device_type == DeviceType.MODBUS_RTU_MASTER:
        from src.protocols.modbus.rtu.master_adapter import ModbusRTUMasterAdapter
        return ModbusRTUMasterAdapter(config, self.event_logger)
    
    elif config.device_type == DeviceType.MODBUS_RTU_SLAVE:
        from src.protocols.modbus.rtu.slave_adapter import ModbusRTUSlaveAdapter
        return ModbusRTUSlaveAdapter(config, self.event_logger)
    
    elif config.device_type == DeviceType.MODBUS_RTU_SIMULATOR:
        from src.protocols.modbus.rtu.slave_adapter import ModbusRTUSlaveAdapter
        return ModbusRTUSlaveAdapter(config, self.event_logger, simulation=True)
```

### Event Flow

**Signal Updates (Master Mode):**
```
1. UpdateEngine triggers polling
2. WatchListManager requests signal read
3. ModbusRTUMasterAdapter sends request frame
4. Transport sends bytes
5. Transport receives response
6. Frame handler parses and validates
7. Adapter updates signal value
8. Callback notifies DeviceManager
9. signal_updated event emitted
10. UI updates
```

**Request Handling (Slave Mode):**
```
1. SlaveAdapter listens on transport
2. Frame received
3. Frame handler validates CRC
4. Simulator processes request
5. Response frame constructed
6. Transport sends response
7. EventLogger records transaction
```

## Testing Strategy

### Unit Tests

**Location:** `tests/protocols/modbus/rtu/`

**Test Files:**
- `test_transport.py` - Transport layer
- `test_frame_handler.py` - Frame parsing/CRC
- `test_timing.py` - Inter-frame gap calculations
- `test_simulator.py` - Simulator logic
- `test_master_adapter.py` - Master operations
- `test_slave_adapter.py` - Slave operations

### Integration Tests

**Location:** `tests/integration/`

**Test File:** `test_modbus_rtu_integration.py`

**Test Scenarios:**
1. **Simulation Loop Test**
   - Start simulator slave
   - Connect master to simulator
   - Test all function codes
   - Verify responses
   - Check CRC validation
   - Test exception responses

2. **External Device Test**
   - Connect to real Modbus RTU device
   - Execute reads/writes
   - Validate data integrity

3. **Cross-Mode Test**
   - Slave receives from external master
   - Master reads from external slave
   - Verify interoperability

4. **Error Handling Test**
   - Invalid CRC
   - Invalid function codes
   - Address out of range
   - Timeout scenarios
   - Broadcast handling

### Automated Test Script

**Location:** `tests/modbus_rtu_automated_test.py`

```python
def test_all_function_codes():
    """
    Comprehensive test of all Modbus RTU function codes
    """
    # Start simulator
    simulator = start_simulator(slave_addr=1)
    
    # Connect master
    master = connect_master()
    
    # Test FC01 - Read Coils
    result = master.read_coils(0, 10)
    assert len(result) == 10
    
    # Test FC02 - Read Discrete Inputs
    result = master.read_discrete_inputs(0, 10)
    assert len(result) == 10
    
    # Test FC03 - Read Holding Registers
    result = master.read_holding_registers(0, 10)
    assert len(result) == 10
    
    # Test FC04 - Read Input Registers
    result = master.read_input_registers(0, 10)
    assert len(result) == 10
    
    # Test FC05 - Write Single Coil
    master.write_coil(0, True)
    result = master.read_coils(0, 1)
    assert result[0] == True
    
    # Test FC06 - Write Single Register
    master.write_register(0, 12345)
    result = master.read_holding_registers(0, 1)
    assert result[0] == 12345
    
    # Test FC15 - Write Multiple Coils
    master.write_coils(0, [True, False, True])
    result = master.read_coils(0, 3)
    assert result == [True, False, True]
    
    # Test FC16 - Write Multiple Registers
    master.write_registers(0, [100, 200, 300])
    result = master.read_holding_registers(0, 3)
    assert result == [100, 200, 300]
    
    # Test CRC validation
    test_crc_validation(master, simulator)
    
    # Test exception responses
    test_exceptions(master, simulator)
    
    # Test broadcast
    test_broadcast(master, simulator)
```

## Cross-Platform Considerations

### Serial Port Access

**Windows:**
- Ports: `COM1`, `COM2`, etc.
- Drivers: Usually automatic for USB-RS-485
- Admin rights: Not required for standard COM ports

**Linux:**
- Ports: `/dev/ttyUSB0`, `/dev/ttyS0`, etc.
- Permissions: User must be in `dialout` group
- udev rules may be needed for USB devices

**macOS:**
- Ports: `/dev/tty.usbserial-XXXX`, `/dev/cu.usbserial-XXXX`
- Drivers: May require FTDI/Prolific drivers
- Use `/dev/cu.*` for opening (not `/dev/tty.*`)

**Port Enumeration:**
```python
import serial.tools.list_ports

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [(p.device, p.description) for p in ports]
```

### Timing Precision

- Use `time.perf_counter()` for high-resolution timing
- For very high baud rates (>115200), OS timer resolution may be limiting factor
- On Windows, can use `timeBeginPeriod(1)` for better timer resolution

### Thread Safety

- Use threading.Lock for shared simulator data
- Master/Slave adapters should handle concurrent access
- UI updates must use Qt signals (thread-safe)

## Performance Considerations

### Optimization Strategies

1. **Frame Buffer Pre-allocation**
   - Reuse byte buffers to reduce GC pressure

2. **CRC Table Lookup**
   - Pre-computed CRC table for fast validation

3. **Async I/O** (Future Enhancement)
   - Use `asyncio` with `pyserial-asyncio`
   - Non-blocking serial operations

4. **Batching**
   - Group multiple register reads into single requests
   - Use FC03/FC04 multi-register reads efficiently

5. **Caching**
   - Cache recently read values
   - Configurable cache TTL

## Dependencies

**Required:**
- `pyserial>=3.5` - Serial port communication
- `PySide6>=6.5.0` - UI framework (existing)

**Optional:**
- `pyserial-asyncio>=0.6` - Async serial I/O (future)

**Update requirements.txt:**
```
pyserial>=3.5
```

## Configuration Files

### Device Configuration (JSON)

```json
{
  "name": "RTU Device 1",
  "device_type": "MODBUS_RTU_MASTER",
  "rtu_transport": "serial",
  "serial_port": "COM3",
  "serial_baudrate": 9600,
  "serial_bytesize": 8,
  "serial_parity": "N",
  "serial_stopbits": 1.0,
  "serial_timeout": 1.0,
  "rtu_slave_address": 1,
  "register_maps": [
    {
      "start_address": 0,
      "count": 10,
      "function_code": 3,
      "data_type": "UINT16",
      "name_prefix": "HR_",
      "poll_rate": 1000
    }
  ]
}
```

### Simulator Configuration (JSON)

```json
{
  "name": "Simulated RTU Slave",
  "device_type": "MODBUS_RTU_SIMULATOR",
  "rtu_transport": "serial",
  "serial_port": "COM4",
  "rtu_slave_address": 1,
  "rtu_simulator_config": {
    "coils": {"start": 0, "count": 100, "initial_value": false},
    "discrete_inputs": {"start": 0, "count": 100, "initial_value": false},
    "input_registers": {"start": 0, "count": 100, "initial_value": 0},
    "holding_registers": {"start": 0, "count": 100, "initial_value": 0}
  }
}
```

## Security Considerations

### Physical Security
- RS-485 has no encryption - physical security of bus is critical
- Bus can be monitored/injected by any connected device

### Access Control
- Application should restrict which function codes are allowed
- Implement address range restrictions
- Logging of all write operations

### Validation
- Strict validation of all input data
- Range checking before writing
- Prevent buffer overflows in frame handling

## Future Enhancements

1. **ASCII Mode Support** - Modbus ASCII in addition to RTU
2. **Protocol Gateway** - Modbus RTU ↔ Modbus TCP bridging
3. **Packet Capture** - Built-in protocol analyzer with Wireshark export
4. **Performance Monitoring** - RTT, error rates, throughput graphs
5. **Advanced Diagnostics** - FC08 diagnostics implementation
6. **Multi-Master Support** - Token-passing or master arbitration
7. **Hot-Swap Detection** - Automatic device reconnection
8. **Scripting API** - Python API for automation

## Conclusion

This architecture provides a comprehensive, production-quality Modbus RTU implementation that:
- ✅ Supports Master and Slave modes
- ✅ Works with RS-485, USB-RS-485, and RTU-over-TCP
- ✅ Implements all required function codes
- ✅ Provides full simulation capability
- ✅ Maintains strict Modbus RTU compliance
- ✅ Integrates cleanly with existing SCADA Scout architecture
- ✅ Is fully testable and cross-platform
- ✅ Follows Python best practices

The implementation will be modular, maintainable, and extensible for future enhancements.
