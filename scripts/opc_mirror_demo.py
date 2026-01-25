"""Headless demo: DeviceManager -> OPC UA mirror example.

Run locally to see a DeviceManager device mirrored into an OPC UA server.

Usage:
    python scripts/opc_mirror_demo.py

"""
from __future__ import annotations

import time

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType, Node, Signal
from src.core.opc_mirror import OPCMirror


def build_demo_device():
    cfg = DeviceConfig(name="DemoDevice", ip_address="127.0.0.1", port=0, device_type=DeviceType.UNKNOWN)
    node = Node(name="Root")
    node.signals.append(Signal(name="Temperature", address="temp", value=21.5))
    node.signals.append(Signal(name="PumpRunning", address="pump", value=False))
    return cfg, node


if __name__ == '__main__':
    dm = DeviceManagerCore(config_path='devices_demo.json')
    cfg, node = build_demo_device()
    dev = dm.add_device(cfg)
    # attach the manually-built node tree (no protocol required)
    dm._devices[cfg.name].root_node = node
    dm._assign_unique_addresses(cfg.name, node)

    mirror = OPCMirror(dm, poll_interval=0.2)
    mirror.start('opc.tcp://0.0.0.0:4844')
    print('OPC mirror running on opc.tcp://0.0.0.0:4844. Press Ctrl-C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Stopping...')
    finally:
        mirror.stop()
