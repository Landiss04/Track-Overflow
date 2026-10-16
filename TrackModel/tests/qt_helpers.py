"""Qt event-loop helpers for the link and end-to-end tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QDeadlineTimer,
    QEvent,
    QObject,
)


def private_link_name() -> str:
    """Return a pipe name no running Track Model window will be using."""
    return f"track-model-test-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def qt_app() -> QCoreApplication:
    """Return the process's one Qt application, creating it once."""
    app = QCoreApplication.instance() or QCoreApplication([])
    assert isinstance(app, QCoreApplication)
    return app


def wait_for(condition: Callable[[], bool], timeout_ms: int = 3000) -> bool:
    """Spin the event loop until ``condition`` holds or time runs out."""
    deadline = QDeadlineTimer(timeout_ms)
    while not condition() and not deadline.hasExpired():
        QCoreApplication.processEvents()
    return condition()


def dispose(*objects: QObject) -> None:
    """Delete Qt objects now, so none outlives its test."""
    for obj in objects:
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
