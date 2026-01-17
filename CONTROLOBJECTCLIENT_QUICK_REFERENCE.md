# Quick Reference: ControlObjectClient API

## Basic Pattern

```python
from src.protocols.iec61850 import iec61850_wrapper as iec61850

# 1. Create control client
control_client = iec61850.ControlObjectClient_create(object_ref, connection)

# 2. Check control model (optional)
ctl_model = iec61850.ControlObjectClient_getControlModel(control_client)
# 0 = STATUS_ONLY
# 1 = DIRECT_NORMAL
# 2 = SBO_NORMAL
# 3 = DIRECT_ENHANCED  
# 4 = SBO_ENHANCED

# 3. Set originator (optional)
iec61850.ControlObjectClient_setOriginator(control_client, "SCADA", 3)

# 4. Perform control action
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
iec61850.MmsValue_delete(mms_val)

# 5. Clean up
iec61850.ControlObjectClient_destroy(control_client)
```

## Control Models

| Value | Model | Description | SELECT Required? |
|-------|-------|-------------|------------------|
| 0 | STATUS_ONLY | Read-only status | No control possible |
| 1 | DIRECT_NORMAL | Direct control | No |
| 2 | SBO_NORMAL | Select Before Operate | Yes - use `select()` |
| 3 | DIRECT_ENHANCED | Direct with security | No |
| 4 | SBO_ENHANCED | SBO with value check | Yes - use `selectWithValue()` |

## Common Patterns

### Direct Control (Model 1 or 3)
```python
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

### SBO Normal (Model 2)
```python
# SELECT
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
success = iec61850.ControlObjectClient_select(control_client)
iec61850.ControlObjectClient_destroy(control_client)

# Wait (optional)
time.sleep(0.1)

# OPERATE
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

### SBO Enhanced (Model 4)
```python
# SELECT WITH VALUE
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_val)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)

# Wait (optional)
time.sleep(0.1)

# OPERATE
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

## Available Functions

### Creation/Destruction
- `ControlObjectClient_create(object_ref, connection)` - Create client
- `ControlObjectClient_destroy(client)` - Destroy client

### Control Actions
- `ControlObjectClient_select(client)` - SELECT for SBO_NORMAL
- `ControlObjectClient_selectWithValue(client, mms_val)` - SELECT for SBO_ENHANCED
- `ControlObjectClient_operate(client, mms_val, oper_time)` - OPERATE
- `ControlObjectClient_cancel(client)` - Cancel selection

### Configuration
- `ControlObjectClient_setOriginator(client, identity, category)` - Set originator
- `ControlObjectClient_setInterlockCheck(client, value)` - Set interlock check
- `ControlObjectClient_setSynchroCheck(client, value)` - Set synchro check
- `ControlObjectClient_setTestMode(client, value)` - Set test mode

### Information
- `ControlObjectClient_getControlModel(client)` - Get control model (0-4)
- `ControlObjectClient_getLastError(client)` - Get last error code

## Originator Categories

| Value | Category | Description |
|-------|----------|-------------|
| 0 | NOT_SUPPORTED | Not supported |
| 1 | BAY_CONTROL | Bay control |
| 2 | STATION_CONTROL | Station control |
| 3 | REMOTE_CONTROL | Remote control (SCADA) |
| 4 | AUTOMATIC_BAY | Automatic bay |
| 5 | AUTOMATIC_STATION | Automatic station |
| 6 | AUTOMATIC_REMOTE | Automatic remote |
| 7 | MAINTENANCE | Maintenance |
| 8 | PROCESS | Process |

## Error Handling

```python
control_client = iec61850.ControlObjectClient_create(object_ref, connection)

if not control_client:
    print("Failed to create control client")
    return False

try:
    success = iec61850.ControlObjectClient_operate(client, mms_val, 0)
    
    if not success:
        error_code = iec61850.ControlObjectClient_getLastError(client)
        print(f"Operation failed with error: {error_code}")
        return False
    
    return True
finally:
    iec61850.ControlObjectClient_destroy(control_client)
```

## Time-Activated Control

```python
# Operate at specific time (operTime in ms since epoch)
import time

# Schedule for 5 seconds in the future
oper_time = int((time.time() + 5) * 1000)

control_client = iec61850.ControlObjectClient_create(object_ref, connection)
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, oper_time)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

## Object References

Control objects are specified by their Data Object reference (without .Oper or .SBO):

```python
# ✅ Correct
object_ref = "IED1LD0/CSWI1.Pos"

# ❌ Wrong
object_ref = "IED1LD0/CSWI1.Pos.Oper"
object_ref = "IED1LD0/CSWI1.Pos.SBO"
object_ref = "IED1LD0/CSWI1.Pos.Oper.ctlVal"
```

The library automatically handles `.Oper`, `.SBO`, and `.SBOw` based on the control model.

## Full Example

```python
from src.protocols.iec61850 import iec61850_wrapper as iec61850

def control_breaker(connection, object_ref, close=True):
    """
    Control a circuit breaker using proper ControlObjectClient API.
    
    Args:
        connection: Active IedConnection
        object_ref: Object reference (e.g., "IED1/CSWI1.Pos")
        close: True to close, False to open
    
    Returns:
        bool: True if successful
    """
    # Create control client
    client = iec61850.ControlObjectClient_create(object_ref, connection)
    if not client:
        print(f"Failed to create control client for {object_ref}")
        return False
    
    try:
        # Get control model
        ctl_model = iec61850.ControlObjectClient_getControlModel(client)
        print(f"Control model: {ctl_model}")
        
        # Set originator
        iec61850.ControlObjectClient_setOriginator(client, "SCADA", 3)
        
        # Handle SBO if needed
        if ctl_model == 2:  # SBO_NORMAL
            if not iec61850.ControlObjectClient_select(client):
                print("SELECT failed")
                return False
            print("SELECT successful")
            
        elif ctl_model == 4:  # SBO_ENHANCED
            mms_val = iec61850.MmsValue_newBoolean(close)
            success = iec61850.ControlObjectClient_selectWithValue(client, mms_val)
            iec61850.MmsValue_delete(mms_val)
            
            if not success:
                print("SELECT WITH VALUE failed")
                return False
            print("SELECT WITH VALUE successful")
        
        # Operate
        mms_val = iec61850.MmsValue_newBoolean(close)
        success = iec61850.ControlObjectClient_operate(client, mms_val, 0)
        iec61850.MmsValue_delete(mms_val)
        
        if success:
            print(f"OPERATE successful - Breaker {'closed' if close else 'opened'}")
            return True
        else:
            error_code = iec61850.ControlObjectClient_getLastError(client)
            print(f"OPERATE failed with error: {error_code}")
            return False
            
    finally:
        iec61850.ControlObjectClient_destroy(client)
```

## Testing

```bash
# Test wrapper functions
python3 test_wrapper_functions.py

# Test pattern demonstration
python3 test_sbo_api_pattern.py
```
