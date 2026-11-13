"""Whole schedule_v4 lines on a realistic railway (``realistic_railway``).

Each line's ten runs are dispatched by the CTC Office through the real
waysides (Red: the HW Track Controller with the integration PLC
programs; Green: the SW Track Controller with its starter programs),
over the Track Model's track, with trains that take time to stop and
can run past the end of their authority.

Two train controller laws, each with a 1 s reaction before the brake
comes on:

- ``lookahead``: the train brakes in time to stop at the end of its
  authority, allowing for its reaction (the model the CTC's tests ask
  of a train controller);
- ``speed``: the Train Controller's own law (``Train-Ctrl_HW/train_ctrl/
  control.py``): it holds the commanded speed and brakes only when the
  commanded speed is lower, or its authority is 0. It relies on the
  CTC's suggested speed to stop within its authority.

Each line and law runs once (``setUpClass``); the tests check what the
run recorded. A failure message carries the run's summary: overruns,
trains frozen side by side, the longest waits, and on a deadlock what
every train was waiting for.

Run from the repository root with
``python -m pytest CTC-Office/tests/test_ctc_realistic.py -q``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.realistic_railway import Result, run_line  # noqa: E402
from tests.test_ctc_scheduler import FILE_GREEN, FILE_RED  # noqa: E402

#: Each run's stations in the file's order (``test_ctc_scheduler``).
EXPECTED_STOPS = {"Green": FILE_GREEN, "Red": FILE_RED}

#: Every run done by then, from the 05:00 start.
LATEST = 4 * 3600


class _LineRun:
    """The checks, for one line and train controller law."""

    line: str
    controller: str
    reaction_s = 1.0
    result: Result

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_line(cls.line, controller=cls.controller,
                              reaction_s=cls.reaction_s)

    def _why(self) -> str:
        return "\n" + self.result.summary()

    def test_every_run_finishes(self) -> None:
        result = self.result
        self.assertTrue(result.finished, self._why())
        self.assertEqual(set(result.statuses.values()), {"done"},
                         self._why())
        self.assertLess(result.end_s, LATEST, self._why())
        # Each run released once and retired once (D022).
        self.assertEqual(sorted(result.released), sorted(result.stops))
        self.assertEqual(sorted(result.retired), sorted(result.stops))

    def test_every_run_stops_in_file_order(self) -> None:
        expected = EXPECTED_STOPS[self.line]
        for train_id, stops in self.result.stops.items():
            with self.subTest(train=train_id):
                self.assertEqual(stops, expected, self._why())
        # Each dwell with the train on its stop's block.
        self.assertEqual(self.result.misplaced_dwells, [], self._why())

    def test_no_train_frozen_beside_another(self) -> None:
        # Two trains standing in neighbouring blocks: the waysides hold
        # a train with an occupied neighbour, and the CTC gives neither
        # authority toward the other, so they stand there for good.
        self.assertEqual([str(f) for f in self.result.freezes], [],
                         self._why())

    def test_no_train_enters_a_block_beyond_its_authority(self) -> None:
        # Past the CTC's own authority: the suggested speed leaves it no
        # room to stop. A wayside that cuts the authority of a train
        # already moving can make it run on too (on Green, the Track
        # Controller SW's loop guard for 1..12 on 145..150, 2026-11-12):
        # that is the wayside's, listed in the summary, not failed here.
        self.assertEqual(
            [str(o) for o in self.result.overruns if o.past_ctc], [],
            self._why())

    def test_no_collision_and_no_switch_run_through(self) -> None:
        self.assertEqual(self.result.collisions, [], self._why())
        self.assertEqual(self.result.trailed, [], self._why())


class RedLookaheadTest(_LineRun, unittest.TestCase):
    line, controller = "Red", "lookahead"


class GreenLookaheadTest(_LineRun, unittest.TestCase):
    line, controller = "Green", "lookahead"


class RedTrainControllerLawTest(_LineRun, unittest.TestCase):
    line, controller = "Red", "speed"


class GreenTrainControllerLawTest(_LineRun, unittest.TestCase):
    line, controller = "Green", "speed"


if __name__ == "__main__":
    unittest.main()
