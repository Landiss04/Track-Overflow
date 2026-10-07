"""Contract tests: the implementation satisfies the protocol."""

from __future__ import annotations

import inspect

from track_model import interface
from track_model.interface import (
    TrackModelOutputs,
    TrackModelSnapshot,
)
from track_model.model import TrackModel
from tests.helpers import DT_S, make_inputs, make_model, report


def test_protocol_conformance_static() -> None:
    """Assign to the protocol type; ``mypy`` checks this."""
    model: interface.TrackModel = make_model()
    assert model.config.layout_paths


def test_protocol_members_match_signatures() -> None:
    """Check that every protocol method exists with the same parameters."""
    for name in ("step", "snapshot", "set_block_failure", "edit_block",
                 "reset"):
        expected = inspect.signature(getattr(interface.TrackModel, name))
        actual = inspect.signature(getattr(TrackModel, name))
        assert list(actual.parameters) == list(expected.parameters), name


def test_step_returns_outputs() -> None:
    """Check that ``step`` returns ``TrackModelOutputs``."""
    outputs = make_model().step(DT_S, make_inputs())
    assert isinstance(outputs, TrackModelOutputs)


def test_snapshot_has_no_side_effects() -> None:
    """Check that two consecutive snapshots are equal."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1")}))
    first = model.snapshot()
    assert isinstance(first, TrackModelSnapshot)
    assert first == model.snapshot()


def test_snapshot_reflects_last_step() -> None:
    """Check that the snapshot reports the outputs of the last step."""
    model = make_model()
    outputs = model.step(DT_S, make_inputs({"T1": report("GREEN A-1")}))
    assert model.snapshot().outputs == outputs
