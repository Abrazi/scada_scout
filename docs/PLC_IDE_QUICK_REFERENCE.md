# PLC IDE Quick Reference Card

## 🚀 Getting Started (5 Steps)

1. **Open PLC IDE**: `Ctrl+Shift+P` or Tools → PLC IDE
2. **Create Program**: Click "New Program"
3. **Write Code**: Use Structured Text (ST) syntax
4. **Compile**: Press `F7` or click 🔨 Compile
5. **Run**: Press `F5` or click ▶ RUN (or 🐛 DEBUG)

---

## ⌨️ Keyboard Shortcuts

### PLC Operations
| Shortcut | Action |
|----------|--------|
| `F7` | Compile current program |
| `F5` | Run PLC (RUN mode) |
| `Ctrl+S` | Save program |

### Debugging
| Shortcut | Action |
|----------|--------|
| `F9` | Toggle breakpoint at current line |
| `F8` | Continue execution |
| `F10` | Step Over (execute current line) |
| `F11` | Step Into (enter function calls) |
| `Shift+F11` | Step Out (exit current function) |

---

## 🎨 Mode Indicator Colors

| Color | Mode | Description |
|-------|------|-------------|
| 🔴 Red | STOP | PLC not running |
| 🟢 Green | RUN | Normal execution |
| 🔵 Blue | DEBUG | Debugging with breakpoints |
| 🔴 Bright Red | FAULTED | Error - requires reset |

---

## 🐛 Debugging Workflow

### Setting Breakpoints
1. **Click** in line number gutter (left margin) → Red dot appears
2. **OR** Press `F9` with cursor on line
3. **OR** Click 🔴 Breakpoint button

### Starting Debug Session
1. Compile program (`F7`)
2. Click **🐛 DEBUG** button (NOT ▶ RUN)
3. Mode indicator turns 🔵 blue
4. Program runs until first breakpoint

### Stepping Through Code
```
F8  → Continue (run until next breakpoint)
F10 → Step Over (execute current line, don't enter functions)
F11 → Step Into (if current line calls function, enter it)
```

### Watching Variables
1. Select **Watch** tab in right panel
2. Enter expression: `counter`, `a + b`, `temperature > 50`
3. Click Add
4. Value updates during execution

### Viewing Call Stack
1. Select **Call Stack** tab
2. See which programs are executing
3. View variables in each stack frame

---

## 📝 Structured Text Syntax

### Variables
```st
VAR
    counter : INT;              // Integer variable
    temperature : REAL := 20.5; // Float with initial value
    running : BOOL;             // Boolean
END_VAR
```

### Assignments
```st
counter := counter + 1;
temperature := 25.3;
running := TRUE;
```

### IF Statements
```st
IF temperature < 20.0 THEN
    mode := HEATING;
ELSIF temperature > 30.0 THEN
    mode := COOLING;
ELSE
    mode := NORMAL;
END_IF;
```

### FOR Loops
```st
FOR i := 1 TO 10 BY 1 DO
    sum := sum + i;
END_FOR;
```

### WHILE Loops
```st
WHILE counter < 100 DO
    counter := counter + 1;
END_WHILE;
```

### CASE Statements
```st
CASE state OF
    1: output := 'ON';
    2: output := 'OFF';
ELSE
    output := 'UNKNOWN';
END_CASE;
```

---

## 🔗 Linking Device Tags to PLC Variables

### Overview
PLC programs can read from and write to actual device signals (tags) from connected devices like Modbus, IEC 61850, or OPC UA devices. This allows your PLC logic to control real hardware.

### Step-by-Step: Link Device Tag to PLC Variable

#### Method 1: Using Address Mapping (Recommended)

1. **Declare Variable with Address**
```st
VAR_INPUT
    sensorTemp : REAL AT %IW100;    // Input from device address IW100
END_VAR

VAR_OUTPUT  
    pumpControl : BOOL AT %QX0.0;   // Output to device address QX0.0
END_VAR
```

**Address Format:**
- `%I` = Input from device
- `%Q` = Output to device
- `%M` = Memory (internal)
- `X` = Bit (BOOL)
- `B` = Byte
- `W` = Word (INT, 16-bit)
- `D` = Double Word (DINT, 32-bit)

**Examples:**
```st
VAR_INPUT
    // Read from Modbus holding register 40001
    flowRate : REAL AT %IW40001;
    
    // Read from IEC 61850 data object
    switchStatus : BOOL AT %IX1.3;
    
    // Read multiple inputs
    temp1 : REAL AT %IW100;
    temp2 : REAL AT %IW101;
    temp3 : REAL AT %IW102;
END_VAR

VAR_OUTPUT
    // Write to Modbus coil
    valveOpen : BOOL AT %QX0.5;
    
    // Write to analog output
    setpoint : REAL AT %QW200;
END_VAR
```

#### Method 2: Manual Tag Browsing

1. **Browse Available Device Tags**
   - In PLC IDE, right-click in Variables panel
   - Select "Browse Device Tags..." (if available)
   - OR use main device tree to find signals

2. **Copy Tag Address**
   - Select device in main window
   - Expand signal tree
   - Right-click signal → Copy Address
   - Example: `Device1::Temperature` or `40001`

3. **Use in PLC Program**
```st
VAR_INPUT
    deviceTag : REAL AT %IW[copied_address];
END_VAR
```

#### Method 3: Direct Signal Reading (Advanced)

For dynamic access, use special functions:
```st
VAR
    tempValue : REAL;
END_VAR

// Read device signal directly (if supported)
tempValue := READ_DEVICE_SIGNAL('DeviceName', 'SignalAddress');

// Or use global variables linked at runtime
tempValue := GLOBAL_INPUT_TEMP;  // Pre-mapped in device config
```

### Variable Types and Device I/O Mapping

| Variable Scope | Direction | Use Case |
|---------------|-----------|----------|
| **VAR_INPUT** | Device → PLC | Read sensor values, switch states |
| **VAR_OUTPUT** | PLC → Device | Control actuators, write setpoints |
| **VAR_IN_OUT** | Both | Read-modify-write operations |
| **VAR** (local) | Internal | Calculations, temporary storage |

### Complete Example: Temperature Control

```st
PROGRAM TemperatureControl
VAR_INPUT
    // Read from device
    currentTemp : REAL AT %IW100;      // Sensor reading
    setpoint : REAL AT %IW101;         // Desired temperature
    manualMode : BOOL AT %IX0.0;       // Manual override switch
END_VAR

VAR_OUTPUT
    // Write to device
    heaterOn : BOOL AT %QX0.0;         // Heater control relay
    coolerOn : BOOL AT %QX0.1;         // Cooler control relay
    alarmLight : BOOL AT %QX0.2;       // Alarm indicator
END_VAR

VAR
    // Internal calculations
    error : REAL;
    deadband : REAL := 2.0;
END_VAR

// Control logic
error := setpoint - currentTemp;

IF NOT manualMode THEN
    // Automatic control
    IF error > deadband THEN
        heaterOn := TRUE;
        coolerOn := FALSE;
    ELSIF error < -deadband THEN
        heaterOn := FALSE;
        coolerOn := TRUE;
    ELSE
        heaterOn := FALSE;
        coolerOn := FALSE;
    END_IF;
    
    // Safety alarm
    IF currentTemp > (setpoint + 10.0) OR currentTemp < (setpoint - 10.0) THEN
        alarmLight := TRUE;
    ELSE
        alarmLight := FALSE;
    END_IF;
END_IF;

END_PROGRAM
```

### Task Configuration for Real-Time I/O

After linking device tags, configure task timing:

1. Click **⚙️ Task Settings** button
2. Set appropriate scan interval:
   - **Fast I/O** (< 50ms): Critical control loops
   - **Normal I/O** (100-500ms): Standard monitoring
   - **Slow I/O** (> 1000ms): Status updates, logging

3. Assign program to task
4. Enable task

### Device Tag Requirements

**Before linking tags to PLC:**
1. ✅ Device must be added to SCADA Scout
2. ✅ Device must be connected (online)
3. ✅ Signals must be discovered (visible in device tree)
4. ✅ Signal addresses must be known

**To verify device signals:**
```
1. Main Window → Device List
2. Select device
3. Expand signal tree
4. Note signal addresses
5. Use these addresses in PLC VAR_INPUT/VAR_OUTPUT
```

### Common Device Address Formats

**Modbus TCP:**
```st
// Format: register_address
holdingReg : INT AT %IW40001;   // Read holding register 40001
coil : BOOL AT %IX10001;        // Read coil 10001
```

**IEC 61850:**
```st
// Format: LogicalNode.DataObject
voltage : REAL AT %IW[MMXU1.PhV.phsA];
switch : BOOL AT %IX[CSWI1.Pos.stVal];
```

**OPC UA:**
```st
// Format: NodeId or BrowseName
pressure : REAL AT %IW[ns=2;s=PressureSensor];
```

### Troubleshooting Tag Linking

**Variable not updating:**
- Check device is connected (green status)
- Verify signal address is correct
- Ensure task is running (⚙️ Task Settings)
- Check read permissions on device

**Write fails:**
- Verify VAR_OUTPUT used (not VAR_INPUT)
- Check device supports writes
- Verify signal is writable (not read-only)
- Check device communication errors

**Address not recognized:**
- Use device-specific address format
- Check address exists in device signal tree
- Verify address syntax (%, I/Q, W/X/D)

### Best Practices

1. **Group Related I/O**
```st
VAR_INPUT
    // Temperature sensors
    temp_zone1 : REAL AT %IW100;
    temp_zone2 : REAL AT %IW101;
    temp_zone3 : REAL AT %IW102;
END_VAR
```

2. **Document Addresses**
```st
VAR_INPUT
    mainPressure : REAL AT %IW200;  // Modbus 40201 - Main line pressure sensor
    tankLevel : REAL AT %IW201;     // Modbus 40202 - Storage tank level
END_VAR
```

3. **Use Meaningful Names**
```st
// Good ✅
pumpMotorRunning : BOOL AT %IX0.5;

// Bad ❌
b1 : BOOL AT %IX0.5;
```

4. **Validate Inputs**
```st
IF currentTemp > -50.0 AND currentTemp < 200.0 THEN
    // Valid range, use value
    validTemp := currentTemp;
ELSE
    // Out of range, use safe default or alarm
    validTemp := 25.0;
    sensorError := TRUE;
END_IF;
```

---

## ⚠️ Common Errors & Solutions

### "Compile at least one program before starting PLC"
**Solution:** Press `F7` to compile first, THEN press `F5` or click 🐛 DEBUG

### "PLC must be in DEBUG mode to step"
**Solution:** Click **🐛 DEBUG** button (not ▶ RUN) to enable stepping

### Breakpoint not working
**Causes:**
- PLC in RUN mode instead of DEBUG mode → Use 🐛 DEBUG
- Breakpoint disabled → Click red dot again to re-enable
- Code not compiled → Press `F7` first

### Variable shows "None" or doesn't update
**Causes:**
- PLC not running → Start with F5 or 🐛 DEBUG
- Variable not used in code → Check spelling
- Program not enabled → Check program properties

---

## 🎯 Best Practices

### 1. Always Compile Before Running
```
1. Write code
2. Press F7 (compile)
3. Check for errors
4. Press F5 or 🐛 DEBUG
```

### 2. Use Descriptive Variable Names
```st
// Good ✅
temperatureCelsius : REAL;
pumpIsRunning : BOOL;

// Bad ❌
t : REAL;
b1 : BOOL;
```

### 3. Initialize Variables
```st
VAR
    counter : INT := 0;      // Start at 0
    maxValue : INT := 100;   // Set limit
END_VAR
```

### 4. Comment Your Code
```st
// This is a comment
(* This is a
   multi-line comment *)

counter := counter + 1;  // Inline comment
```

### 5. Use DEBUG Mode for Development
- **RUN mode**: Fast, for production
- **DEBUG mode**: Slower, but shows execution flow

---

## 🔍 Troubleshooting

### PLC won't start
1. Check mode indicator - is it FAULTED? → Click Reset
2. Check console for error messages
3. Verify at least one program compiled successfully
4. Check task configuration

### Variables not visible
1. Switch to "Variables" tab in right panel
2. Click "Refresh" if needed
3. Ensure PLC is running (RUN or DEBUG)

### Breakpoint ignored
1. Verify mode is DEBUG (blue indicator)
2. Check breakpoint is enabled (solid red dot)
3. Ensure code was compiled after setting breakpoint

### Slow execution
- This is normal in DEBUG mode
- Use RUN mode for full speed
- Reduce watch expression count

---

## 📊 Variable Types Reference

| Type | Range | Example |
|------|-------|---------|
| BOOL | TRUE/FALSE | `running := TRUE;` |
| INT | -32,768 to 32,767 | `counter := 100;` |
| UINT | 0 to 65,535 | `value := 50000;` |
| REAL | ±3.4E38 | `temp := 25.5;` |
| DINT | -2,147,483,648 to 2,147,483,647 | `large := 1000000;` |
| STRING | Text (max 255 chars) | `name := 'Device1';` |

---

## 🎓 Learning Resources

### Documentation
- Press `F1` → Help Index → PLC IDE Quick Start
- Press `Ctrl+F1` → PLC IDE Quick Start (direct)
- Help → PLC IDE Phase 2 Summary (advanced features)

### Example Programs
1. Counter: Basic increment/decrement
2. Temperature Control: IF/ELSIF logic
3. Traffic Light: CASE statement example
4. Sum Calculator: FOR loop usage

### Getting Help
- Press `Ctrl+Shift+A` → AI Assistant
- Ask questions about PLC programming
- Request code examples
- Troubleshoot errors

---

## 💡 Pro Tips

### Tip 1: Use Watch Expressions for Debugging
Instead of checking each variable individually, add expressions:
```
counter > 50
temperature * 1.8 + 32  (Celsius to Fahrenheit)
(a AND b) OR c
```

### Tip 2: Set Conditional Breakpoints
Right-click breakpoint → Add Condition:
```
counter == 10
temperature > threshold
running AND NOT error
```

### Tip 3: Quick Navigation
- Double-click variable in Watch panel → Jumps to declaration
- Double-click Call Stack frame → Shows that code
- Ctrl+Click on program in tree → Opens program

### Tip 4: Hot Reload with Online Change
1. Modify code while PLC running
2. Compile (F7)
3. Runtime → Online Change
4. No need to stop/restart!

### Tip 5: Keyboard Workflow
```
F7 (compile) → F5 (run) → F9 (breakpoint) → F11 (step into) → F8 (continue)
```
Never touch the mouse! 🚀

---

## 🆘 Emergency Procedures

### PLC Stuck/Frozen
1. Click ⏹ STOP button
2. Wait 2 seconds
3. Check mode indicator returns to red STOP
4. If still frozen: Close PLC IDE window, reopen

### Compilation Error Loop
1. Copy your code to external editor (safety)
2. Create NEW program
3. Paste code back
4. Compile again

### Lost Variables
1. Check "Variables" tab is selected
2. Verify program is current/active
3. Click Refresh button
4. If still missing: Stop PLC, recompile, start again

---

## ✅ Pre-Flight Checklist

Before running critical PLC code:
```
□ All programs compiled (F7)
□ No compilation errors
□ Variables initialized properly
□ Output signals configured
□ Safety interlocks tested
□ Watchdog timer configured (if needed)
□ Backup of working code saved
□ Tested in DEBUG mode first
```

---

**Quick Help:**
- `F1` - Help Index
- `Ctrl+F1` - PLC Quick Start
- `Ctrl+Shift+A` - AI Assistant
- Help menu → PLC IDE Phase 2 Summary

**Version:** 1.0 | February 2, 2026 | SCADA Scout PLC IDE
