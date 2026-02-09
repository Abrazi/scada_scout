# Modbus RTU User Interface Guide

## Overview

SCADA Scout now includes full Modbus RTU support with an intuitive user interface for connecting to RTU devices via serial ports (RS-485/USB) or RTU-over-TCP.

## Adding a Modbus RTU Device

### Step 1: Open Connection Dialog

Click the **"Add Device"** button or menu option in the main window.

### Step 2: Select Protocol

In the **Protocol** dropdown, you'll now see three new Modbus RTU options:

- **Modbus RTU Master** - Connect to RTU slave devices as a master/client
- **Modbus RTU Slave** - Act as an RTU slave/server responding to master requests
- **Modbus RTU Simulator** - Simulate an RTU slave device with configurable registers

### Step 3: Configure Connection

When you select a Modbus RTU device type, additional fields will appear:

#### Transport Selection
- **Serial (RS-485/USB)** - Direct serial port connection
- **RTU over TCP** - RTU protocol encapsulated in TCP/IP

#### For Serial Transport:

1. **Serial Port**
   - Click **🔄 Refresh** to scan for available COM ports
   - Select your port from the dropdown (e.g., COM3, /dev/ttyUSB0)
   - Or manually enter the port name

2. **Baud Rate**
   - Common values: 9600, 19200, 38400, 57600, 115200
   - Default: 9600
   - Must match your device's configuration

3. **Data Bits**
   - Options: 7, 8
   - Default: 8
   - Most devices use 8 data bits

4. **Parity**
   - Options: None (N), Even (E), Odd (O)
   - Default: None
   - Must match your device's configuration

5. **Stop Bits**
   - Options: 1, 1.5, 2
   - Default: 1
   - Most devices use 1 stop bit

6. **Slave ID (Unit ID)**
   - Range: 1-255
   - Default: 1
   - The address of the slave device on the RTU network

#### For RTU over TCP:

1. **IP Address** - The IP address of the device or gateway
2. **Port** - TCP port (default: 502)
3. **Slave ID (Unit ID)** - The Modbus slave address (1-255)

### Step 4: Optional Configuration

- **Device Name** - Give your device a memorable name
- **Description** - Add notes about the device
- **Folder** - Organize devices into groups
- **Modbus Config (Optional)** - Load a JSON or CSV file with register definitions
- **Polling** - Enable automatic signal updates with configurable interval

### Step 5: Connect

Click **OK** to save the configuration and connect to the device (Client role).

## Common Serial Port Configurations

### Standard Modbus RTU (Most Common)
- **Baud Rate**: 9600 or 19200
- **Data Bits**: 8
- **Parity**: None (N) or Even (E)
- **Stop Bits**: 1

### High-Speed RTU
- **Baud Rate**: 115200
- **Data Bits**: 8
- **Parity**: None (N)
- **Stop Bits**: 1

### Legacy RTU (Older Equipment)
- **Baud Rate**: 9600
- **Data Bits**: 7
- **Parity**: Even (E)
- **Stop Bits**: 2

## Platform-Specific Serial Port Names

### Windows
- Format: `COM1`, `COM2`, `COM3`, etc.
- USB-to-RS485 adapters typically appear as `COM3` or higher

### Linux
- Format: `/dev/ttyUSB0`, `/dev/ttyUSB1`, `/dev/ttyS0`, etc.
- USB adapters: `/dev/ttyUSB0`, `/dev/ttyUSB1`
- Built-in ports: `/dev/ttyS0`, `/dev/ttyS1`

### macOS
- Format: `/dev/cu.usbserial-XXXXXX` or `/dev/tty.usbserial-XXXXXX`
- Use the `cu.` variant for outgoing connections

## Troubleshooting

### Port Not Found
1. Click the **🔄 Refresh** button to rescan
2. Check physical cable connections
3. Verify USB driver installation
4. On Linux, check permissions: `sudo chmod 666 /dev/ttyUSB0`

### Connection Timeout
1. Verify baud rate matches device configuration
2. Check parity and stop bits settings
3. Ensure correct slave ID/unit ID
4. Check RS-485 termination resistors
5. Verify TX/RX wiring (may need to swap A/B lines)

### No Response from Device
1. Confirm device is powered on
2. Check slave ID matches device configuration
3. Try increasing timeout in polling settings
4. Verify serial parameters (baud, parity, stop bits)
5. Check for address conflicts on multi-drop networks

### Permission Denied (Linux/macOS)
```bash
# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER

# Or change port permissions (temporary)
sudo chmod 666 /dev/ttyUSB0
```

## Example Configurations

### Example 1: USB-to-RS485 Adapter on Windows
```
Device Name: PLC_01
Protocol: Modbus RTU Master
Transport: Serial (RS-485/USB)
Serial Port: COM3
Baud Rate: 9600
Data Bits: 8
Parity: None (N)
Stop Bits: 1
Slave ID: 1
```

### Example 2: RTU over TCP Gateway
```
Device Name: Remote_RTU
Protocol: Modbus RTU Master
Transport: RTU over TCP
IP Address: 192.168.1.100
Port: 502
Slave ID: 1
```

### Example 3: RTU Simulator for Testing
```
Device Name: Test_Simulator
Protocol: Modbus RTU Simulator
Transport: Serial (RS-485/USB)
Serial Port: COM4
Baud Rate: 19200
Data Bits: 8
Parity: Even (E)
Stop Bits: 1
```

## Loading Register Definitions

You can import register definitions from CSV or JSON files:

1. Click **Browse...** next to "Modbus Config (Optional)"
2. Select a `.csv` or `.json` file
3. The application will load register addresses, names, and data types

### CSV Format Example
```csv
start_address,count,function_code,data_type,name_prefix,description
40001,10,3,UINT16,Voltage,Line voltages
40100,5,3,FLOAT32,Temperature,Temperature sensors
```

## Keyboard Shortcuts

- **Ctrl+R** (when port dropdown is focused) - Refresh serial ports
- **Tab** - Navigate between fields
- **Enter** - Accept and connect (when all required fields are filled)

## Next Steps

After connecting:
1. Device Explorer will show discovered signals
2. Add signals to Watch List for monitoring
3. Use Control Panel to write values (for writable registers)
4. Enable polling for automatic updates

## See Also

- **MODBUS_RTU_ARCHITECTURE.md** - Technical implementation details
- **MODBUS_RTU_QUICK_START.md** - Python API and headless usage
- **MODBUS_RTU_IMPLEMENTATION_SUMMARY.md** - Complete feature list
- **example_modbus_rtu.py** - Python script examples
