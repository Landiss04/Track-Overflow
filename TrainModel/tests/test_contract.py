"""Contract tests for whatever sits at ``train_model.model.TrainModel``.

These hold for the stub and for the real implementation alike, so they
never assert physics. They check only that the protocol is satisfied.
"""

from __future__ import annotations

import inspect

from train_model import interface
from train_model.interface import (
    Beacon,
    ControllerCommands,
    TrackInfo,
    TrackInputs,
    TrackSignal,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
    TrainModelSnapshot,
)
from train_model.model import TrainModel

DT_S = 0.1


def make_inputs(block_id: str = "A1") -> TrainModelInputs:
    """Return a plausible, fully populated input set."""
    return TrainModelInputs(
        controller=ControllerCommands(
            power_cmd_w=10_000.0,
            service_brake=False,
            emergency_brake=False,
            cabin_lights=True,
            headlights=True,
            door_left_open=False,
            door_right_open=False,
            temp_setpoint_f=70.0,
            announcement="",
        ),
        track=TrackInputs(
            track_info=TrackInfo(
                block_id=block_id,
                grade_percent=1.0,
                elevation_m=0.0,
                speed_limit_mps=15.0,
                polarity=True,
            ),
            track_signal=TrackSignal(
                commanded_speed_mps=10.0,
                authority_block_id="A9",
            ),
            beacon=Beacon("Station", "L", False),
            passengers_boarded=0,
        ),
    )


def test_protocol_conformance_static() -> None:
    """Assign to the protocol type; ``mypy --strict`` checks this."""
    model: interface.TrainModel = TrainModel(TrainConfig())
    assert model.config == TrainConfig()


def test_protocol_members_match_signatures() -> None:
    """Check that every protocol method exists with the same parameters."""
    impl = TrainModel(TrainConfig())
    for name in ("step", "snapshot", "set_failures",
                 "pull_passenger_emergency_brake"):
        expected = inspect.signature(getattr(interface.TrainModel, name))
        actual = inspect.signature(getattr(TrainModel, name))
        assert list(actual.parameters) == list(expected.parameters), name
        assert callable(getattr(impl, name))
    assert isinstance(impl.config, TrainConfig)


def test_step_returns_outputs() -> None:
    """Check that ``step`` returns ``TrainModelOutputs``."""
    model = TrainModel(TrainConfig())
    outputs = model.step(DT_S, make_inputs())
    assert isinstance(outputs, TrainModelOutputs)


def test_snapshot_has_no_side_effects() -> None:
    """Check that two consecutive snapshots are equal."""
    model = TrainModel(TrainConfig())
    model.step(DT_S, make_inputs())
    first = model.snapshot()
    second = model.snapshot()
    assert isinstance(first, TrainModelSnapshot)
    assert first == second


def test_snapshot_reflects_last_step() -> None:
    """Check that the snapshot reports the outputs of the last step."""
    model = TrainModel(TrainConfig())
    outputs = model.step(DT_S, make_inputs())
    assert model.snapshot().outputs == outputs
