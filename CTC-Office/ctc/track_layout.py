"""Track layout for the CTC Office, read from the course JSON files.

Track layout data is loaded from the course-provided JSON files at
startup (``truth/conventions/files-and-paths.md``). Each file lists a
line name and its blocks; each block belongs to a lettered section, and
a section holds one or more blocks.

Block IDs are strings, never integers, per
``truth/conventions/identifiers.md``.

Each block may list its ``next_blocks``: the blocks a train in it may
move on to, and ``"yard"`` where it may run into the yard. That is the
direction of travel. A file that lists none (the Red line, for now) is
run both ways.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: How ``next_blocks`` names the yard.
YARD = "yard"

#: The course-provided layout files, one per line.
LAYOUT_DIR = Path(__file__).resolve().parents[2] / "TrackModel"
LINE_FILES = {
    "Green": LAYOUT_DIR / "green_line.json",
    "Red": LAYOUT_DIR / "red_line.json",
}


@dataclass(frozen=True, slots=True)
class Block:
    """One block of track, as listed in the layout file."""

    line: str
    block_id: str
    section: str
    length_m: float
    speed_limit_kmh: float = 0.0
    station: str | None = None
    switch: str | None = None
    railway_crossing: bool = False
    underground: bool = False
    # Blocks a train in this block may move on to, in file order; None
    # when the file does not say (then any neighbor will do).
    next_blocks: tuple[str, ...] | None = None
    # Whether a train in this block may run into the yard.
    to_yard: bool = False


@dataclass(frozen=True, slots=True)
class Line:
    """One line: its blocks in file order, grouped by section."""

    name: str
    blocks: tuple[Block, ...]

    def sections(self) -> dict[str, tuple[Block, ...]]:
        """Blocks per section letter, in file order."""
        grouped: dict[str, list[Block]] = {}
        for block in self.blocks:
            grouped.setdefault(block.section, []).append(block)
        return {letter: tuple(blocks) for letter, blocks in grouped.items()}

    def block(self, block_id: str) -> Block | None:
        """The block with this ID, or None."""
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def switch_ids(self) -> tuple[str, ...]:
        """IDs of the switches: the blocks they are listed on."""
        return tuple(b.block_id for b in self.blocks if b.switch)

    def crossing_ids(self) -> tuple[str, ...]:
        """IDs of the railway crossings: the blocks they are on."""
        return tuple(b.block_id for b in self.blocks if b.railway_crossing)

    def stations(self) -> dict[str, tuple[str, ...]]:
        """Block IDs per named station, in file order.

        A station name can appear on more than one block (Green's
        DORMONT is at 73 and 105). Unnamed stations are left out.
        """
        found: dict[str, list[str]] = {}
        for block in self.blocks:
            if block.station:
                found.setdefault(block.station, []).append(block.block_id)
        return {name: tuple(ids) for name, ids in found.items()}


def _block(line: str, raw: dict[str, object]) -> Block:
    infrastructure = raw.get("infrastructure") or {}
    assert isinstance(infrastructure, dict)
    station = infrastructure.get("station")
    switch = infrastructure.get("switch")
    listed = raw.get("next_blocks")
    if listed is not None and not isinstance(listed, list):
        raise ValueError(f"{line} block {raw['block_number']}: next_blocks "
                         f"must be a list, got {listed!r}")
    nexts = (None if listed is None else
             tuple(str(n) for n in listed if str(n).lower() != YARD))
    return Block(
        line=line,
        block_id=str(raw["block_number"]),
        section=str(raw["section"]),
        length_m=float(raw["length_m"]),  # type: ignore[arg-type]
        speed_limit_kmh=float(raw["speed_limit_kmh"]),  # type: ignore
        # A few stations are listed with no name; keep them as stations.
        station=(str(station) if station else
                 ("" if "station" in infrastructure else None)),
        switch=str(switch) if switch else None,
        railway_crossing=bool(infrastructure.get("railway_crossing")),
        underground=bool(infrastructure.get("underground")),
        next_blocks=nexts,
        to_yard=any(str(n).lower() == YARD for n in listed or ()),
    )


def load_line(name: str, path: Path) -> Line:
    """Read one line's layout file."""
    with open(path, encoding="utf-8") as layout_file:
        data = json.load(layout_file)
    return Line(
        name=name,
        blocks=tuple(_block(name, raw) for raw in data["blocks"]),
    )


def load_layout(files: dict[str, Path] | None = None) -> dict[str, Line]:
    """Read every line's layout file, keyed by line name."""
    files = LINE_FILES if files is None else files
    return {name: load_line(name, path) for name, path in files.items()}
