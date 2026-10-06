"""Tests for the test UI's stand-in Track Model and its Blue Line.

The layout conversion and block following alone, then the harness
following the Blue Line with the real Train Model. No QML is loaded.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_model import harness as harness_module  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402
from train_model.track_stub import (  # noqa: E402
    TrackBlock,
    TrackStub,
    blocks_from_layout,
    load_blue_line,
)


@pytest.fixture(scope="module", autouse=True)
def qt_app() -> Iterator[None]:
    """Provide the Qt application the harness timer needs."""
    app = QCoreApplication.instance() or QCoreApplication([])
    yield
    del app


def make_harness(**kwargs: Any) -> tuple[TrainModelState, Any]:
    """Return a fresh model state and a harness driving it."""
    state = TrainModelState()
    return state, harness_module.TestHarnessState(LocalLink(state), **kwargs)


def block(block_id: str, length_m: float = 50.0) -> TrackBlock:
    """Return a flat block with no station."""
    return TrackBlock(block_id, length_m, 0.0, 0.0, 10.0, "", "")


def test_the_blue_line_loads_with_its_route_to_station_b() -> None:
    """Check the default route: section A, then B through the switch."""
    line = load_blue_line()
    assert line is not None
    assert line.name == "Blue Line"
    ids = [b.block_id for b in line.route]
    assert ids == [str(n) for n in range(1, 11)]
    for b in line.route:
        assert b.length_m == 50.0
        assert b.grade_deg == 0.0
        assert b.speed_limit_mps == pytest.approx(50 / 3.6)
    assert line.route[9].station == "Station B"
    # The transponder in block 9 announces the station ahead.
    assert line.route[8].beacon_station == "Station B"
    assert [b.beacon_station for b in line.route[:8]] == [""] * 8


def test_the_other_leg_leads_to_station_c() -> None:
    """Check that routing through section C reaches Station C."""
    line = load_blue_line(sections=("A", "C"))
    assert line is not None
    ids = [b.block_id for b in line.route]
    assert ids == [str(n) for n in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]]
    assert line.route[-1].station == "Station C"
    assert line.route[-2].beacon_station == "Station C"


def test_layout_units_become_backend_units() -> None:
    """Check percent grade, km/h and the cumulative elevation."""
    layout = {"blocks": [{
        "block_number": 7, "section": "X", "length_m": 100,
        "grade_percent": 5, "speed_limit_kmh": 36,
        "elevation_m": 5, "cumulative_elevation_m": 12.5,
    }]}
    (only,) = blocks_from_layout(layout, ("X",))
    assert only.block_id == "7"
    assert only.grade_deg == pytest.approx(math.degrees(math.atan(0.05)))
    assert only.speed_limit_mps == pytest.approx(10.0)
    assert only.elevation_m == 12.5


def test_a_missing_layout_loads_nothing(tmp_path: Path) -> None:
    """Check that an unreadable layout leaves the rows to be typed."""
    assert load_blue_line(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_blue_line(bad) is None


def test_follow_moves_on_at_the_block_length_and_flips_polarity() -> None:
    """Check block changes, polarity and the end of the route."""
    stub = TrackStub("Test", [block("1"), block("2", 20.0)])
    assert stub.inputs()["block"] == "1"
    assert not stub.inputs()["polarity"]
    assert not stub.follow(49.9)
    assert stub.follow(50.0)
    assert stub.inputs()["block"] == "2"
    assert stub.inputs()["polarity"]
    # The last block keeps the train.
    assert not stub.follow(1_000.0)
    assert stub.inputs()["block"] == "2"
    stub.reset()
    assert stub.inputs()["block"] == "1"
    assert not stub.inputs()["polarity"]


def test_an_empty_route_is_refused() -> None:
    """Check that a stub needs a block to stand on."""
    with pytest.raises(ValueError):
        TrackStub("Empty", [])


def test_the_harness_loads_the_blue_line_by_default() -> None:
    """Check the track rows start on the Blue Line's first block."""
    _, harness = make_harness()
    assert harness.trackName == "Blue Line"
    values = harness.inputValues
    assert values["block"] == "1"
    assert values["speed_limit"] == pytest.approx(50 / 3.6)
    assert values["station"] == ""


def test_a_manual_track_keeps_the_typed_rows() -> None:
    """Check track=None leaves the track rows to the tester."""
    _, harness = make_harness(track=None)
    assert harness.trackName == "Manual"
    assert harness.inputValues["block"] == ""
    assert harness.inputValues["speed_limit"] == 0.0


def test_the_train_runs_the_blue_line_to_station_b() -> None:
    """Check blocks, the beacon and the station along the route."""
    state, harness = make_harness()
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    seen: dict[str, dict[str, Any]] = {}
    changes = 0
    for _ in range(600):
        harness.advanceTick()
        outputs = state.outputs()
        changes += outputs.track.block_changed
        seen.setdefault(outputs.track.block_id, {
            "beacon": outputs.controller.beacon,
            "station": harness.inputValues["station"],
        })
    assert list(seen) == [str(n) for n in range(1, 11)]
    assert changes == 9
    beacon = seen["9"]["beacon"]
    assert beacon is not None and beacon.station_name == "Station B"
    assert seen["10"]["station"] == "Station B"


def test_a_typed_track_row_lasts_until_the_next_block() -> None:
    """Check that an edit is kept within a block and replaced after it."""
    state, harness = make_harness()
    harness.setInput("grade", 1.0)
    harness.setInput("power_command", 200_000.0)
    assert harness.sendInputs()
    assert state.snapshot["grade"] == 1.0
    while state.outputs().track.block_id == "1":
        harness.advanceTick()
    harness.advanceTick()
    assert state.snapshot["grade"] == 0.0
    assert harness.inputValues["block"] == "2"


def test_reset_returns_to_the_first_block() -> None:
    """Check that resetting the module also resets the track."""
    _, harness = make_harness()
    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    for _ in range(300):
        harness.advanceTick()
    assert harness.inputValues["block"] != "1"
    harness.resetModule()
    assert harness.inputValues["block"] == "1"
    assert not harness.inputValues["polarity"]
