"""The fleet holds one independent Train Model per running train."""

from __future__ import annotations

import dataclasses
import time
import zlib

import pytest

from train_model.fleet import (
    DuplicateTrainError,
    TrainModelFleet,
    TrainModelFleetError,
    UnknownTrainError,
)
from train_model.interface import TrainConfig, TrainModelInputs
from train_model.model import InvalidInputError, TrainModelError
from tests.test_contract import DT_S, make_inputs


def bad_inputs() -> TrainModelInputs:
    """Inputs the model rejects: a negative power command."""
    inputs = make_inputs()
    return dataclasses.replace(
        inputs,
        controller=dataclasses.replace(inputs.controller, power_cmd_w=-1.0),
    )


def test_add_get_and_remove() -> None:
    """Check trains are kept by ID, in the order they were added."""
    fleet = TrainModelFleet()
    first = fleet.add("T-1", "Green")
    second = fleet.add("T-2", "Red")
    assert fleet.ids() == ["T-1", "T-2"]
    assert len(fleet) == 2 and "T-1" in fleet
    assert fleet.get("T-1") is first and fleet.get("T-2") is second
    assert first.train_id == "T-1" and first.line == "Green"
    assert first.snapshot["train_id"] == "T-1"
    assert first.snapshot["line"] == "Green"
    fleet.remove("T-1")
    assert fleet.ids() == ["T-2"] and "T-1" not in fleet


def test_duplicate_and_unknown_ids_raise() -> None:
    """Check the fleet's errors, all catchable as Train Model errors."""
    fleet = TrainModelFleet()
    fleet.add("T-1")
    with pytest.raises(DuplicateTrainError):
        fleet.add("T-1")
    with pytest.raises(UnknownTrainError):
        fleet.get("T-9")
    with pytest.raises(UnknownTrainError):
        fleet.remove("T-9")
    assert issubclass(TrainModelFleetError, TrainModelError)


def test_trains_are_independent() -> None:
    """Check stepping one train leaves another exactly as it was."""
    fleet = TrainModelFleet()
    moving = fleet.add("T-1")
    still = fleet.add("T-2")
    before = still.outputs()
    for _ in range(50):
        moving.step(DT_S, make_inputs())
    assert moving.outputs().controller.actual_speed_mps > 0.0
    assert still.outputs() == before
    assert still.snapshot["clock"] == "00:00:00"


def test_seed_follows_the_train_id_unless_given() -> None:
    """Check each ID gets its own repeatable seed; a config wins."""
    fleet = TrainModelFleet()
    first = fleet.add("T-1")
    second = fleet.add("T-2")
    # pylint: disable=protected-access
    assert first._config.seed == zlib.crc32(b"T-1")
    assert second._config.seed == zlib.crc32(b"T-2")
    assert first._config.seed != second._config.seed
    given = fleet.add("T-3", config=TrainConfig(seed=7))
    assert given._config.seed == 7


def test_step_all_steps_every_train() -> None:
    """Check one call advances each train and returns its outputs."""
    fleet = TrainModelFleet()
    fleet.add("T-1")
    fleet.add("T-2")
    outputs = fleet.step_all(
        DT_S, {"T-1": make_inputs("A1"), "T-2": make_inputs("B7")},
    )
    assert list(outputs) == ["T-1", "T-2"]
    assert outputs["T-1"].track.block_id == "A1"
    assert outputs["T-2"].track.block_id == "B7"
    assert outputs["T-2"] == fleet.get("T-2").outputs()


def test_step_all_is_all_or_nothing() -> None:
    """Check one train's rejected input leaves every train unchanged."""
    fleet = TrainModelFleet()
    fleet.add("T-1")
    fleet.add("T-2")
    fleet.step_all(DT_S, {"T-1": make_inputs(), "T-2": make_inputs()})
    before = {i: fleet.get(i).outputs() for i in fleet.ids()}
    with pytest.raises(InvalidInputError):
        fleet.step_all(DT_S, {"T-1": make_inputs(), "T-2": bad_inputs()})
    assert {i: fleet.get(i).outputs() for i in fleet.ids()} == before


def test_step_all_needs_inputs_for_exactly_the_fleet() -> None:
    """Check missing or extra inputs raise before any train steps."""
    fleet = TrainModelFleet()
    fleet.add("T-1")
    fleet.add("T-2")
    before = fleet.get("T-1").outputs()
    with pytest.raises(TrainModelFleetError):
        fleet.step_all(DT_S, {"T-1": make_inputs()})
    with pytest.raises(UnknownTrainError):
        fleet.step_all(DT_S, {
            "T-1": make_inputs(), "T-2": make_inputs(),
            "T-9": make_inputs(),
        })
    assert fleet.get("T-1").outputs() == before


def test_selection_follows_adds_and_removes() -> None:
    """Check the first train is selected; removal moves the choice."""
    fleet = TrainModelFleet()
    idle = fleet.current
    assert fleet.selectedIndex == -1 and fleet.count == 0
    first = fleet.add("T-1")
    fleet.add("T-2")
    third = fleet.add("T-3")
    assert fleet.current is first and fleet.selectedIndex == 0
    fleet.selectTrain("T-2")
    fleet.remove("T-2")
    # The next train in the roster takes over.
    assert fleet.current is third and fleet.selectedIndex == 1
    fleet.remove("T-3")
    # With none after it, the one before.
    assert fleet.current is first
    fleet.remove("T-1")
    assert fleet.current is idle and fleet.selectedIndex == -1


def test_removing_an_earlier_train_keeps_the_selection() -> None:
    """Check the selected train stays selected as its index shifts."""
    fleet = TrainModelFleet()
    fleet.add("T-1")
    second = fleet.add("T-2")
    fleet.selectTrain("T-2")
    fleet.remove("T-1")
    assert fleet.current is second and fleet.selectedIndex == 0


def test_select_ignores_unknown_ids() -> None:
    """Check the selector's empty placeholder selects nothing."""
    fleet = TrainModelFleet()
    first = fleet.add("T-1")
    fleet.selectTrain("")
    fleet.selectTrain("T-9")
    assert fleet.current is first


def test_signals_announce_roster_and_selection_changes() -> None:
    """Check the window hears about every change it shows."""
    fleet = TrainModelFleet()
    roster: list[int] = []
    current: list[int] = []
    fleet.rosterChanged.connect(lambda: roster.append(1))
    fleet.currentChanged.connect(lambda: current.append(1))
    fleet.add("T-1")
    assert roster and current
    roster.clear()
    current.clear()
    fleet.add("T-2")
    assert roster and not current
    fleet.selectTrain("T-2")
    assert current
    assert fleet.trains == [
        {"id": "T-1", "line": "", "label": "T-1"},
        {"id": "T-2", "line": "", "label": "T-2"},
    ]


def test_reset_keeps_identity() -> None:
    """Check a reset train keeps its ID and line."""
    fleet = TrainModelFleet()
    state = fleet.add("T-1", "Blue")
    state.step(DT_S, make_inputs())
    state.reset()
    assert state.snapshot["train_id"] == "T-1"
    assert state.snapshot["line"] == "Blue"


def test_twenty_trains_keep_up_at_ten_times_speed() -> None:
    """Check a 20-train tick fits in the 10 ms a 10x clock allows.

    A sanity bound, not a benchmark: at 10x with 0.1 s ticks the clock
    ticks 100 times a real second.
    """
    fleet = TrainModelFleet()
    ids = [f"T-{n}" for n in range(20)]
    for train_id in ids:
        fleet.add(train_id)
    inputs = {train_id: make_inputs() for train_id in ids}
    ticks = 100
    start = time.perf_counter()
    for _ in range(ticks):
        fleet.step_all(DT_S, inputs)
    per_tick_s = (time.perf_counter() - start) / ticks
    assert per_tick_s < 0.010
