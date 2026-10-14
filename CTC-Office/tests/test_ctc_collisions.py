"""Randomized check that the CTC Office never lets trains collide, and
follows its trains from occupancy alone.

Trains run at no more than their suggested speed, toward random
destinations, entering a block only within their authority and holding
both blocks for one step while they cross a boundary. More trains leave
the yard, failures come and go on blocks no train is about to enter, and
switches change position under no train and no authority. The CTC is
given occupancy only. At every step no block may be within two trains'
authorities, no train may be authorized into an occupied block, no two
trains (or a train and a failure) may share a block, and the CTC must
have every train where it really is.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import SwitchReport  # noqa: E402
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.track_layout import load_layout  # noqa: E402
from ctc.tracking import YARD_EXITS  # noqa: E402
from tests.occupancy import reports  # noqa: E402

_LAYOUT = load_layout()
_ON_TRACK = 4                    # trains placed on the track at the start
_IN_YARD = 2                     # trains that leave the yard later
_STEPS = 300
_DT_S = 1.0
_SEEDS = range(4)


def _first_problem(seed: int, line: str) -> str | None:
    rng = random.Random(seed)
    lengths = {b.block_id: b.length_m for b in _LAYOUT[line].blocks}
    blocks = list(lengths)
    switch_ids = _LAYOUT[line].switch_ids()
    exit_block = YARD_EXITS[line]
    ctc = StubCtcOffice()
    # Blocks each train holds, tail first; how far into its head block
    # it is; and how much of its suggested speed it runs at.
    trains: dict[str, list[str]] = {}
    progress: dict[str, float] = {}
    pace: dict[str, float] = {}

    def occupied_by_trains() -> set[str]:
        return {b for held in trains.values() for b in held}

    for n in range(_ON_TRACK):
        train_id = f"T{n}"
        start = rng.choice([b for b in blocks if b not in
                            occupied_by_trains() | {exit_block}])
        trains[train_id], progress[train_id] = [start], 0.0
        pace[train_id] = rng.uniform(0.6, 1.0)
        ctc.place_train(train_id, line, start)
        ctc.dispatch(train_id, line, rng.choice(blocks))
    for n in range(_ON_TRACK, _ON_TRACK + _IN_YARD):
        ctc.dispatch(f"T{n}", line, rng.choice(blocks))
    switches = {s: rng.choice(("normal", "reverse")) for s in switch_ids}
    # Failed blocks, and how many steps each lasts.
    failures: dict[str, int] = {}
    # What the CTC was last told is occupied.
    reported: set[str] = set()

    for step in range(_STEPS):
        where = f"seed {seed} {line} step {step}"
        snap = ctc.snapshot()
        authorized = {b for a in snap.authorities
                      for b in a.route[:a.blocks + 1]}
        taken = occupied_by_trains() | set(failures) | authorized
        # The Track Controller throws a switch under no train and no
        # authority.
        if step % 15 == 0:
            for s in switch_ids:
                if s not in taken and rng.random() < 0.5:
                    switches[s] = rng.choice(("normal", "reverse"))
        # A failure where no train is or may go; it clears later.
        if step % 10 == 5 and rng.random() < 0.5:
            spare = [b for b in blocks if b not in taken]
            if spare:
                failures[rng.choice(spare)] = rng.randint(5, 30)
        # The yard lets the next train out onto an exit block that was
        # clear at the last report too.
        waiting = sorted(o.train_id for o in snap.orders
                         if o.train_id not in trains)
        released = (step % 20 == 10 and waiting
                    and exit_block not in taken | reported)
        if released:
            trains["?"], progress["?"], pace["?"] = [exit_block], 0.0, 0.8

        reported = occupied_by_trains() | set(failures)
        out = ctc.step(_DT_S, reports(
            occupied=[(line, b) for b in reported],
            switches=[SwitchReport(line, s, p)
                      for s, p in switches.items()]))
        snap = ctc.snapshot()
        followed = {t.train_id: list(t.blocks) for t in snap.trains}
        if released:
            # The yard sent the train the CTC took to have left.
            (taken_out,) = [t for t, held in followed.items()
                            if held == [exit_block] and t not in trains]
            trains[taken_out] = trains.pop("?")
            progress[taken_out] = progress.pop("?")
            pace[taken_out] = pace.pop("?")

        if followed != trains:
            return f"{where}: the CTC has {followed}, trains are {trains}"
        if snap.lost_trains:
            return f"{where}: lost {snap.lost_trains}"
        occupied = occupied_by_trains() | set(failures)
        held: dict[str, str] = {}
        for a in snap.authorities:
            for block in a.route[1:a.blocks + 1]:
                if block in held:
                    return (f"{where}: block {block} in the authority of "
                            f"{held[block]} and {a.train_id}")
                if block in occupied:
                    return (f"{where}: {a.train_id} authorized into "
                            f"occupied block {block}")
                held[block] = a.train_id

        # The trains run until the next step.
        speeds = {s.train_id: s.suggested_speed_mps
                  for s in out.track_controller.suggestions}
        limits = {a.train_id: a for a in snap.authorities}
        for train_id in sorted(trains):
            blocks_held = trains[train_id]
            if len(blocks_held) > 1:
                blocks_held.pop(0)              # its tail clears
                continue
            limit = limits.get(train_id)
            length = lengths[blocks_held[-1]]
            progress[train_id] = min(
                length, progress[train_id]
                + speeds.get(train_id, 0) * pace[train_id] * _DT_S)
            if progress[train_id] >= length and limit and limit.blocks:
                blocks_held.append(limit.route[1])
                progress[train_id] = 0.0
            elif limit and limit.reason == "destination" \
                    and limit.blocks == 0:
                ctc.dispatch(train_id, line, rng.choice(blocks))
        for block in list(failures):
            failures[block] -= 1
            if failures[block] == 0:
                del failures[block]

        everything = [b for held in trains.values() for b in held]
        if len(set(everything)) != len(everything):
            return f"{where}: collision {trains}"
        if set(everything) & set(failures):
            return f"{where}: a train ran into a failed block {trains}"
    return None


class CollisionTest(unittest.TestCase):

    def test_trains_never_collide_and_are_never_lost(self) -> None:
        for line in ("Green", "Red"):
            for seed in _SEEDS:
                with self.subTest(line=line, seed=seed):
                    self.assertIsNone(_first_problem(seed, line))


if __name__ == "__main__":
    unittest.main()
