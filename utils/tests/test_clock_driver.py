"""Real-time accuracy tests for ``ClockDriver``.

Every tick is timestamped against a high-resolution wall clock. From
the logged speed changes and pauses the tests work out the exact real
moment each tick fell due, and check how late it actually ran. They
take about 20 s of real time.

Run from the repository root with ``python -m unittest discover utils``.
Set ``CLOCK_TEST_REPORT=1`` to print the measured accuracy.
"""

from __future__ import annotations

import math
import os
import sys
import time
import unittest
from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from utils.clock_driver import MAX_CATCH_UP_TICKS, ClockDriver
from utils.system_clock import DEFAULT_TICK_S, SystemClock

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

REPORT = os.environ.get("CLOCK_TEST_REPORT") == "1"

# How late ticks may run after they fall due, in real seconds. Typical
# lateness is held tight; the single worst tick only has to survive an
# OS scheduling spike, which on Windows can reach a few tens of ms.
MAX_MEAN_LATENESS_S = 0.005
MAX_P95_LATENESS_S = 0.010
MAX_LATENESS_S = 0.050
# How early a tick may run: only timestamp noise between Qt's timer and
# Python's ``perf_counter``.
MAX_EARLINESS_S = 0.002
# Long-run rate must match the commanded speed this closely.
MAX_RATE_ERROR = 0.005

Script = list[tuple[int, Callable[[], None]]]


class _Recorder:
    """Log every tick and state change against a wall clock."""

    def __init__(self, clock: SystemClock) -> None:
        """Start recording ``clock``."""
        self.clock = clock
        self.origin_s = time.perf_counter()
        # (wall time, speed, running) at each state change.
        self.segments: list[tuple[float, int, bool]] = []
        # (wall time, simulated elapsed seconds) at each tick.
        self.samples: list[tuple[float, float]] = []
        clock.add_tick_listener(self._on_tick)
        clock.add_state_listener(self._on_state)
        self._on_state()

    def now_s(self) -> float:
        """Return wall seconds since recording began."""
        return time.perf_counter() - self.origin_s

    def ideal_elapsed_s(self, at_s: float) -> float:
        """Return the exact simulated time due by ``at_s``."""
        total = 0.0
        for (start, speed, running), end in self._spans():
            if running and start < at_s:
                total += (min(end, at_s) - start) * speed
        return total

    def due_at_s(self, sim_elapsed_s: float) -> float:
        """Return the wall time at which ``sim_elapsed_s`` fell due."""
        total = 0.0
        for (start, speed, running), end in self._spans():
            if not running:
                continue
            span_s = (end - start) * speed
            if total + span_s >= sim_elapsed_s - 1e-9:
                return start + (sim_elapsed_s - total) / speed
            total += span_s
        return math.inf

    def lateness_s(self) -> list[float]:
        """Return how late each tick ran after it fell due."""
        return [
            wall - self.due_at_s(elapsed) for wall, elapsed in self.samples
        ]

    def _spans(self) -> list[tuple[tuple[float, int, bool], float]]:
        # Pair each segment with the wall time it ended.
        ends = [start for start, _, _ in self.segments[1:]] + [math.inf]
        return list(zip(self.segments, ends))

    def _on_tick(self, sim_time_s: float, tick_s: float) -> None:
        # Timestamp each tick the moment it happens.
        self.samples.append((self.now_s(), self.clock.elapsed_s))

    def _on_state(self) -> None:
        # Start a new constant-speed segment.
        self.segments.append(
            (self.now_s(), self.clock.speed, not self.clock.is_paused)
        )


def _run(script: Script) -> None:
    # Run each step's action ``delay_ms`` after the previous step, one
    # at a time, then return. Chaining keeps steps in order and leaves
    # no timer pending once the script ends.
    loop = QEventLoop()
    steps = list(script)

    def advance() -> None:
        if not steps:
            loop.quit()
            return
        delay_ms, action = steps.pop(0)

        def fire() -> None:
            action()
            advance()

        QTimer.singleShot(delay_ms, fire)

    advance()
    loop.exec()


def _noop() -> None:
    # Placeholder action that only marks a point in the script.
    return None


class ClockDriverAccuracyTest(unittest.TestCase):
    """Simulated time keeps pace with real time at each speed."""

    def setUp(self) -> None:
        """Create a clock, its recorder, and a started driver."""
        self.clock = SystemClock()
        self.recorder = _Recorder(self.clock)
        self.driver = ClockDriver(self.clock)
        self.driver.start()

    def tearDown(self) -> None:
        """Stop the driver."""
        self.driver.stop()

    def assert_ticks_on_time(self, label: str) -> None:
        """Check every tick ran on time and none are missing."""
        lateness = self.recorder.lateness_s()
        self.assertTrue(lateness, "no ticks were recorded")
        end_s = self.recorder.now_s()
        ideal_ticks = math.floor(
            self.recorder.ideal_elapsed_s(end_s) / DEFAULT_TICK_S + 1e-9
        )
        mean_s = sum(lateness) / len(lateness)
        ordered = sorted(lateness)
        p95_s = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        if REPORT:
            print(
                f"\n  {label}: {len(lateness)} ticks, lateness "
                f"mean {1000 * mean_s:.2f} ms, p95 {1000 * p95_s:.2f} ms, "
                f"worst {1000 * max(lateness):.2f} ms, "
                f"earliest {1000 * min(lateness):+.2f} ms; "
                f"{self.clock.tick_count} of {ideal_ticks} ideal ticks run"
            )
        self.assertLessEqual(mean_s, MAX_MEAN_LATENESS_S)
        self.assertLessEqual(p95_s, MAX_P95_LATENESS_S)
        self.assertLessEqual(max(lateness), MAX_LATENESS_S)
        self.assertGreaterEqual(min(lateness), -MAX_EARLINESS_S)
        # The last tick may still be within its lateness window.
        self.assertIn(
            self.clock.tick_count, (ideal_ticks - 1, ideal_ticks)
        )

    def assert_rate(self, expected_speed: int, label: str) -> None:
        """Check the long-run rate from first tick to last tick."""
        (wall_0, sim_0), (wall_1, sim_1) = (
            self.recorder.samples[0],
            self.recorder.samples[-1],
        )
        rate = (sim_1 - sim_0) / (wall_1 - wall_0)
        if REPORT:
            print(f"  {label}: rate {rate:.4f}x")
        self.assertAlmostEqual(
            rate, expected_speed, delta=expected_speed * MAX_RATE_ERROR
        )

    def test_1x_tracks_real_time(self) -> None:
        """At 1x, one simulated second per real second for 5 s."""
        _run([(0, self.clock.resume), (5000, _noop)])
        self.assert_ticks_on_time("1x for 5 s")
        self.assert_rate(1, "1x for 5 s")

    def test_10x_runs_ten_times_real_time(self) -> None:
        """At 10x, ten simulated seconds per real second for 3 s."""
        self.clock.set_speed(10)
        _run([(0, self.clock.resume), (3000, _noop)])
        self.assert_ticks_on_time("10x for 3 s")
        self.assert_rate(10, "10x for 3 s")

    def test_pause_freezes_simulated_time(self) -> None:
        """No ticks at all while paused; time resumes where it left."""
        marks: dict[str, tuple[float, float]] = {}

        def pause() -> None:
            self.clock.pause()
            marks["paused"] = (self.recorder.now_s(), self.clock.elapsed_s)

        def resume() -> None:
            marks["resumed"] = (self.recorder.now_s(), self.clock.elapsed_s)
            self.clock.resume()

        _run([
            (0, self.clock.resume),
            (500, pause),
            (1000, resume),
            (500, _noop),
        ])
        paused_at_s, sim_at_pause_s = marks["paused"]
        resumed_at_s, sim_at_resume_s = marks["resumed"]
        if REPORT:
            print(
                f"\n  pause: held {resumed_at_s - paused_at_s:.3f} s real, "
                f"sim moved {sim_at_resume_s - sim_at_pause_s:.3f} s"
            )
        self.assertEqual(sim_at_resume_s, sim_at_pause_s)
        ticks_while_paused = [
            wall for wall, _ in self.recorder.samples
            if paused_at_s < wall < resumed_at_s
        ]
        self.assertEqual(ticks_while_paused, [])
        self.assert_ticks_on_time("pause 1 s between two 0.5 s runs")

    def test_rapid_speed_changes_lose_no_time(self) -> None:
        """Switch 1x/10x every 37 ms for 3 s without drifting."""
        script: Script = [(0, self.clock.resume)]
        for index in range(81):
            speed = 10 if index % 2 == 0 else 1
            script.append((37, partial(self.clock.set_speed, speed)))
        _run(script)
        self.assert_ticks_on_time("81 speed changes in 3 s")

    def test_rapid_pause_toggles_lose_no_time(self) -> None:
        """Pause and resume every 23 ms for 2 s without drifting."""
        script: Script = [(0, self.clock.resume)]
        for index in range(87):
            action = self.clock.pause if index % 2 == 0 else self.clock.resume
            script.append((23, action))
        _run(script)
        self.assert_ticks_on_time("87 pause toggles in 2 s")

    def test_reset_while_running_starts_fresh(self) -> None:
        """Reset to the start, hold, then keep real time again."""
        _run([(0, self.clock.resume), (450, self.clock.reset)])
        self.assertTrue(self.clock.is_paused)
        self.assertEqual(self.clock.tick_count, 0)
        self.assertEqual(self.clock.format_time_of_day(), "05:00:00")
        self.recorder.samples.clear()
        resumed_at_s = self.recorder.now_s()
        _run([(0, self.clock.resume), (1000, _noop)])
        running_s = self.recorder.now_s() - resumed_at_s
        # Nothing carried over from before the reset: the first tick
        # after resuming lands one full tick later.
        first_tick_wall_s = self.recorder.samples[0][0]
        self.assertGreaterEqual(
            first_tick_wall_s - resumed_at_s,
            DEFAULT_TICK_S - MAX_EARLINESS_S,
        )
        self.assertAlmostEqual(
            self.clock.elapsed_s, running_s, delta=DEFAULT_TICK_S
        )

    def test_stop_halts_ticks(self) -> None:
        """Run no ticks after the driver is stopped."""
        _run([(0, self.clock.resume), (300, self.driver.stop)])
        ticks_at_stop = self.clock.tick_count
        _run([(500, _noop)])
        self.assertFalse(self.driver.is_running)
        self.assertEqual(self.clock.tick_count, ticks_at_stop)

    def test_stall_drops_backlog_instead_of_bursting(self) -> None:
        """After a 2 s freeze at 10x, slip time instead of replaying."""
        self.clock.set_speed(10)
        bursts: list[int] = []
        last_wall_s = [-1.0]

        def note_burst(sim_time_s: float, tick_s: float) -> None:
            # Group ticks that land within 1 ms of the previous one.
            now_s = self.recorder.now_s()
            if bursts and now_s - last_wall_s[0] < 0.001:
                bursts[-1] += 1
            else:
                bursts.append(1)
            last_wall_s[0] = now_s

        self.clock.add_tick_listener(note_burst)
        _run([
            (0, self.clock.resume),
            (300, lambda: time.sleep(2.0)),
            (1000, _noop),
        ])
        stalled_ticks = round(2.0 / self.clock.tick_interval_s)
        if REPORT:
            print(
                f"\n  stall: {stalled_ticks} ticks missed, largest burst "
                f"{max(bursts)}, sim {self.clock.elapsed_s:.2f} s after "
                f"1.3 s of running"
            )
        self.assertGreater(stalled_ticks, MAX_CATCH_UP_TICKS)
        self.assertLessEqual(max(bursts), MAX_CATCH_UP_TICKS)
        # 0.3 s + 1 s of running at 10x; the frozen 2 s is dropped.
        self.assertAlmostEqual(self.clock.elapsed_s, 13.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
