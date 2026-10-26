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
- **The yard.** A run waits in the yard ("in yard") once its order is
  given. The model releases it when the yard exit block is free
  (D022); it has left once that block becomes occupied
  (``ctc.tracking``). Outside automatic mode, or while dispatch is
  paused, the schedule holds it in the yard. After its last stop it is
  sent to the line's yard entry block; the model retires it once it has
  stopped there, and once its block clears it is back in the yard and
  the run is done.
- **No head-on meets.** The runs must not be scheduled to meet head-on
  (asserted by Landis 2026-10-15; one that happens anyway is for the
  wayside controllers to handle). Where the runs' paths cross the same
  track in both directions (Green 77 to 85 and 13 to 28; Red 16 to
  52), that stretch is a two-way zone, reserved by direction, not by
  train (decided by Landis 2026-10-25):

  - Several trains may be in a zone at once if they all go through it
    the same way. A train is sent into a zone only when no other is in
    it, or has been sent into it, going the other way; until then it
    waits at its last stop, or in the yard ("held"). It has the zone
    until it has left it, and a zone that ends at the yard entry block
    until it is back in the yard.
  - A loop a train runs out and back through (Red 53 to 66) is not part
    of the zone: it is one way. A train that has turned is given its
    order on, but its authority stops a block short of the loop's end
    ("held" while it goes there and waits), clear of the switch out of
    the loop, which the trains it waits for need. It comes back into
    the zone from there once they are through. Then they come back
    together.
  - Once a train waits round a loop to come back into a zone,
    no train is sent into it the other way for the first time, even
    when due: the trains following it go round the loop, and the next
    runs wait in the yard.

  Following trains are kept apart by the authority rules, not here.

The dispatcher can pause automatic dispatch, and nothing advances
outside automatic mode: runs not yet due wait, and a train at a stop
stays there until dispatch resumes. Nor does anything on a line whose
Track Controller is not ready: no train may be dispatched on it.

This module decides; the model (``ctc.model``) applies its decisions as
dispatch orders, with the same safety checks as the dispatcher's own.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Collection, Mapping, Sequence

from ctc.tracking import YARD_ENTRIES, YARD_EXIT_FROM, YARD_EXITS

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
HELD = "held"              # a zone ahead is in use the other way
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
    # The whole way it goes: the yard exit block, then every block to
    # each stop in turn and on to the yard entry block.
    path: tuple[str, ...] = ()
    # Where in ``path`` each stop is, and the yard entry block (-1 if
    # it cannot get back).
    stop_indexes: tuple[int, ...] = ()
    yard_index: int = -1


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
    came_from = YARD_EXIT_FROM.get(run.line)
    left: list[tuple[str, str | None]] = []
    for stop in run.stops:
        if (stop.block_id in station_blocks
                and stop.block_id not in (b for b, _ in left)):
            left.append((stop.block_id, stop.station))
    due = SIMULATION_START_S + run.departure_s
    stops: list[PlannedStop] = []
    path: list[str] = [here] if here else []
    stop_indexes: list[int] = []
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
        path.extend(route[1:])
        stop_indexes.append(len(path) - 1)
        due += DWELL_S
        came_from = route[-2] if len(route) > 1 else came_from
        here = block_id
    yard_block = ""
    yard_index = -1
    for entry in sorted(YARD_ENTRIES.get(run.line, ())):
        route = (graph.route(here, entry, came_from=came_from)
                 if here else None)
        if route:
            yard_block = entry
            path.extend(route[1:])
            yard_index = len(path) - 1
            break
    return RunPlan(
        run.line, run.train_id, train_id_for(run.line, run.train_id),
        SIMULATION_START_S + run.departure_s, tuple(stops), yard_block,
        tuple(station or block_id for block_id, station in left),
        tuple(path), tuple(stop_indexes), yard_index)


def two_way_zones(paths: Sequence[Sequence[str]]) -> dict[str, str]:
    """The two-way zones of one line's run paths, as each zone's blocks
    mapped to the zone's name (its lowest block).

    A zone is the track the paths cross in both directions. A loop a
    path runs out and back through is not part of it: it is one way.
    """
    used = {edge for path in paths for edge in zip(path, path[1:])}
    parent: dict[str, str] = {}

    def find(block: str) -> str:
        parent.setdefault(block, block)
        while parent[block] != block:
            parent[block] = parent[parent[block]]
            block = parent[block]
        return block

    for a, b in used:
        if (b, a) in used:
            parent[find(a)] = find(b)
    members: dict[str, list[str]] = {}
    for block in parent:
        members.setdefault(find(block), []).append(block)
    zones: dict[str, str] = {}
    for blocks in members.values():
        name = min(blocks, key=lambda b: (len(b), b))
        zones.update((block, name) for block in blocks)
    return zones


def zone_spans(path: Sequence[str],
               zone_of: Mapping[str, str]) -> tuple[tuple[str, int, int],
                                                    ...]:
    """Each unbroken stretch of ``path`` within one zone, as (zone,
    first index, last index)."""
    spans = []
    index = 0
    while index < len(path):
        zone = zone_of.get(path[index])
        if zone is None:
            index += 1
            continue
        end = index
        while end + 1 < len(path) and zone_of.get(path[end + 1]) == zone:
            end += 1
        spans.append((zone, index, end))
        index = end + 1
    return tuple(spans)


def opposed(path_a: Sequence[str], span_a: tuple[str, int, int],
            path_b: Sequence[str], span_b: tuple[str, int, int]) -> bool:
    """Whether two passes through the same zone go opposite ways: one
    runs some stretch of track the other runs the other way."""
    if span_a[0] != span_b[0]:
        return False
    _, first, last = span_a
    edges = set(zip(path_a[first:last + 1], path_a[first + 1:last + 1]))
    _, first, last = span_b
    return any((b, a) in edges for a, b in
               zip(path_b[first:last + 1], path_b[first + 1:last + 1]))


@dataclass(frozen=True, slots=True)
class Progress:
    """How far one run has got."""

    status: str = QUEUED
    # The stop it is heading for, dwelling at, or held to go to, by
    # index into the plan's stops (one past the last: the yard).
    leg: int = 0
    # Until when it dwells, in simulated seconds since midnight.
    dwell_until_s: float = 0.0
    # How far along its path its head has been seen: an index into the
    # plan's path, -1 before it has left the yard.
    at: int = -1
    # Where along its path a held run has been sent to wait, round a
    # loop; -1 when it waits where it is.
    wait: int = -1


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
    # The lines whose Track Controller is ready: runs on any other line
    # wait where they are.
    ready_lines: frozenset[str]
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
        paths: dict[str, list[tuple[str, ...]]] = {}
        for plan in self.plans:
            paths.setdefault(plan.line, []).append(plan.path)
        #: Each line's two-way zones: block to zone name.
        self.zones: dict[str, dict[str, str]] = {
            line: two_way_zones(line_paths)
            for line, line_paths in paths.items()}
        self._spans = {
            plan.train_id: zone_spans(plan.path, self.zones[plan.line])
            for plan in self.plans}

    def step(self, world: World) -> list[Action]:
        """Advance every run one step; return the orders to give. Call
        only while automatic dispatch runs."""
        for plan in self.plans:
            self._locate(plan, world)
        actions: list[Action] = []
        for plan in self.plans:
            if plan.line not in world.ready_lines:
                continue
            progress = self.progress[plan.train_id]
            new, act = self._advance(plan, progress, world)
            self.progress[plan.train_id] = new
            actions.extend(act)
        return actions

    def hold_at(self, train_id: str) -> str | None:
        """The block a run's authority stops at while it waits round a
        loop to come back into a zone, or None."""
        progress = self.progress.get(train_id)
        if progress is None or progress.status != HELD or progress.wait < 0:
            return None
        plan = next(p for p in self.plans if p.train_id == train_id)
        return plan.path[progress.wait]

    def skip_stop(self, train_id: str) -> Action | None:
        """The order for a run's current stop was refused (its block is
        closed or closing): go on to the next stop instead."""
        plan = next(p for p in self.plans if p.train_id == train_id)
        progress = self.progress[train_id]
        if progress.status == HELD:
            # The leg it waits round a loop for was refused: it waits
            # where it is.
            self.progress[train_id] = replace(progress, wait=-1)
            return None
        new, act = self._release(plan, progress, progress.leg + 1)
        if progress.status == IN_YARD and new.status == EN_ROUTE:
            new = replace(new, status=IN_YARD)    # it has not left yet
        self.progress[train_id] = new
        return act

    # -- Where each train is ------------------------------------------

    def _locate(self, plan: RunPlan, world: World) -> None:
        """Move a run's place along its path up to where its head is."""
        progress = self.progress[plan.train_id]
        head = world.heads.get(plan.train_id)
        if head is None or progress.status in (QUEUED, DONE):
            return
        end = max(self._released_to(plan, progress), progress.at)
        for index in range(max(progress.at, 0), end + 1):
            if plan.path[index] == head:
                if index != progress.at:
                    self.progress[plan.train_id] = replace(progress,
                                                           at=index)
                return

    @staticmethod
    def _leg_target(plan: RunPlan, leg: int) -> int | None:
        """Where in its path a leg ends: a stop, the yard entry, or
        None when it has nowhere to go."""
        if leg < len(plan.stops):
            return plan.stop_indexes[leg]
        return plan.yard_index if plan.yard_block_id else None

    def _released_to(self, plan: RunPlan, progress: Progress) -> int:
        """How far along its path a run has been sent."""
        if progress.status in (IN_YARD, EN_ROUTE, TO_YARD):
            target = self._leg_target(plan, progress.leg)
            return progress.at if target is None else target
        if progress.status == DWELLING:
            return plan.stop_indexes[progress.leg]
        if progress.status == HELD:
            return max(progress.at, progress.wait)
        return -1

    # -- Two-way zones --------------------------------------------------

    def _held_spans(self, plan: RunPlan,
                    zone: str) -> list[tuple[str, int, int]]:
        """The passes through a zone a run is on, or has been sent on."""
        progress = self.progress[plan.train_id]
        if progress.status in (QUEUED, DONE):
            return []
        sent = self._released_to(plan, progress)
        return [span for span in self._spans[plan.train_id]
                if span[0] == zone and span[1] <= sent
                and progress.at <= span[2]]

    def _returns(self, plan: RunPlan, span: tuple[str, int, int]) -> bool:
        """Whether a pass comes back into a zone the run went through
        earlier on its way."""
        return any(name == span[0] and last < span[1]
                   for name, _, last in self._spans[plan.train_id])

    def _blocking(self, plan: RunPlan, progress: Progress,
                  target: int) -> tuple[str, int, int] | None:
        """The first zone pass a run would make on its way to
        ``target`` that it may not make yet, or None."""
        for span in self._spans[plan.train_id]:
            zone, first, _ = span
            if not progress.at < first <= target:
                continue
            returning = self._returns(plan, span)
            for other in self.plans:
                if other.train_id == plan.train_id or \
                        other.line != plan.line:
                    continue
                if any(opposed(plan.path, span, other.path, held)
                       for held in self._held_spans(other, zone)):
                    return span
                # A train waiting to come back has the zone next: no
                # other is sent into it the other way for the first time.
                waiting = self._waiting_span(other)
                if (not returning and waiting is not None
                        and waiting[0] == zone
                        and opposed(plan.path, span, other.path, waiting)):
                    return span
        return None

    def _waiting_span(self, plan: RunPlan) -> tuple[str, int, int] | None:
        """The zone pass a held run waits to make to come back, if it
        is at the end of a loop waiting to come back."""
        progress = self.progress[plan.train_id]
        if progress.status != HELD or progress.at < progress.wait \
                or progress.wait < 0:
            return None
        target = self._leg_target(plan, progress.leg)
        if target is None:
            return None
        for span in self._spans[plan.train_id]:
            if progress.at < span[1] <= target:
                return span if self._returns(plan, span) else None
        return None

    def _loop_end(self, plan: RunPlan, progress: Progress,
                  target: int) -> int | None:
        """Where a run that has turned waits before it comes back into a
        zone on its way to ``target``: round the loop it is going round,
        a block short of its end, so the block at the switch out of the
        loop stays clear for the trains it waits for to come in by. None
        if it is not coming back into one, or is already there."""
        for span in self._spans[plan.train_id]:
            if not progress.at < span[1] <= target:
                continue
            if not self._returns(plan, span):
                return None
            zone = self.zones[plan.line]
            loop_start = max(last for name, _, last in self._spans[
                plan.train_id] if name == span[0] and last < span[1]) + 1
            wait = span[1] - 1
            if wait - 1 >= loop_start and plan.path[wait - 1] not in zone:
                wait -= 1
            if wait > progress.at and plan.path[wait] not in zone:
                return wait
            return None
        return None

    def _release(self, plan: RunPlan, progress: Progress,
                 leg: int) -> tuple[Progress, Action | None]:
        """Send a run on its next leg, or hold it while a zone that leg
        enters is in use the other way. A run that has turned is sent
        round the loop to its last block first, and comes back into the
        zone from there."""
        target = self._leg_target(plan, leg)
        if target is None:
            new, act = _next_leg(plan, leg)
            return replace(new, at=progress.at), act
        held = replace(progress, status=HELD, leg=leg)
        wait = self._loop_end(plan, progress, target)
        if wait is not None:
            # Its order is the whole leg, so it is routed the way the
            # plan goes round the loop; its authority stops at the wait
            # (``hold_at``).
            if self._blocking(plan, progress, wait) is not None:
                return held, None
            if progress.wait == wait:
                return held, None
            _, order = _next_leg(plan, leg)
            return replace(held, wait=wait), order
        if self._blocking(plan, progress, target) is not None:
            return held, None
        new, act = _next_leg(plan, leg)
        return replace(new, at=progress.at), act

    # -- Each run's step ------------------------------------------------

    def _advance(self, plan: RunPlan, progress: Progress,
                 world: World) -> tuple[Progress, list[Action]]:
        train = plan.train_id
        status = progress.status
        if status == QUEUED:
            if world.now_s < plan.departure_s:
                return progress, []
            return self._out_of_yard(plan, progress, 0)
        if status == HELD:
            if train not in world.heads and progress.at < 0:
                return self._out_of_yard(plan, progress, progress.leg)
            new, act = self._release(plan, progress, progress.leg)
            return new, [act] if act else []
        if status == IN_YARD:
            if train not in world.heads:
                if train in world.orders or train in world.lost:
                    return progress, []
                # Its order went before it left the yard: give it again.
                return self._out_of_yard(plan, progress, progress.leg)
            progress = replace(progress, status=EN_ROUTE)
            status = EN_ROUTE
        if status == EN_ROUTE:
            target = plan.stops[progress.leg].block_id
            if world.heads.get(train) == target:
                return replace(progress, status=DWELLING,
                               dwell_until_s=world.now_s + DWELL_S), []
            if train not in world.orders and train not in world.lost:
                # Its order went (the stop was closed): the next stop.
                new, act = self._release(plan, progress, progress.leg + 1)
                return new, [act] if act else []
            return progress, []
        if status == DWELLING and world.now_s >= progress.dwell_until_s:
            new, act = self._release(plan, progress, progress.leg + 1)
            return new, [act] if act else []
        if status == TO_YARD and train not in world.heads \
                and train not in world.lost:
            # Its blocks cleared at the yard entry: back in the yard.
            return replace(progress, status=DONE), [Cancel(train)]
        return progress, []

    def _out_of_yard(self, plan: RunPlan, progress: Progress,
                     leg: int) -> tuple[Progress, list[Action]]:
        """Dispatch a run still in the yard, unless its way out is
        held."""
        new, act = self._release(plan, progress, leg)
        if new.status == EN_ROUTE:
            new = replace(new, status=IN_YARD)    # it has not left yet
        return new, [act] if act else []


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
