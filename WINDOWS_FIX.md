# Windows Compatibility Fix

## Issue
After migrating from Linux to Windows, the application would crash immediately after launch with exit code 1, showing no Python exception.

## Root Cause
The crash was caused by **corrupted Qt QSettings** stored in the Windows Registry. These settings were created on Linux and were incompatible with Windows, causing Qt to crash silently during window initialization.

## Solution
The Windows Registry keys containing the corrupted settings were cleared:
- `HKEY_CURRENT_USER\Software\scada_scout`
- `HKEY_CURRENT_USER\Software\ScadaScout`

## If You Experience This Issue

Run these PowerShell commands to clear the settings:

```powershell
# Clear scada_scout settings
reg delete "HKEY_CURRENT_USER\Software\scada_scout" /f 2>$null

# Clear ScadaScout settings
reg delete "HKEY_CURRENT_USER\Software\ScadaScout" /f 2>$null
```

Then run the application normally. It will recreate fresh Windows-compatible settings.

## Running the Application

### Windows
```batch
# Using the launcher script (recommended)
run_scadascout.bat

# Or directly with Python
venv\Scripts\python.exe src\main.py
```

### Linux/macOS
```bash
# Using the launcher script (recommended)
./run_scadascout.sh

# Or directly with Python
source venv/bin/activate
python src/main.py
```

## Code Fixes Applied

1. **DeviceTreeWidget** (`src/ui/widgets/device_tree.py`):
   - Removed duplicate `_setup_view()` call
   - Moved signal connections from `add_device()` to `__init__()` to prevent duplicate connections
   - Added proper initialization of filter tracking attributes

2. **Main Entry Point** (`src/main.py`):
   - Restored cross-platform compatibility
   - Proper path handling for Windows, Linux, and macOS
   - Added `sys.exit()` for proper exit code handling

## Prevention

To avoid this issue in the future when moving between platforms:
1. Don't commit QSettings files or registry exports
2. Clear application settings when switching platforms
3. Use the provided launcher scripts which handle platform differences
