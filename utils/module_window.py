"""Module windows that hide instead of closing.

Only the harness ends a module process (D005). Closing a module's
window therefore hides it, and the process does not quit when its last
window goes: it quits when the harness sends ``QUIT``.

Call ``keep_windows_open`` once, right after creating the
``QGuiApplication``.
``ModuleLink.showRequested`` restores the main windows through
``show_module_windows``, leaving transient dialogs hidden, and can show
them maximized.
``ModuleLink.snapshotRequested`` saves a tile-sized image of the main
window through ``save_module_snapshot``, shown or hidden.
"""

from __future__ import annotations

__all__ = [
    "SNAPSHOT_WIDTH_PX",
    "keep_windows_open",
    "save_module_snapshot",
    "save_window_snapshot",
    "show_module_windows",
]

import os
from collections.abc import Iterator

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQuick import QQuickWindow

#: Width of a saved snapshot; the harness's tiled view shows several
#: to a screen.
SNAPSHOT_WIDTH_PX = 720


class _HideOnClose(QObject):
    """Turn a window's close into a hide."""

    def eventFilter(  # noqa: N802 - Qt API
        self, watched: QObject, event: QEvent
    ) -> bool:
        """Hide a window that is asked to close, and keep it."""
        if (
            event.type() == QEvent.Type.Close
            and isinstance(watched, QWindow)
        ):
            event.ignore()
            watched.hide()
            return True
        return False


def keep_windows_open(app: QGuiApplication) -> None:
    """Hide windows on close, and keep running with none shown.

    Args:
        app: The module process's application.
    """
    app.setQuitOnLastWindowClosed(False)
    app.installEventFilter(_HideOnClose(app))


def show_module_windows(maximized: bool = False) -> None:
    """Reopen this module's main windows without reopening dialogs.

    ModuleLink connects its showRequested signal to this shared policy.
    Each module owns one process, so no other module's windows appear.

    Args:
        maximized: Show them maximized and on top.
    """
    app = QGuiApplication.instance()
    wayland = app is not None and app.platformName() == "wayland"
    for window in _main_windows():
        if (not maximized
                and window.windowState() == Qt.WindowState.WindowMinimized):
            window.showNormal()
        else:
            if wayland and window.isVisible():
                # The compositor ignores raise and activate from a
                # process without focus, but focuses a freshly shown
                # window, so show it afresh.
                window.hide()
            if maximized:
                window.showMaximized()
                window.raise_()
            else:
                window.show()
        window.requestActivate()


def save_module_snapshot(path: str) -> None:
    """Save an image of this module's main window to ``path``.

    The window is drawn even while hidden. The file is replaced whole,
    so a reader never sees half of one.

    Args:
        path: The image file; its suffix names the format.
    """
    for window in _main_windows():
        if isinstance(window, QQuickWindow):
            save_window_snapshot(window, path)
            return


def save_window_snapshot(window: QQuickWindow, path: str) -> None:
    """Save a tile-sized image of ``window`` to ``path``, replaced whole.

    Args:
        window: The window, shown or hidden.
        path: The image file; its suffix names the format.
    """
    image = window.grabWindow().scaledToWidth(
        SNAPSHOT_WIDTH_PX, Qt.TransformationMode.SmoothTransformation
    )
    root, suffix = os.path.splitext(path)
    partial = f"{root}.partial{suffix}"
    if image.save(partial):
        try:
            os.replace(partial, path)
        except OSError:
            # Windows refuses while the harness is reading the old
            # image; skip this frame, the next request replaces it.
            pass


def _main_windows() -> Iterator[QWindow]:
    # Top-level windows that are not dialogs; none in a core process.
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return
    for window in app.topLevelWindows():
        if (
            window.type() == Qt.WindowType.Window
            and window.transientParent() is None
        ):
            yield window
