"""Add an IEC61850 IED to DeviceManager and create sample variables — UI-friendly script.

Purpose:
- Demonstrates how a user script can add a device to the DeviceManager (172.16.11.18:102 by default),
  trigger discovery (optional), and create named variables/signals on that device.
- Safe-by-default: DOIT=False prevents any network/control operations until you set it True.
- Uses only public DeviceManager APIs and `ctx` helpers (does NOT modify protocol SBO/OPERATE code).

Usage (from Scripts UI): open the script, edit DEVICE_NAME / OBJECT_PATHS as needed, set DOIT=True
and click "Run Once" to add + discover + populate variables. After discovery the script will try
to locate a control DO and will *not* operate it unless you explicitly call `toggle_control=True`.
"""
from __future__ import annotations

from typing import List, Optional
import time

from src.models.device_models import DeviceConfig, DeviceType, Node, Signal

# --- User-configurable defaults ---
HOST = "172.16.11.18"
PORT = 102
DEVICE_NAME = "IED_172_16_11_18"
# Candidate DOs (logical paths) to add as variables if discovery fails or to validate after discovery
OBJECT_PATHS: List[str] = [
    "LD0/LLN0$XCBR$Pos",
    "LD0/LLN0$CSWI1$Pos",
]
# If True: actually connect/discover and (optionally) perform a toggle. Default is safe (dry-run).
DOIT = False
# If True and DOIT=True the script will attempt a control toggle after discovery (requires confirmation)
toggle_control = False
# How long to wait for discovery to populate the model (seconds)
DISCOVERY_TIMEOUT = 8.0


def _build_sample_node(object_paths: List[str]) -> Node:
    n = Node(name="ImportedVars")
    for p in object_paths:
        # create a Signal per DO; address stored as DO (the runtime will resolve ctlVal/stVal)
        name = p.split("/")[-1]
        s = Signal(name=name, address=p, value=None, access="RW")
        n.signals.append(s)
    return n


def _ensure_device(ctx, name: str, host: str, port: int) -> str:
    """Ensure a device entry exists in DeviceManager; return the device name used."""
    dm = ctx._dm
    # If a device with this name already exists, return it
    if dm.get_device(name):
        ctx.log('info', f"Device '{name}' already exists in DeviceManager")
        return name

    cfg = DeviceConfig(name=name, ip_address=host, port=port, device_type=DeviceType.IEC61850_IED)
    ctx.log('info', f"Adding device {name} @ {host}:{port} to DeviceManager (saved)")
    dm.add_device(cfg, run_offline_discovery=False)
    return name


def _wait_for_discovery(ctx, device_name: str, timeout: float) -> bool:
    dm = ctx._dm
    start = time.time()
    while time.time() - start < timeout:
        dev = dm.get_device(device_name)
        if dev and getattr(dev, 'root_node', None):
            return True
        ctx.sleep(0.2)
    return False


def _find_control_do(ctx, device_name: str) -> Optional[str]:
    """Heuristic: find the first candidate DO that looks like a breaker/control point."""
    dm = ctx._dm
    tags = dm.list_unique_addresses(device_name)
    # prefer explicit .Pos / CSWI / XCBR
    candidates = [t for t in tags if ('.Pos' in t or 'CSWI' in t or 'XCBR' in t or 'Pos' in t)]
    if candidates:
        return candidates[0]
    # fallback: any tag that contains 'Pos' or 'Ctl'
    for t in tags:
        if 'Pos' in t or 'ctl' in t.lower():
            return t
    return None


def main(ctx):
    """Script entrypoint for the Scripts UI (one-shot).

    Behavior summary:
    1. Add device entry to DeviceManager (no network by default)
    2. If DOIT True: connect and run discovery, otherwise create local sample variables
    3. Attach sample Node/signals when discovery is missing or when requested
    4. Optionally toggle the first discovered control DO (requires toggle_control=True + DOIT=True)
    """
    ctx.log('info', f"=== Add IED & Variables helper (target {HOST}:{PORT}) ===")

    dev_name = _ensure_device(ctx, DEVICE_NAME, HOST, PORT)

    if not DOIT:
        ctx.log('warning', 'DOIT is False — no network/discovery will be performed. Script will add sample variables locally.')
        # Create sample node and attach to device so UI shows variables
        node = _build_sample_node(OBJECT_PATHS)
        dm = ctx._dm
        dev = dm.get_device(dev_name)
        # attach at runtime and assign addresses
        dev.root_node = node
        dm._assign_unique_addresses(dev_name, node)
        ctx.log('info', f'Added {len(node.signals)} sample variables to device "{dev_name}"')
        ctx.log('info', f'You can now select the device in the Device Tree and edit signals via the UI')
        return True

    # DOIT == True path: attempt to connect + discover
    ctx.log('info', f'Connecting to device {dev_name} to run discovery...')
    try:
        ctx._dm.connect_device(dev_name)
    except Exception as e:
        ctx.log('error', f'connect_device() failed: {e}')
        return False

    ok = _wait_for_discovery(ctx, dev_name, DISCOVERY_TIMEOUT)
    if not ok:
        ctx.log('warning', f'Discovery did not populate the model within {DISCOVERY_TIMEOUT}s')
        ctx.log('info', 'Attaching sample variables so you can edit them in the UI')
        node = _build_sample_node(OBJECT_PATHS)
        dev = ctx._dm.get_device(dev_name)
        dev.root_node = node
        ctx._dm._assign_unique_addresses(dev_name, node)
        return True

    ctx.log('info', 'Discovery succeeded — searching for control DOs')
    ctrl = _find_control_do(ctx, dev_name)
    if not ctrl:
        ctx.log('warning', 'No obvious control DO found after discovery. You can add variables via the UI or re-run with OBJECT_PATHS updated.')
        return True

    ctx.log('info', f'Candidate control DO found: {ctrl}')

    # If requested, perform a safe toggle using the script runtime's convenience API
    if toggle_control:
        ctx.log('warning', 'toggle_control=True: about to perform a live control operation')
        # Use ScriptContext.send_command to ensure we use the existing IEC61850 SBO/OPERATE flow
        success = ctx.send_command(ctrl, True)
        if success:
            ctx.log('info', f'Control command succeeded for {ctrl}')
        else:
            ctx.log('error', f'Control command failed for {ctrl}')
        return success

    ctx.log('info', 'No control action requested. Device added and model populated — ready in UI.')
    return True
