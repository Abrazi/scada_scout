# SCADA Scout - Script IDE Documentation

## Overview

The Script IDE provides a complete development environment for writing, testing, and debugging Python scripts for SCADA Scout. It features a professional code editor with syntax highlighting, full debugging capabilities with breakpoints and step-by-step execution, variable inspection, and integrated console output.

## Features

### 🎨 Advanced Code Editor
- **Syntax Highlighting**: Python keywords, strings, comments, numbers, and functions
- **Line Numbers**: Easy navigation and reference
- **Breakpoint Support**: Click in the line number area to toggle breakpoints
- **Execution Highlighting**: Current line highlighted during debugging
- **Auto-indent**: Smart indentation for Python code
- **Dark Theme**: Comfortable for extended coding sessions

### 🐞 Full Debugger
- **Breakpoints**: Set/remove breakpoints by clicking line numbers
- **Step Controls**:
  - **Step Over (F10)**: Execute current line and stop at next line
  - **Step Into (F11)**: Enter into function calls
  - **Step Out (Shift+F11)**: Exit current function
  - **Continue (F8)**: Resume execution until next breakpoint
- **Variable Inspector**: View all local variables and their values during execution
- **Call Stack**: See the complete execution stack trace
- **Watch Expressions**: Monitor specific expressions in real-time

### 📁 Project Management
- **File Browser**: Navigate and manage script files
- **Save/Load**: Persistent script storage in `scripts/` folder
- **Multiple Files**: Open and edit multiple scripts
- **Auto-save Prompts**: Never lose your work

### 🎛️ SCADA Integration
- Full access to device manager and all connected devices
- Read/write signals with `ctx.get()`, `ctx.set()`, `ctx.read()`
- IEC 61850 control operations with `ctx.send_command()`
- Event logging integration

## Quick Start

### Opening the IDE

1. Launch SCADA Scout
2. Go to **View → Script IDE (Debug)...** or press **Ctrl+Shift+D**
3. The Script IDE window opens with a default template

### Your First Script

```python
def tick(ctx):
    """
    Called repeatedly at configured interval.
    Perfect for monitoring and automation.
    """
    # Read a value from a device
    voltage = ctx.get('IED1::LD/MMXU1.PhV.phsA.cVal.mag.f', 0)
    
    # Check threshold
    if voltage > 240:
        ctx.log('warning', f'High voltage detected: {voltage}V')
        # Take corrective action
        ctx.set('IED1::LD/CTRL1.setpoint', 230)
    
    # Log for debugging
    ctx.log('info', f'Current voltage: {voltage}V')


def main(ctx):
    """
    Called once when script is run.
    Use for one-time operations.
    """
    ctx.log('info', 'Voltage monitor started')
    
    # List all available tags
    tags = ctx.list_tags('IED1')
    ctx.log('info', f'Found {len(tags)} signals')
```

### Running Scripts

#### Run Mode (F5)
- Executes the script without debugging
- Fast execution
- View output in console
- Good for testing finished scripts

#### Debug Mode (F9)
- Runs with full debugger support
- Pauses at breakpoints
- Shows variable values
- Step through code line by line

## Debugging Workflow

### 1. Set Breakpoints
- Click in the line number margin (left side)
- Red circle indicates active breakpoint
- Click again to remove

### 2. Start Debugging (F9)
- Script runs until first breakpoint
- Execution line highlighted in yellow
- Variables panel shows current values

### 3. Inspect State
- **Variables Tab**: See all local variables
- **Stack Tab**: View call hierarchy
- **Watch Tab**: Add expressions to monitor
- **Console**: View output and logs

### 4. Control Execution
- **Continue (F8)**: Run to next breakpoint
- **Step Over (F10)**: Execute current line, stay in same function
- **Step Into (F11)**: Enter function calls
- **Step Out (Shift+F11)**: Finish current function and return
- **Stop (Shift+F5)**: Terminate execution

### 5. Fix and Repeat
- Edit code while paused (changes apply after restart)
- Remove breakpoints you don't need
- Add watch expressions for key variables

## Script Context API

The `ctx` object provides access to SCADA Scout functionality:

### Reading Data

```python
# Get cached value (fast, non-blocking)
value = ctx.get('DeviceName::SignalAddress', default=0)

# Force read from device (slower, may block)
value = ctx.read('DeviceName::SignalAddress')
```

### Writing Data

```python
# Write to Modbus register
success = ctx.set('ModbusDevice::1:3:40001', 100)

# Write to IEC 61850 data attribute
success = ctx.set('IED::LD/GGIO1.AnIn1.mag.f', 42.5)
```

### IEC 61850 Controls

```python
# Simple control (automatic SBO workflow)
success = ctx.send_command('IED::LD/CSWI1.Pos', True)  # Close breaker

# Control with custom parameters
params = {
    'sbo_timeout': 150,  # milliseconds
    'originator_id': 'SCADA_AUTO'
}
success = ctx.send_command('IED::LD/CSWI1.Pos', False, params)  # Open breaker
```

### Listing Available Tags

```python
# All tags from all devices
all_tags = ctx.list_tags()

# Tags from specific device
ied_tags = ctx.list_tags('IED1')

# Print first 10
for tag in all_tags[:10]:
    print(tag)
```

### Logging

```python
ctx.log('info', 'Normal operation')
ctx.log('warning', 'Threshold exceeded')
ctx.log('error', 'Connection lost')
```

### Variables (Advanced)

```python
# Bind a variable to continuously monitor a tag
ctx.bind_variable('voltage', 'IED1::Voltage', mode='continuous', interval_ms=100)

# Access the variable
v = ctx.var('voltage')
if v:
    print(f"Value: {v.value}, Quality: {v.quality}")

# Unbind when done
ctx.unbind_variable('voltage')
```

## Tag Address Format

Tags use the format: `DeviceName::SignalAddress`

### IEC 61850 Examples
```
IED1::simpleIOGenericIO/GGIO1.SPCSO1.stVal
IED1::LD0/LLN0.Mod.stVal
IED1::simpleIOGenericIO/CSWI1.Pos
```

### Modbus Examples
```
ModbusSlave::1:3:40001    # Unit 1, Function 3, Address 40001
ModbusSlave::1:4:10001    # Unit 1, Function 4, Address 10001
Simulator::holding:40010   # Named register set
```

### OPC UA Examples
```
OPCUA_Server::ns=2;s=Temperature
OPCUA_Server::ns=3;i=1234
```

## Keyboard Shortcuts

### File Operations
- **Ctrl+N** - New script
- **Ctrl+O** - Open script
- **Ctrl+S** - Save script
- **Ctrl+Shift+S** - Save as...
- **Ctrl+W** - Close window

### Editing
- **Ctrl+Z** - Undo
- **Ctrl+Y** / **Ctrl+Shift+Z** - Redo
- **Ctrl+F** - Find (coming soon)

### Debugging
- **F5** - Run without debugging
- **F9** - Start debugging
- **Shift+F5** - Stop execution
- **F8** - Continue
- **F10** - Step over
- **F11** - Step into
- **Shift+F11** - Step out

## Tips and Best Practices

### 1. Use Breakpoints Strategically
- Set breakpoints at decision points (if/else)
- Use conditional breakpoints for specific cases
- Remove old breakpoints to avoid confusion

### 2. Watch Key Variables
- Add important values to Watch panel
- Monitor expressions, not just variables
- Example: `voltage > 240` to watch a condition

### 3. Leverage the Console
- Use `ctx.log()` for production logging
- Use `print()` for debugging (appears in console)
- Check console for exceptions and errors

### 4. Organize Your Scripts
- Save scripts in `scripts/` folder for easy access
- Use descriptive filenames
- Comment your code
- Use `def tick(ctx)` for continuous scripts
- Use `def main(ctx)` for one-shot operations

### 5. Test Incrementally
- Write small functions and test them
- Use debug mode to verify logic
- Run mode for final testing

### 6. Handle Errors Gracefully
```python
def tick(ctx):
    try:
        value = ctx.read('Device::Signal')
        # Process value...
    except Exception as e:
        ctx.log('error', f'Failed to read: {e}')
```

### 7. Check Connection State
```python
def main(ctx):
    tags = ctx.list_tags('IED1')
    if not tags:
        ctx.log('error', 'IED1 not connected or no signals available')
        return
    # Proceed with operations...
```

## Example Scripts

### Voltage Monitor with Alarms
```python
VOLTAGE_MIN = 220
VOLTAGE_MAX = 240
CHECK_INTERVAL = 1.0  # seconds

def tick(ctx):
    """Monitor voltage and trigger alarms."""
    voltage = ctx.get('IED1::Voltage', 0)
    
    if voltage < VOLTAGE_MIN:
        ctx.log('warning', f'Low voltage: {voltage}V')
        ctx.set('Alarms::LowVoltage', True)
    elif voltage > VOLTAGE_MAX:
        ctx.log('warning', f'High voltage: {voltage}V')
        ctx.set('Alarms::HighVoltage', True)
    else:
        # Normal range - clear alarms
        ctx.set('Alarms::LowVoltage', False)
        ctx.set('Alarms::HighVoltage', False)
```

### Circuit Breaker Control Logic
```python
def main(ctx):
    """Close breaker if conditions are met."""
    # Check prerequisites
    voltage = ctx.get('IED1::BusVoltage', 0)
    frequency = ctx.get('IED1::Frequency', 0)
    
    if voltage < 200 or voltage > 250:
        ctx.log('error', 'Voltage out of range, cannot close breaker')
        return False
    
    if frequency < 59.5 or frequency > 60.5:
        ctx.log('error', 'Frequency out of range, cannot close breaker')
        return False
    
    # Send close command
    ctx.log('info', 'Closing circuit breaker...')
    success = ctx.send_command('IED1::CB1.Pos', True)
    
    if success:
        ctx.log('info', 'Breaker closed successfully')
    else:
        ctx.log('error', 'Failed to close breaker')
    
    return success
```

### Data Logger
```python
import time
from datetime import datetime

LOG_FILE = 'logs/voltage_log.csv'
LOG_INTERVAL = 60  # seconds

last_log_time = 0

def tick(ctx):
    """Log voltage readings periodically."""
    global last_log_time
    
    current_time = time.time()
    
    # Check if it's time to log
    if current_time - last_log_time < LOG_INTERVAL:
        return
    
    last_log_time = current_time
    
    # Read values
    voltage = ctx.get('IED1::Voltage', 0)
    current = ctx.get('IED1::Current', 0)
    power = ctx.get('IED1::Power', 0)
    
    # Write to file
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f'{timestamp},{voltage},{current},{power}\n')
    
    ctx.log('info', f'Logged: V={voltage}, I={current}, P={power}')
```

## Troubleshooting

### Script Won't Run
- Check for syntax errors (red underlines)
- Verify device is connected
- Check tag addresses are correct
- Look at console for error messages

### Breakpoints Not Hit
- Ensure breakpoint is on an executable line (not comments/blank lines)
- Check if code path actually reaches that line
- Verify debugging mode is active (F9, not F5)

### Variables Not Showing
- Make sure script is paused at breakpoint
- Check Variables tab is selected
- Local variables only show in current scope

### Slow Execution
- Use `ctx.get()` instead of `ctx.read()` when possible
- Reduce tick interval if running continuously
- Check network latency to devices

### Import Errors
- Scripts run from `scripts/` directory
- Use relative imports for local modules
- Install packages in SCADA Scout virtual environment

## Advanced Topics

### Working with External Files

```python
import os
import json

def main(ctx):
    # Read configuration
    config_path = os.path.join('scripts', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Use configuration
    threshold = config.get('threshold', 100)
    ctx.log('info', f'Threshold: {threshold}')
```

### Creating Reusable Functions

```python
def read_all_voltages(ctx, device_name):
    """Helper function to read all voltage signals."""
    tags = ctx.list_tags(device_name)
    voltages = {}
    
    for tag in tags:
        if 'voltage' in tag.lower():
            value = ctx.get(tag)
            voltages[tag] = value
    
    return voltages

def main(ctx):
    voltages = read_all_voltages(ctx, 'IED1')
    for tag, value in voltages.items():
        ctx.log('info', f'{tag} = {value}V')
```

### State Machine Pattern

```python
class BreakerController:
    STATE_IDLE = 0
    STATE_CLOSING = 1
    STATE_CLOSED = 2
    STATE_OPENING = 3
    STATE_FAULT = 4
    
    def __init__(self):
        self.state = self.STATE_IDLE
        self.retry_count = 0
    
    def update(self, ctx):
        if self.state == self.STATE_IDLE:
            # Wait for command...
            pass
        elif self.state == self.STATE_CLOSING:
            success = ctx.send_command('IED::CB1.Pos', True)
            if success:
                self.state = self.STATE_CLOSED
            else:
                self.retry_count += 1
                if self.retry_count > 3:
                    self.state = self.STATE_FAULT

# Global instance
controller = BreakerController()

def tick(ctx):
    controller.update(ctx)
```

## Comparison with Triangle DTM Insight

If you're familiar with Triangle MicroWorks DTM Insight JS environment, here's how Script IDE compares:

| Feature | DTM Insight JS | SCADA Scout Script IDE |
|---------|----------------|------------------------|
| Language | JavaScript | Python |
| Debugger | ✓ | ✓ |
| Breakpoints | ✓ | ✓ |
| Step Execution | ✓ | ✓ |
| Variable Inspection | ✓ | ✓ |
| Watch Expressions | ✓ | ✓ |
| Syntax Highlighting | ✓ | ✓ |
| Line Numbers | ✓ | ✓ |
| File Management | ✓ | ✓ |
| Protocol Access | IEC 61850 | IEC 61850, Modbus, OPC UA |
| Continuous Scripts | ✓ | ✓ (tick/loop) |
| One-shot Scripts | ✓ | ✓ (main) |

### Migration Tips from DTM Insight

**JavaScript → Python Syntax Changes:**
```javascript
// DTM Insight JS
var voltage = device.getValue("path");
if (voltage > 100) {
    console.log("High voltage");
}

# SCADA Scout Python
voltage = ctx.get("Device::path")
if voltage > 100:
    ctx.log('info', "High voltage")
```

**Loop Patterns:**
```javascript
// DTM Insight - tick function
function tick() {
    // Called repeatedly
}

# SCADA Scout - tick function
def tick(ctx):
    # Called repeatedly
    pass
```

## Support and Resources

- **Scripting Guide**: View → Help → Scripting Guide (Shift+F1)
- **Documentation**: Help → Documentation (F1)
- **Examples**: Help → Load Examples in Script IDE
- **GitHub**: Check issues and discussions
- **Event Log**: View → Event Log for runtime messages

## Future Enhancements

Planned features:
- [ ] Code completion for ctx methods
- [ ] Integrated search/replace
- [ ] Multiple file tabs
- [ ] Git integration
- [ ] Performance profiling
- [ ] Remote debugging
- [ ] Unit test framework

---

**Happy Scripting! 🚀**
