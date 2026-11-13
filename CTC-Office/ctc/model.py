"""Stub CTC Office: satisfies the contract with no scheduling logic yet.

The stub turns dispatcher actions straight into outputs so data can be
seen crossing the boundary. The Track Controller reports only block
occupancy, so the stub follows its own trains from it and infers which
occupied blocks are failures (``ctc.tracking``). Each dispatched train it
is following gets a suggested speed a little under its current block's
speed limit, and an authority counted in blocks toward its destination
that stops short of any closed block and of
any switch not reported set for its route, and never ends next to
another train's block or authority, so one empty block stays between
trains (``ctc.routing``), recomputed
every step. While that authority is at least 1 the train gets a second
suggestion, for the next block on its route, with one block less
authority and a speed worked out for that block (R49).

The stub releases ordered trains from the yard and retires them there
(D022, R46), and reports each in a one-time event in its outputs:

- **Release** (``new_trains``): on each line, one train at a time, the
  waiting train most behind schedule first, only while the line's
  waysides are all ready, its yard exit block (Green 63, Red 9) is
  clear and no train is authorized into it, and the schedule is not
  holding the run. A released train holds its exit block until it is
  found there (``ctc.tracking``).
- **Retirement** (``retired_trains``): a train sent back to the yard
  (a run of the schedule after its last stop, or a manual train by the
  dispatcher's "return to yard", R66), once it has stopped at its
  line's yard entry block (Green 57, Red 9) with authority 0 at its
  destination. The CTC sees only occupancy, so "stopped" means the
  train holds that block alone and the fastest it could still be going,
  braking at ``SERVICE_DECEL_MPS2`` since it was told 0 there, is 0.
  Its order is dropped with it.

Under the central harness each step brings the simulation time
(D017), and the stub's time is that time: a tick it refused or never
got does not put its schedule behind. On its own it counts the time of
the steps it took.

The blocks closed in maintenance mode and
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
    NewTrain,
    RetiredTrain,
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
    keep_gap,
    reversing_route,
)
from ctc.track_layout import Line, load_layout, station_lines
from ctc.scheduler import (
    HELD,
    IN_YARD,
    SIMULATION_START_S,
    TO_YARD,
    AutoDispatcher,
    Cancel,
    World,
    goes_wrong_way,
    plan_run,
    train_id_for,
)
from ctc.tracking import (
    YARD_ENTRIES,
    YARD_EXIT_FROM,
    YARD_EXITS,
    Plan,
    Tracked,
    TrainTracker,
    Waiting,
)

if TYPE_CHECKING:
    from ctc.schedule import Schedule

#: Service deceleration the suggested speed lets a train stop at
#: within its authority, in m/s^2 (``truth/modules/train-model.md``:
#: 1.2 m/s^2 at 2/3 load; ``suggested-speed-stops-within-authority``,
#: proposed on ``ctc-interfacing``).
SERVICE_DECEL_MPS2 = 1.2

#: The service brake's force, in N: the reference mass times the service
#: deceleration (``truth/modules/train-model.md``).
SERVICE_BRAKE_FORCE_N = (40_900 + 2 / 3 * (56_700 - 40_900)) * 1.2

#: A train with every seat and standing place taken, and its crew, in kg:
#: the slowest it can stop (``truth/modules/train-model.md``).
FULL_TRAIN_MASS_KG = 40_900 + (222 + 5) * 77.1107

GRAVITY_MPS2 = 9.81

#: A route around an unusable block or a train that is not moving is
#: taken only if it is at most this many times as long as the shortest
#: route; otherwise the train waits.
MAX_DETOUR_FACTOR = 2

#: How far below the current block's speed limit the suggested speed
#: is, in m/s (asserted by Landis 2026-10-06; it will be adjusted on the
#: fly once several trains share the track).
SUGGESTED_SPEED_MARGIN_MPS = 1

#: Seconds a train runs on at the suggested speed before its brake takes
#: hold, which the suggested speed leaves room for: a train told to stop
#: at the end of its authority stops inside its last block. With no
#: room (until 2026-11-12) trains ran one block past their authority,
#: onto a switch they then locked or next to a train ahead, and the
#: waysides, which hold two trains in neighbouring blocks, held both for
#: good. 3 s covers a 2 s reaction and a step's lag (Landis 2026-11-12,
#: measured on tests/realistic_railway.py).
STOP_REACTION_S = 3.0

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
        self.grades_percent = {(name, b.block_id): b.grade_percent
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

    It does enforce the safety rules: no authority into a closed
    or failed block or onto another line than the train's;
    authority stops short of every such block and of switches not set
    for the route, and never ends next to another train's block or
    authority (one empty block between trains); no switch thrown under
    a train.
    Block closures and switch commands are set and removed in
    maintenance mode only, and both outlast it
    (``maintenance-closure-lock``). Failed blocks are inferred from occupancy
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
        # The loaded schedule's time zero, once it has started: the
        # clock ran with it loaded (``ctc.scheduler``). None until then.
        self._schedule_start_s: float | None = None
        # The loaded schedule's plans and progress (ctc.scheduler).
        self._auto: AutoDispatcher | None = None
        self._automatic = False
        self._dispatch_paused = False
        # Where the trains are and which blocks failed, from occupancy.
        self._tracker = TrainTracker(SERVICE_DECEL_MPS2)
        # What each tracked train should do next, from the last step.
        self._plans: dict[str, Plan] = {}
        # Trains released from the yard and not yet found on the track,
        # by train ID, with their line, in the order released: at most
        # one per line. Each holds its line's yard exit block.
        self._released: dict[str, str] = {}
        # Per line, when the last run of the schedule was released and
        # when it was due out: the next leaves no closer behind it than
        # the schedule's headway between the two.
        self._last_release: dict[str, tuple[float, float]] = {}
        # Trains the CTC has created (released) and not retired: a
        # train already in service that went back into the yard
        # without being retired leaves it again with no second event.
        self._in_service: set[str] = set()
        # Manual trains the dispatcher sent back to the yard ("return to
        # yard", R66) whose order to the yard entry block still stands.
        self._returning: set[str] = set()
        # This step's one-time events (D022); empty after a step with
        # none.
        self._new_trains: tuple[NewTrain, ...] = ()
        self._retired_trains: tuple[RetiredTrain, ...] = ()

    # -- Stepping -----------------------------------------------------

    def step(self, dt: float, inputs: CtcInputs,
             sim_time_s: float | None = None) -> CtcOutputs:
        """Advance one tick; see ``CtcOffice.step``.

        With ``sim_time_s`` (the harness's time at the end of the step,
        D017) the module's time becomes that time; without it, the
        module's time moves on by ``dt``.
        """
        if not _is_finite_number(dt) or dt <= 0:
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {_short(dt)}")
        if sim_time_s is None:
            elapsed_s = self._elapsed_s + dt
            if not math.isfinite(elapsed_s):
                raise InvalidTimeStepError(
                    f"dt {dt:g} s would take the elapsed time past what "
                    "can be counted")
        else:
            elapsed_s = self._elapsed_at(sim_time_s)
        inputs = _normalize(inputs)
        self._layout.validate_inputs(inputs)
        # Time passing means the clock runs: a loaded schedule starts now
        # if it has not yet (it starts at Run, set_clock_paused).
        self._start_schedule()

        self._elapsed_s = elapsed_s
        self._new_trains, self._retired_trains = (), ()
        # Follow the trains (and infer failures) from the new occupancy,
        # against the last step's plans. Only a train the CTC released
        # can be found leaving the yard.
        self._tracker.update(
            frozenset(self._occupied(inputs)), self._elapsed_s,
            self._plans,
            [Waiting(t, line) for t, line in self._released.items()])
        self._released = {t: line for t, line in self._released.items()
                          if t not in self._tracker.trains}
        self._inputs = inputs
        self._staged = None
        for station, tickets in inputs.track_model.ticket_sales.items():
            self._tickets[station] += tickets
        # In automatic mode, the schedule's runs move on.
        self._run_schedule()
        # Trains sent back to the yard that have stopped at its entry
        # block are retired, and their orders dropped.
        self._retire()
        # Commit this step's grants; later steps keep them. Nothing is
        # granted on a line whose Track Controller is not ready.
        ready = self._ready_lines()
        self._granted = {a.train_id: a.route[1:a.blocks + 1]
                         for a in self._authorities() if a.line in ready}
        self._plans = self._make_plans()
        # Then, with this step's grants, a waiting train may be let out.
        self._release()
        return self._outputs()

    def _elapsed_at(self, sim_time_s: float) -> float:
        """The elapsed time at the harness's ``sim_time_s``: unwrapped
        seconds since the first midnight (D017), finite and after the
        module's own time, which never goes back."""
        if not _is_finite_number(sim_time_s):
            raise InvalidTimeStepError(
                "sim_time_s must be a finite number of seconds, got "
                f"{_short(sim_time_s)}")
        if sim_time_s <= self._now_s():
            raise InvalidTimeStepError(
                f"sim_time_s {sim_time_s:g} s is not after the module's "
                f"time, {self._now_s():g} s")
        return float(sim_time_s) - SIMULATION_START_S

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
            schedule_start_s=self._schedule_start_s,
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

        Refused (safety) into a closed block, onto a line
        other than the one the train is on, and on a line whose Track
        Controller is not ready (no PLC program loaded). A block inferred
        to have failed is not refused: the UIs never show a failure, and
        the train waits short of it until it clears.
        """
        train_id = _trim(train_id)
        if arrival_s is not None:
            if isinstance(arrival_s, bool):
                raise InvalidInputError("arrival_s must be a number")
            _require_finite(arrival_s, "arrival_s")
            if not 0 <= arrival_s < _DAY_S:
                raise InvalidInputError(
                    f"arrival_s must be within one day, got {arrival_s}")
        self._check_dispatch(train_id, line, destination_block_id)
        self._orders[train_id] = DispatchOrder(
            train_id, line, destination_block_id, arrival_s)
        # A new order withdraws a "return to yard".
        self._returning.discard(train_id)

    def preview_dispatch(self, train_id: str, line: str,
                         destination_block_id: str) -> TrainSuggestion:
        """The suggested speed and authority the CTC would send for a
        train if it were dispatched now. No side effects.

        Counted from the block the train is in or, for a train still in
        the yard, from its line's yard exit block, where it will appear,
        around every other train's current authority. Refused as
        ``dispatch`` refuses. Once the order stands the values are
        recomputed every step, so they can differ from the preview.
        """
        train_id = _trim(train_id)
        self._check_dispatch(train_id, line, destination_block_id)
        tracked = self._tracker.trains.get(train_id)
        start = tracked.head if tracked is not None else YARD_EXITS.get(line)
        if start is None:
            raise InvalidInputError(f"The {line} line has no yard exit block.")
        applied = self._inputs if self._inputs is not None else CtcInputs()
        own = set(tracked.blocks) if tracked is not None else set()
        route, _ = self._choose_route(
            line, start, destination_block_id, self._unusable(line),
            self._stuck_blocks()[line] - own,
            tracked.came_from if tracked is not None else None)
        if route is None:
            return TrainSuggestion(train_id, line, start, 0, 0)
        switches = {r.switch_id: r.position
                    for r in applied.track_controller.switches
                    if r.line == line}
        reserved = {block: a.train_id for a in self._authorities()
                    if a.line == line and a.train_id != train_id
                    for block in a.route[1:a.blocks + 1]}
        reserved.update((YARD_EXITS[line], other)
                        for other, other_line in self._released.items()
                        if other_line == line and other != train_id)
        counted = authority(self._graphs[line], start, destination_block_id,
                            self._obstructions(applied, line), switches,
                            reserved, route=route)
        within = counted.route[1:counted.blocks + 1]
        return TrainSuggestion(
            train_id, line, start,
            self._suggested_speed_mps(line, start, within), counted.blocks)

    def _check_dispatch(self, train_id: str, line: str,
                        destination_block_id: str) -> None:
        """Raise if a dispatch of ``train_id`` to the block is refused."""
        self._layout.block(line, destination_block_id,
                           f"destination of {train_id}")
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
        reported = self._train_lines().get(train_id)
        if reported is not None and reported != line:
            raise UnsafeActionError(
                f"{train_id} is on the {reported} line; it cannot be sent "
                f"to a {line} block.")

    def return_to_yard(self, train_id: str) -> None:
        """Send a manual train back to the yard (R66, D022).

        The train is ordered to its line's yard entry block (Green 57,
        Red 9), with no arrival time, in place of any order it had. Once
        it has stopped there with authority 0 it is retired as a run of
        the schedule is (``retired_trains``). A later order withdraws
        it.

        Refused (``InvalidInputError``) for a train the CTC is not
        following on the track (one waiting in the yard has nothing to
        return from), and for a run of the
        loaded schedule, which the schedule sends back itself. Refused
        (safety) as ``dispatch`` refuses: the yard entry block closed,
        or the line's Track Controller not ready.
        """
        train_id = _trim(train_id)
        train = self._tracker.trains.get(train_id)
        if train is None:
            raise InvalidInputError(
                f"{train_id} is not on the track; only a train on the "
                "track can be sent back to the yard.")
        if self._auto is not None and train_id in self._auto.progress:
            raise InvalidInputError(
                f"{train_id} is a run of the loaded schedule; the "
                "schedule sends it back to the yard itself.")
        entries = sorted(YARD_ENTRIES.get(train.line, ()))
        if not entries:
            raise InvalidInputError(
                f"The {train.line} line has no yard entry block.")
        self.dispatch(train_id, train.line, entries[0])
        self._returning.add(train_id)

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
            return
        if block in self._closed:
            return
        # Closed at once, even with a train in it (block-closure).
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
        """Drop the command for one switch, if there is one, handing it
        back to the Track Controller. Maintenance mode only."""
        if not self._maintenance:
            raise MaintenanceModeRequiredError(
                "Switches can be released only in maintenance mode.")
        self._switches.pop((line, switch_id), None)

    def set_maintenance_mode(self, active: bool) -> None:
        """Enter or leave maintenance mode. Closed blocks and switch
        commands stay as they are either way: only the dispatcher,
        back in maintenance mode, reopens or releases them
        (``maintenance-closure-lock``)."""
        if not isinstance(active, bool):
            raise InvalidInputError(
                f"maintenance mode must be true or false, got {active!r}")
        self._maintenance = active

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
        if not paused:
            self._start_schedule()

    def load_schedule(self, schedule: Schedule) -> None:
        """Replace the schedule. Every stop must be a block of the
        track layout. Each run is planned at once (``ctc.scheduler``):
        its scheduled stations, and no others, in track order from the
        yard, each with the time it is due there. The schedule's time
        zero is now if the clock is running, else the moment it next runs
        (Run), when the runs are timed again from then. In automatic mode
        the runs then dispatch themselves. Orders already given stay."""
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
        self._schedule = schedule
        self._schedule_start_s = None
        self._plan_schedule(self._now_s())
        if not self._clock_paused:
            self._start_schedule()

    def _plan_schedule(self, start_s: float) -> None:
        """Plan every run of the loaded schedule from time zero
        ``start_s``."""
        schedule = self._schedule
        assert schedule is not None
        # The runs are timed afresh: headway is counted from scratch.
        self._last_release = {}
        self._auto = AutoDispatcher([
            plan_run(train, self._graphs[train.line],
                     lambda route, line=train.line: self._run_time_s(
                         line, route),
                     self._station_blocks[train.line], start_s)
            for train in schedule.trains])

    def _start_schedule(self) -> None:
        """Start a loaded schedule that has not started: its time zero
        is now, and its runs are timed from it."""
        if self._schedule is None or self._schedule_start_s is not None:
            return
        self._schedule_start_s = self._now_s()
        self._plan_schedule(self._schedule_start_s)

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
        """Ordered trains waiting in the yard (not followed, not lost,
        not yet released), most behind schedule first: the order they
        are released in."""
        waiting = []
        for train_id, order in self._orders.items():
            if (train_id in self._tracker.trains
                    or train_id in self._tracker.lost
                    or train_id in self._released):
                continue
            exit_block = YARD_EXITS.get(order.line)
            route = (self._graphs[order.line].route(
                exit_block, order.destination_block_id,
                came_from=YARD_EXIT_FROM.get(order.line))
                if exit_block is not None else None)
            waiting.append((self._priority(order, order.line,
                                           route or ()), order))
        waiting.sort(key=lambda item: item[0])
        return [Waiting(order.train_id, order.line)
                for _, order in waiting]

    def _make_plans(self) -> dict[str, Plan]:
        """What each followed train is told: the next block, if its
        authority lets it in, and the speed suggested in its head
        block. A train told to stop may not manage it, so each also has
        the block it would run on into: the one it was last heading
        for, else the next on its route, else straight on."""
        plans = {}
        limits = {a.train_id: a for a in self._authorities()}
        for train_id, train in self._tracker.trains.items():
            limit = limits.get(train_id)
            last = self._plans.get(train_id)
            onward = last.onward_block if last is not None else None
            if onward in train.blocks:
                onward = None
            route = limit.route if limit is not None else ()
            allowed = limit is not None and limit.blocks >= 1
            if allowed or (onward is None and len(route) > 1):
                onward = route[1]
            if onward is None:
                onward = self._straight_on(train)
            if limit is None and onward is None:
                continue
            plans[train_id] = Plan(
                route[1] if allowed else None,
                self._layout.lengths_m[(train.line, train.head)],
                (self._suggested_speed_mps(
                    train.line, train.head, route[1:limit.blocks + 1])
                 if limit is not None else 0.0),
                onward)
        return plans

    def _straight_on(self, train: Tracked) -> str | None:
        """The block a train runs into past the end of its route: the
        one next to its head block that the track leads it into. Not
        the block it came from, nor one that joins at the same end (a
        switch's other connection). Where that still leaves a choice,
        the train faces a switch's points, and the switch's reported
        position decides. None when nothing settles it."""
        graph = self._graphs[train.line]
        beyond = [n for n in graph.neighbors(train.head)
                  if n != train.came_from
                  and not graph.turns_back(train.came_from, train.head, n)]
        if len(beyond) > 1:
            applied = (self._inputs if self._inputs is not None
                       else CtcInputs())
            reported = {r.switch_id: r.position
                        for r in applied.track_controller.switches
                        if r.line == train.line}
            legs = {n: graph.leg(train.head, n) for n in beyond}
            beyond = [n for n, leg in legs.items()
                      if leg is None
                      or reported.get(leg.switch_id) == leg.position]
        return beyond[0] if len(beyond) == 1 else None

    # -- The yard -----------------------------------------------------

    def _scheduler_holds(self, train_id: str) -> bool:
        """Whether the schedule is holding a run in the yard: outside
        automatic mode, while automatic dispatch is paused, or while the
        run is not waiting to leave (``ctc.scheduler``). A train that is
        not a run of the loaded schedule is never held by it."""
        if self._auto is None or train_id not in self._auto.progress:
            return False
        progress = self._auto.progress[train_id]
        # Held with a place to wait further on: it leaves the yard.
        leaving = (progress.status == IN_YARD
                   or (progress.status == HELD and progress.wait >= 0))
        return (not self._automatic or self._dispatch_paused
                or not leaving)

    def _departure_s(self, train_id: str) -> float | None:
        """When a run of the loaded schedule is due out of the yard;
        None for a train that is not one."""
        if self._auto is None:
            return None
        return next((plan.departure_s for plan in self._auto.plans
                     if plan.train_id == train_id), None)

    def _too_soon_after(self, train_id: str, line: str) -> bool:
        """Whether a run would leave the yard closer behind the last
        run released on its line than the schedule puts them: runs kept
        in the yard past their time leave the schedule's headway apart,
        not one straight after another. A train that is not a run of the
        schedule, and a run due no later than the last one released, is
        never too soon."""
        departure_s = self._departure_s(train_id)
        last = self._last_release.get(line)
        if departure_s is None or last is None:
            return False
        released_s, last_departure_s = last
        return self._now_s() - released_s < departure_s - last_departure_s

    def _sent_to_yard(self, train_id: str) -> bool:
        """Whether a train has been sent back to the yard: a run of the
        loaded schedule on its way back after its last stop, or a manual
        train the dispatcher returned to the yard (``return_to_yard``)."""
        if train_id in self._returning:
            return True
        return (self._auto is not None
                and train_id in self._auto.progress
                and self._auto.progress[train_id].status == TO_YARD)

    def _release(self) -> None:
        """Release waiting trains from the yard (D022, R46): on each
        line, at most one released train not yet found on the track,
        and the most behind schedule first among those the scheduler is
        not holding. Only while the line's waysides are all ready, its
        yard exit block is clear (not occupied, not closed,
        no train on it) and no train is authorized into it, and the
        same for the blocks next to it, closed or not, so a train never
        comes out next to another (``keep_gap``; Landis 2026-11-03). A
        run of the schedule also leaves no closer behind the last run
        released on its line than the schedule puts them
        (``_too_soon_after``). A train is reported in ``new_trains`` the
        step it is released, unless it was already in service."""
        ready = self._ready_lines()
        applied = self._inputs if self._inputs is not None else CtcInputs()
        held = (self._occupied(applied)
                | {(t.line, b) for t in self._tracker.trains.values()
                   for b in t.blocks}
                | {(a.line, b) for a in self._authorities()
                   for b in a.route[1:a.blocks + 1]})
        blocked = held | {(b.line, b.block_id) for b in self._closed}
        busy = set(self._released.values())
        released = []
        for waiting in self._waiting():
            line = waiting.line
            exit_block = YARD_EXITS.get(line)
            if (exit_block is None or line in busy or line not in ready
                    or (line, exit_block) in blocked
                    or any((line, n) in held for n in
                           self._graphs[line].neighbors(exit_block))
                    or self._scheduler_holds(waiting.train_id)
                    or self._too_soon_after(waiting.train_id, line)):
                continue
            busy.add(line)
            self._released[waiting.train_id] = line
            departure_s = self._departure_s(waiting.train_id)
            if departure_s is not None:
                self._last_release[line] = (self._now_s(), departure_s)
            if waiting.train_id not in self._in_service:
                self._in_service.add(waiting.train_id)
                released.append(NewTrain(waiting.train_id, line))
        self._new_trains = tuple(released)

    def _at_a_stand(self, train: Tracked, order: DispatchOrder) -> bool:
        """Whether a followed train has stopped at its destination, as
        far as occupancy can tell: its head and tail are both in that
        block, and the fastest it could still be going, braking at
        ``SERVICE_DECEL_MPS2`` since it was told 0 there, is 0
        (``ctc.tracking``). The CTC never sees a speed, so this is the
        latest it could still be moving, not the moment it stopped."""
        return (train.blocks == (order.destination_block_id,)
                and train.speed_mps <= 0)

    def _retire(self) -> None:
        """Retire each train sent back to the yard that has stopped at
        its line's yard entry block (Green 57, Red 9) with authority 0
        at its destination (D022, R46), reporting it in
        ``retired_trains`` and dropping its order. Nothing more is sent
        for it; the harness removes it, the block clears, and the
        schedule marks its run done."""
        retired = []
        for limit in self._authorities():
            train = self._tracker.trains.get(limit.train_id)
            order = self._orders.get(limit.train_id)
            if (train is None or order is None
                    or order.destination_block_id
                    not in YARD_ENTRIES.get(train.line, ())
                    or limit.blocks != 0 or limit.reason != "destination"
                    or not self._at_a_stand(train, order)
                    or not self._sent_to_yard(limit.train_id)):
                continue
            del self._orders[limit.train_id]
            self._in_service.discard(limit.train_id)
            self._returning.discard(limit.train_id)
            retired.append(RetiredTrain(limit.train_id))
        self._retired_trains = tuple(retired)

    def _cancel_orders_into(self, block: BlockRef, reason: str) -> None:
        for train_id, order in sorted(self._orders.items()):
            if (order.line, order.destination_block_id) == (
                    block.line, block.block_id):
                del self._orders[train_id]
                self._returning.discard(train_id)
                self._cancelled.append(CancelledOrder(
                    train_id, block.line, block.block_id, reason))
        del self._cancelled[:-_CANCELLED_KEPT]

    def _now_s(self) -> float:
        """Simulated time, unwrapped seconds since the first midnight:
        the simulation starts at 05:00:00 (D017). Under the harness it
        is the last step's ``sim_time_s``."""
        return SIMULATION_START_S + self._elapsed_s

    def _run_schedule(self) -> None:
        """Move the schedule's runs on, in automatic mode only, and give
        the orders that takes, with the dispatcher's own safety checks.
        A stop that cannot be ordered (closed) is skipped."""
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
            lost=frozenset(self._tracker.lost),
            released=frozenset(self._released),
            can_stop_by=self._can_stop_by)
        pending = list(self._auto.step(world))
        while pending:
            action = pending.pop(0)
            if isinstance(action, Cancel):
                # The run is back in the yard: its order is done.
                self._orders.pop(action.train_id, None)
                self._returning.discard(action.train_id)
                self._tracker.lost.discard(action.train_id)
                continue
            try:
                self.dispatch(action.train_id, action.line, action.block_id,
                              action.due_s)
            except UnsafeActionError:
                skipped = self._auto.skip_stop(action.train_id)
                if skipped is not None:
                    pending.insert(0, skipped)

    def _can_stop_by(self, train_id: str, block_id: str) -> bool:
        """Whether a train, at the speed it was last suggested, could
        stop by the end of ``block_id`` ahead of it on its route: that
        speed is no more than the one suggested with its authority
        ending there (``_suggested_speed_mps``). A train with no
        authority was suggested none. Not on its route: it could not."""
        limit = {a.train_id: a for a in self._authorities()}.get(train_id)
        if limit is None or limit.blocks == 0:
            return True
        if block_id not in limit.route:
            return False
        end = limit.route.index(block_id)
        given = self._suggested_speed_mps(
            limit.line, limit.route[0], limit.route[1:limit.blocks + 1])
        stopping = self._suggested_speed_mps(
            limit.line, limit.route[0], limit.route[1:end + 1])
        return given <= stopping

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
                             ahead: Collection[str]) -> int:
        """The speed suggested for a train in ``block_id``, with the
        blocks ``ahead`` of it within its authority.

        The lower of: a little under the block's speed limit (the
        limit in whole m/s, rounded down, less
        ``SUGGESTED_SPEED_MARGIN_MPS``), and the speed a full train can
        stop from within the blocks ``ahead``, on their grades, under
        the service brake, after running on ``STOP_REACTION_S`` at
        that speed before braking (0 with none). The distance left in
        the block
        itself is not counted: which way it heads through it is not
        known. For the
        next block on a train's route, ``ahead`` is one block shorter
        than for the block it is in (``suggested-speed``)."""
        limit_kmh = self._layout.speed_limits_kmh[(line, block_id)]
        under_limit = max(0, int(limit_kmh / _KMH_PER_MPS)
                          - SUGGESTED_SPEED_MARGIN_MPS)
        # The speed v a full train stops from within the blocks ahead,
        # less what it covers at v in STOP_REACTION_S before the brake
        # takes hold: v*T + v^2/(2b) = D, with b the length-weighted
        # braking over those blocks.
        distance = sum(self._layout.lengths_m[(line, block)]
                       for block in ahead)
        if distance <= 0:
            return 0
        braking = sum(self._full_train_braking_mps2(line, block)
                      * self._layout.lengths_m[(line, block)]
                      for block in ahead) / distance
        lag = braking * STOP_REACTION_S
        can_stop = int(-lag + math.sqrt(lag * lag + 2 * braking * distance))
        return min(under_limit, can_stop)

    def _full_train_braking_mps2(self, line: str, block_id: str) -> float:
        """How fast the service brake slows a full train in a block:
        less downhill, more uphill."""
        slope = math.atan(
            self._layout.grades_percent[(line, block_id)] / 100.0)
        return (SERVICE_BRAKE_FORCE_N / FULL_TRAIN_MASS_KG
                + GRAVITY_MPS2 * math.sin(slope))

    def _obstructions(self, inputs: CtcInputs,
                      line: str) -> dict[str, str]:
        """Blocks on ``line`` no train may enter, and why."""
        found = {block_id: "occupied"
                 for occupied_line, block_id in self._occupied(inputs)
                 if occupied_line == line}
        found.update((b.block_id, "closed") for b in self._closed
                     if b.line == line)
        # An inferred failure stays "occupied": the UIs never show one.
        return found

    def _unusable(self, line: str) -> set[str]:
        """Blocks on ``line`` no route should run through: closed, and
        inferred to have failed."""
        return ({b.block_id for b in self._closed if b.line == line}
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
               frozenset(self._closed),
               tuple(sorted(self._granted.items())),
               tuple(sorted(self._tracker.trains.items())),
               frozenset(self._tracker.failures),
               tuple(sorted(self._released.items())))
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

        The shortest route around unusable blocks (closed,
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
            # A run keeps to its plan's way (over a passing siding) while
            # nothing that would hold it up for good is on it. A train
            # standing on it (at a stop) does not send it the wrong way
            # round a stretch every run takes one way (``WRONG_WAY``):
            # it would meet the trains coming the right way. It waits.
            planned = (self._auto.planned_route(train_id, block_id)
                       if self._auto is not None else None)
            if (planned is not None and route is not None
                    and planned[-1] == order.destination_block_id
                    and not set(planned[1:]) & unusable
                    and (not set(planned[1:]) & stuck[line]
                         or goes_wrong_way(line, route))):
                route, reverse_at = planned, ""
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
        # (line, block) -> the train whose authority holds it. A train
        # released from the yard and not yet found holds its line's
        # yard exit block, where it will appear.
        holders: dict[tuple[str, str], str] = {
            (line, YARD_EXITS[line]): train_id
            for train_id, line in self._released.items()
            if line in YARD_EXITS}

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
            hold = (self._auto.hold_at(train_id)
                    if self._auto is not None else None)
            if hold is not None and hold in counted.route:
                # The schedule holds it round a loop until the zone
                # ahead is clear the other way (``ctc.scheduler``). Its
                # route ends there, so it lays no claim to the switches
                # beyond, which the trains it waits for need.
                end = counted.route.index(hold)
                counted = replace(counted, route=counted.route[:end + 1])
                if counted.blocks >= end:
                    counted = keep_gap(
                        self._graphs[line],
                        replace(counted, blocks=end, end_block_id=hold,
                                reason="held", at=hold, held_by=""),
                        obstructions[line], reserved_for(train_id, line))
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
        suggestions = []
        for limit in self._authorities():
            if limit.line not in ready:
                continue
            head = self._tracker.trains[limit.train_id].head
            within = limit.route[1:limit.blocks + 1]
            # While it may go on, the next block on its route too, with
            # one block less authority and a speed worked out for that
            # block: it carries the train's values from the moment the
            # train enters it, before the CTC sees it there
            # (``suggested-speed``, ``suggested-authority``; R49). It is
            # the first block within the train's own exclusive
            # authority, so no other train's suggestion names it. It
            # goes before the train's own block: the CTC window and its
            # test UI still key suggestions by train ID alone, and the
            # last one per train is the one they show.
            if limit.blocks >= 1:
                suggestions.append(TrainSuggestion(
                    limit.train_id, limit.line, within[0],
                    self._suggested_speed_mps(limit.line, within[0],
                                              within[1:]),
                    limit.blocks - 1))
            suggestions.append(TrainSuggestion(
                limit.train_id, limit.line, head,
                self._suggested_speed_mps(limit.line, head, within),
                limit.blocks))
        return CtcOutputs(
            track_controller=TrackControllerOutputs(
                suggestions=tuple(suggestions),
                closed_blocks=tuple(b for b in self._closed_blocks()
                                    if b.line in ready),
                switch_commands=tuple(c for c in self._switch_commands()
                                      if c.line in ready),
                route_requests=self._route_requests(ready),
            ),
            clock_speedup=self._clock_speedup,
            clock_paused=self._clock_paused,
            # The last step's events; between steps, the snapshot shows
            # them again, but only ``step`` hands them on.
            new_trains=self._new_trains,
            retired_trains=self._retired_trains,
        )

    def _closed_blocks(self) -> tuple[BlockRef, ...]:
        return tuple(sorted(self._closed, key=_block_order))

    def _route_requests(self, ready: Collection[str]
                        ) -> tuple[SwitchCommand, ...]:
        """The position each switch should take for the train routed
        over it: every switch within a train's authority, and the one
        its authority stops short of. The most urgent train's request
        stands where two trains want the same switch (``_priority``, as
        for contested blocks)."""
        wanted: dict[tuple[str, str], SwitchCommand] = {}
        limits = [a for a in self._authorities()
                  if a.line in ready and a.train_id in self._orders]
        limits.sort(key=lambda a: self._priority(
            self._orders[a.train_id], a.line, a.route))
        for limit in limits:
            graph = self._graphs[limit.line]
            ahead = limit.route[:limit.blocks + 2]
            if limit.reason == "switch":
                # Its authority may end a block further back, clear of
                # the blocks that lock the switch (``ctc.routing``): the
                # request still reaches the switch it waits for.
                for index in range(limit.blocks, len(limit.route) - 1):
                    leg = graph.leg(limit.route[index],
                                    limit.route[index + 1])
                    if leg is not None and leg.switch_id == limit.at:
                        ahead = limit.route[:index + 2]
                        break
            for here, after in zip(ahead, ahead[1:]):
                leg = graph.leg(here, after)
                if leg is not None:
                    wanted.setdefault(
                        (limit.line, leg.switch_id),
                        SwitchCommand(limit.line, leg.switch_id,
                                      leg.position))
        return tuple(wanted[key] for key in sorted(
            wanted, key=lambda k: _id_order(*k)))

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
