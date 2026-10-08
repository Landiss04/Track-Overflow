"""End to end: the test UI harness drives the Track Model over the link.

The harness acts as the Train Model, so a train with a speed travels
block to block and follows the switches the Track Controller set.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.qt_helpers import dispose, qt_app, wait_for
from test_link.link import LinkServer
from test_ui.harness import TrackModelTestHarness
from tests.helpers import make_model

#: The harness, read through its Qt properties. The PySide6 stubs type a
#: Qt property as ``Property`` rather than its value, so reads are Any.
Page = Any


@pytest.fixture()
def harness() -> Iterator[Page]:
    """Return a test UI harness connected to a fresh Track Model."""
    qt_app()
    server = LinkServer(make_model())
    assert server.listen()
    page: Page = TrackModelTestHarness()
    assert wait_for(lambda: page.connected and bool(page.blocks))
    yield page
    page.close()
    server.close()
    dispose(page, server)


def tick(page: Page, count: int = 1) -> None:
    """Send ``count`` ticks, each after the previous reply."""
    for _ in range(count):
        before = page.tick
        page.stepOnce()
        assert wait_for(lambda: page.tick == before + 1
                        and not page._awaiting_reply)  # noqa: SLF001


def feed_value(page: Page, name: str) -> object:
    """Return one row of the selected train's feed."""
    return next(r["value"] for r in page.feedRows if r["id"] == name)


@pytest.mark.parametrize("position, leg", [
    ("NORMAL", "BLUE B-6"),
    ("REVERSE", "BLUE C-11"),
])
def test_train_travels_and_follows_the_switch(
    harness: Page, position: str, leg: str
) -> None:
    """Drive T1 from BLUE A-1 through the switch at A-5."""
    harness.setInput("switch", "BLUE A-5", position)
    harness.addTrain("T1", "BLUE A-1")
    harness.setInput("train", "actual_speed_mps", 20.0)
    visited: list[object] = []
    for _ in range(400):
        tick(harness)
        block = feed_value(harness, "track_info.block_id")
        if not visited or visited[-1] != block:
            visited.append(block)
        if block == leg:
            break
    assert visited[:5] == [f"BLUE A-{n}" for n in range(1, 6)]
    assert visited[-1] == leg


def test_green_train_leaves_the_yard_and_reaches_mt_lebanon(
    harness: Page,
) -> None:
    """Drive T1 out of the yard at GREEN K-63 to N-78 through the link."""
    harness.setInput("signal", "GREEN N-78", "GREEN")
    harness.addTrain("T1", "GREEN K-63")
    harness.setInput("train", "actual_speed_mps", 150.0)  # 15 m per tick
    visited: list[object] = []
    for _ in range(600):
        tick(harness)
        block = feed_value(harness, "track_info.block_id")
        if not visited or visited[-1] != block:
            visited.append(block)
        if block == "GREEN N-78":
            break
    numbers = [int(str(b).rsplit("-", 1)[1]) for b in visited]
    assert numbers == list(range(63, 79))
    rows = {r["id"]: r["value"] for r in harness.trainControllerRows}
    assert rows["signal_seen"] == "GREEN"


def test_signal_colour_is_kept_after_entry(harness: Page) -> None:
    """Check the page keeps the colour a train saw entering BLUE A-4."""
    harness.setInput("signal", "BLUE A-4", "YELLOW")
    harness.addTrain("T1", "BLUE A-3")
    harness.setInput("train", "actual_speed_mps", 20.0)
    for _ in range(200):
        tick(harness)
        if feed_value(harness, "track_info.block_id") == "BLUE A-4":
            break
    rows = {r["id"]: r["value"] for r in harness.trainControllerRows}
    assert "YELLOW" in rows.values()
    harness.setInput("signal", "BLUE A-4", "GREEN")
    tick(harness)
    rows = {r["id"]: r["value"] for r in harness.trainControllerRows}
    assert rows["signal_seen"] == "none"
    assert "YELLOW" in rows.values()


def test_reset_returns_device_commands_to_defaults(harness: Page) -> None:
    """Check reset does not resend the pre-reset switch position."""
    harness.setLine("BLUE")
    harness.setInput("switch", "BLUE A-5", "REVERSE")
    tick(harness)
    harness.resetModule()
    assert wait_for(lambda: bool(harness.switchRows))
    rows = {r["id"]: r["value"] for r in harness.switchRows}
    assert rows["BLUE A-5"] == "NORMAL"
    tick(harness)
    states = {r["id"]: r["value"] for r in harness.deviceStateRows}
    assert states["switch BLUE A-5"] == "NORMAL"


def test_page_starts_on_the_green_line(harness: Page) -> None:
    """Check the main line is shown first, with its devices only."""
    assert harness.line == "GREEN"
    assert harness.filterSummary == "150 of 150 GREEN blocks"
    assert all(b.startswith("GREEN ") for b in harness.filteredBlocks)
    ids = [r["id"] for r in harness.switchRows]
    assert len(ids) == 6 and all(i.startswith("GREEN ") for i in ids)


def test_filter_by_section_and_range(harness: Page) -> None:
    """Check section B, then blocks 20-25, then clearing."""
    harness.setSection("B")
    assert harness.filteredBlocks == ["GREEN B-4", "GREEN B-5", "GREEN B-6"]
    assert harness.selectedBlock == "GREEN B-4"
    harness.setSection("All")
    harness.setRange("20-25")
    numbers = [int(b.rsplit("-", 1)[1]) for b in harness.filteredBlocks]
    assert numbers == list(range(20, 26))
    harness.clearFilter()
    assert len(harness.filteredBlocks) == 150


def test_bad_range_is_reported_not_applied(harness: Page) -> None:
    """Check a range like 9-3 shows an error and keeps the old filter."""
    harness.setRange("9-3")
    assert "backwards" in harness.lastError
    assert harness.rangeText == ""
    assert len(harness.filteredBlocks) == 150


def test_switching_line_resets_the_section(harness: Page) -> None:
    """Check choosing RED shows only red blocks and devices."""
    harness.setSection("B")
    harness.setLine("RED")
    assert harness.section == "All"
    assert all(b.startswith("RED ") for b in harness.filteredBlocks)
    assert harness.selectedBlock.startswith("RED ")
    labels = [r["name"] for r in harness.switchRows]
    assert "H-27" in labels


def test_short_labels_keep_full_ids(harness: Page) -> None:
    """Check rows show short names but are addressed by full ids."""
    harness.addTrain("T1", "GREEN K-63")
    tick(harness)
    feed = {r["name"]: r["id"] for r in harness.feedRows}
    assert feed["block"] == "track_info.block_id"
    assert feed["cmd speed"] == "track_signal.commanded_speed_mps"
    states = {r["name"]: r["id"] for r in harness.deviceStateRows}
    assert states["sw K-63"] == "switch GREEN K-63"
    assert all(len(r["name"]) <= 10 for r in harness.deviceStateRows
               + harness.feedRows + harness.controllerSummaryRows
               + harness.trainRows + harness.blockRows)


def test_rejection_is_shown_not_raised(harness: Page) -> None:
    """Check a bad report surfaces as lastError."""
    harness.addTrain("T1", "BLUE A-1")
    harness.setInput("train", "block_id", "NOWHERE 1")
    harness.stepOnce()
    assert wait_for(lambda: harness.lastError != "")
    assert "NOWHERE" in harness.lastError
