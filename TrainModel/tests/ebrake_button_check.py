"""The overview's emergency-brake button, driven from the real test UI.

The Train Model window runs here, served on a private link name. The
test UI runs as its own process (``drive_test_ui.py``) and is operated
through its own QML controls, as a person would use it.
"""

import json
from pathlib import Path
import sys
import uuid

from PySide6.QtCore import QProcess, QProcessEnvironment, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.link import TestLinkServer  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402
from ui.theme import build_theme  # noqa: E402

APPLY = "APPLY EMERGENCY BRAKE"


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    app = QGuiApplication([])
    name = f"ebrake-check-{uuid.uuid4().hex}"
    state = TrainModelState()
    server = TestLinkServer(state, name)
    assert server.listen()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("theme", build_theme())
    engine.rootContext().setContextProperty("trainModel", state)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/Main.qml")))
    window = engine.rootObjects()[0]

    env = QProcessEnvironment.systemEnvironment()
    env.insert("TRAIN_MODEL_LINK", name)
    driver = QProcess()
    driver.setProcessEnvironment(env)
    driver.start(sys.executable, [str(Path(__file__).with_name(
        "drive_test_ui.py"))])

    def read_reply(timeout_ms=15000):
        # Wait with the event loop running, so this window and its link
        # keep answering the test UI while it works.
        waited = 0
        while not driver.canReadLine():
            assert driver.state() != QProcess.ProcessState.NotRunning, (
                bytes(driver.readAllStandardError().data()).decode()
            )
            assert waited < timeout_ms, "test UI did not answer"
            QTest.qWait(10)
            waited += 10
        return json.loads(bytes(driver.readLine().data()))

    def drive(op, **fields):
        driver.write((json.dumps(dict(fields, op=op)) + "\n").encode())
        answer = read_reply()
        assert answer["ok"], answer
        QTest.qWait(30)  # let this window's bindings settle
        return answer

    def items():
        return list(walk(window.contentItem()))

    def texts():
        return {str(x.property("text") or "").lower()
                for x in items() if x.isVisible()}

    safety = next(x for x in items()
                  if x.objectName() == "passengerEmergencyBrake")

    def button():
        return next(x for x in walk(safety)
                    if hasattr(x, "clicked") and x.property("text") == APPLY)

    def click(item):
        QTest.mouseClick(
            window, Qt.LeftButton, Qt.NoModifier,
            item.mapToScene(item.boundingRect().center()).toPoint(),
        )
        QTest.qWait(20)

    def confirm_visible():
        return any(x.property("text") == "CONFIRM" and x.isVisible()
                   for x in walk(safety))

    def assert_offered():
        assert button().isEnabled() and button().isVisible()
        assert not confirm_visible()

    def assert_blocked():
        assert button().isVisible() and not button().isEnabled()
        # The label never turns into a release control.
        assert "release emergency brake" not in texts()
        click(button())
        assert not confirm_visible(), "a disabled button armed"

    def pull():
        click(button())
        assert confirm_visible()
        click(next(x for x in walk(safety)
                   if x.property("text") == "CONFIRM"))

    try:
        assert read_reply()["ready"]

        # Idle: offered, labelled Apply.
        assert_offered()
        assert "emergency brake released" in texts()

        # 1. The test UI commands the emergency brake (the reported bug).
        drive("toggle", name="emergency_brake_command", value="True")
        drive("send")
        assert state.snapshot["emergency_brake"]
        assert not state.snapshot["passenger_ebrake_pulled"]
        assert_blocked()
        assert "emergency brake applied" in texts()
        assert not state.snapshot["passenger_ebrake_pulled"]

        # 2. The test UI releases it: offered again.
        drive("toggle", name="emergency_brake_command", value="False")
        drive("send")
        assert not state.snapshot["emergency_brake"]
        assert_offered()

        # 3. A passenger pull from this window disables the button and
        #    reaches the test UI at once, without a tick.
        tick = drive("query")["tick"]
        pull()
        assert state.snapshot["passenger_ebrake_pulled"]
        assert_blocked()
        seen = drive("query")
        assert seen["ebrake_control"] is True
        assert seen["ebrake_output"] is True
        assert seen["tick"] == tick

        # 4. The test UI's override clears the latch: offered again.
        drive("toggle", name="emergency_brake_command", value="False")
        assert drive("query")["ebrake_pending"] is True
        drive("send")
        assert not state.snapshot["passenger_ebrake_pulled"]
        assert not state.snapshot["emergency_brake"]
        assert_offered()

        # 5. Armed for confirmation when the test UI applies the brake:
        #    the confirmation is withdrawn and the button disabled.
        click(button())
        assert confirm_visible()
        drive("toggle", name="emergency_brake_command", value="True")
        drive("send")
        assert not confirm_visible()
        assert_blocked()
        drive("toggle", name="emergency_brake_command", value="False")
        drive("send")
        assert_offered()

        # 6. While the clock runs: the brake commanded mid-run disables
        #    the button within a tick; held, it is offered again.
        drive("clock", value="Run")
        QTest.qWait(300)
        assert state.running and "running" in texts()
        drive("toggle", name="emergency_brake_command", value="True")
        drive("send")
        QTest.qWait(200)
        assert_blocked()
        drive("toggle", name="emergency_brake_command", value="False")
        drive("send")
        QTest.qWait(200)
        assert_offered()
        drive("clock", value="Hold")
        QTest.qWait(800)
        assert not state.running and "paused" in texts()

        # 7. Brake failure: a commanded brake cannot engage, so the
        #    button stays offered; a pull latches and disables it.
        drive("failure", name="brake_failure", value="True")
        assert state.isFailed("brake_failure")
        assert drive("query")["brake_failure"] is True
        drive("toggle", name="emergency_brake_command", value="True")
        drive("send")
        assert not state.snapshot["emergency_brake"]
        assert_offered()
        pull()
        assert state.snapshot["passenger_ebrake_pulled"]
        assert_blocked()

        # 8. Reset from the test UI clears it all: offered again.
        drive("reset")
        assert not state.isFailed("brake_failure")
        assert not state.snapshot["passenger_ebrake_pulled"]
        assert not state.snapshot["emergency_brake"]
        assert_offered()
        assert drive("query")["error"] == ""
    finally:
        driver.write(b'{"op": "quit"}\n')
        driver.waitForFinished(10000)
        errors = bytes(driver.readAllStandardError().data()).decode()
        del engine
        del app
    assert driver.exitCode() == 0
    assert errors == "", errors


if __name__ == "__main__":
    main()
