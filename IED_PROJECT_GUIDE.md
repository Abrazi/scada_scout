# IED Project System - Complete Guide

## Overview

The IED Project System enables automatic instantiation of multiple IEC 61850 servers from SCD (Substation Configuration Description) files, with integrated PLC program generation and project persistence.

## Architecture

### Core Components

1. **SCDProjectLoader** (`src/core/scd_project_loader.py`)
   - Parses IEC 61850 SCD/ICD files
   - Extracts IED definitions with network configurations
   - Maps Communication section to IED IP addresses

2. **PLCProgramGenerator** (`src/core/plc_program_generator.py`)
   - Generates IEC 61131-3 Structured Text programs
   - Creates one program per IED device
   - Includes placeholders for user logic

3. **PLCRuntimeEngine** (`src/core/plc_runtime_engine.py`)
   - Executes PLC programs in dedicated threads
   - Cyclic execution with configurable scan time
   - Built-in functions for IED data access

4. **MSSProjectManager** (`src/core/mss_project_manager.py`)
   - Persists complete project state as .mss files
   - JSON-based format with all configuration
   - Supports save/load workflows

5. **IEDProjectOrchestrator** (`src/core/ied_project_orchestrator.py`)
   - High-level integration component
   - Coordinates all subsystems
   - Main entry point for workflows

### Integration Points

- **Device Manager**: Creates and manages IEC 61850 server instances
- **Protocol Adapters**: Uses existing IEC61850ServerAdapter
- **UI**: IEDProjectDialog provides user interface

## Workflow

### 1. Load SCD File

```python
from src.core.ied_project_orchestrator import IEDProjectOrchestrator

orchestrator = IEDProjectOrchestrator(device_manager)
orchestrator.load_from_scd("dubgg/DUBGG.scd", project_name="DUBGG")

# View extracted IEDs
for ied in orchestrator.ied_definitions:
    print(f"{ied.name}: {ied.network_config.ip_address}")
```

### 2. Instantiate IED Servers

```python
# Create servers with PLC programs
orchestrator.instantiate_all_ieds(
    auto_connect=True,  # Start servers immediately
    start_plc=True      # Start PLC runtime
)

# Each IED is now:
# - Registered in Device Explorer
# - Running as IEC 61850 server on configured IP
# - Has a generated PLC program running
```

### 3. Save Project

```python
# Save complete state as .mss file
orchestrator.save_project("DUBGG.mss")

# File contains:
# - SCD reference
# - All device configurations
# - PLC program associations
# - Runtime settings
```

### 4. Load Project

```python
# Restore complete project state
orchestrator.load_project("DUBGG.mss")

# All IEDs are restored:
# - Servers restarted
# - PLC programs reloaded
# - Network bindings restored
```

## MSS File Format

The .mss (Multi-Server Simulation) format is JSON-based:

```json
{
  "metadata": {
    "project_name": "DUBGG",
    "description": "Project loaded from DUBGG.scd",
    "scd_file_path": "dubgg/DUBGG.scd",
    "created": "2026-02-05T10:30:00",
    "modified": "2026-02-05T11:45:00",
    "version": "1.0"
  },
  "devices": [
    {
      "device_name": "IED1",
      "ied_name": "IED1",
      "ip_address": "192.168.1.10",
      "port": 102,
      "enabled": true,
      "auto_connect": true,
      "plc_program": "plc_programs/PRG_IED1.st"
    }
  ],
  "settings": {
    "auto_start_plc": true,
    "default_cycle_time_ms": 100,
    "auto_connect_on_load": true
  }
}
```

## PLC Programs

### Generated Structure

Each IED gets a PLC program in Structured Text (ST) format:

```
plc_programs/
├── PRG_IED1.st
├── PRG_IED2.st
└── PRG_IED3.st
```

### Program Template

```pascal
(* PLC PROGRAM: PRG_IED1 *)
PROGRAM PRG_IED1
VAR
    cycle_count: UDINT := 0;
    first_scan: BOOL := TRUE;
    ied_connected: BOOL := FALSE;
    
    (* User variables *)
    (* Add custom variables here *)
END_VAR

(* Initialization *)
IF first_scan THEN
    cycle_count := 0;
    first_scan := FALSE;
END_IF;

(* Main cyclic execution *)
cycle_count := cycle_count + 1;

(* USER LOGIC SECTION 1: Pre-Processing *)
(* Add logic here *)

(* USER LOGIC SECTION 2: Main Processing *)
(* Add control logic *)

(* USER LOGIC SECTION 3: Post-Processing *)
(* Add outputs and writes *)

END_PROGRAM
```

### Built-in Functions

Programs can use these functions to interact with IED data:

- `READ_IED_DATA(device, ref)` - Read data point
- `WRITE_IED_DATA(device, ref, value)` - Write data
- `WRITE_IED_CONTROL(device, ref, value)` - Send control command
- `SCADA_LOG(level, message)` - Log events
- `GET_DEVICE_STATUS(device)` - Check connection

## UI Usage

### Via Menu

1. **Connection** → **IED Project Manager...**
2. Select SCD file or MSS project
3. Preview extracted IEDs
4. Configure options:
   - Auto-connect servers
   - Auto-start PLC programs
5. Click **Create IED Servers**
6. Save as MSS project

### Via Dialog

The IEDProjectDialog provides:

- File browser for SCD/MSS files
- IED preview table with IP addresses
- Instantiation options checkboxes
- Progress feedback
- Save project functionality

## Command-Line Testing

### Test Script

```bash
python test_dubgg_project.py
```

This script:
1. Loads DUBGG.scd
2. Displays all IEDs
3. Prompts for confirmation
4. Instantiates servers
5. Starts PLC programs
6. Saves DUBGG.mss
7. Shows running status

### Headless Mode

For automated testing or CI/CD:

```python
from src.core.device_manager_core import DeviceManagerCore
from src.core.ied_project_orchestrator import IEDProjectOrchestrator

# Create components
device_manager = DeviceManagerCore()
orchestrator = IEDProjectOrchestrator(device_manager)

# Load and instantiate
orchestrator.load_from_scd("dubgg/DUBGG.scd")
orchestrator.instantiate_all_ieds()
orchestrator.save_project("output.mss")

# Clean shutdown
orchestrator.shutdown()
```

## Key Features

### Automatic IP Binding

IEDs are bound to exact IP addresses from SCD Communication section:

```xml
<ConnectedAP iedName="IED1" apName="AP1">
  <Address>
    <P type="IP">192.168.1.10</P>
    <P type="IP-SUBNET">255.255.255.0</P>
  </Address>
</ConnectedAP>
```

→ Server listens on `192.168.1.10:102`

### PLC Runtime

- Each device gets dedicated PLC thread
- Configurable cycle time (default 100ms)
- Automatic variable initialization
- Error handling and recovery
- Cycle count tracking

### Project Persistence

- Complete state serialization
- Relative paths for portability
- Settings preservation
- Device enable/disable state
- PLC program associations

## Technical Details

### Thread Architecture

```
Main Application
├── Device Manager
│   ├── IED1 Server (Thread)
│   ├── IED2 Server (Thread)
│   └── IED3 Server (Thread)
└── PLC Runtime Engine
    ├── PRG_IED1 (Thread)
    ├── PRG_IED2 (Thread)
    └── PRG_IED3 (Thread)
```

Each IED server and PLC program runs in its own thread for true concurrency.

### Memory Considerations

For large SCD files (>100MB):
- Parsing is done incrementally
- Templates loaded on-demand
- Device instantiation is sequential
- PLC programs are lightweight

### Error Handling

- SCD parsing errors: Logged, UI notified
- Device creation failures: Continue with others
- PLC execution errors: Max 10 retries then stop
- Network binding conflicts: Reported to user

## Troubleshooting

### SCD Won't Load

**Problem**: "Failed to load SCD"

**Solutions**:
- Check file exists and is readable
- Verify SCD is valid XML
- Check file size (<500MB recommended)
- Review logs for XML parsing errors

### No IP Addresses

**Problem**: IEDs show "NO_IP"

**Solutions**:
- SCD missing Communication section
- ConnectedAP elements not properly formed
- Manual IP assignment required

### PLC Won't Start

**Problem**: PLC program fails to run

**Solutions**:
- Check program file exists
- Verify device is connected
- Review PLC runtime logs
- Check cycle time setting

### Server Binding Fails

**Problem**: "Address already in use"

**Solutions**:
- Port 102 already taken
- Another IED on same IP
- Windows firewall blocking
- Check network adapter configuration

## Best Practices

### 1. SCD Preparation

- Ensure Communication section is complete
- Verify all IEDs have IP addresses
- Use unique IED names
- Include manufacturer information

### 2. Project Organization

```
project/
├── dubgg/
│   └── DUBGG.scd
├── plc_programs/
│   ├── PRG_IED1.st
│   └── PRG_IED2.st
└── DUBGG.mss
```

### 3. Development Workflow

1. Load SCD in IED Project Manager
2. Verify IED list and IPs
3. Instantiate with auto-connect
4. Test connectivity from clients
5. Edit PLC programs as needed
6. Save MSS project
7. Commit to version control

### 4. Testing

- Test with small SCD first (<10 IEDs)
- Verify IP addresses don't conflict
- Check PLC programs compile
- Monitor event log for errors
- Test MSS save/load cycle

## API Reference

### IEDProjectOrchestrator

Main orchestration class.

**Methods**:
- `load_from_scd(scd_path, project_name)` - Load and parse SCD
- `instantiate_all_ieds(auto_connect, start_plc)` - Create servers
- `save_project(mss_path)` - Save as MSS
- `load_project(mss_path)` - Load MSS
- `get_project_summary()` - Get status dict
- `shutdown()` - Clean shutdown

### SCDProjectLoader

SCD parsing and extraction.

**Methods**:
- `extract_ieds()` - Get all IED definitions
- `get_ied_by_name(name)` - Get specific IED

**Returns**: List of `IEDDefinition` objects

### PLCProgramGenerator

PLC program creation.

**Methods**:
- `generate_program_for_ied(ied_name, device_name, logical_devices)` - Create program
- `load_program(file_path)` - Load existing
- `save_program(file_path, content)` - Save modified
- `get_all_programs()` - List all .st files

### PLCRuntimeEngine

PLC execution environment.

**Methods**:
- `load_program(program_name, device_name, file_path, cycle_time_ms, auto_start)` - Load program
- `start_program(program_name)` - Start execution
- `stop_program(program_name)` - Stop execution
- `stop_all()` - Stop all programs
- `get_status(program_name)` - Get execution status

### MSSProjectManager

Project file management.

**Methods**:
- `create_project(project_name, description, scd_file_path)` - New project
- `add_device(device_name, ied_name, ip_address, port, plc_program)` - Add device
- `save_project(file_path)` - Save MSS
- `load_project(file_path)` - Load MSS
- `get_project_info(file_path)` - Read metadata only

## Examples

### Example 1: Simple Load

```python
orchestrator = IEDProjectOrchestrator(device_manager)
orchestrator.load_from_scd("test.scd")
orchestrator.instantiate_all_ieds()
orchestrator.save_project("test.mss")
```

### Example 2: Custom Configuration

```python
orchestrator = IEDProjectOrchestrator(device_manager)
orchestrator.load_from_scd("config.scd", project_name="MyProject")

# Instantiate without auto-connect
orchestrator.instantiate_all_ieds(
    auto_connect=False,
    start_plc=False
)

# Manually connect specific IEDs
device_manager.connect_device("IED1")
device_manager.connect_device("IED2")

orchestrator.save_project("custom.mss")
```

### Example 3: Load Existing Project

```python
orchestrator = IEDProjectOrchestrator(device_manager)
orchestrator.load_project("DUBGG.mss")

# All devices restored
summary = orchestrator.get_project_summary()
print(f"Loaded {summary['instantiated_count']} devices")

# Modify and save
orchestrator.save_project("DUBGG_modified.mss")
```

## Integration with Existing Features

### Device Explorer

- IEDs appear as IEC61850_SERVER devices
- Hierarchical signal tree from SCD model
- Real-time value updates
- Control operations

### Watch List

- Add IED signals to watch list
- Monitor values with update rates
- CSV export functionality
- Performance tracking

### Event Log

- Device connection events
- PLC execution status
- Error notifications
- Transaction logging

### Protocol Gateway

- Map IED signals to Modbus
- Bridge protocols
- Data transformation
- Multiple destination support

## Future Enhancements

### Planned Features

1. **Full ST Interpreter**
   - Parse and execute ST code
   - Variable bindings
   - Function blocks
   - Debugging support

2. **Visual PLC Editor**
   - Graphical program editing
   - Ladder Diagram support
   - Online debugging
   - Breakpoints

3. **Advanced SCD Processing**
   - GOOSE subscription setup
   - Report control configuration
   - Sampled Values
   - Data set management

4. **Multi-SCD Projects**
   - Load multiple SCD files
   - Cross-IED communication
   - System-wide simulation
   - Network topology

## Support

For issues or questions:
- Check event log for detailed errors
- Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
- Review generated PLC programs
- Verify SCD structure
- Test with provided examples

## License

Same license as SCADA Scout project.
