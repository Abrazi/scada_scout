"""Abstract OPC interfaces (OPC UA + OPC DA) — no external deps.

Keep implementations behind these interfaces so the rest of the system can
depend on a stable API without importing platform-specific libraries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, Optional

class OPCClientInterface(ABC):
    """Minimal, sync-friendly OPC client interface.

    Implementations MUST be non-blocking where possible or provide explicit
    thread/async helpers so callers can choose execution model.
    """

    @abstractmethod
    def connect(self, endpoint: str, **kwargs) -> None:
        """Connect to an OPC server (UA endpoint or DA connection string)."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect cleanly."""

    @abstractmethod
    def read_node(self, node_id: str) -> Any:
        """Read a single node/value identified by NodeId or address."""

    @abstractmethod
    def write_node(self, node_id: str, value: Any) -> None:
        """Write a value to a node."""

    @abstractmethod
    def browse(self, starting_node: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        """Return a tree/list of available nodes (lightweight metadata)."""

    @abstractmethod
    def subscribe(self, node_id: str, callback: Callable[[Any], None]) -> Any:
        """Subscribe to value changes. Return a subscription handle."""

    @abstractmethod
    def unsubscribe(self, handle: Any) -> None:
        """Remove a subscription."""


class OPCServerInterface(ABC):
    """Minimal OPC server interface (used for exposing internal signals).

    Servers MUST support programmatic variable creation so the app can mirror
    DeviceManager signals without depending on UI code.
    """

    @abstractmethod
    def start(self, endpoint: str, **kwargs) -> None:
        """Start listening (blocking or background depending on implementation)."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the server and free resources."""

    @abstractmethod
    def create_variable(self, path: str, value: Any, data_type: Optional[str] = None) -> Any:
        """Create or update an exposed variable. Returns a handle."""

    @abstractmethod
    def remove_variable(self, handle: Any) -> None:
        """Remove an exposed variable."""


class OPCSimulator(ABC):
    """Lightweight simulator used by tests and diagnostics."""

    @abstractmethod
    def start(self) -> None:
        """Start simulation (non-blocking if possible)."""

    @abstractmethod
    def stop(self) -> None:
        """Stop simulation and cleanup."""

    @abstractmethod
    def set_point(self, path: str, value: Any) -> None:
        """Set a simulated point's value."""
