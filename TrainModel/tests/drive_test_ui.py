"""Operate the real test UI window in its own process, for GUI checks.

Reads one JSON command per line on stdin and answers one JSON line on
stdout. Commands press the test UI's own QML controls; ``query`` reads
back what its rows show. Prints ``{"ready": true}`` once connected to
the Train Model named by ``TRAIN_MODEL_LINK``.
"""

import json
from pathlib import Path
import queue
import sys
import threading

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import SocketLink  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def reply(message):
    print(json.dumps(message), flush=True)


def main():
    app = QGuiApplication([])
    link = SocketLink()
    harness = TestHarnessState(link)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("theme", build_theme())
    engine.rootContext().setContextProperty("harness", harness)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/TestMain.qml")))
    window = engine.rootObjects()[0]

    def items():
        return list(walk(window.contentItem()))

    def press(text, within=None):
        matches = [x for x in walk(within or window.contentItem())
                   if x.property("text") == text and hasattr(x, "clicked")]
        assert len(matches) == 1, (text, len(matches))
        matches[0].clicked.emit()

    def named(prefix, name):
        return next(x for x in items() if x.objectName() == prefix + name)

    def failure_row(name):
        # The failure card's row: the name label beside a True button.
        for item in items():
            if item.property("text") != name:
                continue
            row = item.parentItem()
            if any(x.property("text") == "True" and hasattr(x, "clicked")
                   for x in walk(row)):
                return row
        raise LookupError(name)

    def run(command):
        op = command["op"]
        if op == "toggle":
            press(command["value"], named("input-", command["name"]))
        elif op == "failure":
            press(command["value"], failure_row(command["name"]))
        elif op in ("send", "reset", "clock"):
            press({"send": "Send inputs to train model",
                   "reset": "Reset module"}.get(op, command.get("value")))
        elif op != "query":
            raise ValueError(op)
        control = named("input-", "emergency_brake_command")
        return {
            "connected": harness.connected,
            "tick": harness.tick,
            "error": harness.inputError,
            "ebrake_control": control.property("value"),
            "ebrake_pending": control.property("pending"),
            "ebrake_output": named(
                "output-", "emergency_brake_state").property("value"),
            "brake_failure": named(
                "output-", "brake_failure").property("value"),
        }

    # stdin blocks, so a thread reads it; the GUI thread runs commands.
    commands = queue.Queue()
    threading.Thread(
        target=lambda: [commands.put(line) for line in sys.stdin],
        daemon=True,
    ).start()
    ready = []

    def poll():
        if not ready and harness.connected and link.outputs is not None:
            ready.append(True)
            reply({"ready": True})
        while not commands.empty():
            command = json.loads(commands.get())
            if command["op"] == "quit":
                app.quit()
                return
            try:
                reply(dict(run(command), ok=True))
            except Exception as exc:  # report, keep serving
                reply({"ok": False, "error": repr(exc)})

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(10)
    app.exec()
    del engine


if __name__ == "__main__":
    main()
