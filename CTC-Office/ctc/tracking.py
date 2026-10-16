"""Following trains from block occupancy, for the CTC Office.

The Track Controller reports only which blocks are occupied: no train
IDs, no positions within a block, no speeds, and a failed block reports
occupied like any other (``block-occupancy``, proposed on
``ctc-deployment``). The CTC Office works out where its trains are, and
which occupied blocks are failures, by comparing each occupancy update
with the last, its trains' routes and the speeds it suggested
(``train-tracking-from-occupancy``, proposed on ``ctc-deployment``):

- Leaving the yard: when a line's yard exit block becomes occupied while
  trains dispatched on that line wait in the yard, the most urgent of
  them has left the yard into it.
- Moving: a train moves into the next block of its route, if its
  authority lets it in, when that block becomes occupied, and leaves a
  block when it clears; while crossing a boundary it holds both blocks.
- Too early is a failure: the next block becoming occupied before the
  train could have covered ``MIN_REACH_FRACTION`` of its own block is a
  failure, not the train. How far it could have gone assumes it went as
  fast as the CTC ever suggested and slowed no faster than braking
  allows, since it may carry speed from an earlier, faster block.
- Unexplained occupancy is a failure. A failure ends when its block
  clears.
- A train whose blocks all clear is dropped quietly ("lost"), unless it
  was at a block that runs into the yard: then it has gone back into the
  yard and may leave it again.

This module only tracks. What a failure means for authority and routes
is the model's business.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

#: The block a train leaves the yard into, per line (Green's layout file
#: lists ``Yard-63``; Red's yard joins block 9).
YARD_EXITS: dict[str, str] = {"Green": "63", "Red": "9"}

#: Blocks a train can run from into the yard, per line (Green's 57 lists
#: ``yard`` among its next blocks; Red's yard joins block 9).
YARD_ENTRIES: dict[str, frozenset[str]] = {
    "Green": frozenset({"57"}), "Red": frozenset({"9"})}

#: The next block becoming occupied before a train could have covered
#: this share of its own block is a failure: the margin is a train
#: going twice as fast as it could have.
MIN_REACH_FRACTION = 0.5

Block = tuple[str, str]          # (line, block ID)


@dataclass(frozen=True, slots=True)
class Tracked:
    """One train the CTC Office is following."""

    line: str
    # The blocks it holds, tail first, head last: one, or two while it
    # crosses a block boundary.
    blocks: tuple[str, ...]
    # The furthest its head could have gone into its head block, in m.
    reach_m: float = 0.0
    # The fastest it could be going now, in m/s.
    speed_mps: float = 0.0
    # The block its head entered its head block from: which way it is
    # going. None until it has moved a block (placed, or just out of
    # the yard).
    came_from: str | None = None

    @property
    def head(self) -> str:
        return self.blocks[-1]


@dataclass(frozen=True, slots=True)
class Plan:
    """What a tracked train was told at the last step."""

    # The next block on its route, or None when it may not go on (no
    # authority, at its destination, or no route).
    next_block: str | None
    # The length of its head block, in m.
    head_length_m: float
    # The speed suggested to it, in m/s.
    speed_mps: float


@dataclass(frozen=True, slots=True)
class Waiting:
    """A train dispatched on a line and waiting in the yard."""

    train_id: str
    line: str


class TrainTracker:
    """Where each train is, from occupancy alone; see the module notes.

    Not thread safe and not a boundary type: the model owns one.
    """

    def __init__(self, braking_mps2: float) -> None:
        # How fast a train slows when told to, at the least.
        self._braking_mps2 = braking_mps2
        self.trains: dict[str, Tracked] = {}
        # Blocks inferred to have failed, until they clear.
        self.failures: set[Block] = set()
        # Trains dropped quietly; never taken to have left the yard.
        self.lost: set[str] = set()
        self._occupied: frozenset[Block] = frozenset()
        self._now_s = 0.0

    def place(self, train_id: str, line: str, block_id: str) -> None:
        """Track a train at a block, standing at its start: for tests and
        for seeding a scenario."""
        self.trains[train_id] = Tracked(line, (block_id,))
        self.lost.discard(train_id)
        self.failures.discard((line, block_id))

    def update(self, occupied: frozenset[Block], now_s: float,
               plans: Mapping[str, Plan],
               waiting: Sequence[Waiting]) -> None:
        """Apply one occupancy update.

        ``plans`` are what the tracked trains were told at the last
        step, which they have run on since; ``waiting`` the trains
        waiting in the yard, most urgent first.
        """
        dt = max(0.0, now_s - self._now_s)
        self._now_s = now_s
        new = occupied - self._occupied
        cleared = self._occupied - occupied
        self.failures -= cleared

        # How far each train could have gone since the last update.
        for train_id, train in self.trains.items():
            plan = plans.get(train_id)
            told = plan.speed_mps if plan is not None else 0.0
            fastest = max(told, train.speed_mps)
            self.trains[train_id] = replace(
                train, reach_m=train.reach_m + fastest * dt,
                speed_mps=max(told,
                              train.speed_mps - self._braking_mps2 * dt))

        claimed: set[Block] = set()
        for train_id in sorted(self.trains):
            train = self.trains[train_id]
            plan = plans.get(train_id)
            if plan is None or plan.next_block is None:
                continue
            ahead = (train.line, plan.next_block)
            if ahead not in new or ahead in claimed:
                continue
            if train.reach_m < MIN_REACH_FRACTION * plan.head_length_m:
                continue                    # too early: not this train
            self.trains[train_id] = replace(
                train, blocks=train.blocks + (plan.next_block,),
                reach_m=0.0, came_from=train.head)
            claimed.add(ahead)

        held = {(t.line, b) for t in self.trains.values() for b in t.blocks}
        for line, exit_block in YARD_EXITS.items():
            if (line, exit_block) not in new or (line, exit_block) in held:
                continue
            for candidate in waiting:
                if (candidate.line == line
                        and candidate.train_id not in self.trains
                        and candidate.train_id not in self.lost):
                    self.trains[candidate.train_id] = Tracked(
                        line, (exit_block,))
                    claimed.add((line, exit_block))
                    break

        for train_id in sorted(self.trains):
            train = self.trains[train_id]
            left = tuple(b for b in train.blocks
                         if (train.line, b) not in cleared)
            if left == train.blocks:
                continue
            if left:
                self.trains[train_id] = replace(train, blocks=left)
                continue
            del self.trains[train_id]
            if train.head not in YARD_ENTRIES.get(train.line, ()):
                self.lost.add(train_id)     # dropped quietly

        held = {(t.line, b) for t in self.trains.values() for b in t.blocks}
        self.failures |= {block for block in new
                          if block not in claimed and block not in held}
        self._occupied = occupied
