"""The vital power command: three calculations and a 2-out-of-3 vote.

The power command is this controller's only vital calculation
(REQUIREMENTS.md M21). Each tick it is calculated three times, fresh,
from the same inputs, and passed on only if at least two of the three
results are equal. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import MAX_POWER_W


@dataclass(frozen=True)
class PowerInputs:
    """One tick's inputs to the power law, the same for every channel.

    ``integral`` is the integrator as the last agreed result left it;
    ``braking`` is whether the service brake is commanded this tick.
    """

    target_mps: float
    actual_mps: float
    kp: float
    ki: float
    dt: float
    braking: bool
    integral: float


@dataclass(frozen=True)
class PowerResult:
    """One channel's power command and the integrator it leaves."""

    power_w: float
    integral: float


def compute_power(inputs: PowerInputs) -> PowerResult:
    """Calculate the power command once: one channel of the vote.

    Velocity error through Kp + Ki/s, clamped to 0..MAX_POWER_W with
    the integrator held at either end. Nothing is kept between calls,
    so each tick's three calculations start from the same inputs.
    """
    if inputs.braking:
        # Traction is cut whenever a brake is applied, and the
        # integrator holds rather than winding up against the brake
        # (arbitration/traction-cut-under-braking).
        return PowerResult(0.0, inputs.integral)
    error = inputs.target_mps - inputs.actual_mps
    integral = inputs.integral + error * inputs.dt
    power = inputs.kp * error + inputs.ki * integral
    if power > MAX_POWER_W:
        power = MAX_POWER_W
        integral -= error * inputs.dt
    elif power < 0.0:
        power = 0.0
        integral -= error * inputs.dt
    return PowerResult(power, integral)


@dataclass(frozen=True)
class VitalVote:
    """The three results and what the vote made of them.

    ``agreed`` is the result at least two channels gave, or None when
    no two are equal: a vitality breach. ``agreeing`` is how many gave
    it: 3, 2, or 0 on a breach.
    """

    results: tuple[PowerResult, PowerResult, PowerResult]
    agreed: PowerResult | None
    agreeing: int


def vote_2oo3(
    results: tuple[PowerResult, PowerResult, PowerResult],
) -> VitalVote:
    """Pass the result at least two of the three channels agree on.

    The channels are identical calculations on identical inputs, so
    agreeing means equal, power and integrator both: nothing is
    rounded. A result that is not a number never equals another, so a
    channel that produces one is always outvoted.
    """
    a, b, c = results
    if _equal(a, b) and _equal(b, c):
        return VitalVote(results, a, 3)
    for one, other in ((a, b), (a, c), (b, c)):
        if _equal(one, other):
            return VitalVote(results, one, 2)
    return VitalVote(results, None, 0)


def _equal(one: PowerResult, other: PowerResult) -> bool:
    # Field by field: comparing the dataclasses compares tuples, which
    # count the same NaN object as equal to itself.
    return (one.power_w == other.power_w
            and one.integral == other.integral)
