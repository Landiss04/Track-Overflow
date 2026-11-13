"""Keep the Pi link processes on cores of their own.

Each Pi has a host process that answers its STEP on every 10 ms tick. Behind a
window's redraw on the same core, one late reply slips the clock for every
module. The harness and the modules it starts stay off the last cores, and the
two link processes run on them alone. On a machine with fewer than four cores
nothing is pinned.

Set ``TRACK_OVERFLOW_NO_PIN=1`` to turn this off, for an A/B run.
"""

from __future__ import annotations

__all__ = ["links", "pin_links", "pin_system", "split", "system"]

import os
import sys
from typing import Any

NO_PIN_ENV = "TRACK_OVERFLOW_NO_PIN"


def split(count: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Cores for everything else, and for the Pi links, out of ``count``."""
    dedicated = 2 if count >= 6 else 1 if count >= 4 else 0
    cores = tuple(range(count))
    return cores[: count - dedicated], cores[count - dedicated :]


def system() -> tuple[int, ...]:
    """Cores for the harness and the windows."""
    return split(os.cpu_count() or 1)[0]


def links() -> tuple[int, ...]:
    """Cores for the Pi link processes; empty when nothing is dedicated."""
    return split(os.cpu_count() or 1)[1]


def pin_system() -> bool:
    """Pin this process, and so the modules it starts, off the link cores."""
    return links() != () and _pin(system())


def pin_links() -> bool:
    """Pin this process to the link cores."""
    return _pin(links())


def _pin(cores: tuple[int, ...], kernel32: Any = None) -> bool:
    if not cores or os.environ.get(NO_PIN_ENV):
        return False
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, cores)
        return True
    if sys.platform == "win32":
        return _pin_windows(cores, kernel32)
    return False


def _pin_windows(cores: tuple[int, ...], kernel32: Any = None) -> bool:
    if kernel32 is None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetProcessAffinityMask.argtypes = (
            wintypes.HANDLE,
            ctypes.c_size_t,
        )
    mask = sum(1 << core for core in cores)
    return bool(
        kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), mask)
    )
