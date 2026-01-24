# Quick Start: IEC 61850 Control Operations in SCADA Scout

## For Manual Control (GUI)

1. **Connect to IED**
   - File > Connect to IED
   - Enter IP address and IED name
   - Wait for connection

2. **Find Control Point**
   - Expand device in tree view
   - Look for control objects (CSWI, XCBR, etc.)
   - Right-click on control point > "Control"

3. **Use Control Dialog**
   - For SBO controls: Click "1. Select (SBO)" then "2. Operate"
   - For Direct controls: Just click "Operate"
   - Or use "Send Command" for automatic SBO workflow

## For Script Control

### Method 1: Quick Test
```python
def main(ctx):
    # Replace with your actual tag (use Ctrl+Space for completion)
    ctx.send_command('IED1::CTRL/CSWI1.Pos', True)  # Close breaker
    ctx.log('info', 'Command sent')
```

### Method 2: Continuous Monitoring
```python
def tick(ctx):
    # Read a value
    current = ctx.get('IED1::MMXU1.A.phsA.instMag', 0.0)
    
    # Control based on condition
    if current > 100.0:
        ctx.send_command('IED1::CSWI1.Pos', False)  # Open breaker
        ctx.log('warning', 'Breaker opened due to high current')
```

## Common Control Addresses

### Circuit Breaker (XCBR or CSWI)
```
IEDName::LogicalDevice/CSWI1.Pos    # Control switch
IEDName::LogicalDevice/XCBR1.Pos    # Circuit breaker
```

### Read Status
```
...CSWI1.Pos.stVal    # Current position (True/False)
...CSWI1.Pos.q        # Quality
...CSWI1.Pos.t        # Timestamp
```

## Custom Parameters
```python
params = {
    'sbo_timeout': 200,        # Wait 200ms between SELECT/OPERATE
    'originator_id': 'AUTO',   # Custom originator name
}
ctx.send_command(tag, value, params=params)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Not connected" | Check device connection in tree view |
| "Control not available" | Object has ctlModel=0 (status-only) |
| "SELECT failed" | Check IED is responding, increase timeout |
| "Tag not found" | Use Ctrl+Space to see available tags |

## Examples Location
Full examples: `examples/iec61850_sbo_control_examples.py`

## More Help
See `IEC61850_SBO_FIXES.md` for complete documentation.
