"""Hold the Train Model window at 16:10 while the user drags a border.

Windows sends ``WM_SIZING`` for every mouse move of an interactive
resize, with a pointer to the rectangle it is about to apply. Rewriting
that rectangle in place lets the window manager itself keep the aspect
ratio, so the border tracks the pointer with no after-the-fact
correction and no jitter.

Other platforms have no equivalent (Wayland exposes no aspect-ratio
control to clients), so there the lock is not installed and the QML
canvas letterboxes. See ``documents/SCALING_GUIDE.md``.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

from PySide6.QtGui import QWindow

_WM_SIZING = 0x0214
_GWLP_WNDPROC = -4

# WM_SIZING wParam: the border or corner being dragged.
_WMSZ_LEFT = 1
_WMSZ_RIGHT = 2
_WMSZ_TOP = 3
_WMSZ_TOPLEFT = 4
_WMSZ_TOPRIGHT = 5
_WMSZ_BOTTOM = 6
_WMSZ_BOTTOMLEFT = 7
_WMSZ_BOTTOMRIGHT = 8

_LEFT_EDGES = {_WMSZ_LEFT, _WMSZ_TOPLEFT, _WMSZ_BOTTOMLEFT}
_TOP_EDGES = {_WMSZ_TOP, _WMSZ_TOPLEFT, _WMSZ_TOPRIGHT}
_CORNERS = {_WMSZ_TOPLEFT, _WMSZ_TOPRIGHT, _WMSZ_BOTTOMLEFT, _WMSZ_BOTTOMRIGHT}

Rect = tuple[int, int, int, int]


def constrain_drag(
    edge: int,
    rect: Rect,
    frame: tuple[int, int],
    current_client: tuple[int, int],
    min_client_width: int,
    ratio: tuple[int, int],
) -> Rect:
    """Return ``rect`` adjusted so its client area matches ``ratio``.

    ``rect`` is the proposed outer window rectangle (left, top, right,
    bottom) and ``frame`` the width and height the borders and title bar
    add to the client area. The dragged border follows the pointer; the
    opposite border stays put. For a corner, the axis that moved further
    drives the size.
    """
    left, top, right, bottom = rect
    frame_w, frame_h = frame
    ratio_w, ratio_h = ratio
    client_w = right - left - frame_w
    client_h = bottom - top - frame_h

    if edge in (_WMSZ_LEFT, _WMSZ_RIGHT):
        width_drives = True
    elif edge in (_WMSZ_TOP, _WMSZ_BOTTOM):
        width_drives = False
    else:
        width_change = abs(client_w - current_client[0]) / ratio_w
        height_change = abs(client_h - current_client[1]) / ratio_h
        width_drives = width_change >= height_change

    if width_drives:
        new_w = max(min_client_width, client_w)
    else:
        new_w = max(min_client_width, round(client_h * ratio_w / ratio_h))
    new_h = round(new_w * ratio_h / ratio_w)

    if edge in _LEFT_EDGES:
        left = right - new_w - frame_w
    else:
        right = left + new_w + frame_w
    if edge in _TOP_EDGES:
        top = bottom - new_h - frame_h
    else:
        bottom = top + new_h + frame_h
    return left, top, right, bottom


class WindowsAspectLock:
    """Window-procedure subclass that constrains interactive resizes.

    ``WM_SIZING`` is sent straight to the window procedure rather than
    posted to the message queue, so a Qt native event filter never sees
    it. The lock therefore replaces the window procedure and chains to
    Qt's original.
    """

    def __init__(self, window: QWindow, ratio: tuple[int, int]) -> None:
        from ctypes import wintypes

        self._window = window
        self._ratio = ratio
        self._rect_type = wintypes.RECT
        lresult = ctypes.c_ssize_t
        wndproc_type = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
            lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPARAM,
        )
        user32: Any = ctypes.windll.user32  # type: ignore[attr-defined]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = (
            wintypes.HWND, ctypes.c_int, ctypes.c_void_p,
        )
        user32.CallWindowProcW.restype = lresult
        user32.CallWindowProcW.argtypes = (
            ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPARAM,
        )
        self._user32 = user32
        self._hwnd = int(window.winId())
        # The callback object must outlive the subclass or Windows calls
        # into freed memory.
        self._proc = wndproc_type(self._window_proc)
        self._original = user32.SetWindowLongPtrW(
            self._hwnd, _GWLP_WNDPROC,
            ctypes.cast(self._proc, ctypes.c_void_p),
        )

    def _window_proc(
        self, hwnd: int, msg: int, wparam: int, lparam: int
    ) -> int:
        if msg == _WM_SIZING:
            try:
                self._constrain(hwnd, wparam, lparam)
            except Exception:  # noqa: BLE001  never break the window proc
                pass
        return int(self._user32.CallWindowProcW(
            self._original, hwnd, msg, wparam, lparam))

    def _constrain(self, hwnd: int, edge: int, lparam: int) -> None:
        drag = self._rect_type.from_address(lparam)
        window_rect = self._rect_type()
        client_rect = self._rect_type()
        self._user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
        self._user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        client_w = client_rect.right - client_rect.left
        client_h = client_rect.bottom - client_rect.top
        frame = (
            window_rect.right - window_rect.left - client_w,
            window_rect.bottom - window_rect.top - client_h,
        )
        # The RECT is in physical pixels; Qt's minimum width is logical.
        min_w = round(
            self._window.minimumWidth() * self._window.devicePixelRatio()
        )

        drag.left, drag.top, drag.right, drag.bottom = constrain_drag(
            int(edge),
            (drag.left, drag.top, drag.right, drag.bottom),
            frame,
            (client_w, client_h),
            min_w,
            self._ratio,
        )


def install_aspect_lock(
    window: QWindow, ratio: tuple[int, int]
) -> object | None:
    """Lock ``window`` to ``ratio`` during resizes, where supported.

    Also snaps the initial size to the ratio, since Qt shrinks an
    oversized window to fit the screen without preserving its shape.
    Returns the lock, which the caller must keep alive, or ``None`` when
    the platform has no support and the QML letterbox handles other
    shapes.
    """
    if sys.platform != "win32":
        return None
    ratio_w, ratio_h = ratio
    height = window.height()
    width = round(height * ratio_w / ratio_h)
    if width > window.width():
        width = window.width()
        height = round(width * ratio_h / ratio_w)
    window.resize(width, height)
    return WindowsAspectLock(window, ratio)
