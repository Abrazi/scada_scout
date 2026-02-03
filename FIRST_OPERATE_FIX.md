# IEC 61850 First OPERATE Failure Fix

## Problem
First SBO+OPERATE sequence failed with:
- **First SBO**: SUCCESS (ctlNum=0)
- **First OPERATE**: FAILED (used ctlNum=0, but IED expected ctlNum=1)
- **Subsequent SBO+OPERATE**: SUCCESS (both used ctlNum=1)

## Root Cause
The `_has_operated` flag was only set after successful OPERATE completion. This caused:

1. **First SELECT**: Uses ctlNum=0 (correct - no `_has_operated` flag exists)
   - IED processes SELECT and internally increments ctlNum to 1
   - SELECT succeeds
   
2. **First OPERATE**: Still uses ctlNum=0 because `_has_operated` not yet set
   - IED expects ctlNum=1 (already incremented after SELECT)
   - **MISMATCH → OPERATE FAILS**

3. Now `_has_operated = True` is set (after failed OPERATE)

4. **Second SELECT**: Uses ctlNum=1 (because `_has_operated` exists)
   - Matches IED state → SELECT succeeds
   
5. **Second OPERATE**: Uses ctlNum=1
   - Matches IED state → OPERATE succeeds

## Solution

### Key Changes in `adapter.py`:

1. **Changed flag from `_has_operated` to `_has_selected`** (line 2049)
   - Check: `if ctx.state == ControlState.IDLE and not hasattr(ctx, '_has_selected'):`
   - This tracks whether SELECT has ever completed, not OPERATE

2. **Set `_has_selected = True` immediately after successful SELECT** (line 2071)
   - Added: `ctx._has_selected = True`
   - This happens BEFORE OPERATE is attempted

3. **Increment ctlNum to 1 after SELECT success** (line 2073)
   - Added: `ctx.ctl_num = 1`
   - This matches what the IED does internally after processing SELECT

4. **Enhanced logging in OPERATE** (line 2227)
   - Now logs: `ctlNum={ctx.ctl_num} (has_selected={hasattr(ctx, '_has_selected')})`
   - Helps diagnose ctlNum mismatch issues

## Correct Sequence Flow

### First SBO+OPERATE:
1. **SELECT**:
   - Context is brand new: `_has_selected` doesn't exist
   - Uses ctlNum=0 → SELECT succeeds
   - Sets `_has_selected = True`
   - Increments `ctx.ctl_num = 1` for next phase
   
2. **OPERATE**:
   - Uses `ctx.ctl_num = 1` (set by SELECT)
   - Matches IED's expectation → OPERATE succeeds
   - Increments `ctx.ctl_num = 2` for next cycle

### Subsequent SBO+OPERATE:
1. **SELECT**:
   - `_has_selected` exists
   - Uses ctlNum=1 (or whatever was last incremented)
   - SELECT succeeds
   - Increments ctlNum for OPERATE

2. **OPERATE**:
   - Uses incremented ctlNum
   - OPERATE succeeds

## IEC 61850 ctlNum Protocol

According to IEC 61850-7-2:

1. **Initial state**: Control object has no active ctlNum
2. **SELECT phase**: Client sends ctlNum=0 for first operation
   - IED accepts SELECT and internally sets ctlNum=1 for that session
3. **OPERATE phase**: Client must use ctlNum=1 (matching IED's internal state)
   - After OPERATE, ctlNum increments to 2
4. **Next cycle**: SELECT with ctlNum=1, OPERATE with ctlNum=2, etc.
   - ctlNum wraps at 256

The key insight: **IED increments ctlNum immediately after SELECT**, not after OPERATE.

## Testing

### Test Case 1: Fresh Control Context
```python
# First ever control operation on this object
signal = device.get_signal("IED1/LLN0$CO$CSWI1$Pos")

# SBO
result = adapter.select(signal, True)
assert result == True
assert ctx.ctl_num == 1  # Incremented after SELECT
assert ctx._has_selected == True

# OPERATE (should use ctlNum=1)
result = adapter.operate(signal, True)
assert result == True
assert ctx.ctl_num == 2  # Incremented after OPERATE
```

### Test Case 2: Subsequent Operations
```python
# Second control operation
result = adapter.select(signal, False)
assert result == True
assert ctx.ctl_num == 3  # Uses 2, increments to 3

result = adapter.operate(signal, False)
assert result == True
assert ctx.ctl_num == 4
```

### Test Case 3: ctlNum Wraparound
```python
# After 255 operations
ctx.ctl_num = 255
result = adapter.select(signal, True)
assert ctx.ctl_num == 0  # Wraps to 0

result = adapter.operate(signal, True)
assert ctx.ctl_num == 1
```

## Verification

To verify the fix works:

1. **Open SCADA Scout** and connect to IEC 61850 device
2. **Open Control Dialog** for any control object
3. **First Operation**:
   - Click "Select Before Operate"
   - Observe: "First control operation - using ctlNum=0 for SELECT"
   - Observe: "SELECT completed, ctlNum incremented to 1 for OPERATE phase"
   - Click "Operate"
   - Observe: "OPERATE: Setting ctlNum=1 (has_selected=True)"
   - **Expected**: Both SELECT and OPERATE succeed
4. **Second Operation**:
   - Change value and click "Select Before Operate"
   - Observe: ctlNum=1 for SELECT
   - Click "Operate"
   - Observe: ctlNum=2 for OPERATE
   - **Expected**: Both succeed

## Files Modified
- `src/protocols/iec61850/adapter.py`:
  - Line 2049: Changed `_has_operated` → `_has_selected`
  - Lines 2071-2076: Added `_has_selected = True` and ctlNum increment after SELECT
  - Lines 2227-2234: Enhanced OPERATE logging with ctlNum and flag state

## Related Issues
- Previous fix: "First SBO operation always failed" - fixed ctlNum=0 for first SELECT
- This fix: "First OPERATE failed after successful SELECT" - fixed ctlNum mismatch between phases
- Both issues stem from incorrect understanding of when IED increments ctlNum
