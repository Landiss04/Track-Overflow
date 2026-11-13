"""Tests for the test UI's stand-in station dwell (D007, Kevin).

Standing in for the Train Controller, the test UI holds the train at a
station for the 45 s dwell once a door opens there: no power, service
brake on, doors kept open, whatever the tester enters. No QML is loaded.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.harness import DWELL_S  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402

DT = 0.1
DWELL_TICKS = round(DWELL_S / DT)


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the harness timer needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make_harness() -> tuple[TrainModelState, Any]:
    """Return a model and a harness with hand-typed track rows."""
    state = TrainModelState()
    return state, harness_module.TestHarnessState(
        LocalLink(state), track=None)


def send(harness: Any, **rows: Any) -> None:
    """Stage ``rows`` and send them as one tick."""
    for name, value in rows.items():
        harness.setInput(name, value)
    assert harness.sendInputs(), harness.inputError


def arrive(state: TrainModelState, harness: Any, station: str) -> None:
    """Drive off, then brake to a stop with ``station`` in the rows."""
    send(harness, power_command=480_000.0, service_brake_command=False,
         left_door_command=False, station="")
    for _ in range(20):
        harness.advanceTick()
    send(harness, power_command=0.0, service_brake_command=True,
         station=station)
    while state.outputs().controller.actual_speed_mps != 0.0:
        harness.advanceTick()


def test_the_dwell_is_45_s() -> None:
    """Check the dwell is the decided 45 s (D007)."""
    assert DWELL_S == 45.0


def test_a_door_opened_at_a_station_holds_the_train_for_the_dwell() -> None:
    """Check the train stays, doors open, until the dwell has run."""
    state, harness = make_harness()
    arrive(state, harness, "Station B")
    send(harness, left_door_command=True)
    # The tester tries to leave at once: doors shut, full power.
    send(harness, left_door_command=False, service_brake_command=False,
         power_command=480_000.0)
    # The door's own tick began the dwell; this send is its second.
    held = 2
    while harness.dwellLeft > 0.0:
        ctl = state.outputs().controller
        assert ctl.actual_speed_mps == 0.0
        assert ctl.door_left_open
        assert state.snapshot["power_command"] == 0.0
        harness.advanceTick()
        held += 1
        assert held <= DWELL_TICKS + 2
    assert held >= DWELL_TICKS
    for _ in range(5):
        harness.advanceTick()
    ctl = state.outputs().controller
    assert not ctl.door_left_open
    assert ctl.actual_speed_mps > 0.0


def test_the_dwell_counts_down_in_run_control() -> None:
    """Check the remaining dwell falls by one tick per tick."""
    state, harness = make_harness()
    arrive(state, harness, "Station B")
    assert harness.dwellLeft == 0.0
    send(harness, left_door_command=True)
    harness.advanceTick()
    first = harness.dwellLeft
    assert 0.0 < first <= DWELL_S
    harness.advanceTick()
    assert harness.dwellLeft == pytest.approx(first - DT)


def test_one_dwell_per_stop() -> None:
    """Check reopening a door at the same stop does not hold again."""
    state, harness = make_harness()
    arrive(state, harness, "Station B")
    send(harness, left_door_command=True)
    harness.advanceTick()
    assert harness.dwellLeft > 0.0
    while harness.dwellLeft > 0.0:
        harness.advanceTick()
    send(harness, left_door_command=False)
    send(harness, left_door_command=True)
    harness.advanceTick()
    assert harness.dwellLeft == 0.0
    # A new stop dwells again.
    arrive(state, harness, "Station C")
    send(harness, left_door_command=True)
    harness.advanceTick()
    assert harness.dwellLeft > 0.0


def test_no_dwell_away_from_a_station() -> None:
    """Check a door opened between stations holds nothing."""
    state, harness = make_harness()
    arrive(state, harness, "")
    send(harness, left_door_command=True)
    harness.advanceTick()
    assert harness.dwellLeft == 0.0
    send(harness, left_door_command=False, service_brake_command=False,
         power_command=480_000.0)
    harness.advanceTick()
    assert state.outputs().controller.actual_speed_mps > 0.0


def test_a_rejected_step_leaves_the_dwell_as_it_was() -> None:
    """Check a refused send neither starts nor shortens the dwell."""
    state, harness = make_harness()
    arrive(state, harness, "Station B")
    send(harness, left_door_command=True)
    harness.advanceTick()
    left = harness.dwellLeft
    harness.setInput("power_command", -1.0)
    assert not harness.sendInputs()
    assert harness.dwellLeft == left


def test_reset_clears_the_dwell() -> None:
    """Check resetting the module also ends a dwell."""
    state, harness = make_harness()
    arrive(state, harness, "Station B")
    send(harness, left_door_command=True)
    harness.advanceTick()
    assert harness.dwellLeft > 0.0
    harness.resetModule()
    assert harness.dwellLeft == 0.0


def test_a_door_sent_with_power_still_gets_the_dwell() -> None:
    """Check opening a door and powering off in one send is held."""
    state, harness = make_harness()
    arrive(state, harness, "Station B")
    send(harness, left_door_command=True, service_brake_command=False,
         power_command=480_000.0)
    assert harness.dwellLeft > 0.0
    for _ in range(DWELL_TICKS - 2):
        harness.advanceTick()
        assert state.outputs().controller.actual_speed_mps == 0.0


def test_a_count_sent_while_moving_waits_and_boards_at_the_stop() -> None:
    """Check a boarding count sent too early is not lost.

    It waits in its row until a step can board it: at rest with a door
    open. It then boards once.
    """
    state, harness = make_harness()
    send(harness, power_command=200_000.0)
    for _ in range(20):
        harness.advanceTick()
    send(harness, passengers_boarded=40)
    assert state.snapshot["passengers"] == 0
    assert harness.inputValues["passengers_boarded"] == 40
    send(harness, power_command=0.0, service_brake_command=True,
         station="Station B")
    while state.outputs().controller.actual_speed_mps != 0.0:
        harness.advanceTick()
    assert harness.inputValues["passengers_boarded"] == 40
    send(harness, left_door_command=True)
    assert state.snapshot["passengers"] == 40
    assert harness.inputValues["passengers_boarded"] == 0
    for _ in range(5):
        harness.advanceTick()
    assert state.snapshot["passengers"] == 40
