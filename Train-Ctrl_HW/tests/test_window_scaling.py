"""Physical-pixel regression for the shared Windows minimum-size lock."""

import pytest

from ui.aspect_lock import constrain_drag


@pytest.mark.parametrize("edge", range(1, 9))
@pytest.mark.parametrize("height", [562, 563])
def test_inward_drag_preserves_fractional_dpi_minimum(edge, height):
    """At 125%, 450 logical pixels may occupy 562 or 563 physical pixels."""
    frame = (18, 48)
    original = (100, 100, 1018, 100 + height + frame[1])
    left, top, right, bottom = original
    if edge in (1, 4, 7):
        left += 50
    if edge in (2, 5, 8):
        right -= 50
    if edge in (3, 4, 5):
        top += 30
    if edge in (6, 7, 8):
        bottom -= 30
    assert constrain_drag(
        edge, (left, top, right, bottom), frame, (900, height),
        900, (16, 10),
    ) == original


@pytest.mark.parametrize("edge", range(1, 9))
def test_outward_drag_can_leave_fractional_dpi_minimum(edge):
    """Holding an inward drag must not trap the window at minimum size."""
    frame = (18, 48)
    original = (100, 100, 1018, 711)
    left, top, right, bottom = original
    if edge in (1, 4, 7):
        left -= 50
    if edge in (2, 5, 8):
        right += 50
    if edge in (3, 4, 5):
        top -= 30
    if edge in (6, 7, 8):
        bottom += 30
    result = constrain_drag(
        edge, (left, top, right, bottom), frame, (900, 563),
        900, (16, 10),
    )
    assert result != original
    width = result[2] - result[0] - frame[0]
    height = result[3] - result[1] - frame[1]
    assert width > 900
    assert abs(width * 10 - height * 16) <= 16
