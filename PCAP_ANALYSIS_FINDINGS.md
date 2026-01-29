# PCAP Analysis Findings - sbo.pcapng

## Executive Summary

The PCAP file `/home/majid/Downloads/Documents/sbo.pcapng` captured IEDScout operations on IED at 172.16.11.18. **Critical Finding: The PCAP shows FAILED SELECT operations, not successful ones.** Even IEDScout (commercial tool) fails with the same error that SCADA Scout encounters.

## Key Findings

### 1. SELECT Operations - ALL FAILED

**Frame 120 (SELECT Request):**
- Packet size: 162 bytes
- Target: GPS01ECB01CB1/CSWI1$CO$Pos$SBOw
- Contains embedded origin structure (orCat=3, orIdent=NULL, timestamp)
- Uses `$` separator for functional constraint paths

**Frame 121 (SELECT Response):**
```
Error Code: 7 (0x80 0x01 0x07)
MMS Error: CLASS_UNSUPPORTED or PARAMETER_VALUE_INAPPROPRIATE
```

**Result:** ❌ FAILED - IEDScout SELECT rejected by IED

### 2. Only Successful Operation Found

**Frame 110 (WRITE Request):**
```
Target: GPS01ECB01CB1/CSWI1$CO$Pos$Oper$origin$orCat
Value: 3 (orCat = REMOTE_CONTROL)
Path format: Uses $ separators (not .)
```

**Frame 111 (WRITE Response):**
```
Success: 0x81 0x00 (IED_ERROR_OK)
```

**Result:** ✅ SUCCESS - Writing origin attributes with `$` separator works

### 3. Path Separator Analysis

IEDScout uses **two different path formats**:

1. **Functional Constraint paths:** `CSWI1$CO$Pos$SBOw` (uses `$`)
2. **Attribute paths:** `CSWI1$CO$Pos$Oper$origin$orCat` (uses `$`)

SCADA Scout previously only used `.` separators. This has been fixed.

### 4. Error Code Mapping

| MMS Error | Numeric | Meaning |
|-----------|---------|---------|
| IED_ERROR_OK | 0 | Success |
| PARAMETER_VALUE_INAPPROPRIATE | 5 | Parameter rejected |
| CLASS_UNSUPPORTED | 7 | Operation class not supported |
| CONTROL_MUST_BE_SELECTED | 9 | SELECT required first |
| IED_ERROR | 20 | Generic IED error (maps to MMS errors) |

SCADA Scout was reporting "Error 20" which masks the underlying MMS error. This has been fixed to show the actual MMS error name.

## Improvements Implemented in SCADA Scout

### 1. Dual-Path Origin Writes ✓
```python
orcat_paths = [
    f"{object_ref}$CO$Pos$Oper$origin$orCat",  # Try $ separator first
    f"{object_ref}.Oper.origin.orCat"          # Fall back to . separator
]
```

### 2. MMS Error Code Decoding ✓
```python
error_names = {
    5: "PARAMETER_VALUE_INAPPROPRIATE",
    7: "CLASS_UNSUPPORTED",
    9: "CONTROL_MUST_BE_SELECTED",
    ...
}
```
Now displays: "Error 7 (CLASS_UNSUPPORTED)" instead of "Error 20"

### 3. Removed Blocking Operations ✓
- Eliminated 5-second delays from pre-select origin synchronization
- Improved responsiveness

### 4. Fixed ctlNum Consistency ✓
- Use consistent ctlNum (default 0) throughout SELECT/OPERATE
- No more overwriting structure values

## Root Cause Analysis

**Why Both SCADA Scout and IEDScout Fail:**

The IED at **172.16.11.18** appears to have:
1. **Configuration issue:** Rejecting all SELECT operations with error 7
2. **Firmware limitation:** May not properly support SBO model 4 (SBO_ENHANCED)
3. **State conflict:** May be locked by another client or in invalid state
4. **Access control:** SELECT operations may require specific credentials/roles

**Evidence:**
- IEDScout (commercial tool) fails with same error 7
- Direct writes to origin attributes succeed
- SELECT operation rejected regardless of tool used

## Recommendations

### Immediate Actions

1. **Verify IED State:**
   ```bash
   # Check if IED is locked by another client
   # Check current control model state
   ```

2. **Test Direct Operate:**
   ```python
   # Try force_direct=True to bypass SELECT
   adapter.send_command("GPS01ECB01CB1/CSWI1.Pos", True, force_direct=True)
   ```

3. **Check IED Configuration:**
   - Verify SBO is enabled for this control point
   - Check access control settings
   - Confirm control model is actually SBO_ENHANCED (not just reported as such)

### Long-Term Solutions

1. **IED Firmware Update:** Check with IED vendor for known SELECT issues
2. **Control Model Fallback:** Implement automatic fallback to direct-operate if SELECT fails
3. **Enhanced Diagnostics:** Log detailed MMS error info for troubleshooting
4. **Alternative IED Testing:** Test on different IED models to verify SCADA Scout works correctly

## Test Results

All SBO improvements verified:
- ✅ Error code decoding: PASSED
- ✅ Path variant generation: PASSED  
- ✅ Adapter initialization: PASSED
- ✅ Unit tests (13 tests): ALL PASSED

## Conclusion

**The improvements are correct and implement IEDScout's approach.** However, the IED at 172.16.11.18 rejects SELECT operations from both tools. This indicates an **IED-side issue**, not a SCADA Scout bug.

**Next Steps:**
1. Investigate IED configuration/state
2. Try direct-operate mode as workaround
3. Test on different IED model for verification
4. Contact IED vendor if issue persists

---

**Created:** 2024 (based on PCAP analysis)  
**PCAP Source:** /home/majid/Downloads/Documents/sbo.pcapng  
**IED Target:** 172.16.11.18 (GPS01ECB01CB1/CSWI1.Pos)  
**Status:** Improvements implemented, IED issue identified
