# IEC 61850 Multiple Server Guide

## Overview

SCADA Scout now supports running **multiple IEC 61850 servers simultaneously**, each bound to a different IP address. This allows you to simulate multiple IEDs on your network, each accessible by its configured IP address.

## How It Works

### IP Binding Modes

The IEC 61850 server adapter supports two binding modes:

1. **All Interfaces (0.0.0.0)** - Default
   - Server listens on all network interfaces
   - Accessible from any IP configured on your system
   - Best for single server or when IP doesn't matter

2. **Specific IP** - Multi-server capable
   - Server binds only to the configured IP address
   - Allows multiple servers on different IPs
   - Each server accessible by its specific IP on the network

### Configuration

When creating an IEC 61850 server simulator:

```
Listen IP Options:
- 0.0.0.0        → Binds to all interfaces (default)
- 127.0.0.1      → Localhost only (not accessible from network)
- 192.168.1.100  → Binds to specific IP (must be configured on your system)
- 10.0.0.50      → Another specific IP (for a second server)
```

## Running Multiple Servers

### Prerequisites

Each server needs:
1. **Unique IP address** configured on your network interface(s)
2. **Unique port** (can use same port if IPs differ, but different ports recommended)
3. **Valid SCD/ICD file** with the IED model

### Example: Two Servers on Different IPs

**Server 1:**
- Name: IED1_Simulator
- Listen IP: 192.168.1.100
- Port: 102
- SCD File: substation.scd
- IED Name: IED1

**Server 2:**
- Name: IED2_Simulator
- Listen IP: 192.168.1.101
- Port: 102
- SCD File: substation.scd
- IED Name: IED2

Both servers can run simultaneously and will be accessible on the network:
- Client connects to 192.168.1.100:102 → reaches IED1
- Client connects to 192.168.1.101:102 → reaches IED2

### Example: Multiple Servers on Same IP (Different Ports)

If you only have one IP address:

**Server 1:**
- Listen IP: 0.0.0.0
- Port: 10002

**Server 2:**
- Listen IP: 0.0.0.0
- Port: 10102

Both servers accessible on any system IP, but via different ports.

## Setting Up Network IPs (Windows)

If you need to configure additional IP addresses:

### Method 1: GUI (Temporary - Lost on Reboot)
1. Open Network Connections (Control Panel → Network and Internet → Network Connections)
2. Right-click your adapter → Properties
3. Select "Internet Protocol Version 4 (TCP/IPv4)" → Properties
4. Click "Advanced"
5. Under "IP addresses", click "Add"
6. Enter IP address and subnet mask
7. Click OK

### Method 2: Command Line (Temporary)
```cmd
# Add IP alias (requires admin)
netsh interface ip add address "Ethernet" 192.168.1.100 255.255.255.0

# Remove IP alias
netsh interface ip delete address "Ethernet" 192.168.1.100
```

### Method 3: Loopback Adapter (Persistent)
1. Device Manager → Action → Add legacy hardware
2. Install loopback adapter
3. Configure static IPs on loopback adapter
4. IPs persist across reboots

## IP Configuration Dialog

SCADA Scout includes a built-in IP configuration dialog:

1. When creating servers, click **"Check/Configure IPs"**
2. The dialog shows which IPs are not configured
3. Click **"Configure IPs"** to add them automatically (requires admin)
4. IPs are added as temporary aliases (lost on reboot unless made persistent)

## Verification

### Check Server Status
After starting servers, verify in the Event Log:
```
✅ Started IEC 61850 server 'IED1' on 192.168.1.100:102
✅ Started IEC 61850 server 'IED2' on 192.168.1.101:102
```

### Test Connectivity
Use a client to connect to each server:
1. Add Device → IEC 61850 IED
2. IP: 192.168.1.100, Port: 102
3. Connect and verify data model loads

### Network Test
From command line:
```cmd
# Test if port is open
Test-NetConnection -ComputerName 192.168.1.100 -Port 102
```

## Troubleshooting

### "IP address is not configured on this system"
**Solution:** Configure the IP on your network interface first
- Use Windows Network Connections GUI
- Or use the "Check/Configure IPs" button in SCADA Scout
- Or use `netsh` command line tool

### "Port already in use"
**Solution:** 
- Use a different port for each server on the same IP
- Or use different IPs with the same port

### "Server falls back to 0.0.0.0"
**Cause:** Configured IP not found on system
**Solution:** Check Event Log for details, configure the IP first

### Can't connect from another computer
**Causes:**
- Firewall blocking port
- IP not routable on network
- Server bound to wrong IP

**Solutions:**
- Add firewall exception: `netsh advfirewall firewall add rule name="IEC61850" protocol=TCP dir=in localport=102 action=allow`
- Verify IP with `ipconfig`
- Check server Event Log for actual bind address

## Best Practices

1. **Use 0.0.0.0 for single servers** - Simplest configuration
2. **Use specific IPs for multiple servers** - Better isolation and control
3. **Use ports ≥1024** - Avoid needing admin privileges
4. **Document IP assignments** - Keep track of which IED uses which IP
5. **Use persistent IPs** - Configure loopback adapter for IPs that survive reboot

## Advanced: IedServer_addAccessPoint

For developers: The underlying libiec61850 library supports `IedServer_addAccessPoint()` which allows even more advanced scenarios like one server instance listening on multiple IP:port combinations. This is not currently exposed in the UI but available for custom implementations.

## Summary

✅ **Multiple servers supported** via specific IP binding  
✅ **Default behavior unchanged** (0.0.0.0 still works)  
✅ **Network accessible** by configured IP addresses  
✅ **IP configuration helpers** built into UI  
✅ **Works on Windows, Linux, macOS**  

You can now simulate complex substation networks with multiple IEDs, each accessible by its real IP address as configured in your SCD file!
