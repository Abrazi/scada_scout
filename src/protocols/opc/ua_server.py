"""Guarded OPC UA server wrapper used for mirroring DeviceManager signals.

The wrapper is conservative: it only imports `opcua` at runtime and provides
methods that mirror `OPCServerInterface` from `base_opc.py`. The server can
run in the foreground or background thread and exposes a simple API for
creating/updating variables programmatically.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from .base_opc import OPCServerInterface

log = logging.getLogger(__name__)

try:
    from opcua import Server
except Exception:  # pragma: no cover - optional dependency
    Server = None  # type: ignore


class UAServer(OPCServerInterface):
    def __init__(self) -> None:
        if Server is None:
            raise RuntimeError("python-opcua not installed. Install with: pip install opcua")
        self._server = Server()
        self._objects = None
        self._variables: Dict[str, Any] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self, endpoint: str = "opc.tcp://0.0.0.0:4840", **kwargs) -> None:
        # configure endpoints and server name
        self._server.set_endpoint(endpoint)
        server_name = kwargs.get("server_name", "SCADAScout OPC UA Server")
        self._server.set_server_name(server_name)

        # security - allow callers to pass certificate paths via kwargs
        if "certificate" in kwargs and "private_key" in kwargs:
            self._server.load_certificate(kwargs["certificate"])
            self._server.load_private_key(kwargs["private_key"])

        self._objects = self._server.get_objects_node()

        # run in background thread so caller isn't blocked by default
        def _run():
            try:
                self._server.start()
                log.info("OPC UA server started on %s", endpoint)
                self._stop_event.wait()
            finally:
                try:
                    self._server.stop()
                except Exception:
                    log.exception("error stopping opcua server")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._stop_event.clear()

    def create_variable(self, path: str, value: Any, data_type: Optional[str] = None, on_write: Optional[callable] = None) -> Any:
        """Create or update a variable given a dotted path: e.g. "Device1.Temperature".

        If `on_write` is provided, attempt to register a server-side write callback
        so external OPC UA clients' write operations are delivered immediately.
        If the underlying `python-opcua` version does not support server-side
        write callbacks, the caller may fall back to polling via the node.handle.

        Returns the node handle which can be used later to set_value.
        """
        assert self._objects is not None, "server not started"
        # simple path -> nested folders
        parts = [p for p in path.replace("/", ".").split(".") if p]
        parent = self._objects
        for part in parts[:-1]:
            parent = parent.get_child(part) if parent.get_child(part, False) else parent.add_object(parent.nodeid, part)
        var_name = parts[-1]
        # create variable or get existing
        try:
            node = parent.get_child(var_name)
            node.set_value(value)
        except Exception:
            node = parent.add_variable(parent.nodeid, var_name, value)
            node.set_writable()
        # Attempt to attach a native write-callback if available
        registered = False
        if on_write is not None:
            try:
                # Newer python-opcua exposes a `set_write_callback` on Variable nodes.
                if hasattr(node, 'set_write_callback'):
                    node.set_write_callback(on_write)
                    registered = True
                # Older versions may expose `set_attribute_callback` or similar; try best-effort
                elif hasattr(self._server, 'set_attribute_callback'):
                    try:
                        # server API: set_attribute_callback(nodeid, attributeId, callback)
                        from opcua import ua
                        self._server.set_attribute_callback(node.nodeid, ua.AttributeIds.Value, on_write)
                        registered = True
                    except Exception:
                        registered = False
            except Exception:
                log.debug("Server-side write-callback registration not available", exc_info=True)

        # store both node and whether it has native callback support so callers can
        # choose between callback and poll-based fallback
        self._variables[path] = {'node': node, 'has_write_cb': registered}
        return node

    def register_write_handler(self, path: str, callback: callable) -> bool:
        """Try to register a write callback for an already-created variable.

        Returns True when a native callback was attached, False otherwise.
        """
        entry = self._variables.get(path)
        if not entry:
            return False
        node = entry['node']
        try:
            if hasattr(node, 'set_write_callback'):
                node.set_write_callback(callback)
                entry['has_write_cb'] = True
                return True
            # best-effort server-level attachment
            if hasattr(self._server, 'set_attribute_callback'):
                from opcua import ua
                try:
                    self._server.set_attribute_callback(node.nodeid, ua.AttributeIds.Value, callback)
                    entry['has_write_cb'] = True
                    return True
                except Exception:
                    pass
        except Exception:
            log.exception("register_write_handler failed")
        return False

    def remove_variable(self, handle: Any) -> None:
        try:
            node = handle
            parent = node.get_parent()
            parent.remove_child(node)
        except Exception:
            log.exception("failed to remove variable")
