"""Test UI for the Track Controller (Software) module.

A separate process from the Track Controller UI. It connects to the
controller's local stimulus link and plays the CTC, the Track Model and
the programmer, so the controller's own UI can be watched reacting.

It shares nothing with the controller process except the wire protocol
in ``track_ctrl.stimulus`` and the design tokens in ``track_ctrl.theme``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
