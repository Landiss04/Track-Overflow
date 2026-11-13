"""Tests for slip episodes in ``common.harness.slips``.

The tracker is free of Qt and real time, so these pass the time in.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from common.harness.slips import (  # noqa: E402
    QUIET_S,
    REPORT_INTERVAL_S,
    SLIP_ENDED,
    SLIPPED,
    SLIPPING,
    SlipEpisodes,
)


class SlipEpisodesTest(unittest.TestCase):
    """One episode per slip, however many drops it takes."""

    def setUp(self) -> None:
        self.slips = SlipEpisodes()

    def names(self, events: list[tuple[str, str]]) -> list[str]:
        """The event names alone."""
        return [name for name, _detail in events]

    def test_first_drop_is_logged_as_before(self) -> None:
        events = self.slips.dropped(100.0, 99)
        self.assertEqual(
            events, [(SLIPPED, "99 ticks behind real time, not made up")]
        )
        self.assertTrue(self.slips.is_slipping)
        self.assertEqual(self.slips.total, 99)

    def test_drops_in_a_slip_are_reported_at_intervals(self) -> None:
        self.slips.dropped(100.0, 50)
        logged = []
        # A drop every second for 25 s.
        for second in range(1, 26):
            logged += self.slips.dropped(100.0 + second, 10, 6.25)
        self.assertEqual(self.names(logged), [SLIPPING, SLIPPING])
        self.assertEqual(
            logged[0][1],
            f"100 more ticks dropped in {REPORT_INTERVAL_S:.1f} s; "
            "150 since the slip began; running at 6.2x",
        )
        self.assertIn("250 since the slip began", logged[1][1])
        self.assertEqual(self.slips.total, 300)

    def test_slip_ends_after_keeping_up_quietly(self) -> None:
        self.slips.dropped(100.0, 50)
        self.slips.dropped(101.0, 40)
        # Not keeping up yet: the slip goes on, however long.
        self.assertEqual(self.slips.ticked(200.0, keeping_up=False), [])
        # Keeping up, but a drop too recent.
        self.slips.dropped(201.0, 30)
        self.assertEqual(
            self.slips.ticked(201.0 + QUIET_S - 0.1, keeping_up=True), []
        )
        events = self.slips.ticked(
            201.0 + QUIET_S, keeping_up=True, actual_speed=9.96
        )
        self.assertEqual(
            events,
            [(SLIP_ENDED,
              "120 ticks dropped in 3 batches over 101.0 s; "
              "running at 10.0x")],
        )
        self.assertFalse(self.slips.is_slipping)
        self.assertEqual(self.slips.total, 0)

    def test_a_slip_of_one_drop_ends_silently(self) -> None:
        self.slips.dropped(100.0, 99)
        self.assertEqual(self.slips.ticked(200.0, keeping_up=True), [])
        self.assertFalse(self.slips.is_slipping)

    def test_pausing_ends_the_slip(self) -> None:
        self.slips.dropped(100.0, 50)
        self.slips.dropped(102.0, 9)
        self.assertEqual(
            self.slips.held(),
            [(SLIP_ENDED, "59 ticks dropped in 2 batches over 2.0 s")],
        )
        self.assertEqual(self.slips.held(), [])

    def test_a_pause_drop_alone_is_one_line(self) -> None:
        # The clock pauses with ticks owed: one TIME_SLIPPED, as before.
        events = self.slips.dropped(100.0, 9) + self.slips.held()
        self.assertEqual(self.names(events), [SLIPPED])

    def test_the_next_slip_starts_afresh(self) -> None:
        self.slips.dropped(100.0, 50)
        self.slips.dropped(101.0, 50)
        self.slips.ticked(110.0, keeping_up=True)
        events = self.slips.dropped(200.0, 7)
        self.assertEqual(
            events, [(SLIPPED, "7 ticks behind real time, not made up")]
        )
        self.assertEqual(self.slips.total, 7)
        self.assertEqual(
            self.slips.dropped(200.0 + REPORT_INTERVAL_S, 3)[0][1],
            f"3 more ticks dropped in {REPORT_INTERVAL_S:.1f} s; "
            "10 since the slip began",
        )

    def test_no_slip_nothing_to_say(self) -> None:
        self.assertEqual(self.slips.ticked(100.0, keeping_up=True), [])
        self.assertEqual(self.slips.held(), [])
        self.assertFalse(self.slips.is_slipping)


if __name__ == "__main__":
    unittest.main()
