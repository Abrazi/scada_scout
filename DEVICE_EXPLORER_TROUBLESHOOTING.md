# Device Explorer Troubleshooting Guide

## Issue: Device Explorer shows nothing after successful connection

### Quick Checks

1. **Verify the device was actually added:**
   - Check the Event Log (bottom panel) for "Device added" messages
   - Look for connection success messages

2. **Check if the device has a tree structure:**
   - The device must have a `root_node` with children to display in the tree
   - For IEC 61850: This requires successful browsing/discovery
   - For Modbus: This requires register mapping or manual configuration

3. **Verify Device Explorer is visible:**
   - Check View menu → ensure "Device Explorer" is checked
   - The panel should be on the left side by default

### Common Causes

#### 1. Device Added Before Discovery Completed
**Symptom:** Device shows in the list but no tree structure

**Solution:** 
- For IEC 61850: Wait for discovery to complete (check Event Log)
- For Modbus: Import register mapping or add registers manually

#### 2. Device Added Without Offline Discovery
**Symptom:** Device shows but tree is empty

**Solution:**
- Right-click the device → "Refresh" or "Reconnect"
- For IEC 61850: Import SCD file with device definition

#### 3. Signal Connection Issue
**Symptom:** New devices don't appear at all

**Solution:** Restart the application (this was fixed in the latest update)

### Manual Verification Steps

1. **Check Device Manager has devices:**
   ```python
   # In Python console or debug:
   devices = device_manager.get_all_devices()
   print(f"Total devices: {len(devices)}")
   for d in devices:
       print(f"  - {d.config.name}: connected={d.connected}, root_node={d.root_node is not None}")
   ```

2. **Check DeviceTree has items:**
   ```python
   # In the application:
   print(f"Device items in tree: {len(window.device_tree.device_items)}")
   print(f"Devices: {list(window.device_tree.device_items.keys())}")
   ```

3. **Force refresh:**
   - Close and reopen the application
   - The device should appear if it was saved to `devices.json`

### Testing the Fix

After the latest update, try these steps:

1. **Add a new device:**
   - File → Add Device (or toolbar button)
   - Configure connection details
   - Click Connect

2. **Verify it appears:**
   - Device should appear in Device Explorer immediately
   - Status indicator (🔴/🟢) should show connection state
   - Tree structure should populate after discovery

3. **If still not showing:**
   - Check the terminal/console for error messages
   - Look for exceptions in the Event Log
   - Try restarting the application

### Recent Fixes Applied

✅ Fixed duplicate signal connections in DeviceTreeWidget  
✅ Re-enabled filter functionality  
✅ Added missing attribute initializations  
✅ Fixed device_added signal connection  

If the device still doesn't appear after these fixes, please check:
- The Event Log for error messages
- The terminal output for Python exceptions
- Whether the device has any data/registers configured
