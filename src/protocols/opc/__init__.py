"""OPC package for SCADA Scout — safe, opt-in OPC UA/DA integration.

This package provides:
- abstract interfaces (no external deps)
- optional wrappers for OPC UA (python-opcua) with graceful fallback
- Windows-only placeholder for OPC DA (COM) with integration notes

Files here are intentionally non-invasive: they add new functionality without
changing existing Modbus/IEC61850 code. Integration with DeviceManager is
explicit and opt-in (see README/docs/opc_integration.md).
"""

from __future__ import annotations

__all__ = [
    "OPCClientInterface",
    "OPCServerInterface",
    "OPCSimulator",
    "UAClient",
    "UAServer",
]

from .base_opc import OPCClientInterface, OPCServerInterface, OPCSimulator

# Optional imports — wrappers provide graceful errors when dependencies are
# missing. Do not import heavy packages at module import time in production.
try:
    from .ua_client import UAClient  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    UAClient = None  # type: ignore

try:
    from .ua_server import UAServer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    UAServer = None  # type: ignore
