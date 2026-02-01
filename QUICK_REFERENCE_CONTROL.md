# IEC 61850 SBO Control - Quick Reference

## 🚀 Quick Start (3 Steps)

### Step 1: Import the Fixed Control Client
```python
from protocols.iec61850.control_client_fixed import IEC61850ControlClient
```

### Step 2: Create Client with Your Connection
```python
# Assuming you have an active IEC61850 connection
client = IEC61850ControlClient(connection, event_logger=event_logger)
```

### Step 3: Perform Control
```python
# Use base control reference (NOT the full .ctlVal path)
control_ref = "LD0/CSWI1.Pos"  # ✅ Correct
# NOT: "LD0/CSWI1.Pos.Oper.ctlVal"  # ❌ Wrong

# Automatic control (handles SBO automatically)
success = client.control(control_ref, True)  # True = Close/ON
```

---

## 📝 Path Reference

### Control Object Naming

| Component | Example | Description |
|-----------|---------|-------------|
| Logical Device (LD) | `LD0` | Top-level device |
| Logical Node (LN) | `CSWI1` | Circuit Switch Controller |
| Data Object (DO) | `Pos` | Position |
| Data Attribute (DA) | `ctlVal` | Control value |

### Correct Path Construction

```python
# Base control reference (what you should use)
control_ref = "LD0/CSWI1.Pos"

# Full paths (library constructs these internally)
select_path = f"{control_ref}.SBOw.ctlVal"      # Select path
operate_path = f"{control_ref}.Oper.ctlVal"    # Operate path
status_path = f"{control_ref}.stVal"           # Status path
model_path = f"{control_ref}.ctlModel"         # Control model
```

---

## 🔑 Key API Methods

### Automatic Control (Recommended)

```python
# Single method that handles everything
success = client.control(control_ref, value)
```

This automatically:
- ✅ Reads control model
- ✅ Performs select if needed (SBO models)
- ✅ Performs operate with correct parameters
- ✅ Uses correct paths and FC

### Manual Control (Advanced)

```python
# Step 1: Read control model
ctl_model = client.read_ctl_model(control_ref)
# Returns: 0=status-only, 1=direct-normal, 2=sbo-normal, 
#          3=direct-enhanced, 4=sbo-enhanced

# Step 2: Select (if SBO model)
if ctl_model in [2, 4]:  # SBO required
    if ctl_model == 4:  # Enhanced security
        client.select_with_value(control_ref, value)
    else:  # Normal security
        client.select(control_ref)

# Step 3: Operate
client.operate(control_ref, value)
```

---

## ⚙️ Control Parameters

### Default Parameters
```python
# Library uses these by default
orCat = 3           # 3 = remote-control
orIdent = "scada_scout"
ctlNum = 0          # Auto-incremented
Test = False        # Real operation (not test)
Check = 0           # No interlocking
```

### Custom Parameters
```python
from protocols.iec61850.control_client_fixed import ControlParameters

params = ControlParameters(
    orCat=3,              # Originator category
    orIdent="operator1",  # Your identifier
    ctlNum=0,             # Control number
    T=True,               # Include timestamp
    Test=False,           # False = real, True = test
    Check=0               # 0=none, 1=interlock, 2=synchro, 3=both
)

# Use custom parameters
client.control(control_ref, value, params)
```

---

## 🎯 Common Control Objects

| LN Class | Data Object | Description | Example |
|----------|-------------|-------------|---------|
| XCBR | Pos | Circuit Breaker Position | `LD0/XCBR1.Pos` |
| CSWI | Pos | Switch Position | `LD0/CSWI1.Pos` |
| CILO | EnaOpn | Enable Opening | `LD0/CILO1.EnaOpn` |
| CILO | EnaCls | Enable Closing | `LD0/CILO1.EnaCls` |
| MMXU | VArSet | Reactive Power Setpoint | `LD0/MMXU1.VArSet` |
| GAPC | RefPt | Reference Point | `LD0/GAPC1.RefPt` |

---

## 🔍 Error Reference

| Error Code | Error Name | Cause | Solution |
|------------|------------|-------|----------|
| 10 | OBJECT_REFERENCE_INVALID | Wrong path | Use `.Oper.ctlVal` not `.ctlVal` |
| 13 | OBJECT_ACCESS_DENIED | Wrong FC | Use `FC_CO` not `FC_SP`/`FC_ST` |
| 9 | CONTROL_MUST_BE_SELECTED | Missing select | Call `select()` before `operate()` |
| 12 | TIMEOUT | SBO timeout | Reduce delay between select/operate |
| 19 | OBJECT_VALUE_INVALID | Wrong data type | Check if bool/int/float |
| 2 | INSTANCE_IN_USE | Already selected | Wait or cancel previous selection |
| 8 | INSTANCE_LOCKED | Locked by other client | Wait for release |

---

## 🧪 Testing Commands

### Basic Test
```bash
# Test control operation
python test_control_fixed.py 192.168.1.100 LD0/CSWI1.Pos True
```

### Test Arguments
```bash
# IP address, control reference, value
python test_control_fixed.py <ip> <control_ref> <value>

# Values can be:
# - True/False, 1/0, on/off, close/open  (for boolean)
# - Integer numbers (for integer controls)
```

### Test Output
```
✓ Discovery             - Control object found and analyzed
✓ Read Current Value    - Current status retrieved
✓ Fixed Control Client  - Control operation successful
✓ Verification          - Status matches expected value
```

---

## 📋 Integration Checklist

- [ ] Import `IEC61850ControlClient`
- [ ] Create client with connection
- [ ] Use base control reference (e.g., `LD0/CSWI1.Pos`)
- [ ] Call `client.control(ref, value)` for automatic handling
- [ ] Check return value for success/failure
- [ ] Add error handling
- [ ] Add logging for debugging
- [ ] Test with real IED or simulator

---

## 💡 Pro Tips

### 1. Always Use Base Reference
```python
# ✅ Correct
control_ref = "LD0/CSWI1.Pos"

# ❌ Wrong
control_ref = "LD0/CSWI1.Pos.Oper.ctlVal"
control_ref = "LD0/CSWI1.Pos.ctlVal"
```

### 2. Let the Library Handle SBO
```python
# ✅ Recommended - automatic SBO handling
client.control(control_ref, value)

# ❌ Manual (unless you have specific needs)
client.select(control_ref)
client.operate(control_ref, value)
```

### 3. Check Control Model First (for debugging)
```python
# Read before control to understand device
ctl_model = client.read_ctl_model(control_ref)
print(f"Control model: {ctl_model}")
# 2 or 4 = SBO required
# 1 or 3 = Direct control
# 0 = Read-only
```

### 4. Enable Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use event logger
client = IEC61850ControlClient(connection, event_logger=my_logger)
```

### 5. Verify After Control
```python
# Wait a moment for IED to process
import time
time.sleep(0.5)

# Read back status
stval_path = f"{control_ref}.stVal"
current_value, err = iec61850.IedConnection_readBooleanValue(
    connection, stval_path, iec61850.IEC61850_FC_ST
)

if err == iec61850.IED_ERROR_OK:
    print(f"Current status: {current_value}")
```

---

## 🔗 See Also

- **Complete Guide:** [IEC61850_SBO_CONTROL_FIX.md](IEC61850_SBO_CONTROL_FIX.md)
- **Test Script:** [test_control_fixed.py](test_control_fixed.py)
- **Fixed Client:** [src/protocols/iec61850/control_client_fixed.py](src/protocols/iec61850/control_client_fixed.py)

---

## ❓ FAQ

**Q: Do I need to modify adapter.py?**  
A: No, you can use the fixed client directly. See integration options in the complete guide.

**Q: What if I get error 10 (OBJECT_REFERENCE_INVALID)?**  
A: Check your path. Use base reference like `LD0/CSWI1.Pos`, not the full `.ctlVal` path.

**Q: Does this work with all IEDs?**  
A: Yes, it follows IEC 61850 standard. Some vendors may have quirks - check logs for details.

**Q: Can I use this for Modbus or OPC UA?**  
A: No, this is specifically for IEC 61850. Other protocols have different control mechanisms.

**Q: How do I know if I need SBO?**  
A: The library detects this automatically with `control()` method. For manual control, check `ctlModel` value.
