"""Unit conversions (truth conventions/units.md).

Everything stored, computed or passed across a module boundary is
metric SI; everything the operator reads is imperial, except power,
which is read in kilowatts. Only the backend's snapshot converts.
"""

MPS_TO_MPH = 2.236936
W_TO_KW = 0.001
KMH_PER_MPS = 3.6


def c_to_f(celsius: float) -> float:
    """Convert a backend Celsius figure to displayed Fahrenheit."""
    return celsius * 9 / 5 + 32


def f_to_c(fahrenheit: float) -> float:
    """Convert a Fahrenheit figure the operator set back to Celsius."""
    return (fahrenheit - 32) * 5 / 9
