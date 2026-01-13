# IEC61850 Tree Population & Live Update Debugging Guide

**Purpose:** Help diagnose and verify tree discovery and live updates are working correctly.

---

## Quick Test Checklist

### 1. **Device Connection**
- [ ] App launches without crashes
- [ ] IEC61850 device appears in device list
- [ ] Connect button works, shows progress
- [ ] Status indicator changes to 🟢 (green) when connected

### 2. **Tree Population**
- [ ] Device appears in tree with expected structure
- [ ] All Logical Devices (LDs) are visible (not just one)
- [ ] All Logical Nodes (LNs) under each LD are visible
- [ ] All Data Objects (DOs) under each LN are visible
- [ ] All Signal leaves are visible under each DO
- [ ] Tree can be expanded/collapsed at each level

### 3. **Live Updates**
- [ ] Add a signal to the watch list
- [ ] Signal value appears in tree Description column as: `"description  Value: 123.45"`
- [ ] Value changes every ~1 second (watch list poll interval)
- [ ] Color indicates quality:
  - 🟢 Green text = GOOD quality
  - ⚪ Grey text = NOT_CONNECTED
  - 🟠 Orange text = INVALID or other quality

### 4. **No Auto-Polling**
- [ ] Open browser console or check event log
- [ ] After connection completes, no IEC61850 reads should occur
- [ ] Only signals in watch list are read periodically

---

## Detailed Debugging Steps

### Issue: Tree Only Shows One Branch (Not Fully Populated)

**Symptom:** After connecting, tree shows only one Logical Device or one Logical Node, not all.

**Root Causes:** 
- Exception in discovery loop (should be caught but check logs)
- IED firmware returns incomplete data
- Network issues during discovery

**Debug Steps:**

1. **Check Event Log**
   - Open app → View → Event Log (or bottom panel)
   - Look for messages starting with `_discover_online:`
   - Expected: `_discover_online: Processing N LDs` where N > 0

2. **Check for Errors**
   - Search event log for: `Failed to process LD`
   - If found, note which LD failed and the error message
   - Example: `Failed to process LD GPS01: IedConnection_getLogicalDeviceList failed`
   - This means the IED returned an incomplete list

3. **Verify Discovery Count**
   - Look for: `Logical Devices extracted: [...]`
   - Example: `[GPS01ECB01, GPS02ECB01]` means 2 LDs detected
   - If only 1 shown, either only 1 LD exists on device, or discovery failed

4. **Check Per-LN and Per-DO Logs**
   - Search for: `Processing LN in LD=`
   - Expected: Shows LN count for each LD
   - Search for: `Browsed DO {name}, added`
   - Expected: Shows signal count for each DO

5. **Common Error Messages & Solutions**

   | Error | Meaning | Solution |
   |-------|---------|----------|
   | `IedConnection_getLogicalDeviceList failed` | IED doesn't support getting LD list | Try manual SCD file import instead |
   | `AttributeError: 'NoneType' has no attribute...` | API call returned None | Check IED firmware version compatibility |
   | `connection lost` or `state: 5` | Connection dropped mid-discovery | Check network stability, increase timeout |
   | `Invalid address: X (missing LD/)` | Address malformed in SCD file | Verify SCD file syntax or regenerate |

### Issue: Live Values Not Showing in Tree

**Symptom:** Add signal to watch list, but value doesn't appear in tree Description column.

**Root Causes:**
- Signal read callback not wired
- Watch list not reading (polling disabled)
- Signal not found in tree by address match

**Debug Steps:**

1. **Verify Watch List is Reading**
   - Check event log for repeated `IEC61850: ← Reading {address}...` messages
   - Should appear every 1-2 seconds if polling enabled
   - If absent: Watch list not active, check WatchListWidget

2. **Verify Callback is Wired**
   - Add signal to watch list
   - Check event log for: `signal_updated` or `_on_signal_update`
   - If missing: Callback not connected (code issue)

3. **Verify Signal Read Returns Value**
   - Check event log for read response: `IEC61850: ← VALUE = ...`
   - If shows `← NOT_CONNECTED`: Device disconnected during read
   - If shows `← INVALID_ADDRESS`: Address format wrong

4. **Verify Tree Update Handler**
   - If callback works but tree doesn't update:
   - Check: `DeviceTreeWidget: Failed to update signal in tree:`
   - If error shown, note the exception (helps identify address mismatch)

### Issue: Values Show But Colors Are Wrong

**Symptom:** Values appear in tree but all show grey/orange instead of green.

**Root Causes:**
- Signal quality not being set to GOOD
- Color logic in DeviceTreeWidget is broken
- Quality enum mismatch

**Debug Steps:**

1. **Check Signal Quality**
   - Event log should show: `quality: SignalQuality.GOOD`
   - If shows `NOT_CONNECTED` or `INVALID`: Check read result above
   - If shows different quality: Device returning bad status

2. **Verify Color Mapping**
   - In DeviceTreeWidget._on_signal_updated():
   ```python
   if quality == SignalQuality.GOOD:
       brush = QBrush(QColor('darkgreen'))  # Should be green
   ```
   - If not working: Likely code regression, verify file hasn't been edited

3. **Test with Manual Refresh**
   - Right-click device → Refresh All
   - This manually reads all signals
   - Check if results differ from watch list reads

---

## Event Log Message Reference

### Connection Phase
```
=== Starting connection to 192.168.1.100:9102 ===
Step 1/4: Checking network reachability...
Ping result: True
Step 2/4: Checking TCP port...
TCP port 9102 accessible
Step 3/4: Initiating IEC61850 connection...
← CONNECT in progress...
← CONNECTED
Step 4/4: Checking ready state...
← READY
```

### Discovery Phase
```
_discover_online: Processing 2 LDs
_discover_online: Logical Devices extracted: [GPS01ECB01, GPS02ECB01]
_discover_online: Processing LN in LD=GPS01ECB01, found 3 LNs
Browsed DO XCBR, added 4 signals
Browsed DO XSWI, added 2 signals
_discover_online: Processing LN in LD=GPS02ECB01, found 1 LN
Browsed DO XCBR, added 4 signals
_discover_online: Built tree with 11 signal leaves
```

### Read Phase (Watch List)
```
IEC61850: ← Reading GPS01ECB01/XCBR1.Pos.stVal...
IEC61850: ← VALUE = 1 (Type: BOOLEAN, Quality: GOOD)
IEC61850: ← Reading GPS01ECB01/XCBR1.Beh.stVal...
IEC61850: ← VALUE = 231.5 (Type: FLOAT, Quality: GOOD)
```

### Errors
```
Failed to process LD GPS02: <error message>
IEC61850 ← CONNECTION LOST (State: 5)
DeviceTreeWidget: Failed to update signal in tree: KeyError: 'signal_address'
```

---

## Log File Location

**Windows:**
```
C:\Users\{username}\Documents\scada_scout\logs\
```

**Linux:**
```
~/.local/share/scada_scout/logs/
```

**Mac:**
```
~/Library/Application Support/scada_scout/logs/
```

**To Enable Debug Logging:**
1. Open `src/core/logging_handler.py`
2. Set: `logging.basicConfig(level=logging.DEBUG)`
3. Restart app

---

## Enable Verbose Output

### Option 1: Console Output
In terminal, run:
```bash
python -u src/main.py 2>&1 | tee scada_output.log
```

### Option 2: Add Print Statements
Temporarily add to `src/protocols/iec61850/adapter.py`:
```python
def read_signal(self, signal: Signal) -> Signal:
    print(f"[DEBUG] Reading: {signal.address}")
    # ... rest of method
    print(f"[DEBUG] Result: value={signal.value}, quality={signal.quality}")
    return signal
```

### Option 3: Use Python Debugger
```bash
python -m pdb src/main.py
```

---

## Network Diagnostics

If connection fails, test IED manually:

**Linux/Mac:**
```bash
# Check if IED is reachable
ping 192.168.1.100

# Check if port is open
nc -zv 192.168.1.100 9102

# Try raw TCP connection
telnet 192.168.1.100 9102
```

**Windows PowerShell:**
```powershell
# Check if IED is reachable
Test-Connection -ComputerName 192.168.1.100

# Check if port is open
Test-NetConnection -ComputerName 192.168.1.100 -Port 9102
```

---

## Expected Behavior Summary

| Step | Expected Result | Check |
|------|-----------------|-------|
| **Connect** | Device status → 🟢 | Event log shows `← READY` |
| **Tree Builds** | All branches visible | Tree expands to 3+ levels |
| **Add to Watch List** | Signal selected in UI | Tree highlights selected signal |
| **First Read** | Value appears in Description | Tree shows `Value: X.XX` |
| **Subsequent Reads** | Value updates every ~1s | Watch value change over time |
| **Quality** | Text color reflects signal state | GOOD = green, NOT_CONNECTED = grey |

---

## Common Test Scenarios

### Scenario 1: Quick Offline Test (MOCK Mode)
If no real device available:
1. Make sure `HAS_LIBIEC61850 = False` (missing library)
2. App should use mock mode
3. Create fake device with "MOCK" in name
4. Mock reads generate random values
5. Tree should still populate and update

### Scenario 2: Single LD Device
If device has only 1 Logical Device:
- Tree should show 1 device folder with 1 LD child
- Multiple LNs under that LD are expected
- If tree shows correctly, discovery is working

### Scenario 3: Multiple LD Device
If device has 2+ Logical Devices:
- Tree should show multiple LD folders
- Each LD should have independent LN trees
- If only 1 LD shows: Debug "Issue: Tree Only Shows One Branch" above

---

## When to Report Issues

If after following all steps above the tree still:
- [ ] Doesn't populate fully after connection, OR
- [ ] Shows values but no updates, OR
- [ ] Shows wrong colors

**Collect & Share:**
1. Full event log (copy from Event Log panel)
2. IED device model/firmware version
3. Network diagram (IED → PC → any firewalls)
4. SCD file if available (for IED configuration)
5. Error message from step-by-step debugging above

---

## Quick Reference: File Locations

**Core Discovery Logic:**
- [src/protocols/iec61850/adapter.py](src/protocols/iec61850/adapter.py#L225) - `_discover_online()` method

**Live Update Handler:**
- [src/ui/widgets/device_tree.py](src/ui/widgets/device_tree.py#L310) - `_on_signal_updated()` method

**Callback Wiring:**
- [src/core/device_manager.py](src/core/device_manager.py#L291) - `set_data_callback()` call

**Auto-Polling Control:**
- [src/core/device_manager.py](src/core/device_manager.py#L388) - `poll_devices()` method (disabled by default)

