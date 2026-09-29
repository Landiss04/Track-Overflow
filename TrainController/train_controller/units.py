"""Backend-to-frontend unit conversions, per ``common/Units.md``.

The controller keeps state in SI (backend) units and converts only at the
display boundary, so every factor lives here and nowhere else.
"""

from __future__ import annotations

MPS_TO_MPH = 2.23694
M_TO_FT = 3.28084


def mps_to_mph(speed_mps: float) -> float:
    """Return a speed in miles per hour."""
    return speed_mps * MPS_TO_MPH


def mph_to_mps(speed_mph: float) -> float:
    """Return a speed in metres per second."""
    return speed_mph / MPS_TO_MPH


def m_to_ft(distance_m: float) -> float:
    """Return a distance in feet."""
    return distance_m * M_TO_FT


def ft_to_m(distance_ft: float) -> float:
    """Return a distance in metres."""
    return distance_ft / M_TO_FT


def c_to_f(temp_c: float) -> float:
    """Return a temperature in degrees Fahrenheit."""
    return temp_c * 9 / 5 + 32


def f_to_c(temp_f: float) -> float:
    """Return a temperature in degrees Celsius."""
    return (temp_f - 32) * 5 / 9
