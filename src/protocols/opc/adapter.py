"""DeviceManager-compatible OPC UA adapters (opt-in, guarded).

Provides two lightweight BaseProtocol adapters:
- OPCUAClientAdapter: treat a remote OPC UA server as a DeviceManager-backed device
- OPCUAServerAdapter: host an in-process OPC UA server as a device (useful for
  simulation or exposing internal points)

Adapters are intentionally minimal — they translate between the project's
`Node`/`Signal` dataclasses and OPC UA nodes. Heavy lifting (robust discovery,
complex type mapping, DA support) is left to dedicated modules.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Node, Signal, SignalQuality

log = logging.getLogger(__name__)

# Lazy/optional dependency — raise clear error at construction-time if missing
try:
    from src.protocols.opc.ua_client import UAClient
    from src.protocols.opc.ua_server import UAServer
except Exception:  # pragma: no cover - optional dependency
    UAClient = None  # type: ignore
    UAServer = None  # type: ignore


class OPCUAClientAdapter(BaseProtocol):
    """Wraps `UAClient` to present a BaseProtocol-compatible client.

    Expectations/limitations (for now):
    - Signal.address should contain an OPC NodeId (e.g. "ns=2;s=DeviceX.Temp").
    - discover() performs a lightweight browse and creates signals from
      browse-name/nodeid pairs.
    - Subscription callbacks are forwarded to DeviceManager via set_data_callback.
    """

    def __init__(self, config: DeviceConfig, event_logger: Optional[object] = None):
        super().__init__(config)
        if UAClient is None:
            raise RuntimeError("OPC UA support not installed (pip install opcua)")
        self._client = UAClient()
        self._endpoint = config.protocol_params.get('endpoint') or f"opc.tcp://{config.ip_address}:{config.port}"
        self._event_logger = event_logger

    def connect(self) -> bool:
        self._client.connect(self._endpoint)
        return True

    def disconnect(self):
        try:
            self._client.disconnect()
        except Exception:
            log.exception("OPC client disconnect failed")

    def discover(self) -> Node:
        """Lightweight discovery: browse root/objects and expose immediate children as Signals."""
        root = Node(name=self.config.name)
        try:
            for info in self._client.browse():
                addr = info.get('nodeid')
                name = info.get('browse_name') or addr
                sig = Signal(name=str(name), address=str(addr), value=None, quality=SignalQuality.NOT_CONNECTED)
                root.signals.append(sig)
        except Exception:
            log.exception("OPC UA browse failed during discover")
        return root

    def read_signal(self, signal: Signal) -> Signal:
        try:
            val = self._client.read_node(signal.address)
            signal.value = val
            signal.quality = SignalQuality.GOOD
        except Exception as e:
            log.debug("OPC read failed: %s", e)
            signal.quality = SignalQuality.INVALID
            signal.error = str(e)
        return signal

    def write_signal(self, signal: Signal, value: Any) -> bool:
        try:
            self._client.write_node(signal.address, value)
            signal.value = value
            return True
        except Exception:
            log.exception("OPC write failed")
            return False


class OPCUAServerAdapter(BaseProtocol):
    """Expose a Device (or simulator) as an OPC UA server.

    This adapter is minimal — it hosts a UAServer and provides helpers to
    create/update variables from the DeviceManager device tree.
    """

    def __init__(self, config: DeviceConfig, event_logger: Optional[object] = None):
        super().__init__(config)
        if UAServer is None:
            raise RuntimeError("OPC UA support not installed (pip install opcua)")
        self._server = UAServer()
        self._endpoint = config.protocol_params.get('endpoint') or f"opc.tcp://0.0.0.0:{config.port or 4840}"
        self._handles: Dict[str, Any] = {}
        self._event_logger = event_logger

    def connect(self) -> bool:
        # Start listening in background
        self._server.start(self._endpoint, server_name=f"SCADAScout Device: {self.config.name}")
        return True

    def disconnect(self):
        try:
            self._server.stop()
        except Exception:
            log.exception("OPC UA server stop failed")

    def discover(self) -> Node:
        # Server-adapter discover: reflect any configured export points
        root = Node(name=self.config.name)
        pts = self.config.protocol_params.get('export_points', [])
        for p in pts:
            sig = Signal(name=p.get('name', p.get('address')), address=p.get('address'), value=p.get('value'))
            root.signals.append(sig)
        return root

    def read_signal(self, signal: Signal) -> Signal:
        # If we exposed the variable, read its current value from the node
        try:
            handle = self._handles.get(signal.address)
            if handle is not None:
                signal.value = handle.get_value()
                signal.quality = SignalQuality.GOOD
        except Exception:
            log.exception("Failed to read from server-side variable")
            signal.quality = SignalQuality.INVALID
        return signal

    # Additional helper used by external mirror code
    def create_exposed_variable(self, path: str, signal: Signal):
        node = self._server.create_variable(path, signal.value)
        self._handles[signal.unique_address or signal.address] = node
        return node
