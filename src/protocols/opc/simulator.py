"""Small OPC UA simulator used by tests and diagnostics.

Simulator is intentionally lightweight and depends only on the UA server
wrapper. It provides programmatic point updates for use in CI and local QA.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict

from .ua_server import UAServer

log = logging.getLogger(__name__)


class OPCSimulator:
    def __init__(self, endpoint: str = "opc.tcp://0.0.0.0:4840") -> None:
        self._server = UAServer()
        self._endpoint = endpoint
        self._running = False
        self._thread: threading.Thread | None = None
        self._points: Dict[str, Any] = {}
        self._interval = 1.0

    def start(self) -> None:
        self._server.start(self._endpoint, server_name="SCADAScout Simulator")
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._server.stop()

    def set_point(self, path: str, value: Any) -> None:
        self._points[path] = value
        try:
            self._server.create_variable(path, value)
        except Exception:
            log.exception("failed to set simulator point")

    def _run(self) -> None:
        while self._running:
            for p, v in list(self._points.items()):
                try:
                    # re-push the same value so subscriptions get datachange
                    self._server.create_variable(p, v)
                except Exception:
                    log.exception("simulator push failed for %s", p)
            time.sleep(self._interval)
