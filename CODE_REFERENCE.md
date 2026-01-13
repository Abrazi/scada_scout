# Critical Code Reference Card

Quick lookup for most important sections of IEC61850/Modbus implementation.

---

## Signal Update Flow (Most Critical)

### Step 1: Protocol Emits Signal
**File:** [src/protocols/iec61850/adapter.py#L718](src/protocols/iec61850/adapter.py#L718)
```python
def read_signal(self, signal: Signal) -> Signal:
    # ... read from device ...
    signal.value = 123.45
    signal.quality = SignalQuality.GOOD
    signal.timestamp = datetime.now()
    
    # CRITICAL: Emit to callback
    self._emit_update(signal)  # ← Triggers entire UI update chain
    return signal
```

### Step 2: Base Protocol Invokes Callback
**File:** [src/protocols/base_protocol.py#L44](src/protocols/base_protocol.py#L44)
```python
def _emit_update(self, signal: Signal):
    """Helper to invoke the data callback safely."""
    if self._callback:
        self._callback(signal)  # ← Calls DeviceManager._on_signal_update
```

### Step 3: DeviceManager Forwards to UI
**File:** [src/core/device_manager.py#L375](src/core/device_manager.py#L375)
```python
def _on_signal_update(self, device_name: str, signal: Signal):
    """Internal callback when a protocol pushes data."""
    self.signal_updated.emit(device_name, signal)  # ← Qt signal to UI
```

### Step 4: UI Updates Tree
**File:** [src/ui/widgets/device_tree.py#L310](src/ui/widgets/device_tree.py#L310)
```python
def _on_signal_updated(self, device_name: str, signal):
    """Update the tree row for a signal when live data arrives."""
    # Find signal in tree by address
    item = _search_item(device_item)
    
    # Update description with value
    desc_item.setText(f"{base_desc}  Value: {val_text}")
    
    # Color by quality
    if quality == SignalQuality.GOOD:
        brush = QBrush(QColor('darkgreen'))  # Green ✓
    elif quality == SignalQuality.NOT_CONNECTED:
        brush = QBrush(QColor('grey'))  # Grey ✗
    else:
        brush = QBrush(QColor('darkorange'))  # Orange ⚠
    
    desc_item.setForeground(brush)
```

---

## Discovery Flow (Most Critical)

### File: [src/protocols/iec61850/adapter.py#L225](src/protocols/iec61850/adapter.py#L225)

```python
def _discover_online(self) -> Node:
    """Main live discovery with defensive error handling."""
    
    # Create root node
    root = Node(name=self.config.name, node_type="Device")
    
    # Get list of Logical Devices (LD)
    ld_names = iec61850.IedConnection_getLogicalDeviceList(self.connection)
    logger.debug(f"_discover_online: Processing {len(ld_names)} LDs")
    
    # PER-LD TRY/EXCEPT: One LD failure doesn't block others
    for ld_name in ld_names:
        try:
            # Get Logical Nodes under this LD
            ln_list = iec61850.IedConnection_getLogicalNodeDirectory(
                self.connection, f"{ld_name}/"
            )
            
            # PER-LN TRY/EXCEPT: One LN failure doesn't block others
            for ln_name in ln_list:
                try:
                    # Get Data Objects under this LN
                    do_list = iec61850.IedConnection_getDataObjectDirectory(
                        self.connection, f"{ld_name}/{ln_name}.DA"
                    )
                    
                    # PER-DO TRY/EXCEPT: One DO failure doesn't block others
                    for do_name in do_list:
                        try:
                            # Recursively get all signals from this DO
                            signals = self._browse_data_object_recursive(...)
                            # Add to tree
                            ...
                        except Exception as e:
                            logger.error(f"Failed to process DO {do_name}: {e}")
                            continue  # Skip this DO, continue with next
                            
                except Exception as e:
                    logger.error(f"Failed to process LN {ln_name}: {e}")
                    continue  # Skip this LN, continue with next
                    
        except Exception as e:
            logger.error(f"Failed to process LD {ld_name}: {e}")
            continue  # Skip this LD, continue with next
    
    return root  # Returns fully populated tree despite any failures
```

**Key Points:**
- 3-level nested try/except (LD → LN → DO)
- `continue` skips failure, doesn't abort
- Each error logged for debugging
- Root node returned even if partial discovery

---

## Connection & Callback Setup

### File: [src/core/device_manager.py#L278](src/core/device_manager.py#L278)

```python
def connect_device(self, device_name: str):
    """Establishes connection and wires callbacks."""
    
    # Create protocol adapter
    protocol = self._create_protocol_adapter(device.config)
    
    # CRITICAL: Wire the data callback
    # This callback is called every time protocol reads a signal
    protocol.set_data_callback(
        lambda sig: self._on_signal_update(device_name, sig)
    )
    
    # Connect via worker thread
    worker = ConnectionWorker(protocol)
    worker.signals.finished.connect(lambda node: self._on_connection_success(...))
    worker.run()  # Blocks until connection complete
    
    # After connection:
    # 1. discover() returns tree
    # 2. read_signal() emits via callback
    # 3. Callback → _on_signal_update() → signal_updated.emit()
    # 4. UI handler updates tree with live values
```

---

## Auto-Polling Control

### File: [src/core/device_manager.py#L388](src/core/device_manager.py#L388)

```python
def poll_devices(self):
    """Polls signals for all devices with polling enabled.
    
    Note: Auto-polling is disabled by default. Only watch-list items or
    explicit refresh calls will trigger reads.
    """
    for name, device in self._devices.items():
        # Skip automatic polling unless explicitly enabled
        if device.connected and getattr(device.config, 'polling_enabled', False):
            # This is only reached if explicitly enabled per device
            # Default: polling_enabled = False, so this never runs
            ...
```

**To Enable Per-Device:**
```python
device.config.polling_enabled = True
device.config.poll_interval = 1.0  # seconds
```

---

## Watch List Polling (Only Active Read Path)

### File: [src/core/watch_list_manager.py#L100](src/core/watch_list_manager.py#L100)

```python
def _poll_all_signals(self):
    """Polls all watched signals periodically.
    
    This is the ONLY place where signals are automatically read.
    Auto-polling in DeviceManager is disabled.
    """
    for signal in self.watched_signals:
        try:
            # Read signal from protocol
            result = self.device_manager.read_signal(
                signal.device_name,
                signal.address
            )
            # Result triggers callback → signal_updated.emit() → UI update
        except Exception as e:
            logger.error(f"Failed to read {signal.address}: {e}")
```

---

## Mock Mode (For Testing Without Real Device)

### File: [src/protocols/iec61850/adapter.py#L705](src/protocols/iec61850/adapter.py#L705)

```python
# Check if libiec61850 available
HAS_LIBIEC61850 = False
try:
    from . import lib61850 as iec61850
    HAS_LIBIEC61850 = True
except ImportError:
    try:
        from pyiec61850 import iec61850
        HAS_LIBIEC61850 = True
    except ImportError:
        HAS_LIBIEC61850 = False  # ← Triggers MOCK mode
        logger.warning("libiec61850 not found, using MOCK mode")

# In read_signal():
if not HAS_LIBIEC61850:
    # MOCK: Generate random values
    import random
    if signal.signal_type == SignalType.ANALOG:
        signal.value = round(random.uniform(220.0, 240.0), 2)
    elif signal.signal_type == SignalType.BINARY:
        signal.value = random.choice([True, False])
    signal.timestamp = datetime.now()
    signal.quality = SignalQuality.GOOD
    
    # CRITICAL: Emit update even in MOCK mode
    self._emit_update(signal)  # ← Triggers UI update
    return signal
```

**For Testing:**
1. Don't install libiec61850
2. App automatically uses MOCK mode
3. Tree populates with mock data
4. Watch list reads generate random values
5. Fully functional for UI testing

---

## Signal Quality Coloring

### File: [src/ui/widgets/device_tree.py#L365](src/ui/widgets/device_tree.py#L365)

```python
# Color signal row by quality
from src.models.device_models import SignalQuality

if quality == SignalQuality.GOOD:
    brush = QBrush(QColor('darkgreen'))        # 🟢 Green
elif quality == SignalQuality.NOT_CONNECTED:
    brush = QBrush(QColor('grey'))             # ⚪ Grey
else:  # INVALID, STALE, UNKNOWN
    brush = QBrush(QColor('darkorange'))       # 🟠 Orange

desc_item.setForeground(brush)
```

**Quality Values:**
- `GOOD`: Signal read successfully, value is valid
- `NOT_CONNECTED`: Connection lost or device unreachable
- `INVALID`: Address malformed or object doesn't exist on device
- `STALE`: Value older than threshold (not currently used)

---

## Error Detection & Logging

### Discovery Errors
Look for in event log:
```
Failed to process LD GPS01: IedConnection_getLogicalDeviceList failed
Failed to process LN ECB01: AttributeError: NoneType has no attribute...
Failed to process DO XCBR: TimeoutError: connection lost
```

### Read Errors
Look for in event log:
```
IEC61850 ← CONNECTION LOST (State: 5)
IEC61850 ← INVALID ADDRESS: address (missing LD/)
IEC61850 ← Raw Error Code: 13 (OBJECT_DOES_NOT_EXIST)
```

### Callback Errors
Look for in event log:
```
DeviceTreeWidget: Failed to update signal in tree: KeyError
_on_signal_update called with invalid device_name
```

---

## Testing Checklist

- [ ] Tree shows all Logical Devices (not just one)
- [ ] Each LD shows all Logical Nodes
- [ ] Each LN shows all Data Objects
- [ ] Each DO shows all Signal leaves
- [ ] Add signal to watch list
- [ ] Signal updates every 1 second in tree
- [ ] Value shows in Description column: `Value: X.XX`
- [ ] Color is green (GOOD), grey (NOT_CONNECTED), or orange (other)
- [ ] No IEC61850 reads in log until watch list accessed
- [ ] Event log shows `_discover_online:` messages with counts

---

## Quick Debug Commands

**Print tree structure:**
```python
def print_node(node, indent=0):
    print("  " * indent + f"- {node.name}")
    for child in node.children:
        print_node(child, indent+1)

print_node(device.root_node)
```

**Check watched signals:**
```python
for sig in watch_list_manager.watched_signals:
    print(f"{sig.device_name}: {sig.address} = {sig.value}")
```

**Force refresh all signals:**
```python
device_manager.refresh_all(device_name)
```

**Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

