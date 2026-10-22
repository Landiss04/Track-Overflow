"""Check both actual Windows launchers against the current work area.

Run with the project's Windows interpreter from any directory. Repeat
at the display sizes and Windows DPI settings used for the presentation.
Use --shots DIR to retain a screenshot of each startup window.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import runpy
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]


def check_window(entry: str, shots: Path | None) -> int:
    """Observe the real bootstrap without replacing its sizing logic."""
    sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow

    from train_model import app as bootstrap

    original = bootstrap.run_window
    failures: list[str] = []

    def observed(name, qml_file, build_context):
        def inspect():
            try:
                assert QGuiApplication.platformName() == "windows"
                window = next(
                    item for item in QGuiApplication.topLevelWindows()
                    if isinstance(item, QQuickWindow)
                    and item.title() == name
                )
                frame = window.frameGeometry()
                available = window.screen().availableGeometry()
                assert available.contains(frame), (frame, available)
                error = window.width() * 10 - window.height() * 16
                assert abs(error) <= 16
                app = QGuiApplication.instance()
                assert not app.windowIcon().isNull()
                if entry == "test_ui":
                    def walk(item):
                        yield item
                        for child in item.childItems():
                            yield from walk(child)

                    # Disconnected is a link state, not a brake reading.
                    assert not any(
                        item.isVisible()
                        and item.property("label") == "E-brake"
                        for item in walk(window.contentItem())
                    )
                if shots is not None:
                    shots.mkdir(parents=True, exist_ok=True)
                    assert window.grabWindow().save(
                        str(shots / f"{entry}-startup.png")
                    )
                print(
                    f"PASS: {entry}: {window.width()}x{window.height()}, "
                    f"DPI scale {window.devicePixelRatio():g}, "
                    "frame fits the available desktop; icon installed",
                    flush=True,
                )
            except Exception as exc:
                failures.append(repr(exc))
            finally:
                QGuiApplication.instance().quit()

        def context():
            objects = build_context()
            QTimer.singleShot(300, inspect)
            return objects

        return original(name, qml_file, context)

    bootstrap.run_window = observed
    sys.argv = [str(ROOT / "TrainModel" / f"{entry}.py")]
    try:
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as exc:
        if exc.code:
            failures.append(f"launcher exited with {exc.code}")
    for failure in failures:
        print(f"FAIL: {entry}: {failure}", file=sys.stderr)
    return bool(failures)


def main() -> int:
    """Isolate each launcher in its own native Windows process."""
    if sys.platform != "win32":
        sys.exit("Run this check in the Windows 11 desktop session.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", choices=["main", "test_ui"])
    parser.add_argument("--shots", type=Path)
    args = parser.parse_args()
    if args.window:
        return check_window(args.window, args.shots)
    code = 0
    for entry in ("main", "test_ui"):
        command = [sys.executable, __file__, "--window", entry]
        if args.shots is not None:
            command.extend(["--shots", str(args.shots.resolve())])
        result = subprocess.run(
            command, check=False, timeout=30,
            env={**os.environ,
                 "TRAIN_MODEL_LINK": f"startup-{uuid.uuid4().hex}"},
        )
        code = code or result.returncode
    return code


if __name__ == "__main__":
    raise SystemExit(main())
