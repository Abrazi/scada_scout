# DUBGG Project - Automated IED Simulation

This directory contains everything needed to automatically instantiate all IED devices from the DUBGG.scd file as running IEC 61850 servers with associated PLC programs.

## Quick Start

### Method 1: Using the GUI

1. Launch SCADA Scout:
   ```bash
   python src/main.py
   ```

2. Go to **Connection → IED Project Manager...**

3. Click **Browse** next to "SCD File" and select `dubgg/DUBGG.scd`

4. Click **Load SCD** - This will parse the file and show all IEDs in the preview table

5. Review the IEDs and their IP addresses

6. Ensure both checkboxes are enabled:
   - ✅ Auto-connect IED servers after creation
   - ✅ Auto-start PLC programs

7. Click **Create IED Servers**

8. Once complete, click **Save as MSS Project...** and save as `DUBGG.mss`

9. All IED servers are now running! Check **Device Explorer** to see them.

### Method 2: Using the Test Script

```bash
python test_dubgg_project.py
```

This will:
- Load and parse DUBGG.scd
- Display all extracted IEDs
- Prompt for confirmation
- Create all IED servers
- Generate and start PLC programs
- Save complete state as DUBGG.mss
- Show running status

Press `y` when prompted to proceed.

## What Happens

### 1. SCD Parsing
The `DUBGG.scd` file is parsed to extract:
- All IED definitions
- IP addresses from Communication section
- Logical device structures
- Manufacturer information

### 2. Server Instantiation
For each IED:
- Creates an IEC 61850 server instance
- Binds to the exact IP address from SCD
- Loads the IED model from SCD
- Registers in Device Explorer
- Auto-connects (if enabled)

### 3. PLC Program Generation
For each IED:
- Generates a Structured Text (.st) program
- Saves to `plc_programs/PRG_<device>.st`
- Includes template with user sections
- Documents available built-in functions

### 4. Runtime Execution
For each PLC program:
- Starts dedicated execution thread
- Runs cyclically (100ms default)
- Maintains variable state
- Provides IED data access functions

### 5. Project Persistence
All state saved to `DUBGG.mss`:
- Device configurations
- IP bindings
- PLC program associations
- Runtime settings

## Generated Files

After running, you'll have:

```
dubgg/
  └── DUBGG.scd              # Input (existing)

DUBGG.mss                    # Project file (new)

plc_programs/                # Generated PLC programs
  ├── PRG_IED1.st
  ├── PRG_IED2.st
  ├── PRG_IED3.st
  └── ... (one per IED)
```

## Using the Project

### Loading DUBGG.mss

To restore the complete project later:

1. **Via GUI**: Connection → IED Project Manager → Browse MSS → Load Project

2. **Via Code**:
   ```python
   from src.core.ied_project_orchestrator import IEDProjectOrchestrator
   
   orchestrator = IEDProjectOrchestrator(device_manager)
   orchestrator.load_project("DUBGG.mss")
   ```

All IED servers and PLC programs will be restored exactly as saved.

### Viewing Devices

After instantiation, devices appear in **Device Explorer**:
- Each IED as a separate device
- Full signal tree from SCD model
- Real-time value monitoring
- Control operations available

### Editing PLC Programs

PLC programs are in `plc_programs/` directory:

```pascal
PROGRAM PRG_IED1
VAR
    cycle_count: UDINT := 0;
    first_scan: BOOL := TRUE;
    (* Your variables here *)
END_VAR

(* Initialization *)
IF first_scan THEN
    (* Setup code *)
    first_scan := FALSE;
END_IF;

(* Main cyclic execution *)
cycle_count := cycle_count + 1;

(* USER LOGIC SECTION 1: Pre-Processing *)
(* Add your code here *)

(* USER LOGIC SECTION 2: Main Processing *)
(* Add control logic *)

(* USER LOGIC SECTION 3: Post-Processing *)
(* Add outputs *)

END_PROGRAM
```

Edit these files with any text editor. Changes take effect on next load.

### Connecting Clients

IED servers are bound to IP addresses from DUBGG.scd. Connect your IEC 61850 clients to these addresses.

Example: If DUBGG.scd defines IED1 at `192.168.1.10`, connect your client to:
- IP: `192.168.1.10`
- Port: `102` (MMS default)

## File Descriptions

### DUBGG.scd
Original IEC 61850 Substation Configuration Description file containing:
- IED definitions
- Data models
- Communication parameters
- Network topology

**Size**: Typically large (50-500 MB)
**Format**: XML (SCL schema)

### DUBGG.mss
Generated project file containing:
- Project metadata
- Device configurations
- IP address mappings
- PLC program associations
- Runtime settings

**Size**: Small (<100 KB)
**Format**: JSON (human-readable)

### PLC Programs (*.st)
Generated Structured Text programs, one per IED:
- System variables
- User variable sections
- Initialization block
- Main cyclic execution
- Three user logic sections

**Size**: ~10 KB per program
**Format**: IEC 61131-3 Structured Text

## Network Configuration

The system uses IP addresses **exactly as defined** in DUBGG.scd Communication section.

Example from SCD:
```xml
<ConnectedAP iedName="IED1" apName="AP1">
  <Address>
    <P type="IP">192.168.1.10</P>
    <P type="IP-SUBNET">255.255.255.0</P>
    <P type="IP-GATEWAY">192.168.1.1</P>
  </Address>
</ConnectedAP>
```

→ IED1 server will listen on `192.168.1.10:102`

**Important**: Ensure these IP addresses are available on your network adapter or configure virtual adapters.

## PLC Built-in Functions

PLC programs can use these functions:

```pascal
(* Read data from IED *)
value := READ_IED_DATA('IED1', 'LD0/MMXU1$MX$TotW$mag');

(* Write data to IED *)
success := WRITE_IED_DATA('IED1', 'LD0/CSWI1$ST$Pos', TRUE);

(* Send control command *)
success := WRITE_IED_CONTROL('IED1', 'LD0/CSWI1$CO$Pos', TRUE);

(* Log message to event log *)
SCADA_LOG('INFO', 'Control executed successfully');

(* Check if device is connected *)
IF GET_DEVICE_STATUS('IED1') THEN
    (* Device online *)
END_IF;
```

## Troubleshooting

### SCD Won't Load
**Error**: "Failed to load SCD"

**Solutions**:
- Verify `dubgg/DUBGG.scd` exists
- Check file is readable
- Ensure valid XML structure
- Check logs for parsing errors

### No IP Addresses
**Problem**: IEDs show "NO_IP" in preview

**Solutions**:
- DUBGG.scd missing Communication section
- ConnectedAP elements not properly defined
- May need to add Communication section manually

### Server Won't Start
**Error**: "Failed to bind" or "Address in use"

**Solutions**:
- Port 102 already taken by another process
- IP address not available on network adapter
- Another IED already using same IP
- Windows firewall blocking port 102

### PLC Program Won't Run
**Error**: "Failed to load program"

**Solutions**:
- Check program file exists in `plc_programs/`
- Verify device is connected
- Check PLC runtime logs
- Restart PLC runtime engine

## Status Monitoring

### In GUI
- **Device Explorer**: Shows connection status
- **Event Log**: All operations logged
- **Signal Viewer**: Real-time data

### Via Code
```python
# Get project summary
summary = orchestrator.get_project_summary()
print(f"Devices: {summary['instantiated_count']}")
print(f"PLCs: {summary['plc_programs']}")

# Get PLC status
statuses = orchestrator.plc_runtime.get_all_statuses()
for name, status in statuses.items():
    print(f"{name}: {status['cycle_count']} cycles")
```

## Performance

Expected performance with DUBGG.scd:

- **Parsing**: 5-10 seconds (depends on file size)
- **Instantiation**: ~1 second per IED
- **PLC Execution**: 100ms cycle time per program
- **Memory**: ~5-10 MB per IED server
- **CPU**: <1% per PLC program

## System Requirements

- Python 3.8+
- PySide6
- libiec61850 (for IEC 61850 protocol)
- Network adapters with configured IPs
- Port 102 available (or custom port)

## Architecture

```
DUBGG.scd
    ↓
SCDProjectLoader
    ↓
IEDProjectOrchestrator
    ├─→ DeviceManager
    │   ├─→ IED1 Server (Thread)
    │   ├─→ IED2 Server (Thread)
    │   └─→ IED3 Server (Thread)
    │
    ├─→ PLCProgramGenerator
    │   ├─→ PRG_IED1.st
    │   ├─→ PRG_IED2.st
    │   └─→ PRG_IED3.st
    │
    └─→ PLCRuntimeEngine
        ├─→ PRG_IED1 (Thread)
        ├─→ PRG_IED2 (Thread)
        └─→ PRG_IED3 (Thread)
    ↓
DUBGG.mss
```

## Related Documentation

- **Full Guide**: `IED_PROJECT_GUIDE.md`
- **Quick Reference**: `IED_PROJECT_QUICK_REF.md`
- **Implementation**: `IED_PROJECT_IMPLEMENTATION.md`

## Support

For issues:
1. Check Event Log in GUI
2. Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
3. Review generated PLC programs
4. Check network configuration
5. Verify DUBGG.scd structure

## Example Workflow

```bash
# 1. Parse and preview
python test_dubgg_project.py

# 2. Confirm and instantiate
# Follow prompts...

# 3. Monitor status
# (Keep script running)

# 4. Later: Load in GUI
# File → Open Project → DUBGG.mss

# 5. Edit PLC programs
# Edit files in plc_programs/

# 6. Reload project
# File → Open Project → DUBGG.mss
```

## Success Checklist

After running, verify:
- ✅ DUBGG.mss exists in project root
- ✅ `plc_programs/` directory created
- ✅ One .st file per IED
- ✅ Devices visible in Device Explorer
- ✅ All IEDs show "Connected" status
- ✅ Event Log shows successful starts
- ✅ No error messages in console

## Next Steps

1. **Test Connectivity**: Connect IEC 61850 clients to IED IPs
2. **Monitor Signals**: Add IED signals to Watch List
3. **Edit PLCs**: Customize PLC logic in .st files
4. **Configure Gateway**: Map IED signals to other protocols
5. **Save Changes**: File → Save Project

---

**Ready to start?** Run `python test_dubgg_project.py` now!
