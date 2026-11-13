"""Tests for following trains from block occupancy (``ctc.tracking``):
the Track Controller reports only which blocks are occupied, and the CTC
Office works out where its trains are and which blocks have failed.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import (  # noqa: E402
    CtcInputs,
    SwitchReport,
    TrackedTrain,
)
from ctc.model import StubCtcOffice  # noqa: E402
from tests.occupancy import own_block, ready_office, reports  # noqa: E402


def _occupied(ctc: StubCtcOffice, *blocks: str, line: str = "Green",
              dt: float = 1.0, steps: int = 1) -> None:
    """Step with ``blocks`` of ``line`` occupied, and nothing else."""
    for _ in range(steps):
        ctc.step(dt, reports(occupied=[(line, b) for b in blocks]))


def _where(ctc: StubCtcOffice) -> dict[str, tuple[str, ...]]:
    return {t.train_id: t.blocks for t in ctc.snapshot().trains}


def _authority(ctc: StubCtcOffice, train_id: str = "T1"):
    (found,) = [a for a in ctc.snapshot().authorities
                if a.train_id == train_id]
    return found


class YardTest(unittest.TestCase):
    """A train the CTC has released leaves the yard when the yard exit
    block becomes occupied: Green 63, Red 9. The CTC releases a waiting
    train on a step when its exit block is clear (D022), so it is found
    there on a later step."""

    def test_leaves_into_the_exit_block(self) -> None:
        for line, exit_block, destination in (("Green", "63", "70"),
                                              ("Red", "9", "7")):
            with self.subTest(line=line):
                ctc = ready_office()
                ctc.dispatch("T1", line, destination)
                _occupied(ctc, line=line)
                self.assertEqual(ctc.snapshot().trains, ())
                _occupied(ctc, exit_block, line=line)
                self.assertEqual(ctc.snapshot().trains, (
                    TrackedTrain("T1", line, (exit_block,)),))

    def test_the_train_most_behind_schedule_leaves_first(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        ctc.dispatch("T2", "Green", "70", arrival_s=9 * 3600)
        ctc.dispatch("T3", "Green", "70", arrival_s=8 * 3600)
        ctc.dispatch("T4", "Red", "7", arrival_s=5 * 3600)
        _occupied(ctc)                      # T3 is released
        _occupied(ctc, "63")
        self.assertEqual(_where(ctc), {"T3": ("63",)})

    def test_with_no_arrival_times_by_train_id(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T2", "Green", "70")
        ctc.dispatch("T1", "Green", "70")
        _occupied(ctc)                      # T1 is released
        _occupied(ctc, "63")
        self.assertEqual(_where(ctc), {"T1": ("63",)})

    def test_with_no_train_waiting_it_is_a_failure(self) -> None:
        ctc = ready_office()
        _occupied(ctc, "63")
        # Ordered afterwards: 63 is not newly occupied, so T1 is still
        # in the yard, and 63 is a failure it waits behind.
        ctc.dispatch("T1", "Green", "70")
        _occupied(ctc, "63")
        self.assertEqual(ctc.snapshot().trains, ())
        # 63 clears and is occupied again: now that is T1.
        _occupied(ctc)
        _occupied(ctc, "63")
        self.assertEqual(_where(ctc), {"T1": ("63",)})

    def test_a_train_that_ran_into_the_yard_may_leave_again(self) -> None:
        # Green 57 runs into the yard: a train whose blocks clear there
        # has gone back in, and is not lost.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "57")
        ctc.place_train("T1", "Green", "57")
        _occupied(ctc, "57")
        _occupied(ctc)
        snap = ctc.snapshot()
        self.assertEqual((snap.trains, snap.lost_trains), ((), ()))
        _occupied(ctc, "63")
        self.assertEqual(_where(ctc), {"T1": ("63",)})


class MovingTest(unittest.TestCase):
    """A train moves into the next block of its route when that block
    becomes occupied, if it could have got there."""

    def _out_of_the_yard(self) -> StubCtcOffice:
        # Green 63 to 70: 63 is 100 m long, limited to 70 km/h.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        _occupied(ctc)                      # T1 is released
        _occupied(ctc, "63")
        return ctc

    def test_holds_both_blocks_while_crossing(self) -> None:
        ctc = self._out_of_the_yard()
        _occupied(ctc, "63", steps=10)
        _occupied(ctc, "63", "64")
        self.assertEqual(_where(ctc), {"T1": ("63", "64")})
        # Authority is counted from its head, and the Track Controller
        # is told to send it down the head's block.
        self.assertEqual(_authority(ctc).route[0], "64")
        suggestion = own_block(
            ctc.snapshot().outputs.track_controller.suggestions)
        self.assertEqual((suggestion.line, suggestion.block_id),
                         ("Green", "64"))
        _occupied(ctc, "64")
        self.assertEqual(_where(ctc), {"T1": ("64",)})

    def test_too_early_is_a_failure(self) -> None:
        # One second after leaving the yard T1 cannot have crossed 63:
        # 64 is a failure, which it waits behind.
        ctc = self._out_of_the_yard()
        _occupied(ctc, "63", "64")
        self.assertEqual(_where(ctc), {"T1": ("63",)})
        limit = _authority(ctc)
        # Shown only as an occupied block.
        self.assertEqual((limit.blocks, limit.reason, limit.at),
                         (0, "occupied", "64"))
        # It stays a failure however long it lasts...
        _occupied(ctc, "63", "64", steps=30)
        self.assertEqual(_where(ctc), {"T1": ("63",)})
        # ...until it clears.
        _occupied(ctc, "63")
        self.assertEqual(_authority(ctc).blocks, 7)

    def test_no_authority_into_the_next_block_is_a_failure(self) -> None:
        # T1 is at its destination: it may not go on, however long ago
        # it got there.
        ctc = self._out_of_the_yard()
        ctc.dispatch("T1", "Green", "63")
        _occupied(ctc, "63", steps=30)
        _occupied(ctc, "63", "64")
        self.assertEqual(_where(ctc), {"T1": ("63",)})

    def _running_into_a_closure(self) -> StubCtcOffice:
        # T1 running 30 to 37; 31 closes when it is too late to stop.
        ctc = ready_office()
        ctc.place_train("T1", "Green", "30")
        ctc.dispatch("T1", "Green", "37")
        _occupied(ctc, "30", steps=20)
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "31", True)
        _occupied(ctc, "30")
        self.assertEqual(_authority(ctc).blocks, 0)
        return ctc

    def test_a_train_too_late_to_stop_is_followed_on(self) -> None:
        ctc = self._running_into_a_closure()
        # Nothing says it is T1 until T1's own block clears.
        _occupied(ctc, "30", "31")
        self.assertEqual(_where(ctc), {"T1": ("30",)})
        _occupied(ctc, "31")
        self.assertEqual(_where(ctc), {"T1": ("31",)})
        self.assertEqual(ctc.snapshot().lost_trains, ())
        # Reopened, it carries on under its own name.
        ctc.set_block_closed("Green", "31", False)
        _occupied(ctc, "31")
        self.assertGreater(_authority(ctc).blocks, 0)

    def test_a_failure_ahead_of_a_standing_train_stays_a_failure(
            self) -> None:
        # T1 stays in 30, so what is in 31 is not T1.
        ctc = self._running_into_a_closure()
        _occupied(ctc, "30", "31", steps=60)
        self.assertEqual(_where(ctc), {"T1": ("30",)})
        self.assertEqual(ctc.snapshot().lost_trains, ())

    def test_a_train_past_its_destination_is_followed_on(self) -> None:
        # T1 stops at 31, but does not manage it and runs on into 32.
        ctc = ready_office()
        ctc.place_train("T1", "Green", "30")
        ctc.dispatch("T1", "Green", "31")
        _occupied(ctc, "30", steps=20)
        _occupied(ctc, "30", "31")
        _occupied(ctc, "31", steps=2)
        _occupied(ctc, "31", "32")
        _occupied(ctc, "32")
        self.assertEqual(_where(ctc), {"T1": ("32",)})
        self.assertEqual(ctc.snapshot().lost_trains, ())

    def test_unexplained_occupancy_is_a_failure(self) -> None:
        ctc = self._out_of_the_yard()
        _occupied(ctc, "63", "67")
        self.assertEqual(_where(ctc), {"T1": ("63",)})
        limit = _authority(ctc)
        self.assertEqual((limit.blocks, limit.reason, limit.at),
                         (2, "occupied", "67"))

    def test_a_faster_past_counts(self) -> None:
        # T1 runs 2 s at 18 m/s; then a train standing on 66 cuts its
        # authority to 64 and its suggested speed to 11 m/s. 64 becomes
        # occupied a second later: 3 s in, too soon at 11 m/s (it would
        # need 4.5 s for half of 63's 100 m), but T1 may well have gone
        # 47 m by then. That is T1, not a failure.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "80")
        ctc.place_train("T1", "Green", "63")
        _occupied(ctc, "63", dt=0.1)
        self.assertEqual(own_block(ctc.snapshot().outputs.track_controller
                                   .suggestions).suggested_speed_mps, 18)
        ctc.place_train("T2", "Green", "66")
        _occupied(ctc, "63", "66", dt=2.0)
        self.assertEqual(own_block(ctc.snapshot().outputs.track_controller
                                   .suggestions).suggested_speed_mps, 11)
        _occupied(ctc, "63", "64", "66", dt=1.0)
        self.assertEqual(_where(ctc)["T1"], ("63", "64"))


class OverrunAtASwitchTest(unittest.TestCase):
    """A train that runs past its stop onto a switch's points block,
    and on past it, is followed the way the track leads it."""

    @staticmethod
    def _red(ctc: StubCtcOffice, *blocks: str, steps: int = 1,
             position: str = "normal") -> None:
        for _ in range(steps):
            ctc.step(1.0, reports(
                occupied=[("Red", b) for b in blocks],
                switches=[SwitchReport("Red", "15", position)]))

    def test_trailing_through_the_points(self) -> None:
        # R3 of 2026-11-09: in by 15 to its stop at 16, and on into 17.
        # Block 1 joins 16 at the end the train came in by.
        ctc = ready_office()
        ctc.place_train("T1", "Red", "15")
        ctc.dispatch("T1", "Red", "16")
        self._red(ctc, "15", steps=20)
        self._red(ctc, "15", "16")
        self._red(ctc, "16", steps=2)
        self._red(ctc, "16", "17")
        self._red(ctc, "17")
        self.assertEqual(_where(ctc), {"T1": ("17",)})
        self.assertEqual(ctc.snapshot().lost_trains, ())

    def test_facing_the_points_it_goes_where_the_switch_is_set(
            self) -> None:
        # In by 17 to 16, facing switch 15: on to 15 when it reports
        # normal, to 1 when it reports reverse.
        for position, onward in (("normal", "15"), ("reverse", "1")):
            with self.subTest(position=position):
                ctc = ready_office()
                ctc.place_train("T1", "Red", "17")
                ctc.dispatch("T1", "Red", "16")
                self._red(ctc, "17", steps=20, position=position)
                self._red(ctc, "17", "16", position=position)
                self._red(ctc, "16", steps=2, position=position)
                self._red(ctc, "16", onward, position=position)
                self._red(ctc, onward, position=position)
                self.assertEqual(_where(ctc), {"T1": (onward,)})
                self.assertEqual(ctc.snapshot().lost_trains, ())


class LostTest(unittest.TestCase):
    """A train whose blocks all clear, outside the yard, is dropped
    quietly; its order stays."""

    def test_dropped_quietly(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "37")
        ctc.place_train("T1", "Green", "30")
        _occupied(ctc, "30")
        _occupied(ctc)
        snap = ctc.snapshot()
        self.assertEqual((snap.trains, snap.lost_trains), ((), ("T1",)))
        self.assertEqual([o.train_id for o in snap.orders], ["T1"])
        self.assertEqual(snap.authorities, ())
        # Never taken to have left the yard.
        _occupied(ctc, "63")
        self.assertEqual(ctc.snapshot().trains, ())

    def test_found_again_by_placing_it(self) -> None:
        ctc = ready_office()
        ctc.place_train("T1", "Green", "30")
        _occupied(ctc, "30")
        ctc.step(1.0, CtcInputs())
        ctc.place_train("T1", "Green", "31")
        self.assertEqual(ctc.snapshot().lost_trains, ())


if __name__ == "__main__":
    unittest.main()
