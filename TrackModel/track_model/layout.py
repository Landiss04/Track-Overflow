"""Track layout loading and the track graph.

The layout files are the course-provided JSON files, one per line. Each
lists blocks with section, number, length (m), grade (%), speed limit
(km/h) and elevation (m), and an optional ``infrastructure`` object. The
loader converts grade to degrees and speed to m/s on read, so nothing
downstream sees the file units (``truth/conventions/units.md``).

The graph only describes where the rails go. ``next_block`` follows a
switch in whatever position it is given; the Track Model never chooses a
switch position, it applies the Track Controller's commands.
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from track_model.interface import (
    Beacon,
    Block,
    PlatformSide,
    Switch,
    SwitchPosition,
    TrackModelError,
)

KMH_PER_MPS = 3.6

#: Lines without ``next_blocks`` only: consecutive block numbers that
#: are NOT joined by rail. Every other pair of consecutive numbers is.
#: These are branch ends that switch legs join elsewhere, read off the
#: course track map. A line with ``next_blocks`` (Green) states its
#: joins and ignores this table.
_SEGMENT_BREAKS: dict[str, frozenset[tuple[int, int]]] = {
    "BLUE": frozenset({(10, 11)}),
    "RED": frozenset({(66, 67), (71, 72)}),
}

_STATION_SIDES: dict[str, PlatformSide] = {
    "Left": "L",
    "Right": "R",
    "Left/Right": "LR",
}

#: ``came_from`` value for a train that entered from the yard.
YARD = "YARD"
_PAIR = re.compile(r"^\s*(\d+|yard)\s*-\s*(\d+|yard)\s*$", re.IGNORECASE)
_TO = re.compile(r"^\s*(\d+)\s+to\s+(\d+)\s*$", re.IGNORECASE)


class LayoutError(TrackModelError):
    """A layout file could not be read or understood."""


def block_id_for(line: str, section: str, number: int) -> str:
    """Return the canonical block ID, for example ``"GREEN D-13"``."""
    return f"{line.upper()} {section}-{number}"


def grade_percent_to_deg(grade_percent: float) -> float:
    """Convert rise-over-run percent to degrees."""
    return math.degrees(math.atan(grade_percent / 100.0))


@dataclass(frozen=True, slots=True)
class Layout:
    """Every loaded line, its switches, and how the blocks connect."""

    blocks: Mapping[str, Block]                  # in file order
    switches: Mapping[str, Switch]               # by point block ID
    neighbours: Mapping[str, frozenset[str]]
    signal_block_ids: tuple[str, ...]
    beacons: Mapping[str, Beacon]                # by block ID
    _by_number: Mapping[tuple[str, int], str]
    # Blocks whose next_blocks name each block; empty if not annotated.
    _predecessors: Mapping[str, tuple[str, ...]]

    def next_block(
        self,
        block_id: str,
        came_from: str | None,
        switch_states: Mapping[str, SwitchPosition],
    ) -> str | None:
        """Return the block the rails lead to, leaving ``block_id``.

        ``came_from`` is the block the train entered from, or None if
        unknown, or ``YARD`` if it came out of the yard. At a switch
        point entered from its fixed side, the leg is the one
        ``switch_states`` holds for that switch; entered from a leg,
        including the yard leg, the train trails out the fixed side.
        Returns None when the rails lead into the yard, and ``block_id``
        itself at a dead end.
        """
        switch = self.switches.get(block_id)
        if switch is not None:
            legs = {switch.normal_block_id, switch.reverse_block_id}
            from_leg = came_from is not None and (
                came_from in legs or (came_from == YARD and None in legs)
            )
            if not from_leg:
                position = switch_states.get(
                    switch.switch_id, SwitchPosition.NORMAL
                )
                if position is SwitchPosition.NORMAL:
                    return switch.normal_block_id
                return switch.reverse_block_id
            # Trailing through the points: out the fixed side.
            candidates = set(self.neighbours[block_id]) - legs
        else:
            block = self.blocks[block_id]
            if came_from is None and not block.bidirectional:
                # A one-way block says which way an unplaced train goes.
                outs = [b for b in block.next_block_ids if b is not None]
                if len(outs) == 1:
                    return outs[0]
            candidates = set(self.neighbours[block_id]) - {came_from}
        return self._pick(block_id, candidates)

    def previous_block(self, block_id: str, came_from: str | None) -> str:
        """Return the block a train rolls back into.

        That is the block it came from. If that is unknown: the one block
        that leads here on a one-way line, else the next lower-numbered
        neighbour, else ``block_id`` itself at a dead end. A train that
        came out of the yard stays put: it does not roll back off the
        line.
        """
        if came_from == YARD:
            return block_id
        if came_from is not None:
            return came_from
        block = self.blocks[block_id]
        feeders = self._predecessors.get(block_id, ())
        if not block.bidirectional and len(feeders) == 1:
            return feeders[0]
        lower = self._by_number.get((block.line, block.number - 1))
        if lower is not None and lower in self.neighbours[block_id]:
            return lower
        return block_id

    def _pick(self, block_id: str, candidates: Iterable[str | None]) -> str:
        # With an unknown direction, default to the next higher number.
        real = {c for c in candidates if c is not None}
        if not real:
            return block_id
        if len(real) == 1:
            return next(iter(real))
        block = self.blocks[block_id]
        higher = self._by_number.get((block.line, block.number + 1))
        if higher in real:
            return higher
        return min(real, key=lambda b: self.blocks[b].number)


def load_layout(paths: Iterable[str | Path]) -> Layout:
    """Load one or more line files into a single ``Layout``."""
    blocks: dict[str, Block] = {}
    switches: dict[str, Switch] = {}
    neighbours: dict[str, set[str]] = {}
    by_number: dict[tuple[str, int], str] = {}

    for path in paths:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        line, raw_blocks = _read_line(data, path)
        line_blocks = [_read_block(line, raw) for raw in raw_blocks]
        for block in line_blocks:
            if block.block_id in blocks:
                raise LayoutError(f"duplicate block {block.block_id}")
            blocks[block.block_id] = block
            by_number[(line, block.number)] = block.block_id
            neighbours[block.block_id] = set()
        line_switches = _read_switches(line, raw_blocks, by_number)
        switches.update((s.switch_id, s) for s in line_switches)
        raw_next = _read_next_blocks(line, raw_blocks)
        if raw_next is None:
            # Not annotated: infer the joins from the numbering.
            _link_sequential(line, line_blocks, neighbours, by_number)
            for switch in line_switches:
                for leg in (switch.normal_block_id, switch.reverse_block_id):
                    if leg is not None:
                        neighbours[switch.point_block_id].add(leg)
                        neighbours[leg].add(switch.point_block_id)
            continue
        exits = _resolve_exits(line, raw_next, by_number)
        _check_directions(line, exits, line_switches, blocks)
        for block_id, outs in exits.items():
            for out in outs:
                if out is not None:
                    neighbours[block_id].add(out)
                    neighbours[out].add(block_id)
            blocks[block_id] = dataclasses.replace(
                blocks[block_id],
                next_block_ids=outs,
                bidirectional=any(
                    out is not None and block_id in exits[out]
                    for out in outs
                ),
            )

    frozen = {b: frozenset(n) for b, n in neighbours.items()}
    predecessors: dict[str, list[str]] = {b: [] for b in blocks}
    for block in blocks.values():
        for out in block.next_block_ids:
            if out is not None:
                predecessors[out].append(block.block_id)
    return Layout(
        blocks=blocks,
        switches=switches,
        neighbours=frozen,
        signal_block_ids=_signal_blocks(switches, frozen, blocks),
        beacons=_beacons(blocks, frozen),
        _by_number=by_number,
        _predecessors={b: tuple(p) for b, p in predecessors.items()},
    )


def _read_next_blocks(
    line: str, raw_blocks: list[Any]
) -> dict[int, list[int | None]] | None:
    """Return each block's ``next_blocks`` by number, or None.

    None when no block on the line has the field. Every block must have
    it if any does. ``"yard"`` becomes None.
    """
    annotated = [raw for raw in raw_blocks if "next_blocks" in raw]
    if not annotated:
        return None
    if len(annotated) != len(raw_blocks):
        missing = [raw["block_number"] for raw in raw_blocks
                   if "next_blocks" not in raw]
        raise LayoutError(
            f"{line}: next_blocks missing on blocks {missing}; annotate "
            f"every block on a line or none"
        )
    result: dict[int, list[int | None]] = {}
    for raw in raw_blocks:
        number = int(raw["block_number"])
        values = raw["next_blocks"]
        if not isinstance(values, list) or not values:
            raise LayoutError(
                f"{line} block {number}: next_blocks must be a non-empty "
                f"list"
            )
        outs: list[int | None] = []
        for value in values:
            if isinstance(value, str) and value.upper() == YARD:
                outs.append(None)
            elif isinstance(value, int) and not isinstance(value, bool):
                outs.append(value)
            else:
                raise LayoutError(
                    f"{line} block {number}: bad next_blocks entry {value!r}"
                )
        result[number] = outs
    return result


def _resolve_exits(
    line: str,
    raw_next: Mapping[int, list[int | None]],
    by_number: Mapping[tuple[str, int], str],
) -> dict[str, tuple[str | None, ...]]:
    # Turn block numbers into block IDs; None (the yard) stays None.
    exits: dict[str, tuple[str | None, ...]] = {}
    for number, outs in raw_next.items():
        resolved: list[str | None] = []
        for out in outs:
            if out is None:
                resolved.append(None)
                continue
            out_id = by_number.get((line, out))
            if out_id is None:
                raise LayoutError(
                    f"{line} block {number}: next_blocks names missing "
                    f"block {out}"
                )
            resolved.append(out_id)
        exits[by_number[(line, number)]] = tuple(resolved)
    return exits


def _check_directions(
    line: str,
    exits: Mapping[str, tuple[str | None, ...]],
    switches: list[Switch],
    blocks: Mapping[str, Block],
) -> None:
    """Check ``next_blocks`` agrees with the line's switches.

    A join between non-consecutive numbers must be a switch leg, every
    switch leg must be a join, the yard may only be named where a switch
    leads into it, and every block needs a way in.
    """
    by_point = {s.point_block_id: s for s in switches}

    def is_leg(point: str, other: str | None) -> bool:
        switch = by_point.get(point)
        return switch is not None and other in (
            switch.normal_block_id, switch.reverse_block_id
        )

    entered: set[str] = {s.point_block_id for s in switches if s.from_yard}
    for block_id, outs in exits.items():
        for out in outs:
            if out is None:
                switch = by_point.get(block_id)
                if (switch is None or switch.from_yard
                        or None not in (switch.normal_block_id,
                                        switch.reverse_block_id)):
                    raise LayoutError(
                        f"{block_id}: next_blocks names the yard, but no "
                        f"switch there leads into it"
                    )
                continue
            entered.add(out)
            gap = abs(blocks[block_id].number - blocks[out].number)
            if gap != 1 and not (is_leg(block_id, out)
                                 or is_leg(out, block_id)):
                raise LayoutError(
                    f"{block_id} -> {out}: blocks are not consecutive and "
                    f"no switch joins them"
                )

    for switch in switches:
        point = switch.point_block_id
        for leg in (switch.normal_block_id, switch.reverse_block_id):
            if leg is None:
                if not switch.from_yard and None not in exits[point]:
                    raise LayoutError(
                        f"{point}: switch leads to the yard but "
                        f"next_blocks does not"
                    )
            elif leg not in exits[point] and point not in exits[leg]:
                raise LayoutError(
                    f"{point}: switch leg {leg} is not in next_blocks "
                    f"either way"
                )

    no_way_in = sorted(set(exits) - entered, key=lambda b: blocks[b].number)
    if no_way_in:
        raise LayoutError(f"{line}: no block leads into {no_way_in}")


def _read_line(data: Any, path: str | Path) -> tuple[str, list[Any]]:
    # Validate the top level of one layout file.
    if not isinstance(data, dict) or "line" not in data:
        raise LayoutError(f"{path}: no 'line' field")
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise LayoutError(f"{path}: no blocks")
    return str(data["line"]).upper(), raw_blocks


def _read_block(line: str, raw: Mapping[str, Any]) -> Block:
    # Convert one block record to backend units.
    infra = raw.get("infrastructure") or {}
    number = int(raw["block_number"])
    station = infra.get("station")
    side = _STATION_SIDES.get(str(raw.get("station_side")))
    return Block(
        block_id=block_id_for(line, str(raw["section"]), number),
        line=line,
        section=str(raw["section"]),
        number=number,
        length_m=float(raw["length_m"]),
        grade_deg=grade_percent_to_deg(float(raw["grade_percent"])),
        speed_limit_mps=float(raw["speed_limit_kmh"]) / KMH_PER_MPS,
        elevation_m=float(raw["elevation_m"]),
        station_name=str(station) if station else None,
        platform_side=side if station else None,
        underground=bool(infra.get("underground", False)),
        has_crossing=bool(infra.get("railway_crossing", False)),
    )


def _link_sequential(
    line: str,
    line_blocks: list[Block],
    neighbours: dict[str, set[str]],
    by_number: Mapping[tuple[str, int], str],
) -> None:
    # Join consecutive numbers except at the known branch ends.
    breaks = _SEGMENT_BREAKS.get(line, frozenset())
    for block in line_blocks:
        after = by_number.get((line, block.number + 1))
        if after is None or (block.number, block.number + 1) in breaks:
            continue
        neighbours[block.block_id].add(after)
        neighbours[after].add(block.block_id)


def _read_switches(
    line: str,
    raw_blocks: list[Any],
    by_number: Mapping[tuple[str, int], str],
) -> list[Switch]:
    # Group every switch text on the line by its point block.
    legs: dict[int, list[int | None]] = {}
    sources: dict[int, list[str]] = {}
    for raw in raw_blocks:
        text = (raw.get("infrastructure") or {}).get("switch")
        if not text:
            continue
        for point, leg in _parse_switch_text(str(text)):
            point_legs = legs.setdefault(point, [])
            if leg not in point_legs:
                point_legs.append(leg)
            if text not in sources.setdefault(point, []):
                sources[point].append(str(text))

    switches: list[Switch] = []
    for point, point_legs in legs.items():
        if len(point_legs) != 2:
            raise LayoutError(
                f"{line} switch at {point}: expected 2 legs, "
                f"got {point_legs}"
            )
        point_id = _lookup(line, point, by_number)
        normal, reverse = (
            None if leg is None else _lookup(line, leg, by_number)
            for leg in point_legs
        )
        switches.append(Switch(
            switch_id=point_id,
            line=line,
            point_block_id=point_id,
            normal_block_id=normal,
            reverse_block_id=reverse,
            source="; ".join(sources[point]),
            from_yard=any(
                s.strip().upper().startswith(YARD) for s in sources[point]
            ),
        ))
    return switches


def _parse_switch_text(text: str) -> list[tuple[int, int | None]]:
    """Return ``(point, leg)`` pairs for one layout switch string.

    Forms in the course files:

    - ``"12-13; 1-13"``: the point is the number common to both pairs,
      and the legs are the other ends, the first listed being NORMAL.
    - ``"5 to 6"``: one leg of the switch at 5; other rows add the rest.
    - ``"57-yard"``: leaving 57 for the yard instead of 58, so the legs
      are 58 (NORMAL) and the yard (REVERSE).
    - ``"Yard-63"``: entering 63 from the yard instead of from 62, so
      the legs are 62 (NORMAL) and the yard (REVERSE).

    Which leg is NORMAL is provisional: the files do not say.
    """
    to_match = _TO.match(text)
    if to_match:
        return [(int(to_match.group(1)), int(to_match.group(2)))]

    pairs = [_PAIR.match(part) for part in text.split(";")]
    if not all(pairs):
        raise LayoutError(f"unreadable switch text {text!r}")
    ends = [(m.group(1), m.group(2)) for m in pairs if m is not None]

    if len(ends) == 2:
        first, second = ({int(e) for e in pair} for pair in ends)
        common = first & second
        if len(common) != 1:
            raise LayoutError(f"no common point in switch text {text!r}")
        point = common.pop()
        return [(point, (first - {point}).pop()),
                (point, (second - {point}).pop())]

    left, right = ends[0]
    if right.upper() == YARD:
        point = int(left)
        return [(point, point + 1), (point, None)]
    if left.upper() == YARD:
        point = int(right)
        return [(point, point - 1), (point, None)]
    raise LayoutError(f"single-pair switch text without a yard {text!r}")


def _lookup(
    line: str, number: int, by_number: Mapping[tuple[str, int], str]
) -> str:
    # Resolve a block number named by a switch on this line.
    try:
        return by_number[(line, number)]
    except KeyError:
        raise LayoutError(
            f"{line}: switch names missing block {number}"
        ) from None


def _signal_blocks(
    switches: Mapping[str, Switch],
    neighbours: Mapping[str, frozenset[str]],
    blocks: Mapping[str, Block],
) -> tuple[str, ...]:
    """Return the blocks that carry a signal light.

    One signal stands on each block right before a switch: the point's
    neighbours on its fixed side, the side away from the legs.
    """
    signals: set[str] = set()
    for switch in switches.values():
        legs = {switch.normal_block_id, switch.reverse_block_id}
        signals |= set(neighbours[switch.point_block_id]) - legs
    order = list(blocks)
    return tuple(sorted(signals, key=order.index))


def _beacons(
    blocks: Mapping[str, Block],
    neighbours: Mapping[str, frozenset[str]],
) -> dict[str, Beacon]:
    """Return the beacon carried by each block next to a station.

    Provisional placement: one beacon on every neighbour of a station
    block that is not itself a station.
    """
    beacons: dict[str, Beacon] = {}
    for block in blocks.values():
        if block.station_name is None:
            continue
        beacon = Beacon(
            station_name=block.station_name,
            platform_side=block.platform_side,
            underground=block.underground,
        )
        for neighbour in sorted(neighbours[block.block_id]):
            if blocks[neighbour].station_name is None:
                beacons.setdefault(neighbour, beacon)
    return beacons
