"""Track Controller (Software) module for the ECE1140 project.

The package is layered so the safety logic can be tested without Qt:

``layout``      static block/section/controller configuration
``plc``         the boolean-only PLC language: parse, compile, scan
``vital``       the fail-safe supervisor applied to every PLC result
``controller``  one wayside controller: I/O decode, scan, commit history
``system``      every line and controller, plus the simulation tick
``state``       the QObject bridge the QML views bind to
``theme``       design tokens from the UI Style Guide

Only ``state`` and ``theme`` import Qt.
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["__version__"]

# The shared simulation clock lives in the repository-level ``utils``
# package (D017), one directory above this module. Appended rather than
# inserted, so nothing at the repository root can shadow this module's
# own packages.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.append(_REPO_ROOT)

__version__ = "0.1.0"
