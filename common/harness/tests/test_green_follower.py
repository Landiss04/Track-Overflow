"""The Green follower at 75/76 (CTC-3), across the CTC and the SW starter.

This seeds owner-boundary snapshots, rather than relocating a live train
in the physics loop. It reuses the SW starter tick helper (``sw_line``);
no launcher or production routing rule is duplicated.
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


READY = (WaysideStatus("G1", "Green", True),)


def office():
    """A head on 77 bound for 101 and a follower on 75."""
    ctc = StubCtcOffice()
    ctc.stage_inputs(CtcInputs(track_controller=TrackControllerInputs(
        waysides=READY)))
    ctc.dispatch("HEAD", "Green", "101")
    ctc.dispatch("FOLLOWER", "Green", "101")
    ctc.place_train("HEAD", "Green", "77")
    ctc.place_train("FOLLOWER", "Green", "75")
    return ctc


def authorities(ctc, occupied, switch_76):
    """One CTC step; the authority suggested on each block."""
    out = ctc.step(0.1, CtcInputs(track_controller=TrackControllerInputs(
        occupancy=tuple(BlockOccupancy("Green", b, True)
                        for b in sorted(occupied)),
        switches=(SwitchReport("Green", "76", switch_76),),
        waysides=READY)))
    return {s.block_id: s.authority_blocks
            for s in out.track_controller.suggestions}


# CTC-3, as Landis and Harry Tye agreed on 2026-10-28: a switch's blocks
# are next to each other whatever position it reports, so the CTC keeps
# the follower on 75 while the head is on 77. It never reaches 76, where
# the vital lock on the listed block would hold switch 76 reverse under
# it. Once the head is in 101 the starter sets the switch normal (no
# train wants reverse) and the follower runs on.


def test_green_follower_waits_on_75_then_runs():
    ctc = office()
    line = _Line()
    line.tick(occupied={"78"}, suggested={"78", "77"})
    # Head on 77: it may run into 101; the follower may not move.
    first = authorities(ctc, {"77", "75"}, "reverse")
    assert first["77"] == 1
    assert first["75"] == 0
    assert line.tick(occupied={"77", "75"}, suggested={"77"})["76"] \
        == "reverse"
    # Head in 101: the starter sets the switch normal at once.
    after = [line.tick(occupied={"101", "75"}, suggested={"101"})["76"]
             for _ in range(5)]
    assert after == ["normal"] * 5
    # Reported normal, the follower's authority runs to 85.
    assert authorities(ctc, {"101", "75"}, "normal")["75"] == 10
