"""Open or check the shared QML component gallery.

Run from the repository root with the Train Model virtual environment:

    python ui/gallery/gallery.py                 open the gallery
    python ui/gallery/gallery.py --check         offscreen self-test
    python ui/gallery/gallery.py --check --shots DIR

The self-test renders the whole gallery, clicks every control, types into
every text field, confirms and cancels the safety prompt, and exits
non-zero if any QML warning appears or a disabled control fires.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_GALLERY_QML = _HERE / "Gallery.qml"

# The theme tokens live with the Train Model; see ui/README.md.
sys.path.insert(0, str(_REPO / "TrainModel"))

# Offscreen rendering has no font directory. That notice is platform
# noise, not a UI fault.
_NOISE = ("QFontDatabase: Cannot find font directory",)


def _parse_args() -> argparse.Namespace:
    # Command-line options; see the module docstring.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true",
        help="run offscreen, exercise every control, report problems",
    )
    parser.add_argument(
        "--shots", type=Path, default=None,
        help="with --check, save before/after screenshots to this folder",
    )
    return parser.parse_args()


ARGS = _parse_args()
if ARGS.check:
    # Must be set before the Qt application is created.
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import (  # noqa: E402
    Property,
    QCoreApplication,
    QEvent,
    QObject,
    QPointF,
    Qt,
    QUrl,
    Signal,
    qInstallMessageHandler,
)
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
import PySide6.QtQuick  # noqa: E402,F401  Enables the QQuickWindow downcast.
from PySide6.QtTest import QTest  # noqa: E402

from train_model.theme import build_theme  # noqa: E402


class WarningLog(QObject):
    """Collect QML and Qt warnings and expose them to the page."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._warnings: list[str] = []

    def add(self, text: str) -> None:
        """Record one warning unless it is known platform noise."""
        if text.startswith(_NOISE):
            return
        self._warnings.append(text)
        print("WARNING:", text, flush=True)
        self.changed.emit()

    @Property(int, notify=changed)
    def warning_count(self) -> int:
        """Number of warnings recorded so far."""
        return len(self._warnings)

    @Property("QVariantList", notify=changed)
    def warnings(self) -> list[str]:
        """Every warning recorded so far, oldest first."""
        return list(self._warnings)


def _walk(item):
    # Visual children, including Repeater-created controls.
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _is_button(item) -> bool:
    # A control's label Text shares its text, so match on clicked().
    return item.metaObject().indexOfSignal("clicked()") >= 0


def _click(window, item, wait_ms: int = 20) -> None:
    # Click the centre of an item through the real mouse path.
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, centre.toPoint())
    QTest.qWait(wait_ms)


def _find_button(window, text: str):
    # The first visible, enabled button showing exactly this text.
    return next(
        i for i in _walk(window.contentItem())
        if i.property("text") == text and _is_button(i)
        and i.isVisible() and i.isEnabled()
    )


def _find_named(window, name: str):
    # The first item with this objectName.
    return next(
        i for i in _walk(window.contentItem()) if i.objectName() == name
    )


def run_check(window, log: WarningLog, shots: Path | None) -> int:
    """Exercise every control offscreen and report what happened.

    Args:
        window: The gallery's QQuickWindow.
        log: The warning collector bound to the page.
        shots: Folder for screenshots, or None to skip them.

    Returns:
        0 when there are no warnings, no disabled control fired, and
        both long labels elide; 1 otherwise.
    """
    # Grow the window so the whole gallery is on screen at once.
    QTest.qWait(200)
    content = _find_named(window, "galleryContent")
    window.setHeight(int(content.height()) + 120)
    QTest.qWait(300)
    if shots is not None:
        shots.mkdir(parents=True, exist_ok=True)
        window.grabWindow().save(str(shots / "gallery-initial.png"))

    button_label = _find_named(window, "elideButton").property("contentItem")
    select_label = next(
        i for i in _walk(_find_named(window, "elideSelect"))
        if str(i.property("text") or "").startswith("Green Line")
        and i.property("truncated") is not None
    )
    elided = (
        bool(button_label.property("truncated"))
        and bool(select_label.property("truncated"))
    )

    # Click every visible control once. Disabled ones must ignore it.
    clickables = [
        i for i in _walk(window.contentItem())
        if _is_button(i) and i.isVisible()
    ]
    for item in clickables:
        if item.isVisible():  # An earlier click may have hidden it.
            _click(window, item, wait_ms=5)

    # The sweep armed the confirmed safety button: confirm, re-arm, cancel.
    _click(window, _find_button(window, "CONFIRM"))
    _click(window, _find_button(window, "RELEASE EMERGENCY BRAKE"))
    _click(window, _find_button(window, "Cancel"))

    # Keyboard selection commits the next value in every enabled select.
    for combo in _walk(window.contentItem()):
        if combo.objectName() == "selectEditor" and combo.isEnabled():
            combo.forceActiveFocus()
            QTest.keyClick(window, Qt.Key_Down)
            QTest.qWait(20)

    # Type valid and invalid text into every visible text field.
    editors = [
        i for i in _walk(window.contentItem())
        if i.inherits("QQuickTextField") and i.isVisible()
    ]
    for editor in editors:
        editor.forceActiveFocus()
        for text in ("3.5", "abc"):
            editor.setProperty("text", text)
            QTest.keyClick(window, Qt.Key_Return)
    for _ in range(60):
        QTest.keyClick(window, Qt.Key_Tab)
    QTest.qWait(300)
    if shots is not None:
        window.grabWindow().save(str(shots / "gallery-after-clicks.png"))

    fired = window.property("errorCount")
    print("controls clicked:", len(clickables))
    print("text fields typed into:", len(editors))
    print("events logged:", window.property("eventCount"))
    for line in window.property("eventLines").toVariant():
        print("   event:", line)
    print("disabled controls that fired:", fired)
    print("long labels elide:", elided)
    print("warnings:", log.warning_count)
    passed = log.warning_count == 0 and fired == 0 and elided
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def main() -> int:
    """Create the app, load the gallery, and open or check it."""
    log = WarningLog()
    qInstallMessageHandler(lambda kind, context, message: log.add(message))

    app = QGuiApplication(sys.argv)
    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    engine = QQmlEngine()
    engine.warnings.connect(
        lambda errors: [log.add(error.toString()) for error in errors]
    )
    engine.rootContext().setContextProperty("theme", theme)
    engine.rootContext().setContextProperty("warningLog", log)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(_GALLERY_QML)))
    window = component.create()
    if window is None:
        print(component.errorString(), file=sys.stderr)
        return 1

    if ARGS.check:
        exit_code = run_check(window, log, ARGS.shots)
    else:
        exit_code = app.exec()

    # Destroy the page before the objects it binds to, so teardown does
    # not evaluate bindings against deleted context properties.
    qInstallMessageHandler(None)
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
