"""Deterministic tests for ``SystemClock``.

Run from the repository root with ``python -m unittest discover utils``.
"""

from __future__ import annotations

import unittest

from utils.system_clock import (
    ALLOWED_SPEEDS,
    DEFAULT_START_TIME_S,
    DEFAULT_TICK_S,
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    InvalidClockSettingError,
    SystemClock,
)

TICKS_PER_SIM_DAY = round(SECONDS_PER_DAY / DEFAULT_TICK_S)


def _clock_at(hours: int, minutes: int, seconds: float) -> SystemClock:
    # A clock that starts at the given time of day.
    return SystemClock(
        start_time_s=(
            hours * SECONDS_PER_HOUR + minutes * SECONDS_PER_MINUTE + seconds
        )
    )


class DefaultsTest(unittest.TestCase):
    """The clock's out-of-the-box settings."""

    def test_starts_at_five_am(self) -> None:
        """Start at 05:00:00 simulated time."""
        clock = SystemClock()
        self.assertEqual(DEFAULT_START_TIME_S, 5 * SECONDS_PER_HOUR)
        self.assertEqual(clock.sim_time_s, 5 * SECONDS_PER_HOUR)
        self.assertEqual(clock.format_time_of_day(), "05:00:00")

    def test_default_tick_and_speed(self) -> None:
        """Default to 0.1 s ticks at 1x, held until resumed."""
        clock = SystemClock()
        self.assertEqual(clock.tick_s, 0.1)
        self.assertEqual(clock.speed, 1)
        self.assertTrue(clock.is_paused)
        self.assertEqual(clock.tick_count, 0)
        self.assertEqual(clock.elapsed_s, 0.0)


class MilitaryTimeTest(unittest.TestCase):
    """``format_time_of_day`` is 24-hour, zero-padded HH:MM:SS."""

    def test_afternoon_uses_24_hour_hours(self) -> None:
        """Show 1:05:09 PM as 13:05:09."""
        self.assertEqual(_clock_at(13, 5, 9).format_time_of_day(), "13:05:09")

    def test_zero_padding(self) -> None:
        """Pad single-digit fields with a leading zero."""
        self.assertEqual(_clock_at(0, 0, 0).format_time_of_day(), "00:00:00")
        self.assertEqual(_clock_at(9, 7, 3).format_time_of_day(), "09:07:03")

    def test_last_second_of_day(self) -> None:
        """Show the last second before midnight as 23:59:59."""
        self.assertEqual(
            _clock_at(23, 59, 59).format_time_of_day(), "23:59:59"
        )

    def test_partial_seconds_round_down(self) -> None:
        """Show a time partway through a second as that second."""
        self.assertEqual(
            _clock_at(12, 0, 59.95).format_time_of_day(), "12:00:59"
        )

    def test_rolls_over_midnight(self) -> None:
        """Wrap the time of day to 00:00:00; sim time keeps counting."""
        clock = _clock_at(23, 59, 59.95)
        clock.tick()
        self.assertEqual(clock.format_time_of_day(), "00:00:00")
        self.assertAlmostEqual(clock.sim_time_s, SECONDS_PER_DAY + 0.05)
        self.assertAlmostEqual(clock.time_of_day_s, 0.05)


class TickTest(unittest.TestCase):
    """Advancing simulation time."""

    def test_one_tick_advances_tick_s(self) -> None:
        """Advance by exactly one tick length."""
        clock = SystemClock()
        clock.tick()
        self.assertEqual(clock.tick_count, 1)
        self.assertAlmostEqual(clock.elapsed_s, DEFAULT_TICK_S)

    def test_ten_ticks_make_one_second(self) -> None:
        """Advance one simulated second in ten default ticks."""
        clock = SystemClock()
        for _ in range(10):
            clock.tick()
        self.assertEqual(clock.format_time_of_day(), "05:00:01")

    def test_no_drift_over_a_full_day(self) -> None:
        """Land exactly on 24 h after a day of ticks, with no drift."""
        clock = SystemClock()
        for _ in range(TICKS_PER_SIM_DAY):
            clock.tick()
        self.assertEqual(clock.tick_count, TICKS_PER_SIM_DAY)
        self.assertAlmostEqual(clock.elapsed_s, SECONDS_PER_DAY, places=9)
        self.assertEqual(clock.format_time_of_day(), "05:00:00")

    def test_custom_tick_length(self) -> None:
        """Honour a non-default tick length."""
        clock = SystemClock(tick_s=0.05)
        for _ in range(20):
            clock.tick()
        self.assertAlmostEqual(clock.elapsed_s, 1.0)

    def test_tick_advances_while_paused(self) -> None:
        """Step a held clock by hand, for test harnesses."""
        clock = SystemClock()
        self.assertTrue(clock.is_paused)
        clock.tick()
        self.assertEqual(clock.tick_count, 1)

    def test_speed_does_not_change_tick_length(self) -> None:
        """Keep tick length fixed at every speed (D006)."""
        clock = SystemClock()
        clock.set_speed(10)
        clock.tick()
        self.assertEqual(clock.tick_s, DEFAULT_TICK_S)
        self.assertAlmostEqual(clock.elapsed_s, DEFAULT_TICK_S)

    def test_tick_interval_scales_with_speed(self) -> None:
        """Shorten the real time between ticks by the speed factor."""
        clock = SystemClock()
        self.assertAlmostEqual(clock.tick_interval_s, 0.1)
        clock.set_speed(10)
        self.assertAlmostEqual(clock.tick_interval_s, 0.01)


class SettingsTest(unittest.TestCase):
    """Speed, pause, reset, and validation."""

    def test_only_1x_and_10x_allowed(self) -> None:
        """Accept 1x and 10x and reject every other speed."""
        self.assertEqual(ALLOWED_SPEEDS, (1, 10))
        clock = SystemClock()
        for speed in ALLOWED_SPEEDS:
            clock.set_speed(speed)
            self.assertEqual(clock.speed, speed)
        for bad in (0, -1, 2, 5, 100):
            with self.subTest(speed=bad):
                with self.assertRaises(InvalidClockSettingError):
                    clock.set_speed(bad)
        self.assertEqual(clock.speed, 10)

    def test_rejects_bad_construction(self) -> None:
        """Reject a non-positive tick, negative start, or bad speed."""
        for kwargs in (
            {"tick_s": 0},
            {"tick_s": -0.1},
            {"start_time_s": -1},
            {"speed": 3},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(InvalidClockSettingError):
                    SystemClock(**kwargs)  # type: ignore[arg-type]

    def test_pause_and_resume(self) -> None:
        """Toggle the paused flag."""
        clock = SystemClock()
        clock.resume()
        self.assertFalse(clock.is_paused)
        clock.pause()
        self.assertTrue(clock.is_paused)

    def test_reset_returns_to_start_and_holds(self) -> None:
        """Return to the start time and pause on reset."""
        clock = SystemClock()
        clock.resume()
        for _ in range(50):
            clock.tick()
        clock.reset()
        self.assertEqual(clock.tick_count, 0)
        self.assertTrue(clock.is_paused)
        self.assertEqual(clock.format_time_of_day(), "05:00:00")

    def test_reset_count_tells_reset_from_pause(self) -> None:
        """Count resets but not pauses."""
        clock = SystemClock()
        self.assertEqual(clock.reset_count, 0)
        clock.resume()
        clock.pause()
        self.assertEqual(clock.reset_count, 0)
        clock.reset()
        clock.reset()
        self.assertEqual(clock.reset_count, 2)

    def test_reset_to_new_start_time(self) -> None:
        """Move the start time on reset."""
        clock = SystemClock()
        clock.reset(start_time_s=6 * SECONDS_PER_HOUR)
        self.assertEqual(clock.format_time_of_day(), "06:00:00")
        with self.assertRaises(InvalidClockSettingError):
            clock.reset(start_time_s=-1)


class ListenerTest(unittest.TestCase):
    """Tick and state notifications."""

    def test_tick_listener_receives_time_and_tick(self) -> None:
        """Pass the new sim time and tick length to tick listeners."""
        clock = SystemClock()
        calls: list[tuple[float, float]] = []
        clock.add_tick_listener(lambda t, dt: calls.append((t, dt)))
        clock.tick()
        clock.tick()
        self.assertEqual(len(calls), 2)
        self.assertAlmostEqual(calls[1][0], DEFAULT_START_TIME_S + 0.2)
        self.assertEqual(calls[1][1], DEFAULT_TICK_S)

    def test_removed_tick_listener_is_not_called(self) -> None:
        """Stop notifying a removed tick listener."""
        clock = SystemClock()
        calls: list[float] = []

        def listener(sim_time_s: float, tick_s: float) -> None:
            calls.append(sim_time_s)

        clock.add_tick_listener(listener)
        clock.tick()
        clock.remove_tick_listener(listener)
        clock.tick()
        self.assertEqual(len(calls), 1)

    def test_listener_may_unsubscribe_during_tick(self) -> None:
        """Let a listener remove itself without skipping others."""
        clock = SystemClock()
        calls: list[str] = []

        def once(sim_time_s: float, tick_s: float) -> None:
            calls.append("once")
            clock.remove_tick_listener(once)

        clock.add_tick_listener(once)
        clock.add_tick_listener(lambda t, dt: calls.append("always"))
        clock.tick()
        clock.tick()
        self.assertEqual(calls, ["once", "always", "always"])

    def test_state_listener_fires_on_real_changes_only(self) -> None:
        """Notify on pause, resume, speed, and reset; skip no-ops."""
        clock = SystemClock()
        events: list[tuple[bool, int]] = []
        clock.add_state_listener(
            lambda: events.append((clock.is_paused, clock.speed))
        )
        clock.pause()
        clock.resume()
        clock.resume()
        clock.set_speed(10)
        clock.set_speed(10)
        clock.reset()
        self.assertEqual(events, [(False, 1), (False, 10), (True, 10)])


if __name__ == "__main__":
    unittest.main()
