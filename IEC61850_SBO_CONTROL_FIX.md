# IEC 61850 SBO Control Fix - Complete Integration Guide

## 🎯 Overview

This document explains the comprehensive fix for IEC 61850 SBO (Select-Before-Operate) control operations in scada_scout. The fix addresses critical issues that were preventing control operations from working correctly.

## 🔴 Critical Issues Fixed

### 1. Wrong Object Reference Path
**Problem:** Code was trying to write directly to `.ctlVal` instead of `.Oper.ctlVal`

```python
# ❌ WRONG - This will fail
address = "LD0/CSWI1.Pos.ctlVal"

# ✅ CORRECT - ctlVal is under Oper structure
address = "LD0/CSWI1.Pos.Oper.ctlVal"
```

### 2. Missing SBO Sequence
**Problem:** For SBO control models, you MUST select before operating

```python
# ❌ WRONG for SBO control
write_value("LD0/CSWI1.Pos.Oper.ctlVal", True)

# ✅ CORRECT for SBO control
select("LD0/CSWI1.Pos")           # Step 1: Select first
write_value("LD0/CSWI1.Pos.Oper.ctlVal", True)  # Step 2: Then operate
```

### 3. Wrong Functional Constraint
**Problem:** Using wrong FC (Functional Constraint) for control operations

```python
# ❌ WRONG
iec61850.IEC61850_FC_SP  # Setpoint
iec61850.IEC61850_FC_ST  # Status

# ✅ CORRECT
iec61850.IEC61850_FC_CO  # Controllable
```

### 4. Missing Control Parameters
**Problem:** IEC 61850 requires complete control parameters

Required parameters:
- `origin.orCat` - originator category (typically 3=remote)
- `origin.orIdent` - originator identifier
- `ctlNum` - control number/sequence
- `T` - timestamp
- `Test` - test mode flag
- `Check` - interlock/synchro check conditions

## 📦 New Files Added

### 1. `src/protocols/iec61850/control_client_fixed.py`

Complete, standard-compliant IEC 61850 control client with:
- ✅ Correct `.Oper.ctlVal` path handling
- ✅ Proper SBO sequence (Select → Operate)
- ✅ Correct FC=CO usage
- ✅ Complete control parameter handling
- ✅ Automatic control model detection
- ✅ Enhanced security support (SelectWithValue)

**Key Classes:**

```python
class IEC61850ControlClient:
    """Main control client"""
    
    def control(self, control_ref: str, value) -> bool:
        """Automatic control with SBO handling"""
        
    def select(self, control_ref: str) -> bool:
        """Manual SELECT for SBO normal security"""
        
    def select_with_value(self, control_ref: str, value) -> bool:
        """Manual SELECT for SBO enhanced security"""
        
    def operate(self, control_ref: str, value) -> bool:
        """Manual OPERATE (requires SELECT first for SBO)"""
```

### 2. `test_control_fixed.py`

Comprehensive test suite that:
- Discovers control object capabilities
- Reads current control values
- Tests automatic control with SBO handling
- Tests manual SBO sequences
- Demonstrates wrong vs. correct approaches
- Verifies control results

## 🚀 Quick Start

### Method 1: Using the Fixed Control Client Directly

```python
from protocols.iec61850 import iec61850_wrapper as iec61850
from protocols.iec61850.control_client_fixed import IEC61850ControlClient

# Connect to IED
connection = iec61850.IedConnection_create()
error = iec61850.IedConnection_connect(connection, "192.168.1.100", 102)

if error == iec61850.IED_ERROR_OK:
    # Create control client
    client = IEC61850ControlClient(connection)
    
    # Set originator (optional)
    client.set_originator("operator1", 3)
    
    # Perform control (automatic SBO handling)
    control_ref = "LD0/CSWI1.Pos"  # Base reference only
    success = client.control(control_ref, True)  # True = Close/ON
    
    if success:
        print("Control operation successful!")
    else:
        print("Control operation failed!")
    
    # Clean up
    iec61850.IedConnection_close(connection)
    iec61850.IedConnection_destroy(connection)
```

### Method 2: Manual SBO Sequence (More Control)

```python
# Create client
client = IEC61850ControlClient(connection)

# Read control model to determine SBO requirement
ctl_model = client.read_ctl_model("LD0/CSWI1.Pos")

if ctl_model in [2, 4]:  # SBO models
    # Step 1: Select
    if ctl_model == 4:  # Enhanced security
        client.select_with_value("LD0/CSWI1.Pos", False)
    else:  # Normal security
        client.select("LD0/CSWI1.Pos")
    
    # Step 2: Operate
    client.operate("LD0/CSWI1.Pos", False)
else:
    # Direct control
    client.operate("LD0/CSWI1.Pos", False)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Activate virtual environment
source venv/bin/activate

# Run test
python test_control_fixed.py 192.168.1.100 LD0/CSWI1.Pos True
```

The test will:
1. ✓ Discover control object and capabilities
2. ✓ Read current control value
3. ✓ Test automatic control with SBO handling
4. ✓ Test manual SBO sequence (if automatic fails)
5. ✓ Demonstrate wrong paths for comparison
6. ✓ Verify control result

## 🔧 Integrating into Existing Code

### Option A: Replace Existing Implementation

If you want to completely replace the existing control logic in `adapter.py`:

```python
# In adapter.py, add import at top
from .control_client_fixed import IEC61850ControlClient

# In IEC61850Adapter class
def __init__(self, ...):
    # ... existing code ...
    self._control_client = None

def operate(self, signal: Signal, value: Any, params: dict = None) -> bool:
    """Use fixed control client for operations"""
    if not self.connected or not self.connection:
        return False
    
    # Create client if needed
    if not self._control_client:
        self._control_client = IEC61850ControlClient(
            self.connection, 
            event_logger=self.event_logger
        )
    
    # Get control reference
    control_ref = self._get_control_object_reference(signal.address)
    
    # Perform control
    return self._control_client.control(control_ref, value)
```

### Option B: Use as Fallback

Keep existing implementation but use fixed client as fallback:

```python
def operate(self, signal: Signal, value: Any, params: dict = None) -> bool:
    """Try existing method, fallback to fixed client"""
    
    # Try existing ControlObjectClient approach first
    success = self._existing_operate_logic(signal, value, params)
    
    if not success:
        # Fallback to fixed control client
        if self.event_logger:
            self.event_logger.warning("IEC61850", "Trying fixed control client...")
        
        if not self._control_client:
            self._control_client = IEC61850ControlClient(
                self.connection,
                event_logger=self.event_logger
            )
        
        control_ref = self._get_control_object_reference(signal.address)
        return self._control_client.control(control_ref, value)
    
    return success
```

### Option C: Use from UI Dialogs

For direct use in control dialogs:

```python
# In control_dialog.py or similar
from protocols.iec61850.control_client_fixed import IEC61850ControlClient

class ControlDialog:
    def perform_control(self):
        # Get adapter's connection
        connection = self.adapter.connection
        
        # Create control client
        client = IEC61850ControlClient(connection, event_logger=self.adapter.event_logger)
        
        # Get control reference from user selection
        control_ref = self.selected_control_object  # e.g., "LD0/CSWI1.Pos"
        value = self.control_value  # e.g., True/False
        
        # Perform control
        success = client.control(control_ref, value)
        
        if success:
            self.show_success_message()
        else:
            self.show_error_message()
```

## 📋 Control Model Reference

| ctlModel | Mode | Action Required |
|----------|------|-----------------|
| 0 | status-only | ❌ No control allowed |
| 1 | direct-with-normal-security | ✅ Operate directly |
| 2 | sbo-with-normal-security | ⚠️ Select → Operate |
| 3 | direct-with-enhanced-security | ✅ Operate directly |
| 4 | sbo-with-enhanced-security | ⚠️ SelectWithValue → Operate |

## ⚠️ Common Errors & Solutions

### Error: "Object reference invalid" (Error 10)
**Cause:** Wrong path - trying to access `.ctlVal` directly  
**Solution:** Use `.Oper.ctlVal` path

```python
# Fix:
control_ref = "LD0/CSWI1.Pos"  # Base reference
path = f"{control_ref}.Oper.ctlVal"  # Correct path
```

### Error: "Object access denied" (Error 13)
**Cause:** Wrong functional constraint (using FC_SP or FC_ST)  
**Solution:** Use FC_CO for control operations

```python
# Fix:
iec61850.IedConnection_writeBooleanValue(
    connection, 
    path, 
    iec61850.IEC61850_FC_CO,  # ✅ Correct FC
    value
)
```

### Error: "Control must be selected" (Error 9)
**Cause:** SBO control model requires select before operate  
**Solution:** Call select() before operate()

```python
# Fix:
client.select(control_ref)  # Step 1
client.operate(control_ref, value)  # Step 2
```

### Error: "Timeout" (Error 12)
**Cause:** SBO timeout expired between select and operate  
**Solution:** Reduce delay between select and operate, or re-select

```python
# Fix:
client.select(control_ref)
# Operate immediately, don't wait too long
client.operate(control_ref, value)
```

### Error: "Object value invalid" (Error 19)
**Cause:** ctlVal doesn't match CDC type or wrong data type  
**Solution:** Check if control expects bool, int, or float

```python
# Fix: Use correct type
client.operate(control_ref, True)  # For boolean controls
# OR
client.operate(control_ref, 1)     # For integer controls
```

## 🔍 Debugging Tips

### 1. Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

client = IEC61850ControlClient(connection)
```

### 2. Check Control Model First

```python
ctl_model = client.read_ctl_model(control_ref)
print(f"Control model: {ctl_model}")
print(f"SBO required: {ControlModel.is_sbo(ctl_model)}")
```

### 3. Verify Paths

```python
# Test if path is accessible
stval_path = f"{control_ref}.stVal"
value, error = iec61850.IedConnection_readBooleanValue(
    connection, stval_path, iec61850.IEC61850_FC_ST
)
print(f"Path accessible: {error == iec61850.IED_ERROR_OK}")
```

### 4. Monitor with Wireshark

Capture packets to see exact MMS communication:
- Filter: `mms`
- Look for Select/Operate PDUs
- Verify control parameters are sent

### 5. Check LastApplError

```python
# After failed operation, check detailed error
last_error_path = f"{control_ref}.LastApplError"
error_val, err = iec61850.IedConnection_readInt32Value(
    connection, last_error_path, iec61850.IEC61850_FC_ST
)
if err == iec61850.IED_ERROR_OK:
    print(f"LastApplError: {error_val}")
```

## 📚 Additional Resources

- [libiec61850 Control Tutorial](https://libiec61850.com/documentation/control-tutorial/)
- [IEC 61850 Control Model Documentation](https://www.iec61850.com/)
- [libiec61850 API Reference](https://libiec61850.com/api/)

## ✅ Verification Checklist

After integrating the fix, verify:

- [ ] Control objects use base reference (e.g., `LD0/CSWI1.Pos`)
- [ ] Paths constructed as `.Oper.ctlVal` (not just `.ctlVal`)
- [ ] FC_CO used for all control writes
- [ ] SBO sequence implemented (select → operate)
- [ ] Control parameters included (origin, ctlNum, etc.)
- [ ] Control model read before operations
- [ ] Error handling for all control failures
- [ ] Logging for debugging
- [ ] Tested with real IED or simulator

## 🎉 Expected Results

After implementing this fix:

✅ SBO control operations work correctly  
✅ Control model automatically detected  
✅ Proper select → operate sequence  
✅ Complete control parameters sent  
✅ Correct paths used throughout  
✅ Better error messages and debugging  
✅ Works with various IED vendors  

---

**Questions or Issues?**

If you encounter problems:
1. Run the test script: `python test_control_fixed.py <ip> <control_ref> <value>`
2. Check the logs for detailed error information
3. Verify paths are correct using Wireshark
4. Check IED documentation for vendor-specific requirements
