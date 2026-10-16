"""The central clock's time reaches the Track Model and its window."""

from __future__ import annotations

import json

import pytest

from common.harness.track_model_edges import build_track_model_inputs
from common.interfaces import WaysideCommands
from test_link.codec import decode_inputs, encode_inputs
from track_model.interface import InvalidInputError
from tests.helpers import DT_S, make_inputs, make_model

FIVE_AM_S = 5 * 3600.0


def test_no_clock_time_by_default() -> None:
    """Without a clock the snapshot has no simulation time."""
    model = make_model()
    model.step(DT_S, make_inputs())
    snap = model.snapshot()
    assert snap.sim_time_s is None
    assert snap.elapsed_s == pytest.approx(DT_S)


def test_step_records_clock_time() -> None:
    """The time the harness sends is what the snapshot reports."""
    model = make_model()
    model.step(DT_S, make_inputs(sim_time_s=FIVE_AM_S + 1.5))
    assert model.snapshot().sim_time_s == FIVE_AM_S + 1.5


def test_reset_clears_clock_time() -> None:
    """A module reset forgets the last clock time."""
    model = make_model()
    model.step(DT_S, make_inputs(sim_time_s=FIVE_AM_S))
    model.reset()
    assert model.snapshot().sim_time_s is None


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_bad_clock_time_rejected_whole(bad: float) -> None:
    """A bad time rejects the tick and changes nothing."""
    model = make_model()
    with pytest.raises(InvalidInputError):
        model.step(DT_S, make_inputs(sim_time_s=bad))
    snap = model.snapshot()
    assert snap.elapsed_s == 0.0
    assert snap.sim_time_s is None


def test_clock_time_crosses_the_link() -> None:
    """The JSON codec keeps the time, and keeps its absence."""
    for value in (None, FIVE_AM_S + 0.1):
        sent = make_inputs(sim_time_s=value)
        got = decode_inputs(json.loads(json.dumps(encode_inputs(sent))))
        assert got.sim_time_s == value


def test_edge_passes_clock_time() -> None:
    """build_track_model_inputs carries the clock's time unchanged."""
    inputs = build_track_model_inputs(
        WaysideCommands(), {}, 10.0, sim_time_s=FIVE_AM_S)
    assert inputs.sim_time_s == FIVE_AM_S
    assert build_track_model_inputs(
        WaysideCommands(), {}, 10.0).sim_time_s is None
