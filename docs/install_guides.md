# SCADA Scout - Cross-Platform Installation Guide

## Supported Platforms

✅ **Windows** (10, 11, Server 2016+)  
✅ **Linux** (Ubuntu 20.04+, Debian 11+, RHEL 8+, Fedora 35+)  
✅ **macOS** (11.0 Big Sur+, Intel and Apple Silicon)

---

## Quick Start (All Platforms)

### 1. Prerequisites

- **Python 3.8 or higher**
- **pip** (Python package manager)
- **Git** (optional, for cloning repository)

### 2. Basic Installation

```bash
# Clone repository (or download ZIP)
git clone https://github.com/yourusername/scada-scout.git
cd scada-scout

# Install core dependencies
pip install -r requirements.txt

# Run application
python src/main.py
```

---

## Platform-Specific Instructions

## 🪟 Windows Installation

### Method 1: Using Python from python.org

1. **Download Python**
   - Visit https://www.python.org/downloads/
   - Download Python 3.11+ (64-bit recommended)
   - **Important:** Check "Add Python to PATH" during installation

2. **Install SCADA Scout**
   ```cmd
   cd scada-scout
   pip install -r requirements.txt
   ```

3. **Run Application**
   ```cmd
   python src\main.py
   ```

### Method 2: Using Anaconda/Miniconda

```cmd
conda create -n scadascout python=3.11
conda activate scadascout
cd scada-scout
pip install -r requirements.txt
python src\main.py
```

### Windows-Specific Notes

- **Firewall:** Allow Python through Windows Firewall for network operations
- **Admin Rights:** Network configuration scripts require "Run as Administrator"
- **Virtual Environments:** Recommended to avoid conflicts

### Optional: IEC 61850 Support on Windows

```cmd
# Download pre-built wheel from:
# https://github.com/mz-automation/libiec61850/releases

pip install libiec61850-1.5.0-cp311-cp311-win_amd64.whl
```

---

## 🐧 Linux Installation

### Ubuntu/Debian

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade

# Install Python and dependencies
sudo apt-get install python3 python3-pip python3-venv python3-dev build-essential

# Create virtual environment (recommended)
cd scada-scout
python3 -m venv venv
source venv/bin/activate

# Install SCADA Scout
pip install -r requirements.txt

# Run application
python src/main.py
```

### Fedora/RHEL/CentOS

```bash
# Install Python and tools
sudo dnf install python3 python3-pip python3-devel gcc

# Create virtual environment
cd scada-scout
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt
python src/main.py
```

### Arch Linux

```bash
sudo pacman -S python python-pip base-devel

cd scada-scout
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Linux-Specific Notes

- **Permissions:** Network scripts require `sudo`
- **Virtual Environment:** Always recommended
- **System Python:** Avoid using `sudo pip install` on system Python

### Optional: IEC 61850 on Linux

```bash
# Build from source
git clone https://github.com/mz-automation/libiec61850.git
cd libiec61850
make
cd pyiec61850
python setup.py install
```

---

## 🍎 macOS Installation

### Using Homebrew (Recommended)

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.11

# Create virtual environment
cd scada-scout
python3 -m venv venv
source venv/bin/activate

# Install SCADA Scout
pip install -r requirements.txt

# Run application
python src/main.py
```

### Using Python from python.org

```bash
# Download from https://www.python.org/downloads/macos/
# Install the .pkg file

cd scada-scout
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### macOS-Specific Notes

- **Apple Silicon (M1/M2):** Works natively, some packages may require Rosetta 2
- **Permissions:** Network scripts require `sudo`
- **Xcode Tools:** May be required: `xcode-select --install`

### Optional: IEC 61850 on macOS

```bash
# Install dependencies
brew install cmake

# Build libiec61850
git clone https://github.com/mz-automation/libiec61850.git
cd libiec61850
mkdir build && cd build
cmake ..
make
cd ../pyiec61850
python setup.py install
```

---

## Verification

### Test Installation

```bash
# Activate virtual environment (if using one)
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Run test script
python -c "
import sys
print(f'Python: {sys.version}')

try:
    import PySide6
    print('✓ PySide6 installed')
except ImportError:
    print('✗ PySide6 missing')

try:
    import pymodbus
    print('✓ pymodbus installed')
except ImportError:
    print('✗ pymodbus missing')

try:
    import psutil
    print('✓ psutil installed')
except ImportError:
    print('✗ psutil missing')

try:
    from pyiec61850 import iec61850
    print('✓ IEC 61850 support available')
except ImportError:
    print('⚠ IEC 61850 not installed (optional)')
"
```

Expected output:
```
Python: 3.11.x
✓ PySide6 installed
✓ pymodbus installed
✓ psutil installed
⚠ IEC 61850 not installed (optional)
```

### Launch Application

```bash
python src/main.py
```

You should see the SCADA Scout main window.

---

## Troubleshooting

### Common Issues

#### Import Error: No module named 'PySide6'

**Solution:**
```bash
pip install --upgrade pip
pip install PySide6
```

#### Permission Denied (Linux/macOS)

**Solution:**
```bash
# Don't use sudo pip! Use virtual environment instead
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Qt Platform Plugin Error

**Windows:**
```cmd
set QT_QPA_PLATFORM_PLUGIN_PATH=%VIRTUAL_ENV%\Lib\site-packages\PySide6\plugins\platforms
```

**Linux:**
```bash
export QT_QPA_PLATFORM_PLUGIN_PATH=$VIRTUAL_ENV/lib/python3.11/site-packages/PySide6/Qt/plugins
```

#### libiec61850 Build Fails

**Solution:** Use Modbus TCP only (fully supported), IEC 61850 is optional

#### Network Scripts Don't Work

**Windows:** Right-click → "Run as Administrator"  
**Linux/macOS:** Use `sudo bash script.sh`

---

## Development Setup

### For Contributors

```bash
# Clone repository
git clone https://github.com/yourusername/scada-scout.git
cd scada-scout

# Create development environment
python3 -m venv venv-dev
source venv-dev/bin/activate  # or venv-dev\Scripts\activate on Windows

# Install with dev dependencies
pip install -r requirements.txt
pip install pytest pytest-qt black flake8

# Run tests
pytest

# Run with logging
python src/main.py --debug
```

---

## Performance Optimization

### Linux: Reduce Startup Time

```bash
# Pre-compile Python files
python -m compileall src/

# Use PyPy for better performance (optional)
pypy3 -m venv venv-pypy
source venv-pypy/bin/activate
pip install -r requirements.txt
```

### Windows: Reduce Antivirus Impact

- Add Python directory to antivirus exclusions
- Add scada-scout directory to exclusions

### macOS: Disable Gatekeeper Warnings

```bash
xattr -dr com.apple.quarantine scada-scout/
```

---

## Uninstallation

### Remove Virtual Environment

```bash
# Simply delete the venv directory
rm -rf venv  # Linux/macOS
rmdir /s venv  # Windows
```

### System-Wide Uninstall

```bash
pip uninstall PySide6 pymodbus psutil numpy -y
```

---

## Next Steps

After successful installation:

1. **Read User Guide:** `docs/USER_GUIDE.md`
2. **Try Modbus Example:** `docs/MODBUS_TCP_GUIDE.md`
3. **Configure First Device:** Connection → Connect to Device
4. **Join Community:** Report issues on GitHub

---

## Support

- **Documentation:** `docs/` directory
- **Issues:** https://github.com/yourusername/scada-scout/issues
- **Discussions:** GitHub Discussions
- **Email:** support@scadascout.example.com

---

## License

MIT License - See `LICENSE` file for details
