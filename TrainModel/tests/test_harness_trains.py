"""The test UI creates, drives and removes many trains (Kevin 2026-10-09).

Every tick steps every train, each on its own rows and stand-ins. The
page shows and edits the selected train.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model.fleet import TrainModelFleet  # noqa: E402
from train_model.harness import TestHarnessState as Harness  # noqa: E402
from train_model.link import LocalLink, next_train_id  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the harness timer needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make_harness(**kwargs: Any) -> tuple[TrainModelFleet, Harness]:
    """Return a one-train fleet and a harness driving it."""
    fleet = TrainModelFleet()
    fleet.add("T-1")
    return fleet, Harness(LocalLink(fleet), **kwargs)


def speed(fleet: TrainModelFleet, train_id: str) -> float:
    """One train's actual speed."""
    return fleet.get(train_id).outputs().controller.actual_speed_mps


def test_new_trains_take_the_next_id() -> None:
    assert next_train_id([]) == "T-1"
    assert next_train_id(["T-1"]) == "T-2"
    assert next_train_id(["T-1", "T-3"]) == "T-4"
    assert next_train_id(["T-2", "GREEN-7", "T-01"]) == "T-3"


def test_add_selects_the_new_train_and_puts_it_in_the_fleet() -> None:
    fleet, harness = make_harness()
    assert harness.trainIds == ["T-1"] and not harness.canRemoveTrain
    assert harness.addTrain()
    assert fleet.ids() == ["T-1", "T-2"]
    assert harness.trainIds == ["T-1", "T-2"]
    assert harness.selectedTrain == "T-2" and harness.selectedIndex == 1
    assert harness.canRemoveTrain


def test_every_tick_steps_every_train_on_its_own_inputs() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    harness.setInput("power_command", 100_000.0)
    assert harness.sendInputs()
    for _ in range(20):
        harness.advanceTick()
    # T-2 was given power; T-1 was not, but was stepped all the same.
    assert speed(fleet, "T-2") > 0 and speed(fleet, "T-1") == 0
    assert fleet.get("T-1").snapshot["clock"] == "00:00:02"
    assert harness.tick == 21


def test_edits_belong_to_the_train_they_were_made_on() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    harness.setInput("power_command", 100_000.0)
    harness.selectTrain("T-1")
    assert harness.pendingInputs == {}
    assert harness.inputValues["power_command"] == 0.0
    harness.setInput("temperature_setpoint", 25.0)
    harness.selectTrain("T-2")
    assert harness.pendingInputs == {"power_command": True}
    # A send carries every train's edits.
    assert harness.sendInputs()
    assert harness.pendingInputs == {}
    harness.selectTrain("T-1")
    assert harness.pendingInputs == {}
    assert harness.inputValues["temperature_setpoint"] == 25.0


def test_a_rejected_edit_names_its_train_and_steps_none() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    harness.setInput("power_command", -1.0)
    harness.selectTrain("T-1")
    harness.setInput("power_command", 100_000.0)
    assert not harness.sendInputs()
    assert harness.inputError.startswith("T-2: ")
    assert harness.tick == 0
    assert fleet.get("T-1").snapshot["clock"] == "00:00:00"
    # Both drafts are kept for correction.
    assert harness.pendingInputs == {"power_command": True}


def test_each_train_follows_the_line_on_its_own() -> None:
    fleet, harness = make_harness()
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    for _ in range(600):
        harness.advanceTick()
    first_block = harness.inputValues["block"]
    assert first_block != "1"
    harness.addTrain()
    # The new train starts at the start of the line.
    assert harness.inputValues["block"] == "1"
    harness.advanceTick()
    assert fleet.get("T-2").outputs().track.block_id == "1"
    harness.selectTrain("T-1")
    assert harness.inputValues["block"] != "1"


def test_removing_the_selected_train_selects_a_neighbour() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    harness.addTrain()
    harness.selectTrain("T-2")
    assert harness.removeTrain()
    assert fleet.ids() == ["T-1", "T-3"]
    assert harness.selectedTrain == "T-3"
    assert harness.removeTrain()
    assert harness.selectedTrain == "T-1"
    # The last train stays.
    assert not harness.removeTrain()
    assert "last train" in harness.inputError
    assert fleet.ids() == ["T-1"]
    harness.advanceTick()
    assert harness.tick == 1


def test_a_train_added_mid_run_starts_fresh_without_drift() -> None:
    fleet, harness = make_harness()
    for _ in range(30):
        harness.advanceTick()
    harness.addTrain()
    for _ in range(30):
        harness.advanceTick()
    assert harness.driftTicks == 0
    assert fleet.get("T-2").snapshot["clock"] == "00:00:03"
    assert harness.elapsed == "00:00:06"


def test_reset_resets_every_train_and_keeps_the_roster() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    harness.setInput("power_command", 100_000.0)
    assert harness.sendInputs()
    harness.resetModule()
    assert fleet.ids() == ["T-1", "T-2"]
    assert speed(fleet, "T-2") == 0 and harness.tick == 0
    assert harness.inputValues["power_command"] == 0.0


def test_the_passenger_latch_override_clears_only_its_train() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    harness.advanceTick()
    for state in fleet:
        state.applyEmergencyBrake()
    harness.setInput("emergency_brake_command", False)
    assert harness.sendInputs()
    assert not fleet.get("T-2").snapshot["passenger_ebrake_pulled"]
    assert fleet.get("T-1").snapshot["passenger_ebrake_pulled"]


def test_a_train_removed_elsewhere_drops_its_stand_ins() -> None:
    fleet, harness = make_harness()
    harness.addTrain()
    fleet.remove("T-2")
    assert harness.trainIds == ["T-1"]
    assert harness.selectedTrain == "T-1"
    harness.advanceTick()
    assert harness.inputError == ""
