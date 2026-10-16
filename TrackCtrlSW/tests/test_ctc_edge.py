"""Tests for the harness edge from the CTC Office to this module.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v

The edge imports both modules' boundary types, which only the harness
may. It needs no Qt.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "CTC-Office"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.harness.ctc_edges import ctc_to_track_controller  # noqa: E402
from ctc.interface import (  # noqa: E402
    BlockRef,
    SwitchCommand,
    TrackControllerOutputs,
    TrainSuggestion,
)
from track_ctrl.interface import BlockKey, Suggestion  # noqa: E402
from track_ctrl.module import SwTrackController  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rig import default_module  # noqa: E402


class CtcEdge(unittest.TestCase):
    def test_a_train_suggestion_becomes_its_blocks_suggestion(self) -> None:
        mapped = ctc_to_track_controller(TrackControllerOutputs(
            suggestions=(
                TrainSuggestion(
                    train_id="T1", line="Green", block_id="63",
                    suggested_speed_mps=18, authority_blocks=2),
            ),
        ))
        self.assertEqual(
            mapped.suggestions, {BlockKey("Green", "63"): Suggestion(18, 2)})

    def test_the_train_id_stops_at_the_edge(self) -> None:
        mapped = ctc_to_track_controller(TrackControllerOutputs(
            suggestions=(
                TrainSuggestion("T1", "Green", "63", 18, 2),
                TrainSuggestion("T2", "Red", "63", 10, 5),
            ),
        ))
        # Same block number on two lines: two blocks, not one.
        self.assertEqual(len(mapped.suggestions), 2)
        self.assertNotIn("T1", repr(mapped))

    def test_two_suggestions_for_one_block_take_the_more_restrictive(
        self,
    ) -> None:
        mapped = ctc_to_track_controller(TrackControllerOutputs(
            suggestions=(
                TrainSuggestion("T1", "Green", "5", 18, 1),
                TrainSuggestion("T2", "Green", "5", 9, 4),
            ),
        ))
        self.assertEqual(
            mapped.suggestions, {BlockKey("Green", "5"): Suggestion(9, 1)})

    def test_closed_blocks_and_switch_commands_carry_over(self) -> None:
        mapped = ctc_to_track_controller(TrackControllerOutputs(
            closed_blocks=(BlockRef("Green", "7"),),
            switch_commands=(SwitchCommand("Green", "12", "reverse"),),
        ))
        self.assertEqual(mapped.closed_blocks, {BlockKey("Green", "7")})
        self.assertEqual(
            mapped.switch_commands, {BlockKey("Green", "12"): "reverse"})

    def test_nothing_sent_maps_to_nothing(self) -> None:
        mapped = ctc_to_track_controller(TrackControllerOutputs())
        self.assertEqual(mapped.suggestions, {})
        self.assertEqual(mapped.closed_blocks, frozenset())
        self.assertEqual(mapped.switch_commands, {})

    def test_the_mapped_suggestion_reaches_the_blocks_circuit(self) -> None:
        from track_ctrl.interface import TrackControllerInputs

        module: SwTrackController = default_module()
        mapped = ctc_to_track_controller(TrackControllerOutputs(
            suggestions=(TrainSuggestion("T1", "Green", "8", 9, 2),),
        ))
        out = module.step(0.1, TrackControllerInputs(time_s=1.0, ctc=mapped))
        circuit = out.track_model.track_circuits[BlockKey("Green", "8")]
        self.assertEqual(
            (circuit.speed_mps, circuit.authority_blocks), (9, 2))
        # Only the block the train is in gets a circuit.
        self.assertEqual(list(out.track_model.track_circuits),
                         [BlockKey("Green", "8")])


if __name__ == "__main__":
    unittest.main()
