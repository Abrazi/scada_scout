# Remote IEC 61850 SBO Troubleshooting Guide

## Problem Summary
When connecting to an IEC 61850 simulated server from an **external PC**, device discovery succeeds but **SBO (Select-Before-Operate) fails silently** without error messages.

## Root Causes

### 1. **Request Timeout Too Short for Remote Connections** ⏱️
- **Local connections (127.0.0.1)**: 5000ms timeout is adequate
- **Remote connections**: Network latency (20-100ms) + processing time can exceed timeout
- **SBO sequence takes longer**: SELECT → WAIT → OPERATE (3 steps, each with network round-trip)

**Solution**: Increase timeout for remote connections
```bash
# Set environment variable BEFORE starting SCADA Scout
export IEC61850_REQUEST_TIMEOUT_MS=30000  # 30 seconds for high-latency networks
python src/main.py
```

### 2. **Server Not Binding to All Interfaces** 🔗
- Server may be bound to `127.0.0.1` (localhost only) instead of `0.0.0.0` (all interfaces)
- External clients cannot reach a localhost-only server

**Check Server Configuration**:
```
In SCADA Scout:
1. Right-click IED → "Edit Simulator"
2. Check "Listen IP" field
3. Must be: **0.0.0.0** (not 127.0.0.1)
```

**Verify Server is Listening**:
```bash
# From external PC, test port reachability:
nc -zv <SERVER_IP> 10002
# Or using telnet:
telnet <SERVER_IP> 10002
```

### 3. **Firewall Blocking IEC 61850 Port** 🔥
- Windows Firewall may block inbound connections
- Corporate firewalls may filter port 102 or custom ports

**Windows Firewall Fix**:
```powershell
# Run as Administrator
netsh advfirewall firewall add rule name="IEC61850_Server" dir=in action=allow protocol=tcp localport=10002

# Or open Windows Firewall GUI:
# Settings → Firewall & Network Protection → Allow an app through firewall
```

**Linux Firewall Fix**:
```bash
# UFW
sudo ufw allow 10002/tcp

# Iptables
sudo iptables -A INPUT -p tcp --dport 10002 -j ACCEPT
```

### 4. **Network Quality Issues** 📡
- High packet loss on the network
- MTU mismatch between server and client networks
- Network congestion

**Test Network Quality**:
```bash
# From client PC:
ping -c 10 <SERVER_IP>           # Check latency and loss
tracert <SERVER_IP>              # (Windows) see hops
traceroute <SERVER_IP>           # (Linux/macOS)
```

## Step-by-Step Diagnostic Process

### Step 1: Verify Server is Reachable
```bash
# From the client PC:
ping <SERVER_IP>
# Should see responses with reasonable latency (<100ms typical)
```

### Step 2: Verify Port is Open
```bash
# Windows
netstat -ano | findstr :10002

# Linux/macOS
netstat -an | grep 10002
lsof -i :10002
```

### Step 3: Check Server Configuration
1. Open SCADA Scout on server PC
2. Right-click the simulator IED
3. Click "Edit Simulator"
4. Verify:
   - ✅ Listen IP: **0.0.0.0** (not 127.0.0.1)
   - ✅ Port: **10002** (or your configured port)
   - ✅ SCD file is loaded

### Step 4: Test Discovery from External PC
1. Open SCADA Scout on client PC
2. Click "Add Device" → "IEC 61850 IED"
3. Enter:
   - IP Address: **`<SERVER_PC_IP>`** (e.g., 192.168.1.100)
   - Port: **10002**
4. Click "Connect"
5. Check Event Log:
   - ✅ Connection SUCCESS
   - ✅ Discovery SUCCESS
   - ✅ Found control objects

### Step 5: Increase Timeout and Retry SBO
If discovery works but SBO fails:

**Option A: Environment Variable (Recommended)**
```bash
# Linux/macOS
export IEC61850_REQUEST_TIMEOUT_MS=30000
python src/main.py

# Windows (PowerShell)
$env:IEC61850_REQUEST_TIMEOUT_MS=30000
python src\main.py

# Windows (Command Prompt)
set IEC61850_REQUEST_TIMEOUT_MS=30000
python src\main.py
```

**Option B: Configuration File** (if implemented)
- Edit `settings.json` or device config
- Add: `"sbo_timeout_ms": 30000`
- Add: `"request_timeout_ms": 30000`

## Diagnostic Script

Run the included diagnostic tool to identify issues automatically:

```bash
python diagnose_remote_sbo.py

# This will:
# 1. Check server binding configuration
# 2. Measure network latency
# 3. Test full SBO workflow
# 4. Provide specific recommendations
```

## Expected Behavior

### ✅ Working Setup
1. Server PC starts IED simulator with "Listen IP: 0.0.0.0"
2. Client PC on different network connects
3. Discovery shows all control objects
4. **SBO succeeds**: "← SELECT SUCCESS" shown in Event Log
5. Control value changes on server

### ❌ Broken Setup
1. Server binds to 127.0.0.1 only
2. Client cannot connect (connection timeout)
3. **OR** Client connects but SBO fails with no error
4. "SELECT FAILED" shown in Event Log (if error logging is enabled)

## Common Error Messages and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `Connection timeout` | Server not reachable | Check IP, port, firewall |
| `Connection refused` | Port not open on server | Verify server is running |
| `SELECT FAILED` with no details | Timeout expired | Increase `IEC61850_REQUEST_TIMEOUT_MS` |
| `SELECT FAILED: Error 8` | Already selected | Cancel previous operation first |
| `SELECT FAILED: Error 9` | Must select first | SBO is working; try OPERATE next |
| `SELECT FAILED: Error 11` | Timeout | Increase timeout for high-latency networks |

## Advanced Configuration

### Custom Timeout for Specific Devices

In device configuration (devices.json):
```json
{
  "devices": [
    {
      "name": "RemoteIED",
      "ip_address": "192.168.1.100",
      "port": 10002,
      "device_type": "IEC61850_IED",
      "protocol_params": {
        "request_timeout_ms": 30000,
        "sbo_timeout_ms": 500,
        "ctlnum_timeout_ms": 2000
      }
    }
  ]
}
```

### Enable Debug Logging

```bash
# Set environment variables BEFORE starting:
export IEC61850_DEBUG_SBO_LOGS=true
export SCADAScout_DEBUG_RESET_LAYOUT=1
python src/main.py

# Then check the output for [SBO_DEBUG] and [SBO_REGISTER] messages
```

## Performance Statistics

### Typical Network Latencies (Single Round-Trip)
| Network Type | Latency | Comments |
|--------------|---------|----------|
| Local (same switch) | <1ms | Prefer localhost (127.0.0.1) |
| Local LAN (same subnet) | 1-5ms | Good for 5000ms timeout |
| Remote LAN (different subnet) | 5-20ms | May need 10000ms timeout |
| Remote WAN | 20-100ms | Need 20000-30000ms timeout |
| High-Latency WAN | 100-500ms | Need 60000ms+ timeout |

### SBO Sequence Timing
```
SELECT phase: Network latency + processing (typically 20-100ms)
WAIT phase: Configurable, default 100ms
OPERATE phase: Network latency + processing (typically 20-100ms)
Total: ~200-300ms local, 100-500ms remote (depending on network)
```

## Prevention

To avoid SBO issues in the future:

1. **Always configure server with 0.0.0.0** (all interfaces)
2. **Use appropriate timeouts** based on network distance
3. **Test from an external PC** before deploying
4. **Monitor Event Log** for SBO-related messages
5. **Check firewall rules** after network changes
6. **Document timeout settings** for your network environment

## Support

If issues persist:

1. Collect logs:
   ```bash
   python diagnose_remote_sbo.py > remote_sbo_diagnostic.log 2>&1
   ```

2. Check server logs:
   - Look for "registration" messages in Event Log
   - Verify control objects are found

3. Enable verbose logging:
   ```bash
   export IEC61850_DEBUG_SBO_LOGS=true
   export LIBIEC61850_DEBUG=1
   ```

4. Report with:
   - Network topology (server PC IP, client PC IP, subnets)
   - Firewall configuration
   - Server binding configuration
   - Full Event Log output
   - Diagnostic script output
