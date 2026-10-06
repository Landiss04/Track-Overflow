"""Stand-in Track Model for the Train Model test UI.

The test UI stands in for the Track Model (D010). With a track loaded,
it supplies the Track Model's per-block inputs itself: block, grade,
elevation, speed limit, polarity, station and beacon. It follows the
train along one route, moving to the next block once the offset the
Train Model reports reaches the block's length, and flips the track
circuit polarity on every block change, which is how the Train Model
detects one.

The Blue Line is loaded by default. Its layout comes from the Track
Model's own file, ``TrackModel/blue_line.json``, converted from the
layout file's units to backend units (``truth/conventions/units.md``).
Travel is forward only, and the train stays on the last block of the
route. Like the rest of the test UI, this file is test scaffolding and
is removed at integration.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

#: The Track Model's Blue Line layout file.
BLUE_LINE_PATH = (
    Path(__file__).resolve().parents[2] / "TrackModel" / "blue_line.json"
)

#: Sections in travel order. The switch at block 5 sets the leg: section
#: B leads to Station B, section C to Station C.
BLUE_LINE_ROUTE: tuple[str, ...] = ("A", "B")

# The Blue Line layout gives no platform side, and none of it is
# underground.
_PLATFORM_SIDE = "R"
_UNDERGROUND = False

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
    # Station a transponder in this block announces; empty where none.
    beacon_station: str


def _grade_deg(grade_percent: float) -> float:
    # A grade of p percent rises p m per 100 m of run.
    return math.degrees(math.atan(grade_percent / 100.0))


def _station_name(raw: str) -> str:
    # The layout spreadsheet names Blue Line stations "Station B".
    return f"Station {raw}"


def blocks_from_layout(
    layout: dict[str, Any], sections: Sequence[str],
) -> list[TrackBlock]:
    """Return a route's blocks, in travel order, from a layout file.

    Args:
        layout: The parsed layout file, as the Track Model stores it.
        sections: Section letters in travel order.

    Returns:
        The route's blocks. A transponder block announces the next
        station along the route.

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
    stations = [
        _station_name(row["infrastructure"]["station"])
        if "station" in row.get("infrastructure", {}) else ""
        for row in rows
    ]
    blocks = []
    for index, row in enumerate(rows):
        infrastructure = row.get("infrastructure", {})
        announced = ""
        if infrastructure.get("transponder"):
            announced = next(
                (name for name in stations[index + 1:] if name), ""
            )
        blocks.append(TrackBlock(
            # Block IDs are strings, never integers (identifiers.md).
            block_id=str(row["block_number"]),
            length_m=float(row["length_m"]),
            grade_deg=_grade_deg(float(row["grade_percent"])),
            elevation_m=float(row["cumulative_elevation_m"]),
            speed_limit_mps=float(row["speed_limit_kmh"]) / _KMH_PER_MPS,
            station=stations[index],
            beacon_station=announced,
        ))
    return blocks


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
            "beacon_platform_side": _PLATFORM_SIDE,
            "beacon_underground": _UNDERGROUND,
        }


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
