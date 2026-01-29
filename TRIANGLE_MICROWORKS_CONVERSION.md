# Converting Triangle MicroWorks Scripts to SCADA Scout

## Overview

The JavaScript files (GenDevices.js, GenRun_Edited.js, swgDevices.js) were originally written for **Triangle MicroWorks DTM Insight Java environment**, which is a completely different SCADA simulation platform from SCADA Scout.

These scripts **cannot run directly** in SCADA Scout because:
1. They use Triangle MicroWorks-specific APIs (FindNode, AddFolder, MBCreateOutstationChannelConfig, etc.)
2. They're written in JavaScript, while SCADA Scout uses Python
3. They're designed for creating Modbus slave devices in a simulation environment, not for interacting with existing devices

## What Has Been Converted

### 1. Device Setup Scripts (✓ Complete)

**Original:** GenDevices.js, swgDevices.js  
**Converted to:**
- `scripts/gen_devices_setup.py` - Adds 22 generator devices (G1-G22)
- `scripts/swg_devices_setup.py` - Adds 4 switchgear devices (GPS1-GPS4)

**How to use:**
1. Open SCADA Scout
2. Go to Scripts window
3. Add script by importing the Python file
4. Run once with `main(ctx)` to add all devices to DeviceManager
5. Connect to devices from the Device Manager window

### 2. Generator Simulation Script (⚠️ Template Only)

**Original:** GenRun_Edited.js (1367 lines of complex generator/switchgear simulation)  
**Converted to:** `scripts/gen_simulation_template.py` (simplified template)

**What's included in the template:**
- Basic GeneratorController class with state machine
- Simple voltage/frequency/power ramping logic
- Modbus register read/write structure
- Example of continuous tick() execution
- Placeholder for SwitchgearController

**What's NOT included (would require significant work):**
- 100+ SSL (Signal Status Logic) flags
- Complex load sharing between generators
- Fast transfer logic
- Detailed fault injection and handling
- Switchgear coordination algorithms
- All the timing and synchronization logic
- Bus monitoring and dead bus detection
- Complete Modbus register mappings from Gen_Registers.csv

## Register Mapping Reference

The **Gen_Registers.csv** file defines the Modbus register layout used by the original scripts. You'll need to map these to actual SCADA Scout register addresses:

```
Format: IsEnabled, Index, PointType, Name, Description, Direction, Value, Quality
Example: True,0,4,R000,,None,0,0

PointType values:
- 4 = Holding Register (read/write)
```

In SCADA Scout, Modbus addresses use format: `unit:function:address`
- Unit: Modbus unit/slave ID (usually 1)
- Function: 3 = Read Holding Registers, 6 = Write Single Register, 16 = Write Multiple
- Address: Register address (40001-49999 for holding registers)

Example mapping:
- Original: R000 (index 0)
- SCADA Scout: `G1::1:3:40000` (device G1, unit 1, function 3, register 40000)

## sbo.pcapng File

This is a **Wireshark packet capture** file containing IEC 61850 SBO (Select Before Operate) protocol traffic. It cannot be "run" as a script - it's network traffic analysis data.

**How to use:**
1. Open with Wireshark or similar packet analyzer
2. Analyze IEC 61850 protocol sequences
3. Use as reference for understanding SBO control flows
4. See SCADA Scout's existing IEC 61850 examples in `scripts/iec61850_sbo_toggle.py`

## How to Add Scripts to SCADA Scout

### Method 1: Add to user_scripts.json

Edit `/home/majid/Documents/scada_scout/user_scripts.json`:

```json
{
  "name": "Setup Generators (G1-G22)",
  "code": "from scripts.gen_devices_setup import main as _main\\ndef main(ctx):\\n    return _main(ctx)",
  "interval": 0.5
}
```

### Method 2: Use the UI

1. Open SCADA Scout
2. Click Scripts window
3. Click "Add Script" or "Import Script"
4. Select the Python file
5. Configure run mode (one-shot or continuous)

## Complete Conversion Checklist

If you need full functionality of GenRun_Edited.js, you would need to:

- [ ] Convert all state machine logic (STANDSTILL, STARTING, RUNNING, SHUTDOWN, FAULT, FAST_TRANSFER)
- [ ] Implement all SSL flags (100+ boolean signals)
- [ ] Implement complete ramping logic for voltage/frequency/power
- [ ] Add load sharing algorithm between generators
- [ ] Implement fast transfer coordination
- [ ] Add fault detection and handling
- [ ] Implement switchgear bus monitoring
- [ ] Map all Modbus registers from Gen_Registers.csv
- [ ] Test with actual devices
- [ ] Handle timing and synchronization properly
- [ ] Add dead bus detection (7-second window)
- [ ] Implement blackout detection and recovery

**Estimated effort:** 40-80 hours of development and testing

## Quick Start Guide

### Step 1: Add Devices
```bash
# In SCADA Scout Scripts window, run:
from scripts.gen_devices_setup import main
# This adds G1-G22

from scripts.swg_devices_setup import main
# This adds GPS1-GPS4
```

### Step 2: Connect to Devices
- Open Device Manager window
- Select devices (G1, G2, etc.)
- Click "Connect"
- Devices should show as connected if the Modbus servers are running

### Step 3: Monitor/Control
- Use Watch List to add specific registers
- Read values: `G1::1:3:40001`
- Write values: Use set() in scripts or write directly in UI

### Step 4: (Optional) Start Simulation
- If you have actual Modbus slave devices running
- Configure gen_simulation_template.py with correct register mappings
- Enable continuous execution of the simulation script

## Support Files Reference

| File | Purpose | Can Run in SCADA Scout? |
|------|---------|------------------------|
| GenDevices.js | Device setup (Triangle MW) | ❌ No - Converted to Python |
| swgDevices.js | Switchgear setup (Triangle MW) | ❌ No - Converted to Python |
| GenRun_Edited.js | Generator simulation (Triangle MW) | ❌ No - Template provided |
| Gen_Registers.csv | Register definitions | ℹ️ Reference only |
| sbo.pcapng | Packet capture | ℹ️ Analysis only (Wireshark) |

## Getting Help

For SCADA Scout-specific questions:
- Check `examples/` directory for working script examples
- See `QUICK_START_CONTROL.md` for IEC 61850 control examples
- Read `.github/copilot-instructions.md` for architecture details
- Look at existing scripts in `scripts/` directory

For conversion questions:
- Refer to this guide
- Compare original JavaScript with Python templates
- Test incrementally with small portions
