# PLC IDE - Phase 1 Implementation Complete

## Overview

SCADA Scout now includes a **professional PLC IDE** for developing IEC 61131-3 programs directly within the Device Explorer. This Phase 1 implementation provides the foundation for industrial-grade PLC programming.

## Features Implemented

### ✅ Core Infrastructure
- **PLC Data Models**: Complete type system with IEC 61131-3 elementary types
- **Program Organization**: Programs, tasks, and variable scopes
- **Operating Modes**: STOP, RUN, DEBUG, FAULTED with safe transitions
- **Task Types**: Cyclic, event-driven, and interrupt tasks

### ✅ IDE Interface
- **Syntax Highlighting**: Full ST (Structured Text) syntax highlighting
- **Program Editor**: Professional code editor with auto-formatting
- **Project Tree**: Hierarchical view of programs and tasks
- **Variable Inspector**: Real-time variable monitoring
- **Toolbar Controls**: Compile, RUN, STOP with visual mode indicators
- **Output Console**: Compilation and runtime diagnostics

### ✅ Compiler
- **ST Parser**: Variable declaration extraction
- **Type Checking**: Strong typing per IEC 61131-3
- **Error Reporting**: Line-accurate error messages
- **Bytecode Generation**: Compiled programs ready for execution

### ✅ Runtime Engine
- **Simulated PLC**: Full scan cycle implementation
- **Task Scheduler**: Priority-based task execution
- **Variable Context**: Isolated program contexts with global scope
- **Fault Handling**: Safe fault detection and recovery

## Quick Start

### 1. Access PLC IDE

**Option A: Via Device Explorer**
- Right-click any device → **"Open PLC IDE..."**

**Option B: Via Menu**
- View Menu → **"PLC IDE (IEC 61131-3)"** (Ctrl+Shift+P)

### 2. Create Your First Program

1. Click **"New Program"** in the project tree
2. Enter a program name (e.g., "PumpController")
3. Edit the code in the editor:

```st
PROGRAM PumpController
VAR
    pumpRunning : BOOL := FALSE;
    cycleCount : INT := 0;
    temperature : REAL := 20.0;
END_VAR

(* Main control logic *)
IF temperature > 80.0 THEN
    pumpRunning := TRUE;
ELSE
    pumpRunning := FALSE;
END_IF

cycleCount := cycleCount + 1;

END_PROGRAM
```

4. Press **F7** or click **"Compile"**
5. Press **F5** or click **"RUN"** to start execution

### 3. Monitor Variables

The **Variable Inspector** (right panel) shows real-time values:
- Name, Type, Current Value, Quality
- Updates at 2Hz when PLC is running

### 4. Create Tasks (Optional)

For advanced control, create tasks:
1. Click **"New Task"**
2. Configure priority and interval
3. Assign programs to tasks in task properties

## Architecture

```
Device Explorer
  └── Device (e.g., "ModbusPLC")
      ├── Configuration
      ├── Programs ▼
      │   └── PumpController.st [Cyclic, 100ms]
      ├── Tasks ▼
      │   └── MainTask (Priority 10, 100ms)
      └── **Open PLC IDE** ←
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+Shift+P** | Open PLC IDE (device selector) |
| **Ctrl+S** | Save current program |
| **F7** | Compile program |
| **F5** | Start PLC (RUN mode) |
| **Shift+F5** | Stop PLC |

## IEC 61131-3 Language Support

### Phase 1: Structured Text (ST) ✅
- Variable declarations (VAR, VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT)
- Elementary data types (BOOL, INT, DINT, REAL, etc.)
- Arithmetic operators (+, -, *, /, MOD, DIV)
- Comparison operators (=, <>, <, >, <=, >=)
- Boolean operators (AND, OR, NOT, XOR)
- Assignment (:=)
- Comments ((* ... *) and //)

### Future Phases (Roadmap)
- **Phase 2**: Control flow (IF/THEN/ELSE, FOR loops, WHILE loops)
- **Phase 3**: Function blocks and functions
- **Phase 4**: Ladder Diagram (LD) visual editor
- **Phase 5**: Function Block Diagram (FBD) editor

## Operating Modes

### STOP Mode (Red)
- No program execution
- Safe state for editing
- All outputs held safe

### RUN Mode (Green)
- Continuous scan cycle execution
- Programs execute by priority
- Real-time variable updates

### DEBUG Mode (Blue)
- *Phase 3 feature* - Breakpoints and stepping

### FAULTED Mode (Red Flashing)
- Critical error detected
- Execution halted safely
- Requires manual reset

## Examples

### Simple Counter
```st
PROGRAM Counter
VAR
    count : INT := 0;
END_VAR

count := count + 1;

END_PROGRAM
```

### Temperature Control
```st
PROGRAM TempControl
VAR_INPUT
    sensorTemp : REAL;
    setpoint : REAL;
END_VAR
VAR_OUTPUT
    heaterOn : BOOL;
END_VAR
VAR
    hysteresis : REAL := 2.0;
END_VAR

IF sensorTemp < (setpoint - hysteresis) THEN
    heaterOn := TRUE;
ELSIF sensorTemp > (setpoint + hysteresis) THEN
    heaterOn := FALSE;
END_IF

END_PROGRAM
```

### Motor Sequencer
```st
PROGRAM MotorSeq
VAR
    motor1 : BOOL := FALSE;
    motor2 : BOOL := FALSE;
    motor3 : BOOL := FALSE;
    sequence : INT := 0;
    timer : INT := 0;
END_VAR

(* 10-second startup sequence *)
timer := timer + 1;

IF timer = 100 THEN
    motor1 := TRUE;
    sequence := 1;
ELSIF timer = 200 THEN
    motor2 := TRUE;
    sequence := 2;
ELSIF timer = 300 THEN
    motor3 := TRUE;
    sequence := 3;
END_IF

END_PROGRAM
```

## Integration with SCADA Scout

### Device Data Access: Linking Device Tags to PLC Variables

PLC programs can seamlessly integrate with live SCADA device data. Here's how to connect device signals to your PLC variables:

#### Method 1: Address Mapping (Recommended)

Use special address syntax in variable declarations to automatically link device tags:

```st
PROGRAM ProcessControl
VAR_INPUT
    flowRate : REAL AT %IW100;      (* Read from Modbus register 40101 *)
    tankLevel : REAL AT %IW102;     (* Read from Modbus register 40103 *)
    pumpStatus : BOOL AT %IX0.5;    (* Read discrete input 5 *)
END_VAR
VAR_OUTPUT
    valveOpen : BOOL AT %QX1.3;     (* Write to coil 3 *)
    heaterOn : BOOL AT %QX1.4;      (* Write to coil 4 *)
END_VAR

(* Your control logic automatically uses live device data *)
IF flowRate < 10.0 THEN
    valveOpen := TRUE;
END_IF

END_PROGRAM
```

**Address Format:**
- `%I` = Input, `%Q` = Output
- `X` = Bit, `B` = Byte, `W` = Word (16-bit), `D` = Double word (32-bit)
- Examples: `%IW100`, `%QX0.5`, `%ID200`

#### Method 2: Device Tag Browser

1. **Add Device to Project:**
   - Open Device Explorer
   - Connect to your Modbus/IEC61850/OPC UA device
   - Discover signals

2. **Browse Tags in PLC IDE:**
   - In Variables panel, right-click → "Browse Device Tags..."
   - Select device and signal
   - Choose variable type (INPUT/OUTPUT)
   - Address automatically assigned

3. **Tag Appears in Code:**
   ```st
   VAR_INPUT
       tempSensor : REAL AT %IW250;  (* Auto-generated from tag browse *)
   END_VAR
   ```

#### Method 3: Direct Signal Reading (Advanced)

Use built-in functions to read device signals by name:

```st
PROGRAM DirectRead
VAR
    currentTemp : REAL;
    tankFull : BOOL;
END_VAR

(* Read by device:signal path *)
currentTemp := READ_DEVICE_SIGNAL('IED_Server::TEMP/TMPSV1$MX$TmpSv$instMag$f');
tankFull := READ_DEVICE_SIGNAL('ModbusPLC::1:3:40005') > 95.0;

END_PROGRAM
```

#### Device Address Formats

**Modbus TCP/RTU:**
- Holding Registers: `unit:function:address` → `1:3:40001` maps to `%IW0`
- Coils: `unit:function:address` → `1:1:10` maps to `%IX10`
- Input Registers: Use function code 4

**IEC 61850:**
- Object reference: `IED_NAME/LN0$FC$DO$DA` → `TEMP/TMPSV1$MX$TmpSv$instMag$f`
- Map to `%IW` addresses via Device Tag browser

**OPC UA:**
- Node ID: `ns=2;s=Temperature` → Assign to `%IW` manually

#### Real-Time Updates

Configure task intervals for I/O refresh rate:
```
Task: MainControl
Interval: 100 ms   ← I/O updated 10x/second
Priority: 1
```

#### Complete Example: Tank Controller with Real Device I/O

```st
PROGRAM TankController
VAR_INPUT
    tankLevel : REAL AT %IW100;      (* Modbus 1:3:40101 - Level sensor *)
    fillSwitch : BOOL AT %IX0.0;     (* Modbus 1:2:10000 - Manual switch *)
    highAlarm : REAL := 95.0;
    lowAlarm : REAL := 10.0;
END_VAR
VAR_OUTPUT
    fillValve : BOOL AT %QX1.0;      (* Modbus 1:5:0 - Fill valve coil *)
    drainValve : BOOL AT %QX1.1;     (* Modbus 1:5:1 - Drain valve *)
    alarmLight : BOOL AT %QX1.2;     (* Modbus 1:5:2 - Alarm indicator *)
END_VAR
VAR
    state : INT := 0;  (* 0=idle, 1=filling, 2=draining *)
END_VAR

(* Safety check *)
IF tankLevel > highAlarm THEN
    fillValve := FALSE;
    alarmLight := TRUE;
    state := 0;
ELSIF tankLevel < lowAlarm AND fillSwitch THEN
    fillValve := TRUE;
    drainValve := FALSE;
    alarmLight := FALSE;
    state := 1;
ELSIF tankLevel > 90.0 AND state = 1 THEN
    fillValve := FALSE;
    state := 0;
ELSE
    alarmLight := FALSE;
END_IF

END_PROGRAM
```

**Device Configuration (devices.json):**
```json
{
  "name": "TankPLC",
  "device_type": "MODBUS_TCP",
  "ip_address": "192.168.1.100",
  "port": 502,
  "registers": [
    {"address": "1:3:40101", "name": "TankLevel", "data_type": "FLOAT32"},
    {"address": "1:2:10000", "name": "FillSwitch", "data_type": "BOOL"},
    {"address": "1:5:0", "name": "FillValve", "data_type": "BOOL"},
    {"address": "1:5:1", "name": "DrainValve", "data_type": "BOOL"}
  ]
}
```

**Steps to Connect:**
1. Add TankPLC device to Device Explorer
2. Connect and verify signals update
3. Open PLC IDE (Ctrl+Shift+P)
4. Create TankController program with VAR_INPUT/VAR_OUTPUT addresses
5. Compile program (F7)
6. Create task with 100ms interval
7. Start PLC (F5) - now reads/writes live device data!

#### Troubleshooting Device I/O

**Variables Not Updating:**
- Verify device connected in Device Explorer
- Check address format matches device type
- Ensure task interval isn't too fast (min 50ms)
- Look for I/O errors in Output panel

**Cannot Write to Output:**
- Confirm VAR_OUTPUT variables (not VAR_INPUT)
- Check device supports writes (some protocols read-only)
- Verify PLC is in RUN mode

**Address Not Recognized:**
- Use Device Tag browser instead of manual entry
- Check device configuration in devices.json
- Ensure register exists in device model

### Automation Scripts
PLC programs complement Python/IEC 61131 automation scripts:
- **PLC Programs**: Real-time, deterministic control logic
- **Python Scripts**: High-level orchestration, data analysis
- **IEC 61131 Scripts**: External runtime integration

## Troubleshooting

### Compilation Errors
**Problem**: "Expected ';' after assignment"
**Solution**: Ensure all statements end with semicolon

**Problem**: "Unknown type 'INTEGER'"
**Solution**: Use standard IEC 61131-3 type: `INT`

### Runtime Issues
**Problem**: PLC won't start (stays in STOP)
**Solution**: Compile at least one program first

**Problem**: Variables not updating
**Solution**: Check PLC is in RUN mode (green indicator)

### Performance
**Problem**: Slow scan times
**Solution**: 
- Reduce program complexity
- Increase task intervals
- Split logic across multiple tasks

## Technical Details

### Scan Cycle
```
1. Read Inputs (I/O Update)
2. Execute Programs (by priority)
3. Write Outputs (I/O Update)
4. Housekeeping (diagnostics, communication)
5. Wait for next cycle
```

Default scan rate: **10ms** (100Hz)

### Variable Context
- **Global Variables**: Shared across all programs
- **Program Variables**: Isolated per program
- **Task Variables**: Scoped to task execution

### File Storage
PLC programs are stored in the device's `plc_extension` attribute and persist with device configuration.

## Next Steps (Phase 2)

### Planned Features
- ✅ Breakpoint debugging with step execution
- ✅ Control flow statements (IF, FOR, WHILE, CASE)
- ✅ Function blocks and user-defined functions
- ✅ Online change (modify running programs)
- ✅ Inline variable display (values in editor)
- ✅ Call stack inspector
- ✅ Watch expressions
- ✅ Ladder Diagram (LD) editor
- ✅ Cross-reference tool

### Runtime Enhancements
- ✅ External PLC runtime bridge (real hardware)
- ✅ Task profiling and diagnostics
- ✅ Memory usage monitoring
- ✅ RETAIN variable persistence

## Documentation

- **Architecture**: `docs/PLC_IDE_ARCHITECTURE.md`
- **API Reference**: `src/models/plc_models.py`
- **Compiler**: `src/core/st_compiler.py`
- **Runtime**: `src/core/plc_runtime.py`

## Support

For issues or feature requests, see the main project documentation.

---

**Status**: Phase 1 Complete ✅
**Next Release**: Phase 2 - Advanced Debugging (Q2 2026)
