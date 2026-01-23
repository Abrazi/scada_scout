# IEC 61850 Dynamic Model Configuration

## Overview

SCADA Scout's IEC 61850 server has two model loading modes:

1. **Native Parser** (preferred): Uses libiec61850's ConfigFileParser - most stable
2. **Python Dynamic Builder** (fallback): Builds model from SCD using Python/ctypes - may be unstable with some DLL builds

## Important Note About .lib vs .dll Files

**`.lib` files CANNOT be used with Python!**

- `.lib` = Static library for C/C++ compilation (link-time)
- `.dll` = Dynamic library for runtime loading (what Python needs)

You need the **`.dll`** file from your libiec61850 build.

## Using a Different libiec61850 DLL

### Option 1: Environment Variable (Recommended)

Set the path to your custom DLL before running:

```powershell
# Windows PowerShell
$env:LIBIEC61850_PATH = "C:\path\to\your\libiec61850.dll"
& C:/Users/majid/Documents/scadaScout/scada_scout/venv/Scripts/python.exe src/main.py
```

```bash
# Linux/macOS
export LIBIEC61850_PATH="/path/to/your/libiec61850.so"
python src/main.py
```

### Option 2: Copy to Project

Copy your DLL to one of these locations:
- `scada_scout/lib/iec61850.dll` (or libiec61850.dll)
- `scada_scout/src/protocols/iec61850/iec61850.dll`
- `scada_scout/libiec61850-1.6.1/build/iec61850.dll`

## Dynamic Model Builder Control

The Python dynamic builder is now **enabled by default** but may crash with some libiec61850 builds.

### Disable Dynamic Builder (Use Minimal Model Only)

```powershell
# Windows
$env:IEC61850_USE_DYNAMIC_BUILDER = "false"
python src/main.py
```

```bash
# Linux/macOS
export IEC61850_USE_DYNAMIC_BUILDER=false
python src/main.py
```

With dynamic builder disabled:
- Only LLN0 logical node exposed
- Very stable (won't crash)
- Minimal functionality for testing

### Enable Dynamic Builder (Full Model from SCD)

```powershell
# Windows
$env:IEC61850_USE_DYNAMIC_BUILDER = "true"  # This is the default
python src/main.py
```

With dynamic builder enabled:
- Full model from SCD parsed and exposed
- All logical devices, nodes, data objects
- May crash with some libiec61850 DLL builds
- Up to 10,000 attributes supported

## Testing Your Setup

### Step 1: Check which DLL is loaded

Add this to your PowerShell before running:
```powershell
$env:IEC61850_USE_DYNAMIC_BUILDER = "true"
python -c "from src.protocols.iec61850 import iec61850_wrapper; print(iec61850_wrapper._lib)"
```

### Step 2: Run with dynamic builder

```powershell
# Run as Administrator (for port 102)
Start-Process -FilePath "$env:USERPROFILE\Documents\scadaScout\scada_scout\venv\Scripts\python.exe" -ArgumentList "$env:USERPROFILE\Documents\scadaScout\scada_scout\src\main.py" -Verb RunAs
```

Watch the logs for:
- ✅ "Dynamic model built from SCD" = Success!
- ❌ Application crash = Your DLL doesn't support dynamic models

### Step 3: If it crashes, disable dynamic builder

```powershell
$env:IEC61850_USE_DYNAMIC_BUILDER = "false"
# Run again - will use minimal model only
```

## Finding a Working libiec61850 DLL

### Option A: Rebuild from Source

1. Get libiec61850 source: https://github.com/mz-automation/libiec61850
2. Build with CMake:
   ```bash
   mkdir build && cd build
   cmake .. -DBUILD_EXAMPLES=OFF
   cmake --build .
   ```
3. Look for `iec61850.dll` in `build/` directory
4. Copy to SCADA Scout `lib/` directory

### Option B: Use Pre-built Binary

Some libiec61850 distributions provide pre-compiled DLLs:
- Check your vendor's SDK
- Look in binary distribution packages
- Try different versions (1.4.x, 1.5.x, 1.6.x)

### Option C: Use Alternative Tools

If dynamic model building doesn't work:
- Use libiec61850 demo apps as server (e.g., `server_example_61850`)
- Connect SCADA Scout as a **client** instead of server
- Use external IEC 61850 simulators

## Current Behavior

**As configured now:**
- Dynamic builder: **ENABLED** (default)
- Custom DLL path: Check `LIBIEC61850_PATH` environment variable
- Model limit: 10,000 attributes (increased from 5,000)

If your libiec61850 DLL has a working ConfigFileParser, it will be used automatically (best case).
