"""Stub CTC Office: satisfies the contract with no scheduling logic yet.

The stub turns dispatcher actions straight into outputs so data can be
seen crossing the boundary. The Track Controller reports only block
occupancy, so the stub follows its own trains from it and infers which
occupied blocks are failures (``ctc.tracking``). Each dispatched train it
is following gets a suggested speed a little under its current block's
speed limit, and an authority counted in blocks toward its destination
that stops short of any occupied, closed, closing or failed block and of
any switch not reported set for its route (``ctc.routing``), recomputed
every step.
The blocks closed in maintenance mode (closing ones included) and
switch commands pass through. Nothing is sent to a line's Track
Controller, and no train is dispatched on the line, until it reports
the line ready (a PLC program on every wayside): its waysides are
vital. Track
Controller and Track Model inputs are validated against the track
layout and recorded. Real logic replaces this class behind the same
``CtcOffice`` contract.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Collection, Mapping, get_args

from ctc.interface import (
    BlockOccupancy,
    BlockRef,
    CancelledOrder,
    CrossingReport,
    CrossingState,
    CtcInputs,
    CtcOutputs,
    CtcSnapshot,
    DispatchOrder,
    ScheduledRun,
    SwitchCommand,
    SwitchPosition,
    SwitchReport,
    TrackControllerInputs,
    TrackedTrain,
    TrackModelInputs,
    TrainAuthority,
    TrainSuggestion,
    TrackControllerOutputs,
    WaysideStatus,
)
from ctc.routing import (
    authority,
    build_graphs,
    first_reversal,
    reversing_route,
)
from ctc.track_layout import Line, load_layout, station_lines
from ctc.scheduler import (
    SIMULATION_START_S,
    AutoDispatcher,
    Cancel,
    World,
    plan_run,
    train_id_for,
)
from ctc.tracking import YARD_EXITS, Plan, TrainTracker, Waiting

if TYPE_CHECKING:
    from ctc.schedule import Schedule

#: Service deceleration the suggested speed lets a train stop at
#: within its authority, in m/s^2 (``truth/modules/train-model.md``:
#: 1.2 m/s^2 at 2/3 load; ``suggested-speed-stops-within-authority``,
#: proposed on ``ctc-interfacing``).
SERVICE_DECEL_MPS2 = 1.2

#: A route around an unusable block or a train that is not moving is
#: taken only if it is at most this many times as long as the shortest
#: route; otherwise the train waits.
MAX_DETOUR_FACTOR = 2

#: How far below the current block's speed limit the suggested speed
#: is, in m/s (asserted by Landis 2026-10-06; it will be adjusted on the
#: fly once several trains share the track).
SUGGESTED_SPEED_MARGIN_MPS = 1

_KMH_PER_MPS = 3.6

#: Longest train ID accepted, in characters.
MAX_TRAIN_ID_LENGTH = 32

#: Most tickets one report may carry: QML integers are 32-bit.
MAX_TICKETS = 2**31 - 1

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


def _is_finite_number(value: object) -> bool:
    """A real int or float, finite. An int too big for a float (10**400)
    is not: ``math.isfinite`` would raise ``OverflowError`` on it."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _require_finite(value: float, what: str) -> None:
    if not _is_finite_number(value):
        raise InvalidInputError(
            f"{what} must be a finite number, got {_short(value)}")


def _short(value: object) -> str:
    """``repr`` cut down, so a huge value does not flood a message."""
    text = repr(value)
    return text if len(text) <= 40 else text[:37] + "..."


def _require_train_id(value: str, what: str = "train_id") -> None:
    """A train ID: a non-empty string, no control characters (no
    newlines or NULs), at most ``MAX_TRAIN_ID_LENGTH`` characters once
    trimmed."""
    _require_id(value, what)
    text = value.strip()
    if len(text) > MAX_TRAIN_ID_LENGTH:
        raise InvalidInputError(
            f"{what} must be at most {MAX_TRAIN_ID_LENGTH} characters, "
            f"got {len(text)}")
    if not text.isprintable():
        raise InvalidInputError(
            f"{what} must not contain control characters, got "
            f"{_short(text)}")


#: The list fields of the inputs, and what each holds.
_INPUT_LISTS = (
    ("track_controller", "occupancy", BlockOccupancy),
    ("track_controller", "switches", SwitchReport),
    ("track_controller", "crossings", CrossingReport),
    ("track_controller", "waysides", WaysideStatus),
)


def _require_shape(inputs: object) -> None:
    """The inputs are the boundary types, each list a list or tuple of
    the right entries: anything else is rejected before it is read."""
    if not isinstance(inputs, CtcInputs):
        raise InvalidInputError(
            f"inputs must be CtcInputs, got {type(inputs).__name__}")
    for name, kind in (("track_controller", TrackControllerInputs),
                       ("track_model", TrackModelInputs)):
        part = getattr(inputs, name)
        if not isinstance(part, kind):
            raise InvalidInputError(
                f"{name} must be {kind.__name__}, got "
                f"{type(part).__name__}")
    for part, field, kind in _INPUT_LISTS:
        items = getattr(getattr(inputs, part), field)
        if not isinstance(items, (tuple, list)):
            raise InvalidInputError(
                f"{field} must be a list, got {type(items).__name__}")
        for item in items:
            if not isinstance(item, kind):
                raise InvalidInputError(
                    f"every entry of {field} must be a {kind.__name__}, "
                    f"got {type(item).__name__}")
    sales = inputs.track_model.ticket_sales
    if not isinstance(sales, Mapping):
        raise InvalidInputError(
            "ticket_sales must map station names to tickets, got "
            f"{type(sales).__name__}")


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
        self.lengths_m = self._lengths
        # Each named station's line, by station name.
        self.station_lines = station_lines(dict(lines))
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
        startup: dict[tuple[str, str], tuple[bool, str]] = {}
        for status in track_controller.waysides:
            self._line(status.line, "wayside report")
            _require_id(status.wayside_id, "wayside ID")
            if not isinstance(status.ready, bool):
                raise InvalidInputError(
                    f"ready of {status.line} wayside {status.wayside_id} "
                    f"must be true or false, got {status.ready!r}")
            if not isinstance(status.reason, str):
                raise InvalidInputError(
                    f"reason of {status.line} wayside {status.wayside_id} "
                    f"must be text, got {_short(status.reason)}")
            _no_conflict(startup, (status.line, status.wayside_id),
                         (status.ready, status.reason),
                         f"{status.line} wayside {status.wayside_id}")
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
        for station, tickets in inputs.track_model.ticket_sales.items():
            if (not isinstance(station, str)
                    or station not in self.station_lines):
                raise InvalidInputError(
                    f"ticket sales: no station is named {_short(station)}")
            if (isinstance(tickets, bool) or not isinstance(tickets, int)
                    or not 0 <= tickets <= MAX_TICKETS):
                raise InvalidInputError(
                    f"ticket sales at {station} must be a whole number "
                    f"from 0 to {MAX_TICKETS}, got {_short(tickets)}")


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
    """Check the inputs' shape and make every list a tuple."""
    _require_shape(inputs)
    # A copy, so a later change to the caller's dict changes nothing here.
    inputs = replace(inputs, track_model=replace(
        inputs.track_model,
        ticket_sales=dict(inputs.track_model.ticket_sales)))
    for part, field, _ in _INPUT_LISTS:
        owner = getattr(inputs, part)
        items = getattr(owner, field)
        if isinstance(items, list):
            inputs = replace(inputs, **{part: replace(
                owner, **{field: tuple(items)})})
    return inputs


def ready_lines(waysides: Collection[WaysideStatus]) -> frozenset[str]:
    """The lines on which a wayside has reported and every wayside
    reported is ready."""
    reported = {status.line for status in waysides}
    held = {status.line for status in waysides if not status.ready}
    return frozenset(reported - held)


def _not_ready(inputs: CtcInputs, line: str) -> str:
    """Why a line is not ready, for a message."""
    waiting = [s for s in inputs.track_controller.waysides
               if s.line == line and not s.ready]
    if not waiting:
        return "no wayside has reported"
    return "; ".join(f"wayside {s.wayside_id}: {s.reason or 'not ready'}"
                     for s in waiting)


def _trim(train_id: str) -> str:
    _require_train_id(train_id)
    return train_id.strip()


#: How many self-cancelled orders the snapshot keeps.
_CANCELLED_KEPT = 20


class StubCtcOffice:
    """A ``CtcOffice`` with dispatcher pass-through and no scheduling.

    It does enforce the safety rules: no authority into a closed,
    closing or failed block or onto another line than the train's;
    authority stops short of every such block, of occupied blocks and
    of switches not set for the route; no switch thrown under a train.
    Block closures are maintenance-mode only and wait for an occupied
    block to clear. Failed blocks are inferred from occupancy
    (``ctc.tracking``) and shown to the UIs only as occupied. Nothing is
    sent to a line's Track Controller until it reports the line ready,
    and no train is dispatched on it: closures and switch commands are
    kept and go out once it is.
    """

    def __init__(self, layout: Mapping[str, Line] | None = None) -> None:
        lines = load_layout() if layout is None else layout
        self._layout = _Layout(lines)
        self._graphs = build_graphs(lines)
        # Blocks the layout marks as stations, named or not, per line.
        self._station_blocks = {
            name: frozenset(b.block_id for b in line.blocks
                            if b.station is not None)
            for name, line in lines.items()}
        self._lines = tuple(sorted(lines))
        self._orders: dict[str, DispatchOrder] = {}
        self._closed: set[BlockRef] = set()
        # Closures waiting for their (occupied) block to clear.
        self._pending: set[BlockRef] = set()
        self._cancelled: list[CancelledOrder] = []
        self._switches: dict[tuple[str, str], SwitchPosition] = {}
        # Blocks within each train's authority as of the last step: kept
        # until the train has passed through them (exclusive-authority).
        self._granted: dict[str, tuple[str, ...]] = {}
        # The last authorities computed, and the state they came from.
        self._authority_cache: tuple[Any, tuple[TrainAuthority, ...]] | None
        self._authority_cache = None
        self._maintenance = False
        self._clock_speedup = False
        # The simulation starts paused, until the dispatcher runs it.
        self._clock_paused = True
        self._inputs: CtcInputs | None = None
        # Reports received while no time passes; applied at next step.
        self._staged: CtcInputs | None = None
        self._elapsed_s = 0.0
        # Tickets sold at each named station since the start.
        self._tickets: dict[str, int] = {
            station: 0 for station in self._layout.station_lines}
        self._schedule: Schedule | None = None
        # The loaded schedule's plans and progress (ctc.scheduler).
        self._auto: AutoDispatcher | None = None
        self._automatic = False
        self._dispatch_paused = False
        # Where the trains are and which blocks failed, from occupancy.
        self._tracker = TrainTracker(SERVICE_DECEL_MPS2)
        # What each tracked train should do next, from the last step.
        self._plans: dict[str, Plan] = {}

    # -- Stepping -----------------------------------------------------

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        """Advance one tick; see ``CtcOffice.step``."""
        if not _is_finite_number(dt) or dt <= 0:
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {_short(dt)}")
        if not math.isfinite(self._elapsed_s + dt):
            raise InvalidTimeStepError(
                f"dt {dt:g} s would take the elapsed time past what can "
                "be counted")
        inputs = _normalize(inputs)
        self._layout.validate_inputs(inputs)

        self._elapsed_s += dt
        # Follow the trains (and infer failures) from the new occupancy,
        # against the last step's plans.
        self._tracker.update(frozenset(self._occupied(inputs)),
                             self._elapsed_s, self._plans, self._waiting())
        self._inputs = inputs
        self._staged = None
        for station, tickets in inputs.track_model.ticket_sales.items():
            self._tickets[station] += tickets
        # In automatic mode, the schedule's runs move on.
        self._run_schedule()
        # Pending closures close once their block is clear.
        occupied = self._occupied(inputs)
        for block in sorted(self._pending, key=_block_order):
            if (block.line, block.block_id) not in occupied:
                self._pending.discard(block)
                self._closed.add(block)
        # Commit this step's grants; later steps keep them. Nothing is
        # granted on a line whose Track Controller is not ready.
        ready = self._ready_lines()
        self._granted = {a.train_id: a.route[1:a.blocks + 1]
                         for a in self._authorities() if a.line in ready}
        self._plans = self._make_plans()
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
            tickets_sold=dict(self._tickets),
            scheduled_runs=self._scheduled_runs(),
            orders=tuple(self._orders[t] for t in sorted(self._orders)),
            pending_closures=tuple(sorted(self._pending,
                                          key=_block_order)),
            closed_blocks=self._closed_blocks(),
            switch_commands=self._switch_commands(),
            cancelled_orders=tuple(self._cancelled),
            authorities=self._authorities(),
            inputs_staged=self._staged is not None,
            maintenance_mode=self._maintenance,
            automatic_mode=self._automatic,
            dispatch_paused=self._dispatch_paused,
            trains=tuple(TrackedTrain(train_id, t.line, t.blocks)
                         for train_id, t in sorted(
                             self._tracker.trains.items())),
            lost_trains=tuple(sorted(self._tracker.lost)),
        )

    def place_train(self, train_id: str, line: str, block_id: str) -> None:
        """Start following a train at a block, standing at its start.
        For tests and for seeding a scenario: in operation a train is
        found by leaving the yard (``ctc.tracking``)."""
        train_id = _trim(train_id)
        self._layout.block(line, block_id, f"position of {train_id}")
        self._tracker.place(train_id, line, block_id)

    # -- Dispatcher actions -------------------------------------------

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        """Send a train toward a block; replaces any earlier order.

        Refused (safety) into a closed or closing block, onto a line
        other than the one the train is on, and on a line whose Track
        Controller is not ready (no PLC program loaded). A block inferred
        to have failed is not refused: the UIs never show a failure, and
        the train waits short of it until it clears.
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
        if line not in self._ready_lines(self._newest()):
            raise UnsafeActionError(
                f"The {line} line's Track Controller is not ready "
                f"({_not_ready(self._newest(), line)}); no train can be "
                "dispatched on it yet.")
        if target in self._closed:
            raise UnsafeActionError(
                f"{where} is closed; no train can be sent into it.")
        if target in self._pending:
            raise UnsafeActionError(
                f"{where} is closing; no train can be sent into it.")
        reported = self._train_lines().get(train_id)
        if reported is not None and reported != line:
            raise UnsafeActionError(
                f"{train_id} is on the {reported} line; it cannot be sent "
                f"to a {line} block.")
        self._orders[train_id] = DispatchOrder(
            train_id, line, destination_block_id, arrival_s)

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

    def set_clock_paused(self, paused: bool) -> None:
        """Command the shared clock to pause or resume; see
        ``CtcOffice.set_clock_paused``."""
        if not isinstance(paused, bool):
            raise InvalidInputError(
                f"clock paused must be true or false, got {paused!r}")
        self._clock_paused = paused

    def load_schedule(self, schedule: Schedule) -> None:
        """Replace the schedule. Every stop must be a block of the
        track layout. Each run is planned at once (``ctc.scheduler``):
        its scheduled stations, and no others, in track order from the
        yard, each with the time it is due there. In automatic mode the
        runs then dispatch themselves. Orders already given stay."""
        runs = set()
        for train in schedule.trains:
            what = f"schedule {train.line} train {train.train_id}"
            if not train.stops:
                raise InvalidInputError(f"{what}: no stops")
            if (train.line, train.train_id) in runs:
                raise InvalidInputError(f"{what} is listed twice")
            runs.add((train.line, train.train_id))
            for stop in train.stops:
                self._layout.block(train.line, stop.block_id,
                                   f"schedule {train.line} train "
                                   f"{train.train_id}")
        train_ids = [train_id_for(t.line, t.train_id)
                     for t in schedule.trains]
        for train_id in train_ids:
            if train_ids.count(train_id) > 1:
                raise InvalidInputError(
                    f"schedule: two runs would both be train {train_id}")
            _require_train_id(train_id, "schedule train ID")
        self._auto = AutoDispatcher([
            plan_run(train, self._graphs[train.line],
                     lambda route, line=train.line: self._run_time_s(
                         line, route),
                     self._station_blocks[train.line])
            for train in schedule.trains])
        self._schedule = schedule

    def set_automatic_mode(self, active: bool) -> None:
        """Enter or leave automatic mode; see ``CtcOffice``."""
        if not isinstance(active, bool):
            raise InvalidInputError(
                f"automatic mode must be true or false, got {active!r}")
        self._automatic = active

    def set_dispatch_paused(self, paused: bool) -> None:
        """Pause or resume automatic dispatch; see ``CtcOffice``."""
        if not isinstance(paused, bool):
            raise InvalidInputError(
                f"paused must be true or false, got {paused!r}")
        self._dispatch_paused = paused

    # -- Internals ----------------------------------------------------

    def _newest(self) -> CtcInputs:
        """The newest reports: staged ones if any, else the applied."""
        if self._staged is not None:
            return self._staged
        return self._inputs if self._inputs is not None else CtcInputs()

    def _ready_lines(self, inputs: CtcInputs | None = None
                     ) -> frozenset[str]:
        """The lines whose Track Controller is ready, in ``inputs`` or
        else in the reports last applied: a wayside on the line has
        reported, and every wayside on it is ready."""
        inputs = self._inputs if inputs is None else inputs
        return (frozenset() if inputs is None
                else ready_lines(inputs.track_controller.waysides))

    @staticmethod
    def _occupied(inputs: CtcInputs) -> set[tuple[str, str]]:
        return {(o.line, o.block_id)
                for o in inputs.track_controller.occupancy if o.occupied}

    def _train_lines(self) -> dict[str, str]:
        return {train_id: t.line
                for train_id, t in self._tracker.trains.items()}

    def _waiting(self) -> list[Waiting]:
        """Ordered trains waiting in the yard (not followed, not lost),
        most behind schedule first: the order they leave it in."""
        waiting = []
        for train_id, order in self._orders.items():
            if (train_id in self._tracker.trains
                    or train_id in self._tracker.lost):
                continue
            exit_block = YARD_EXITS.get(order.line)
            route = (self._graphs[order.line].route(
                exit_block, order.destination_block_id)
                if exit_block is not None else None)
            waiting.append((self._priority(order, order.line,
                                           route or ()), order))
        waiting.sort(key=lambda item: item[0])
        return [Waiting(order.train_id, order.line)
                for _, order in waiting]

    def _make_plans(self) -> dict[str, Plan]:
        """What each followed train is told: the next block, if its
        authority lets it in, and the speed suggested in its head
        block."""
        plans = {}
        for limit in self._authorities():
            train = self._tracker.trains.get(limit.train_id)
            if train is None:
                continue
            plans[limit.train_id] = Plan(
                limit.route[1] if limit.blocks >= 1 else None,
                self._layout.lengths_m[(limit.line, train.head)],
                self._suggested_speed_mps(limit.line, train.head, limit))
        return plans

    def _cancel_orders_into(self, block: BlockRef, reason: str) -> None:
        for train_id, order in sorted(self._orders.items()):
            if (order.line, order.destination_block_id) == (
                    block.line, block.block_id):
                del self._orders[train_id]
                self._cancelled.append(CancelledOrder(
                    train_id, block.line, block.block_id, reason))
        del self._cancelled[:-_CANCELLED_KEPT]

    def _now_s(self) -> float:
        """Simulated time of day: the module is stepped from the
        simulation start (D017)."""
        return SIMULATION_START_S + self._elapsed_s

    def _run_schedule(self) -> None:
        """Move the schedule's runs on, in automatic mode only, and give
        the orders that takes, with the dispatcher's own safety checks.
        A stop that cannot be ordered (closed or closing) is skipped."""
        if self._auto is None or not self._automatic \
                or self._dispatch_paused:
            return
        world = World(
            now_s=self._now_s(),
            ready_lines=self._ready_lines(self._newest()),
            heads={train_id: t.head
                   for train_id, t in self._tracker.trains.items()},
            orders={train_id: o.destination_block_id
                    for train_id, o in self._orders.items()},
            lost=frozenset(self._tracker.lost))
        pending = list(self._auto.step(world))
        while pending:
            action = pending.pop(0)
            if isinstance(action, Cancel):
                # The run is back in the yard: its order is done.
                self._orders.pop(action.train_id, None)
                self._tracker.lost.discard(action.train_id)
                continue
            try:
                self.dispatch(action.train_id, action.line, action.block_id,
                              action.due_s)
            except UnsafeActionError:
                skipped = self._auto.skip_stop(action.train_id)
                if skipped is not None:
                    pending.insert(0, skipped)

    def _scheduled_runs(self) -> tuple[ScheduledRun, ...]:
        if self._auto is None:
            return ()
        runs = []
        for plan in self._auto.plans:
            progress = self._auto.progress[plan.train_id]
            stop = (plan.stops[progress.leg]
                    if progress.status in ("in yard", "en route",
                                           "dwelling", "held")
                    and progress.leg < len(plan.stops) else None)
            done = {"dwelling": progress.leg + 1, "to yard": len(plan.stops),
                    "done": len(plan.stops)}.get(progress.status,
                                                 progress.leg)
            runs.append(ScheduledRun(
                plan.line, plan.run_id, plan.train_id, plan.departure_s,
                progress.status,
                stop.block_id if stop else "",
                stop.station if stop else "",
                stop.due_s if stop else None,
                done, len(plan.stops)))
        return tuple(runs)

    def _suggested_speed_mps(self, line: str, block_id: str,
                             limit: TrainAuthority) -> int:
        """The lower of: a little under the block's speed limit (the
        limit in whole m/s, rounded down, less
        ``SUGGESTED_SPEED_MARGIN_MPS``), and the speed the train can
        stop from within its authority at ``SERVICE_DECEL_MPS2`` (0 with
        no authority). The distance left in its own block is not
        counted: which way it heads through it is not known."""
        limit_kmh = self._layout.speed_limits_kmh[(line, block_id)]
        under_limit = max(0, int(limit_kmh / _KMH_PER_MPS)
                          - SUGGESTED_SPEED_MARGIN_MPS)
        stopping_m = sum(self._layout.lengths_m[(line, ahead)]
                         for ahead in limit.route[1:limit.blocks + 1])
        can_stop = int(math.sqrt(2 * SERVICE_DECEL_MPS2 * stopping_m))
        return min(under_limit, can_stop)

    def _obstructions(self, inputs: CtcInputs,
                      line: str) -> dict[str, str]:
        """Blocks on ``line`` no train may enter, and why."""
        found = {block_id: "occupied"
                 for occupied_line, block_id in self._occupied(inputs)
                 if occupied_line == line}
        found.update((b.block_id, "closing") for b in self._pending
                     if b.line == line)
        found.update((b.block_id, "closed") for b in self._closed
                     if b.line == line)
        # An inferred failure stays "occupied": the UIs never show one.
        return found

    def _unusable(self, line: str) -> set[str]:
        """Blocks on ``line`` no route should run through: closed,
        closing, and inferred to have failed."""
        return ({b.block_id for b in self._closed | self._pending
                 if b.line == line}
                | {block for ln, block in self._tracker.failures
                   if ln == line})

    def _run_time_s(self, line: str, route: tuple[str, ...]) -> float:
        """Time to run a route's blocks after the first at each block's
        speed limit: how long a train needs to get there."""
        total = 0.0
        for block_id in route[1:]:
            limit_mps = (self._layout.speed_limits_kmh[(line, block_id)]
                         / _KMH_PER_MPS)
            if limit_mps > 0:
                total += self._layout.lengths_m[(line, block_id)] / limit_mps
        return total

    def _priority(self, order: DispatchOrder, line: str,
                  route: tuple[str, ...]) -> tuple[int, float, str]:
        """Sort key, most urgent first: least slack between the
        requested arrival and the run time left; trains with no
        requested arrival last; then by train ID."""
        if order.arrival_s is None:
            return (1, 0.0, order.train_id)
        slack = order.arrival_s - self._run_time_s(line, route)
        return (0, slack, order.train_id)

    def _authorities(self) -> tuple[TrainAuthority, ...]:
        """Authority of every ordered train on the track, by train ID.

        The yard is a black box: a train gets authority once it is
        reported on the track. None while its line's Track Controller is
        not ready (reason "not ready"). Recomputed from the applied reports
        every time (``ctc.routing``), with no block in two trains' authorities
        (exclusive-authority): first every train keeps what it was
        granted at the last step and has not passed yet, then, most
        urgent first, each extends toward its destination through blocks
        no other train holds.
        """
        # Everything the result depends on; the inputs by identity.
        key = (self._inputs, tuple(sorted(self._orders.items())),
               frozenset(self._closed), frozenset(self._pending),
               tuple(sorted(self._granted.items())),
               tuple(sorted(self._tracker.trains.items())),
               frozenset(self._tracker.failures))
        cached = self._authority_cache
        if (cached is not None and cached[0][0] is key[0]
                and cached[0][1:] == key[1:]):
            return cached[1]
        result = self._compute_authorities()
        self._authority_cache = (key, result)
        return result

    def _stuck_blocks(self) -> dict[str, set[str]]:
        """Per line, blocks holding a train that is not going to move:
        one with no order, or one that had no authority at the last step
        (at its destination or held up). Trains route around them where
        they can. (Inferred failures are unusable, not stuck.)"""
        stuck: dict[str, set[str]] = {line: set() for line in self._lines}
        for train_id, train in self._tracker.trains.items():
            if (train_id not in self._orders
                    or self._granted.get(train_id) == ()):
                stuck[train.line].update(train.blocks)
        return stuck

    def _choose_route(self, line: str, block_id: str, destination: str,
                      unusable: set[str], stuck: set[str],
                      came_from: str | None = None
                      ) -> tuple[tuple[str, ...] | None, str]:
        """The route, and where the train would have to reverse ("" if
        nowhere).

        The shortest route around unusable blocks (closed, closing,
        failed) and trains that are not going to move; failing that,
        around unusable blocks only; failing that, the shortest route,
        which the train waits on. A detour more than
        ``MAX_DETOUR_FACTOR`` times as long as the shortest route is not
        taken. When the train waits on something that will not clear by
        itself and only reversing would get it round, the block it would
        reverse in is returned too: the CTC never reverses a train.

        ``came_from`` is the block the train entered its block from, when
        the CTC has seen it move: every route carries on that way.
        """
        graph = self._graphs[line]
        blocking = (unusable | stuck) - {block_id}
        direct = graph.route(block_id, destination, came_from=came_from)
        if direct is None:
            return None, self._reversal(line, block_id, destination,
                                        blocking, came_from)
        for avoid in (unusable | stuck, unusable):
            route = graph.route(block_id, destination, avoid - {block_id},
                                came_from=came_from)
            if (route is not None
                    and len(route) <= MAX_DETOUR_FACTOR * len(direct)):
                return route, ""
        if not set(direct[1:]) & blocking:
            return direct, ""
        return direct, self._reversal(line, block_id, destination, blocking,
                                      came_from)

    def _reversal(self, line: str, block_id: str, destination: str,
                  blocking: set[str], came_from: str | None = None) -> str:
        """Where reversing would get the train round ``blocking``, or
        ""."""
        graph = self._graphs[line]
        route = reversing_route(graph, block_id, destination, blocking,
                                came_from)
        return first_reversal(graph, route, came_from) if route else ""

    def _compute_authorities(self) -> tuple[TrainAuthority, ...]:
        applied = self._inputs if self._inputs is not None else CtcInputs()
        positions = {train_id: (t.line, t.head)
                     for train_id, t in self._tracker.trains.items()}
        ready = self._ready_lines()
        found: dict[str, TrainAuthority] = {}
        obstructions = {line: self._obstructions(applied, line)
                        for line in self._lines}
        stuck = self._stuck_blocks()
        # Where a held train would have to reverse, by train ID.
        reversals: dict[str, str] = {}
        # (train, line, block, order, route) for trains that can move.
        movers = []
        for train_id, order in sorted(self._orders.items()):
            if train_id not in positions:
                continue
            line, block_id = positions[train_id]
            if line not in ready:
                # Vital waysides with no PLC program: no train may move.
                found[train_id] = TrainAuthority(
                    train_id, line, 0, block_id, "not ready")
                continue
            unusable = self._unusable(line)
            route, reverse_at = (
                self._choose_route(line, block_id,
                                   order.destination_block_id, unusable,
                                   stuck[line],
                                   self._tracker.trains[train_id].came_from)
                if line == order.line else (None, ""))
            if route is None:
                found[train_id] = TrainAuthority(
                    train_id, line, 0, block_id, "no route",
                    reverse_at=reverse_at)
                continue
            reversals[train_id] = reverse_at
            movers.append((train_id, line, block_id, order, route))
        movers.sort(key=lambda m: self._priority(m[3], m[1], m[4]))

        switches: dict[str, dict[str, SwitchPosition]] = {
            line: {} for line in self._lines}
        for report in applied.track_controller.switches:
            switches[report.line][report.switch_id] = report.position
        # (line, block) -> the train whose authority holds it.
        holders: dict[tuple[str, str], str] = {}

        def reserved_for(train_id: str, line: str) -> dict[str, str]:
            return {block: holder for (ln, block), holder in holders.items()
                    if ln == line and holder != train_id}

        def count(train_id: str, line: str, block_id: str,
                  order: DispatchOrder, route: tuple[str, ...],
                  keep: Collection[str] | None) -> TrainAuthority:
            counted = authority(
                self._graphs[line], block_id, order.destination_block_id,
                obstructions[line], switches[line],
                reserved_for(train_id, line), keep, route)
            for ahead in counted.route[1:counted.blocks + 1]:
                holders[(line, ahead)] = train_id
            return TrainAuthority(
                train_id, line, counted.blocks, counted.end_block_id,
                counted.reason, counted.at, counted.route, counted.held_by,
                reversals.get(train_id, ""))

        # Keep what was granted and is still ahead, before anyone
        # extends: a lower-priority train keeps its blocks.
        for train_id, line, block_id, order, route in movers:
            count(train_id, line, block_id, order, route,
                  self._granted.get(train_id, ()))
        for train_id, line, block_id, order, route in movers:
            found[train_id] = count(train_id, line, block_id, order, route,
                                    None)
        return tuple(found[t] for t in sorted(found))

    def _outputs(self) -> CtcOutputs:
        # The waysides are vital: nothing goes to a line's Track
        # Controller until it reports the line ready. Closures and
        # switch commands are kept and sent once it does.
        ready = self._ready_lines()
        # The yard is a black box: a train gets speed and authority once
        # it has left the yard, from the block its head is in.
        positions = {train_id: (t.line, t.head)
                     for train_id, t in self._tracker.trains.items()}
        suggestions = tuple(
            TrainSuggestion(limit.train_id, *positions[limit.train_id],
                            self._suggested_speed_mps(
                                *positions[limit.train_id], limit),
                            limit.blocks)
            for limit in self._authorities() if limit.line in ready
        )
        return CtcOutputs(
            track_controller=TrackControllerOutputs(
                suggestions=suggestions,
                closed_blocks=tuple(b for b in self._closed_blocks()
                                    if b.line in ready),
                switch_commands=tuple(c for c in self._switch_commands()
                                      if c.line in ready),
            ),
            clock_speedup=self._clock_speedup,
            clock_paused=self._clock_paused,
        )

    def _closed_blocks(self) -> tuple[BlockRef, ...]:
        # Closing blocks too: locked from the moment the closure is
        # requested.
        return tuple(sorted(self._closed | self._pending,
                            key=_block_order))

    def _switch_commands(self) -> tuple[SwitchCommand, ...]:
        return tuple(
            SwitchCommand(line, switch_id, position)
            for (line, switch_id), position in sorted(
                self._switches.items(),
                key=lambda item: _id_order(*item[0])))


def _id_order(line: str, block_id: str) -> tuple[str, int, str]:
    # Line, then block number as a number where it is one, for display.
    number = int(block_id) if block_id.isdigit() else -1
    return (line, number, block_id)


def _block_order(block: BlockRef) -> tuple[str, int, str]:
    return _id_order(block.line, block.block_id)
