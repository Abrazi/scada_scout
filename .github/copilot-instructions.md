# SCADA Scout - AI Coding Agent Instructions

## Architecture Overview

SCADA Scout is a cross-platform SCADA protocol analyzer built with Python/PySide6. The architecture follows a layered design:

- **UI Layer**: PySide6-based GUI (`src/ui/`) with main window, dialogs, and widgets
- **Core Layer**: Framework-agnostic business logic (`src/core/`) including DeviceManager, UpdateEngine, and ProtocolGateway
- **Protocol Layer**: Protocol implementations (`src/protocols/`) inheriting from BaseProtocol
- **Model Layer**: Data structures (`src/models/`) for devices, signals, and configurations

Key architectural patterns:
- **Event-driven communication**: Uses EventEmitter for core events, Qt signals for UI integration
- **Adapter pattern**: DeviceManager provides Qt signals, delegates to DeviceManagerCore
- **Callback-based async updates**: Protocols notify data changes via registered callbacks
- **Periodic polling**: UpdateEngine + WatchListManager handle timed signal reads

## Critical Workflows

### Development Setup
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

### IEC 61850 Dependencies
- Requires native `libiec61850` library installed system-wide
- Uses pure Python ctypes bindings (no SWIG/compilation)
- See `IEC61850_SETUP.md` for platform-specific installation
- Test with `python -c "from src.protocols.iec61850 import iec61850_wrapper; print(iec61850_wrapper.is_library_loaded())"`

### Running the Application
```bash
# GUI mode
python src/main.py

# Headless testing
python headless_test.py
```

### Protocol Testing
- Use `DeviceManagerCore` directly for headless testing (bypasses Qt dependencies)
- Mock devices with `DeviceConfig` and `DeviceType` enums
- Listen to events: `manager.on("signal_updated", callback)`

## Project Conventions

### Device Management
- Devices added via `DeviceManager.add_device(DeviceConfig)`
- Each device gets a protocol adapter instantiated automatically
- Discovery happens immediately on add (offline via SCD or online connect)
- Signals accessed by `device_name::signal_address` format

### Signal Updates
- Signals are dataclasses with `name`, `address`, `value`, `quality`, `timestamp`
- Quality enum: GOOD, INVALID, NOT_CONNECTED, BLOCKED
- Updates flow: Protocol → callback → DeviceManager.signal_updated → UI/Gateway

### Modbus Specifics
- Register addresses: `unit:function:address` (e.g., `1:3:40001`)
- Data types: INT16, UINT16, FLOAT32, etc. with endianness control
- Endianness: BIG_ENDIAN (ABCD), LITTLE_ENDIAN (CDAB), etc.

### IEC 61850 Specifics
- Object references as addresses (e.g., `IED1/LLN0$ST$Mod$stVal`)
- Functional constraints: ST, MX, CO, etc.
- Control objects use `ControlModel` and `ControlState`

### Protocol Gateway
- Bridges protocols (e.g., IEC61850 → Modbus slave)
- Mappings defined with `GatewayMapping` dataclass
- Listens to `device_manager.signal_updated` for source data

### Event Logging
- Use `EventLogger` for user-visible events (not just print statements)
- Methods: `info()`, `warning()`, `error()`, `transaction()`
- Connected to UI event log widget automatically

### Configuration Persistence
- Devices saved to `devices.json` automatically on changes
- Load on startup via `DeviceManager.load_configuration()`

## Key Files & Directories

- `src/main.py`: GUI entry point, initializes DeviceManager/AppController/MainWindow
- `src/core/device_manager.py`: Qt adapter for DeviceManagerCore
- `src/core/device_manager_core.py`: Core device lifecycle management
- `src/core/app_controller.py`: Orchestrates UI-core interaction
- `src/core/update_engine.py`: Periodic timer for polling
- `src/core/watch_list_manager.py`: Manages polled signals with RTT tracking
- `src/core/protocol_gateway.py`: Cross-protocol data bridging
- `src/protocols/base_protocol.py`: Abstract protocol interface
- `src/models/device_models.py`: Core data structures (Device, Signal, etc.)
- `headless_test.py`: Framework-agnostic testing example
- `requirements.txt`: Python dependencies (PySide6, pymodbus, etc.)

## Common Patterns

### Adding a New Protocol
1. Create adapter inheriting `BaseProtocol`
2. Implement `connect()`, `disconnect()`, `discover()`, `read_signal()`
3. Set data callback in `__init__`: `protocol.set_data_callback(self._on_signal_update)`
4. Add to DeviceManagerCore._create_protocol() mapping

### Signal Reading
```python
# Synchronous read
signal = protocol.read_signal(existing_signal)

# Async updates via callback
def on_update(sig):
    self._callback(sig)  # Notify DeviceManager
protocol.set_data_callback(on_update)
```

### Device Connection Flow
1. `DeviceManager.add_device(config)` → instantiates protocol
2. `DeviceManager.connect_device(name)` → calls `protocol.connect()`
3. Protocol discovers model via `discover()` → builds Node/Signal tree
4. Updates flow via callback → `signal_updated` signal

### Testing Without GUI
```python
from src.core.device_manager_core import DeviceManagerCore
manager = DeviceManagerCore()
config = DeviceConfig(name="Test", ip_address="127.0.0.1", device_type=DeviceType.MODBUS_TCP)
device = manager.add_device(config)
manager.on("signal_updated", lambda name, sig: print(f"{name}: {sig.address} = {sig.value}"))
```

## Integration Points

- **PySide6**: GUI framework, use Qt signals/slots for UI updates
- **pymodbus**: Modbus TCP client/server, handles connection pooling
- **libiec61850**: Native C library, accessed via ctypes wrapper
- **scapy**: Packet capture for diagnostics (if implemented)
- **psutil**: System monitoring utilities

## Debugging Tips

- Enable logging: `logging.basicConfig(level=logging.INFO)`
- Check protocol connections: `protocol.connected` attribute
- Monitor signal updates: connect to `device_manager.signal_updated`
- IEC61850 issues: verify libiec61850 installation and library loading
- Modbus issues: check unit ID, register addresses, data type/endianness