# Modbus TCP Implementation Guide

## Installation

### 1. Install Dependencies

```bash
# Install pymodbus
pip install pymodbus

# Or install all requirements
pip install -r requirements.txt
```

### 2. Verify Installation

```python
# Test pymodbus import
python -c "from pymodbus.client import ModbusTcpClient; print('Modbus OK')"
```

---

## Quick Start

### Connecting to a Modbus TCP Device

1. **Launch Application**
   ```bash
   python src/main.py
   ```

2. **Add New Connection**
   - Click **Connection > Connect...**
   - Select Protocol: **Modbus TCP**
   - Enter IP Address: e.g., `192.168.1.100`
   - Port: `502` (default)
   - Unit ID: `1` (default slave address)
   - Click **OK**

3. **Device Discovery**
   - Application will scan default register ranges:
     - Holding Registers 0-9
     - Input Registers 0-9
     - Coils 0-15
     - Discrete Inputs 0-15

---

## Register Mapping

### Create Custom Register Map (CSV)

Create a CSV file with these columns:

```csv
start_address,count,function_code,data_type,name_prefix,description,scale,offset,endianness
0,10,3,FLOAT32,Temperature,Temperature Sensors,0.1,0,BIG_BIG
100,5,4,UINT16,Pressure,Pressure Readings,1.0,0,BIG_BIG
200,8,1,BOOL,Relay,Relay Outputs,1.0,0,BIG_BIG
```

**Columns:**
- `start_address`: Starting Modbus address
- `count`: Number of registers/coils
- `function_code`: 1=Coils, 2=Discrete Inputs, 3=Holding Registers, 4=Input Registers
- `data_type`: UINT16, INT16, UINT32, INT32, FLOAT32, FLOAT64, BOOL
- `name_prefix`: Prefix for signal names
- `description`: Description for the register group
- `scale`: Multiply raw value by this
- `offset`: Add this to scaled value
- `endianness`: BIG_BIG, BIG_LITTLE, LITTLE_BIG, LITTLE_LITTLE

### Import Register Map

1. In Connection Dialog, click **Import Map (CSV)...**
2. Select your CSV file
3. Map will be applied on connection

---

## Supported Features

### ✅ Reading Operations

| Function Code | Name | Description |
|--------------|------|-------------|
| FC 01 | Read Coils | Read ON/OFF status of coils |
| FC 02 | Read Discrete Inputs | Read ON/OFF status of inputs |
| FC 03 | Read Holding Registers | Read 16-bit registers (R/W) |
| FC 04 | Read Input Registers | Read 16-bit registers (RO) |

### ✅ Writing Operations

| Function Code | Name | Description |
|--------------|------|-------------|
| FC 05 | Write Single Coil | Write ON/OFF to single coil |
| FC 06 | Write Single Register | Write 16-bit value to register |
| FC 15 | Write Multiple Coils | Write multiple coils (auto-detected) |
| FC 16 | Write Multiple Registers | Write multiple registers (auto-detected) |

### ✅ Data Types

- **UINT16**: Unsigned 16-bit integer (0-65535)
- **INT16**: Signed 16-bit integer (-32768 to 32767)
- **UINT32**: Unsigned 32-bit integer (2 registers)
- **INT32**: Signed 32-bit integer (2 registers)
- **FLOAT32**: 32-bit floating point (2 registers)
- **FLOAT64**: 64-bit floating point (4 registers)
- **BOOL**: Boolean value

### ✅ Byte Order (Endianness)

For multi-register values (INT32, FLOAT32, etc.):

- **BIG_BIG (ABCD)**: Big-endian word, big-endian byte (most common)
- **BIG_LITTLE (BADC)**: Big-endian word, little-endian byte
- **LITTLE_BIG (CDAB)**: Little-endian word, big-endian byte
- **LITTLE_LITTLE (DCBA)**: Little-endian word, little-endian byte

---

## Writing to Modbus Devices

### Method 1: Context Menu

1. Right-click on signal in Signals View
2. Select **Control...**
3. Enter new value
4. Click **OK**
5. Optional: Enable "Read back after write to verify"

### Method 2: Watch List

1. Add signal to Watch List
2. Right-click signal
3. Select **Write Value...**

---

## Scaling and Offset

Many devices store values in scaled format. Use scaling to convert:

**Formula:** `Display Value = (Raw Value × Scale) + Offset`

**Example 1: Temperature (0.1°C per unit)**
- Raw value: 235
- Scale: 0.1
- Offset: 0
- Display: 23.5°C

**Example 2: Pressure (PSI, offset by 14.7)**
- Raw value: 100
- Scale: 1.0
- Offset: 14.7
- Display: 114.7 PSI

---

## Troubleshooting

### Connection Fails

**Symptoms:**
- "Connection FAILED" in event log
- Device shows as disconnected

**Solutions:**
1. Verify IP address is correct
2. Check device is powered on
3. Verify port 502 is open (firewall)
4. Check Unit ID matches device configuration
5. Try ping: `ping 192.168.1.100`

### Read Errors

**Symptoms:**
- Quality shows "Invalid"
- Error message in signal error column

**Common Causes:**
1. **Illegal Address**: Register doesn't exist on device
2. **Illegal Function**: Device doesn't support that function code
3. **Slave Failure**: Device internal error
4. **Timeout**: Device not responding

**Solutions:**
- Check device documentation for valid addresses
- Reduce read count if requesting too many registers
- Increase timeout in connection settings

### Wrong Values

**Symptoms:**
- Values don't match expected
- Random numbers displayed

**Solutions:**
1. Check **endianness** setting
2. Verify **data type** (INT vs UINT vs FLOAT)
3. Check **scale** and **offset** values
4. Confirm **starting address** (0-based vs 1-based)

### Write Fails

**Symptoms:**
- "Write operation failed" message
- Device doesn't respond to commands

**Solutions:**
1. Verify signal has **RW** access (not RO)
2. Check device allows writes (some are read-only)
3. Ensure value is within valid range
4. Check connection is still active

---

## Event Log Reference

### Transaction Log Examples

**Successful Read:**
```
→ READ FC3 Unit=1 Addr=100 Count=1
← READ OK: 1234
```

**Successful Write:**
```
→ WRITE FC3 Unit=1 Addr=100 Value=5678
← WRITE SUCCESS
```

**Connection:**
```
→ TCP Connect to 192.168.1.100:502
← Connection SUCCESS
✓ Connected to Unit ID 1
```

**Error:**
```
→ READ FC3 Unit=1 Addr=9999 Count=1
← READ ERROR: IllegalAddress
```

---

## Advanced Usage

### Polling Rate

Adjust in Watch List:
- Default: 1000ms (1 second)
- Minimum: 100ms
- Recommended: 500-2000ms for Modbus TCP

### Multiple Devices

- Each device can have different Unit ID
- Connect to multiple IPs on same network
- Use SCD Import for batch configuration

### Protocol Statistics

View in Event Log:
- Packets sent/received
- Error rate
- Connection uptime
- Average response time

---

## Example Configurations

### PLC (Schneider M221)
```
IP: 192.168.1.10
Port: 502
Unit ID: 1
Holding Registers: 0-999 (UINT16)
```

### Energy Meter (Eastron SDM630)
```
IP: 192.168.1.20
Port: 502
Unit ID: 1
Input Registers: 0-200 (FLOAT32, BIG_BIG)
Scale: 1.0, Offset: 0
```

### Temperature Controller
```
IP: 192.168.1.30
Port: 502
Unit ID: 5
Holding Registers:
  - 0-9: Temperatures (FLOAT32, scale=0.1)
  - 100-109: Setpoints (FLOAT32, scale=0.1)
```

---

## CSV Register Map Template

Save this as `template.csv`:

```csv
start_address,count,function_code,data_type,name_prefix,description,scale,offset,endianness
0,10,3,UINT16,HR,Holding Registers,1.0,0.0,BIG_BIG
0,10,4,UINT16,IR,Input Registers,1.0,0.0,BIG_BIG
0,16,1,BOOL,Coil,Coils,1.0,0.0,BIG_BIG
0,16,2,BOOL,DI,Discrete Inputs,1.0,0.0,BIG_BIG
```

---

## Next Steps

After mastering Modbus TCP:
1. Configure custom register maps for your devices
2. Set up Watch Lists for critical signals
3. Export data trends to Excel
4. Use scripting for automation (future feature)

For more help, check the Event Log for detailed transaction traces!
