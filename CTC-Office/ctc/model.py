"""Stub CTC Office: satisfies the contract with no routing logic yet.

The stub turns dispatcher actions straight into outputs so data can be
seen crossing the boundary: each dispatched train on the track gets its
destination as authority and a suggested speed a little under its
current block's speed limit, and closed blocks,
switch commands and maintenance mode pass through. Track Controller and
Track Model inputs are validated against the track layout and recorded;
apart from the safety rules (``StubCtcOffice``) they drive nothing yet.
Real logic replaces this class behind the same ``CtcOffice`` contract.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Mapping, get_args

from ctc.interface import (
    BlockRef,
    CancelledOrder,
    CrossingState,
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    DispatchOrder,
    QueuedTrain,
    SwitchCommand,
    SwitchPosition,
    TicketSales,
    TrackFailureKind,
    TrainSuggestion,
    TrackControllerOutputs,
)
from ctc.track_layout import Line, load_layout

if TYPE_CHECKING:
    from ctc.schedule import Schedule

#: How far below the current block's speed limit the suggested speed
#: is, in m/s (asserted by Landis 2026-10-06; it will be adjusted on the
#: fly once several trains share the track).
SUGGESTED_SPEED_MARGIN_MPS = 1

_KMH_PER_MPS = 3.6

_DAY_S = 24 * 60 * 60


class CtcError(Exception):
    """Base class for every CTC Office error."""


class InvalidTimeStepError(CtcError):
    """dt was not finite and positive."""


class InvalidInputError(CtcError):
    """An input or dispatcher action failed validation."""


class MaintenanceModeRequiredError(CtcError):
    """A switch or block closure was commanded outside maintenance
    mode."""


class UnsafeActionError(CtcError):
    """A dispatcher action was refused by a safety rule."""


def _require_id(value: str, what: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{what} must be a non-empty string ID")


def _require_finite(value: float, what: str) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise InvalidInputError(
            f"{what} must be a finite number, got {value!r}")


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
        self._lengths = {(name, b.block_id): b.length_m
                         for name, line in lines.items()
                         for b in line.blocks}
        self.speed_limits_kmh = {(name, b.block_id): b.speed_limit_kmh
                                 for name, line in lines.items()
                                 for b in line.blocks}

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
        """Raise ``InvalidInputError`` if any input is malformed.

        A report may repeat itself, but not contradict itself: the same
        switch reported both normal and reverse in one update is
        rejected.
        """
        track_controller = inputs.track_controller
        occupied: dict[tuple[str, str], bool] = {}
        for block in track_controller.occupancy:
            self.block(block.line, block.block_id, "occupancy")
            if not isinstance(block.occupied, bool):
                raise InvalidInputError(
                    f"occupancy of {block.line} {block.block_id} must be "
                    f"true or false, got {block.occupied!r}")
            _no_conflict(occupied, (block.line, block.block_id),
                         block.occupied,
                         f"occupancy of {block.line} {block.block_id}")
        # Safety: one train per block, so trains cannot collide. Two
        # trains reported in one block is rejected, never applied.
        in_block: dict[tuple[str, str], str] = {}
        for train in track_controller.trains:
            _require_id(train.train_id, "train_id")
            what = f"train {train.train_id}"
            self.block(train.line, train.block_id, what)
            _require_finite(train.offset_m, f"offset_m of {what}")
            _require_finite(train.speed_mps, f"speed_mps of {what}")
            if train.speed_mps < 0:
                raise InvalidInputError(
                    f"{what}: speed cannot be negative, got "
                    f"{train.speed_mps:g} m/s")
            length = self._lengths[(train.line, train.block_id)]
            if not 0 <= train.offset_m <= length:
                raise InvalidInputError(
                    f"{what}: offset {train.offset_m:g} m is outside "
                    f"{train.line} block {train.block_id} "
                    f"(0 to {length:g} m)")
            if train.train_id in in_block.values():
                raise InvalidInputError(
                    f"train {train.train_id} is reported twice")
            other = in_block.setdefault((train.line, train.block_id),
                                        train.train_id)
            if other != train.train_id:
                raise InvalidInputError(
                    f"trains {other} and {train.train_id} are both in "
                    f"{train.line} block {train.block_id}; two trains "
                    "cannot occupy one block")
        positions: dict[tuple[str, str], str] = {}
        for switch in track_controller.switches:
            self.switch(switch.line, switch.switch_id, "switch state")
            _require_choice(switch.position, SwitchPosition,
                            f"position of {switch.line} switch "
                            f"{switch.switch_id}")
            _no_conflict(positions, (switch.line, switch.switch_id),
                         switch.position,
                         f"{switch.line} switch {switch.switch_id}")
        states: dict[tuple[str, str], str] = {}
        for crossing in track_controller.crossings:
            self.crossing(crossing.line, crossing.crossing_id,
                          "crossing state")
            _require_choice(crossing.state, CrossingState,
                            f"state of {crossing.line} crossing "
                            f"{crossing.crossing_id}")
            _no_conflict(states, (crossing.line, crossing.crossing_id),
                         crossing.state,
                         f"{crossing.line} crossing {crossing.crossing_id}")
        kinds: dict[tuple[str, str], str] = {}
        for failure in track_controller.failures:
            self.block(failure.line, failure.block_id, "track failure")
            _require_choice(failure.kind, TrackFailureKind,
                            f"failure on {failure.line} block "
                            f"{failure.block_id}")
            _no_conflict(kinds, (failure.line, failure.block_id),
                         failure.kind,
                         f"failure on {failure.line} block "
                         f"{failure.block_id}")
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


def _require_choice(value: object, choices: object, what: str) -> None:
    allowed = get_args(choices)
    if value not in allowed:
        raise InvalidInputError(
            f"{what} must be one of {', '.join(allowed)}, got {value!r}")


def _no_conflict(seen: dict[Any, Any], key: Any, value: Any,
                 what: str) -> None:
    """Allow a repeated report, but not a contradictory one."""
    if seen.setdefault(key, value) != value:
        raise InvalidInputError(
            f"{what} is reported as both {seen[key]!r} and {value!r}")


def _normalize(inputs: CtcInputs) -> CtcInputs:
    """Train IDs with stray spaces are the same train: trim them."""
    trains = inputs.track_controller.trains
    if all(not isinstance(t.train_id, str)
           or t.train_id == t.train_id.strip() for t in trains):
        return inputs
    trimmed = tuple(
        replace(t, train_id=t.train_id.strip())
        if isinstance(t.train_id, str) else t for t in trains)
    return replace(inputs, track_controller=replace(
        inputs.track_controller, trains=trimmed))


def _trim(train_id: str) -> str:
    _require_id(train_id, "train_id")
    return train_id.strip()


#: How many self-cancelled orders the snapshot keeps.
_CANCELLED_KEPT = 20


class StubCtcOffice:
    """A ``CtcOffice`` with dispatcher pass-through and no routing.

    It does enforce the safety rules: no authority into a closed,
    closing or failed block or onto another line than the train's; no
    switch thrown under a train; one train per block. Block closures
    are maintenance-mode only and wait for an occupied block to clear.
    """

    def __init__(self, layout: Mapping[str, Line] | None = None) -> None:
        lines = load_layout() if layout is None else layout
        self._layout = _Layout(lines)
        self._lines = tuple(sorted(lines))
        self._orders: dict[str, DispatchOrder] = {}
        self._closed: set[BlockRef] = set()
        # Closures waiting for their (occupied) block to clear.
        self._pending: set[BlockRef] = set()
        self._cancelled: list[CancelledOrder] = []
        self._switches: dict[tuple[str, str], SwitchPosition] = {}
        self._maintenance = False
        self._clock_speedup = False
        self._inputs: CtcInputs | None = None
        # Reports received while no time passes; applied at next step.
        self._staged: CtcInputs | None = None
        self._elapsed_s = 0.0
        self._tickets: dict[str, int] = {name: 0 for name in self._lines}
        self._schedule: Schedule | None = None

    # -- Stepping -----------------------------------------------------

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        """Advance one tick; see ``CtcOffice.step``."""
        if (isinstance(dt, bool) or not isinstance(dt, (int, float))
                or not math.isfinite(dt) or dt <= 0):
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {dt!r}")
        inputs = _normalize(inputs)
        self._layout.validate_inputs(inputs)

        self._inputs = inputs
        self._staged = None
        self._elapsed_s += dt
        for sale in inputs.track_model.ticket_sales:
            self._tickets[sale.line] += sale.tickets
        # A failure now reported cancels orders into that block.
        for failure in inputs.track_controller.failures:
            self._cancel_orders_into(
                BlockRef(failure.line, failure.block_id),
                f"track failure: {failure.kind.replace('_', ' ')}")
        # Pending closures close once their block is clear.
        occupied = self._occupied(inputs)
        for block in sorted(self._pending, key=_block_order):
            if (block.line, block.block_id) not in occupied:
                self._pending.discard(block)
                self._closed.add(block)
        return self._outputs()

    def validate_inputs(self, inputs: CtcInputs) -> None:
        """Raise ``InvalidInputError`` if any input is malformed."""
        self._layout.validate_inputs(_normalize(inputs))

    def stage_inputs(self, inputs: CtcInputs) -> None:
        """See ``CtcOffice.stage_inputs``."""
        inputs = _normalize(inputs)
        self._layout.validate_inputs(inputs)
        self._staged = inputs

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
            pending_closures=tuple(sorted(self._pending,
                                          key=_block_order)),
            cancelled_orders=tuple(self._cancelled),
            inputs_staged=self._staged is not None,
        )

    # -- Dispatcher actions -------------------------------------------

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        """Send a train toward a block; replaces any earlier order.

        Refused (safety) into a closed, closing or failed block, and
        onto a line other than the one the train is reported on.
        """
        train_id = _trim(train_id)
        self._layout.block(line, destination_block_id,
                           f"destination of {train_id}")
        if arrival_s is not None:
            if isinstance(arrival_s, bool):
                raise InvalidInputError("arrival_s must be a number")
            _require_finite(arrival_s, "arrival_s")
            if not 0 <= arrival_s < _DAY_S:
                raise InvalidInputError(
                    f"arrival_s must be within one day, got {arrival_s}")
        target = BlockRef(line, destination_block_id)
        where = f"{line} block {destination_block_id}"
        if target in self._closed:
            raise UnsafeActionError(
                f"{where} is closed; no train can be sent into it.")
        if target in self._pending:
            raise UnsafeActionError(
                f"{where} is closing; no train can be sent into it.")
        failure = self._failures().get((line, destination_block_id))
        if failure is not None:
            raise UnsafeActionError(
                f"{where} has a track failure "
                f"({failure.replace('_', ' ')}); no train can be sent "
                "into it.")
        reported = self._train_lines().get(train_id)
        if reported is not None and reported != line:
            raise UnsafeActionError(
                f"{train_id} is on the {reported} line; it cannot be sent "
                f"to a {line} block.")
        self._orders[train_id] = DispatchOrder(
            train_id, line, destination_block_id, arrival_s)

    def cancel_dispatch(self, train_id: str) -> None:
        """Drop a train's dispatch order, if it has one."""
        self._orders.pop(_trim(train_id), None)

    def set_block_closed(self, line: str, block_id: str,
                         closed: bool) -> None:
        """Close or reopen a block; see ``CtcOffice.set_block_closed``."""
        self._layout.block(line, block_id, "block closure")
        if not isinstance(closed, bool):
            raise InvalidInputError(
                f"closed must be true or false, got {closed!r}")
        if not self._maintenance:
            raise MaintenanceModeRequiredError(
                "Blocks can be closed or reopened only in maintenance "
                "mode.")
        block = BlockRef(line, block_id)
        if not closed:
            self._closed.discard(block)
            self._pending.discard(block)
            return
        if block in self._closed:
            return
        if (line, block_id) in self._occupied(self._newest()):
            self._pending.add(block)
            self._cancel_orders_into(block, "block closing")
        else:
            self._pending.discard(block)
            self._closed.add(block)
            self._cancel_orders_into(block, "block closed")

    def set_switch(self, line: str, switch_id: str,
                   position: SwitchPosition) -> None:
        """Command a switch; see ``CtcOffice.set_switch``."""
        self._layout.switch(line, switch_id, "switch command")
        if position not in get_args(SwitchPosition):
            raise InvalidInputError(
                f"switch position must be normal or reverse, "
                f"got {position!r}")
        if not self._maintenance:
            raise MaintenanceModeRequiredError(
                "Switches can be set only in maintenance mode.")
        if (line, switch_id) in self._occupied(self._newest()):
            raise UnsafeActionError(
                f"{line} block {switch_id} is occupied; its switch cannot "
                "be moved under a train.")
        self._switches[(line, switch_id)] = position

    def release_switch(self, line: str, switch_id: str) -> None:
        """Drop the command for one switch, if there is one."""
        self._switches.pop((line, switch_id), None)

    def set_maintenance_mode(self, active: bool) -> None:
        """Enter or leave maintenance mode. Leaving drops every switch
        command, handing the switches back to the Track Controller;
        closed blocks stay closed and pending closures still close."""
        if not isinstance(active, bool):
            raise InvalidInputError(
                f"maintenance mode must be true or false, got {active!r}")
        self._maintenance = active
        if not self._maintenance:
            self._switches.clear()

    def set_clock_speedup(self, active: bool) -> None:
        if not isinstance(active, bool):
            raise InvalidInputError(
                f"clock speedup must be true or false, got {active!r}")
        self._clock_speedup = active

    def load_schedule(self, schedule: Schedule) -> None:
        """Replace the schedule. Every stop must be a block of the
        track layout. With no scheduling algorithm yet, every run stays
        queued."""
        for train in schedule.trains:
            for stop in train.stops:
                self._layout.block(train.line, stop.block_id,
                                   f"schedule {train.line} train "
                                   f"{train.train_id}")
        self._schedule = schedule

    # -- Internals ----------------------------------------------------

    def _newest(self) -> CtcInputs:
        """The newest reports: staged ones if any, else the applied."""
        if self._staged is not None:
            return self._staged
        return self._inputs if self._inputs is not None else CtcInputs()

    @staticmethod
    def _occupied(inputs: CtcInputs) -> set[tuple[str, str]]:
        track = inputs.track_controller
        blocks = {(t.line, t.block_id) for t in track.trains}
        blocks |= {(o.line, o.block_id) for o in track.occupancy
                   if o.occupied}
        return blocks

    def _failures(self) -> dict[tuple[str, str], str]:
        return {(f.line, f.block_id): f.kind
                for f in self._newest().track_controller.failures}

    def _train_lines(self) -> dict[str, str]:
        return {t.train_id: t.line
                for t in self._newest().track_controller.trains}

    def _cancel_orders_into(self, block: BlockRef, reason: str) -> None:
        for train_id, order in sorted(self._orders.items()):
            if (order.line, order.destination_block_id) == (
                    block.line, block.block_id):
                del self._orders[train_id]
                self._cancelled.append(CancelledOrder(
                    train_id, block.line, block.block_id, reason))
        del self._cancelled[:-_CANCELLED_KEPT]

    def _queued(self) -> tuple[QueuedTrain, ...]:
        if self._schedule is None:
            return ()
        runs = sorted(self._schedule.trains,
                      key=lambda t: (t.departure_s, t.line, t.train_id))
        return tuple(
            QueuedTrain(t.line, t.train_id, t.departure_s,
                        t.stops[0].block_id)
            for t in runs)

    def _suggested_speed_mps(self, line: str, block_id: str) -> int:
        """A little under the block's speed limit: the limit in whole
        m/s (rounded down) less ``SUGGESTED_SPEED_MARGIN_MPS``."""
        limit_kmh = self._layout.speed_limits_kmh[(line, block_id)]
        return max(0, int(limit_kmh / _KMH_PER_MPS)
                   - SUGGESTED_SPEED_MARGIN_MPS)

    def _outputs(self) -> CtcOutputs:
        # The yard is a black box: a train gets speed and authority once
        # it is reported on the track, from the block it is in then.
        applied = self._inputs if self._inputs is not None else CtcInputs()
        positions = {t.train_id: (t.line, t.block_id)
                     for t in applied.track_controller.trains}
        suggestions = tuple(
            TrainSuggestion(order.train_id, order.line,
                            self._suggested_speed_mps(
                                *positions[order.train_id]),
                            order.destination_block_id)
            for _, order in sorted(self._orders.items())
            if order.train_id in positions
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
