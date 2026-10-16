"""Wayside databases: the JSON file that defines one wayside's territory.

The format is the course track layout file (``TrackModel/*.json``) cut
down to the blocks one wayside governs, with a ``wayside`` field added::

    {
      "line": "Green",
      "wayside": "1",
      "blocks": [
        {"block_number": 12, "section": "C", "length_m": 100,
         "speed_limit_kmh": 45,
         "infrastructure": {"switch": "12-13; 1-13"}},
        ...
      ]
    }

Only what the controller uses is read: block number, section, length,
speed limit, and the ``switch`` and ``railway_crossing`` entries under
``infrastructure``. Everything else in the file (grade, elevation,
stations, beacons, ...) belongs to other modules and is ignored.

A switch string lists its connections, normal first and reverse second,
as the layout file does: ``"12-13; 1-13"`` joins 12 to 13 when normal
and 1 to 13 when reversed. The block both connections share is the
switch's point. A string with one connection, such as ``"57-yard"``,
lists only the diverging route; its normal route is the main line
through the block the switch is listed on. A signal stands at every
switch, and nowhere else.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from track_ctrl_hw.errors import TerritoryError
from track_ctrl_hw.interface import Block, BlockKey, Switch, Territory

YARD = "yard"

_KMH_PER_MPS = 3.6
_CONNECTION_SPLIT = re.compile(r"\s*(?:-|\bto\b)\s*", re.IGNORECASE)


def load_territory_file(path: str | Path) -> Territory:
    """Read and check one wayside database file.

    Raises:
        TerritoryError: If the file cannot be read or is malformed.
    """
    try:
        with open(path, encoding="utf-8") as database:
            data = json.load(database)
    except OSError as error:
        raise TerritoryError(
            f"Cannot read {Path(path).name}: {error}"
        ) from error
    except ValueError as error:
        raise TerritoryError(
            f"{Path(path).name} is not valid JSON: {error}"
        ) from error
    return parse_territory(data)


def parse_territory(data: Any) -> Territory:
    """Build a territory from a decoded wayside database.

    Raises:
        TerritoryError: If a required field is missing or malformed.
    """
    if not isinstance(data, Mapping):
        raise TerritoryError("A wayside database must be a JSON object.")
    line = _text(data.get("line"), "line")
    if "wayside" not in data:
        raise TerritoryError(
            "This file has no \"wayside\" field. A wayside database is the "
            "track layout file cut to one wayside's blocks, with the "
            "wayside named."
        )
    wayside_id = _identifier(data["wayside"], "wayside")
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise TerritoryError("\"blocks\" must be a non-empty list.")

    blocks: list[Block] = []
    switch_text: list[tuple[BlockKey, str]] = []
    crossings: list[BlockKey] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_blocks, start=1):
        if not isinstance(raw, Mapping):
            raise TerritoryError(f"Block entry {index} is not an object.")
        block_id = _identifier(raw.get("block_number"), "block_number", index)
        if not block_id.isdigit():
            raise TerritoryError(
                f"Block entry {index}: block_number {block_id!r} is not a "
                "whole number."
            )
        if block_id in seen:
            raise TerritoryError(f"Block {block_id} is listed twice.")
        seen.add(block_id)
        section = _text(raw.get("section"), "section", index)
        key = BlockKey(line=line, section=section, block_id=block_id)
        length_m = _positive(raw.get("length_m"), "length_m", block_id)
        limit_kmh = _positive(
            raw.get("speed_limit_kmh"), "speed_limit_kmh", block_id
        )
        blocks.append(
            Block(
                key=key,
                length_m=length_m,
                speed_limit_mps=limit_kmh / _KMH_PER_MPS,
            )
        )
        infrastructure = raw.get("infrastructure") or {}
        if not isinstance(infrastructure, Mapping):
            raise TerritoryError(
                f"Block {block_id}: \"infrastructure\" is not an object."
            )
        if "switch" in infrastructure:
            text = infrastructure["switch"]
            if not isinstance(text, str) or not text.strip():
                raise TerritoryError(
                    f"Block {block_id}: the switch entry is not text."
                )
            switch_text.append((key, text))
        crossing = infrastructure.get("railway_crossing", False)
        if not isinstance(crossing, bool):
            raise TerritoryError(
                f"Block {block_id}: \"railway_crossing\" must be true or "
                "false."
            )
        if crossing:
            crossings.append(key)

    switches = tuple(
        parse_switch(key, text, seen) for key, text in switch_text
    )
    return Territory(
        line=line,
        wayside_id=wayside_id,
        blocks=tuple(blocks),
        switches=switches,
        crossings=tuple(crossings),
    )


def parse_switch(
    key: BlockKey, text: str, territory_ids: set[str] | frozenset[str]
) -> Switch:
    """Read one switch string listed on ``key``.

    Raises:
        TerritoryError: If the string is not one or two connections, or
            the switch's point lies outside the territory.
    """
    where = f"Switch on block {key.block_id} ({text.strip()!r})"
    parts = [part for part in text.split(";") if part.strip()]
    if not 1 <= len(parts) <= 2:
        raise TerritoryError(f"{where}: expected one or two connections.")
    connections = [_connection(part, where) for part in parts]

    if len(connections) == 2:
        first, second = connections
        shared = set(first) & set(second)
        if len(shared) != 1 or YARD in shared:
            raise TerritoryError(
                f"{where}: the two connections must share exactly one "
                "block."
            )
        point = shared.pop()
        normal_end = first[1] if first[0] == point else first[0]
        reverse_end = second[1] if second[0] == point else second[0]
    else:
        (only,) = connections
        if YARD not in only:
            raise TerritoryError(
                f"{where}: a single connection must lead to the yard."
            )
        point = only[1] if only[0] == YARD else only[0]
        if point == key.block_id:
            raise TerritoryError(
                f"{where}: its normal route is not listed and cannot be "
                "inferred."
            )
        normal_end = key.block_id
        reverse_end = YARD

    if point not in territory_ids:
        raise TerritoryError(
            f"{where}: its point, block {point}, is outside this wayside."
        )
    return Switch(
        key=key,
        point=point,
        normal_end=normal_end,
        reverse_end=reverse_end,
    )


def _connection(part: str, where: str) -> tuple[str, str]:
    # One "a-b" or "a to b" connection, ends normalised.
    ends = [end for end in _CONNECTION_SPLIT.split(part.strip()) if end]
    if len(ends) != 2:
        raise TerritoryError(f"{where}: cannot read connection {part!r}.")
    normalised = []
    for end in ends:
        if end.lower() == YARD:
            normalised.append(YARD)
        elif end.isdigit():
            normalised.append(str(int(end)))
        else:
            raise TerritoryError(
                f"{where}: {end!r} is not a block number or the yard."
            )
    if normalised[0] == normalised[1]:
        raise TerritoryError(f"{where}: connection {part!r} is a loop.")
    return normalised[0], normalised[1]


def _identifier(value: Any, name: str, index: int | None = None) -> str:
    # IDs are strings; a whole JSON number is accepted and converted.
    where = f"Block entry {index}: " if index is not None else ""
    if isinstance(value, bool) or value is None:
        raise TerritoryError(f"{where}\"{name}\" is missing.")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise TerritoryError(f"{where}\"{name}\" must be text or a whole number.")


def _text(value: Any, name: str, index: int | None = None) -> str:
    where = f"Block entry {index}: " if index is not None else ""
    if not isinstance(value, str) or not value.strip():
        raise TerritoryError(f"{where}\"{name}\" must be non-empty text.")
    return value.strip()


def _positive(value: Any, name: str, block_id: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise TerritoryError(
            f"Block {block_id}: \"{name}\" must be a positive number."
        )
    return float(value)
