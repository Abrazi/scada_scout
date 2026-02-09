# SCADA Scout 🛡️

**Cross-Platform SCADA Protocol Analyzer and Diagnostic Tool**

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-green)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## 🎯 Features

### Protocol Support
- ✅ **Modbus TCP** (Master & Slave)
- ✅ **IEC 61850** (Client mode)
- ✅ **IEC 60870-5-104** (Client mode - coming soon)

### Capabilities
- 🔌 **Dual-Mode Operation**: Act as client or server
- 📊 **Real-time Monitoring**: Watch lists with live updates
- 🔍 **Protocol Analysis**: Detailed transaction logging
- 🌉 **Protocol Gateway**: Bridge between different SCADA protocols
- 📁 **SCD Import**: IEC 61850 configuration file support
- 💾 **Data Export**: CSV, scripts, diagnostics reports
- 🎨 **Modern GUI**: Qt6-based interface with dark theme support

### Cross-Platform
- 🪟 **Windows** 10/11
- 🐧 **Linux** (Ubuntu, Debian, Fedora, RHEL, Arch)
- 🍎 **macOS** (Intel & Apple Silicon)

---

## 🚀 Quick Start

### Installation

#### Windows
```cmd
# Double-click to install
install_scadascout.bat

# Run application
run_scadascout.bat
```

#### Linux/macOS
```bash
# Make executable
chmod +x install_scadascout.sh run_scadascout.sh

# Install
./install_scadascout.sh

# Run
./run_scadascout.sh
```

### Manual Installation
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

---

## 📖 Documentation

- [Installation Guide](CROSS_PLATFORM_INSTALLATION.md) - Detailed platform-specific instructions
- [Modbus TCP Guide](MODBUS_TCP_GUIDE.md) - Modbus client usage
- [Modbus Slave Guide](MODBUS_SLAVE_SERVER_GUIDE.md) - Server/simulator usage
- User Guide - Coming soon
- API Reference - Coming soon

---

## 🎮 Usage Examples

### Connect to Modbus Device

1. **Device → Add Device**
2. Select **Modbus TCP**
3. Enter IP: `192.168.1.100`, Port: `502`
4. Set Unit ID: `1`
5. Click **OK**

### Start Modbus Slave Server

1. **Device → Modbus Slave Server**
2. Configure port (e.g., `5020`)
3. Click **Start Server**
4. Clients can now connect!

### Protocol Gateway (IEC 61850 → Modbus)

```python
# 1. Connect to IEC 61850 device
# 2. Start Modbus slave server
# 3. Map IEC 61850 signals to Modbus registers

from src.core.protocol_gateway import ProtocolGateway, GatewayMapping

gateway = ProtocolGateway(device_manager, modbus_slave, event_logger)
mapping = GatewayMapping(
    source_device="IED_Device",
    source_signal_address="LD0/MMXU1.TotW.mag.f",
    dest_register_type="input",
    dest_address=100
)
gateway.add_mapping(mapping)
gateway.start()
```

### Export Network Configuration

1. **File → Export → Network Config Scripts (All Platforms)**
2. Select output directory
3. Use platform-specific script:
   - Windows: `configure_network_windows.bat`
   - Linux: `configure_network_linux.sh`
   - macOS: `configure_network_macos.sh`

---

## 🏗️ Architecture

```
scada-scout/
├── src/
│   ├── core/              # Core logic
│   │   ├── device_manager.py
│   │   ├── protocol_gateway.py
│   │   └── exporters.py
│   ├── protocols/         # Protocol adapters
│   │   ├── modbus/
│   │   │   ├── adapter.py      (client)
│   │   │   └── slave_server.py (server)
│   │   ├── iec61850/
│   │   └── iec104/
│   ├── ui/                # User interface
│   │   ├── main_window.py
│   │   └── widgets/
│   ├── models/            # Data models
│   └── utils/             # Utilities
│       └── network_utils.py (cross-platform)
├── requirements.txt
└── docs/
```

---

## 🔧 Development

### Setup Development Environment

```bash
git clone https://github.com/yourusername/scada-scout.git
cd scada-scout
python3 -m venv venv-dev
source venv-dev/bin/activate
pip install -r requirements.txt
pip install pytest pytest-qt black flake8
```

### Run Tests

```bash
pytest
```

### Code Style

```bash
black src/
flake8 src/
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📋 Requirements

### Minimum
- Python 3.8+
- 4GB RAM
- 500MB disk space

### Recommended
- Python 3.11+
- 8GB RAM
- SSD storage

### Dependencies
- PySide6 (GUI)
- pymodbus (Modbus support)
- psutil (network utilities)
- numpy (data processing)

### Optional
- pyiec61850 (IEC 61850 support)
- pytest (testing)

---

## 🐛 Troubleshooting

### Application won't start

**Check Python version:**
```bash
python --version  # Must be 3.8+
```

**Reinstall dependencies:**
```bash
pip install --force-reinstall -r requirements.txt
```

### Network scripts fail

**Windows:** Run as Administrator  
**Linux/macOS:** Use `sudo`

### Can't connect to device

1. Check firewall settings
2. Verify IP address and port
3. Test connectivity: Use **File → Export → Diagnostics Report**

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file

---

## 🌟 Acknowledgments

- Built with [PySide6](https://wiki.qt.io/Qt_for_Python)
- Modbus support via [pymodbus](https://github.com/pymodbus-dev/pymodbus)
- IEC 61850 via [libiec61850](https://github.com/mz-automation/libiec61850)
- Network utilities via [psutil](https://github.com/giampaolo/psutil)

---

## 📧 Contact

- **Issues:** [GitHub Issues](https://github.com/yourusername/scada-scout/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/scada-scout/discussions)
- **Email:** support@scadascout.example.com

---

## 🗺️ Roadmap

- [ ] IEC 60870-5-104 real implementation
- [ ] Modbus RTU serial support
- [ ] DNP3 protocol support
- [ ] MQTT gateway
- [ ] Database trending
- [ ] Scripting engine (Python API)
- [ ] Multi-language support
- [ ] Standalone executables (PyInstaller)

---

**Made with ❤️ for SCADA engineers worldwide**
