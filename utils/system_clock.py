"""Shared simulation clock.

One clock serves the whole system. At 1x speed one simulated second
lasts one real second; at 10x it lasts a tenth of a real second.
Simulation time advances in fixed ticks of ``tick_s`` seconds. Speed
and pause change how often ticks happen, never how long a tick is, so
every module sees the same behaviour at any speed.

The clock is passive and free of Qt: it advances only when ``tick()``
is called. ``utils.clock_driver.ClockDriver`` calls it in real time
for the running application, and tests or a test harness can call it
directly to step time by hand.
"""

from __future__ import annotations

__all__ = [
    "ALLOWED_SPEEDS",
    "DEFAULT_START_TIME_S",
    "DEFAULT_TICK_S",
    "InvalidClockSettingError",
    "SystemClock",
]

from collections.abc import Callable

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

DEFAULT_START_TIME_S = 5 * SECONDS_PER_HOUR
DEFAULT_TICK_S = 0.1
ALLOWED_SPEEDS = (1, 10)

TickListener = Callable[[float, float], None]
StateListener = Callable[[], None]


class InvalidClockSettingError(ValueError):
    """Raised when the clock is given an unsupported setting."""


class SystemClock:
    """Simulation clock that advances in fixed ticks.

    Simulation time is measured in seconds since midnight of the first
    simulated day. It keeps counting past midnight; use
    ``time_of_day_s`` or ``format_time_of_day()`` for a wall-clock
    reading.

    Tick listeners are called after every tick with
    ``(sim_time_s, tick_s)``. State listeners are called with no
    arguments whenever speed, pause, or a reset changes, so a driver
    can retime itself. ``reset_count`` tells a reset apart from a
    pause.
    """

    def __init__(
        self,
        tick_s: float = DEFAULT_TICK_S,
        start_time_s: float = DEFAULT_START_TIME_S,
        speed: int = 1,
    ) -> None:
        """Create a paused clock at ``start_time_s``.

        Args:
            tick_s: Simulated seconds per tick. Fixed for the life of
                the clock.
            start_time_s: Simulation time of the first tick, in
                seconds since midnight. Defaults to 05:00:00.
            speed: Speed multiplier; one of ``ALLOWED_SPEEDS``.

        Raises:
            InvalidClockSettingError: If ``tick_s`` is not positive,
                ``start_time_s`` is negative, or ``speed`` is not
                allowed.
        """
        if tick_s <= 0:
            raise InvalidClockSettingError(
                f"tick_s must be positive, got {tick_s}"
            )
        self._check_start_time(start_time_s)
        self._check_speed(speed)
        self._tick_s = tick_s
        self._start_time_s = start_time_s
        self._speed = speed
        self._tick_count = 0
        self._reset_count = 0
        self._paused = True
        self._tick_listeners: list[TickListener] = []
        self._state_listeners: list[StateListener] = []

    @property
    def tick_s(self) -> float:
        """Simulated seconds per tick."""
        return self._tick_s

    @property
    def speed(self) -> int:
        """Current speed multiplier."""
        return self._speed

    @property
    def is_paused(self) -> bool:
        """Whether the clock is held."""
        return self._paused

    @property
    def tick_count(self) -> int:
        """Ticks taken since the last reset."""
        return self._tick_count

    @property
    def reset_count(self) -> int:
        """Times the clock has been reset since it was created."""
        return self._reset_count

    @property
    def elapsed_s(self) -> float:
        """Simulated seconds since the last reset."""
        # Derived from the tick count, not accumulated, so repeated
        # float additions cannot drift.
        return self._tick_count * self._tick_s

    @property
    def sim_time_s(self) -> float:
        """Simulation time in seconds since the first midnight."""
        return self._start_time_s + self.elapsed_s

    @property
    def time_of_day_s(self) -> float:
        """Seconds since the most recent simulated midnight."""
        return self.sim_time_s % SECONDS_PER_DAY

    @property
    def tick_interval_s(self) -> float:
        """Real seconds between ticks at the current speed."""
        return self._tick_s / self._speed

    def tick(self) -> None:
        """Advance simulation time by one tick and notify listeners.

        This advances even while paused, so a test harness can step a
        held clock by hand. Real-time drivers skip ticks while paused.
        """
        self._tick_count += 1
        sim_time_s = self.sim_time_s
        for listener in list(self._tick_listeners):
            listener(sim_time_s, self._tick_s)

    def pause(self) -> None:
        """Hold the clock."""
        if not self._paused:
            self._paused = True
            self._notify_state()

    def resume(self) -> None:
        """Let the clock run."""
        if self._paused:
            self._paused = False
            self._notify_state()

    def set_speed(self, speed: int) -> None:
        """Set the speed multiplier.

        Args:
            speed: One of ``ALLOWED_SPEEDS``.

        Raises:
            InvalidClockSettingError: If ``speed`` is not allowed.
        """
        self._check_speed(speed)
        if speed != self._speed:
            self._speed = speed
            self._notify_state()

    def reset(self, start_time_s: float | None = None) -> None:
        """Return to the start time and hold the clock.

        Args:
            start_time_s: New start time in seconds since midnight.
                Keeps the current start time if omitted.

        Raises:
            InvalidClockSettingError: If ``start_time_s`` is negative.
        """
        if start_time_s is not None:
            self._check_start_time(start_time_s)
            self._start_time_s = start_time_s
        self._tick_count = 0
        self._reset_count += 1
        self._paused = True
        self._notify_state()

    def add_tick_listener(self, listener: TickListener) -> None:
        """Call ``listener(sim_time_s, tick_s)`` after every tick."""
        self._tick_listeners.append(listener)

    def remove_tick_listener(self, listener: TickListener) -> None:
        """Stop calling a tick listener."""
        self._tick_listeners.remove(listener)

    def add_state_listener(self, listener: StateListener) -> None:
        """Call ``listener()`` when speed, pause, or a reset changes."""
        self._state_listeners.append(listener)

    def remove_state_listener(self, listener: StateListener) -> None:
        """Stop calling a state listener."""
        self._state_listeners.remove(listener)

    def format_time_of_day(self) -> str:
        """Return the simulated time of day in 24-hour ``HH:MM:SS``.

        Military time: hours run 00 to 23, so 1:05 PM is ``13:05:00``.
        """
        whole_s = int(self.time_of_day_s)
        hours, remainder_s = divmod(whole_s, SECONDS_PER_HOUR)
        minutes, seconds = divmod(remainder_s, SECONDS_PER_MINUTE)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _notify_state(self) -> None:
        # Copy first so a listener may unsubscribe itself.
        for listener in list(self._state_listeners):
            listener()

    @staticmethod
    def _check_speed(speed: int) -> None:
        # Reject anything but the supported multipliers.
        if speed not in ALLOWED_SPEEDS:
            raise InvalidClockSettingError(
                f"speed must be one of {ALLOWED_SPEEDS}, got {speed}"
            )

    @staticmethod
    def _check_start_time(start_time_s: float) -> None:
        # Simulation time is counted from midnight, so it cannot start
        # before it.
        if start_time_s < 0:
            raise InvalidClockSettingError(
                f"start_time_s must not be negative, got {start_time_s}"
            )
