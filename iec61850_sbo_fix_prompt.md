# IEC 61850 SBO/Operate Fix - Current Status

## LATEST UPDATE: Silent Select Failure - No Handler Invocation

**Current Issue**: IEDScout shows "Select failed" with NO error messages in either application Event Log or IEDScout. The SBO handlers are NOT being called at all.

### Hypothesis: Object Reference Mismatch

The handlers may be registered on a different object reference format than what IEDScout is sending control commands to.

**Example**:
- Handlers registered on: `CTRL/DCCSWI1.Pos`
- IEDScout sends control to: `ABBK3A03A1CTRL/DCCSWI1$CO$Pos` (canonical format)

### Latest Debugging Changes (Applied)

1. **Canonical Reference Lookup**: Added code to retrieve the actual canonical object reference from libiec61850 model
2. **Comprehensive Handler Logging**: Added detailed logging to both check and control handlers
3. **Handler Registration Verification**: Logging the data_object pointer and reference used

### Expected Log Output (If Working)

On startup:
```
Canonical object reference: ABBK3A03A1CTRL/DCCSWI1$CO$Pos
Registering handlers on data_object=0x... for ABBK3A03A1CTRL/DCCSWI1$CO$Pos
✓ Registered SBO handlers for ABBK3A03A1CTRL/DCCSWI1$CO$Pos (found as CTRL/DCCSWI1.Pos, ctlModel=sbo-with-enhanced-security)
```

On IEDScout select:
```
[SBO] Select request received for ABBK3A03A1CTRL/DCCSWI1$CO$Pos
[SBO] ✓ Select ACCEPTED for ABBK3A03A1CTRL/DCCSWI1$CO$Pos
```

### If No Logs Appear
This confirms the handlers are not being invoked, meaning:
- libiec61850 cannot find the control object at the reference client is using
- OR handlers are not properly attached to the data object
- OR the data object pointer is invalid

## Problem Summary
The simulated IEC 61850 server has non-functional SBO (Select-Before-Operate) and Operate control operations. Clients can connect but control commands fail because the control handlers are not working correctly.

## Root Cause Analysis

### Current Focus: Handler Invocation Failure (CRITICAL)

The handlers are not being called at all when IEDScout sends select commands. This indicates:

**Most Likely**: Object reference format mismatch between:
- What the handlers are registered on (e.g., `CTRL/DCCSWI1.Pos`)
- What IEDScout sends control commands to (e.g., `ABBK3A03A1CTRL/DCCSWI1$CO$Pos`)

**Solution Applied**: Use `ModelNode_getObjectReference()` to get canonical reference and register handlers using that exact format.

### Previous Issues (Now Addressed)

### Issue 1: Missing `ControlAction_isOperate` Function ✓ FIXED
In `server_adapter.py`, replaced with `if not lib.ControlAction_isSelect(action)` to detect operate actions.

### Issue 2: Handler Return Values ✓ FIXED  
Now properly returning ctypes-wrapped enum values from libiec61850.

### Issue 3: Missing Function Existence Checks ✓ FIXED
Added hasattr() checks before calling optional library functions.

## Current Implementation Status

### What's Been Fixed ✓

1. **Control Object Pre-creation**: Using `CDC_DPC_create()` for proper CSWI.Pos structure
2. **Handler Logic**: Fixed isOperate detection and selection state management  
3. **Comprehensive Logging**: Added detailed [SBO] prefixed logs for all operations
4. **Canonical Reference Lookup**: Getting actual object reference from libiec61850
5. **ctlModel Value**: Properly setting to numeric value 4 for sbo-with-enhanced-security

### Current Code (Latest Version)

**Handler Registration with Canonical Reference**:
```python
# Get the actual canonical reference from the model node
canonical_ref = None
try:
    if hasattr(lib, "ModelNode_getObjectReference"):
        ref_str = lib.ModelNode_getObjectReference(model_node, None)
        if ref_str:
            canonical_ref = ref_str.decode("utf-8") if isinstance(ref_str, bytes) else str(ref_str)
            logger.info(f"Canonical object reference: {canonical_ref}")
except Exception as e:
    logger.debug(f"Failed to get canonical reference: {e}")

control_ctx = {
    "ref": canonical_ref or found_ref,  # Use canonical ref
    "st_val": self._get_child_attribute(data_object, "stVal"),
    "op_ok": self._get_child_attribute(data_object, "opOk"),
    "t": self._get_child_attribute(data_object, "t"),
}

logger.info(f"Registering handlers on data_object={data_object} for {control_ctx['ref']}")
lib.IedServer_setPerformCheckHandler(self.server, data_object, check_handler, param_ptr)
lib.IedServer_setControlHandler(self.server, data_object, control_handler, param_ptr)
```

### What Needs Testing ⏳

**RUN THE APPLICATION** and check Event Log for:
1. Canonical reference format (does it match what IEDScout uses?)
2. Handler registration confirmation
3. When selecting in IEDScout: Do `[SBO] Select request received` messages appear?

### If Handlers Still Not Called

**Next diagnostic steps**:

1. **Verify handler attachment**:
```python
# After IedServer_setPerformCheckHandler
handler_ptr = lib.IedServer_getControlHandler(self.server, data_object)
logger.info(f"Handler verification: {handler_ptr is not None}")
```

2. **Dump all control objects**:
```python
def _dump_all_control_objects(self):
    # Recursively walk model and find all objects with ctlModel attribute
    # Log their canonical references
    pass
```

3. **MMS packet capture**: Use Wireshark to see actual MMS control request and object reference client is sending

## Required Fixes

### Fix 1: Replace Non-existent `ControlAction_isOperate` Call

In `_make_sbo_check_handler`, replace:
```python
# Operate: require prior selection
if lib.ControlAction_isOperate(action):
```

With:
```python
# Operate: require prior selection (isOperate = not isSelect)
if not lib.ControlAction_isSelect(action):
```

### Fix 2: Add Function Existence Checks

Add safety checks before calling library functions:
```python
# Check if required functions exist
if not hasattr(lib, 'ControlAction_isSelect'):
    logger.error("ControlAction_isSelect not available in libiec61850")
    return lib.CONTROL_OBJECT_ACCESS_DENIED
```

### Fix 3: Ensure Proper Return Types

Make sure handlers return the correct ctypes-wrapped enum values:
- `CheckHandlerResult` should return: `CONTROL_ACCEPTED` (-1), `CONTROL_WAITING_FOR_SELECT` (0), or `CONTROL_OBJECT_ACCESS_DENIED` (3)
- `ControlHandlerResult` should return: `CONTROL_RESULT_OK` (1) or `CONTROL_RESULT_FAILED` (0)

### Fix 4: Add Debug Logging

Add more detailed logging to trace control flow:
```python
logger.debug(f"[SBO] Check handler called for {ref}, action type: {'select' if lib.ControlAction_isSelect(action) else 'operate'}")
```

## Complete Fixed Code for `_make_sbo_check_handler`

```python
def _make_sbo_check_handler(self, ctx):
    @lib.ControlPerformCheckHandler
    def _handler(action, _param, value, _test, _interlock_check):
        try:
            ref = ctx["ref"]
            
            # Check if required functions exist
            if not hasattr(lib, 'ControlAction_isSelect'):
                logger.error("[SBO] ControlAction_isSelect not available in libiec61850")
                return lib.CONTROL_OBJECT_ACCESS_DENIED
            
            if not hasattr(lib, 'Hal_getTimeInMs'):
                logger.error("[SBO] Hal_getTimeInMs not available")
                return lib.CONTROL_OBJECT_ACCESS_DENIED
            
            is_select = bool(lib.ControlAction_isSelect(action))
            action_type = "select" if is_select else "operate"
            logger.info(f"[SBO] Check handler called for {ref}, action={action_type}")
            
            now = int(lib.Hal_getTimeInMs())
            
            if is_select:
                logger.info(f"[SBO] Select request received for {ref}")
                selected_at = self._sbo_state.get(ref)
                
                # Check if already selected and selection is still valid
                if selected_at and (now - selected_at) < self._sbo_select_timeout_ms:
                    logger.warning(f"[SBO] {ref} already selected (age={(now-selected_at)}ms)")
                    if hasattr(lib, 'ControlAction_setAddCause'):
                        lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_ALREADY_SELECTED)
                    return lib.CONTROL_OBJECT_ACCESS_DENIED
                
                # Accept new selection
                self._sbo_state[ref] = now
                logger.info(f"[SBO] Select ACCEPTED for {ref}")
                return lib.CONTROL_ACCEPTED
            
            else:
                # Operate: require prior selection
                logger.info(f"[SBO] Operate request received for {ref}")
                selected_at = self._sbo_state.get(ref)
                
                if not selected_at:
                    logger.warning(f"[SBO] {ref} not selected - rejecting operate")
                    if hasattr(lib, 'ControlAction_setAddCause'):
                        lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_NOT_SELECTED)
                    return lib.CONTROL_WAITING_FOR_SELECT
                
                if (now - selected_at) > self._sbo_select_timeout_ms:
                    logger.warning(f"[SBO] {ref} selection expired (age={(now-selected_at)}ms)")
                    if hasattr(lib, 'ControlAction_setAddCause'):
                        lib.ControlAction_setAddCause(action, lib.ADD_CAUSE_OBJECT_NOT_SELECTED)
                    return lib.CONTROL_WAITING_FOR_SELECT
                
                logger.info(f"[SBO] Operate ACCEPTED for {ref} (selected {now-selected_at}ms ago)")
                return lib.CONTROL_ACCEPTED
                
        except Exception as e:
            logger.error(f"[SBO] Exception in check handler for {ctx.get('ref', 'unknown')}: {e}", exc_info=True)
            return lib.CONTROL_OBJECT_ACCESS_DENIED
    
    return _handler
```

## Additional Improvements Needed

### 1. Verify Control Model Constants Are Available
Ensure these constants exist in lib61850.py or add them:
- `CONTROL_MODEL_SBO_ENHANCED`
- `CONTROL_MODEL_SBO_NORMAL`
- `CONTROL_MODEL_DIRECT_ENHANCED`
- `CONTROL_MODEL_DIRECT_NORMAL`
- `CONTROL_MODEL_STATUS_ONLY`

### 2. Add Handler Registration Verification
After registering handlers, verify they were actually registered:
```python
logger.info(f"Registered SBO handlers for {control_ctx['ref']}")
# Add a test to verify handler is callable
```

### 3. Fix `_make_sbo_control_handler` Too
Ensure the control handler also has proper error handling:
```python
def _make_sbo_control_handler(self, ctx):
    @lib.ControlHandler
    def _handler(action, _param, value, _test):
        try:
            ref = ctx["ref"]
            logger.info(f"[SBO] Control handler invoked for {ref}")
            
            # Check if required functions exist
            if not hasattr(lib, 'MmsValue_getBoolean'):
                logger.error("[SBO] MmsValue_getBoolean not available")
                return lib.CONTROL_RESULT_FAILED
            
            state = False
            try:
                if value:
                    state = bool(lib.MmsValue_getBoolean(value))
                logger.debug(f"[SBO] Control value for {ref}: {state}")
            except Exception as e:
                logger.warning(f"[SBO] Failed to read control value: {e}")
            
            # Update opOk if available
            if ctx.get("op_ok") and hasattr(lib, 'MmsValue_newBoolean'):
                try:
                    op_ok_val = lib.MmsValue_newBoolean(True)
                    if hasattr(lib, 'IedServer_updateAttributeValue'):
                        lib.IedServer_updateAttributeValue(self.server, ctx["op_ok"], op_ok_val)
                    if hasattr(lib, 'MmsValue_delete'):
                        lib.MmsValue_delete(op_ok_val)
                    logger.debug(f"[SBO] Updated opOk for {ref}")
                except Exception as e:
                    logger.debug(f"[SBO] Failed to update opOk: {e}")
            
            # Update stVal if available
            if ctx.get("st_val") and hasattr(lib, 'MmsValue_newBoolean'):
                try:
                    st_val = lib.MmsValue_newBoolean(state)
                    if hasattr(lib, 'IedServer_updateAttributeValue'):
                        lib.IedServer_updateAttributeValue(self.server, ctx["st_val"], st_val)
                    if hasattr(lib, 'MmsValue_delete'):
                        lib.MmsValue_delete(st_val)
                    logger.debug(f"[SBO] Updated stVal={state} for {ref}")
                except Exception as e:
                    logger.debug(f"[SBO] Failed to update stVal: {e}")
            
            # Update timestamp if available
            if ctx.get("t") and hasattr(lib, 'Hal_getTimeInMs'):
                try:
                    ts = int(lib.Hal_getTimeInMs())
                    if hasattr(lib, 'IedServer_updateUTCTimeAttributeValue'):
                        lib.IedServer_updateUTCTimeAttributeValue(self.server, ctx["t"], ts)
                    logger.debug(f"[SBO] Updated timestamp for {ref}")
                except Exception as e:
                    logger.debug(f"[SBO] Failed to update timestamp: {e}")
            
            # Clear selection on operate
            self._sbo_state.pop(ref, None)
            logger.info(f"[SBO] Control operation completed for {ref} (state={state})")
            return lib.CONTROL_RESULT_OK
            
        except Exception as e:
            logger.error(f"[SBO] Exception in control handler: {e}", exc_info=True)
            return lib.CONTROL_RESULT_FAILED
    
    return _handler
```

## Testing Checklist After Fix

1. Start the IEC 61850 server with an SCD file containing SBO controls
2. Connect with an IEC 61850 client (e.g., IEDScout, OMICRON IEDScout, or custom client)
3. Attempt to select a control object - should succeed
4. Attempt to operate within timeout - should succeed and update stVal
5. Attempt to operate without select - should fail with proper error
6. Attempt to select twice - second select should fail with "already selected"
7. Wait for timeout then operate - should fail with "not selected"

## Files to Modify

1. `/mnt/okcomputer/upload/server_adapter.py` - Fix the `_make_sbo_check_handler` and `_make_sbo_control_handler` methods

## Expected Behavior After Fix

- Select requests are properly accepted/rejected based on selection state
- Operate requests require a prior valid select
- Selection times out after 30 seconds (configurable via `self._sbo_select_timeout_ms`)
- Control operations update stVal, opOk, and timestamp attributes
- Proper error codes are returned to clients
