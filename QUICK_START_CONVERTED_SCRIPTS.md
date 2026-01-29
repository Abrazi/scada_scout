# Quick Start: Running Triangle MicroWorks Scripts in SCADA Scout

## What I've Done

I've converted your Triangle MicroWorks DTM Insight JavaScript files into SCADA Scout-compatible Python scripts. Here's what's ready to use:

### ✅ Ready to Run

1. **Generator Device Setup** (`scripts/gen_devices_setup.py`)
   - Adds 22 generator devices (G1-G22) to SCADA Scout
   - Automatically configured with IP addresses from your original script
   - Run once to set up all devices

2. **Switchgear Device Setup** (`scripts/swg_devices_setup.py`)
   - Adds 4 switchgear devices (GPS1-GPS4) to SCADA Scout
   - Pre-configured with IP addresses
   - Run once to set up all devices

3. **Generator Simulation Template** (`scripts/gen_simulation_template.py`)
   - Simplified Python version of GenRun_Edited.js
   - Includes basic state machine, voltage/frequency/power ramping
   - Ready to customize and extend
   - Can run continuously to simulate generator behavior

### 📋 Reference Files

4. **Conversion Guide** (`TRIANGLE_MICROWORKS_CONVERSION.md`)
   - Complete documentation of what was converted
   - Explains differences between platforms
   - Step-by-step usage instructions
   - Checklist for completing full conversion if needed

5. **Register Mapping Helper** (`gen_registers_helper.py`)
   - Parses Gen_Registers.csv
   - Shows how to map registers to SCADA Scout format
   - Run: `python gen_registers_helper.py` to see mapping table
   - Run: `python gen_registers_helper.py --constants` to generate Python constants

### 🔄 Updated Configuration

6. **User Scripts** (`user_scripts.json`)
   - Added 3 new script entries ready to use in the UI:
     - "Setup Generators (G1-G22)"
     - "Setup Switchgear (GPS1-GPS4)"
     - "Generator Simulation (Template)"

## How to Use

### Step 1: Add Devices to SCADA Scout

```bash
# Option A: From command line
cd /home/majid/Documents/scada_scout
source venv/bin/activate
python -c "from scripts.gen_devices_setup import main; from src.core.device_manager_core import DeviceManagerCore; ctx = type('obj', (), {'_dm': DeviceManagerCore(), 'log': lambda *args: print(args[1])})(); main(ctx)"
```

Or better yet:

**Option B: From SCADA Scout UI**
1. Open SCADA Scout: `python src/main.py`
2. Open Scripts window
3. Select "Setup Generators (G1-G22)"
4. Click "Run Script" (one-shot execution)
5. Repeat for "Setup Switchgear (GPS1-GPS4)"

### Step 2: Connect to Your Devices

1. Open Device Manager window in SCADA Scout
2. You should see G1-G22 and GPS1-GPS4 listed
3. Select a device (e.g., G1)
4. Click "Connect"
5. If the Modbus server is running on that IP, it will connect

### Step 3: View Register Mappings

```bash
# See how registers map to SCADA Scout format
python gen_registers_helper.py

# Generate Python constants for easy use
python gen_registers_helper.py --constants > scripts/register_constants.py
```

### Step 4: (Optional) Run Simulation

If you want to simulate generator behavior:

1. Edit `scripts/gen_simulation_template.py`:
   - Configure `GENERATOR_IDS` (which generators to simulate)
   - Update register mappings to match your actual setup
   - Adjust ramping rates and timing parameters

2. In SCADA Scout Scripts window:
   - Select "Generator Simulation (Template)"
   - Enable "Continuous" execution
   - Set interval to 0.1 seconds (100ms)
   - Click "Start"

## What Cannot Run Directly

These files are **not executable** as scripts in SCADA Scout:

- ❌ **GenDevices.js** - JavaScript for Triangle MW (converted to Python ✓)
- ❌ **GenRun_Edited.js** - JavaScript simulation (template provided ✓)
- ❌ **swgDevices.js** - JavaScript for Triangle MW (converted to Python ✓)
- ℹ️ **Gen_Registers.csv** - Register definitions (use helper script to parse)
- ℹ️ **sbo.pcapng** - Wireshark packet capture (open with Wireshark)

## File Locations

All new files are in your workspace:
```
/home/majid/Documents/scada_scout/
├── scripts/
│   ├── gen_devices_setup.py          ← Add generator devices
│   ├── swg_devices_setup.py          ← Add switchgear devices
│   └── gen_simulation_template.py    ← Generator simulation
├── gen_registers_helper.py            ← Register mapping tool
├── user_scripts.json                  ← Updated with new scripts
└── TRIANGLE_MICROWORKS_CONVERSION.md  ← Complete guide
```

## Examples

### Read a Modbus Register
```python
# In a SCADA Scout script
def tick(ctx):
    # Read holding register 40001 from G1
    value = ctx.get('G1::1:3:40001')
    ctx.log('info', f'G1 Register 40001: {value}')
```

### Write a Modbus Register
```python
# In a SCADA Scout script
def main(ctx):
    # Write value 1500 to holding register 40010 on G2
    ctx.set('G2::1:3:40010', 1500)
    ctx.log('info', 'Setpoint updated')
```

### Check Device Connection
```python
def main(ctx):
    device = ctx._dm.get_device('G1')
    if device and device.connected:
        ctx.log('info', 'G1 is connected')
    else:
        ctx.log('warning', 'G1 is not connected')
```

## Troubleshooting

**Problem:** Devices don't connect  
**Solution:** 
- Verify IP addresses in the device setup scripts
- Check that Modbus servers are running on those IPs
- Test with `telnet <ip> 502` to verify port is open

**Problem:** Register reads return None  
**Solution:**
- Check device is connected first
- Verify register address format: `DeviceName::unit:function:address`
- Use register helper to find correct addresses: `python gen_registers_helper.py`

**Problem:** Script errors on import  
**Solution:**
- Make sure virtual environment is activated: `source venv/bin/activate`
- Check all dependencies installed: `pip install -r requirements.txt`
- Verify file paths are correct

## Next Steps

1. **Test device connectivity:** Add and connect to one device first (e.g., G1)
2. **Verify register mappings:** Use the helper script to understand register addresses
3. **Customize simulation:** Edit the template to match your exact needs
4. **Monitor in UI:** Use Watch List to monitor specific registers

## Need More Help?

- Read `TRIANGLE_MICROWORKS_CONVERSION.md` for detailed explanations
- Check `examples/` directory for more script examples
- Look at existing scripts in `scripts/` directory
- See SCADA Scout architecture in `.github/copilot-instructions.md`
