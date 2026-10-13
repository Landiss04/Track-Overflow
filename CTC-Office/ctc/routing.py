"""Track connectivity and authority counting for the CTC Office.

Authority is the number of blocks ahead of a train's current block that
it may still enter (decision D013, proposed on ``ctc-interfacing``). The
CTC recomputes it every step: the count runs along the train's route
toward its destination and ends at the earliest of the destination, the
block before the first occupied, closed, closing or failed block, and
the block before a switch not reported set for the route
(``authority-stops-before-obstruction``, proposed on ``ctc-interfacing``).
No block is within two trains' authorities (``exclusive-authority``):
another train's blocks stop the count too.

The route is the shortest path a train can run through the layout
files in ``TrackModel/``. Connections come from the files alone:

- Blocks listed next to each other in a file are joined, except where
  both are the far end of a switch connection (Green 100 and 101 are
  not joined: 100 joins 85, and 101 joins 77).
- Each switch joins the blocks of its connections. Normal is the first
  connection listed, reverse the second. Connections to the yard are
  left out: the yard is a black box.

Every block has two ends: its low end, toward lower block numbers, and
its high end. A neighbor joins at one of them: the block before it in
the file at the low end, the block after at the high end, and a
switch's far block at the same end as the switch's other connection
(Green 1 joins 13 where 12 does, at 13's low end). Then:

- A train leaves a block by the other end from the one it came in by,
  so it never turns back, nor passes from one connection of a switch
  straight into the other (Green 12 -> 13 -> 1).
- Each block's direction of travel is kept: a train moves on only to a
  block its ``next_blocks`` lists (``ctc.track_layout``). A line whose
  file lists none is run both ways. Every listed next block must be one
  the layout joins to it.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass
from typing import Collection, Mapping

from ctc.interface import SwitchPosition
from ctc.track_layout import Line

_POSITIONS: tuple[SwitchPosition, ...] = ("normal", "reverse")
_YARD = "yard"
_LOW, _HIGH = "low", "high"

#: What one reversal costs, in blocks, when searching for a route that
#: may reverse: a route reverses as few times as it can.
REVERSAL_COST = 10


@dataclass(frozen=True, slots=True)
class SwitchLeg:
    """One connection of a switch: the position that makes it."""

    switch_id: str
    position: SwitchPosition


@dataclass(frozen=True, slots=True)
class AuthorityLimit:
    """A train's authority and where it runs out."""

    # Blocks ahead of the current block the train may still enter.
    blocks: int
    # The last block it may enter: its own block when ``blocks`` is 0.
    end_block_id: str
    # Why the count ends there: "destination", "occupied", "closed",
    # "closing", "failed", "reserved", "switch" or "no route". With
    # ``keep``, also "granted": the end of the part of an earlier grant
    # the train still has. The CTC uses that one internally only; it
    # never reaches a TrainAuthority.
    reason: str
    # The block or switch the reason names; "" for "destination" and
    # "no route".
    at: str = ""
    # The route counted along: the train's own block first, then every
    # block to the destination. The first ``blocks`` after the train's
    # own are within authority. Empty for "no route".
    route: tuple[str, ...] = ()
    # For "reserved": the train whose authority holds the block.
    held_by: str = ""
    # Where the train would have to reverse to get round what blocks
    # its route, when nothing else gets it there; "" otherwise. The CTC
    # does not reverse trains: the train waits.
    reverse_at: str = ""


def _legs(switch: str) -> list[tuple[str, str] | None]:
    """A switch's connections in listed order, as block ID pairs; None
    for a connection to the yard. ``"12-13; 1-13"`` gives
    ``[("12", "13"), ("1", "13")]``."""
    legs: list[tuple[str, str] | None] = []
    for part in switch.split(";"):
        ends = [end.strip() for end in part.split("-")]
        if len(ends) != 2 or not all(ends):
            raise ValueError(f"unreadable switch connection {part!r} "
                             f"in {switch!r}")
        if any(end.lower() == _YARD for end in ends):
            legs.append(None)
        else:
            legs.append((ends[0], ends[1]))
    return legs


class TrackGraph:
    """How the blocks of one line connect."""

    def __init__(self, line: Line) -> None:
        self.line = line.name
        order = [block.block_id for block in line.blocks]
        index = {block_id: i for i, block_id in enumerate(order)}
        self._order = index
        self._neighbors: dict[str, set[str]] = {b: set() for b in order}
        # Switch connections, keyed by the (unordered) pair they join.
        self._legs: dict[frozenset[str], SwitchLeg] = {}
        # (block, neighbor) -> the end of ``block`` the neighbor joins.
        self._ends: dict[tuple[str, str], str] = {}
        # block -> the blocks a train in it may move on to; absent when
        # the file does not say (any neighbor will do).
        self._next: dict[str, frozenset[str]] = {
            block.block_id: frozenset(block.next_blocks)
            for block in line.blocks if block.next_blocks is not None}

        switches: list[tuple[str, list[tuple[str, str]]]] = []
        far_ends: set[str] = set()
        for block in line.blocks:
            if not block.switch:
                continue
            legs = []
            for position, leg in zip(_POSITIONS, _legs(block.switch)):
                if leg is None:
                    continue
                a, b = leg
                for end in leg:
                    if end not in index:
                        raise ValueError(
                            f"{line.name} switch {block.block_id} names "
                            f"block {end!r}, which the line does not have")
                self._legs[frozenset(leg)] = SwitchLeg(block.block_id,
                                                       position)
                self._join(a, b)
                legs.append(leg)
                if not self._next_in_file(a, b):
                    far_ends.update(leg)
            switches.append((block.block_id, legs))

        for a, b in zip(order, order[1:]):
            if not (a in far_ends and b in far_ends):
                self._join(a, b)
        # Neighbors in the file join at the low or high end.
        for a, b in zip(order, order[1:]):
            if b in self._neighbors[a]:
                self._ends[(a, b)] = _HIGH
                self._ends[(b, a)] = _LOW
        for switch_id, legs in switches:
            self._place_far_legs(f"{line.name} switch {switch_id}", legs)
        for block_id, nexts in self._next.items():
            for after in sorted(nexts - self._neighbors[block_id]):
                raise ValueError(
                    f"{line.name} block {block_id} lists next block "
                    f"{after!r}, which the layout does not join to it")

    def _next_in_file(self, a: str, b: str) -> bool:
        return abs(self._order[a] - self._order[b]) == 1

    def _place_far_legs(self, what: str,
                        legs: list[tuple[str, str]]) -> None:
        """Ends for a switch's far connection: at the block both
        connections share, the end its other connection joins; at the
        far block, its free end."""
        far = [leg for leg in legs if not self._next_in_file(*leg)]
        if not far:
            return
        near = [leg for leg in legs if self._next_in_file(*leg)]
        shared = set(legs[0]).intersection(*legs[1:])
        if len(legs) != 2 or len(near) != 1 or len(shared) != 1:
            raise ValueError(f"{what}: expected one connection to a "
                             "neighboring block and one far connection, "
                             "sharing a block")
        (hub,) = shared
        (partner,) = [b for b in near[0] if b != hub]
        (far_block,) = [b for b in far[0] if b != hub]
        used = {self._ends[(far_block, n)]
                for n in self._neighbors[far_block]
                if (far_block, n) in self._ends}
        free = {_LOW, _HIGH} - used
        if len(free) != 1:
            raise ValueError(f"{what}: block {far_block} has no free end")
        self._ends[(hub, far_block)] = self._ends[(hub, partner)]
        self._ends[(far_block, hub)] = free.pop()

    def _join(self, a: str, b: str) -> None:
        self._neighbors[a].add(b)
        self._neighbors[b].add(a)

    def neighbors(self, block_id: str) -> tuple[str, ...]:
        """Blocks joined to this one, in file order."""
        return tuple(sorted(self._neighbors[block_id],
                            key=self._order.__getitem__))

    def leg(self, a: str, b: str) -> SwitchLeg | None:
        """The switch connection joining two blocks, if it is one."""
        return self._legs.get(frozenset((a, b)))

    def end(self, block_id: str, neighbor: str) -> str:
        """The end of ``block_id`` ("low" or "high") ``neighbor`` joins."""
        return self._ends[(block_id, neighbor)]

    def can_run(self, here: str, after: str) -> bool:
        """Whether the direction of travel lets a train run from
        ``here`` into ``after``: ``here`` lists it as a next block, or
        lists none."""
        nexts = self._next.get(here)
        return nexts is None or after in nexts

    def turns_back(self, before: str | None, here: str,
                   after: str) -> bool:
        """Whether running ``before`` -> ``here`` -> ``after`` reverses
        in ``here``: leaves it by the end it came in by."""
        return (before is not None
                and self._ends[(here, before)] == self._ends[(here, after)])

    def route(self, start: str, destination: str,
              avoid: Collection[str] = ()) -> tuple[str, ...] | None:
        """The blocks from ``start`` to ``destination``, both included,
        by the shortest path a train can run; None if there is none.
        With ``avoid``, the path enters none of those blocks."""
        if start not in self._neighbors or destination not in self._neighbors:
            return None
        if destination in avoid:
            return None
        if start == destination:
            return (start,)
        # Search over (previous block, block) so that turning back can
        # be ruled out.
        first: tuple[str | None, str] = (None, start)
        came_from: dict[tuple[str | None, str],
                        tuple[str | None, str] | None] = {first: None}
        queue = deque([first])
        while queue:
            state = queue.popleft()
            before, here = state
            for after in self.neighbors(here):
                if (after in avoid
                        or self.turns_back(before, here, after)
                        or not self.can_run(here, after)):
                    continue
                nxt = (here, after)
                if nxt in came_from:
                    continue
                came_from[nxt] = state
                if after == destination:
                    path = [after]
                    back: tuple[str | None, str] | None = state
                    while back is not None:
                        path.append(back[1])
                        back = came_from[back]
                    return tuple(reversed(path))
                queue.append(nxt)
        return None


def reversing_route(graph: TrackGraph, start: str, destination: str,
                    avoid: Collection[str] = ()) -> tuple[str, ...] | None:
    """The route from ``start`` to ``destination`` if the train may
    reverse (in a block it is allowed to leave by the end it came in),
    each reversal costing ``REVERSAL_COST`` blocks; None if there is
    none. Directions of travel still hold."""
    if destination in avoid or start == destination:
        return None if destination in avoid else (start,)
    first: tuple[str | None, str] = (None, start)
    best = {first: 0}
    came_from: dict[tuple[str | None, str],
                    tuple[str | None, str] | None] = {first: None}
    queue: list[tuple[int, int, tuple[str | None, str]]] = [(0, 0, first)]
    tie = 1
    while queue:
        cost, _, state = heapq.heappop(queue)
        if cost > best[state]:
            continue
        before, here = state
        if here == destination:
            path = []
            back: tuple[str | None, str] | None = state
            while back is not None:
                path.append(back[1])
                back = came_from[back]
            return tuple(reversed(path))
        for after in graph.neighbors(here):
            if after in avoid or not graph.can_run(here, after):
                continue
            step = 1 + (REVERSAL_COST if graph.turns_back(before, here, after)
                        else 0)
            nxt = (here, after)
            if cost + step < best.get(nxt, cost + step + 1):
                best[nxt] = cost + step
                came_from[nxt] = state
                heapq.heappush(queue, (cost + step, tie, nxt))
                tie += 1
    return None


def first_reversal(graph: TrackGraph, route: tuple[str, ...]) -> str:
    """The first block on ``route`` where the train reverses, or ""."""
    for before, here, after in zip(route, route[1:], route[2:]):
        if graph.turns_back(before, here, after):
            return here
    return ""


def build_graphs(lines: Mapping[str, Line]) -> dict[str, TrackGraph]:
    """One ``TrackGraph`` per line, keyed by line name."""
    return {name: TrackGraph(line) for name, line in lines.items()}


def authority(graph: TrackGraph, start: str, destination: str,
              obstructions: Mapping[str, str],
              switches: Mapping[str, SwitchPosition],
              reserved: Mapping[str, str] | None = None,
              keep: Collection[str] | None = None,
              route: tuple[str, ...] | None = None) -> AuthorityLimit:
    """Count a train's authority along its route.

    ``obstructions`` maps a block ID to why no train may enter it
    ("occupied", "closed", "closing" or "failed"); the train's own block
    may be listed and is ignored. ``switches`` maps a switch ID to its
    reported position; a switch not listed counts as not set.
    ``reserved`` maps a block ID to the other train whose authority
    holds it. With ``keep``, the count also stops at the first block
    not in it: the part of an earlier grant the train still has.
    ``route``, if given, is the path to count along (from ``start`` to
    ``destination``); otherwise the shortest one is taken.
    """
    path = route if route is not None else graph.route(start, destination)
    if path is None:
        return AuthorityLimit(0, start, "no route")
    reserved = reserved or {}
    here = start
    for count, after in enumerate(path[1:]):
        leg = graph.leg(here, after)
        if leg is not None and switches.get(leg.switch_id) != leg.position:
            return AuthorityLimit(count, here, "switch", leg.switch_id,
                                  path)
        reason = obstructions.get(after)
        if reason is not None:
            return AuthorityLimit(count, here, reason, after, path)
        holder = reserved.get(after)
        if holder is not None:
            return AuthorityLimit(count, here, "reserved", after, path,
                                  holder)
        if keep is not None and after not in keep:
            return AuthorityLimit(count, here, "granted", after, path)
        here = after
    return AuthorityLimit(len(path) - 1, destination, "destination",
                          route=path)
