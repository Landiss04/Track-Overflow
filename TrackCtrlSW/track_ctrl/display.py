"""Units for what the user sees.

The module works in the system's backend units: speed in whole m/s,
authority in blocks (``truth/conventions/units.md``, D002, D013). The
user interface shows speed in miles per hour. The conversion happens
here and only here, at the display layer, so nothing stored or passed
between modules is ever converted.
"""

from __future__ import annotations

import math

#: Backend to display. Used exactly as ``units.md`` gives it; only the
#: displayed result is rounded, never the factor.
MPH_PER_MPS = 2.236936


def mps_to_mph(speed_mps: float) -> float:
    """Convert a speed from m/s to mph for display."""
    return speed_mps * MPH_PER_MPS


def mph_to_mps(speed_mph: float) -> float:
    """Convert a speed typed in mph back to m/s."""
    return speed_mph / MPH_PER_MPS


def whole_mps_from_mph(speed_mph: float) -> int:
    """Convert mph to a whole m/s, rounding down.

    Speeds are sent as whole m/s and rounding down is the safe
    direction: a typed speed can only ever become slower.
    """
    return math.floor(mph_to_mps(speed_mph) + 1e-9)


def format_mph(speed_mps: float) -> str:
    """Render a backend speed for the screen, e.g. ``33.6 MPH``."""
    return f"{mps_to_mph(speed_mps):.1f} MPH"
