# SBO/Operate Fix Summary - January 17, 2026

## Problem Identified

The original SCADA Scout implementation was **manually building MmsValue structures** and writing directly to `.SBO`, `.SBOw`, and `.Oper` attributes. This approach had several issues:

1. **Manual structure building** - Creating 7-element MmsValue structures with ctlVal, operTm, origin, ctlNum, T, Test, and Check
2. **Manual ctlNum tracking** - Incrementing control numbers manually
3. **Manual timestamp generation** - Creating UTC timestamps manually
4. **Direct attribute writes** - Using `IedConnection_writeObject()` to write to control attributes

This approach was **error-prone** and **not following the libiec61850 standard pattern**.

## Root Cause

After examining the [keyvdir/pyiec61850](https://github.com/keyvdir/pyiec61850) repository and the official [mz-automation/libiec61850](https://github.com/mz-automation/libiec61850) C library examples, it became clear that:

**The proper way to perform SBO and operate is to use the `ControlObjectClient` API.**

## Solution Implemented

### Updated Files

1. **`src/protocols/iec61850/adapter.py`**
   - Completely refactored `select()` method
   - Completely refactored `operate()` method
   - Now uses `ControlObjectClient` API pattern

2. **`src/protocols/iec61850/iec61850_wrapper.py`**
   - Added `ControlObjectClient_getControlModel()`
   - Added `ControlObjectClient_selectWithValue()`
   - Added `ControlObjectClient_getLastError()`
   - All wrapper functions properly defined with ctypes

### New Implementation Pattern

#### SELECT Phase (SBO Normal):
```python
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
ctl_model = iec61850.ControlObjectClient_getControlModel(control_client)
success = iec61850.ControlObjectClient_select(control_client)
iec61850.ControlObjectClient_destroy(control_client)
```

#### SELECT Phase (SBO Enhanced):
```python
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
mms_val = iec61850.MmsValue_newBoolean(value)
success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_val)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

#### OPERATE Phase:
```python
control_client = iec61850.ControlObjectClient_create(object_ref, connection)
iec61850.ControlObjectClient_setOriginator(control_client, "SCADA", 3)
mms_val = iec61850.MmsValue_newBoolean(value)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

## Key Improvements

### ✅ Automatic Protocol Handling
- Library automatically builds correct MmsValue structures
- Library manages ctlNum incrementing
- Library handles timestamp generation
- Library manages all protocol state

### ✅ Control Model Detection
- Automatically detects ctlModel from IED
- Supports STATUS_ONLY (0), DIRECT_NORMAL (1), SBO_NORMAL (2), DIRECT_ENHANCED (3), SBO_ENHANCED (4)
- Automatically chooses between `select()` and `selectWithValue()`

### ✅ Error Handling
- Uses `ControlObjectClient_getLastError()` for detailed error codes
- No more manual error checking of writeObject results

### ✅ Simplified Code
- Removed ~200 lines of manual structure building code
- Removed `_build_operate_struct()` method
- Removed manual ctlNum tracking
- Removed manual timestamp generation

## What Was Wrong Before

```python
# OLD (INCORRECT) PATTERN
struct = iec61850.MmsValue_newStructure(7)
iec61850.MmsValue_setElement(struct, 0, iec61850.MmsValue_newBoolean(value))  # ctlVal
iec61850.MmsValue_setElement(struct, 1, iec61850.MmsValue_newUtcTimeMs(now_ms))  # operTm
# ... manually build 5 more elements ...
err = iec61850.IedConnection_writeObject(connection, "CSWI1.Pos.SBO", iec61850.IEC61850_FC_CO, struct)
```

## What Is Correct Now

```python
# NEW (CORRECT) PATTERN
control_client = iec61850.ControlObjectClient_create("CSWI1.Pos", connection)
success = iec61850.ControlObjectClient_select(control_client)
iec61850.ControlObjectClient_destroy(control_client)
```

## Testing

### Test Files Created
1. `test_wrapper_functions.py` - Validates all new wrapper functions are available
2. `test_sbo_api_pattern.py` - Demonstrates the proper API usage pattern

### Validation
```bash
$ python3 test_wrapper_functions.py
Testing wrapper functions...
ControlObjectClient_create: True
ControlObjectClient_getControlModel: True
ControlObjectClient_select: True
ControlObjectClient_selectWithValue: True
ControlObjectClient_operate: True
ControlObjectClient_getLastError: True
ControlObjectClient_destroy: True
ControlObjectClient_setOriginator: True

All wrapper functions available!
```

## References

### libiec61850 C Examples
- [client_example_control.c](https://github.com/mz-automation/libiec61850/blob/main/examples/iec61850_client_example_control/client_example_control.c)
  ```c
  // Line 104-110: SBO Normal pattern
  control = ControlObjectClient_create("simpleIOGenericIO/GGIO1.SPCSO2", con);
  if (ControlObjectClient_select(control)) {
      ctlVal = MmsValue_newBoolean(true);
      if (ControlObjectClient_operate(control, ctlVal, 0)) {
          printf("operated successfully\n");
      }
  }
  ```

- [client_example_control.c](https://github.com/mz-automation/libiec61850/blob/main/examples/iec61850_client_example_control/client_example_control.c)
  ```c
  // Line 177-188: SBO Enhanced pattern
  control = ControlObjectClient_create("simpleIOGenericIO/GGIO1.SPCSO4", con);
  ctlVal = MmsValue_newBoolean(true);
  if (ControlObjectClient_selectWithValue(control, ctlVal)) {
      if (ControlObjectClient_operate(control, ctlVal, 0)) {
          printf("operated successfully\n");
      }
  }
  ```

### Python Examples
- [keyvdir/pyiec61850](https://github.com/keyvdir/pyiec61850) - Python bindings for libiec61850

## Impact

### Code Simplification
- **Removed**: ~200 lines of manual structure building
- **Removed**: ctlNum tracking logic
- **Removed**: Manual timestamp generation
- **Added**: ~150 lines of clean, standard API calls

### Reliability
- ✅ Follows official libiec61850 patterns
- ✅ Library-managed protocol state
- ✅ Automatic error handling
- ✅ Better IED compatibility

### Maintainability
- ✅ Less code to maintain
- ✅ Standard API patterns
- ✅ Better aligned with examples
- ✅ Easier to debug

## Next Steps

1. Test with your real IED at 172.16.11.18:102
2. Verify SBO workflow works correctly
3. Test both SBO_NORMAL and SBO_ENHANCED control models
4. Validate with different IED vendors

## Conclusion

The fix replaces the manual, error-prone structure building approach with the proper `ControlObjectClient` API as demonstrated in the official libiec61850 examples. This results in:

- **Simpler code** (200+ lines removed)
- **More reliable operation** (library handles protocol details)
- **Better compatibility** (follows standard patterns)
- **Easier maintenance** (standard API usage)

The implementation now matches the patterns shown in:
- libiec61850 C examples
- pyiec61850 Python bindings
- Official IEC 61850 client documentation
