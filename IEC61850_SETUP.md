# IEC 61850 Setup Guide

## Overview

SCADA Scout uses **libiec61850** with pure Python ctypes bindings for cross-platform IEC 61850 protocol support. This approach works on Windows, Linux, and macOS without requiring SWIG or compiled Python extensions.

## Requirements

You need the **libiec61850** native library compiled and available on your system:
- **Windows**: `iec61850.dll` or `libiec61850.dll`
- **Linux**: `libiec61850.so` or `libiec61850.so.1`
- **macOS**: `libiec61850.dylib`

## Installation Options

### Option 1: Pre-compiled Binaries (Easiest)

If pre-compiled binaries are available for your platform, download and install them.

#### Windows
1. Download pre-built DLL from libiec61850 releases
2. Place `iec61850.dll` in one of:
   - System32 folder (`C:\Windows\System32`)
   - Project directory (`C:\Users\majid\Documents\scada_scout\lib`)
   - Add directory to PATH environment variable

#### Linux (Ubuntu/Debian)
```bash
# Check if available in package manager
sudo apt-cache search libiec61850
sudo apt-get install libiec61850-dev  # if available
```

#### macOS
```bash
# Check Homebrew
brew search libiec61850
brew install libiec61850  # if available
```

### Option 2: Build from Source

If pre-compiled binaries aren't available, you'll need to build libiec61850 from source.

#### Prerequisites

**All Platforms:**
- Git
- CMake (version 3.0 or higher)
- C compiler (GCC, Clang, or MSVC)

**Windows:**
- MSYS2/MinGW (recommended) OR Visual Studio 2017+

**Linux:**
```bash
sudo apt-get update
sudo apt-get install build-essential cmake git
```

**macOS:**
```bash
xcode-select --install  # Install Xcode Command Line Tools
brew install cmake
```

#### Build Instructions

##### Windows (MSYS2/MinGW - Recommended)

1. **Install MSYS2** from https://www.msys2.org/
2. **Open MSYS2 MinGW 64-bit terminal**
3. **Install build tools:**
   ```bash
   pacman -S mingw-w64-x86_64-gcc mingw-w64-x86_64-cmake make git
   ```
4. **Clone and build libiec61850:**
   ```bash
   cd ~
   git clone https://github.com/mz-automation/libiec61850.git
   cd libiec61850
   mkdir build && cd build
   cmake .. -G "MinGW Makefiles"
   mingw32-make
   ```
5. **Install the library:**
   ```bash
   mingw32-make install
   ```
6. **Copy DLL to project (if not in system PATH):**
   ```bash
   cp libiec61850.dll /c/Users/majid/Documents/scada_scout/lib/
   ```

##### Windows (Visual Studio)

1. **Open Visual Studio Developer Command Prompt**
2. **Clone repository:**
   ```cmd
   cd %USERPROFILE%
   git clone https://github.com/mz-automation/libiec61850.git
   cd libiec61850
   ```
3. **Build with CMake:**
   ```cmd
   mkdir build
   cd build
   cmake .. -G "Visual Studio 16 2019"  # Adjust version as needed
   cmake --build . --config Release
   ```
4. **Copy DLL:**
   ```cmd
   copy Release\iec61850.dll C:\Users\majid\Documents\scada_scout\lib\
   ```

##### Linux

```bash
# Clone repository
git clone https://github.com/mz-automation/libiec61850.git
cd libiec61850

# Build
mkdir build && cd build
cmake ..
make

# Install system-wide (requires sudo)
sudo make install
sudo ldconfig  # Update library cache

# OR install locally
cp libiec61850.so ~/Documents/scada_scout/lib/
```

##### macOS

```bash
# Clone repository
git clone https://github.com/mz-automation/libiec61850.git
cd libiec61850

# Build
mkdir build && cd build
cmake ..
make

# Install system-wide
sudo make install

# OR install locally
cp libiec61850.dylib ~/Documents/scada_scout/lib/
```

## Verification

To verify the library is correctly installed and accessible:

```bash
# Navigate to project directory
cd C:\Users\majid\Documents\scada_scout  # Windows
cd ~/Documents/scada_scout  # Linux/macOS

# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Test import
python -c "from src.protocols.iec61850 import iec61850_wrapper; print('Library loaded:', iec61850_wrapper.is_library_loaded())"
```

Expected output:
```
Library loaded: True
```

If you see an error, check:
1. Library file exists in system PATH or project `lib/` directory
2. Library architecture matches Python (64-bit Python needs 64-bit library)
3. On Windows, required DLL dependencies are available

## Troubleshooting

### Library Not Found

**Windows:**
```powershell
# Check if DLL exists
Test-Path "C:\Windows\System32\iec61850.dll"
Test-Path "C:\Users\majid\Documents\scada_scout\lib\iec61850.dll"

# Check PATH
$env:PATH -split ';' | Select-String "iec61850"
```

**Linux:**
```bash
# Check if .so exists
ldconfig -p | grep libiec61850

# Check LD_LIBRARY_PATH
echo $LD_LIBRARY_PATH
```

**macOS:**
```bash
# Check DYLD_LIBRARY_PATH
echo $DYLD_LIBRARY_PATH

# Check default paths
ls /usr/local/lib/libiec61850.dylib
```

### Architecture Mismatch

Ensure Python and library are both 32-bit or both 64-bit:

```python
import platform
print("Python architecture:", platform.architecture()[0])
```

To check library architecture:
- **Windows**: Use tools like Dependency Walker
- **Linux**: `file /path/to/libiec61850.so`
- **macOS**: `file /path/to/libiec61850.dylib`

### Missing Dependencies

**Windows:**
Use [Dependencies](https://github.com/lucasg/Dependencies) tool to check for missing DLLs.

**Linux:**
```bash
ldd /path/to/libiec61850.so
```

**macOS:**
```bash
otool -L /path/to/libiec61850.dylib
```

### Permission Issues

**Linux/macOS:**
```bash
# If library in project directory
chmod +x ~/Documents/scada_scout/lib/libiec61850.*
```

## Alternative: Use Existing libiec61850 in Project

If you already have the libiec61850 library files compiled, you can use them directly:

```bash
# Create lib directory in project
mkdir -p C:\Users\majid\Documents\scada_scout\lib  # Windows
mkdir -p ~/Documents/scada_scout/lib  # Linux/macOS

# Copy your pre-compiled library there
# Windows: copy libiec61850.dll to lib\
# Linux: copy libiec61850.so to lib/
# macOS: copy libiec61850.dylib to lib/
```

The ctypes wrapper will automatically search this directory.

## Getting Help

If you encounter issues:
1. Check the libiec61850 repository: https://github.com/mz-automation/libiec61850
2. Review build logs for errors
3. Ensure all prerequisites are installed
4. Try building a simple C example from libiec61850 to verify library works

## Next Steps

Once the library is installed and verified:
1. Run SCADA Scout: `python src/main.py`
2. Try connecting to an IEC 61850 device
3. Test device discovery and data reading
