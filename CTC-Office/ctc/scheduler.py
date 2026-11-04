"""Automatic dispatch from a loaded schedule, for the CTC Office.

A schedule (``ctc.schedule``) lists, per line, the runs and each run's
timed stops. This module turns each run into a plan and, in automatic
mode, carries the plans out:

- **Scheduled stations only.** A run stops at the stations the file
  lists for it (blocks the track layout marks as stations, named or
  not) and nowhere else: it runs through every other station on its
  way without stopping. Blocks the file times that are not stations
  are not stops. (Confirmed by Landis 2026-10-14.)
- **File order.** A run visits its stations in the order the file lists
  them, whatever the track makes that cost: it runs from the yard to
  its first station without stopping, then on to each next one in turn,
  running through every station on the way, even one it stops at later
  (asserted by Landis 2026-11-03; it replaces track order from the yard,
  his first approach of 2026-10-14). It then returns to the yard. A
  station the track cannot reach from where the run is, it skips.
- **Due times.** Time zero is the moment the schedule starts: the
  simulation time when the clock runs with the schedule loaded, at Run,
  or at once if it is loaded while the clock is running, whatever the
  time is then (asserted by Landis 2026-11-03; it replaces the
  simulation start, 05:00:00). A run is due to leave the yard at time
  zero plus its departure offset in the file, so the runs keep the
  file's headway however late the schedule is loaded. Each stop is due
  when the run would reach it running every block at its speed limit,
  stopping ``DWELL_S`` at each stop before.
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
    it, or has been sent into it, going the other way. Until then it is
    "held": in the yard if that zone is the first on its way out
    (Landis 2026-11-03: the line does not fill up with trains queuing
    for it), else on the one-way track before the zone, a block short
    of it, or at its last stop when there is none. It has the zone
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

- **Passing sidings** (``PASSING_SIDINGS``, off for now). A run plans
  its way back over a parallel track where there is one (Red 72 to 76
  beside 28 to 32, 67 to 71 beside 39 to 43) rather than the track it
  went out on, so those stretches are one way each and the zones
  between them are short: trains going opposite ways pass there instead
  of waiting for the whole of Red 16 to 52 (Landis 2026-11-03). The
  model then keeps a run to its plan's way, and asks the Track
  Controller to set each switch for it (``route_requests``). It stays
  off until the Track Controller acts on those requests: today's Red
  programs set a switch only to let a train out of a siding.

The dispatcher can pause automatic dispatch, and nothing advances
outside automatic mode: runs not yet due wait, and a train at a stop
stays there until dispatch resumes. Nor does anything on a line whose
Track Controller is not ready: no train may be dispatched on it.

This module decides; the model (``ctc.model``) applies its decisions as
dispatch orders, with the same safety checks as the dispatcher's own.
"""

from __future__ import annotations

import heapq
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

#: Whether runs plan their way back over a parallel track where there
#: is one, so trains going opposite ways pass there (module docstring).
#: Off until the Track Controller sets switches for the CTC's route
#: requests.
PASSING_SIDINGS = False

#: With passing sidings, what running a block the run has already run
#: the other way costs on top of the block itself: enough to prefer a
#: parallel track of the same length, not a long detour.
REUSE_COST = 0.5

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


def leg_route(graph: TrackGraph, here: str, target: str,
              came_from: str | None,
              ran: Collection[tuple[str, str]] = ()
              ) -> tuple[str, ...] | None:
    """The way a run goes from ``here`` to ``target``: the shortest, or
    with ``PASSING_SIDINGS`` the cheapest, where running a stretch the
    run has already run the other way (``ran``: its path's steps so far)
    costs ``REUSE_COST`` more a block."""
    shortest = graph.route(here, target, came_from=came_from)
    if not PASSING_SIDINGS or shortest is None or not ran:
        return shortest
    start: tuple[str | None, str] = (came_from, here)
    best = {start: 0.0}
    back: dict[tuple[str | None, str],
               tuple[str | None, str] | None] = {start: None}
    queue: list[tuple[float, int, tuple[str | None, str]]] = [
        (0.0, 0, start)]
    count = 0
    while queue:
        cost, _, state = heapq.heappop(queue)
        if cost > best[state]:
            continue
        before, block = state
        if block == target:
            path = []
            step: tuple[str | None, str] | None = state
            while step is not None:
                path.append(step[1])
                step = back[step]
            return tuple(reversed(path))
        for after in graph.neighbors(block):
            if (graph.turns_back(before, block, after)
                    or not graph.can_run(block, after)):
                continue
            nxt = (block, after)
            total = cost + 1.0 + (REUSE_COST if (after, block) in ran
                                  else 0.0)
            if total < best.get(nxt, float("inf")):
                best[nxt] = total
                back[nxt] = state
                count += 1
                heapq.heappush(queue, (total, count, nxt))
    return shortest


def plan_run(run: ScheduledTrain, graph: TrackGraph,
             run_time_s: Callable[[tuple[str, ...]], float],
             station_blocks: Collection[str],
             start_s: float = SIMULATION_START_S) -> RunPlan:
    """Route a run to its scheduled stations in the order the file
    lists them, time them, and route the return to the yard.

    ``run_time_s`` is how long a route takes after its first block, and
    ``station_blocks`` the blocks of the run's line the track layout
    marks as stations. ``start_s`` is the schedule's time zero, in
    simulated seconds since midnight. Each leg carries on the way the
    train is going: it never turns back at a stop.
    """
    here = YARD_EXITS.get(run.line, "")
    came_from = YARD_EXIT_FROM.get(run.line)
    listed: list[tuple[str, str | None]] = []
    for stop in run.stops:
        if (stop.block_id in station_blocks
                and (not listed or listed[-1][0] != stop.block_id)):
            listed.append((stop.block_id, stop.station))
    left: list[tuple[str, str | None]] = []
    due = start_s + run.departure_s
    stops: list[PlannedStop] = []
    path: list[str] = [here] if here else []
    stop_indexes: list[int] = []
    for block_id, station in listed:
        route = (leg_route(graph, here, block_id, came_from,
                           set(zip(path, path[1:])))
                 if here else None)
        if route is None or len(route) < 2:
            # Unreachable from here (or where it already is): skipped.
            left.append((block_id, station))
            continue
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
        route = (leg_route(graph, here, entry, came_from,
                           set(zip(path, path[1:])))
                 if here else None)
        if route:
            yard_block = entry
            path.extend(route[1:])
            yard_index = len(path) - 1
            break
    return RunPlan(
        run.line, run.train_id, train_id_for(run.line, run.train_id),
        start_s + run.departure_s, tuple(stops), yard_block,
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
        self._plan = {plan.train_id: plan for plan in self.plans}
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
        """The block a run's authority stops at for now, or None: where
        it waits round a loop to come back into a zone, short of a zone it
        may not enter yet, or short of the zone after the next one, which
        it has not claimed yet."""
        progress = self.progress.get(train_id)
        if (progress is None or progress.wait < 0
                or progress.status not in (HELD, IN_YARD, EN_ROUTE, TO_YARD)):
            return None
        plan = next(p for p in self.plans if p.train_id == train_id)
        return plan.path[progress.wait]

    def planned_route(self, train_id: str,
                      head: str) -> tuple[str, ...] | None:
        """The way a run's plan goes from its head block to the end of
        its current leg, or None if it is not on its way along it. None
        too without ``PASSING_SIDINGS``: the model then routes it."""
        if not PASSING_SIDINGS:
            return None
        progress = self.progress.get(train_id)
        if progress is None or progress.status in (QUEUED, DONE):
            return None
        plan = self._plan[train_id]
        target = self._leg_target(plan, progress.leg)
        if target is None:
            return None
        for index in range(max(progress.at, 0), target + 1):
            if plan.path[index] == head:
                return plan.path[index:target + 1]
        return None

    def skip_stop(self, train_id: str) -> Action | None:
        """The order for a run's current stop was refused (its block is
        closed): go on to the next stop instead."""
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
            sent = progress.at if target is None else target
            if progress.wait >= 0:
                sent = max(progress.at, min(sent, progress.wait))
            return sent
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
        """Whether a pass comes back into the zone the run has just
        left: its last zone pass was through the same zone, so it has
        turned round a loop in between (not gone round the line)."""
        spans = self._spans[plan.train_id]
        index = spans.index(span)
        return index > 0 and spans[index - 1][0] == span[0]

    def _loop_room(self, plan: RunPlan,
                   span: tuple[str, int, int]) -> int | None:
        """How many trains the loop a zone pass leads into holds, a
        block apart and the first a block short of its end; None if the
        run does not come back through the zone after it."""
        later = [other for other in self._spans[plan.train_id]
                 if other[0] == span[0] and other[1] > span[2]]
        if not later or not self._returns(plan, later[0]):
            return None
        return max(1, (later[0][1] - span[2] - 1) // 2)

    def _in_loop(self, plan: RunPlan, zone: str) -> bool:
        """Whether a run has been sent into a zone on its way into a
        loop and has not yet come back into the zone."""
        progress = self.progress[plan.train_id]
        if progress.status in (QUEUED, DONE):
            return False
        sent = self._released_to(plan, progress)
        spans = [s for s in self._spans[plan.train_id] if s[0] == zone]
        for out, back in zip(spans, spans[1:]):
            if (self._returns(plan, back) and out[1] <= sent
                    and progress.at < back[1]):
                return True
        return False

    def _blocked(self, plan: RunPlan, span: tuple[str, int, int]) -> bool:
        """Whether a run may not make a zone pass yet: another train is
        in the zone, or has been sent into it, going the other way, or
        waits round a loop to come back into it the other way; or the
        pass leads into a loop that has no room left for it."""
        zone = span[0]
        returning = self._returns(plan, span)
        room = None if returning else self._loop_room(plan, span)
        if room is not None and sum(
                self._in_loop(other, zone) for other in self.plans
                if other.line == plan.line
                and other.train_id != plan.train_id) >= room:
            return True
        for other in self.plans:
            if other.train_id == plan.train_id or other.line != plan.line:
                continue
            if any(opposed(plan.path, span, other.path, held)
                   for held in self._held_spans(other, zone)):
                return True
            # A train waiting to come back has the zone next: no other
            # is sent into it the other way for the first time.
            waiting = self._waiting_span(other)
            if (not returning and waiting is not None
                    and waiting[0] == zone
                    and opposed(plan.path, span, other.path, waiting)):
                return True
        return False

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

    def _loop_wait(self, plan: RunPlan,
                   span: tuple[str, int, int]) -> int | None:
        """Where a run that has turned waits before it comes back into a
        zone: round the loop, a block short of its end, so the block at
        the switch out of the loop stays clear for the trains it waits
        for to come in by. None if there is no room out of the zone."""
        zone = self.zones[plan.line]
        spans = self._spans[plan.train_id]
        loop_start = spans[spans.index(span) - 1][2] + 1
        wait = span[1] - 1
        if wait - 1 >= loop_start and plan.path[wait - 1] not in zone:
            wait -= 1
        return wait if plan.path[wait] not in zone else None

    def _wait_before(self, plan: RunPlan, progress: Progress,
                     span: tuple[str, int, int]) -> int | None:
        """Where a run waits short of a zone pass: on the one-way track
        before it, a block short of the zone where there is room. None
        to wait where it is: there is no such track ahead of it, or it
        is still in the yard and the zone is the first on its way."""
        zone = self.zones[plan.line]
        if progress.at < 0 and not any(
                first < span[1]
                for _, first, _ in self._spans[plan.train_id]):
            return None
        start = max(progress.at, 0)
        for wait in (span[1] - 2, span[1] - 1):
            if wait >= start and all(plan.path[i] not in zone
                                     for i in range(wait, span[1])):
                return wait
        return None

    def _reach(self, plan: RunPlan, progress: Progress, target: int,
               sent: int) -> tuple[int | None, bool]:
        """How far along its path a run may go now on its way to
        ``target``, and whether it is held there.

        It makes the zone passes ahead in turn. It claims a pass only
        when it is next and nothing blocks it, and goes no further than
        the one-way track before the pass after that, so it never holds
        a zone it is still far from. A pass back into a zone it went
        through earlier it makes from the end of the loop it turned
        round, held there until the zone is free. A blocked pass holds
        it short of the zone (``_wait_before``). None: it may not move.
        A pass it has been sent into already (up to ``sent``) is its own.
        """
        claimed = False
        for span in self._spans[plan.train_id]:
            if not progress.at < span[1] <= target:
                continue
            if span[1] <= sent:
                claimed = True
                continue
            if self._returns(plan, span):
                wait = self._loop_wait(plan, span)
                if wait is not None and wait > progress.at:
                    # On its way round the loop: not held until it is
                    # at the end and the zone is not free.
                    return wait, False
                if self._blocked(plan, span):
                    # At the loop's end: it waits there.
                    return (progress.at if wait is not None
                            else self._wait_before(plan, progress, span)), True
            elif self._blocked(plan, span):
                return self._wait_before(plan, progress, span), True
            if claimed:
                wait = self._wait_before(plan, progress, span)
                if wait is not None:
                    return wait, False
            claimed = True
        return target, False

    def _release(self, plan: RunPlan, progress: Progress,
                 leg: int) -> tuple[Progress, Action | None]:
        """Send a run on its next leg as far as it may go now (``_reach``),
        or hold it. Its order is the whole leg, so it is routed the way
        its plan goes; a wait short of the leg's end limits its
        authority (``hold_at``). A run already sent on this leg gets no
        new order."""
        target = self._leg_target(plan, leg)
        if target is None:
            new, act = _next_leg(plan, leg)
            return replace(new, at=progress.at), act
        ordered = progress.leg == leg and (
            progress.status in (IN_YARD, EN_ROUTE, TO_YARD)
            or (progress.status == HELD and progress.wait >= 0))
        sent = (self._released_to(plan, progress) if ordered
                else progress.at)
        reach, held = self._reach(plan, progress, target, sent)
        if reach is None:
            # It may not move: one already sent stops where it has got
            # to; one at a stop, or in the yard, stays there.
            stay = progress.at if ordered and progress.at >= 0 else -1
            return replace(progress, status=HELD, leg=leg, wait=stay), None
        new, order = _next_leg(plan, leg)
        new = replace(new, at=progress.at,
                      wait=-1 if reach == target else reach)
        if held:
            new = replace(new, status=HELD)
        return new, None if ordered else order

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
                return replace(progress, status=DWELLING, wait=-1,
                               dwell_until_s=world.now_s + DWELL_S), []
            if train not in world.orders and train not in world.lost:
                # Its order went (the stop was closed): the next stop.
                new, act = self._release(plan, progress, progress.leg + 1)
                return new, [act] if act else []
            if progress.wait >= 0:
                # Short of its stop for now: on as far as it may go.
                new, act = self._release(plan, progress, progress.leg)
                return new, [act] if act else []
            return progress, []
        if status == TO_YARD and progress.wait >= 0 \
                and train in world.heads:
            new, act = self._release(plan, progress, progress.leg)
            return new, [act] if act else []
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
