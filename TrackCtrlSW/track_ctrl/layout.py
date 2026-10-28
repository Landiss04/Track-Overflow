"""Track configuration: read a track layout file, divide it among waysides.

The input is the course track layout (``Track_layout/*.json``): one JSON
file per line, listing every block with its section, length, grade and
speed limit, and an optional ``infrastructure`` object that names a
station, a switch or a railway crossing. This module reads it and
builds the fixed things a controller owns.

Blocks are fixed by the layout and never change while the system runs;
which trains are on them does. That is why everything a controller
exchanges is keyed by block (``D015``), and why this module holds only
blocks, switches, signals and crossings and never a train.

Identifiers follow ``truth/conventions/identifiers.md``. A block is its
layout block number as a string, within its line; a switch is named by
the block it is listed on; a signal stands at every switch and is named
after it; a crossing is named by its block. So PLC names read
``OCC_12``, ``SW_12``, ``SIG_12_R`` and ``XING_19``.

Switch strings list the normal connection first and the reverse second,
as the layout does: ``"12-13; 1-13"`` joins 12 to 13 when normal and 1
to 13 when reversed. A string with one connection, such as
``"57-yard"``, names only the diverging route to the yard; the normal
route is the main line through the block the switch is listed on.

Each block's ``next_blocks`` gives the direction of travel: the blocks
a train in it may move on to. It is kept with the blocks, and every
controller carries the whole line's, so a starter program can tell
which way a train comes to a switch (``controller.default_program_source``).
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from track_ctrl.errors import TrackControllerError

#: Marker in a switch string for the yard, which is not a block.
YARD = "yard"

#: Each line needs at least this many wayside controllers (D014).
MIN_CONTROLLERS = 2

#: How many wayside controllers each line is built with. Fixed by the
#: track, like the blocks: the user never chooses it. A line not listed
#: is built with the fewest D014 allows.
WAYSIDE_COUNTS: dict[str, int] = {"Green": 6, "Red": 5}

#: Identity colours from the track chart. Any other line is neutral.
LINE_COLORS: dict[str, str] = {"Green": "#2F7D4F", "Red": "#B03A3A"}
NEUTRAL_LINE_COLOR = "#4B5C6B"

_KMH_PER_MPS = 3.6
_CONNECTION_SPLIT = re.compile(r"\s*(?:-|\bto\b)\s*", re.IGNORECASE)


class LayoutError(TrackControllerError, ValueError):
    """A track layout file could not be read or is malformed."""


@dataclass(frozen=True)
class Block:
    """One track circuit: the unit of occupancy and of authority."""

    block_id: str
    index: int
    section: str
    length_m: float
    grade_percent: float
    #: The posted limit exactly as the layout gives it, in m/s.
    speed_limit_mps: float
    station: str | None = None
    #: The blocks a train in this block may move on to, as the layout
    #: file's ``next_blocks`` lists them (block numbers, or ``yard``).
    #: Empty where the file gives no direction of travel.
    next_blocks: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """Short label for a block tile: section letter + block number."""
        return f"{self.section}{self.index}"

    @property
    def whole_speed_limit_mps(self) -> int:
        """The limit rounded down to a whole m/s, as speeds are sent."""
        return math.floor(self.speed_limit_mps)


@dataclass(frozen=True)
class ControllerConfig:
    """Everything one wayside controller owns, fixed by the layout.

    A switch is named by the block it is listed on, a signal stands at
    every switch and is named after it, and a crossing is named by its
    block. So every id below is also the block its device stands on, and
    the PLC names read ``SW_12``, ``SIG_12_R`` and ``XING_19``.
    """

    controller_id: str
    line_name: str
    block_ids: tuple[str, ...]
    #: Switch id -> ``(point, normal end, reverse end)``: the block the
    #: points are at, and the blocks the switch joins it to when normal
    #: and when reversed (``yard`` is not a block). ``False`` is the
    #: normal position and ``True`` is reverse.
    switches: Mapping[str, tuple[str, str, str]] = field(
        default_factory=dict
    )
    #: Crossing ids: one output drives both lights and gates.
    crossings: tuple[str, ...] = ()
    #: Every block of the line with the blocks a train in it may move
    #: on to (``Block.next_blocks``), for the whole line and not only
    #: this territory: the track chart a starter program is written
    #: from. Fixed by the layout; never an input.
    line_next_blocks: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def signals(self) -> tuple[str, ...]:
        """Signal ids: a four-aspect light stands at every switch.

        Each aspect is its own boolean output so a single stuck bit
        cannot upgrade one aspect into a more permissive one; ``vital``
        enforces that exactly one of the four is lit.
        """
        return tuple(self.switches)

    def owns(self, block_id: str) -> bool:
        """Return whether this controller is responsible for a block."""
        return block_id in self.block_ids

    def switch_point(self, switch_id: str) -> str:
        """The block a switch's points are at."""
        return self.switches[switch_id][0]

    def switch_normal_end(self, switch_id: str) -> str:
        """Where a switch leads when normal."""
        return self.switches[switch_id][1]

    def switch_reverse_end(self, switch_id: str) -> str:
        """Where a switch leads when reversed."""
        return self.switches[switch_id][2]

    @staticmethod
    def switch_output(switch_id: str) -> str:
        """Name the PLC writes to throw a switch."""
        return f"SW_{switch_id}"

    @staticmethod
    def aspect_outputs(signal_id: str) -> tuple[str, str, str, str]:
        """A signal's red, yellow, green and super-green outputs."""
        return (
            f"SIG_{signal_id}_R",
            f"SIG_{signal_id}_Y",
            f"SIG_{signal_id}_G",
            f"SIG_{signal_id}_SG",
        )

    @staticmethod
    def crossing_output(crossing_id: str) -> str:
        """Name the PLC writes to arm a crossing."""
        return f"XING_{crossing_id}"

    def crossing_approach(self, crossing_id: str) -> tuple[str, ...]:
        """Blocks whose occupancy must arm a crossing.

        Its own block and the ones beside it that this wayside owns. The
        vital layer treats this as a floor.
        """
        return tuple(sorted(
            (each for each in (crossing_id, *self.neighbours(crossing_id))
             if each in self.block_ids),
            key=_block_order,
        ))

    def neighbours(self, block_id: str) -> tuple[str, ...]:
        """Blocks physically joined to ``block_id``, whatever their ids.

        A block's neighbours are the ones the layout joins to it, in
        either direction of travel: those it lists in ``next_blocks`` and
        those that list it. Block numbers say nothing about adjacency
        (block 101 joins block 77). The yard is not a block.
        """
        found = set(self.next_blocks(block_id))
        found.update(
            candidate for candidate, after in self.line_next_blocks
            if block_id in after
        )
        found.discard(YARD)
        found.discard(block_id)
        return tuple(sorted(found, key=_block_order))

    def within(self, block_id: str, depth: int) -> tuple[str, ...]:
        """Blocks within ``depth`` joins of ``block_id``, either way."""
        seen = {block_id}
        frontier = [block_id]
        for _ in range(depth):
            frontier = [
                nxt for each in frontier for nxt in self.neighbours(each)
                if nxt not in seen
            ]
            seen.update(frontier)
        seen.discard(block_id)
        return tuple(sorted(seen, key=_block_order))

    def next_blocks(self, block_id: str) -> tuple[str, ...]:
        """Where a train in ``block_id`` may move on to, per the layout.

        Empty for a block the layout gives no direction for, or one not
        on this line.
        """
        for candidate, after in self.line_next_blocks:
            if candidate == block_id:
                return after
        return ()


@dataclass
class LineLayout:
    """One line: its blocks, switches and crossings, and its waysides.

    A layout file reads into an undivided line (no ``controllers``);
    :meth:`divide` gives the line the waysides the track is built with.
    """

    key: str
    blocks: tuple[Block, ...]
    #: Switch id -> ``(point, normal end, reverse end)``, for the whole
    #: line. See :attr:`ControllerConfig.switches`.
    switches: Mapping[str, tuple[str, str, str]] = field(
        default_factory=dict
    )
    #: Crossing ids for the whole line, by block number.
    crossings: tuple[str, ...] = ()
    controllers: tuple[ControllerConfig, ...] = field(default=())

    @property
    def name(self) -> str:
        """Display name of the line, e.g. ``Green Line``."""
        return f"{self.key} Line"

    @property
    def color(self) -> str:
        """The line's identity colour; neutral for a line not charted."""
        return LINE_COLORS.get(self.key, NEUTRAL_LINE_COLOR)

    @property
    def switch_count(self) -> int:
        """Switches on the whole line."""
        return len(self.switches)

    @property
    def crossing_count(self) -> int:
        """Crossings on the whole line."""
        return len(self.crossings)

    @property
    def max_controllers(self) -> int:
        """Most waysides this line can be divided into."""
        return len(self.blocks)

    @property
    def min_controllers(self) -> int:
        """Fewest waysides this line may have (D014)."""
        return min(MIN_CONTROLLERS, len(self.blocks))

    @property
    def default_controllers(self) -> int:
        """How many waysides this line is built with."""
        wanted = WAYSIDE_COUNTS.get(self.key, MIN_CONTROLLERS)
        return max(self.min_controllers, min(wanted, self.max_controllers))

    def block(self, block_id: str) -> Block:
        """Return one block by id."""
        for candidate in self.blocks:
            if candidate.block_id == block_id:
                return candidate
        raise KeyError(f"unknown block: {block_id}")

    def controller(self, controller_id: str) -> ControllerConfig:
        """Return one controller config by id."""
        for candidate in self.controllers:
            if candidate.controller_id == controller_id:
                return candidate
        raise KeyError(f"unknown controller: {controller_id}")

    def divide(self, controller_count: int | None = None) -> "LineLayout":
        """Divide the line's blocks among the waysides it is built with.

        The number of waysides is fixed by the track (``WAYSIDE_COUNTS``),
        so the user never chooses it. ``controller_count`` overrides it
        for tests only.

        Each wayside owns a contiguous run of block numbers. That run
        does not have to line up with a section boundary, and a switch
        belongs to the wayside that owns the block it is listed on, even
        if the switch's legs lead into a neighbouring territory.

        Raises:
            LayoutError: If the count is outside what this line allows.
        """
        if controller_count is None:
            controller_count = self.default_controllers
        if isinstance(controller_count, bool) or not isinstance(
            controller_count, int
        ):
            raise LayoutError(
                "The number of controllers must be a whole number."
            )
        if not self.min_controllers <= controller_count <= (
            self.max_controllers
        ):
            raise LayoutError(
                f"{self.name} needs between {self.min_controllers} and "
                f"{self.max_controllers} controllers, not "
                f"{controller_count}."
            )

        prefix = self.key[:1].upper()
        directions = tuple(
            (block.block_id, block.next_blocks) for block in self.blocks
        )
        configs: list[ControllerConfig] = []
        for position, (start, stop) in enumerate(
            _partition(len(self.blocks), controller_count), start=1
        ):
            owned_ids = tuple(
                block.block_id for block in self.blocks[start:stop]
            )
            configs.append(
                ControllerConfig(
                    controller_id=f"{prefix}TC-{position:02d}",
                    line_name=self.name,
                    block_ids=owned_ids,
                    switches={
                        block_id: self.switches[block_id]
                        for block_id in owned_ids
                        if block_id in self.switches
                    },
                    crossings=tuple(
                        block_id for block_id in owned_ids
                        if block_id in self.crossings
                    ),
                    line_next_blocks=directions,
                )
            )
        return LineLayout(
            key=self.key,
            blocks=self.blocks,
            switches=self.switches,
            crossings=self.crossings,
            controllers=tuple(configs),
        )


# --- reading a layout file ---------------------------------------------

def load_layout_file(path: str | Path) -> LineLayout:
    """Read and check one track layout file.

    Raises:
        LayoutError: If the file cannot be read or is malformed.
    """
    name = Path(path).name
    try:
        with open(path, encoding="utf-8") as layout_file:
            data = json.load(layout_file)
    except OSError as error:
        raise LayoutError(f"Cannot read {name}: {error.strerror}") from error
    except ValueError as error:
        raise LayoutError(f"{name} is not valid JSON: {error}") from error
    return parse_layout(data, name)


def parse_layout(data: Any, source: str = "layout") -> LineLayout:
    """Build a layout from a decoded track layout file.

    Raises:
        LayoutError: If a required field is missing or malformed.
    """
    if not isinstance(data, Mapping):
        raise LayoutError(f"{source}: a track layout must be a JSON object.")
    if "wayside" in data:
        raise LayoutError(
            f"{source} is a wayside database (one wayside's blocks). "
            "Load the line's full track layout file instead; the "
            "waysides are divided up here."
        )
    line = data.get("line")
    if not isinstance(line, str) or not line.strip():
        raise LayoutError(f"{source}: \"line\" must be the line's name.")
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise LayoutError(f"{source}: \"blocks\" must be a non-empty list.")

    blocks: list[Block] = []
    switch_text: list[tuple[str, str]] = []
    crossings: list[str] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_blocks, start=1):
        if not isinstance(raw, Mapping):
            raise LayoutError(f"{source}: block entry {position} is not an "
                              "object.")
        number = raw.get("block_number")
        if isinstance(number, bool) or not isinstance(number, (int, str)):
            raise LayoutError(f"{source}: block entry {position} has no "
                              "block_number.")
        block_id = str(number).strip()
        if not block_id.isdigit():
            raise LayoutError(f"{source}: block_number {block_id!r} is not "
                              "a whole number.")
        if block_id in seen:
            raise LayoutError(f"{source}: block {block_id} is listed twice.")
        seen.add(block_id)

        section = raw.get("section")
        if not isinstance(section, str) or not section.strip():
            raise LayoutError(f"{source}: block {block_id} has no section.")
        limit_kmh = _positive(raw.get("speed_limit_kmh"), "speed_limit_kmh",
                              block_id, source)
        grade = raw.get("grade_percent", 0.0)
        if isinstance(grade, bool) or not isinstance(grade, (int, float)):
            raise LayoutError(f"{source}: block {block_id}: grade_percent "
                              "must be a number.")

        infrastructure = raw.get("infrastructure") or {}
        if not isinstance(infrastructure, Mapping):
            raise LayoutError(f"{source}: block {block_id}: infrastructure "
                              "is not an object.")
        station = infrastructure.get("station")
        next_blocks = _next_blocks(raw.get("next_blocks"), block_id, source)
        if line == "Red" and block_id in {"9", "75"}:
            # Interpret the given course file without changing its rows.
            next_blocks = tuple(n for n in next_blocks if n != YARD)
            if block_id == "9":
                next_blocks += (YARD,)
        blocks.append(
            Block(
                block_id=block_id,
                index=int(block_id),
                section=section.strip(),
                length_m=_positive(raw.get("length_m"), "length_m",
                                   block_id, source),
                grade_percent=float(grade),
                speed_limit_mps=limit_kmh / _KMH_PER_MPS,
                station=station if isinstance(station, str) else None,
                next_blocks=next_blocks,
            )
        )
        if "switch" in infrastructure:
            text = infrastructure["switch"]
            if not isinstance(text, str) or not text.strip():
                raise LayoutError(f"{source}: block {block_id}: the switch "
                                  "entry is not text.")
            switch_text.append((block_id, text))
        crossing = infrastructure.get("railway_crossing", False)
        if not isinstance(crossing, bool):
            raise LayoutError(f"{source}: block {block_id}: "
                              "railway_crossing must be true or false.")
        if crossing:
            crossings.append(block_id)

    blocks.sort(key=lambda block: block.index)
    switches = {
        block_id: _parse_switch(block_id, text, source, next(
            b.next_blocks for b in blocks if b.block_id == block_id
        ))
        for block_id, text in switch_text
    }
    return LineLayout(
        key=line.strip(),
        blocks=tuple(blocks),
        switches=switches,
        crossings=tuple(sorted(crossings, key=int)),
    )


def _block_order(block_id: str) -> tuple[int, str]:
    """Sort key: numbered blocks by number, then anything else by name."""
    return (int(block_id), "") if block_id.isdigit() else (1 << 30, block_id)


def _next_blocks(value: Any, block_id: str, source: str) -> tuple[str, ...]:
    """Read a block's ``next_blocks``: block numbers, or the yard."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LayoutError(f"{source}: block {block_id}: next_blocks must "
                          "be a list.")
    found: list[str] = []
    for entry in value:
        if isinstance(entry, str) and entry.strip().lower() == YARD:
            found.append(YARD)
        elif isinstance(entry, int) and not isinstance(entry, bool):
            found.append(str(entry))
        else:
            raise LayoutError(f"{source}: block {block_id}: next_blocks "
                              f"lists {entry!r}, neither a block number "
                              "nor the yard.")
    return tuple(found)


def _positive(value: Any, name: str, block_id: str, source: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LayoutError(f"{source}: block {block_id}: {name} must be a "
                          "number.")
    if not math.isfinite(value) or value <= 0:
        raise LayoutError(f"{source}: block {block_id}: {name} must be "
                          "above zero.")
    return float(value)


def _connection(part: str, where: str) -> tuple[str, str]:
    ends = [end for end in _CONNECTION_SPLIT.split(part.strip()) if end]
    if len(ends) != 2:
        raise LayoutError(f"{where}: {part.strip()!r} is not a connection "
                          "between two blocks.")
    cleaned: list[str] = []
    for end in ends:
        if end.lower() == YARD:
            cleaned.append(YARD)
        elif end.isdigit():
            cleaned.append(end)
        else:
            raise LayoutError(f"{where}: {end!r} is neither a block number "
                              "nor the yard.")
    return cleaned[0], cleaned[1]


def _parse_switch(
    block_id: str, text: str, source: str, next_blocks: tuple[str, ...] = ()
) -> tuple[str, str, str]:
    """Read the switch string listed on ``block_id``.

    Returns ``(point, normal end, reverse end)``.
    """
    where = f"{source}: switch on block {block_id} ({text.strip()!r})"
    parts = [part for part in text.split(";") if part.strip()]
    if not 1 <= len(parts) <= 2:
        raise LayoutError(f"{where}: expected one or two connections.")
    connections = [_connection(part, where) for part in parts]

    if len(connections) == 2:
        first, second = connections
        shared = set(first) & set(second)
        if len(shared) != 1 or YARD in shared:
            raise LayoutError(f"{where}: the two connections must share "
                              "exactly one block.")
        point = shared.pop()
        normal_end = first[1] if first[0] == point else first[0]
        reverse_end = second[1] if second[0] == point else second[0]
    else:
        (only,) = connections
        if YARD not in only:
            raise LayoutError(f"{where}: a single connection must lead to "
                              "the yard.")
        point = only[1] if only[0] == YARD else only[0]
        if (
            block_id == "9" and text.strip() == "75-yard"
            and YARD in next_blocks
        ):
            # Assumption: yard arrivals leave 9 on its fixed side toward 10.
            point = block_id
            normal_end, reverse_end = str(int(point) - 1), YARD
            if normal_end not in next_blocks:
                raise LayoutError(f"{where}: normal main-line leg is missing.")
        elif point == block_id:
            raise LayoutError(f"{where}: its normal route is not listed and "
                              "cannot be inferred.")
        else:
            normal_end, reverse_end = block_id, YARD

    return point, normal_end, reverse_end


# --- dividing a line among waysides --------------------------------------

def _partition(count: int, parts: int) -> list[tuple[int, int]]:
    """Split ``count`` items into ``parts`` contiguous half-open spans.

    The first spans absorb the remainder, so no controller is left
    empty and sizes differ by at most one block.
    """
    base, extra = divmod(count, parts)
    spans: list[tuple[int, int]] = []
    start = 0
    for position in range(parts):
        size = base + (1 if position < extra else 0)
        spans.append((start, start + size))
        start += size
    return spans


# --- the layouts the system starts with ------------------------------------

def default_layout_dir() -> Path:
    """The ``Track_layout`` folder, which holds the layouts.

    In the repository, or in a built executable's bundle, which lays the
    folders out the same way (``track_overflow.py``).
    """
    root = getattr(sys, "_MEIPASS", None)
    if root is not None:
        return Path(root) / "Track_layout"
    return Path(__file__).resolve().parents[2] / "Track_layout"


def build_default_system() -> tuple[LineLayout, ...]:
    """Load the Green and Red layouts and divide each among waysides.

    Raises:
        LayoutError: If a layout file is missing or malformed.
    """
    lines: list[LineLayout] = []
    for key in WAYSIDE_COUNTS:
        parsed = load_layout_file(
            default_layout_dir() / f"{key.lower()}_line.json"
        )
        lines.append(parsed.divide())
    return tuple(lines)
