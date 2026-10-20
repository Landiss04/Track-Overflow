"""Track configuration: read a track layout file, divide it among waysides.

The input is the course track layout (``TrackModel/*.json``): one JSON
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

#: Default wayside count for each line the system starts with. The
#: count is configurable: it is chosen again whenever a layout is loaded.
DEFAULT_CONTROLLER_COUNTS: dict[str, int] = {"Green": 6, "Red": 5}

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

    @property
    def label(self) -> str:
        """Short label for a block tile: section letter + block number."""
        return f"{self.section}{self.index}"

    @property
    def whole_speed_limit_mps(self) -> int:
        """The limit rounded down to a whole m/s, as speeds are sent."""
        return math.floor(self.speed_limit_mps)


@dataclass(frozen=True)
class Switch:
    """A powered switch driven by one boolean PLC output.

    ``False`` is the normal position and ``True`` is reverse. The id is
    the block the switch is listed on.
    """

    switch_id: str
    block_id: str
    point: str
    normal_end: str
    reverse_end: str

    @property
    def output_signal(self) -> str:
        """Name the PLC writes to throw this switch."""
        return f"SW_{self.switch_id}"


@dataclass(frozen=True)
class WaysideSignal:
    """A four-aspect wayside light, standing at a switch.

    Each aspect is its own boolean output so a single stuck bit cannot
    upgrade one aspect into a more permissive one; ``vital`` enforces
    that exactly one of the four is lit.
    """

    signal_id: str
    block_id: str

    @property
    def aspect_signals(self) -> tuple[str, str, str, str]:
        """Red, yellow, green and super-green outputs; _O is legacy yellow."""
        return (
            f"SIG_{self.signal_id}_R",
            f"SIG_{self.signal_id}_O",
            f"SIG_{self.signal_id}_G",
            f"SIG_{self.signal_id}_SG",
        )


@dataclass(frozen=True)
class Crossing:
    """A railway crossing: one output drives both lights and gates."""

    crossing_id: str
    block_id: str
    #: Blocks whose occupancy must arm the crossing: its own block and
    #: the ones beside it. The vital layer treats this as a floor.
    approach_block_ids: tuple[str, ...]

    @property
    def output_signal(self) -> str:
        """Name the PLC writes to arm this crossing."""
        return f"XING_{self.crossing_id}"


@dataclass(frozen=True)
class ControllerConfig:
    """Everything one wayside controller owns, fixed by the layout."""

    controller_id: str
    line_name: str
    block_ids: tuple[str, ...]
    switches: tuple[Switch, ...] = ()
    signals: tuple[WaysideSignal, ...] = ()
    crossings: tuple[Crossing, ...] = ()

    def owns(self, block_id: str) -> bool:
        """Return whether this controller is responsible for a block."""
        return block_id in self.block_ids


@dataclass(frozen=True)
class ParsedLayout:
    """A track layout file, checked and read, before it is divided up."""

    key: str
    blocks: tuple[Block, ...]
    switches: tuple[Switch, ...] = ()
    crossing_blocks: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        """Display name of the line, e.g. ``Green Line``."""
        return f"{self.key} Line"

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
        """The wayside count to offer when the line is first loaded."""
        wanted = DEFAULT_CONTROLLER_COUNTS.get(self.key, MIN_CONTROLLERS)
        return max(self.min_controllers, min(wanted, self.max_controllers))


@dataclass
class LineLayout:
    """One line: its blocks and the controllers it is divided among."""

    name: str
    key: str
    color: str
    blocks: tuple[Block, ...]
    controllers: tuple[ControllerConfig, ...] = field(default=())

    @property
    def switch_count(self) -> int:
        """Switches on the whole line."""
        return sum(len(config.switches) for config in self.controllers)

    @property
    def crossing_count(self) -> int:
        """Crossings on the whole line."""
        return sum(len(config.crossings) for config in self.controllers)

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


# --- reading a layout file ---------------------------------------------

def load_layout_file(path: str | Path) -> ParsedLayout:
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


def parse_layout(data: Any, source: str = "layout") -> ParsedLayout:
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
    switches = tuple(
        _parse_switch(block_id, text, source)
        for block_id, text in switch_text
    )
    return ParsedLayout(
        key=line.strip(),
        blocks=tuple(blocks),
        switches=switches,
        crossing_blocks=tuple(sorted(crossings, key=int)),
    )


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


def _parse_switch(block_id: str, text: str, source: str) -> Switch:
    """Read the switch string listed on ``block_id``."""
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
        if point == block_id:
            raise LayoutError(f"{where}: its normal route is not listed and "
                              "cannot be inferred.")
        normal_end, reverse_end = block_id, YARD

    return Switch(
        switch_id=block_id,
        block_id=block_id,
        point=point,
        normal_end=normal_end,
        reverse_end=reverse_end,
    )


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


def build_line(parsed: ParsedLayout, controller_count: int) -> LineLayout:
    """Divide a line's blocks among ``controller_count`` waysides.

    Each wayside owns a contiguous run of block numbers. That run does
    not have to line up with a section boundary, and a switch belongs to
    the wayside that owns the block it is listed on, even if the switch's
    legs lead into a neighbouring territory.

    Raises:
        LayoutError: If the count is outside what this line allows.
    """
    if isinstance(controller_count, bool) or not isinstance(
        controller_count, int
    ):
        raise LayoutError("The number of controllers must be a whole number.")
    if not parsed.min_controllers <= controller_count <= (
        parsed.max_controllers
    ):
        raise LayoutError(
            f"{parsed.name} needs between {parsed.min_controllers} and "
            f"{parsed.max_controllers} controllers, not {controller_count}."
        )

    prefix = parsed.key[:1].upper()
    switches = {switch.block_id: switch for switch in parsed.switches}
    crossing_blocks = set(parsed.crossing_blocks)
    configs: list[ControllerConfig] = []
    for position, (start, stop) in enumerate(
        _partition(len(parsed.blocks), controller_count), start=1
    ):
        owned = parsed.blocks[start:stop]
        owned_ids = tuple(block.block_id for block in owned)
        owned_set = set(owned_ids)
        owned_switches = tuple(
            switches[block_id] for block_id in owned_ids
            if block_id in switches
        )
        configs.append(
            ControllerConfig(
                controller_id=f"{prefix}TC-{position:02d}",
                line_name=parsed.name,
                block_ids=owned_ids,
                switches=owned_switches,
                signals=tuple(
                    WaysideSignal(signal_id=s.switch_id,
                                  block_id=s.block_id)
                    for s in owned_switches
                ),
                crossings=tuple(
                    Crossing(
                        crossing_id=block_id,
                        block_id=block_id,
                        approach_block_ids=tuple(
                            neighbour
                            for neighbour in (
                                str(int(block_id) - 1),
                                block_id,
                                str(int(block_id) + 1),
                            )
                            if neighbour in owned_set
                        ),
                    )
                    for block_id in owned_ids
                    if block_id in crossing_blocks
                ),
            )
        )
    return LineLayout(
        name=parsed.name,
        key=parsed.key,
        color=LINE_COLORS.get(parsed.key, NEUTRAL_LINE_COLOR),
        blocks=parsed.blocks,
        controllers=tuple(configs),
    )


# --- the layouts the system starts with ------------------------------------

def default_layout_dir() -> Path:
    """The ``TrackModel`` folder, which holds the layouts.

    In the repository, or in a built executable's bundle, which lays the
    folders out the same way (``track_overflow.py``).
    """
    root = getattr(sys, "_MEIPASS", None)
    if root is not None:
        return Path(root) / "TrackModel"
    return Path(__file__).resolve().parents[2] / "TrackModel"


def build_default_system() -> tuple[LineLayout, ...]:
    """Load the Green and Red layouts and divide each among waysides.

    Raises:
        LayoutError: If a layout file is missing or malformed.
    """
    lines: list[LineLayout] = []
    for key in DEFAULT_CONTROLLER_COUNTS:
        parsed = load_layout_file(
            default_layout_dir() / f"{key.lower()}_line.json"
        )
        lines.append(build_line(parsed, parsed.default_controllers))
    return tuple(lines)
