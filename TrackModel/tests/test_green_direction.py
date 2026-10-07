"""Green line direction of travel, from ``next_blocks`` in the layout.

Directions come from the arrows on the course track map. The joins
between non-consecutive blocks agree with the switch entries in
``Track Layout & Vehicle Data vF5.xlsx`` (Green Line sheet).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from track_model.layout import Layout, LayoutError, load_layout
from tests.helpers import DT_S, MODULE_DIR, make_inputs, make_model, report

GREEN_PATH = MODULE_DIR / "green_line.json"
FAR_M = 100_000.0


@pytest.fixture(scope="module")
def green() -> Layout:
    """Return the annotated Green line."""
    return load_layout([GREEN_PATH])


def raw_green() -> dict[str, Any]:
    """Return the Green layout file as parsed JSON."""
    with open(GREEN_PATH, encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def write(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write a layout file into the test's temporary folder."""
    path = tmp_path / "green_line.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return path


def nums(green: Layout, block_id: str) -> set[int | None]:
    """Return a block's next blocks as numbers; None is the yard."""
    return {None if b is None else green.blocks[b].number
            for b in green.blocks[block_id].next_block_ids}


def by_number(green: Layout, number: int) -> str:
    """Return the Green block ID for a block number."""
    return next(b.block_id for b in green.blocks.values()
                if b.number == number)


# --------------------------------------------------------------------------- #
# The data
# --------------------------------------------------------------------------- #

def test_every_green_block_has_next_blocks(green: Layout) -> None:
    """Check no Green block is left without a direction."""
    assert all(b.next_block_ids for b in green.blocks.values())


@pytest.mark.parametrize("number, expected", [
    (1, {13}),          # start of A runs up into D
    (12, {11}),         # C runs away from D, toward B
    (13, {12, 14}),
    (28, {27, 29}),
    (57, {58, None}),   # on to J, or into the yard
    (63, {64}),
    (76, {77}),         # end of M into N
    (77, {78, 101}),
    (85, {84, 86}),     # end of N
    (100, {85}),
    (101, {102}),
    (150, {28}),        # Z into F
])
def test_next_blocks_at_the_key_points(
    green: Layout, number: int, expected: set[int | None],
) -> None:
    """Check the switch ends and section ends named on the map."""
    assert nums(green, by_number(green, number)) == expected


def test_two_way_blocks_are_d_to_f_and_n(green: Layout) -> None:
    """Check exactly 13-28 and 77-85 run both ways."""
    two_way = {b.number for b in green.blocks.values() if b.bidirectional}
    assert two_way == set(range(13, 29)) | set(range(77, 86))


@pytest.mark.parametrize("first, last, step", [
    (2, 12, -1),      # A, B, C: downward
    (29, 56, 1),      # G, H, I
    (58, 75, 1),      # J, K, L, M
    (86, 99, 1),      # O, P, Q
    (101, 149, 1),    # R ... Y
])
def test_one_way_runs(green: Layout, first: int, last: int,
                      step: int) -> None:
    """Check each one-way run leads block to block in its direction."""
    for number in range(first, last + 1):
        assert nums(green, by_number(green, number)) == {number + step}


def test_annotation_matches_the_old_inferred_track(tmp_path: Path) -> None:
    """Check next_blocks joins exactly the blocks the old inference did."""
    data = raw_green()
    for block in data["blocks"]:
        del block["next_blocks"]
    inferred = load_layout([write(tmp_path, data)])
    annotated = load_layout([GREEN_PATH])
    # Without next_blocks, Green needs its old branch-end break.
    fixed = {b: set(n) for b, n in inferred.neighbours.items()}
    fixed["GREEN Q-100"].discard("GREEN R-101")
    fixed["GREEN R-101"].discard("GREEN Q-100")
    assert fixed == {b: set(n) for b, n in annotated.neighbours.items()}


def test_every_block_reachable_from_the_yard(green: Layout) -> None:
    """Follow next_blocks from the yard entry: all 150 and the yard."""
    seen: set[str | None] = set()
    stack: list[str | None] = ["GREEN K-63"]
    while stack:
        block = stack.pop()
        if block in seen:
            continue
        seen.add(block)
        if block is not None:
            stack.extend(green.blocks[block].next_block_ids)
    assert seen - {None} == set(green.blocks)
    assert None in seen


def test_red_and_blue_are_not_annotated() -> None:
    """Check the other lines still use the inferred track."""
    model = make_model()
    blocks = model.snapshot().blocks
    assert all(b.next_block_ids == () for b in blocks
               if b.line in ("RED", "BLUE"))


# --------------------------------------------------------------------------- #
# What direction changes in the model
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("start, expected", [
    ("GREEN C-10", "GREEN C-9"),     # used to go to 11
    ("GREEN A-1", "GREEN D-13"),
    ("GREEN Z-150", "GREEN F-28"),
    ("GREEN Q-100", "GREEN N-85"),
    ("GREEN B-5", "GREEN B-4"),
])
def test_new_train_heads_the_way_the_block_runs(
    start: str, expected: str,
) -> None:
    """Check a train placed on a one-way block moves in its direction."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report(start, 1.0)}))
    out = model.step(DT_S, make_inputs({"T1": report(start, FAR_M)}))
    assert out.train_feeds["T1"].track_info.block_id == expected


@pytest.mark.parametrize("start, expected", [
    ("GREEN C-10", "GREEN C-11"),
    ("GREEN R-101", "GREEN N-77"),
    ("GREEN A-1", "GREEN A-2"),
])
def test_new_train_rolls_back_to_the_block_behind(
    start: str, expected: str,
) -> None:
    """Check rollback of a placed train goes to the block feeding it."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report(start, 1.0)}))
    out = model.step(DT_S, make_inputs({"T1": report(start, -1.0)}))
    assert out.train_feeds["T1"].track_info.block_id == expected


def test_a_to_c_loop_runs_round_into_d() -> None:
    """Drive from C-12 down through B and A, then up through D."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN C-12", 1.0)}))
    block, path = "GREEN C-12", ["GREEN C-12"]
    for _ in range(13):
        out = model.step(DT_S, make_inputs({"T1": report(block, FAR_M)}))
        block = out.train_feeds["T1"].track_info.block_id
        path.append(block)
    numbers = [int(b.rsplit("-", 1)[1]) for b in path]
    assert numbers == [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 13, 14]


# --------------------------------------------------------------------------- #
# The loader rejects a bad annotation
# --------------------------------------------------------------------------- #

def test_partial_annotation_is_rejected(tmp_path: Path) -> None:
    """Check a line must annotate every block or none."""
    data = raw_green()
    del data["blocks"][40]["next_blocks"]
    with pytest.raises(LayoutError, match="missing on blocks"):
        load_layout([write(tmp_path, data)])


def test_unknown_next_block_is_rejected(tmp_path: Path) -> None:
    """Check next_blocks may only name blocks on the line."""
    data = raw_green()
    data["blocks"][9]["next_blocks"] = [151]
    with pytest.raises(LayoutError, match="missing block 151"):
        load_layout([write(tmp_path, data)])


def test_yard_without_a_yard_switch_is_rejected(tmp_path: Path) -> None:
    """Check "yard" only where a switch leads into the yard."""
    data = raw_green()
    data["blocks"][9]["next_blocks"] = [9, "yard"]
    with pytest.raises(LayoutError, match="yard"):
        load_layout([write(tmp_path, data)])


def test_unswitched_jump_is_rejected(tmp_path: Path) -> None:
    """Check a join between non-consecutive blocks needs a switch."""
    data = raw_green()
    data["blocks"][49]["next_blocks"] = [70]        # 50 -> 70
    with pytest.raises(LayoutError, match="no switch joins them"):
        load_layout([write(tmp_path, data)])


def test_missing_switch_leg_is_rejected(tmp_path: Path) -> None:
    """Check every switch leg appears in next_blocks."""
    data = raw_green()
    data["blocks"][149]["next_blocks"] = [149]      # drop 150 -> 28
    with pytest.raises(LayoutError, match="switch leg"):
        load_layout([write(tmp_path, data)])


def test_block_with_no_way_in_is_rejected(tmp_path: Path) -> None:
    """Check every block is entered from somewhere."""
    data = raw_green()
    data["blocks"][129]["next_blocks"] = [129]      # 130 -> 129, not 131
    with pytest.raises(LayoutError, match=r"no block leads into.*W-131"):
        load_layout([write(tmp_path, data)])
