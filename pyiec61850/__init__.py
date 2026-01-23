"""Compatibility package for environments that expect `pyiec61850`.

This project primarily uses the ctypes wrapper in `src.protocols.iec61850.iec61850_wrapper`.
Some bundled/vendor tests (and a few local smoke tests) import:

    from pyiec61850 import iec61850

To keep those imports working without requiring a separately installed SWIG wheel,
we expose `iec61850` as an alias to the wrapper.

If you have a real `pyiec61850` binding installed, you can remove this shim.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)


def _load_iec61850():
    # Prefer the project's wrapper (works with the rest of the app).
    try:
        from src.protocols.iec61850 import iec61850_wrapper as wrapper

        return wrapper
    except Exception as e:
        logger.debug("Failed to import project iec61850 wrapper: %s", e)

    # Fallback: try importing a separately installed binding.
    return importlib.import_module("iec61850")


iec61850 = _load_iec61850()

__all__ = ["iec61850"]
