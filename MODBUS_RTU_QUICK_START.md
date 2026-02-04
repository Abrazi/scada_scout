# Modbus RTU Quick Start Guide

## Overview

SCADA Scout now supports full Modbus RTU capability including:
- ✓ Master mode (client)
- ✓ Slave mode (server)
- ✓ Simulation mode
- ✓ RS-485 serial transport
- ✓ USB-to-RS-485 adapters
- ✓ RTU-over-TCP
- ✓ All standard function codes (01-16)
- ✓ Strict CRC validation
- ✓ Proper RTU timing
- ✓ Cross-platform support

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This includes:
- `pyserial` - Serial port communication
- `pymodbus` - Modbus protocol utilities
- `PySide6` - GUI framework

### 2. Verify Installation

```bash
python test_modbus_rtu_comprehensive.py
```

This runs unit tests for:
- Frame handling
- CRC validation
- Simulator functionality
- Timing calculations

## Quick Examples

### Example 1: Connect to RTU Slave Device (Master Mode)

```python
from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.modbus.rtu.master_adapter import ModbusRTUMasterAdapter

# Create configuration
config = DeviceConfig(
    name="RTU Slave 1",
    ip_address="",  # Not used for serial
    port=0,
    device_type=DeviceType.MODBUS_RTU_MASTER,
    rtu_transport="serial",
    serial_port="COM3",  # Windows: COM3, Linux: /dev/ttyUSB0
    serial_baudrate=9600,
    serial_bytesize=8,
    serial_parity='N',  # N=None, E=Even, O=Odd
    serial_stopbits=1.0,
    serial_timeout=1.0,
    rtu_slave_address=1
)

# Create and connect master
master = ModbusRTUMasterAdapter(config)
if master.connect():
    print("Connected!")
    
    # Read holding registers
    registers = master.read_holding_registers(
        slave_address=1,
        start_address=0,
        count=10
    )
    print(f"Registers: {registers}")
    
    # Write single register
    master.write_single_register(
        slave_address=1,
        address=0,
        value=12345
    )
    
    master.disconnect()
```

### Example 2: Start RTU Simulator (Slave Mode)

```python
from src.models.device_models import DeviceConfig, DeviceType
from src.protocols.modbus.rtu.slave_adapter import ModbusRTUSlaveAdapter

# Create simulator configuration
config = DeviceConfig(
    name="RTU Simulator",
    ip_address="",
    port=0,
    device_type=DeviceType.MODBUS_RTU_SIMULATOR,
    rtu_transport="serial",
    serial_port="COM4",  # Different port than master
    serial_baudrate=9600,
    rtu_slave_address=1,
    rtu_simulator_config={
        "coils": {"start": 0, "count": 100},
        "discrete_inputs": {"start": 0, "count": 100},
        "input_registers": {"start": 0, "count": 100},
        "holding_registers": {"start": 0, "count": 100}
    }
)

# Start simulator
slave = ModbusRTUSlaveAdapter(config, simulation=True)
if slave.connect():
    print("Simulator started on address 1")
    print("Press Ctrl+C to stop...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        slave.disconnect()
        print("Simulator stopped")
```

### Example 3: RTU-over-TCP

```python
# Master connecting to RTU-over-TCP device
config = DeviceConfig(
    name="RTU over TCP",
    ip_address="192.168.1.100",
    port=502,
    device_type=DeviceType.MODBUS_RTU_MASTER,
    rtu_transport="rtu_over_tcp",
    rtu_slave_address=1
)

master = ModbusRTUMasterAdapter(config)
if master.connect():
    # Same API as serial
    registers = master.read_holding_registers(1, 0, 10)
    master.disconnect()
```

## Serial Port Configuration

### Finding Serial Ports

```python
from src.protocols.modbus.rtu.transport import list_serial_ports

ports = list_serial_ports()
for device, description in ports:
    print(f"{device}: {description}")
```

**Output:**
```
COM3: USB-SERIAL CH340 (COM3)
COM4: USB-SERIAL CH340 (COM4)
```

### Common Serial Settings

| Setting | Typical Value | Options |
|---------|---------------|---------|
| Baud Rate | 9600 | 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200 |
| Data Bits | 8 | 5, 6, 7, 8 |
| Parity | None | None (N), Even (E), Odd (O), Mark (M), Space (S) |
| Stop Bits | 1 | 1, 1.5, 2 |

**Most Common:** 9600 baud, 8 data bits, No parity, 1 stop bit (9600 8N1)

## Platform-Specific Notes

### Windows

- Ports: `COM1`, `COM2`, `COM3`, etc.
- USB adapters usually auto-install drivers
- No special permissions required

### Linux

- Ports: `/dev/ttyUSB0`, `/dev/ttyS0`, `/dev/ttyAMA0` (Raspberry Pi)
- Add user to `dialout` group: `sudo usermod -a -G dialout $USER`
- Log out and back in for permissions to take effect
- Check permissions: `ls -l /dev/ttyUSB0`

### macOS

- Ports: `/dev/tty.usbserial-XXXX`, `/dev/cu.usbserial-XXXX`
- Use `/dev/cu.*` for opening (not `/dev/tty.*`)
- May need FTDI or Prolific drivers for some USB adapters
- Install drivers from manufacturer website

## Function Codes Reference

| FC | Name | Description | Request | Response |
|----|------|-------------|---------|----------|
| 01 | Read Coils | Read 1-2000 coils | Addr + Count | Byte count + Coil data |
| 02 | Read Discrete Inputs | Read 1-2000 inputs | Addr + Count | Byte count + Input data |
| 03 | Read Holding Registers | Read 1-125 registers | Addr + Count | Byte count + Register data |
| 04 | Read Input Registers | Read 1-125 registers | Addr + Count | Byte count + Register data |
| 05 | Write Single Coil | Write one coil | Addr + Value | Echo request |
| 06 | Write Single Register | Write one register | Addr + Value | Echo request |
| 15 | Write Multiple Coils | Write multiple coils | Addr + Count + Data | Addr + Count |
| 16 | Write Multiple Registers | Write multiple registers | Addr + Count + Data | Addr + Count |

## Address Formats

Modbus RTU uses **Modbus address format** in protocol:

| Type | Protocol Address | Traditional | Example |
|------|------------------|-------------|---------|
| Coils | 0-65535 | 00001-09999 | 0 = coil 00001 |
| Discrete Inputs | 0-65535 | 10001-19999 | 0 = input 10001 |
| Input Registers | 0-65535 | 30001-39999 | 0 = register 30001 |
| Holding Registers | 0-65535 | 40001-49999 | 0 = register 40001 |

**In SCADA Scout:** Addresses use format `slave:function:address`
- `1:3:0` = Slave 1, FC03, Holding Register 0 (40001)
- `2:4:100` = Slave 2, FC04, Input Register 100 (30101)

## Configuration File Format

### JSON Device Configuration

```json
{
  "name": "RTU Device 1",
  "device_type": "Modbus RTU Master",
  "rtu_transport": "serial",
  "serial_port": "COM3",
  "serial_baudrate": 9600,
  "serial_bytesize": 8,
  "serial_parity": "N",
  "serial_stopbits": 1.0,
  "serial_timeout": 1.0,
  "rtu_slave_address": 1,
  "modbus_register_maps": [
    {
      "start_address": 0,
      "count": 10,
      "function_code": 3,
      "data_type": "Unsigned 16-bit",
      "name_prefix": "Sensor_",
      "description": "Temperature Sensors",
      "scale": 0.1,
      "offset": 0.0
    }
  ]
}
```

### Simulator Configuration

```json
{
  "name": "Test Simulator",
  "device_type": "Modbus RTU Simulator",
  "rtu_transport": "serial",
  "serial_port": "COM4",
  "serial_baudrate": 9600,
  "rtu_slave_address": 1,
  "rtu_simulator_config": {
    "coils": {
      "start": 0,
      "count": 100,
      "initial_value": false
    },
    "discrete_inputs": {
      "start": 0,
      "count": 100,
      "initial_value": false
    },
    "input_registers": {
      "start": 0,
      "count": 100,
      "initial_value": 0
    },
    "holding_registers": {
      "start": 0,
      "count": 100,
      "initial_value": 0
    }
  }
}
```

## Testing with Virtual Serial Ports

For testing without hardware, create virtual serial port pairs:

### Windows: com0com

1. Download and install [com0com](https://sourceforge.net/projects/com0com/)
2. Create a pair: COM3 ↔ COM4
3. Connect master to COM3, simulator to COM4

### Linux: socat

```bash
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

Output:
```
2024/01/01 12:00:00 socat[12345] N PTY is /dev/pts/2
2024/01/01 12:00:00 socat[12345] N PTY is /dev/pts/3
```

Use `/dev/pts/2` and `/dev/pts/3` as your port pair.

### macOS: socat

```bash
brew install socat
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

## Troubleshooting

### "Permission denied" on Linux

```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### "Port already in use"

- Close other applications using the port
- On Linux: `lsof /dev/ttyUSB0`
- Kill process or wait for timeout

### No response from slave

1. Check wiring (A to A, B to B, GND to GND)
2. Verify baud rate matches
3. Check slave address
4. Verify RTU timing (inter-frame gap)
5. Enable logging: `logging.basicConfig(level=logging.DEBUG)`

### CRC errors

- Cable too long (max 1200m for RS-485)
- Electromagnetic interference
- Wrong baud rate
- Damaged cable
- Bus termination missing (120Ω resistors at ends)

### Timeouts

- Increase `serial_timeout` value
- Check slave is powered and running
- Verify slave address
- Try slower baud rate

## Performance Tips

1. **Batch Reads**: Read multiple registers in one request
   ```python
   # Good: 1 request
   values = master.read_holding_registers(1, 0, 10)
   
   # Bad: 10 requests
   for addr in range(10):
       value = master.read_holding_registers(1, addr, 1)
   ```

2. **Optimize Baud Rate**: Higher = faster, but less reliable over distance
   - Short cables (<10m): Up to 115200 baud
   - Medium cables (10-100m): 19200-38400 baud
   - Long cables (100m+): 9600 baud or lower

3. **Reduce Polling**: Only poll registers that change
   ```python
   config.polling_enabled = True
   config.poll_interval = 1.0  # seconds
   ```

4. **Use Multiple Slave Addresses**: Distribute load across slaves

## Next Steps

1. **Run Tests**: `python test_modbus_rtu_comprehensive.py`
2. **Try Examples**: Test with virtual serial ports
3. **Connect Hardware**: Test with real RTU devices
4. **Explore UI**: Use SCADA Scout GUI for visual interaction
5. **Read Architecture**: See `MODBUS_RTU_ARCHITECTURE.md` for details

## Support

For issues or questions:
- Check logs with `logging.basicConfig(level=logging.DEBUG)`
- Review architecture documentation
- Test with simulator first before hardware
- Verify serial port configuration

## Reference Links

- [Modbus RTU Specification](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf)
- [pyserial Documentation](https://pyserial.readthedocs.io/)
- [RS-485 Basics](https://www.ti.com/lit/an/slyt324/slyt324.pdf)
