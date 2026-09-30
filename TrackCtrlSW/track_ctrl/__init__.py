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

__all__ = ["__version__"]

__version__ = "0.1.0"
