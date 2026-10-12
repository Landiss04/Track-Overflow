"""Display units and text formats shared by the CTC UI and its test UI.

Backend values are SI (m/s, m) and convert to display units (mph, ft)
only here, at the UI edge, per ``truth/conventions/units.md``. Times of
day are 24-hour ``HH:MM:SS`` (decision on the shared clock).
"""

from __future__ import annotations

MPS_TO_MPH = 2.236936
M_TO_FT = 3.280840

_DAY_S = 24 * 60 * 60


class TimeOfDayError(ValueError):
    """Text is not a 24-hour ``HH:MM`` or ``HH:MM:SS`` time."""


def parse_time_of_day(text: str) -> float:
    """Seconds since midnight from ``HH:MM`` or ``HH:MM:SS``."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise TimeOfDayError(
            f"'{text}' is not a time; use 24-hour HH:MM, e.g. 08:30")
    hours, minutes = int(parts[0]), int(parts[1])
    seconds = int(parts[2]) if len(parts) == 3 else 0
    if hours > 23 or minutes > 59 or seconds > 59:
        raise TimeOfDayError(f"'{text}' is not a valid time of day")
    return float(hours * 3600 + minutes * 60 + seconds)


def format_time_of_day(seconds: float) -> str:
    """``HH:MM`` for whole minutes, else ``HH:MM:SS``."""
    total = int(seconds) % _DAY_S
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if secs:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}"


def block_key(line: str, block_id: str) -> str:
    """``Line:block``, the text form of a block (or switch) reference."""
    return f"{line}:{block_id}"
