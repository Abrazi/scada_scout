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

## 📖 Documentation

See the following files for detailed information:
- `CROSS_PLATFORM_INSTALLATION.md` - Installation guide
- `MODBUS_TCP_GUIDE.md` - Modbus usage
- `MODBUS_SLAVE_SERVER_GUIDE.md` - Server mode

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
