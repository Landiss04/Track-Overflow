"""Stand-in Track Model for the Train Model test UI.

The test UI stands in for the Track Model (D010). With a track loaded,
it supplies the Track Model's per-block inputs itself: block, grade,
elevation, speed limit, polarity, station and beacon. It follows the
train along one route, moving to the next block once the offset the
Train Model reports reaches the block's length, and flips the track
circuit polarity on every block change, which is how the Train Model
detects one.

The Blue Line is loaded by default; ``test_ui.py --line red`` or
``--line green`` loads another, and ``--route`` sets the blocks to
travel. Each line's layout comes from the Track Model's own file in
``TrackModel/``, converted from the layout file's units to backend units
(``truth/conventions/units.md``). A route is a list of block ranges in
travel order; a range that counts down is travelled against the block
numbering, so its grades change sign. Travel is forward only, and the
train stays on the last block of the route. Like the rest of the test
UI, this file is test scaffolding and is removed at integration.

Beacons: where a layout marks transponders (the Blue Line), a
transponder announces the next station along the route. The Red and
Green layouts mark none, so the block just before each station
announces it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

#: Where the Track Model keeps its layout files.
LAYOUT_DIR = Path(__file__).resolve().parents[2] / "TrackModel"

#: The lines a test UI can load, by the name ``--line`` takes.
LINE_FILES: dict[str, str] = {
    "blue": "blue_line.json",
    "red": "red_line.json",
    "green": "green_line.json",
}

#: Each line's default route, as block ranges in travel order.
DEFAULT_ROUTES: dict[str, str] = {
    # Section A, then B through the switch at block 5, to Station B.
    "blue": "1-10",
    # From the yard at block 9 down to block 1, through the switch to
    # block 16, then on to South Hills Junction.
    "red": "9-1,16-66",
    # The loop from the yard at block 63 back to it at block 57.
    "green": "63-100,85-77,101-150,28-1,13-57",
}

#: The Track Model's Blue Line layout file.
BLUE_LINE_PATH = LAYOUT_DIR / LINE_FILES["blue"]

#: Sections in travel order. The switch at block 5 sets the leg: section
#: B leads to Station B, section C to Station C.
BLUE_LINE_ROUTE: tuple[str, ...] = ("A", "B")

# A beacon carries one platform side. Where a layout gives none (the
# Blue Line) it is assumed right; where a station has platforms on both
# sides, left.
_DEFAULT_PLATFORM_SIDE = "R"
_PLATFORM_SIDES = {"Left": "L", "Right": "R", "Left/Right": "L"}

_KMH_PER_MPS = 3.6


@dataclass(frozen=True, slots=True)
class TrackBlock:
    """One block of the loaded route, in backend units."""

    block_id: str
    length_m: float
    grade_deg: float
    elevation_m: float
    speed_limit_mps: float
    # Station in this block; empty where there is none.
    station: str
    # Station a beacon in this block announces; empty where none.
    beacon_station: str
    # The announced station's platform side and whether it is
    # underground.
    beacon_side: str = _DEFAULT_PLATFORM_SIDE
    beacon_underground: bool = False


def _grade_deg(grade_percent: float) -> float:
    # A grade of p percent rises p m per 100 m of run.
    return math.degrees(math.atan(grade_percent / 100.0))


def _station_name(raw: str | None, block_number: int) -> str:
    # The layout spreadsheet names Blue Line stations "Station B"; the
    # other lines name them in capitals, and one Green Line station
    # has no name at all.
    if not raw:
        return f"Station {block_number}"
    if len(raw) == 1:
        return f"Station {raw}"
    return raw.title()


def parse_route(text: str) -> list[tuple[int, int]]:
    """Parse block ranges, such as ``"63-100,85-77,13"``.

    Args:
        text: Comma-separated block numbers and inclusive ranges, in
            travel order. A range may count down.

    Returns:
        ``(block_number, direction)`` for each block in travel order,
        where direction is +1 along the block numbering and -1 against
        it. A lone block is travelled along the numbering.

    Raises:
        ValueError: If a part is not a block number or a range.
    """
    route: list[tuple[int, int]] = []
    for part in text.split(","):
        bounds = part.strip().split("-")
        if len(bounds) > 2 or not all(b.strip().isdigit() for b in bounds):
            raise ValueError(f"not a block or a block range: {part!r}")
        first, last = int(bounds[0]), int(bounds[-1])
        step = 1 if last >= first else -1
        route.extend((n, step) for n in range(first, last + step, step))
    return route


def blocks_from_route(
    layout: dict[str, Any], route: Sequence[tuple[int, int]],
) -> list[TrackBlock]:
    """Return a route's blocks, in travel order, from a layout file.

    Args:
        layout: The parsed layout file, as the Track Model stores it.
        route: ``(block_number, direction)`` pairs in travel order, as
            ``parse_route`` returns them.

    Returns:
        The route's blocks. A block travelled against the numbering has
        its grade negated, since grade is positive uphill in the
        direction of travel.

    Raises:
        KeyError: If a block lacks a field the route needs.
        ValueError: If the route is empty or names a block the layout
            does not have.
    """
    if not route:
        raise ValueError("a route needs at least one block")
    rows = {row["block_number"]: row for row in layout["blocks"]}
    missing = sorted({n for n, _ in route if n not in rows})
    if missing:
        raise ValueError(f"no such blocks on this line: {missing}")
    path = [(rows[n], step) for n, step in route]
    infra = [row.get("infrastructure", {}) for row, _ in path]
    stations = [
        _station_name(i["station"], row["block_number"])
        if "station" in i else ""
        for (row, _), i in zip(path, infra)
    ]
    # Which block on the route announces each station: a transponder
    # where the layout has any, else the block just before the station.
    has_transponders = any(
        row.get("infrastructure", {}).get("transponder")
        for row in layout["blocks"]
    )
    beacons: dict[int, int] = {}
    for index in range(len(path)):
        if has_transponders:
            if not infra[index].get("transponder"):
                continue
            ahead = range(index + 1, len(path))
            target = next((j for j in ahead if stations[j]), None)
        else:
            target = index + 1
            if target >= len(path) or not stations[target]:
                continue
        if target is not None:
            beacons[index] = target

    blocks = []
    for index, (row, step) in enumerate(path):
        target = beacons.get(index)
        side, underground = _DEFAULT_PLATFORM_SIDE, False
        if target is not None:
            side = _PLATFORM_SIDES.get(
                path[target][0].get("station_side") or "",
                _DEFAULT_PLATFORM_SIDE,
            )
            underground = bool(infra[target].get("underground"))
        blocks.append(TrackBlock(
            # Block IDs are strings, never integers (identifiers.md).
            block_id=str(row["block_number"]),
            length_m=float(row["length_m"]),
            # Adding 0.0 turns the -0.0 of a negated flat grade into 0.0.
            grade_deg=_grade_deg(step * float(row["grade_percent"]) + 0.0),
            elevation_m=float(row["cumulative_elevation_m"]),
            speed_limit_mps=float(row["speed_limit_kmh"]) / _KMH_PER_MPS,
            station=stations[index],
            beacon_station=stations[target] if target is not None else "",
            beacon_side=side,
            beacon_underground=underground,
        ))
    return blocks


def blocks_from_layout(
    layout: dict[str, Any], sections: Sequence[str],
) -> list[TrackBlock]:
    """Return the blocks of whole sections, in travel order.

    Args:
        layout: The parsed layout file, as the Track Model stores it.
        sections: Section letters in travel order; each section's
            blocks are travelled along the numbering.

    Returns:
        The route's blocks, as ``blocks_from_route`` builds them.

    Raises:
        KeyError: If a block lacks a field the route needs.
        ValueError: If no block lies on the route.
    """
    rows = sorted(
        (row for row in layout["blocks"] if row["section"] in sections),
        key=lambda row: (sections.index(row["section"]),
                         row["block_number"]),
    )
    if not rows:
        raise ValueError(f"no blocks in sections {list(sections)}")
    return blocks_from_route(
        layout, [(row["block_number"], 1) for row in rows]
    )


class TrackStub:
    """Follows the train along a fixed route of blocks."""

    def __init__(self, name: str, blocks: Sequence[TrackBlock]) -> None:
        """Start on the first block.

        Args:
            name: The line's name, for display.
            blocks: The route's blocks in travel order; at least one.

        Raises:
            ValueError: If ``blocks`` is empty.
        """
        if not blocks:
            raise ValueError("a route needs at least one block")
        self.name = name
        self._blocks = tuple(blocks)
        self._index = 0
        self._polarity = False

    @property
    def block(self) -> TrackBlock:
        """The block the train is on."""
        return self._blocks[self._index]

    @property
    def route(self) -> tuple[TrackBlock, ...]:
        """Every block of the route, in travel order."""
        return self._blocks

    def reset(self) -> None:
        """Return to the first block."""
        self._index = 0
        self._polarity = False

    def follow(self, offset_m: float) -> bool:
        """Move to the next block once the train has left this one.

        Args:
            offset_m: The train's offset into the current block, as the
                Train Model last reported it.

        Returns:
            Whether the train changed block.
        """
        last = len(self._blocks) - 1
        if offset_m < self.block.length_m or self._index == last:
            return False
        self._index += 1
        self._polarity = not self._polarity
        return True

    def inputs(self) -> dict[str, Any]:
        """The test UI's track input rows for the current block."""
        block = self.block
        return {
            "block": block.block_id,
            "grade": block.grade_deg,
            "elevation": block.elevation_m,
            "speed_limit": block.speed_limit_mps,
            "polarity": self._polarity,
            "station": block.station,
            "beacon_station": block.beacon_station,
            "beacon_platform_side": block.beacon_side,
            "beacon_underground": block.beacon_underground,
        }


def load_line(
    line: str,
    route: str | None = None,
    layout_dir: Path = LAYOUT_DIR,
) -> TrackStub:
    """Load one line's layout along a route.

    Args:
        line: ``"blue"``, ``"red"`` or ``"green"``.
        route: Block ranges in travel order, as ``parse_route`` takes
            them; the line's default route when None.
        layout_dir: Where the layout files are.

    Returns:
        A stub that follows the route from its first block.

    Raises:
        KeyError: If the line is unknown or a block lacks a field.
        OSError: If the layout file cannot be read.
        ValueError: If the file is not valid JSON, or the route is
            malformed or names a block the line does not have.
    """
    path = layout_dir / LINE_FILES[line]
    layout = json.loads(path.read_text(encoding="utf-8"))
    ranges = DEFAULT_ROUTES[line] if route is None else route
    blocks = blocks_from_route(layout, parse_route(ranges))
    return TrackStub(f"{line.title()} Line", blocks)


def load_blue_line(
    path: Path = BLUE_LINE_PATH,
    sections: Sequence[str] = BLUE_LINE_ROUTE,
) -> TrackStub | None:
    """Load the Blue Line, or return None if its layout is unavailable."""
    try:
        layout = json.loads(path.read_text(encoding="utf-8"))
        return TrackStub("Blue Line", blocks_from_layout(layout, sections))
    except (OSError, ValueError, KeyError, TypeError):
        return None
