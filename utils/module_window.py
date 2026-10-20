"""Module windows that hide instead of closing.

Only the harness ends a module process (D005). Closing a module's
window therefore hides it, and the process does not quit when its last
window goes: it quits when the harness sends ``QUIT``.

Call ``keep_windows_open`` once, right after creating the
``QGuiApplication``.
"""

from __future__ import annotations

__all__ = ["keep_windows_open"]

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QGuiApplication, QWindow


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
