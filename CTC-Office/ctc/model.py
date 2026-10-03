"""Stub CTC Office: satisfies the contract with no routing logic yet.

The stub turns dispatcher actions straight into outputs so data can be
seen crossing the boundary: each dispatched train gets its destination
as authority and a placeholder suggested speed, and closed blocks and
maintenance mode pass through. Track Controller and Track Model inputs
are validated and recorded but drive nothing yet. Real logic replaces
this class behind the same ``CtcOffice`` contract.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ctc.interface import (
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    QueuedTrain,
    TrainSuggestion,
    TrackControllerOutputs,
)

if TYPE_CHECKING:
    from ctc.schedule import Schedule

# Placeholder until the CTC computes speeds. Not a decided value.
STUB_SUGGESTED_SPEED_MPS = 10.0


class CtcError(Exception):
    """Base class for every CTC Office error."""


class InvalidTimeStepError(CtcError):
    """dt was not finite and positive."""


class InvalidInputError(CtcError):
    """An input or dispatcher action failed validation."""


def _require_id(value: str, what: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{what} must be a non-empty string ID")


def _require_finite(value: float, what: str) -> None:
    if not math.isfinite(value):
        raise InvalidInputError(f"{what} must be finite, got {value!r}")


def validate_inputs(inputs: CtcInputs) -> None:
    """Raise ``InvalidInputError`` if any input is malformed."""
    track_controller = inputs.track_controller
    for block in track_controller.occupancy:
        _require_id(block.block_id, "occupancy block_id")
    for train in track_controller.trains:
        _require_id(train.train_id, "train_id")
        _require_id(train.block_id, f"block_id of {train.train_id}")
        _require_finite(train.offset_m, f"offset_m of {train.train_id}")
        _require_finite(train.speed_mps, f"speed_mps of {train.train_id}")
    for switch in track_controller.switches:
        _require_id(switch.switch_id, "switch_id")
    for crossing in track_controller.crossings:
        _require_id(crossing.crossing_id, "crossing_id")
    for failure in track_controller.failures:
        _require_id(failure.block_id, "failure block_id")
    if inputs.track_model.ticket_sales < 0:
        raise InvalidInputError("ticket_sales must not be negative")


class StubCtcOffice:
    """A ``CtcOffice`` with dispatcher pass-through and no routing."""

    def __init__(
        self, suggested_speed_mps: float = STUB_SUGGESTED_SPEED_MPS
    ) -> None:
        _require_finite(suggested_speed_mps, "suggested_speed_mps")
        self._suggested_speed_mps = suggested_speed_mps
        self._orders: dict[str, str] = {}
        self._closed: set[str] = set()
        self._maintenance = False
        self._clock_speedup = False
        self._inputs: CtcInputs | None = None
        self._elapsed_s = 0.0
        self._tickets_total = 0
        self._schedule: Schedule | None = None

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        """Advance one tick; see ``CtcOffice.step``."""
        if not (isinstance(dt, (int, float)) and math.isfinite(dt)
                and dt > 0):
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {dt!r}")
        validate_inputs(inputs)

        self._inputs = inputs
        self._elapsed_s += dt
        self._tickets_total += inputs.track_model.ticket_sales
        return self._outputs()

    def snapshot(self) -> CtcSnapshot:
        """Current state for display. No side effects."""
        return CtcSnapshot(
            outputs=self._outputs(),
            inputs=self._inputs,
            elapsed_s=self._elapsed_s,
            tickets_sold_total=self._tickets_total,
            queued_trains=self._queued(),
        )

    def dispatch(self, train_id: str, destination_block_id: str) -> None:
        """Send a train toward a destination block."""
        _require_id(train_id, "train_id")
        _require_id(destination_block_id, "destination_block_id")
        self._orders[train_id] = destination_block_id

    def cancel_dispatch(self, train_id: str) -> None:
        """Drop a train's dispatch order, if it has one."""
        self._orders.pop(train_id, None)

    def set_block_closed(self, block_id: str, closed: bool) -> None:
        """Close a block for maintenance, or reopen it."""
        _require_id(block_id, "block_id")
        if closed:
            self._closed.add(block_id)
        else:
            self._closed.discard(block_id)

    def set_maintenance_mode(self, active: bool) -> None:
        self._maintenance = bool(active)

    def set_clock_speedup(self, active: bool) -> None:
        self._clock_speedup = bool(active)

    def load_schedule(self, schedule: Schedule) -> None:
        """Replace the schedule. With no scheduling algorithm yet, every
        run stays queued."""
        self._schedule = schedule

    def _queued(self) -> tuple[QueuedTrain, ...]:
        if self._schedule is None:
            return ()
        runs = sorted(self._schedule.trains,
                      key=lambda t: (t.departure_s, t.line, t.train_id))
        return tuple(
            QueuedTrain(t.line, t.train_id, t.departure_s,
                        t.stops[0].block_id)
            for t in runs)

    def _outputs(self) -> CtcOutputs:
        suggestions = tuple(
            TrainSuggestion(train_id, self._suggested_speed_mps, block_id)
            for train_id, block_id in sorted(self._orders.items())
        )
        return CtcOutputs(
            track_controller=TrackControllerOutputs(
                suggestions=suggestions,
                closed_block_ids=tuple(sorted(self._closed)),
                maintenance_mode=self._maintenance,
            ),
            clock_speedup=self._clock_speedup,
        )
