"""Tests for the next-block suggestion (``suggested-speed``,
``suggested-authority``; R49).

While a train's authority is at least 1, the CTC Office sends a second
suggestion for the next block on its route: authority one less, and a
speed worked out for that block from its own limit and the stopping
distance left with one block less authority. Without it, the block a
train has just entered carries nothing until the CTC sees the train
there, and the train reads 0 and 0.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import math
import sys
import unittest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import TrainSuggestion  # noqa: E402
from ctc.model import (  # noqa: E402
    SERVICE_DECEL_MPS2,
    SUGGESTED_SPEED_MARGIN_MPS,
)
from ctc.track_layout import load_layout  # noqa: E402
from tests.occupancy import at, ready_office, reports, step_at  # noqa: E402

_LAYOUT = load_layout()
_BLOCKS = {(name, b.block_id): b
           for name, line in _LAYOUT.items() for b in line.blocks}


def _limit_mps(line: str, block_id: str) -> int:
    """A block's speed limit in whole m/s, rounded down."""
    return int(_BLOCKS[(line, block_id)].speed_limit_kmh / 3.6)


def _expected_speed(line: str, block_id: str,
                    ahead: tuple[str, ...]) -> int:
    """The suggested speed for a block: a little under its limit, and
    no faster than a train can stop from over the blocks ``ahead``."""
    stopping_m = sum(_BLOCKS[(line, b)].length_m for b in ahead)
    can_stop = int(math.sqrt(2 * SERVICE_DECEL_MPS2 * stopping_m))
    return min(max(0, _limit_mps(line, block_id)
                   - SUGGESTED_SPEED_MARGIN_MPS), can_stop)


def _for(suggestions: tuple[TrainSuggestion, ...],
         train_id: str) -> list[TrainSuggestion]:
    """A train's suggestions, its own block's first."""
    return sorted((s for s in suggestions if s.train_id == train_id),
                  key=lambda s: -s.authority_blocks)


class NextBlockTest(unittest.TestCase):
    """Up to two suggestions per train, with the right values."""

    def test_two_suggestions_while_authority_is_at_least_one(self) -> None:
        # T1 in Green 63, sent to 66: three blocks ahead (64, 65, 66).
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "66")
        out = step_at(ctc, at("T1", "63"))
        here, ahead = _for(out.track_controller.suggestions, "T1")
        self.assertEqual(
            here, TrainSuggestion("T1", "Green", "63",
                                  _expected_speed("Green", "63",
                                                  ("64", "65", "66")), 3))
        # The next block on its route, authority one less, its speed
        # worked out for 64 with 65 and 66 to stop in.
        self.assertEqual(
            ahead, TrainSuggestion("T1", "Green", "64",
                                   _expected_speed("Green", "64",
                                                   ("65", "66")), 2))
        self.assertIs(type(ahead.suggested_speed_mps), int)

    def test_next_block_speed_is_its_own_not_a_copy(self) -> None:
        # Green 69 (40 km/h) toward 70 and 71: 69's speed is held to
        # what stops in 100 m + 100 m, 70's to what stops in 100 m.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "71")
        out = step_at(ctc, at("T1", "69"))
        here, ahead = _for(out.track_controller.suggestions, "T1")
        self.assertEqual((ahead.block_id, ahead.authority_blocks),
                         ("70", 1))
        self.assertEqual(ahead.suggested_speed_mps,
                         _expected_speed("Green", "70", ("71",)))
        # A faster block followed by a slower one: the next block gets
        # the slower block's own limit, not the current block's speed.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        out = step_at(ctc, at("T1", "66"))
        here, ahead = _for(out.track_controller.suggestions, "T1")
        self.assertEqual(ahead.block_id, "67")
        self.assertLessEqual(ahead.suggested_speed_mps,
                             _limit_mps("Green", "67"))
        self.assertNotEqual(ahead.suggested_speed_mps,
                            here.suggested_speed_mps)

    def test_authority_one_gives_the_next_block_zero(self) -> None:
        # One block to go: the next block is the destination, where it
        # must stop, so its authority is 0 and its speed what stops in
        # no distance at all.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "65")
        out = step_at(ctc, at("T1", "64"))
        here, ahead = _for(out.track_controller.suggestions, "T1")
        self.assertEqual(here.authority_blocks, 1)
        self.assertEqual(ahead, TrainSuggestion("T1", "Green", "65", 0, 0))

    def test_none_for_the_next_block_at_authority_zero(self) -> None:
        # At its destination, and held short of an occupied block.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "65")
        out = step_at(ctc, at("T1", "65"))
        (only,) = _for(out.track_controller.suggestions, "T1")
        self.assertEqual((only.block_id, only.authority_blocks), ("65", 0))
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        ctc.dispatch("T2", "Green", "70")
        out = step_at(ctc, at("T1", "63"), at("T2", "64"))
        (only,) = _for(out.track_controller.suggestions, "T1")
        self.assertEqual((only.block_id, only.authority_blocks), ("63", 0))

    def test_never_above_the_block_limit_and_within_authority(self) -> None:
        # Many trains and destinations on both lines: every suggestion
        # is at or under its block's limit, every next block is the
        # first block of the train's authority, and no block is named
        # by two trains.
        cases = [("Green", "63", d) for d in ("64", "65", "70", "77",
                                              "100")]
        cases += [("Green", "13", d) for d in ("20", "28", "57")]
        cases += [("Red", "9", d) for d in ("7", "1", "16", "40")]
        for line, start, destination in cases:
            with self.subTest(line=line, start=start, to=destination):
                ctc = ready_office()
                ctc.dispatch("T1", line, destination)
                out = step_at(ctc, at("T1", start, line))
                found = out.track_controller.suggestions
                for s in found:
                    self.assertLessEqual(s.suggested_speed_mps,
                                         _limit_mps(s.line, s.block_id))
                    self.assertGreaterEqual(s.suggested_speed_mps, 0)
                (limit,) = ctc.snapshot().authorities
                if limit.blocks >= 1:
                    here, ahead = _for(found, "T1")
                    self.assertEqual(ahead.block_id, limit.route[1])
                    self.assertIn(ahead.block_id,
                                  limit.route[1:limit.blocks + 1])
                    self.assertEqual(ahead.authority_blocks,
                                     here.authority_blocks - 1)
                    self.assertEqual(
                        ahead.suggested_speed_mps,
                        _expected_speed(
                            line, ahead.block_id,
                            limit.route[2:limit.blocks + 1]))
                else:
                    self.assertEqual(len(found), 1)

    def test_two_trains_never_name_one_block(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "73")
        ctc.dispatch("T2", "Green", "77")
        out = step_at(ctc, at("T1", "63"), at("T2", "66"))
        named = [(s.line, s.block_id)
                 for s in out.track_controller.suggestions]
        self.assertEqual(len(named), len(set(named)))
        self.assertEqual(len(_for(out.track_controller.suggestions, "T1")),
                         2)


class BlockChangeLoopTest(unittest.TestCase):
    """A whole run with the loop's latency in it: the train reads the
    values of the block its head is in, as the Track Controller passes
    on the CTC's suggestions, and the CTC sees the train only through
    delayed occupancy."""

    #: Ticks from the train's blocks changing to the CTC seeing it, and
    #: from the CTC's outputs to the track circuits (Track Model, Track
    #: Controller, CTC Office, Track Controller, Track Model: about 4).
    OCCUPANCY_LAG = 2
    COMMAND_LAG = 2
    DT_S = 0.5

    def test_authority_never_falls_from_two_blocks_to_none(self) -> None:
        # Green 63 to 76, the last block before the switch at 76-77,
        # which no wayside reports here: 13 blocks, no switch to set.
        line, destination = "Green", "76"
        ctc = ready_office()
        ctc.dispatch("T1", line, destination)
        lengths = {b.block_id: b.length_m for b in _LAYOUT[line].blocks}
        # The train: blocks held (tail first), how far into its head
        # block, and whether it is on the track yet.
        held: list[str] = []
        progress = 0.0
        occupancy: deque[set[str]] = deque(
            [set()] * self.OCCUPANCY_LAG)
        commands: deque[tuple[TrainSuggestion, ...]] = deque(
            [()] * self.COMMAND_LAG)
        last_read = None
        block_changes = 0
        for tick in range(4000):
            occupancy.append(set(held))
            out = ctc.step(self.DT_S, reports(
                occupied=[(line, b) for b in occupancy.popleft()]))
            if out.new_trains:
                # The yard: the harness puts the released train at the
                # exit block.
                self.assertEqual([t.train_id for t in out.new_trains],
                                 ["T1"])
                held = ["63"]
            commands.append(out.track_controller.suggestions)
            on_track = {s.block_id: s for s in commands.popleft()
                        if s.line == line}
            if not held:
                continue
            if len(held) > 1:
                held.pop(0)                   # the tail clears
            # What the train picks up from its head block: a block not
            # commanded on the latest tick reads zero.
            value = on_track.get(held[-1])
            read = ((value.suggested_speed_mps, value.authority_blocks)
                    if value is not None else (0, 0))
            if last_read is not None and last_read[1] >= 2:
                self.assertNotEqual(
                    read[1], 0,
                    f"tick {tick}: block {held[-1]} reads authority 0 "
                    f"after {last_read[1]}")
            last_read = read
            progress = min(lengths[held[-1]], progress + read[0] * self.DT_S)
            if progress >= lengths[held[-1]] and read[1] >= 1:
                (limit,) = ctc.snapshot().authorities
                route = limit.route
                # The next block of its route from where it is.
                after = route[route.index(held[-1]) + 1]
                held.append(after)
                progress = 0.0
                block_changes += 1
            if held[-1] == destination and read == (0, 0):
                break
        self.assertEqual(held, [destination])
        self.assertGreater(block_changes, 5)


if __name__ == "__main__":
    unittest.main()
