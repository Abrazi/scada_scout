"""A conservative, dependency-guarded OPC UA client wrapper.

This wrapper is intentionally small: it provides the methods declared in
`OPCClientInterface` while failing fast with a clear error message if the
`opcua` package is not installed. The implementation is synchronous to match
most of the existing codebase; callers may run it in a thread or adapt to
async if desired.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, Optional

from .base_opc import OPCClientInterface

log = logging.getLogger(__name__)

try:  # optional dependency
    from opcua import Client, ua
except Exception:  # pragma: no cover - optional dependency
    Client = None  # type: ignore
    ua = None  # type: ignore


class UAClient(OPCClientInterface):
    """Small wrapper around `opcua.Client` (python-opcua).

    - Fails at connect time with actionable error if the package is missing.
    - Keeps operations simple: connect/read/write/subscribe/browse.
    - Subscription callback runs in the library thread — callers should
      marshal into the app thread if needed.
    """

    def __init__(self, timeout: float = 4.0) -> None:
        if Client is None:
            raise RuntimeError(
                "python-opcua package not installed. Install with: pip install opcua"
            )
        self._client: Optional[Client] = None
        self._timeout = timeout
        self._subscriptions: Dict[int, Any] = {}

    def connect(self, endpoint: str, **kwargs) -> None:
        self._client = Client(endpoint, timeout=self._timeout)
        # allow user to pass security/cert args via kwargs (handled by caller)
        self._client.connect()
        log.info("Connected to OPC UA server: %s", endpoint)

    def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            self._client.disconnect()
        finally:
            self._client = None

    def read_node(self, node_id: str) -> Any:
        assert self._client is not None, "client not connected"
        node = self._client.get_node(node_id)
        return node.get_value()

    def write_node(self, node_id: str, value: Any) -> None:
        assert self._client is not None, "client not connected"
        node = self._client.get_node(node_id)
        node.set_value(value)

    def browse(self, starting_node: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        assert self._client is not None, "client not connected"
        root = self._client.get_root_node()
        start = root if starting_node is None else self._client.get_node(starting_node)
        # return lightweight children info
        for child in start.get_children():
            yield {"nodeid": child.nodeid.to_string(), "browse_name": child.get_browse_name().Name}

    def subscribe(self, node_id: str, callback: Callable[[Any], None]) -> Any:
        assert self._client is not None, "client not connected"

        class _Handler(object):
            def datachange_notification(self, node, val, data):
                try:
                    callback(val)
                except Exception:
                    log.exception("OPC UA subscription callback error")

        handler = _Handler()
        sub = self._client.create_subscription(500, handler)
        node = self._client.get_node(node_id)
        handle = sub.subscribe_data_change(node)
        self._subscriptions[handle] = sub
        return handle

    def unsubscribe(self, handle: Any) -> None:
        sub = self._subscriptions.pop(handle, None)
        if sub is not None:
            try:
                sub.unsubscribe(handle)
            except Exception:
                log.exception("failed to unsubscribe")
            try:
                sub.delete()
            except Exception:
                log.exception("failed to delete subscription")
