"""Tests for the harness's tick pacer in ``common.harness.pacer``.

Real time is faked and the pacer is polled by hand, so these run at
once and exactly.

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

from PySide6.QtCore import QCoreApplication  # noqa: E402

from common.harness.pacer import TickPacer  # noqa: E402
from utils.clock_driver import MAX_CATCH_UP_TICKS  # noqa: E402
from utils.system_clock import SystemClock  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

# Small enough that every tick is noticed on time.
STEP_S = 0.0005


class _FakeTime:
    """Real time that moves only when told."""

    def __init__(self) -> None:
        self.now_s = 1000.0

    def __call__(self) -> float:
        return self.now_s


class PacerTest(unittest.TestCase):
    """The pacer keeps real time, one tick in flight at most."""

    def setUp(self) -> None:
        self.time = _FakeTime()
        self.clock = SystemClock()
        self.started: list[int] = []
        self.clock.add_tick_listener(
            lambda _sim_time_s, _tick_s: self.started.append(
                self.clock.tick_count
            )
        )
        self.pacer = TickPacer(self.clock, now_s=self.time)
        self.addCleanup(self.pacer.stop)
        self.dropped: list[int] = []
        self.pacer.backlogDropped.connect(self.dropped.append)
        self.pacer.start()

    def advance(self, seconds: float) -> None:
        """Move real time on and give the pacer its chance."""
        self.time.now_s += seconds
        self.pacer.poll()

    def finish(self) -> None:
        """End the tick in flight, as the last reply would."""
        self.pacer.tick_finished()
        self.pacer.poll()

    def run_for(self, seconds: float) -> None:
        """Run with modules that reply at once."""
        end_s = self.time.now_s + seconds
        while self.time.now_s < end_s:
            self.advance(STEP_S)
            while self.pacer.is_in_flight:
                self.finish()

    def test_paused_clock_does_not_tick(self) -> None:
        self.run_for(2.0)
        self.assertEqual(self.started, [])

    def test_ticks_keep_the_clock_rate(self) -> None:
        self.clock.resume()
        self.run_for(1.02)
        self.assertEqual(len(self.started), 10)
        self.clock.set_speed(10)
        self.run_for(1.0)
        self.assertEqual(len(self.started), 110)
        self.assertEqual(self.dropped, [])

    def test_next_tick_waits_for_the_one_in_flight(self) -> None:
        self.clock.resume()
        self.advance(0.35)
        self.assertEqual(self.started, [1])
        self.advance(0.2)
        self.assertEqual(self.started, [1])
        self.assertTrue(self.pacer.is_in_flight)
        # The owed ticks run back to back, each after the one before.
        self.finish()
        self.assertEqual(self.started, [1, 2])
        self.finish()
        self.finish()
        self.finish()
        self.assertEqual(self.started, [1, 2, 3, 4, 5])
        self.finish()
        self.assertEqual(self.started, [1, 2, 3, 4, 5])
        self.advance(0.06)
        self.assertEqual(self.started, [1, 2, 3, 4, 5, 6])

    def test_backlog_past_the_limit_is_dropped(self) -> None:
        self.clock.set_speed(10)
        self.clock.resume()
        self.advance(0.0105)
        self.assertEqual(self.started, [1])
        self.advance(1.5)
        self.finish()
        # Owed: 150 ticks, more than the limit. One runs, the rest go.
        self.assertEqual(self.started, [1, 2])
        self.assertEqual(self.dropped, [149])
        self.assertEqual(self.pacer.dropped_ticks, 149)
        self.finish()
        self.assertEqual(self.started, [1, 2])
        self.advance(0.0105)
        self.assertEqual(self.started, [1, 2, 3])

    def test_backlog_within_the_limit_is_made_up(self) -> None:
        self.clock.set_speed(10)
        self.clock.resume()
        self.advance(0.0105)
        self.advance(0.0099 * MAX_CATCH_UP_TICKS)
        while self.pacer.is_in_flight:
            self.finish()
        self.assertEqual(len(self.started), MAX_CATCH_UP_TICKS)
        self.assertEqual(self.dropped, [])

    def test_pause_keeps_at_most_the_next_tick(self) -> None:
        self.clock.resume()
        self.advance(0.105)
        self.assertEqual(self.started, [1])
        # A reply is late; the clock pauses with ticks owed.
        self.advance(1.0)
        self.clock.pause()
        self.assertEqual(self.dropped, [9])
        self.finish()
        self.assertEqual(self.started, [1])
        self.advance(5.0)
        self.assertEqual(self.started, [1])
        # The next tick was already due, so it runs on resume, alone.
        self.clock.resume()
        self.pacer.poll()
        self.assertEqual(self.started, [1, 2])
        self.finish()
        self.advance(0.09)
        self.assertEqual(self.started, [1, 2])
        self.advance(0.0105)
        self.assertEqual(self.started, [1, 2, 3])

    def test_pause_keeps_the_part_of_a_tick(self) -> None:
        self.clock.resume()
        self.advance(0.06)
        self.clock.pause()
        self.advance(10.0)
        self.clock.resume()
        self.advance(0.039)
        self.assertEqual(self.started, [])
        self.advance(0.002)
        self.assertEqual(self.started, [1])

    def test_speed_change_keeps_the_part_of_a_tick(self) -> None:
        self.clock.resume()
        self.advance(0.05)
        self.clock.set_speed(10)
        self.advance(0.0049)
        self.assertEqual(self.started, [])
        self.advance(0.0002)
        self.assertEqual(self.started, [1])

    def test_tick_finished_from_inside_the_tick(self) -> None:
        # With no module to wait on, the tick ends while it starts.
        self.clock.add_tick_listener(
            lambda _sim_time_s, _tick_s: self.pacer.tick_finished()
        )
        self.clock.resume()
        self.advance(0.105)
        self.assertEqual(self.started, [1])
        self.assertFalse(self.pacer.is_in_flight)
        self.advance(0.1)
        self.assertEqual(self.started, [1, 2])

    def test_stop_stops_ticking(self) -> None:
        self.clock.resume()
        self.run_for(0.25)
        self.pacer.stop()
        self.run_for(1.0)
        self.assertEqual(self.started, [1, 2])


if __name__ == "__main__":
    unittest.main()
