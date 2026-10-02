"""Tests for the test harness on the shared simulation clock.

The harness takes dt from ``utils/system_clock.py`` and steps the module
once per clock tick. Speed changes how often ticks happen, never dt
(D006). Exercised from Python, plus one offscreen QML check in its own
process; nothing here checks real-time accuracy, which ``utils/tests``
covers.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402
from utils.system_clock import (  # noqa: E402
    ALLOWED_SPEEDS,
    DEFAULT_TICK_S,
    InvalidClockSettingError,
)

POWER_W = 100000.0


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the clock driver needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make() -> tuple[TrainModelState, Any]:
    """Return a fresh model state and a harness driving it."""
    state = TrainModelState()
    return state, harness_module.TestHarnessState(LocalLink(state))


def wait_for(predicate: Callable[[], bool], timeout_s: float = 5.0) -> None:
    """Spin the event loop until ``predicate()`` holds."""
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_dt_is_the_clock_tick() -> None:
    """Check dt is the shared clock's default tick length."""
    _, harness = make()
    assert harness.property("dt") == DEFAULT_TICK_S


def test_speed_starts_at_real_time() -> None:
    """Check the harness offers the clock's speeds and starts at 1x."""
    _, harness = make()
    assert harness.property("speeds") == list(ALLOWED_SPEEDS) == [1, 10]
    assert harness.property("speed") == 1


def test_set_speed_keeps_dt() -> None:
    """Check 10x changes the speed and leaves dt alone."""
    _, harness = make()
    harness.setSpeed(10)
    assert harness.property("speed") == 10
    assert harness.property("dt") == DEFAULT_TICK_S
    harness.setSpeed(1)
    assert harness.property("speed") == 1


def test_speed_change_notifies_once() -> None:
    """Check a speed change notifies the view, and a repeat does not."""
    _, harness = make()
    notified: list[bool] = []
    harness.runControlChanged.connect(lambda: notified.append(True))
    harness.setSpeed(10)
    harness.setSpeed(10)
    assert notified == [True]


def test_unsupported_speed_rejected() -> None:
    """Check a speed the clock does not allow is refused."""
    _, harness = make()
    with pytest.raises(InvalidClockSettingError):
        harness.setSpeed(5)
    assert harness.property("speed") == 1


def test_same_ticks_same_train_at_any_speed() -> None:
    """Check hand ticks at 1x and 10x give the same train (D006)."""
    snapshots = []
    for speed in ALLOWED_SPEEDS:
        state, harness = make()
        harness.setSpeed(speed)
        harness.setInput("power_command", POWER_W)
        assert harness.sendInputs()
        for _ in range(49):
            harness.advanceTick()
        assert harness.property("tick") == 50
        assert harness.property("elapsed") == "00:00:05"
        snapshots.append(state.property("snapshot"))
    assert snapshots[0] == snapshots[1]


def test_running_clock_steps_the_module() -> None:
    """Check the running clock steps the module and holding stops it."""
    state, harness = make()
    harness.setInput("power_command", POWER_W)
    assert harness.sendInputs()
    harness.setSpeed(10)
    harness.setRunning(True)
    assert harness.property("running")
    wait_for(lambda: harness.property("tick") >= 10)
    harness.setRunning(False)
    assert not harness.property("running")
    held = harness.property("tick")
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    assert harness.property("tick") == held
    assert state.property("snapshot")["actual_speed"] > 0.0


def test_reset_holds_clock_and_keeps_speed() -> None:
    """Check a reset holds the clock and keeps the chosen speed."""
    _, harness = make()
    harness.setSpeed(10)
    assert harness.sendInputs()
    harness.setRunning(True)
    harness.resetModule()
    assert not harness.property("running")
    assert harness.property("tick") == 0
    assert harness.property("elapsed") == "00:00:00"
    assert harness.property("speed") == 10


def test_output_rows_are_stable_across_ticks() -> None:
    """Check output definitions stay fixed and values follow the rows."""
    _, harness = make()
    definitions = harness.property("outputDefinitions")
    assert [
        {key: row[key] for key in ("name", "kind", "unit")}
        for row in harness.property("outputs")
    ] == definitions
    harness.setInput("power_command", POWER_W)
    assert harness.sendInputs()
    harness.advanceTick()
    assert harness.property("outputDefinitions") == definitions
    assert harness.property("outputValues") == {
        row["name"]: row["value"] for row in harness.property("outputs")
    }
    assert harness.property("outputValues")["actual_speed"] > 0.0


def test_clock_controls_in_the_real_test_ui() -> None:
    """Run the offscreen QML check for the speed toggle and output rows."""
    script = Path(__file__).with_name("clock_ui_check.py")
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        timeout=60, env={
            **os.environ, "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software", "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # A QML binding error is a failure even when the checks pass.
    assert ".qml:" not in result.stderr, result.stderr
