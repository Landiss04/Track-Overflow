"""The test UI's block filter: line, section and number range."""

from __future__ import annotations

import pytest

from test_ui.block_filter import (
    BlockRef,
    filter_blocks,
    lines_of,
    parse_block_id,
    parse_range,
    sections_of,
    short_name,
)

IDS = ["BLUE A-1", "BLUE B-6", "GREEN A-1", "GREEN B-4", "GREEN B-5",
       "GREEN D-13", "GREEN Z-150", "RED A-1"]


def test_parse_block_id() -> None:
    """Check a block ID splits into line, section and number."""
    assert parse_block_id("GREEN D-13") == BlockRef("GREEN", "D", 13)
    assert parse_block_id("not a block") is None


def test_short_name_drops_the_line() -> None:
    """Check the line prefix comes off."""
    assert short_name("GREEN Z-150") == "Z-150"


@pytest.mark.parametrize("text, expected", [
    ("", None), ("  ", None), ("12", (12, 12)), ("5-20", (5, 20)),
    (" 5 - 20 ", (5, 20)),
])
def test_parse_range(text: str, expected: tuple[int, int] | None) -> None:
    """Check the accepted range forms."""
    assert parse_range(text) == expected


@pytest.mark.parametrize("text", ["9-3", "a-b", "5-", "1,2"])
def test_parse_range_rejects(text: str) -> None:
    """Check malformed or backwards ranges raise."""
    with pytest.raises(ValueError):
        parse_range(text)


def test_lines_and_sections_in_layout_order() -> None:
    """Check lines and a line's sections come out in first-seen order."""
    assert lines_of(IDS) == ["BLUE", "GREEN", "RED"]
    assert sections_of(IDS, "GREEN") == ["A", "B", "D", "Z"]


@pytest.mark.parametrize("section, number_range, expected", [
    ("", None, ["GREEN A-1", "GREEN B-4", "GREEN B-5", "GREEN D-13",
                "GREEN Z-150"]),
    ("B", None, ["GREEN B-4", "GREEN B-5"]),
    ("", (5, 13), ["GREEN B-5", "GREEN D-13"]),
    ("B", (5, 5), ["GREEN B-5"]),
    ("C", None, []),
])
def test_filter_blocks(
    section: str, number_range: tuple[int, int] | None,
    expected: list[str],
) -> None:
    """Check line, section and range combine."""
    assert filter_blocks(IDS, "GREEN", section, number_range) == expected
