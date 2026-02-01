# SCADA Scout 🛡️

**Cross-Platform SCADA Protocol Analyzer and Diagnostic Tool**

## 🚀 Quick Start

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python src/main.py
```

### Optional: OPC UA support

OPC UA is provided as an opt-in extension (server + client). To install the
optional dependency and run OPC UA examples/tests:

```bash
# install optional OPC UA support
pip install -e '.[opc]'
# or install python-opcua directly
pip install opcua
```

The OPC integration is guarded — missing the optional package will not affect
existing Modbus or IEC 61850 features.

### Native dependency: libiec61850

This project uses the native `libiec61850` library with **pure Python ctypes bindings** (no SWIG or compiled extensions required). 

**Important:** You must have the compiled libiec61850 shared library (DLL/SO/DYLIB) installed on your system:
- Windows: `iec61850.dll` or `libiec61850.dll`
- Linux: `libiec61850.so`
- macOS: `libiec61850.dylib`

**See [IEC61850_SETUP.md](IEC61850_SETUP.md) for complete installation instructions** including:
- Pre-compiled binary installation
- Building from source for Windows/Linux/macOS  
- Troubleshooting common issues


## 📖 Documentation

### Setup & Installation
- `IEC61850_SETUP.md` - IEC 61850 library installation guide
- `CROSS_PLATFORM_INSTALLATION.md` - Installation guide

### Protocol Guides
- `MODBUS_TCP_GUIDE.md` - Modbus usage
- `MODBUS_SLAVE_SERVER_GUIDE.md` - Server mode
- **`IEC61850_SBO_CONTROL_FIX.md`** - ⭐ IEC 61850 control operations (SBO) - Complete guide
- **`QUICK_REFERENCE_CONTROL.md`** - ⭐ IEC 61850 control quick reference

### Control Operations (IEC 61850)
**NEW:** Fixed implementation for IEC 61850 SBO (Select-Before-Operate) control:
- ✅ Correct `.Oper.ctlVal` path handling
- ✅ Proper SBO sequence (Select → Operate)
- ✅ Complete control parameter support
- ✅ Automatic control model detection

**Quick Start:**
```python
from protocols.iec61850.control_client_fixed import IEC61850ControlClient
client = IEC61850ControlClient(connection)
client.control("LD0/CSWI1.Pos", True)  # Automatic SBO handling
```

**Files:**
- `src/protocols/iec61850/control_client_fixed.py` - Fixed control client implementation
- `test_control_fixed.py` - Comprehensive test suite
- `INTEGRATION_SNIPPET.py` - Integration examples
- `IMPLEMENTATION_SUMMARY.md` - Complete implementation details

## ✨ Features

- ✅ Modbus TCP (Master & Slave)
- ✅ IEC 61850 (Client)
- ✅ Cross-platform (Windows/Linux/macOS)
- ✅ Protocol Gateway
- ✅ Event Logging

## 📜 License

MIT License - See LICENSE file


Create a virtual environment for your project and install requirements there.

1️⃣ Install venv support (if not already installed)
sudo apt update
sudo apt install python3-full python3-venv -y

2️⃣ Go to your project directory
cd ~/Documents/scada_scout

3️⃣ Create a virtual environment
python3 -m venv venv

4️⃣ Activate the virtual environment
source venv/bin/activate


You should now see something like:

(venv) majid@majid-ThinkPad:~/Documents/scada_scout$

5️⃣ Install requirements
pip install -r requirements.txt


✅ This is the proper Python way and won’t break your system.

🚫 What NOT to do (unless you really know why)
pip install -r requirements.txt --break-system-packages


⚠️ This can break your OS Python and cause system tools to fail.

🧠 Extra Tips

Every time you work on this project:

source venv/bin/activate


To leave the venv:

deactivate
