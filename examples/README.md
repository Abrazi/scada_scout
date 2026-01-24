# SCADA Scout Examples

This directory contains example scripts and configurations for SCADA Scout.

## Files

### iec61850_sbo_control_examples.py
Comprehensive examples showing how to use IEC 61850 control operations from Python scripts, including:
- Simple circuit breaker control with automatic SBO workflow
- Custom SBO timeout configuration
- Sequential control of multiple devices
- External and simulated IED control
- Continuous monitoring scripts
- Error handling and retry logic

## How to Use

1. **Open SCADA Scout**
2. **Go to Tools > Python Scripts**
3. **Copy an example from `iec61850_sbo_control_examples.py`**
4. **Modify the device names and addresses** to match your system
   - Press `Ctrl+Space` in the editor to see available tags
   - Use tag completion to find the correct addresses
5. **Test with "Run Once"** or run continuously with "Start Continuous"
6. **Monitor the Event Log** to see detailed SBO workflow messages

## Quick Reference

### Available Script Methods

```python
# Read value (cached)
value = ctx.get('Device::Address', default=None)

# Force read (network request)
value = ctx.read('Device::Address')

# Write value (standard write)
success = ctx.set('Device::Address', value)

# IEC 61850 control with automatic SBO handling
success = ctx.send_command('IED::Control/Point', value, params=None)

# List all available tags
tags = ctx.list_tags(device_name=None)

# Logging
ctx.log('info', 'message')
ctx.log('warning', 'message')
ctx.log('error', 'message')

# Sleep
ctx.sleep(seconds)
```

### Tag Address Format
```
DeviceName::SignalAddress
```

Examples:
- `IED1::simpleIOGenericIO/CSWI1.Pos` - Control point
- `IED1::simpleIOGenericIO/CSWI1.Pos.stVal` - Status value
- `ModbusDevice::holding:40001` - Modbus register

## More Information

- See `../IEC61850_SBO_FIXES.md` for complete technical documentation
- See `../QUICK_START_CONTROL.md` for quick start guide
- Check the SCADA Scout documentation for protocol-specific details

## Support

For issues or questions:
1. Check the Event Log for detailed error messages
2. Verify device connections in the device tree
3. Use Ctrl+Space in script editor to verify tag addresses
4. Review the troubleshooting section in `IEC61850_SBO_FIXES.md`
