# SBO Implementation: Before vs After

## ❌ BEFORE (Incorrect Manual Approach)

### Problems:
1. Manually building 7-element MmsValue structures
2. Manual ctlNum tracking and incrementing
3. Manual timestamp generation
4. Direct writes to .SBO/.Oper attributes
5. 200+ lines of complex structure building code

### Code Example:
```python
def operate(self, signal: Signal, value: Any, params: dict = None) -> bool:
    # Get control context
    ctx = self.controls.get(object_ref)
    
    # Manually increment ctlNum
    ctx.ctl_num = (ctx.ctl_num + 1) % 256
    
    # Manually build 7-element structure
    struct = iec61850.MmsValue_newStructure(7)
    
    # Element 0: ctlVal
    iec61850.MmsValue_setElement(struct, 0, iec61850.MmsValue_newBoolean(value))
    
    # Element 1: operTm (manual timestamp)
    now_ms = int(time.time() * 1000)
    mms_tm = iec61850.MmsValue_newUtcTimeMs(now_ms)
    iec61850.MmsValue_setElement(struct, 1, mms_tm)
    
    # Element 2: origin [cat, ident]
    origin = iec61850.MmsValue_newStructure(2)
    iec61850.MmsValue_setElement(origin, 0, iec61850.MmsValue_newInteger(3))
    iec61850.MmsValue_setElement(origin, 1, iec61850.MmsValue_newVisibleString("SCADA"))
    iec61850.MmsValue_setElement(struct, 2, origin)
    
    # Element 3: ctlNum (manually tracked)
    iec61850.MmsValue_setElement(struct, 3, iec61850.MmsValue_newInteger(ctx.ctl_num))
    
    # Element 4: T (timestamp)
    mms_t = iec61850.MmsValue_newUtcTimeMs(now_ms)
    iec61850.MmsValue_setElement(struct, 4, mms_t)
    
    # Element 5: Test
    iec61850.MmsValue_setElement(struct, 5, iec61850.MmsValue_newBoolean(False))
    
    # Element 6: Check (BitString)
    mms_check = iec61850.MmsValue_newBitString(2)
    iec61850.MmsValue_setBitStringBit(mms_check, 0, False)
    iec61850.MmsValue_setBitStringBit(mms_check, 1, False)
    iec61850.MmsValue_setElement(struct, 6, mms_check)
    
    # Manual write to .Oper attribute
    oper_path = f"{object_ref}.Oper"
    err = iec61850.IedConnection_writeObject(self.connection, oper_path, 
                                              iec61850.IEC61850_FC_CO, struct)
    
    iec61850.MmsValue_delete(struct)
    return err == iec61850.IED_ERROR_OK
```

---

## ✅ AFTER (Correct ControlObjectClient API)

### Improvements:
1. Library handles all structure building
2. Automatic ctlNum management
3. Automatic timestamp generation
4. Proper control protocol handling
5. ~50 lines of clean, standard code

### Code Example:
```python
def operate(self, signal: Signal, value: Any, params: dict = None) -> bool:
    object_ref = self._get_control_object_reference(signal.address)
    
    with self._lock:
        # Create control client
        control_client = iec61850.ControlObjectClient_create(object_ref, self.connection)
        
        if not control_client:
            return False
        
        try:
            # Set originator (optional)
            iec61850.ControlObjectClient_setOriginator(control_client, "SCADA", 3)
            
            # Create simple MmsValue
            mms_val = self._create_mms_value(value, signal)
            if not mms_val:
                return False
            
            try:
                # Operate (library handles everything!)
                success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
                return success
            finally:
                iec61850.MmsValue_delete(mms_val)
        finally:
            # Always destroy control client
            iec61850.ControlObjectClient_destroy(control_client)
```

---

## Key Differences

| Aspect | BEFORE ❌ | AFTER ✅ |
|--------|----------|----------|
| **Lines of Code** | ~200 lines | ~50 lines |
| **Structure Building** | Manual 7-element MmsValue | Automatic (library handles) |
| **ctlNum Management** | Manual tracking/increment | Automatic (library handles) |
| **Timestamps** | Manual UTC time creation | Automatic (library handles) |
| **Control Protocol** | Direct attribute writes | Proper ControlObjectClient API |
| **Error Handling** | Check writeObject error codes | Use getLastError() |
| **Compatibility** | Custom implementation | Follows libiec61850 standard |
| **Maintainability** | Complex, error-prone | Simple, clean |
| **Follows Examples** | No | Yes (C examples, pyiec61850) |

---

## SBO Workflow Comparison

### BEFORE ❌
```python
# SELECT Phase
payload = _build_operate_struct(value, ctx, is_select=True)  # 200 lines!
err = iec61850.IedConnection_writeObject(conn, "CSWI1.Pos.SBO", FC_CO, payload)

# OPERATE Phase  
ctx.ctl_num = (ctx.ctl_num + 1) % 256  # Manual increment
oper_struct = _build_operate_struct(value, ctx)  # 200 lines again!
err = iec61850.IedConnection_writeObject(conn, "CSWI1.Pos.Oper", FC_CO, oper_struct)
```

### AFTER ✅
```python
# SELECT Phase
control_client = iec61850.ControlObjectClient_create("CSWI1.Pos", conn)
success = iec61850.ControlObjectClient_select(control_client)
iec61850.ControlObjectClient_destroy(control_client)

# OPERATE Phase
control_client = iec61850.ControlObjectClient_create("CSWI1.Pos", conn)
mms_val = iec61850.MmsValue_newBoolean(True)
success = iec61850.ControlObjectClient_operate(control_client, mms_val, 0)
iec61850.MmsValue_delete(mms_val)
iec61850.ControlObjectClient_destroy(control_client)
```

---

## Why This Matters

### Reliability
- **BEFORE**: Custom protocol implementation could have subtle bugs
- **AFTER**: Uses battle-tested library code

### Compatibility
- **BEFORE**: May not work with all IED vendors
- **AFTER**: Standard pattern works with all compliant IEDs

### Maintainability
- **BEFORE**: Hard to debug, hard to modify
- **AFTER**: Easy to understand, follows standard patterns

### Standards Compliance
- **BEFORE**: Custom interpretation of IEC 61850
- **AFTER**: Follows official libiec61850 patterns

---

## References

The new implementation follows these official examples:

1. **libiec61850 C Example** (Line 104-110):
   ```c
   control = ControlObjectClient_create("simpleIOGenericIO/GGIO1.SPCSO2", con);
   if (ControlObjectClient_select(control)) {
       ctlVal = MmsValue_newBoolean(true);
       if (ControlObjectClient_operate(control, ctlVal, 0)) {
           printf("operated successfully\n");
       }
   }
   ControlObjectClient_destroy(control);
   ```

2. **pyiec61850 Python Bindings**:
   - Uses same ControlObjectClient pattern
   - Simple, clean API calls
   - No manual structure building

---

## Conclusion

✅ **Fixed**: Replaced custom manual approach with proper `ControlObjectClient` API  
✅ **Simplified**: Reduced from 200+ lines to ~50 lines  
✅ **Standardized**: Now follows official libiec61850 patterns  
✅ **Improved**: Better reliability and IED compatibility  
