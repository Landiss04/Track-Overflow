"""Train Model implementation.

Currently a stub: ``step`` returns safe values and nothing is simulated.
It satisfies the ``TrainModel`` protocol in ``interface.py`` so the
harness and the contract tests can run against it.
"""

from __future__ import annotations

from train_model.interface import (
    ControllerOutputs,
    FailureState,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
    TrainModelSnapshot,
    TrackOutputs,
)

STUB = True

# The stub has seen no Track Info before its first step.
_NO_BLOCK_ID = ""


def _safe_outputs(block_id: str, capacity: int) -> TrainModelOutputs:
    # Every numeric zero, every flag off, no beacon, no authority.
    return TrainModelOutputs(
        controller=ControllerOutputs(
            actual_speed_mps=0.0,
            emergency_brake_active=False,
            door_left_open=False,
            door_right_open=False,
            cabin_lights_on=False,
            headlights_on=False,
            cabin_temp_f=0.0,
            commanded_speed_mps=0.0,
            authority_block_id=None,
            speed_limit_mps=0.0,
            beacon=None,
            failures=FailureState(),
        ),
        track=TrackOutputs(
            block_id=block_id,
            offset_m=0.0,
            actual_speed_mps=0.0,
            block_changed=False,
            passenger_capacity=capacity,
        ),
    )


class TrainModel:
    """Stub Train Model. Constructed as ``TrainModel(config)``."""

    def __init__(self, config: TrainConfig) -> None:
        """Store the configuration and start with safe outputs."""
        self.config = config
        self._outputs = _safe_outputs(_NO_BLOCK_ID, config.capacity)

    def step(self, dt: float, inputs: TrainModelInputs) -> TrainModelOutputs:
        """Return safe outputs, echoing the block ID from the input."""
        self._outputs = _safe_outputs(
            inputs.track.track_info.block_id, self.config.capacity
        )
        return self._outputs

    def snapshot(self) -> TrainModelSnapshot:
        """Return the current state for display. No side effects."""
        return TrainModelSnapshot(
            mass_kg=0.0,
            acceleration_mps2=0.0,
            velocity_mps=0.0,
            n_crew=0,
            n_passengers=0,
            passenger_ebrake_pulled=False,
            outputs=self._outputs,
        )

    def set_failures(self, failures: FailureState) -> None:
        """Accept a fault injection. The stub ignores it."""

    def pull_passenger_emergency_brake(self) -> None:
        """Accept a passenger pull. The stub ignores it."""
