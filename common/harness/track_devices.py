"""Where each switch and its light stand, in each module's names.

A switch is named by its line and the block it is listed on in the
track layout file (``conventions/identifiers``): Green block 12 lists
``12-13; 1-13``, so its ID is ``("Green", "12")``. The Track Controller
names it so, and names the switch's light after it too. The Track Model
names a switch by its point, the block where its legs meet
(``GREEN D-13``), and its light the same: signals sit at switches, one
per switch, at the switch (``decisions/signals-at-switches``, proposed;
TM-2, 2026-10-27). The light faces a train coming onto the point from
its fixed side. The harness maps one module's names to the other's
through the switch, with a ``SwitchPlace`` for each:

=========  =====  ======  =====
line       ID     point   light
=========  =====  ======  =====
Green      12     13      13
Green      28     28      28
Green      58     57      57
Green      62     63      63
Green      76     77      77
Green      85     85      85
=========  =====  ======  =====

Switch positions mean the same in both: NORMAL is the first connection
the layout file lists, REVERSE the second (``signals/switch-command``).

The places come from the layout files the system runs on (D023: Green
and Red), the same files both modules read, by the rules both apply:

- the point is the block both connections share, or for a switch to or
  from the yard the block its one connection names (``57-yard``: 57,
  ``Yard-63``: 63);
- the legs are the other ends; a yard switch's are the yard and the
  next block along the line, 58 for ``57-yard`` and 62 for
  ``Yard-63``;
- the light stands at the point. The point has one neighbour that is
  neither leg, its fixed side, where the light faces; the neighbours
  are what each block's ``next_blocks`` joins it to, either way.

The harness's tests check the places against both modules' own
readings of the files.
"""

from __future__ import annotations

__all__ = [
    "LAYOUT_FILES",
    "SwitchPlace",
    "TrackDevices",
    "layout_dir",
    "switch_places",
]

import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The layout file of each line in the system (D023).
LAYOUT_FILES: Mapping[str, str] = {
    "Green": "green_line.json",
    "Red": "red_line.json",
}

YARD = "yard"

# One end of a connection in a switch's text: a block number or the
# yard, joined by "-" or "to".
_SPLIT = re.compile(r"\s*(?:-|\bto\b)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class SwitchPlace:
    """One switch, by the blocks each module names it by.

    Attributes:
        line: Its line, ``"Green"`` or ``"Red"``.
        switch_id: The block it is listed on: its ID
            (``conventions/identifiers``), the Track Controller's name
            for it and for its light.
        point: The block where its legs meet: the Track Model's name
            for it.
        light: The block its light stands on in the Track Model: its
            point, since signals sit at switches (TM-2).
    """

    line: str
    switch_id: str
    point: str
    light: str


def layout_dir() -> Path:
    """Return the folder of the layout files.

    The Track Model's folder: in the repository, or in a built
    executable's bundle, laid out the same.
    """
    root = getattr(sys, "_MEIPASS", None)
    if root is None:
        return Path(__file__).resolve().parents[2] / "TrackModel"
    return Path(root) / "TrackModel"


def switch_places(layout: Mapping[str, Any]) -> tuple[SwitchPlace, ...]:
    """Return every switch on one line, from its decoded layout file.

    Args:
        layout: The layout file's JSON: its ``line`` and its
            ``blocks``, each with its ``block_number``,
            ``next_blocks`` and any ``infrastructure.switch``.

    Raises:
        ValueError: If a switch's text cannot be read, or its light
            cannot be placed.
    """
    line = str(layout["line"])
    rows = {str(row["block_number"]): row for row in layout["blocks"]}
    neighbours = _neighbours(rows)
    places = []
    for block, row in rows.items():
        text = (row.get("infrastructure") or {}).get("switch")
        if not text:
            continue
        point, legs = _point_and_legs(str(text))
        if (
            line == "Red" and block == "9"
            and str(text).strip() == "75-yard"
        ):
            # Assumption: yard arrivals leave 9 on its fixed side toward 10.
            point, legs = block, {str(int(block) - 1), YARD}
        beside = neighbours.get(point, set()) - legs
        if len(beside) != 1:
            raise ValueError(
                f"{line} switch {block} ({text!r}): no one fixed side for "
                f"its light at {point}, found {sorted(beside)}"
            )
        # The light stands at the switch, facing the fixed side.
        places.append(SwitchPlace(line, block, point, point))
    return tuple(places)


class TrackDevices:
    """Every switch place, looked up by any of its names."""

    def __init__(self, places: Iterable[SwitchPlace]) -> None:
        """Index ``places``."""
        self._places = tuple(places)
        self._by_switch = {(p.line, p.switch_id): p for p in self._places}
        self._by_point = {(p.line, p.point): p for p in self._places}
        self._by_light = {(p.line, p.light): p for p in self._places}

    @classmethod
    def load(cls, directory: Path | None = None) -> TrackDevices:
        """Read the switch places from every line's layout file.

        Args:
            directory: Where the files are; ``layout_dir()`` if None.

        Raises:
            OSError: If a file cannot be read.
            ValueError: If a file is malformed.
        """
        folder = layout_dir() if directory is None else directory
        places: list[SwitchPlace] = []
        for name in LAYOUT_FILES.values():
            with open(folder / name, encoding="utf-8") as handle:
                places += switch_places(json.load(handle))
        return cls(places)

    def places(self, line: str) -> tuple[SwitchPlace, ...]:
        """Return the switches on ``line``, in layout order."""
        return tuple(p for p in self._places if p.line == line)

    def by_switch(self, line: str, switch_id: str) -> SwitchPlace:
        """Return the switch with ID ``switch_id``.

        Raises:
            KeyError: If ``line`` has no such switch.
        """
        return self._by_switch[(line, switch_id)]

    def by_point(self, line: str, point: str) -> SwitchPlace:
        """Return the switch whose point is block ``point``.

        Raises:
            KeyError: If no switch on ``line`` has that point.
        """
        return self._by_point[(line, point)]

    def by_light(self, line: str, light: str) -> SwitchPlace:
        """Return the switch whose light stands on block ``light``.

        Raises:
            KeyError: If no light on ``line`` stands there.
        """
        return self._by_light[(line, light)]


def _neighbours(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, set[str]]:
    # The blocks each block's next_blocks joins it to, either way; the
    # yard is not a block.
    found: dict[str, set[str]] = {block: set() for block in rows}
    for block, row in rows.items():
        for after in row.get("next_blocks", ()):
            if str(after).lower() == YARD:
                continue
            found[block].add(str(after))
            found.setdefault(str(after), set()).add(block)
    return found


def _point_and_legs(text: str) -> tuple[str, set[str]]:
    # A switch's point and its legs, from its text in the layout file.
    connections = [_ends(part) for part in text.split(";") if part.strip()]
    if len(connections) == 2:
        shared = set(connections[0]) & set(connections[1])
        if len(shared) != 1 or YARD in shared:
            raise ValueError(f"switch {text!r}: no one shared block")
        point = shared.pop()
        legs = {end for ends in connections for end in ends} - {point}
        return point, legs
    if len(connections) == 1 and YARD in connections[0]:
        first, second = connections[0]
        if second == YARD:
            # Leaving the point for the yard instead of the next block.
            return first, {str(int(first) + 1), YARD}
        # Entering the point from the yard instead of the block before.
        return second, {str(int(second) - 1), YARD}
    raise ValueError(f"switch {text!r}: not a switch this reads")


def _ends(part: str) -> tuple[str, ...]:
    # The two ends of one connection, as block numbers or the yard.
    ends = [end for end in _SPLIT.split(part.strip()) if end]
    if len(ends) != 2:
        raise ValueError(f"{part.strip()!r} is not a connection")
    return tuple(
        YARD if end.lower() == YARD else str(int(end)) for end in ends
    )
