# Modbus Server CSV Import Guide

## Overview

SCADA Scout now supports importing register definitions from CSV files to configure Modbus TCP Slave Servers. This allows you to:

1. Define register layouts in CSV format
2. Automatically configure Modbus servers with proper register blocks
3. Set up data types, scaling, and endianness for each register
4. Create multiple Modbus servers with the same register layout

## What Are Modbus Servers?

**Modbus TCP Servers (Slave Devices)** are software components that:
- Listen on a TCP port (usually 502)
- Respond to Modbus protocol requests from clients
- Maintain register data (coils, discrete inputs, holding registers, input registers)
- Allow external systems to read/write data via Modbus protocol

In SCADA Scout, you can create virtual Modbus servers for:
- **Simulation**: Simulate PLCs, RTUs, or other devices
- **Testing**: Test SCADA systems without hardware
- **Gateway**: Bridge between different protocols
- **Development**: Develop and test Modbus client applications

## CSV Format

### Basic Format (Triangle MicroWorks Compatible)

```csv
IsEnabled,Index,PointType,Name,Description,Direction,Value,Quality
True,0,4,R000,Generator State,None,0,0
True,1,4,R001,Control Mode,None,0,0
```

### Extended Format (With Data Types)

```csv
IsEnabled,Index,PointType,Name,Description,Direction,Value,Quality,DataType,Endianness,Scale,Offset
True,10,4,R010,Voltage (V),Output,0,0,UINT16,BIG_ENDIAN,1.0,0.0
True,11,4,R011,Frequency,Output,500,0,UINT16,BIG_ENDIAN,0.1,0.0
```

### Column Definitions

| Column | Required | Description | Example Values |
|--------|----------|-------------|----------------|
| IsEnabled | Yes | Enable this register | True, False |
| Index | Yes | Register address/index (0-based) | 0, 1, 100, 40001 |
| PointType | Yes | Register type | 1=Coil, 2=Discrete, 3=Input, 4=Holding |
| Name | Yes | Register identifier | R000, VOLTAGE, GEN_STATE |
| Description | No | Human-readable description | "Generator voltage in volts" |
| Direction | No | Data flow direction | Input, Output, None |
| Value | No | Default/initial value | 0, 100, 5000 |
| Quality | No | Initial quality flag | 0 (good), 1 (bad) |
| DataType | No | Data type for interpretation | UINT16, INT16, FLOAT32, etc. |
| Endianness | No | Byte order for multi-register | BIG_ENDIAN, LITTLE_ENDIAN |
| Scale | No | Multiply factor | 1.0, 0.1, 0.01 |
| Offset | No | Offset value | 0.0, -273.15 |

### Point Types

| Type | Name | Address Range | Access | Description |
|------|------|---------------|--------|-------------|
| 1 | Coil | 0-9999 | Read/Write | Single bit (on/off) |
| 2 | Discrete Input | 10000-19999 | Read-Only | Single bit input |
| 3 | Input Register | 30000-39999 | Read-Only | 16-bit register |
| 4 | Holding Register | 40000-49999 | Read/Write | 16-bit register |

### Supported Data Types

- **UINT16**: Unsigned 16-bit integer (0-65535)
- **INT16**: Signed 16-bit integer (-32768 to 32767)
- **UINT32**: Unsigned 32-bit integer
- **INT32**: Signed 32-bit integer
- **FLOAT32**: 32-bit floating point (IEEE 754)
- **FLOAT64**: 64-bit floating point (double)
- **BOOL**: Boolean (0/1)
- **HEX16**: 16-bit hexadecimal
- **BINARY16**: 16-bit binary
- **BCD16**: Binary-Coded Decimal (16-bit)

### Endianness Options

For multi-register values (32-bit, 64-bit):

- **BIG_ENDIAN (ABCD)**: Most significant byte first (standard)
- **LITTLE_ENDIAN (CDAB)**: Word swap
- **BIG_ENDIAN_BYTE_SWAP (BADC)**: Byte swap within words
- **LITTLE_ENDIAN_BYTE_SWAP (DCBA)**: Least significant byte first

## Usage Instructions

### Step 1: Prepare Your CSV File

1. Create or edit `Gen_Registers.csv` in the project root directory
2. Define all registers your Modbus server should expose
3. Set appropriate point types, data types, and scaling

Example minimal CSV:
```csv
IsEnabled,Index,PointType,Name,Description,Direction,Value,Quality
True,0,4,STATE,Device State,None,0,0
True,1,4,CONTROL,Control Word,None,0,0
True,10,4,VOLTAGE,Voltage Value,Output,0,0
True,11,4,FREQUENCY,Frequency Value,Output,500,0
```

### Step 2: Test CSV Import

Run the test script to verify your CSV is valid:

```bash
cd /home/majid/Documents/scada_scout
source venv/bin/activate
python test_csv_import.py Gen_Registers.csv
```

This will show:
- Total register count
- Register types breakdown
- Generated register blocks
- Sample register definitions

### Step 3: Add Modbus Server Devices

Run one of the setup scripts from SCADA Scout UI:

**Option A: Generator Servers (G1-G22)**
1. Open SCADA Scout
2. Go to Scripts window
3. Select "Setup Generators (G1-G22)"
4. Click "Run Script"
5. This creates 22 Modbus servers with IPs from 172.16.31.13 to 172.16.35.23

**Option B: Switchgear Servers (GPS1-GPS4)**
1. Select "Setup Switchgear (GPS1-GPS4)"
2. Click "Run Script"
3. This creates 4 Modbus servers for switchgear devices

### Step 4: Start Modbus Servers

1. Open Device Manager window
2. Select a server device (e.g., G1)
3. Click "Connect" (starts the server)
4. Server now listens on configured IP:port
5. External Modbus clients can now connect

### Step 5: Verify Server Operation

Use a Modbus client tool to test:

```bash
# Example with modpoll (Linux)
modpoll -m tcp -a 1 -t 4 -r 0 -c 10 172.16.31.13

# Example with Python
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('172.16.31.13', port=502)
client.connect()
result = client.read_holding_registers(0, 10, unit=1)
print(result.registers)
client.close()
```

## Register Block Optimization

The CSV importer automatically creates optimized register blocks:

- **Contiguous blocks**: Groups consecutive registers
- **Gap detection**: Splits blocks if gap > threshold (default 50)
- **Size limiting**: Limits block size (default 100 registers)
- **Memory efficiency**: Only allocates needed memory

Example:
- Registers: 0-50, 55-60, 100-150
- Generated blocks: [0-50], [55-60], [100-150]
- Not a single large block from 0-150 (saves memory)

## Scaling and Offset

Use scale and offset for engineering unit conversion:

```
Actual Value = (Raw Register Value × Scale) + Offset
```

Examples:

1. **Temperature in 0.1°C steps**
   - Raw: 235 → Actual: 235 × 0.1 + 0 = 23.5°C
   - CSV: DataType=UINT16, Scale=0.1, Offset=0

2. **Frequency in 0.01 Hz steps**
   - Raw: 5000 → Actual: 5000 × 0.01 + 0 = 50.00 Hz
   - CSV: DataType=UINT16, Scale=0.01, Offset=0

3. **Temperature with offset (Celsius to Kelvin)**
   - Raw: 20 → Actual: 20 × 1.0 + 273.15 = 293.15 K
   - CSV: DataType=INT16, Scale=1.0, Offset=273.15

## Programmatic Access

### Read Register from Script

```python
def tick(ctx):
    # Read holding register 10 from G1
    value = ctx.get('G1::holding:10')
    ctx.log('info', f'G1 Register 10: {value}')
```

### Write Register from Script

```python
def main(ctx):
    # Write value 5000 to holding register 22 on G2
    ctx.set('G2::holding:22', 5000)
    ctx.log('info', 'Setpoint updated')
```

### Update Server Registers Programmatically

```python
def tick(ctx):
    # Get device manager
    dm = ctx._dm
    device = dm.get_device('G1')
    
    if device and device.connected:
        # Get the Modbus server instance
        protocol = device.protocol
        if hasattr(protocol, 'server'):
            # Write to server's data store
            protocol.server.write_register('holding', 10, 12345)
            ctx.log('info', 'Updated G1 register 10 to 12345')
```

## Multiple Servers with Different Configurations

To create servers with different register layouts:

1. Create separate CSV files (e.g., `Gen_Registers.csv`, `Switch_Registers.csv`)
2. Modify the setup script to use different CSV per device type
3. Or create device-specific setup scripts

Example modification in `gen_devices_setup.py`:

```python
# Different CSV for different generator types
if gen_id in ['G1', 'G2', 'G3']:
    CSV_PATH = 'Gen_Type1_Registers.csv'
elif gen_id in ['G4', 'G5', 'G6']:
    CSV_PATH = 'Gen_Type2_Registers.csv'
else:
    CSV_PATH = 'Gen_Default_Registers.csv'
```

## Troubleshooting

### Problem: "Failed to load register definitions"

**Solution:**
- Verify CSV file exists: `ls -l Gen_Registers.csv`
- Check CSV format (use test script)
- Ensure CSV is UTF-8 encoded
- Check for extra BOM characters

### Problem: "Register already exists" error

**Solution:**
- Check for duplicate Index values in CSV
- Ensure each register has unique index
- Check IsEnabled column (disabled duplicates are OK)

### Problem: External client cannot connect

**Solution:**
- Verify server is started (Connected in Device Manager)
- Check IP address is correct and reachable
- Check port is not blocked by firewall:
  ```bash
  sudo ufw allow 502/tcp
  ```
- Verify port is not in use:
  ```bash
  netstat -tulpn | grep 502
  ```

### Problem: Server starts but no data

**Solution:**
- Check register blocks were created (test script)
- Verify client is reading correct register addresses
- Check unit ID matches (default is 1)
- Use Modbus diagnostic tools to verify requests

## Advanced Usage

### Custom Register Block Configuration

Edit `gen_devices_setup.py` to customize block generation:

```python
# Larger blocks, more aggressive merging
register_blocks, signal_mappings = import_csv_to_device_config(
    CSV_PATH,
    block_size=500,      # Allow up to 500 registers per block
    gap_threshold=100    # Merge blocks if gap < 100 registers
)

# Smaller blocks, less merging (more memory efficient)
register_blocks, signal_mappings = import_csv_to_device_config(
    CSV_PATH,
    block_size=50,       # Limit to 50 registers per block
    gap_threshold=10     # Only merge if gap < 10 registers
)
```

### Per-Device CSV Files

```python
# In gen_devices_setup.py
for i in DEVICE_RANGE:
    gen_id = f"G{i}"
    csv_path = f"registers/Gen_{gen_id}_Registers.csv"
    
    if os.path.exists(csv_path):
        register_blocks, signal_mappings = import_csv_to_device_config(csv_path)
    else:
        # Fallback to default
        register_blocks, signal_mappings = import_csv_to_device_config(CSV_PATH)
```

### Dynamic Register Updates

Update register values in simulation scripts:

```python
# In gen_simulation_template.py
def tick(ctx):
    dm = ctx._dm
    device = dm.get_device('G1')
    
    if device and device.connected and hasattr(device.protocol, 'server'):
        server = device.protocol.server
        
        # Update voltage register (index 10)
        voltage = calculate_voltage()  # Your simulation
        server.write_register('holding', 10, int(voltage))
        
        # Update frequency register (index 11)
        frequency = calculate_frequency()
        server.write_register('holding', 11, int(frequency * 10))  # 0.1 Hz scale
```

## Summary

✓ Import register definitions from CSV files
✓ Create Modbus TCP Slave Servers with full register layout
✓ Support for coils, discrete inputs, input registers, holding registers
✓ Data type mapping (INT16, UINT16, FLOAT32, etc.)
✓ Scaling and offset for engineering units
✓ Optimized memory allocation with register blocks
✓ Multiple servers with same or different configurations
✓ Easy integration with simulation scripts
✓ External Modbus clients can connect and read/write data

For more examples, see:
- `Gen_Registers.csv` - Original Triangle MicroWorks format
- `Gen_Registers_Extended_Example.csv` - Extended format with data types
- `test_csv_import.py` - Test and validation script
- `scripts/gen_devices_setup.py` - Generator server setup
- `scripts/swg_devices_setup.py` - Switchgear server setup
