"""Tell whether Qt Quick is drawing on the CPU instead of a GPU.

Software rendering (Mesa's llvmpipe, Windows' WARP or Basic Render Driver, Qt's
own software backend) saturated every core in the 2026-11-04 stress runs, so
the harness warns about it and lowers the redraw rate of the Train Model.

``detect`` can only see what Qt reports. On Direct3D it cannot name the adapter,
so a WARP adapter behind the default Direct3D 11 backend is not caught; ``detect``
says so rather than answering "fine".
"""

from __future__ import annotations

__all__ = ["LOW_FRAME_RATE_ENV", "detect", "software_reason"]

import os
from collections.abc import Mapping

#: Set by the harness for every module it starts when rendering is software.
LOW_FRAME_RATE_ENV = "TRACK_OVERFLOW_LOW_FRAME_RATE"

_SOFTWARE_RENDERERS = (
    "llvmpipe",
    "softpipe",
    "swrast",
    "swiftshader",
    "microsoft basic render",
    "gdi generic",
    "warp",
)
_SOFTWARE_ENV = (
    ("QT_QUICK_BACKEND", ("software", "softwarecontext")),
    ("QSG_RHI_BACKEND", ("software",)),
    ("LIBGL_ALWAYS_SOFTWARE", ("1", "true")),
)


def software_reason(
    env: Mapping[str, str], graphics_api: str, gl_renderer: str | None
) -> str | None:
    """Why this setup renders in software, or None when nothing says so."""
    for name, values in _SOFTWARE_ENV:
        if env.get(name, "").lower() in values:
            return f"{name}={env[name]}"
    if graphics_api.lower() == "software":
        return "Qt Quick's graphics API is Software"
    renderer = (gl_renderer or "").lower()
    for word in _SOFTWARE_RENDERERS:
        if word in renderer:
            return f"the GL renderer is {gl_renderer!r}"
    return None


def detect(env: Mapping[str, str] = os.environ) -> tuple[str | None, str]:
    """Probe Qt after the application exists.

    Returns:
        ``(reason, summary)``: ``reason`` is why rendering is software, or None;
        ``summary`` is one line saying what was seen, for the log.
    """
    from PySide6.QtQuick import QQuickWindow

    api = QQuickWindow.graphicsApi().name
    renderer = _gl_renderer() if api == "OpenGL" else None
    reason = software_reason(env, api, renderer)
    if reason is None and renderer is None and api != "Software":
        seen = (
            "the GL renderer could not be read"
            if api == "OpenGL"
            else f"{api} cannot be checked for a software adapter such as"
            " WARP; run with QSG_INFO=1 to see the adapter"
        )
        return None, f"graphics API {api}: {seen}"
    return reason, f"graphics API {api}, GL renderer {renderer or 'n/a'}"


def _gl_renderer() -> str | None:
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext

    context = QOpenGLContext()
    surface = QOffscreenSurface()
    surface.create()
    if not context.create() or not context.makeCurrent(surface):
        return None
    try:
        value = context.functions().glGetString(0x1F01)  # GL_RENDERER
        return value.decode() if isinstance(value, bytes) else str(value)
    finally:
        context.doneCurrent()
