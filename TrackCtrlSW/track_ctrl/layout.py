"""Static track layout and wayside controller assignment.

This is the "initial config" input on the module architecture diagram:
the owned block layout and the posted speed limits are loaded once at
startup and never change while the simulation runs.

The layout here is generated rather than read from the course track
JSON. ``build_default_system()`` is the only place that knows how the
stub network is shaped, so swapping in the real loader (REQ-INTF-009)
means replacing that one function.

Two vocabularies meet in this module and are deliberately kept apart:

``section``   the letter grouping printed on the track chart (A, B, C...)
``block``     the individually detected length of rail a train occupies

A controller owns a contiguous run of blocks, which does not have to
line up with a section boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

#: Blocks per lettered section in the generated stub layout.
BLOCKS_PER_SECTION = 10

#: Posted speed limits cycle through this table, slowest through
#: stations and switches. Real limits come from the track data file.
_SPEED_LIMIT_TABLE_MPH: tuple[int, ...] = (25, 40, 55, 40, 30)

_STATION_NAMES: tuple[str, ...] = (
    "Shadyside",
    "Herron Ave",
    "Swissvale",
    "Penn Station",
    "Steel Plaza",
    "First Ave",
    "Station Square",
    "South Hills Junction",
    "Dormont",
    "Mt Lebanon",
    "Poplar",
    "Castle Shannon",
)


def section_letter(index: int) -> str:
    """Return the section label for a zero-based block index.

    Sections run A..Z and then AA, AB, ... so a long line does not run
    out of labels.
    """
    ordinal = index // BLOCKS_PER_SECTION
    letters = ""
    while True:
        letters = chr(ord("A") + ordinal % 26) + letters
        ordinal = ordinal // 26 - 1
        if ordinal < 0:
            return letters


@dataclass(frozen=True)
class Block:
    """One track circuit: the unit of occupancy and of authority."""

    block_id: str
    index: int
    section: str
    length_m: float
    grade_percent: float
    speed_limit_mph: int
    station: str | None = None

    @property
    def label(self) -> str:
        """Short label for a block tile: section letter + block number."""
        return f"{self.section}{self.index}"


@dataclass(frozen=True)
class Switch:
    """A powered switch driven by one boolean PLC output.

    ``False`` is the normal (through) position and ``True`` is reverse,
    matching the single-coil convention of the output card.
    """

    switch_id: str
    block_id: str
    normal_to: str
    reverse_to: str

    @property
    def output_signal(self) -> str:
        """Name the PLC writes to throw this switch."""
        return f"SW_{self.switch_id}"


@dataclass(frozen=True)
class WaysideSignal:
    """A four-aspect wayside light.

    Each aspect is its own boolean output so a single stuck bit cannot
    upgrade one aspect into a more permissive one; ``vital`` enforces
    that exactly one of the four is lit.
    """

    signal_id: str
    block_id: str

    @property
    def aspect_signals(self) -> tuple[str, str, str, str]:
        """Red, orange, green and super-green output names."""
        return (
            f"LT_{self.signal_id}_R",
            f"LT_{self.signal_id}_O",
            f"LT_{self.signal_id}_G",
            f"LT_{self.signal_id}_SG",
        )


@dataclass(frozen=True)
class Crossing:
    """A railway crossing: one output drives both lights and gates."""

    crossing_id: str
    block_id: str
    #: Blocks whose occupancy must arm the crossing. The vital layer
    #: treats this as a floor, never as a ceiling.
    approach_block_ids: tuple[str, ...]

    @property
    def output_signal(self) -> str:
        """Name the PLC writes to arm this crossing."""
        return f"XING_{self.crossing_id}"


@dataclass(frozen=True)
class ControllerConfig:
    """Everything one wayside controller owns, fixed at startup."""

    controller_id: str
    line_name: str
    block_ids: tuple[str, ...]
    switches: tuple[Switch, ...] = ()
    signals: tuple[WaysideSignal, ...] = ()
    crossings: tuple[Crossing, ...] = ()

    def owns(self, block_id: str) -> bool:
        """Return whether this controller is responsible for a block."""
        return block_id in self.block_ids


@dataclass
class LineLayout:
    """One coloured line: its blocks and the controllers over them."""

    name: str
    color: str
    blocks: tuple[Block, ...]
    controllers: tuple[ControllerConfig, ...] = field(default=())

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


def _partition(count: int, parts: int) -> list[tuple[int, int]]:
    """Split ``count`` items into ``parts`` contiguous half-open spans.

    The first spans absorb the remainder, so every controller owns at
    least ``count // parts`` blocks and no controller is left empty.
    """
    if parts < 1:
        raise ValueError("a line needs at least one track controller")
    if parts > count:
        raise ValueError("more controllers than blocks on the line")

    base, extra = divmod(count, parts)
    spans: list[tuple[int, int]] = []
    start = 0
    for position in range(parts):
        size = base + (1 if position < extra else 0)
        spans.append((start, start + size))
        start += size
    return spans


def _build_blocks(prefix: str, count: int) -> tuple[Block, ...]:
    """Generate ``count`` blocks with cycling limits and stations."""
    blocks: list[Block] = []
    for index in range(1, count + 1):
        station: str | None = None
        # A station every 13 blocks keeps stops spread across sections
        # without landing on the switch and crossing positions below.
        if index % 13 == 0:
            station = _STATION_NAMES[(index // 13 - 1) % len(_STATION_NAMES)]
        blocks.append(
            Block(
                block_id=f"{prefix}{index:03d}",
                index=index,
                section=section_letter(index - 1),
                length_m=50.0 + (index % 7) * 10.0,
                grade_percent=round(((index % 11) - 5) * 0.3, 2),
                speed_limit_mph=(
                    25
                    if station is not None
                    else _SPEED_LIMIT_TABLE_MPH[index % len(_SPEED_LIMIT_TABLE_MPH)]
                ),
                station=station,
            )
        )
    return tuple(blocks)


def _build_controllers(
    line_name: str,
    prefix: str,
    blocks: Sequence[Block],
    controller_count: int,
) -> tuple[ControllerConfig, ...]:
    """Split a line's blocks across ``controller_count`` waysides.

    Each controller gets a switch, a signal and a crossing placed at
    fixed offsets inside its own span, so every controller has all
    three kinds of output to drive.
    """
    configs: list[ControllerConfig] = []
    for position, (start, stop) in enumerate(
        _partition(len(blocks), controller_count), start=1
    ):
        owned = blocks[start:stop]
        controller_id = f"{prefix}TC-{position:02d}"
        tag = f"{position:02d}"

        switch_index = len(owned) // 3
        switch_block = owned[switch_index]
        signal_block = owned[len(owned) // 2]
        crossing_block = owned[(2 * len(owned)) // 3]
        through_block = owned[min(len(owned) - 1, switch_index + 1)]

        # The crossing arms on its own block and the two behind it, so
        # the gates are down before a train at line speed reaches it.
        approach_index = owned.index(crossing_block)
        approach = owned[max(0, approach_index - 2): approach_index + 1]

        configs.append(
            ControllerConfig(
                controller_id=controller_id,
                line_name=line_name,
                block_ids=tuple(block.block_id for block in owned),
                switches=(
                    Switch(
                        switch_id=f"SW{tag}",
                        block_id=switch_block.block_id,
                        normal_to=through_block.block_id,
                        reverse_to="YARD" if position == 1 else "SIDING",
                    ),
                ),
                signals=(
                    WaysideSignal(
                        signal_id=f"LT{tag}",
                        block_id=signal_block.block_id,
                    ),
                ),
                crossings=(
                    Crossing(
                        crossing_id=f"XG{tag}",
                        block_id=crossing_block.block_id,
                        approach_block_ids=tuple(
                            block.block_id for block in approach
                        ),
                    ),
                ),
            )
        )
    return tuple(configs)


def build_line(
    name: str,
    color: str,
    prefix: str,
    block_count: int,
    controller_count: int,
) -> LineLayout:
    """Build one line and divide it among its wayside controllers."""
    blocks = _build_blocks(prefix, block_count)
    controllers = _build_controllers(name, prefix, blocks, controller_count)
    return LineLayout(
        name=name, color=color, blocks=blocks, controllers=controllers
    )


def build_default_system() -> tuple[LineLayout, ...]:
    """Return the stub two-line network: Green and Red.

    Block counts match the course track data; the controller counts are
    the configurable part and are set here to the wireframe's 6 and 5.
    """
    return (
        build_line("Green Line", "#2F7D4F", "G", 150, 6),
        build_line("Red Line", "#B03A3A", "R", 76, 5),
    )


def iter_blocks(
    line: LineLayout, block_ids: Iterable[str]
) -> tuple[Block, ...]:
    """Return the blocks for ``block_ids``, in the order given."""
    return tuple(line.block(block_id) for block_id in block_ids)
