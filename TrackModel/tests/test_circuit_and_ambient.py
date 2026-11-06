"""Per-block track circuit in the snapshot, and ambient set in the UI."""

from __future__ import annotations

import math

import pytest

from track_model.interface import (
    InvalidInputError,
    TrackControllerCommands,
    TrackFailure,
)
from tests.helpers import DT_S, make_inputs, make_model

BLOCK = "GREEN C-9"


def _commands() -> TrackControllerCommands:
    return TrackControllerCommands(
        commanded_speed_mps={BLOCK: 12}, commanded_authority={BLOCK: 3},
    )


def test_snapshot_shows_commanded_speed_and_authority() -> None:
    """Check that each block's track circuit is in the snapshot."""
    model = make_model()
    model.step(DT_S, make_inputs(controller=_commands()))
    circuit = model.snapshot().track_circuit
    assert circuit[BLOCK].commanded_speed_mps == 12
    assert circuit[BLOCK].authority_blocks == 3
    assert circuit["GREEN C-10"].commanded_speed_mps == 0
    assert circuit["GREEN C-10"].authority_blocks == 0


def test_dead_circuit_shows_zero() -> None:
    """Check that a failed circuit shows 0 m/s and 0 blocks."""
    model = make_model()
    model.step(DT_S, make_inputs(controller=_commands()))
    model.set_block_failure(BLOCK, TrackFailure.BROKEN_RAIL)
    signal = model.snapshot().track_circuit[BLOCK]
    assert (signal.commanded_speed_mps, signal.authority_blocks) == (0, 0)
    model.set_block_failure(BLOCK, TrackFailure.NONE)
    assert model.snapshot().track_circuit[BLOCK].commanded_speed_mps == 12


def test_ambient_set_in_ui_beats_the_test_ui() -> None:
    """Check that the UI temperature wins over the one a step sends."""
    model = make_model()
    model.set_ambient_temp(-5.0)
    assert model.snapshot().ambient_temp_c == -5.0
    model.step(DT_S, make_inputs(ambient_temp_c=20.0))
    assert model.snapshot().ambient_temp_c == -5.0


def test_test_ui_ambient_applies_until_one_is_set() -> None:
    """Check that the step's temperature is used with no UI override."""
    model = make_model()
    model.step(DT_S, make_inputs(ambient_temp_c=20.0))
    assert model.snapshot().ambient_temp_c == 20.0


def test_reset_clears_the_ambient_override() -> None:
    """Check that a restart goes back to the test UI's temperature."""
    model = make_model()
    model.set_ambient_temp(-5.0)
    model.reset()
    model.step(DT_S, make_inputs(ambient_temp_c=20.0))
    assert model.snapshot().ambient_temp_c == 20.0


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_non_finite_ambient_is_rejected(bad: float) -> None:
    """Check that a non-finite temperature changes nothing."""
    model = make_model()
    with pytest.raises(InvalidInputError):
        model.set_ambient_temp(bad)
    assert model.snapshot().ambient_temp_c == 0.0
