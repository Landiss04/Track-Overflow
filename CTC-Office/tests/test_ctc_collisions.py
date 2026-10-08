"""Randomized check that the CTC Office never lets trains collide.

Trains move one block per step whenever they have authority, toward
random destinations, while switches change position. At every step no
block may be within two trains' authorities, no train may be authorized
into an occupied block, and no two trains may share a block.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import (  # noqa: E402
    CtcInputs,
    SwitchReport,
    TrackControllerInputs,
    TrainReport,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.track_layout import load_layout  # noqa: E402

_LAYOUT = load_layout()
_TRAINS = 4
_STEPS = 150
_SEEDS = range(4)


def _first_problem(seed: int, line: str) -> str | None:
    rng = random.Random(seed)
    blocks = [b.block_id for b in _LAYOUT[line].blocks]
    switch_ids = _LAYOUT[line].switch_ids()
    ctc = StubCtcOffice()
    positions: dict[str, str] = {}
    for n in range(_TRAINS):
        free = [b for b in blocks if b not in positions.values()]
        positions[f"T{n}"] = rng.choice(free)
        ctc.dispatch(f"T{n}", line, rng.choice(blocks))
    switches = {s: rng.choice(("normal", "reverse")) for s in switch_ids}
    for step in range(_STEPS):
        if step % 15 == 0:
            occupied = set(positions.values())
            for s in switch_ids:
                if s not in occupied and rng.random() < 0.5:
                    switches[s] = rng.choice(("normal", "reverse"))
        ctc.step(0.1, CtcInputs(track_controller=TrackControllerInputs(
            trains=tuple(TrainReport(t, line, b, 0.0, 0.0)
                         for t, b in positions.items()),
            switches=tuple(SwitchReport(line, s, p)
                           for s, p in switches.items()))))
        authorities = ctc.snapshot().authorities
        held: dict[str, str] = {}
        for a in authorities:
            for block in a.route[1:a.blocks + 1]:
                where = f"seed {seed} {line} step {step}"
                if block in held:
                    return (f"{where}: block {block} in the authority of "
                            f"{held[block]} and {a.train_id}")
                if block in positions.values():
                    return (f"{where}: {a.train_id} authorized into "
                            f"occupied block {block}")
                held[block] = a.train_id
        for a in authorities:
            if a.blocks >= 1:
                positions[a.train_id] = a.route[1]
            elif a.reason == "destination":
                ctc.dispatch(a.train_id, line, rng.choice(blocks))
        if len(set(positions.values())) != len(positions):
            return f"seed {seed} {line} step {step}: collision {positions}"
    return None


class CollisionTest(unittest.TestCase):

    def test_trains_never_collide(self) -> None:
        for line in ("Green", "Red"):
            for seed in _SEEDS:
                with self.subTest(line=line, seed=seed):
                    self.assertIsNone(_first_problem(seed, line))


if __name__ == "__main__":
    unittest.main()
