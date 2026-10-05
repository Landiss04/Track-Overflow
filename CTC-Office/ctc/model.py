"""Stub CTC Office: satisfies the contract with no routing logic yet.

The stub turns dispatcher actions straight into outputs so data can be
seen crossing the boundary: each dispatched train gets its destination
as authority and a placeholder suggested speed, and closed blocks,
switch commands and maintenance mode pass through. Track Controller and
Track Model inputs are validated against the track layout and recorded
but drive nothing yet. Real logic replaces this class behind the same
``CtcOffice`` contract.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Mapping, get_args

from ctc.interface import (
    BlockRef,
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    DispatchOrder,
    QueuedTrain,
    SwitchCommand,
    SwitchPosition,
    TicketSales,
    TrainSuggestion,
    TrackControllerOutputs,
)
from ctc.track_layout import Line, load_layout

if TYPE_CHECKING:
    from ctc.schedule import Schedule

# Placeholder until the CTC computes speeds. Not a decided value.
STUB_SUGGESTED_SPEED_MPS = 10

_DAY_S = 24 * 60 * 60


class CtcError(Exception):
    """Base class for every CTC Office error."""


class InvalidTimeStepError(CtcError):
    """dt was not finite and positive."""


class InvalidInputError(CtcError):
    """An input or dispatcher action failed validation."""


class MaintenanceModeRequiredError(CtcError):
    """A switch was commanded outside maintenance mode."""


def _require_id(value: str, what: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{what} must be a non-empty string ID")


def _require_finite(value: float, what: str) -> None:
    if not math.isfinite(value):
        raise InvalidInputError(f"{what} must be finite, got {value!r}")


class _Layout:
    """Checks block, switch and crossing references against the track."""

    def __init__(self, lines: Mapping[str, Line]) -> None:
        self._lines = lines
        self._blocks = {name: {b.block_id for b in line.blocks}
                        for name, line in lines.items()}
        self._switches = {name: set(line.switch_ids())
                          for name, line in lines.items()}
        self._crossings = {name: set(line.crossing_ids())
                           for name, line in lines.items()}

    def _line(self, line: str, what: str) -> None:
        _require_id(line, f"line of {what}")
        if line not in self._lines:
            known = ", ".join(sorted(self._lines))
            raise InvalidInputError(
                f"{what}: unknown line {line!r} (known: {known})")

    def block(self, line: str, block_id: str, what: str) -> None:
        self._line(line, what)
        _require_id(block_id, f"block of {what}")
        if block_id not in self._blocks[line]:
            raise InvalidInputError(
                f"{what}: {line} has no block {block_id!r}")

    def switch(self, line: str, switch_id: str, what: str) -> None:
        self._line(line, what)
        _require_id(switch_id, f"switch of {what}")
        if switch_id not in self._switches[line]:
            raise InvalidInputError(
                f"{what}: {line} has no switch at block {switch_id!r}")

    def crossing(self, line: str, crossing_id: str, what: str) -> None:
        self._line(line, what)
        _require_id(crossing_id, f"crossing of {what}")
        if crossing_id not in self._crossings[line]:
            raise InvalidInputError(
                f"{what}: {line} has no crossing at block "
                f"{crossing_id!r}")

    def validate_inputs(self, inputs: CtcInputs) -> None:
        """Raise ``InvalidInputError`` if any input is malformed."""
        track_controller = inputs.track_controller
        for block in track_controller.occupancy:
            self.block(block.line, block.block_id, "occupancy")
        for train in track_controller.trains:
            _require_id(train.train_id, "train_id")
            what = f"train {train.train_id}"
            self.block(train.line, train.block_id, what)
            _require_finite(train.offset_m, f"offset_m of {what}")
            _require_finite(train.speed_mps, f"speed_mps of {what}")
        for switch in track_controller.switches:
            self.switch(switch.line, switch.switch_id, "switch state")
        for crossing in track_controller.crossings:
            self.crossing(crossing.line, crossing.crossing_id,
                          "crossing state")
        for failure in track_controller.failures:
            self.block(failure.line, failure.block_id, "track failure")
        lines_sold = set()
        for sale in inputs.track_model.ticket_sales:
            self._line(sale.line, "ticket sales")
            if sale.line in lines_sold:
                raise InvalidInputError(
                    f"ticket sales: {sale.line} is listed twice")
            lines_sold.add(sale.line)
            if (isinstance(sale.tickets, bool)
                    or not isinstance(sale.tickets, int)
                    or sale.tickets < 0):
                raise InvalidInputError(
                    f"ticket sales on {sale.line} must be a whole number "
                    f">= 0, got {sale.tickets!r}")


class StubCtcOffice:
    """A ``CtcOffice`` with dispatcher pass-through and no routing."""

    def __init__(
        self, suggested_speed_mps: int = STUB_SUGGESTED_SPEED_MPS,
        layout: Mapping[str, Line] | None = None,
    ) -> None:
        if (isinstance(suggested_speed_mps, bool)
                or not isinstance(suggested_speed_mps, int)
                or suggested_speed_mps < 0):
            raise InvalidInputError(
                "suggested_speed_mps must be a whole number of m/s >= 0, "
                f"got {suggested_speed_mps!r}")
        self._suggested_speed_mps = suggested_speed_mps
        lines = load_layout() if layout is None else layout
        self._layout = _Layout(lines)
        self._lines = tuple(sorted(lines))
        self._orders: dict[str, DispatchOrder] = {}
        self._closed: set[BlockRef] = set()
        self._switches: dict[tuple[str, str], SwitchPosition] = {}
        self._maintenance = False
        self._clock_speedup = False
        self._inputs: CtcInputs | None = None
        self._elapsed_s = 0.0
        self._tickets: dict[str, int] = {name: 0 for name in self._lines}
        self._schedule: Schedule | None = None

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        """Advance one tick; see ``CtcOffice.step``."""
        if not (isinstance(dt, (int, float)) and math.isfinite(dt)
                and dt > 0):
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {dt!r}")
        self._layout.validate_inputs(inputs)

        self._inputs = inputs
        self._elapsed_s += dt
        for sale in inputs.track_model.ticket_sales:
            self._tickets[sale.line] += sale.tickets
        return self._outputs()

    def validate_inputs(self, inputs: CtcInputs) -> None:
        """Raise ``InvalidInputError`` if any input is malformed."""
        self._layout.validate_inputs(inputs)

    def snapshot(self) -> CtcSnapshot:
        """Current state for display. No side effects."""
        return CtcSnapshot(
            outputs=self._outputs(),
            inputs=self._inputs,
            elapsed_s=self._elapsed_s,
            tickets_sold=tuple(TicketSales(line, tickets)
                               for line, tickets in self._tickets.items()),
            queued_trains=self._queued(),
            orders=tuple(self._orders[t] for t in sorted(self._orders)),
        )

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        """Send a train toward a block; replaces any earlier order."""
        _require_id(train_id, "train_id")
        self._layout.block(line, destination_block_id,
                           f"destination of {train_id}")
        if arrival_s is not None:
            _require_finite(arrival_s, "arrival_s")
            if not 0 <= arrival_s < _DAY_S:
                raise InvalidInputError(
                    f"arrival_s must be within one day, got {arrival_s}")
        self._orders[train_id] = DispatchOrder(
            train_id, line, destination_block_id, arrival_s)

    def cancel_dispatch(self, train_id: str) -> None:
        """Drop a train's dispatch order, if it has one."""
        self._orders.pop(train_id, None)

    def set_block_closed(self, line: str, block_id: str,
                         closed: bool) -> None:
        """Close a block for maintenance, or reopen it."""
        self._layout.block(line, block_id, "block closure")
        if closed:
            self._closed.add(BlockRef(line, block_id))
        else:
            self._closed.discard(BlockRef(line, block_id))

    def set_switch(self, line: str, switch_id: str,
                   position: SwitchPosition) -> None:
        """Command a switch position. Only in maintenance mode."""
        self._layout.switch(line, switch_id, "switch command")
        if position not in get_args(SwitchPosition):
            raise InvalidInputError(
                f"switch position must be normal or reverse, "
                f"got {position!r}")
        if not self._maintenance:
            raise MaintenanceModeRequiredError(
                "Switches can be set only in maintenance mode.")
        self._switches[(line, switch_id)] = position

    def release_switch(self, line: str, switch_id: str) -> None:
        """Drop the command for one switch, if there is one."""
        self._switches.pop((line, switch_id), None)

    def set_maintenance_mode(self, active: bool) -> None:
        """Enter or leave maintenance mode; leaving drops every switch
        command, handing the switches back to the Track Controller."""
        self._maintenance = bool(active)
        if not self._maintenance:
            self._switches.clear()

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
            TrainSuggestion(order.train_id, order.line,
                            self._suggested_speed_mps,
                            order.destination_block_id)
            for _, order in sorted(self._orders.items())
        )
        return CtcOutputs(
            track_controller=TrackControllerOutputs(
                suggestions=suggestions,
                closed_blocks=tuple(sorted(
                    self._closed, key=_block_order)),
                switch_commands=tuple(
                    SwitchCommand(line, switch_id, position)
                    for (line, switch_id), position in sorted(
                        self._switches.items(),
                        key=lambda item: _id_order(*item[0]))),
                maintenance_mode=self._maintenance,
            ),
            clock_speedup=self._clock_speedup,
        )


def _id_order(line: str, block_id: str) -> tuple[str, int, str]:
    # Line, then block number as a number where it is one, for display.
    number = int(block_id) if block_id.isdigit() else -1
    return (line, number, block_id)


def _block_order(block: BlockRef) -> tuple[str, int, str]:
    return _id_order(block.line, block.block_id)
