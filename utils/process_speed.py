"""Keep a process out of Windows power throttling (EcoQoS).

Windows 11 throttles a process it judges to be in the background: one
whose windows are hidden or behind another, or that has none, as the
Pi agents do. On a hybrid Intel laptop that moves it to an efficiency
core at a low clock, and at 10x one slow module makes every tick late.
Linux has no such policy.

Call ``keep_full_speed`` once, at the start of every process the
harness runs.
"""

from __future__ import annotations

__all__ = ["keep_full_speed"]

import sys

# processthreadsapi.h
_PROCESS_POWER_THROTTLING = 4  # PROCESS_INFORMATION_CLASS
_VERSION = 1
_EXECUTION_SPEED = 0x1
_IGNORE_TIMER_RESOLUTION = 0x4


def keep_full_speed() -> bool:
    """Opt this process out of power throttling, on Windows only.

    Returns:
        Whether Windows accepted the request; False on other systems.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    class _State(ctypes.Structure):
        _fields_ = [
            ("Version", wintypes.ULONG),
            ("ControlMask", wintypes.ULONG),
            ("StateMask", wintypes.ULONG),
        ]

    # Control both behaviours, with neither bit set in the state: off.
    state = _State(_VERSION, _EXECUTION_SPEED | _IGNORE_TIMER_RESOLUTION, 0)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetProcessInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel32.SetProcessInformation.restype = wintypes.BOOL
    return bool(kernel32.SetProcessInformation(
        kernel32.GetCurrentProcess(),
        _PROCESS_POWER_THROTTLING,
        ctypes.byref(state),
        ctypes.sizeof(state),
    ))
