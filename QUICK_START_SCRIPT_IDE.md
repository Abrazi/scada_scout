# Quick Start: Script IDE

## Launch the IDE

1. **Start SCADA Scout**:
   ```bash
   source venv/bin/activate  # Linux/macOS
   python src/main.py
   ```

2. **Open Script IDE**:
   - Menu: **View → Script IDE (Debug)...**
   - Or press: **Ctrl+Shift+D**

## Your First Debug Session

### 1. Write a Simple Script

The IDE opens with a template. Replace it with:

```python
def tick(ctx):
    """Simple voltage monitor."""
    # Get voltage (replace with your device/tag)
    voltage = ctx.get('IED1::Voltage', 230)
    
    # Check threshold
    if voltage > 240:
        ctx.log('warning', f'High voltage: {voltage}V')
    else:
        ctx.log('info', f'Voltage OK: {voltage}V')
```

### 2. Set a Breakpoint

- Click in the **line number area** (left margin) on line 6 (`if voltage > 240:`)
- A **red circle** appears indicating the breakpoint

### 3. Start Debugging

- Press **F9** or click **🐞 Debug**
- Script starts running...
- Execution **pauses at your breakpoint**
- Current line highlighted in **yellow**

### 4. Inspect Variables

- Look at **Variables tab** (right panel)
- You should see:
  - `ctx` - Script context object
  - `voltage` - Current voltage value
  
### 5. Step Through Code

- Press **F10** (Step Over) to execute the `if` statement
- Press **F10** again to execute the log statement
- Watch the **Console** (bottom) for output

### 6. Add a Watch Expression

- Click **Watch tab** (right panel)
- Type: `voltage > 240`
- Click **Add**
- See the result update as you step

### 7. Continue or Stop

- Press **F8** (Continue) to run to next breakpoint
- Or press **Shift+F5** (Stop) to end debugging

## Keyboard Shortcuts (Essential)

| Key | Action |
|-----|--------|
| **F9** | Start Debugging |
| **F5** | Run (no debugging) |
| **Shift+F5** | Stop |
| **F10** | Step Over |
| **F11** | Step Into |
| **F8** | Continue |

## Next Steps

1. **Read Full Guide**: See `docs/SCRIPT_IDE_GUIDE.md`
2. **Try Examples**: Load `scripts/example_voltage_monitor_debug.py`
3. **Connect Devices**: Add your IEDs/Modbus devices first
4. **Write Real Scripts**: Automate your SCADA system!

## Troubleshooting

### IDE Won't Open
- Check for import errors in terminal
- Ensure PySide6 is installed: `pip install PySide6`

### Breakpoints Not Working
- Make sure you're in **Debug mode** (F9), not Run mode (F5)
- Breakpoints only work on executable lines (not comments/blank lines)

### No Devices Available
- Add devices first using the main SCADA Scout window
- Check device connection status
- Verify tag addresses are correct

### Script Errors
- Check **Console** (bottom panel) for error messages
- Verify tag format: `DeviceName::SignalAddress`
- Test device connectivity in main window first

## Tips

1. **Start Simple**: Begin with basic read/write operations
2. **Use Breakpoints**: Don't guess - see what's happening
3. **Check Variables**: Inspect values at each step
4. **Watch Expressions**: Monitor conditions as you debug
5. **Save Often**: Use Ctrl+S to save your work

---

**Happy Debugging! 🐞**

For detailed documentation, see: `docs/SCRIPT_IDE_GUIDE.md`
