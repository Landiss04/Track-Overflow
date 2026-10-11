"""Native QML synchronization regression, isolated from QCoreApplication."""

from pathlib import Path
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.fleet import TrainModelFleet  # noqa: E402
from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    app = QGuiApplication([])
    fleet = TrainModelFleet()
    state = fleet.add("T-1", "Blue")
    harness = TestHarnessState(LocalLink(state))
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("fleet", fleet),
                        ("harness", harness)]:
        engine.rootContext().setContextProperty(name, value)
    # Two separate windows, as in the two processes; one engine here.
    for qml in ("Main.qml", "TestMain.qml"):
        engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui" / qml)))
    assert len(engine.rootObjects()) == 2
    model_window, test_window = engine.rootObjects()
    QTest.qWait(50)

    def items(window=test_window):
        return list(walk(window.contentItem()))

    def click(text, window=test_window, root=None):
        matches = [x for x in walk(root or window.contentItem())
                   if x.property("text") == text and x.isVisible()
                   and hasattr(x, "clicked")]
        assert len(matches) == 1, (text, len(matches))
        item = matches[0]
        QTest.mouseClick(
            window, Qt.LeftButton, Qt.NoModifier,
            item.mapToScene(item.boundingRect().center()).toPoint(),
        )
        QTest.qWait(10)

    def row(name):
        return next(x for x in items() if x.objectName() == "input-" + name)

    def edit(name, text):
        editor = next(x for x in walk(row(name))
                      if x.objectName() == "valueEditor")
        editor.forceActiveFocus()
        QTest.keyClick(test_window, Qt.Key_A, Qt.ControlModifier)
        for char in text:
            QTest.keyClick(test_window, Qt.Key(ord(char.upper())))
        QTest.keyClick(test_window, Qt.Key_Return)

    def send_from_qml():
        # Run control is below the viewport: exercise its QML click handler.
        button = next(x for x in items()
                      if x.property("text") == "Send inputs to train model"
                      and hasattr(x, "clicked"))
        button.clicked.emit()
        QTest.qWait(10)

    # No view switcher: each window shows only its own page.
    assert not [x for x in items(model_window)
                if x.objectName().startswith("input-")]

    # Overview apply updates the test UI's control immediately, paused.
    click("APPLY EMERGENCY BRAKE", model_window)
    click("CONFIRM", model_window)
    assert row("emergency_brake_command").property("value") is True
    assert state.snapshot["emergency_brake"]
    # No release from the overview: the same label, disabled.
    click("APPLY EMERGENCY BRAKE", model_window)
    assert not any(x.property("text") in ("CONFIRM",
                                          "RELEASE EMERGENCY BRAKE")
                   and x.isVisible() for x in items(model_window))
    assert state.snapshot["emergency_brake"]  # normal release unchanged
    click("False", root=row("emergency_brake_command"))
    assert row("emergency_brake_command").property("pending")
    harness.sendInputs()
    assert row("emergency_brake_command").property("value") is False
    assert not row("emergency_brake_command").property("pending")

    # Live updates must neither recreate the editor nor destroy raw text.
    harness.setInput("power_command", 100000)
    harness.sendInputs()
    power_row = row("power_command")
    editor = next(x for x in walk(power_row)
                  if x.objectName() == "valueEditor")
    editor.forceActiveFocus()
    QTest.keyClick(test_window, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClick(test_window, Qt.Key_9)
    QTest.keyClick(test_window, Qt.Key_9)
    state.setFailure("engine_failure", True)
    for _ in range(3):
        harness.advanceTick()
    QTest.qWait(20)
    assert row("power_command") == power_row
    assert editor.property("activeFocus")
    assert editor.property("text") == "99"
    QTest.keyClick(test_window, Qt.Key_Return)
    assert harness.inputValues["power_command"] == 99000
    assert power_row.property("pending")
    editor.setProperty("focus", False)  # commit and blur
    QTest.qWait(10)
    assert not editor.property("activeFocus")
    harness.sendInputs()
    # No power output exists: the control keeps the accepted command.
    assert harness.inputValues["power_command"] == 99000
    state.setFailure("engine_failure", False)
    assert harness.inputValues["power_command"] == 99000
    harness.resetModule()
    QTest.qWait(10)
    assert editor.property("text") == "0"
    assert not power_row.property("pending")
    assert state.snapshot["clock"] == harness.elapsed == "00:00:00"
    # Reset returns to the starting values on the first block of the
    # Blue Line: 50 km/h, flat, commanded at the speed limit.
    for name, unit, value in [
        ("power_command", "kW", 0),
        ("commanded_speed", "mph", round(50 / 3.6 * 2.236936, 6)),
        ("speed_limit", "mph", round(50 / 3.6 * 2.236936, 6)),
        ("elevation", "ft", 0),
        ("temperature_setpoint", "°F", 70),
    ]:
        assert row(name).property("unit") == unit
        assert row(name).property("value") == value

    # A failed submission via QML retains the latch, state and drafts.
    state.applyEmergencyBrake()
    before = dict(state.snapshot)
    click("False", root=row("emergency_brake_command"))
    edit("power_command", "-1")
    send_from_qml()
    assert state.snapshot == before
    assert harness.tick == 0
    error = next(x for x in items() if x.objectName() == "inputError")
    assert error.isVisible()
    assert "nonnegative" in error.property("text")
    assert row("emergency_brake_command").property("pending")
    edit("power_command", "100")
    edit("temperature_setpoint", "77")
    edit("commanded_speed", "22.36936")
    edit("elevation", "328.084")
    send_from_qml()
    assert not error.isVisible()
    assert not state.snapshot["passenger_ebrake_pulled"]
    assert state.command_values()["power_command"] == 100000
    assert state.command_values()["temperature_setpoint"] == 25
    assert abs(state.command_values()["commanded_speed"] - 10) < 1e-12
    assert abs(state.command_values()["elevation"] - 100) < 1e-12
    assert row("power_command").property("value") == 100
    assert row("temperature_setpoint").property("value") == 77
    assert not row("power_command").property("pending")
    # Outputs the main window shows are left out of the output table;
    # converted rows stay.
    assert not [x for x in items()
                if x.objectName() in ("output-commanded_speed",
                                      "output-speed_limit")]
    output = next(x for x in items()
                  if x.objectName() == "output-position_offset")
    assert output.property("unit") == "ft"
    # A count refuses a typed minus sign, so no negative is staged.
    edit("passengers_boarded", "-5")
    assert harness.inputValues["passengers_boarded"] == 5
    del engine
    del app


if __name__ == "__main__":
    main()
