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
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.link import (  # noqa: E402
    LinkError,
    LocalLink,
    SocketLink,
)
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
    assert harness.property("outputValues")["position_offset"] > 0.0


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


# ---------------------------------------------------------------------- #
# Steps are checked before their tick; drift is checked every 30 ticks
# ---------------------------------------------------------------------- #

def clock_ticks(harness: Any) -> int:
    """Read how many ticks the harness's shared clock has taken."""
    count: int = harness._clock.tick_count
    return count


class DroppableLink(LocalLink):
    """A same-process link whose Train Model can drop or lose a reply."""

    def __init__(self, state: TrainModelState) -> None:
        super().__init__(state)
        self.up = True
        self.lose_next_reply = False

    @property
    def connected(self) -> bool:
        """Whether the Train Model is reachable."""
        return self.up

    def step(self, *args: Any, **kwargs: Any) -> Any:
        """Step, or fail as a link that dropped mid-step would."""
        if self.lose_next_reply:
            self.lose_next_reply = False
            raise LinkError("Train Model did not respond")
        return super().step(*args, **kwargs)


@pytest.mark.parametrize(("name", "value"), [
    ("power_command", -1.0),
    ("grade", float("nan")),
    ("beacon_platform_side", "X"),
])
def test_rejected_send_does_not_tick_the_clock(name: str, value: Any) -> None:
    """Check input the module would reject never advances the clock."""
    state, harness = make()
    harness.setInput("beacon_station", "Dormont")
    harness.setInput(name, value)
    assert not harness.sendInputs()
    assert harness.property("inputError")
    assert clock_ticks(harness) == 0
    assert state.property("snapshot")["clock"] == "00:00:00"
    harness.setInput(name, 0.0 if name != "beacon_platform_side" else "L")
    assert harness.sendInputs()
    assert clock_ticks(harness) == harness.property("tick") == 1


def test_rejected_first_advance_does_not_tick_the_clock() -> None:
    """Check advancing a fresh run with a bad draft leaves time alone."""
    _, harness = make()
    harness.setInput("power_command", -1.0)
    harness.advanceTick()
    assert harness.property("inputError")
    assert clock_ticks(harness) == harness.property("tick") == 0


def test_run_refuses_a_bad_first_draft() -> None:
    """Check Run does not start the clock on input that would fail."""
    _, harness = make()
    harness.setInput("power_command", -1.0)
    harness.setRunning(True)
    assert not harness.property("running")
    assert "nonnegative" in harness.property("inputError")
    assert clock_ticks(harness) == 0


def test_unreachable_module_does_not_tick_the_clock() -> None:
    """Check an unreachable Train Model holds the clock, untouched."""
    link = SocketLink(f"train-model-test-{uuid.uuid4().hex}")
    harness = harness_module.TestHarnessState(link)
    for action in (harness.sendInputs, harness.advanceTick,
                   lambda: harness.setRunning(True)):
        action()
        assert not harness.property("running")
        assert "not running" in harness.property("inputError")
        assert clock_ticks(harness) == 0


def test_link_drop_holds_a_running_clock() -> None:
    """Check the clock is held as soon as the Train Model drops."""
    state = TrainModelState()
    link = DroppableLink(state)
    harness = harness_module.TestHarnessState(link)
    harness.setRunning(True)
    assert harness.property("running")
    link.up = False
    link.connectedChanged.emit()
    assert not harness.property("running")
    assert "not running" in harness.property("inputError")
    assert clock_ticks(harness) == 0


def test_no_drift_while_steps_keep_up() -> None:
    """Check normal ticking, with rejections, reports no drift."""
    _, harness = make()
    notified: list[bool] = []
    harness.driftChanged.connect(lambda: notified.append(True))
    assert harness.sendInputs()
    for count in range(3 * harness_module.DRIFT_CHECK_TICKS):
        if count % 7 == 0:
            harness.setInput("power_command", -1.0)
            assert not harness.sendInputs()
            harness.setInput("power_command", POWER_W)
        harness.advanceTick()
    assert clock_ticks(harness) == harness.property("tick")
    assert harness.property("driftTicks") == 0
    assert not notified


def test_drift_check_runs_every_30_ticks() -> None:
    """Check a lost step shows as drift at the next 30-tick check."""
    state = TrainModelState()
    link = DroppableLink(state)
    harness = harness_module.TestHarnessState(link)
    assert harness_module.DRIFT_CHECK_TICKS == 30
    assert harness.sendInputs()
    link.lose_next_reply = True
    harness.advanceTick()
    assert clock_ticks(harness) == 2
    assert harness.property("tick") == 1
    while clock_ticks(harness) < 29:
        harness.advanceTick()
    assert harness.property("driftTicks") == 0  # not checked yet
    harness.advanceTick()
    assert clock_ticks(harness) == 30
    assert harness.property("driftTicks") == 1
    while clock_ticks(harness) < 60:
        harness.advanceTick()
    assert harness.property("driftTicks") == 1
    harness.resetModule()
    assert harness.property("driftTicks") == 0
