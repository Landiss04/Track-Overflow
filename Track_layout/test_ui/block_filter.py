"""Block filtering for the test UI: by line, section and number range.

Works on block IDs alone (``"GREEN D-13"``), since the test UI learns
the track only from the Track Model's outputs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import NamedTuple

_BLOCK_ID = re.compile(r"^(?P<line>\S+) (?P<section>[A-Z]+)-(?P<number>\d+)$")
_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


class BlockRef(NamedTuple):
    """The parts of a block ID."""

    line: str
    section: str
    number: int


def parse_block_id(block_id: str) -> BlockRef | None:
    """Split ``"GREEN D-13"`` into line, section and number."""
    match = _BLOCK_ID.match(block_id)
    if match is None:
        return None
    return BlockRef(match["line"], match["section"], int(match["number"]))


def short_name(block_id: str) -> str:
    """Drop the line from a block ID: ``"GREEN D-13"`` -> ``"D-13"``."""
    return block_id.split(" ", 1)[-1]


def parse_range(text: str) -> tuple[int, int] | None:
    """Read ``"12"`` or ``"5-20"`` as an inclusive range; blank is None.

    Raises ValueError for anything else, or a range that runs backwards.
    """
    if not text.strip():
        return None
    match = _RANGE.match(text)
    if match is None:
        raise ValueError(f"block range {text!r}: use 12 or 5-20")
    low = int(match[1])
    high = int(match[2]) if match[2] else low
    if high < low:
        raise ValueError(f"block range {text!r} runs backwards")
    return low, high


def lines_of(block_ids: Iterable[str]) -> list[str]:
    """Return the lines present, in first-seen order."""
    seen: dict[str, None] = {}
    for block_id in block_ids:
        ref = parse_block_id(block_id)
        if ref is not None:
            seen.setdefault(ref.line)
    return list(seen)


def sections_of(block_ids: Iterable[str], line: str) -> list[str]:
    """Return one line's sections, in first-seen order."""
    seen: dict[str, None] = {}
    for block_id in block_ids:
        ref = parse_block_id(block_id)
        if ref is not None and ref.line == line:
            seen.setdefault(ref.section)
    return list(seen)


def filter_blocks(
    block_ids: Iterable[str],
    line: str,
    section: str = "",
    number_range: tuple[int, int] | None = None,
) -> list[str]:
    """Return the block IDs on ``line`` matching section and range.

    An empty ``section`` or a None range matches everything.
    """
    result = []
    for block_id in block_ids:
        ref = parse_block_id(block_id)
        if ref is None or ref.line != line:
            continue
        if section and ref.section != section:
            continue
        if number_range is not None and not (
            number_range[0] <= ref.number <= number_range[1]
        ):
            continue
        result.append(block_id)
    return result
