"""Tests for the harness's tick pacer in ``common.harness.pacer``.

Real time is faked and the pacer is polled by hand, so these run at
once and exactly.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import unittest
from collections.abc import Callable
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


class PacerSlipRegressionTest(unittest.TestCase):
    """What a slip must never change, however the pacer sheds load.

    Each tick takes a set round trip of fake real time, as modules
    replying after that long would. A slip may only drop wall-clock
    time that was owed: the ticks that do run follow one another with
    a constant ``dt``, one at a time, and a run that keeps up loses
    nothing and runs every tick on time.
    """

    def setUp(self) -> None:
        self.time = _FakeTime()
        self.clock = SystemClock()
        # (real time it started, tick, sim time, dt) per tick.
        self.ticks: list[tuple[float, int, float, float]] = []
        self.clock.add_tick_listener(self._on_tick)
        self.pacer = TickPacer(self.clock, now_s=self.time)
        self.addCleanup(self.pacer.stop)
        self.dropped: list[int] = []
        self.pacer.backlogDropped.connect(self.dropped.append)
        self.pacer.start()
        self._started_s: float | None = None

    def _on_tick(self, sim_time_s: float, tick_s: float) -> None:
        # Never two ticks in flight: the one before is finished.
        self.assertIsNone(self._started_s, "a tick started mid-flight")
        self._started_s = self.time.now_s
        self.ticks.append(
            (self.time.now_s, self.clock.tick_count, sim_time_s, tick_s)
        )

    def run_for(
        self,
        seconds: float,
        round_trip_s: Callable[[int], float] = lambda _tick: 0.0,
    ) -> None:
        """Run with each tick taking ``round_trip_s(tick)`` real time."""
        end_s = self.time.now_s + seconds
        while self.time.now_s < end_s:
            self.time.now_s += STEP_S
            if (
                self._started_s is not None
                and self.time.now_s - self._started_s
                >= round_trip_s(self.clock.tick_count) - 1e-12
            ):
                self._started_s = None
                self.pacer.tick_finished()
            self.pacer.poll()
            # A tick that takes no time ends as it starts.
            while (
                self._started_s is not None
                and round_trip_s(self.clock.tick_count) <= 0
            ):
                self._started_s = None
                self.pacer.tick_finished()
                self.pacer.poll()

    def assert_ticks_unbroken(self) -> None:
        """Ticks 1..n ran in order, each ``dt`` on from the last."""
        start_s = self.clock.sim_time_s - self.clock.elapsed_s
        self.assertEqual(
            [tick for _s, tick, _t, _dt in self.ticks],
            list(range(1, len(self.ticks) + 1)),
        )
        for _s, tick, sim_time_s, dt in self.ticks:
            self.assertEqual(dt, self.clock.tick_s)
            self.assertAlmostEqual(sim_time_s, start_s + tick * dt, places=6)

    def test_round_trips_inside_the_budget_cost_nothing_at_10x(self) -> None:
        # 7 ms of a 10 ms budget: every tick starts when it falls due.
        self.clock.set_speed(10)
        self.clock.resume()
        began_s = self.time.now_s
        self.run_for(2.0, lambda _tick: 0.007)
        self.assertEqual(len(self.ticks), 200)
        self.assertEqual(self.dropped, [])
        for real_s, tick, _sim_s, _dt in self.ticks:
            self.assertAlmostEqual(
                real_s - began_s, tick * 0.01, delta=2 * STEP_S
            )
        self.assert_ticks_unbroken()

    def test_round_trips_inside_the_budget_cost_nothing_at_1x(self) -> None:
        self.clock.resume()
        began_s = self.time.now_s
        self.run_for(2.0, lambda _tick: 0.08)
        self.assertEqual(len(self.ticks), 20)
        self.assertEqual(self.dropped, [])
        for real_s, tick, _sim_s, _dt in self.ticks:
            self.assertAlmostEqual(
                real_s - began_s, tick * 0.1, delta=2 * STEP_S
            )

    def test_short_hold_up_is_made_up_at_10x(self) -> None:
        # One reply takes 0.3 s: 30 ticks owed, all run afterwards.
        self.clock.set_speed(10)
        self.clock.resume()
        self.run_for(2.0, lambda tick: 0.3 if tick == 5 else 0.0)
        self.assertEqual(self.dropped, [])
        self.assertEqual(self.pacer.dropped_ticks, 0)
        self.assertAlmostEqual(len(self.ticks), 200, delta=1)
        self.assert_ticks_unbroken()

    def test_short_hold_up_is_made_up_at_1x(self) -> None:
        # One reply takes 0.4 s: 4 ticks owed, all run afterwards.
        self.clock.resume()
        self.run_for(3.0, lambda tick: 0.4 if tick == 3 else 0.0)
        self.assertEqual(self.dropped, [])
        self.assertAlmostEqual(len(self.ticks), 30, delta=1)
        self.assert_ticks_unbroken()

    def test_overload_drops_time_never_a_tick(self) -> None:
        # 25 ms round trips at 10x: the run cannot keep up, so owed
        # real time is dropped, yet every tick that runs is whole.
        self.clock.set_speed(10)
        self.clock.resume()
        self.run_for(5.0, lambda _tick: 0.025)
        self.assertGreater(self.pacer.dropped_ticks, 0)
        self.assertEqual(sum(self.dropped), self.pacer.dropped_ticks)
        # Never more ticks than the round trips allow.
        self.assertLessEqual(len(self.ticks), 5.0 / 0.025 + 1)
        self.assert_ticks_unbroken()

    def test_every_dropped_tick_is_reported(self) -> None:
        # A drop for falling behind, then one for pausing with ticks
        # owed: the total is the sum of what was reported.
        self.clock.set_speed(10)
        self.clock.resume()
        self.run_for(0.05)
        self.run_for(1.6, lambda tick: 1.5 if tick == 6 else 0.0)
        self.run_for(0.2, lambda tick: 0.1 if tick > 6 else 0.0)
        self.clock.pause()
        self.assertGreaterEqual(len(self.dropped), 2)
        self.assertEqual(sum(self.dropped), self.pacer.dropped_ticks)
        self.assert_ticks_unbroken()

    def test_resume_after_a_pause_does_not_burst(self) -> None:
        self.clock.set_speed(10)
        self.clock.resume()
        self.run_for(0.5, lambda tick: 0.2 if tick == 3 else 0.0)
        self.clock.pause()
        self.run_for(3.0)
        count = len(self.ticks)
        self.clock.resume()
        self.run_for(0.1)
        # At most the one owed tick, then real time: 10 in 0.1 s.
        self.assertLessEqual(len(self.ticks) - count, 11)


if __name__ == "__main__":
    unittest.main()
