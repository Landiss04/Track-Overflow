"""Backend-to-display unit conversions.

Factors follow ``truth/conventions/units.md``. The controller keeps
state in backend (SI) units and converts only at the display boundary,
so every factor lives here and nowhere else. Authority is a block ID,
not a measurement, so it has no conversion.
"""

from __future__ import annotations

MPS_TO_MPH = 2.236936
M_TO_FT = 3.280840
KMH_PER_MPS = 3.6


def mps_to_mph(speed_mps: float) -> float:
    """Return a speed in miles per hour."""
    return speed_mps * MPS_TO_MPH


def mph_to_mps(speed_mph: float) -> float:
    """Return a speed in metres per second."""
    return speed_mph / MPS_TO_MPH


def kmh_to_mps(speed_kmh: float) -> float:
    """Return a layout-file speed in metres per second."""
    return speed_kmh / KMH_PER_MPS


def m_to_ft(distance_m: float) -> float:
    """Return a distance in feet."""
    return distance_m * M_TO_FT


def c_to_f(temp_c: float) -> float:
    """Return a temperature in degrees Fahrenheit."""
    return temp_c * 9 / 5 + 32


def f_to_c(temp_f: float) -> float:
    """Return a temperature in degrees Celsius."""
    return (temp_f - 32) * 5 / 9
