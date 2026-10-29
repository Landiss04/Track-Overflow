"""Observe the existing Green follower rule for Harry and Landis's review.

This seeds owner-boundary snapshots, rather than relocating a live train
in the physics loop. It reuses the SW starter tick helper (``sw_line``);
no launcher or production routing rule is duplicated or changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for folder in (ROOT / "CTC-Office", ROOT / "TrackCtrlSW"):
    sys.path.insert(0, str(folder))

from ctc.interface import (  # noqa: E402
    BlockOccupancy, CtcInputs, SwitchReport, TrackControllerInputs,
    WaysideStatus,
)
from ctc.model import StubCtcOffice  # noqa: E402
from common.harness.tests.sw_line import GreenLine as _Line  # noqa: E402


def observe(follower: str):
    """Seed a head on 77 bound for 101 and follower on 75 or 76."""
    ctc = StubCtcOffice()
    ready = (WaysideStatus("G1", "Green", True),)
    ctc.stage_inputs(CtcInputs(track_controller=TrackControllerInputs(
        waysides=ready)))
    ctc.dispatch("HEAD", "Green", "101")
    ctc.dispatch("FOLLOWER", "Green", "101")
    ctc.place_train("HEAD", "Green", "77")
    ctc.place_train("FOLLOWER", "Green", follower)
    out = ctc.step(0.1, CtcInputs(track_controller=TrackControllerInputs(
        occupancy=(BlockOccupancy("Green", "77", True),
                   BlockOccupancy("Green", follower, True)),
        switches=(SwitchReport("Green", "76", "reverse"),),
        waysides=ready)))
    suggestions = {s.block_id: s for s in
                   out.track_controller.suggestions}
    line = _Line()
    line.tick(occupied={"78"}, suggested={"78", "77"})
    before = line.tick(occupied={"77", follower}, suggested=suggestions)
    # Once the head clears to 101, the follower still occupies 76.
    after = [line.tick(occupied={"76", "101"}, suggested={"76", "77"})
             ["76"] for _ in range(5)]
    return suggestions, before["76"], after


# Observed 2026-10-28 with Harry Tye's Track-Ctrl-SW starter (e5e51d4):
# switch 76 stays reverse throughout. Once the head is in 101 the starter
# asks for normal (WANT_N_76 := OCC_76), but the vital lock reads the
# listed block 76, which the follower is on, so the switch cannot move.
# Landis, 2026-10-28: with the head in 101 and the follower on 76, reverse
# leaves the follower no authority, for good. This records the stall; it
# is not the intended behaviour. (With his development starter,
# 2026-10-27, it commanded normal.)


def test_green_follower_75_observation():
    suggestions, switch, after = observe("75")
    assert suggestions["75"].authority_blocks == 1
    assert suggestions["76"].authority_blocks == 0
    assert switch == "reverse"
    assert after == ["reverse"] * 5


def test_green_follower_76_observation():
    suggestions, switch, after = observe("76")
    assert suggestions["76"].authority_blocks == 0
    assert switch == "reverse"
    assert after == ["reverse"] * 5
