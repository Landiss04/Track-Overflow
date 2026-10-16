"""Automatic dispatch from a loaded schedule, for the CTC Office.

A schedule (``ctc.schedule``) lists, per line, the runs and each run's
timed stops. This module turns each run into a plan and, in automatic
mode, carries the plans out:

- **Scheduled stations only.** A run stops at the stations the file
  lists for it (blocks the track layout marks as stations, named or
  not) and nowhere else: it runs through every other station on its
  way without stopping. Blocks the file times that are not stations
  are not stops. (Confirmed by Landis 2026-10-14.)
- **Track order.** A run visits its stations in the order the track
  reaches them from the line's yard exit, not the order the file lists
  them in (the file lists them by block number, which a train cannot
  always run). It then returns to the yard. (Asserted by Landis
  2026-10-14, as a first approach that may change.)
- **Due times.** Time zero is the simulation start, 05:00:00 (D017). A
  run is due to leave the yard at 05:00 plus its departure offset in the
  file. Each stop is due when the run would reach it running every
  block at its speed limit, stopping ``DWELL_S`` at each stop before.
- **Stopping.** The CTC stops a train at each of its stops: it sends
  the train to the stop (its authority ends there), holds it for
  ``DWELL_S`` once it is there, then sends it to the next stop.
- **The yard.** A run leaves the yard when the dispatcher's order is
  given and the yard exit becomes occupied (``ctc.tracking``). After
  its last stop it is sent to the line's yard entry block; once its
  blocks clear there it is back in the yard and the run is done.

The dispatcher can pause automatic dispatch, and nothing advances
outside automatic mode: runs not yet due wait, and a train at a stop
stays there until dispatch resumes.

This module decides; the model (``ctc.model``) applies its decisions as
dispatch orders, with the same safety checks as the dispatcher's own.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Collection, Mapping, Sequence

from ctc.tracking import YARD_ENTRIES, YARD_EXITS

if TYPE_CHECKING:
    # Types only: ctc.schedule imports ctc.model, which imports this.
    from ctc.routing import TrackGraph
    from ctc.schedule import ScheduledTrain

#: Station dwell, in seconds (D007).
DWELL_S = 45

#: Simulated time a simulation starts at, in seconds since midnight
#: (D017: 05:00:00). The schedule's time zero.
SIMULATION_START_S = 5 * 3600

#: What a run is doing, as the snapshot reports it.
QUEUED = "queued"          # not due yet, or dispatch is held
IN_YARD = "in yard"        # dispatched; waiting to leave the yard
EN_ROUTE = "en route"      # heading for its next stop
DWELLING = "dwelling"      # stopped at a stop
TO_YARD = "to yard"        # past its last stop, heading back
DONE = "done"              # back in the yard


def train_id_for(line: str, run_id: str) -> str:
    """The train ID a run is dispatched as: run numbers repeat across
    lines, so the line's initial goes first ("G1" for Green run 1)."""
    return f"{line[:1].upper()}{run_id}"


@dataclass(frozen=True, slots=True)
class PlannedStop:
    """One stop of a run, in the order the train reaches it."""

    block_id: str
    station: str
    # Due there, in simulated seconds since midnight.
    due_s: float


@dataclass(frozen=True, slots=True)
class RunPlan:
    """What one run does, worked out when the schedule is loaded."""

    line: str
    run_id: str
    train_id: str
    # Due to leave the yard, in simulated seconds since midnight.
    departure_s: float
    stops: tuple[PlannedStop, ...]
    # The yard entry block it ends at; "" if it cannot get back.
    yard_block_id: str
    # Stations the file lists that the track does not reach from the
    # yard: not stops.
    unreachable: tuple[str, ...] = ()


def plan_run(run: ScheduledTrain, graph: TrackGraph,
             run_time_s: Callable[[tuple[str, ...]], float],
             station_blocks: Collection[str]) -> RunPlan:
    """Order a run's scheduled stations by track from the yard exit,
    time them, and route the return to the yard.

    ``run_time_s`` is how long a route takes after its first block, and
    ``station_blocks`` the blocks of the run's line the track layout
    marks as stations. Each leg carries on the way the train is going:
    it never turns back at a stop.
    """
    here = YARD_EXITS.get(run.line, "")
    came_from: str | None = None
    left: list[tuple[str, str | None]] = []
    for stop in run.stops:
        if (stop.block_id in station_blocks
                and stop.block_id not in (b for b, _ in left)):
            left.append((stop.block_id, stop.station))
    due = SIMULATION_START_S + run.departure_s
    stops: list[PlannedStop] = []
    while left and here:
        best: tuple[int, tuple[str, ...]] | None = None
        for index, (block_id, _) in enumerate(left):
            route = graph.route(here, block_id, came_from=came_from)
            if route is not None and (best is None
                                      or len(route) < len(best[1])):
                best = (index, route)
        if best is None:
            break
        block_id, station = left.pop(best[0])
        route = best[1]
        due += run_time_s(route)
        stops.append(PlannedStop(block_id, station or "", due))
        due += DWELL_S
        came_from = route[-2] if len(route) > 1 else came_from
        here = block_id
    yard_block = ""
    for entry in sorted(YARD_ENTRIES.get(run.line, ())):
        if here and graph.route(here, entry, came_from=came_from):
            yard_block = entry
            break
    return RunPlan(
        run.line, run.train_id, train_id_for(run.line, run.train_id),
        SIMULATION_START_S + run.departure_s, tuple(stops), yard_block,
        tuple(station or block_id for block_id, station in left))


@dataclass(frozen=True, slots=True)
class Progress:
    """How far one run has got."""

    status: str = QUEUED
    # The stop it is heading for or dwelling at, by index into the
    # plan's stops.
    leg: int = 0
    # Until when it dwells, in simulated seconds since midnight.
    dwell_until_s: float = 0.0


@dataclass(frozen=True, slots=True)
class Order:
    """Send a train toward a block, due there at ``due_s``."""

    train_id: str
    line: str
    block_id: str
    due_s: float


@dataclass(frozen=True, slots=True)
class Cancel:
    """Drop a train's order: its run is over."""

    train_id: str


Action = Order | Cancel


@dataclass(frozen=True, slots=True)
class World:
    """What the scheduler needs to know about the trains this step."""

    # Simulated seconds since midnight.
    now_s: float
    # Head block of each train the CTC is following, by train ID.
    heads: Mapping[str, str]
    # Trains with a dispatch order, by train ID, and the block it is to.
    orders: Mapping[str, str]
    # Trains the CTC lost track of.
    lost: frozenset[str]


class AutoDispatcher:
    """The plans of the loaded schedule and how far each run has got."""

    def __init__(self, plans: Sequence[RunPlan]) -> None:
        self.plans = tuple(sorted(
            plans, key=lambda p: (p.departure_s, p.line, p.train_id)))
        self.progress: dict[str, Progress] = {
            plan.train_id: Progress() for plan in self.plans}

    def step(self, world: World) -> list[Action]:
        """Advance every run one step; return the orders to give. Call
        only while automatic dispatch runs."""
        actions: list[Action] = []
        for plan in self.plans:
            progress = self.progress[plan.train_id]
            new, act = _advance(plan, progress, world)
            self.progress[plan.train_id] = new
            actions.extend(act)
        return actions

    def skip_stop(self, train_id: str) -> Action | None:
        """The order for a run's current stop was refused (its block is
        closed or closing): go on to the next stop instead."""
        plan = next(p for p in self.plans if p.train_id == train_id)
        progress = self.progress[train_id]
        new, act = _next_leg(plan, progress.leg + 1)
        if progress.status == IN_YARD and new.status == EN_ROUTE:
            new = replace(new, status=IN_YARD)    # it has not left yet
        self.progress[train_id] = new
        return act


def _advance(plan: RunPlan, progress: Progress,
             world: World) -> tuple[Progress, list[Action]]:
    train = plan.train_id
    status = progress.status
    if status == QUEUED:
        if world.now_s < plan.departure_s:
            return progress, []
        new, act = _next_leg(plan, 0)
        if new.status == EN_ROUTE:
            new = replace(new, status=IN_YARD)
        return new, [act] if act else []
    if status == IN_YARD:
        if train not in world.heads:
            if train in world.orders or train in world.lost:
                return progress, []
            # Its order went before it left the yard: give it again.
            new, act = _next_leg(plan, progress.leg)
            if new.status == EN_ROUTE:
                new = replace(new, status=IN_YARD)
            return new, [act] if act else []
        progress = replace(progress, status=EN_ROUTE)
        status = EN_ROUTE
    if status == EN_ROUTE:
        target = plan.stops[progress.leg].block_id
        if world.heads.get(train) == target:
            return replace(progress, status=DWELLING,
                           dwell_until_s=world.now_s + DWELL_S), []
        if train not in world.orders and train not in world.lost:
            # Its order went (the stop was closed): the next stop.
            new, act = _next_leg(plan, progress.leg + 1)
            return new, [act] if act else []
        return progress, []
    if status == DWELLING and world.now_s >= progress.dwell_until_s:
        new, act = _next_leg(plan, progress.leg + 1)
        return new, [act] if act else []
    if status == TO_YARD and train not in world.heads \
            and train not in world.lost:
        # Its blocks cleared at the yard entry: back in the yard.
        return replace(progress, status=DONE), [Cancel(train)]
    return progress, []


def _next_leg(plan: RunPlan, leg: int) -> tuple[Progress, Action | None]:
    """Head for stop ``leg``, or for the yard after the last stop."""
    if leg < len(plan.stops):
        stop = plan.stops[leg]
        return (Progress(EN_ROUTE, leg),
                Order(plan.train_id, plan.line, stop.block_id, stop.due_s))
    if plan.yard_block_id:
        return (Progress(TO_YARD, leg),
                Order(plan.train_id, plan.line, plan.yard_block_id,
                      plan.stops[-1].due_s + DWELL_S if plan.stops
                      else plan.departure_s))
    # Nowhere to go: it stays at its last stop, its run over.
    return Progress(DONE, leg), None
