"""Speed limiter for the Train Model test UI's stand-in Train Controller.

The Train Model applies the power it is given and does not govern its own
speed (D009): regulating speed is the Train Controller's job. The test UI
stands in for the Train Controller (D010), so without this limiter a
steady power command entered there would accelerate the train without
bound.

The limiter is a PI control law in the course's discrete form: the speed
error is integrated with the trapezoidal rule, and the integration stops
while the output saturates (anti-windup). Its output only ever lowers the
entered power, so the speed settles at the cap instead of passing it. Well
over the cap, it cuts power and applies the service brake until the train
is back down to it. Like the rest of the test UI, this file is test
scaffolding and is removed at integration.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Proportional gain, in W per m/s of speed error.
KP_W_PER_MPS = 200_000.0
#: Integral gain, in W per m of integrated speed error.
KI_W_PER_M = 20_000.0
#: Over the cap by more than this, the service brake is applied.
BRAKE_MARGIN_MPS = 0.5


@dataclass(frozen=True, slots=True)
class LimiterState:
    """What the control law carries from one tick to the next."""

    integral_m: float = 0.0
    last_error_mps: float = 0.0
    braking: bool = False


@dataclass(frozen=True, slots=True)
class LimitedCommand:
    """The commands the stand-in Train Controller sends this tick."""

    power_w: float
    service_brake: bool
    # Whether the limiter lowered the power or applied the brake.
    limiting: bool


class SpeedLimiter:
    """Caps the entered power so the train's speed settles at a cap."""

    def __init__(
        self,
        kp: float = KP_W_PER_MPS,
        ki: float = KI_W_PER_M,
        brake_margin_mps: float = BRAKE_MARGIN_MPS,
    ) -> None:
        """Start with no integrated error and the brake released."""
        self._kp = kp
        self._ki = ki
        self._brake_margin_mps = brake_margin_mps
        self.state = LimiterState()

    def reset(self) -> None:
        """Forget the integrated error and release the brake."""
        self.state = LimiterState()

    def apply(
        self,
        dt: float,
        cap_mps: float,
        speed_mps: float,
        power_cmd_w: float,
        service_brake: bool,
    ) -> LimitedCommand:
        """Limit one tick's commands and advance the control law.

        Args:
            dt: Sample period in seconds.
            cap_mps: The speed the train must not exceed.
            speed_mps: The train's speed, as last reported.
            power_cmd_w: The power entered in the test UI; nonnegative.
            service_brake: The service brake command entered in the
                test UI.

        Returns:
            The power and service brake command to send this tick.
        """
        prev = self.state
        error = cap_mps - speed_mps
        braking = speed_mps > cap_mps + self._brake_margin_mps or (
            prev.braking and speed_mps > cap_mps
        )
        # The Train Controller cuts traction when it brakes.
        ceiling = 0.0 if braking else power_cmd_w

        integral = prev.integral_m + dt / 2.0 * (error + prev.last_error_mps)
        power = self._kp * error + self._ki * integral
        if not 0.0 < power < ceiling:
            # Saturated: hold the integral rather than wind it up.
            integral = prev.integral_m
            power = self._kp * error + self._ki * integral
        power = min(max(power, 0.0), ceiling)

        self.state = LimiterState(integral, error, braking)
        return LimitedCommand(
            power_w=power,
            service_brake=service_brake or braking,
            limiting=braking or power < power_cmd_w,
        )
