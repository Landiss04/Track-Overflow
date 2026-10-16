"""Layout loading, unit conversion and the track graph."""

from __future__ import annotations

import math

import pytest

from track_model.interface import SwitchPosition
from track_model.layout import (
    LayoutError,
    Layout,
    _parse_switch_text,
    load_layout,
)
from tests.helpers import LAYOUT_PATHS

NORMAL = {"BLUE A-5": SwitchPosition.NORMAL}
REVERSE = {"BLUE A-5": SwitchPosition.REVERSE}


@pytest.fixture(scope="module")
def layout() -> Layout:
    """Return every course line, loaded once."""
    return load_layout(LAYOUT_PATHS)


def test_all_three_lines_load(layout: Layout) -> None:
    """Check the block counts of the Blue, Red and Green lines."""
    lines = [b.line for b in layout.blocks.values()]
    assert (lines.count("BLUE"), lines.count("RED"),
            lines.count("GREEN")) == (15, 76, 150)


def test_ids_are_strings_with_line_and_section(layout: Layout) -> None:
    """Check the block ID format and that every ID is a string."""
    assert "GREEN A-1" in layout.blocks
    assert all(isinstance(b, str) for b in layout.blocks)


def test_units_are_converted_on_read(layout: Layout) -> None:
    """Check grade % -> deg and km/h -> m/s for GREEN A-1."""
    block = layout.blocks["GREEN A-1"]
    assert block.grade_deg == pytest.approx(math.degrees(math.atan(0.005)))
    assert block.speed_limit_mps == pytest.approx(45 / 3.6)
    assert block.length_m == 100.0


def test_station_side_and_underground(layout: Layout) -> None:
    """Check station name, platform side and underground flag."""
    pioneer = layout.blocks["GREEN A-2"]
    assert (pioneer.station_name, pioneer.platform_side) == ("PIONEER", "L")
    central = next(
        b for b in layout.blocks.values() if b.station_name == "CENTRAL"
    )
    assert central.underground


@pytest.mark.parametrize("text, expected", [
    ("12-13; 1-13", [(13, 12), (13, 1)]),
    ("76-77;77-101", [(77, 76), (77, 101)]),
    ("57-yard", [(57, 58), (57, None)]),
    ("Yard-63", [(63, 62), (63, None)]),
    ("5 to 11", [(5, 11)]),
])
def test_switch_text_parses(
    text: str, expected: list[tuple[int, int | None]]
) -> None:
    """Check every switch string form in the course files."""
    assert _parse_switch_text(text) == expected


def test_unreadable_switch_text_is_rejected() -> None:
    """Check that an unknown switch string raises instead of guessing."""
    with pytest.raises(LayoutError):
        _parse_switch_text("13 or 14")


def test_switches_found(layout: Layout) -> None:
    """Check switch counts per line and one known switch's legs."""
    lines = [s.line for s in layout.switches.values()]
    assert (lines.count("BLUE"), lines.count("RED"),
            lines.count("GREEN")) == (1, 7, 6)
    blue = layout.switches["BLUE A-5"]
    assert (blue.normal_block_id, blue.reverse_block_id) == (
        "BLUE B-6", "BLUE C-11")


def test_crossings_found(layout: Layout) -> None:
    """Check that railway crossings are flagged on their blocks."""
    assert layout.blocks["BLUE A-3"].has_crossing
    assert not layout.blocks["BLUE A-4"].has_crossing


def test_segment_breaks_are_not_joined(layout: Layout) -> None:
    """Check that branch ends are not joined to the next number."""
    assert "BLUE C-11" not in layout.neighbours["BLUE B-10"]
    assert "GREEN R-101" not in layout.neighbours["GREEN Q-100"]


def test_next_block_follows_the_given_switch_position(
    layout: Layout,
) -> None:
    """Check both legs, and that the switch state is only read."""
    states = dict(NORMAL)
    assert layout.next_block("BLUE A-5", "BLUE A-4", states) == "BLUE B-6"
    assert states == NORMAL
    assert layout.next_block("BLUE A-5", "BLUE A-4", REVERSE) == "BLUE C-11"


def test_trailing_move_leaves_by_the_fixed_side(layout: Layout) -> None:
    """Check that a train entering the points from a leg goes straight."""
    for states in (NORMAL, REVERSE):
        assert layout.next_block(
            "BLUE A-5", "BLUE C-11", states) == "BLUE A-4"


def test_yard_leg_returns_none(layout: Layout) -> None:
    """Check that a switch leg into the yard is reported as None."""
    states = {"GREEN I-57": SwitchPosition.REVERSE}
    assert layout.next_block("GREEN I-57", "GREEN I-56", states) is None


def test_dead_end_stays_put(layout: Layout) -> None:
    """Check that a train at the end of a branch does not move."""
    assert layout.next_block("BLUE B-10", "BLUE B-9", {}) == "BLUE B-10"


def test_signals_stand_before_each_switch(layout: Layout) -> None:
    """Check signal placement on the fixed side of every switch point."""
    assert "BLUE A-4" in layout.signal_block_ids
    assert "GREEN D-14" in layout.signal_block_ids
    assert len(layout.signal_block_ids) == len(layout.switches)


def test_beacons_flank_stations(layout: Layout) -> None:
    """Check that a station's neighbours carry its beacon."""
    beacon = layout.beacons["GREEN A-3"]
    assert (beacon.station_name, beacon.platform_side) == ("PIONEER", "L")
    assert "GREEN A-2" not in layout.beacons
