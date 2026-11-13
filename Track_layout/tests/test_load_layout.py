"""Loading a track from a JSON file while the module is running."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from track_model.layout import LayoutError
from tests.helpers import DT_S, MODULE_DIR, make_inputs, make_model, report


def _tiny_blue(path: Path) -> str:
    # A two-block Blue line, small enough to tell from the real one.
    block = {"section": "A", "length_m": 20.0, "grade_percent": 0.0,
             "speed_limit_kmh": 40.0, "elevation_m": 0.0}
    data = {"line": "Blue", "blocks": [
        {**block, "block_number": 1}, {**block, "block_number": 2},
    ]}
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_load_replaces_the_line_of_the_same_name(tmp_path: Path) -> None:
    """Check that a file replaces its line and leaves the others."""
    model = make_model()
    before = {b.block_id for b in model.snapshot().blocks
              if b.line != "BLUE"}
    line = model.load_layout_file(str(MODULE_DIR / "blue_line.json"))
    blocks = model.snapshot().blocks
    assert line == "BLUE"
    assert before <= {b.block_id for b in blocks}
    assert {"BLUE", "GREEN", "RED"} == {b.line for b in blocks}


def test_load_restarts_the_module() -> None:
    """Check that loading clears trains and the clock."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1")}))
    model.load_layout_file(str(MODULE_DIR / "green_line.json"))
    snap = model.snapshot()
    assert snap.trains == ()
    assert snap.elapsed_s == 0.0


def test_load_a_different_track(tmp_path: Path) -> None:
    """Check that a new file's blocks replace the old line's."""
    model = make_model()
    model.load_layout_file(_tiny_blue(tmp_path / "tiny.json"))
    blue = [b for b in model.snapshot().blocks if b.line == "BLUE"]
    assert len(blue) == 2


@pytest.mark.parametrize("text", [
    "not json", "[]", '{"line": "X"}',
    '{"line": "X", "blocks": [{"section": "A"}]}',
])
def test_bad_file_changes_nothing(tmp_path: Path, text: str) -> None:
    """Check that an unreadable file raises and leaves the track alone."""
    model = make_model()
    model.step(DT_S, make_inputs({"T1": report("GREEN A-1")}))
    before = model.snapshot()
    bad = tmp_path / "bad.json"
    bad.write_text(text, encoding="utf-8")
    with pytest.raises(LayoutError):
        model.load_layout_file(str(bad))
    assert model.snapshot() == before


def test_missing_file_raises(tmp_path: Path) -> None:
    """Check that a file that does not exist raises LayoutError."""
    with pytest.raises(LayoutError):
        make_model().load_layout_file(str(tmp_path / "nope.json"))
