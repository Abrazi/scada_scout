# Multiple SubNetwork Support - Quick Guide

## Overview

The IED Project System now supports SCD files with multiple SubNetworks, allowing users to select which SubNetwork's IP addresses should be used for device instantiation.

## Why This Matters

In IEC 61850 systems, IEDs can have multiple network interfaces connected to different SubNetworks (e.g., station bus, process bus, engineering network). Each SubNetwork assigns different IP addresses to the same IED.

## How It Works

### Automatic Detection

When loading an SCD file with multiple SubNetworks, the system:
1. Detects all SubNetworks in the Communication section
2. Counts IEDs per SubNetwork
3. Displays a selection dropdown if multiple exist
4. Shows a notification dialog

### UI Workflow

1. **Load SCD File**: Click "Browse" and select your SCD file, then "Load SCD"

2. **SubNetwork Selection Appears**: If multiple SubNetworks detected, a new row appears:
   ```
   SubNetwork: [Dropdown] [Reload with Selected Subnet]
   ```

3. **Select SubNetwork**: Choose from dropdown (shows: "SubnetName (N IEDs)")

4. **Reload**: Click "Reload with Selected Subnet" to re-parse with selected IPs

5. **Review IPs**: The IED table shows IP addresses with subnet name:
   ```
   IED Name    IP Address         Subnet
   IED1        192.168.1.10       Station_Bus
   IED2        192.168.1.11       Station_Bus
   ```

### Programmatic Usage

```python
from src.core.ied_project_orchestrator import IEDProjectOrchestrator

orchestrator = IEDProjectOrchestrator(device_manager)

# Check available subnets
orchestrator.load_from_scd("config.scd")
subnets = orchestrator.get_available_subnets()

for subnet_name, ied_count in subnets:
    print(f"{subnet_name}: {ied_count} IEDs")

# Load with specific subnet
if len(subnets) > 1:
    orchestrator.load_from_scd(
        "config.scd", 
        subnet_name="Station_Bus"  # Use specific subnet
    )
```

## Example SCD Structure

```xml
<Communication>
  <!-- Station Bus Network -->
  <SubNetwork name="Station_Bus" type="8-MMS">
    <ConnectedAP iedName="IED1" apName="AP1">
      <Address>
        <P type="IP">192.168.1.10</P>
      </Address>
    </ConnectedAP>
  </SubNetwork>
  
  <!-- Process Bus Network -->
  <SubNetwork name="Process_Bus" type="8-MMS">
    <ConnectedAP iedName="IED1" apName="AP1">
      <Address>
        <P type="IP">10.0.0.10</P>
      </Address>
    </ConnectedAP>
  </SubNetwork>
</Communication>
```

In this example:
- IED1 has **two** IP addresses
- `192.168.1.10` on Station_Bus
- `10.0.0.10` on Process_Bus

The user selects which network to use for device instantiation.

## API Changes

### SCDProjectLoader

**New Method**:
```python
def get_subnetworks() -> List[Tuple[str, int]]:
    """
    Returns list of (subnet_name, ied_count) tuples
    """
```

**Updated Method**:
```python
def extract_ieds(subnet_name: Optional[str] = None) -> List[IEDDefinition]:
    """
    Args:
        subnet_name: Optional SubNetwork to filter by
    """
```

### IEDNetworkConfig

**New Field**:
```python
@dataclass
class IEDNetworkConfig:
    subnet_name: str = ""  # SubNetwork name from SCD
```

### IEDProjectOrchestrator

**New Method**:
```python
def get_available_subnets() -> List[Tuple[str, int]]:
    """
    Returns available SubNetworks from loaded SCD
    """
```

**Updated Method**:
```python
def load_from_scd(scd_path: str, project_name: str = None, 
                  subnet_name: str = None) -> bool:
    """
    Args:
        subnet_name: Optional SubNetwork to use for IPs
    """
```

## Behavior

### Single SubNetwork
- No selection UI shown
- Uses IPs from that SubNetwork
- Normal workflow continues

### Multiple SubNetworks
- Selection dropdown appears
- User must choose SubNetwork
- Can change selection and reload
- IPs update based on selection

### No Communication Section
- Warning logged
- IEDs extracted without IPs
- Manual IP assignment required

## Example: DUBGG with Multiple SubNetworks

```bash
python test_dubgg_project.py
```

Output:
```
2. Loading SCD file...
   ✓ Successfully parsed SCD
   ✓ Found 45 IED(s)

   📡 SubNetworks detected: 2
      • Station_Network: 45 IED(s)
      • Process_Network: 45 IED(s)

   ℹ️  Multiple SubNetworks found!
      Each IED may have different IP addresses per SubNetwork.
      Current IPs are from the first SubNetwork found.

3. IED Summary:
   ──────────────────────────────────────────────────────────────
   IED Name                       IP Address           SubNet
   ──────────────────────────────────────────────────────────────
   IED1                          192.168.1.10          Station_Network
   IED2                          192.168.1.11          Station_Network
   ...
```

## Use Cases

### 1. Station Bus vs Process Bus
- Station bus: 192.168.x.x (protection, control)
- Process bus: 10.0.x.x (sampled values, GOOSE)
- Select based on communication type needed

### 2. Redundant Networks
- Network A: 172.16.x.x (primary)
- Network B: 172.17.x.x (backup)
- Choose primary for normal operation

### 3. Engineering Network
- Operational: 192.168.1.x
- Engineering: 192.168.100.x
- Select engineering for configuration/testing

## Notes

- **First SubNetwork Default**: If no subnet specified, uses first found
- **Per-IED Selection**: All IEDs use same SubNetwork (no mixing)
- **Reload Required**: Changing subnet requires reload
- **MSS Persistence**: Selected subnet not saved (re-select on load)

## Troubleshooting

### "NO_IP" in Table
- IED not in selected SubNetwork
- Try different SubNetwork
- Or add IED to that SubNetwork in SCD

### IPs Don't Change After Selection
- Click "Reload with Selected Subnet"
- Don't just change dropdown

### Can't See SubNetwork Selection
- Only shown if 2+ SubNetworks exist
- Check SCD has multiple <SubNetwork> elements

## Future Enhancements

Potential additions:
- Save selected subnet in MSS file
- Per-IED subnet selection (mixed networks)
- Visual network topology view
- Automatic subnet recommendation

---

For complete documentation, see [IED_PROJECT_GUIDE.md](IED_PROJECT_GUIDE.md)
