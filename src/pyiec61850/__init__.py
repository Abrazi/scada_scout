"""Compatibility shim for pyiec61850 bindings.

This module ensures `from pyiec61850 import iec61850` works by trying
the installed package first and falling back to the bundled bindings
located at `libiec61850/pyiec61850` inside the workspace.

Do not import heavy symbols at module import time; just expose `iec61850`.
"""
from __future__ import annotations

import importlib
import os
import sys
import logging

logger = logging.getLogger(__name__)

def _load_binding():
    # Try to import installed package first
    try:
        pkg = importlib.import_module('pyiec61850')
        # If the installed package is itself a shim, ensure it exposes iec61850
        if hasattr(pkg, 'iec61850'):
            return pkg.iec61850
    except Exception:
        pass

    # Fallback: try bundled bindings under repo/libiec61850/pyiec61850
    # Compute repository root (two levels up from this file: src/pyiec61850)
    this_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(this_dir, '..', '..'))
    bundled = os.path.join(repo_root, 'libiec61850', 'pyiec61850')
    if os.path.isdir(bundled):
        # Ensure the bundled path is first on sys.path so relative imports work
        if bundled not in sys.path:
            sys.path.insert(0, bundled)
        try:
            bundled_pkg = importlib.import_module('iec61850')
            return bundled_pkg
        except Exception as e:
            logger.debug('Failed to import bundled pyiec61850 bindings: %s', e)

    # As a final attempt, try importing module named `iec61850` directly
    try:
        mod = importlib.import_module('iec61850')
        return mod
    except Exception:
        pass

    raise ImportError('pyiec61850 bindings not found. Install libiec61850 Python bindings or ensure libiec61850/pyiec61850 is present.')


# Expose iec61850 symbol used throughout the project
iec61850 = _load_binding()

__all__ = ['iec61850']
