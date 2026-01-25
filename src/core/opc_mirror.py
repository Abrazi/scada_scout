"""DeviceManager <-> OPC UA mirroring bridge (end-to-end demo implementation).

- Mirrors DeviceManager signals into an OPC UA server under a configurable
  namespace: `SCADAScout/Devices/<device>/<signal>`.
- For demo completeness the bridge polls server variables for external writes
  and forwards them into DeviceManager (safe, simple; replace with event
  callbacks in production).

This module is opt-in and guarded: it requires `python-opcua` at runtime and
will raise a clear error if missing.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict

from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import Signal

log = logging.getLogger(__name__)

try:
    from src.protocols.opc.ua_server import UAServer
except Exception:  # pragma: no cover - optional dependency
    UAServer = None  # type: ignore


class OPCMirror:
    """Mirror DeviceManager signals into an OPC UA server.

    Usage:
        bridge = OPCMirror(device_manager)
        bridge.start('opc.tcp://0.0.0.0:4843')
        bridge.stop()
    """

    def __init__(self, device_manager: DeviceManagerCore, poll_interval: float = 0.25):
        if UAServer is None:
            raise RuntimeError("OPC UA support not installed. Install with: pip install opcua")
        self.dm = device_manager
        self._server = UAServer()
        self._handles: Dict[str, object] = {}
        self._poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, endpoint: str = "opc.tcp://0.0.0.0:4843", server_name: str = "SCADAScout Mirror"):
        self._server.start(endpoint, server_name=server_name)
        # Mirror existing devices
        for dev in self.dm.get_all_devices():
            if dev.root_node:
                self._mirror_device_tree(dev.config.name, dev.root_node)
        # Listen for future updates
        self.dm.on('signal_updated', self._on_signal_updated)
        # Start write-poll thread to detect external writes and forward them
        self._running = True
        self._thread = threading.Thread(target=self._poll_for_writes, daemon=True)
        self._thread.start()
        log.info("OPC mirror started on %s", endpoint)

    def stop(self):
        try:
            self._running = False
            if self._thread:
                self._thread.join(timeout=1.0)
            self.dm.off('signal_updated', self._on_signal_updated)
            self._server.stop()
        except Exception:
            log.exception("Error stopping OPC mirror")

    def _mirror_device_tree(self, device_name: str, node):
        # create variables for each signal under a dotted path
        for sig in getattr(node, 'signals', []) or []:
            path = f"{device_name}.{sig.name}"
            # prefer native server-side write callbacks when available
            try:
                handle = self._server.create_variable(path, sig.value, on_write=lambda node, val=None: self._on_external_write(key, node, val))
            except Exception:
                # older server wrapper may not accept on_write — fall back
                handle = self._server.create_variable(path, sig.value)
            # store mapping from unique_address (if present) to node handle
            key = sig.unique_address or f"{device_name}::{sig.address}"
            # record whether native write-callback is available for this node
            has_cb = False
            try:
                entry = getattr(self._server, '_variables', {}).get(path)
                if isinstance(entry, dict) and entry.get('has_write_cb'):
                    has_cb = True
            except Exception:
                has_cb = False
            self._handles[key] = {'node': handle, 'last': sig.value, 'has_cb': has_cb}
        for child in getattr(node, 'children', []) or []:
            self._mirror_device_tree(device_name, child)

    def _on_signal_updated(self, device_name: str, signal: Signal):
        key = signal.unique_address or f"{device_name}::{signal.address}"
        try:
            if key not in self._handles:
                # create lazily
                path = f"{device_name}.{signal.name}"
                node = self._server.create_variable(path, signal.value)
                self._handles[key] = {'node': node, 'last': signal.value, 'has_cb': False}
                return
            entry = self._handles[key]
            node = entry['node']
            node.set_value(signal.value)
            entry['last'] = signal.value
        except Exception:
            log.exception("Failed to mirror signal to OPC: %s", key)

    def _on_external_write(self, key: str, node, data):
        """Invoked when the OPC UA server receives a write (native callback).

        The signature varies between library versions; we accept (node, value)
        or (node, data) and attempt to extract the written value.
        """
        try:
            # Extract value from possible DataValue wrapper
            val = None
            if data is None:
                try:
                    val = node.get_value()
                except Exception:
                    val = None
            else:
                # data might be a DataValue or a raw value
                try:
                    # DataValue has a .Value.Value in some versions
                    val = getattr(data, 'Value', getattr(data, 'value', data))
                    if hasattr(val, 'Value'):
                        val = getattr(val, 'Value')
                except Exception:
                    val = data

            # forward into DeviceManager
            dm_device, dm_addr = self._parse_key(key)
            if dm_device:
                sig = self.dm.get_signal_by_unique_address(key) or self.dm.get_signal_by_unique_address(f"{dm_device}::{dm_addr}")
                if sig:
                    try:
                        self.dm.write_signal(dm_device, sig, val)
                    except Exception:
                        log.exception("Failed to forward OPC write to DeviceManager (callback route): %s", key)
            # update last-known value so polling won't treat it as external
            if key in self._handles:
                self._handles[key]['last'] = val
        except Exception:
            log.exception("_on_external_write handler failed for %s", key)

    def _poll_for_writes(self):
        while self._running:
            try:
                for key, entry in list(self._handles.items()):
                    # skip nodes that have native server-side callbacks registered
                    if entry.get('has_cb'):
                        continue
                    node = entry['node']
                    try:
                        v = node.get_value()
                    except Exception:
                        continue
                    # if external write detected (value differs from last mirrored)
                    if v != entry.get('last'):
                        # attempt to resolve to a Signal and write into DeviceManager
                        dm_device, dm_addr = self._parse_key(key)
                        if dm_device:
                            sig = self.dm.get_signal_by_unique_address(key) or self.dm.get_signal_by_unique_address(f"{dm_device}::{dm_addr}")
                            if sig:
                                # call write_signal (best-effort)
                                try:
                                    self.dm.write_signal(dm_device, sig, v)
                                except Exception:
                                    log.exception("Failed to forward OPC write to DeviceManager for %s", key)
                        entry['last'] = v
            except Exception:
                log.exception("OPC mirror poll error")
            time.sleep(self._poll_interval)

    def _poll_for_writes(self):
        while self._running:
            try:
                for key, entry in list(self._handles.items()):
                    node = entry['node']
                    try:
                        v = node.get_value()
                    except Exception:
                        continue
                    # if external write detected (value differs from last mirrored)
                    if v != entry.get('last'):
                        # attempt to resolve to a Signal and write into DeviceManager
                        dm_device, dm_addr = self._parse_key(key)
                        if dm_device:
                            sig = self.dm.get_signal_by_unique_address(key) or self.dm.get_signal_by_unique_address(f"{dm_device}::{dm_addr}")
                            if sig:
                                # call write_signal (best-effort)
                                try:
                                    self.dm.write_signal(dm_device, sig, v)
                                except Exception:
                                    log.exception("Failed to forward OPC write to DeviceManager for %s", key)
                        entry['last'] = v
            except Exception:
                log.exception("OPC mirror poll error")
            time.sleep(self._poll_interval)

    @staticmethod
    def _parse_key(key: str):
        # key is either unique_address or 'Device::address'
        if '::' in key:
            device, addr = key.split('::', 1)
            return device, addr
        return None, None
