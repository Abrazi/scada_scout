# IEC 61850 Simulator IP Selection Guide

## New Features

The IEC 61850 Simulator dialog now includes enhanced IP address management with visual indicators and smart defaults.

## Visual IP Indicators

### Color Coding

IP addresses in the simulator dialog are now color-coded for instant visibility:

- **🟢 GREEN** - IP address is available on your system (ready to use)
- **🔴 RED** - IP address is not configured on your system (needs setup)

### Symbol Prefixes

IP addresses in the dropdown menu show status symbols:

- **✓** - Available on system (green background)
- **⚠** - Not configured (red background)

## IP Address Dropdown

Each IED row now has a **dropdown combo box** instead of a text field:

```
IP Address Dropdown Contents:
┌────────────────────────────────────────┐
│ ✓ 127.0.0.1                            │ ← Local loopback (always available)
│ ✓ 192.168.1.100                        │ ← Your system IP #1
│ ✓ 192.168.1.101                        │ ← Your system IP #2
│ ──────────────────────────────────────  │ ← Separator
│ ⚠ 172.16.11.18 (not configured)        │ ← IP from SCD (needs setup)
└────────────────────────────────────────┘
```

### Dropdown Features

1. **Pre-populated with system IPs** - All IPs configured on your network interfaces
2. **SCD IP shown** - The IP from the SCD file is automatically displayed
3. **Editable** - You can type a custom IP address
4. **Real-time validation** - Background color changes as you type/select

## How It Works

### Loading SCD File

When you load an SCD file:

1. Dialog parses all IEDs and their IP addresses from the Communication section
2. System queries network interfaces for available IPs
3. Each IED row shows:
   - **Name** from SCD
   - **IP Address** dropdown (SCD IP pre-selected, color-coded)
   - **Port** from SCD (or default 102)
   - **Access Point** information
   - **Select** checkbox

### Single IP IED (Most Common)

```
Name: IED1
IP Address: [⚠ 172.16.11.18 (not configured) ▼]  ← RED background
            Options in dropdown:
            - ✓ 127.0.0.1
            - ✓ 192.168.1.100
            - ⚠ 172.16.11.18 (not configured)
Port: 102
Access Point: AP1 (Station Bus)
Select: ☑
```

**If IP is available:**
```
Name: IED1
IP Address: [✓ 192.168.1.100 ▼]  ← GREEN background
Port: 102
```

### Multiple IP IED (Multiple Access Points)

For IEDs with multiple access points in the SCD:

```
IP Address: [⚠ 172.16.11.18 - AP1 (Station Bus) ▼]
            Options:
            - ⚠ 172.16.11.18 - AP1 (Station Bus)
            - ⚠ 172.16.11.19 - AP2 (Process Bus)
            ────────────────────────────────────
            - ✓ 127.0.0.1 (system)
            - ✓ 192.168.1.100 (system)
```

## Usage Workflow

### Scenario 1: All IPs Available (Green)

**What you see:**
- All IP dropdowns have GREEN background
- All IPs show ✓ prefix

**What to do:**
1. Select which IEDs to simulate (checkboxes)
2. Click OK
3. Servers start immediately on their configured IPs

### Scenario 2: Some IPs Not Available (Red)

**What you see:**
- Some IP dropdowns have RED background
- IPs show ⚠ prefix

**Option A - Configure Missing IPs:**
1. Click **"Check/Configure IPs"** button
2. Dialog shows list of missing IPs
3. Click "Configure IPs" (requires admin)
4. IPs are added to loopback adapter
5. Background turns GREEN

**Option B - Use System IPs:**
1. Click dropdown on RED IP
2. Select a ✓ IP from the list (e.g., 127.0.0.1)
3. Background turns GREEN
4. Continue with simulation

**Option C - Use 0.0.0.0 (All Interfaces):**
1. Type "0.0.0.0" in the IP field
2. Server will listen on all interfaces
3. Accessible via any system IP

### Scenario 3: Custom IP Address

**Steps:**
1. Click dropdown
2. Type custom IP address (e.g., 10.0.0.50)
3. Background shows:
   - GREEN if IP exists on system
   - RED if IP needs configuration
4. If RED, configure IP first or use "Check/Configure IPs"

## Color Reference

### Green (IP Available)
```css
Background: Light green (#d4edda)
Text: Dark green (#155724)
Meaning: Ready to use - server will bind successfully
```

### Red (IP Not Available)
```css
Background: Light red (#f8d7da)
Text: Dark red (#721c24)
Meaning: Needs configuration - server will fail or fall back to 0.0.0.0
```

## Best Practices

### ✅ Recommended

1. **Use system IPs when possible** - They're already configured and will work immediately
2. **Configure missing IPs before simulating** - Use "Check/Configure IPs" button
3. **Use 0.0.0.0 for testing** - Works on all interfaces, no configuration needed
4. **Match SCD IPs for production** - Configure exact IPs from SCD for realistic simulation

### ⚠️ Warnings

1. **RED IP = Will Fail or Fall Back** - Server may not start on the exact IP
2. **Multiple servers need unique IPs** - Can't use same IP:port combination
3. **Temporary IPs lost on reboot** - Use loopback adapter for persistence

## Examples

### Example 1: Testing Locally

```
SCD IP: 172.16.11.18 (RED)
Change to: 127.0.0.1 (GREEN)
Result: Server accessible at localhost
```

### Example 2: Network Simulation

```
Your system has: 192.168.1.100, 192.168.1.101, 192.168.1.102

IED1: Use 192.168.1.100 (GREEN)
IED2: Use 192.168.1.101 (GREEN)
IED3: Use 192.168.1.102 (GREEN)

Result: Three servers on network, each with unique IP
```

### Example 3: Exact SCD Match

```
SCD IPs: 172.16.11.18, 172.16.11.19, 172.16.11.20 (all RED)

1. Click "Check/Configure IPs"
2. Configure all three IPs
3. All turn GREEN
4. Simulate with exact SCD configuration
```

## Troubleshooting

### IP stays RED after configuration
- Wait a moment and reload the dialog
- Check network adapter status
- Verify IP with `ipconfig`

### Can't select from dropdown
- The dropdown is editable - you can type directly
- Try clicking the down arrow ▼

### Background doesn't change color
- Type the complete IP address
- Check for typos in IP format
- Verify IP has 4 octets (x.x.x.x)

### All IPs show as RED
- Network interfaces may not be detected
- Restart the application
- Check NetworkUtils is working

## Technical Details

### IP Detection
- Uses `NetworkUtils.get_network_interfaces()`
- Scans all network adapters
- Includes physical and virtual adapters
- Updates on dialog open

### Color Logic
```python
if ip in system_ips:
    color = GREEN  # Available
else:
    color = RED    # Not configured
```

### IP Extraction
Handles multiple formats:
- `"✓ 192.168.1.100"`
- `"⚠ 172.16.11.18 (not configured)"`
- `"✓ 192.168.1.100 - AP1 (Station Bus)"`
- `"192.168.1.100"`

## Summary

✅ **Visual feedback** - Instant red/green status  
✅ **System IPs available** - No typing needed  
✅ **SCD IPs preserved** - Default to SCD configuration  
✅ **Editable** - Type custom IPs  
✅ **Real-time validation** - Updates as you type  
✅ **Multiple access points** - Supports complex SCD files  

The new IP selection makes it immediately obvious which IPs are ready to use (green) and which need configuration (red), streamlining the simulator setup process!
