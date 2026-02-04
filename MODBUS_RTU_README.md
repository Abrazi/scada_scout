# Modbus RTU Implementation

## 📋 Quick Reference

This directory contains a complete, production-ready Modbus RTU implementation for SCADA Scout.

### Key Documents

1. **[MODBUS_RTU_QUICK_START.md](MODBUS_RTU_QUICK_START.md)** - Start here! User-friendly guide with examples
2. **[MODBUS_RTU_ARCHITECTURE.md](MODBUS_RTU_ARCHITECTURE.md)** - Technical architecture and design
3. **[MODBUS_RTU_IMPLEMENTATION_SUMMARY.md](MODBUS_RTU_IMPLEMENTATION_SUMMARY.md)** - Complete implementation status

### Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run tests
python test_modbus_rtu_comprehensive.py

# 3. Try examples
python example_modbus_rtu.py
```

### Features

✅ **Master Mode** - Connect to RTU slave devices  
✅ **Slave Mode** - Act as RTU slave server  
✅ **Simulator** - Software-based testing without hardware  
✅ **RS-485** - Native serial port support  
✅ **USB-RS-485** - Full USB adapter support  
✅ **RTU-over-TCP** - RTU frames over TCP socket  
✅ **All Function Codes** - FC01-FC16 implemented  
✅ **CRC Validation** - Strict Modbus RTU compliance  
✅ **Cross-Platform** - Windows, Linux, macOS  

### File Overview

| File | Purpose |
|------|---------|
| `MODBUS_RTU_QUICK_START.md` | User guide, examples, configuration |
| `MODBUS_RTU_ARCHITECTURE.md` | Technical architecture, module breakdown |
| `MODBUS_RTU_IMPLEMENTATION_SUMMARY.md` | Implementation status, API reference |
| `test_modbus_rtu_comprehensive.py` | Automated test suite |
| `example_modbus_rtu.py` | Interactive examples |
| `src/protocols/modbus/rtu/` | Core implementation modules |

### Basic Usage

```python
from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.modbus.rtu.master_adapter import ModbusRTUMasterAdapter

# Configure device
config = DeviceConfig(
    name="RTU Device",
    device_type=DeviceType.MODBUS_RTU_MASTER,
    rtu_transport="serial",
    serial_port="COM3",
    serial_baudrate=9600,
    rtu_slave_address=1
)

# Connect and read
master = ModbusRTUMasterAdapter(config)
master.connect()
registers = master.read_holding_registers(1, 0, 10)
master.disconnect()
```

### Documentation Roadmap

1. **New Users**: Start with [MODBUS_RTU_QUICK_START.md](MODBUS_RTU_QUICK_START.md)
2. **Developers**: Read [MODBUS_RTU_ARCHITECTURE.md](MODBUS_RTU_ARCHITECTURE.md)
3. **API Reference**: See [MODBUS_RTU_IMPLEMENTATION_SUMMARY.md](MODBUS_RTU_IMPLEMENTATION_SUMMARY.md)

### Support

- Run tests: `python test_modbus_rtu_comprehensive.py`
- Try examples: `python example_modbus_rtu.py`
- Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
- Check serial ports: Use examples menu option 3

### Requirements

- Python 3.8+
- pyserial >= 3.5
- PySide6 >= 6.5.0 (for GUI)

### Implementation Status

✅ **Complete** - All core functionality implemented and tested  
⏳ **Optional** - UI connection dialog (can use JSON config instead)

See [MODBUS_RTU_IMPLEMENTATION_SUMMARY.md](MODBUS_RTU_IMPLEMENTATION_SUMMARY.md) for detailed status.
