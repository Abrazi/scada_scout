# Modbus Slave/Server Implementation Guide

## Overview

SCADA Scout now supports **dual-mode Modbus operation**:
- ✅ **Master/Client Mode**: Connect to remote Modbus devices (existing)
- ✅ **Slave/Server Mode**: Act as a Modbus device for testing (NEW)

---

## Use Cases

### 1. Device Simulation
Simulate PLCs, RTUs, or other Modbus devices without physical hardware.

**Example:**
- Test your SCADA HMI software
- Validate client applications
- Create training environments

### 2. Protocol Gateway
Bridge data from other protocols (IEC 61850, IEC 104) to Modbus.

**Example:**
- Read IEC 61850 IED data
- Expose it as Modbus registers
- Legacy systems can access modern devices

### 3. Development & Testing
Develop and test Modbus applications without real devices.

**Example:**
- Test edge cases
- Simulate error conditions
- Performance testing with high register counts

---

## Quick Start

### Starting the Slave Server

1. **Open Slave Server Panel**
   - Menu: **Connection > Modbus Slave Server...**
   - Or: **View** menu and enable "Modbus Slave Server"

2. **Configure Server**
   - Listen Address: `0.0.0.0` (all interfaces)
   - Port: `5020` (avoid conflict with standard 502)
   - Click **Start Server**

3. **Server is Running!**
   - Status shows "Server: Running on 0.0.0.0:5020"
   - Now accepts client connections

### Connecting a Client

From another application or SCADA Scout instance:

```
IP: 127.0.0.1 (localhost) or your computer's IP
Port: 5020
Unit ID: 1
```

---

## Register Management

### Manual Register Editing

1. **Select Register Type**
   - Holding Registers (FC 03/06/16)
   - Input Registers (FC 04)
   - Coils (FC 01/05/15)
   - Discrete Inputs (FC 02)

2. **Edit Values**
   - Double-click value in table
   - Enter new value
   - Press Enter

3. **Quick Write**
   - Enter Address and Value
   - Click "Write"

### Bulk Operations

#### Import from CSV

Create a CSV file:
```csv
address,value,hex
0,1234,0x04D2
1,5678,0x162E
2,9999,0x270F
```

Click **Import CSV...** and select your file.

#### Export to CSV

Click **Export CSV...** to save current register values.

### Clear All Registers

Click **Clear All** to reset all registers to zero.

---

## Simulation Features

### Automatic Sensor Simulation

Enable **"Enable sensor simulation"** checkbox to automatically update:

| Register | Type | Description | Range |
|----------|------|-------------|-------|
| Input Reg 0 | Temperature | Simulated temperature sensor | 20.0-30.0°C |
| Input Reg 1 | Pressure | Simulated pressure sensor | 1000-1100 |
| Discrete 0-7 | Binary | Random state changes | ON/OFF |

Updates every second with realistic variations.

### Pattern Generation

#### Ramp Pattern
Generates ascending values 0-99 in registers 0-99.

**Use Case:** Test trending, min/max detection

#### Sine Wave Pattern
Generates sine wave values in registers 0-99.

**Use Case:** Test analog signal processing

#### Random Pattern
Fills all registers with random values.

**Use Case:** Stress testing, noise simulation

---

## Protocol Gateway

### Concept

Gateway bridges protocols by:
1. Reading from source device (IEC 61850, etc.)
2. Transforming data (scale, offset)
3. Writing to Modbus slave registers

### Setup Example

**Scenario:** Expose IEC 61850 temperature to Modbus

1. **Connect to IEC 61850 Device**
   - Normal connection as client

2. **Start Modbus Slave Server**
   - Listening for Modbus clients

3. **Create Gateway Mapping** (programmatic):
   ```python
   from src.core.protocol_gateway import ProtocolGateway, GatewayMapping
   
   gateway = ProtocolGateway(device_manager, modbus_slave, event_logger)
   
   mapping = GatewayMapping(
       source_device="IED_192_168_1_10",
       source_signal_address="LD0/MMXU1.TotW.mag.f",  # IEC 61850 address
       dest_register_type="input",
       dest_address=100,  # Modbus Input Register 100
       scale=1.0,
       offset=0.0
   )
   
   gateway.add_mapping(mapping)
   gateway.start()
   ```

4. **Result**
   - IEC 61850 power measurement appears at Modbus register 100
   - Updates every second
   - Legacy Modbus clients can read it!

### Gateway Mappings

| Field | Description |
|-------|-------------|
| Source Device | Name of connected device |
| Source Signal | Full signal address |
| Dest Register Type | holding, input, coils, discrete |
| Dest Address | Modbus address (0-999) |
| Scale | Multiply source value |
| Offset | Add to scaled value |

**Transformation Formula:**
```
Modbus Value = (Source Value × Scale) + Offset
```

### Export/Import Mappings

Save mappings to CSV for reuse:

```csv
source_device,source_signal,dest_register_type,dest_address,scale,offset,enabled
IED_Device,LD0/XCBR1.Pos.stVal,coils,0,1.0,0.0,True
IED_Device,LD0/MMXU1.TotW.mag.f,input,100,0.001,0.0,True
```

---

## Advanced Configuration

### Server Configuration

Edit `ModbusSlaveConfig` parameters programmatically:

```python
from src.protocols.modbus.slave_server import ModbusSlaveConfig

config = ModbusSlaveConfig(
    name="Custom Simulator",
    listen_address="192.168.1.100",  # Specific interface
    port=502,  # Standard Modbus port (requires admin)
    
    # Increase register counts
    coils_count=5000,
    discrete_inputs_count=5000,
    holding_registers_count=5000,
    input_registers_count=5000,
    
    # Device identification
    vendor_name="My Company",
    product_name="Custom Device Simulator"
)
```

### Multi-Slave Support

Currently supports **Unit ID 1**. Future enhancement will support multiple unit IDs.

### Security Considerations

⚠️ **Warning:** Modbus TCP has no built-in security!

**Best Practices:**
- Use non-standard ports (not 502)
- Bind to `127.0.0.1` for local testing only
- Use firewall to restrict access
- For production, use VPN or other network security

---

## Testing Scenarios

### Test 1: Basic Read/Write

**Objective:** Verify client can read and write

1. Start slave server
2. Write value 1234 to Holding Register 0
3. Connect with client (e.g., `mbpoll` utility):
   ```bash
   # Read
   mbpoll -a 1 -r 0 -c 10 127.0.0.1 -p 5020
   
   # Write
   mbpoll -a 1 -r 0 -t 4 127.0.0.1 -p 5020 5678
   ```
4. Verify value changed in SCADA Scout

### Test 2: Simulation

**Objective:** Test dynamic data

1. Enable sensor simulation
2. Connect client
3. Continuously poll Input Register 0
4. Verify temperature values change (20.0-30.0°C range)

### Test 3: Gateway

**Objective:** Bridge IEC 61850 to Modbus

1. Connect to real IEC 61850 device
2. Start Modbus slave
3. Create gateway mapping
4. Connect Modbus client
5. Verify IEC 61850 data appears in Modbus registers

### Test 4: Performance

**Objective:** Stress test with high load

1. Generate random pattern in all 1000 registers
2. Connect multiple clients
3. Poll registers continuously
4. Monitor CPU usage and response times

---

## Troubleshooting

### Server Won't Start

**Error:** "Address already in use"

**Solution:**
- Another process is using the port
- Change port number (5020 → 5021)
- Or stop conflicting process

**Error:** "Permission denied" (port 502 on Linux/Mac)

**Solution:**
- Ports < 1024 require root/admin
- Use port ≥ 1024 (e.g., 5020)
- Or run with `sudo` (not recommended)

### Client Can't Connect

**Symptoms:**
- Timeout errors
- Connection refused

**Solutions:**
1. Verify server is running (status shows "Running")
2. Check firewall allows incoming connections
3. Ping server: `ping 127.0.0.1`
4. Test port: `telnet 127.0.0.1 5020`
5. Try `0.0.0.0` instead of specific IP

### Wrong Values

**Symptoms:**
- Client reads different values than displayed

**Solutions:**
1. Verify Unit ID is 1
2. Check register type (FC 03 vs 04)
3. Refresh register view in SCADA Scout
4. Check byte order (big-endian)

### Performance Issues

**Symptoms:**
- Slow response times
- Timeouts with many clients

**Solutions:**
1. Reduce simulation update rate
2. Limit number of concurrent clients
3. Increase client timeout values
4. Use smaller register blocks

---

## Command-Line Tools

### mbpoll (Linux/Mac/Windows)

Install:
```bash
# Linux
apt-get install mbpoll

# Mac
brew install mbpoll

# Windows: Download from https://github.com/epsilonrt/mbpoll
```

Examples:
```bash
# Read 10 holding registers starting at 0
mbpoll -a 1 -r 0 -c 10 -t 4 127.0.0.1 -p 5020

# Write single register
mbpoll -a 1 -r 0 -t 4 127.0.0.1 -p 5020 1234

# Read coils
mbpoll -a 1 -r 0 -c 16 -t 0 127.0.0.1 -p 5020

# Continuous polling (1 second interval)
mbpoll -a 1 -r 0 -c 10 -t 4 -l 1000 127.0.0.1 -p 5020
```

### pymodbus Console (Python)

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('127.0.0.1', port=5020)
client.connect()

# Read (pymodbus 3.x)
result = client.read_holding_registers(0, 10, slave=1)
if not result.isError():
    print(result.registers)

# Write
client.write_register(0, 1234, slave=1)

client.close()
```

---

## API Reference

### ModbusSlaveServer

```python
from src.protocols.modbus.slave_server import ModbusSlaveServer, ModbusSlaveConfig

# Create server
config = ModbusSlaveConfig(port=5020)
server = ModbusSlaveServer(config, event_logger)

# Start/Stop
server.start()
server.stop()

# Write registers programmatically
server.write_register(0, 1234)
server.write_input_register(100, 5678)
server.write_coil(0, True)
server.write_discrete_input(0, False)

# Read registers
value = server.read_register(0)
coil = server.read_coil(0)

# Bulk operations
server.bulk_write_registers(0, [1, 2, 3, 4, 5])

# Simulation
server.simulate_sensor_updates(True)

# Export/Import
data = server.get_all_registers("holding")
server.import_register_data({0: 100, 1: 200}, "holding")
```

### ProtocolGateway

```python
from src.core.protocol_gateway import ProtocolGateway, GatewayMapping

gateway = ProtocolGateway(device_manager, modbus_slave, event_logger)

# Add mapping
mapping = GatewayMapping(
    source_device="IED_Device",
    source_signal_address="LD0/MMXU1.TotW.mag.f",
    dest_register_type="input",
    dest_address=100,
    scale=0.001,  # kW to W
    offset=0.0
)
mapping_id = gateway.add_mapping(mapping)

# Control
gateway.start()
gateway.set_update_interval(500)  # 500ms
gateway.stop()

# Export/Import
gateway.export_mappings("mappings.csv")
count = gateway.import_mappings("mappings.csv")
```

---

## Future Enhancements

Planned features:

- [ ] Multi-slave support (Unit IDs 1-247)
- [ ] Modbus RTU serial support
- [ ] GUI for gateway mapping editor
- [ ] Register value logging to database
- [ ] Alarm simulation
- [ ] Custom Modbus exceptions
- [ ] Authentication/encryption layer

---

## Summary

You now have **complete Modbus dual-mode capability**:

✅ **Client Mode:** Connect to devices, read/write registers  
✅ **Server Mode:** Simulate devices, serve register data  
✅ **Gateway Mode:** Bridge protocols seamlessly  

This makes SCADA Scout a **powerful testing and integration tool** for Modbus TCP environments!
