# IEC 61850 SBO Control Fixes and Enhancements

## Date: 2026-01-24

## Summary
Fixed IEC 61850 Select Before Operate (SBO) functionality and added comprehensive script support for IEC 61850 control operations.

## Changes Made

### 1. Fixed SBO Availability Check (`adapter.py`)
**Location:** `src/protocols/iec61850/adapter.py`, line ~1415-1434

**Problem:** The code was trying to read SBO/SBOw as a boolean value, but these are structural types in IEC 61850, not simple booleans. This caused the SBO availability check to fail.

**Fix:** Changed from `IedConnection_readBooleanValue` to `IedConnection_readObject` to properly check if the SBO/SBOw structure exists:

```python
# Before (incorrect):
test_val, test_err = iec61850.IedConnection_readBooleanValue(
    self.connection, ctx.sbo_reference, iec61850.IEC61850_FC_CO
)
if test_err == iec61850.IED_ERROR_OK:
    sbo_available = True

# After (correct):
test_val = iec61850.IedConnection_readObject(
    self.connection, ctx.sbo_reference, iec61850.IEC61850_FC_CO
)
if test_val:
    sbo_available = True
    iec61850.MmsValue_delete(test_val)
```

### 2. Enhanced Fallback SBO SELECT Method (`adapter.py`)
**Location:** `src/protocols/iec61850/adapter.py`, `_fallback_select()` method

**Problem:** The fallback method was writing a simple boolean value to .SBO/.SBOw, but IEC 61850 requires a full structure (similar to Operate structure) for proper SBO operation.

**Fix:** Modified `_fallback_select()` to:
- Use `_build_operate_struct()` to create a proper 7-element structure
- Update control context state after successful SELECT
- Try both .SBOw (enhanced) and .SBO (normal) automatically

### 3. Enhanced Fallback OPERATE Method (`adapter.py`)
**Location:** `src/protocols/iec61850/adapter.py`, `_fallback_operate()` method

**Improvements:**
- Try both `.Oper` (with full structure) and `.Oper.ctlVal` (with simple value)
- Update control context state and increment ctlNum after successful operation
- Better error handling and logging

### 4. Added Script Support for IEC 61850 Controls (`script_runtime.py`)
**Location:** `src/core/script_runtime.py`, `ScriptContext` class

**New Method:** `send_command(tag_address, value, params=None)`

This method allows Python scripts to perform IEC 61850 control operations with automatic SBO workflow handling.

**Features:**
- Automatically detects if control requires SBO workflow
- Handles SELECT -> wait -> OPERATE sequence transparently
- Supports custom parameters:
  - `sbo_timeout`: Time to wait between SELECT and OPERATE (default 100ms)
  - `originator_id`: Custom originator identifier (default "SCADA")
  - `originator_cat`: Originator category (default 3 = Remote)
- Falls back to regular write for non-IEC61850 protocols

**Example Usage:**
```python
def tick(ctx):
    # Simple control - SBO handled automatically
    success = ctx.send_command('IED1::CTRL/CSWI1.Pos', True)
    
    # With custom parameters
    params = {'sbo_timeout': 200, 'originator_id': 'SCADA_MASTER'}
    ctx.send_command('IED1::CTRL/CSWI1.Pos', False, params=params)
```

### 5. Updated Script Editor with Examples (`python_script_dialog.py`)
**Location:** `src/ui/dialogs/python_script_dialog.py`

**Changes:**
- Updated placeholder text to mention `send_command()` method
- Enhanced default example script with IEC 61850 control examples
- Added comprehensive comments explaining SBO workflow
- Included examples for:
  - Simple control operations
  - Custom SBO parameters
  - External IED control
  - Simulated IED control
  - One-shot scripts
  - Continuous monitoring and control

### 6. Created Comprehensive Example File
**Location:** `examples/iec61850_sbo_control_examples.py`

Contains 8 detailed examples covering:
1. Simple circuit breaker control
2. Custom SBO timeout usage
3. Sequential control of multiple breakers
4. External client control
5. Simulated IED control
6. Continuous monitoring and control
7. One-shot control scripts
8. Error handling and retry logic

## How SBO Works Now

### Automatic SBO Workflow
When you call `adapter.send_command()` or `ctx.send_command()`:

1. **Detection**: System checks if the control object has `ctlModel=2` (SBO Normal) or `ctlModel=4` (SBO Enhanced)

2. **Availability Check**: Verifies that .SBO or .SBOw attributes exist on the IED

3. **SELECT Phase**:
   - Creates ControlObjectClient (or uses fallback)
   - Calls `ControlObjectClient_select()` or `selectWithValue()` (for enhanced)
   - Fallback: Writes full structure to `.SBO` or `.SBOw`

4. **Wait Period**: Waits for SBO timeout (default 100ms, configurable)

5. **OPERATE Phase**:
   - Calls `ControlObjectClient_operate()` with control value
   - Fallback: Writes full structure to `.Oper` or simple value to `.Oper.ctlVal`
   - Increments ctlNum for next operation

6. **Status Update**: Updates control context state and logs results

### Direct Control
For controls with `ctlModel=1` (Direct Normal) or `ctlModel=3` (Direct Enhanced):
- Skips SELECT phase
- Directly calls OPERATE
- Still handles proper structure construction and ctlNum management

## Testing

### For External IEDs:
1. Connect to your IED (File > Connect to IED)
2. Browse to find control points (typically in .../CSWI or .../XCBR)
3. Use Control Dialog (right-click > Control) to test manual operation
4. Try script control using examples in `examples/iec61850_sbo_control_examples.py`

### For Simulated IEDs:
1. Create simulated IED (Tools > Simulate IED)
2. Load an ICD file with control objects
3. Browse the simulated IED to see control points
4. Test with script or Control Dialog

### Script Testing:
1. Open Python Scripts (Tools > Python Scripts)
2. Copy an example from `examples/iec61850_sbo_control_examples.py`
3. Replace device/address with your actual tags (use Ctrl+Space for completion)
4. Click "Run Once" or "Start Continuous"
5. Monitor Event Log for detailed SBO workflow messages

## Event Log Messages
The system now provides detailed logging for SBO operations:

```
→ SEND_COMMAND IED$CSWI$Pos = True
SBO Mode detected (SBO_NORMAL). Starting SBO sequence...
  → SELECT IED$CSWI$Pos.SBO.ctlVal
  ← SELECT SUCCESS
  Waiting 100ms for SBO timeout...
  → OPERATE IED$CSWI$Pos.Oper.ctlVal
  ← OPERATE SUCCESS
← SBO SEQUENCE COMPLETE
```

## Troubleshooting

### Issue: SBO not available despite ctlModel=2/4
**Solution:** System automatically falls back to direct control. Check IED configuration to ensure .SBO/.SBOw attributes are present.

### Issue: ControlObjectClient_create fails
**Solution:** System uses fallback methods automatically. This can happen with:
- Incompatible IED implementations
- Network timeouts
- Non-standard control configurations

### Issue: SELECT succeeds but OPERATE fails
**Possible causes:**
- SBO timeout too short (increase with `sbo_timeout` parameter)
- ctlNum mismatch (system auto-handles, but check IED logs)
- IED rejected operation (check IED permissions/interlocks)

### Issue: Script control not working
**Checklist:**
1. Device connected? (check device tree)
2. Control point address correct? (use Ctrl+Space for completion)
3. Control model supports control? (status-only = ctlModel 0 cannot be controlled)
4. Check Event Log for detailed error messages

## Related Files
- `src/protocols/iec61850/adapter.py` - Main SBO implementation
- `src/core/script_runtime.py` - Script API
- `src/ui/dialogs/python_script_dialog.py` - Script editor
- `src/ui/dialogs/control_dialog.py` - Manual control dialog
- `src/protocols/iec61850/control_models.py` - Control data structures
- `examples/iec61850_sbo_control_examples.py` - Usage examples

## API Reference

### ctx.send_command(tag_address, value, params=None)

**Parameters:**
- `tag_address` (str): Unique tag address in format "DeviceName::SignalAddress"
- `value` (Any): Control value (typically bool for switches, but can be int/float)
- `params` (dict, optional): Control parameters
  - `sbo_timeout` (int): Milliseconds to wait between SELECT and OPERATE (default: 100)
  - `originator_id` (str): Originator identifier string (default: "SCADA")
  - `originator_cat` (int): Originator category (default: 3 = Remote)

**Returns:**
- `bool`: True if command succeeded, False otherwise

**Example:**
```python
# Simple usage
success = ctx.send_command('IED1::CTRL/CSWI1.Pos', True)

# With parameters
success = ctx.send_command(
    'IED1::CTRL/CSWI1.Pos', 
    False, 
    params={'sbo_timeout': 200, 'originator_id': 'SCRIPT_AUTO'}
)
```

## Future Enhancements
- Add support for time-activated controls (operTm parameter)
- Add support for Test mode operations
- Enhanced originator configuration in UI
- Control command queuing for sequential operations
- Control history/audit log
