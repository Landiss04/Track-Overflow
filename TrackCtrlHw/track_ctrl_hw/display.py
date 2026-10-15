"""Display formatting for the Track Controller UIs.

Conversion happens here and nowhere else (``truth/conventions/
units.md``): state and signals stay in backend units, and only the text
a user reads is imperial. Factors are the convention's, applied
unrounded; only the displayed result is rounded, half up.
"""

from __future__ import annotations

import math

from track_ctrl_hw.interface import FailureKind, SignalAspect, SwitchPosition

MPH_PER_MPS = 2.236936
FT_PER_M = 3.280840
SECONDS_PER_DAY = 86400

NO_TIME = "--:--:--"
EM_DASH = "\u2014"

_ASPECT_NAMES = {
    "red": "Red",
    "yellow": "Yellow",
    "green": "Green",
    "super_green": "Super green",
}
_ASPECT_LETTERS = {
    "red": "R",
    "yellow": "Y",
    "green": "G",
    "super_green": "SG",
}
_FAILURE_NAMES = {
    "broken_rail": "Broken rail",
    "track_circuit": "Track circuit",
    "power": "Power failure",
}


def _half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def mph(speed_mps: float) -> str:
    """A speed in m/s, shown in whole mph."""
    return f"{_half_up(speed_mps * MPH_PER_MPS)} mph"


def feet(length_m: float) -> str:
    """A length in m, shown in whole feet."""
    return f"{_half_up(length_m * FT_PER_M)} ft"


def blocks(count: int) -> str:
    """An authority, in blocks."""
    return f"{count} block" if count == 1 else f"{count} blocks"


def clock(time_s: float | None) -> str:
    """Simulation time as a 24-hour ``HH:MM:SS`` time of day."""
    if time_s is None:
        return NO_TIME
    whole = int(math.floor(time_s)) % SECONDS_PER_DAY
    hours, rest = divmod(whole, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def aspect_name(aspect: SignalAspect | None) -> str:
    """``Super green``; an em dash when unknown."""
    return EM_DASH if aspect is None else _ASPECT_NAMES[aspect]


def aspect_letter(aspect: SignalAspect | None) -> str:
    """``SG``; an em dash when unknown."""
    return EM_DASH if aspect is None else _ASPECT_LETTERS[aspect]


def position_name(position: SwitchPosition | None) -> str:
    """``Normal`` or ``Reverse``; an em dash when unknown."""
    return EM_DASH if position is None else position.capitalize()


def crossing_name(active: bool | None) -> str:
    """What a crossing is doing; an em dash when unknown."""
    if active is None:
        return EM_DASH
    return "Lights on, gates down" if active else "Gates up"


def failure_name(failure: FailureKind | None) -> str:
    """``Broken rail``; ``None`` when there is no failure."""
    return "None" if failure is None else _FAILURE_NAMES[failure]
