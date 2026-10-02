"""Tests for the CTC Office boundary, stub module and test harness.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import (  # noqa: E402
    CtcInputs,
    TrackModelInputs,
    TrainReport,
    TrackControllerInputs,
)
from ctc.link import LocalLink  # noqa: E402
from ctc.model import (  # noqa: E402
    STUB_SUGGESTED_SPEED_MPS,
    InvalidInputError,
    InvalidTimeStepError,
    StubCtcOffice,
)
from ctc_ui.test_harness import (  # noqa: E402
    DT_S,
    M_TO_FT,
    MPS_TO_MPH,
    CtcTestHarness,
    HarnessInputError,
    build_inputs,
    parse_train_reports,
)


def _values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "occupied_blocks": "", "train_reports": "", "switch_states": "",
        "crossing_states": "", "track_failures": "", "ticket_sales": 0,
    }
    values.update(overrides)
    return values


class StubModuleTest(unittest.TestCase):

    def test_dispatch_becomes_suggestion_and_authority(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "A9")
        out = ctc.step(DT_S, CtcInputs())
        (suggestion,) = out.track_controller.suggestions
        self.assertEqual(suggestion.train_id, "T1")
        self.assertEqual(suggestion.authority_block_id, "A9")
        self.assertEqual(suggestion.suggested_speed_mps,
                         STUB_SUGGESTED_SPEED_MPS)

    def test_cancel_closed_blocks_and_maintenance(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "A9")
        ctc.cancel_dispatch("T1")
        ctc.set_block_closed("B2", True)
        ctc.set_block_closed("A1", True)
        ctc.set_block_closed("A1", False)
        ctc.set_maintenance_mode(True)
        out = ctc.step(DT_S, CtcInputs()).track_controller
        self.assertEqual(out.suggestions, ())
        self.assertEqual(out.closed_block_ids, ("B2",))
        self.assertTrue(out.maintenance_mode)

    def test_bad_dt_rejected(self) -> None:
        ctc = StubCtcOffice()
        for dt in (0.0, -0.1, math.inf, math.nan):
            with self.assertRaises(InvalidTimeStepError):
                ctc.step(dt, CtcInputs())

    def test_invalid_inputs_change_no_state(self) -> None:
        ctc = StubCtcOffice()
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(3)))
        before = ctc.snapshot()
        bad = CtcInputs(
            track_controller=TrackControllerInputs(
                trains=(TrainReport("T1", "A1", math.nan, 1.0),)),
            track_model=TrackModelInputs(5),
        )
        with self.assertRaises(InvalidInputError):
            ctc.step(DT_S, bad)
        self.assertEqual(ctc.snapshot(), before)

    def test_tickets_accumulate(self) -> None:
        ctc = StubCtcOffice()
        for sold in (2, 3):
            ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(sold)))
        snap = ctc.snapshot()
        self.assertEqual(snap.tickets_sold_total, 5)
        self.assertAlmostEqual(snap.elapsed_s, 2 * DT_S)

    def test_empty_ids_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            StubCtcOffice().dispatch(" ", "A1")


class HarnessParsingTest(unittest.TestCase):

    def test_train_reports_convert_display_units_to_si(self) -> None:
        (report,) = parse_train_reports("T1:A3:328.084:22.36936")
        self.assertEqual((report.train_id, report.block_id), ("T1", "A3"))
        self.assertAlmostEqual(report.offset_m, 328.084 / M_TO_FT)
        self.assertAlmostEqual(report.speed_mps, 22.36936 / MPS_TO_MPH)

    def test_build_inputs(self) -> None:
        inputs = build_inputs(_values(
            occupied_blocks="A1, A2",
            switch_states="SW1=reverse",
            crossing_states="X1=active",
            track_failures="A5=broken_rail",
            ticket_sales=4,
        ))
        track = inputs.track_controller
        self.assertEqual(
            [b.block_id for b in track.occupancy], ["A1", "A2"])
        self.assertEqual(track.switches[0].position, "reverse")
        self.assertEqual(track.crossings[0].state, "active")
        self.assertEqual(track.failures[0].kind, "broken_rail")
        self.assertEqual(inputs.track_model.ticket_sales, 4)

    def test_malformed_rows_rejected(self) -> None:
        for row, text in (
            ("switch_states", "SW1=sideways"),
            ("train_reports", "T1:A1:ten:5"),
            ("train_reports", "T1:A1:inf:5"),
            ("track_failures", "A5"),
        ):
            with self.subTest(row=row), self.assertRaises(HarnessInputError):
                build_inputs(_values(**{row: text}))


class HarnessSendTest(unittest.TestCase):

    def test_send_applies_dispatcher_and_reads_outputs(self) -> None:
        harness = CtcTestHarness(LocalLink())
        harness.setInput("dispatch_orders", "T1=A9; T2=B3")
        harness.setInput("closed_blocks", "C1")
        harness.setInput("maintenance_mode", True)
        harness.setInput("ticket_sales", 7)
        harness.send()
        self.assertFalse(harness.statusIsError, harness.status)
        rows = {row["name"]: row["value"] for row in harness.outputs}
        self.assertEqual(rows["authority[T1]"], "A9")
        self.assertEqual(rows["authority[T2]"], "B3")
        self.assertAlmostEqual(rows["suggested_speed[T1]"],
                               round(STUB_SUGGESTED_SPEED_MPS
                                     * MPS_TO_MPH, 1))
        self.assertEqual(rows["closed_blocks"], "C1")
        self.assertTrue(rows["maintenance_mode"])
        self.assertEqual(rows["tickets_sold_total"], 7)

        # Removing an order on the next Send cancels it.
        harness.setInput("dispatch_orders", "T2=B3")
        harness.send()
        names = {row["name"] for row in harness.outputs}
        self.assertNotIn("authority[T1]", names)
        self.assertIn("authority[T2]", names)

    def test_toggle_edit_republishes_rows(self) -> None:
        # A toggle draws itself from its row, so a bool edit must
        # re-publish the rows, keeping earlier text drafts.
        harness = CtcTestHarness(LocalLink())
        published: list[bool] = []
        harness.inputsChanged.connect(lambda: published.append(True))
        harness.setInput("dispatch_orders", "T1=A9")
        self.assertEqual(published, [])    # text edits keep focus
        harness.setInput("maintenance_mode", True)
        self.assertEqual(published, [True])
        rows = {r["name"]: r["value"] for r in harness.dispatcherInputs}
        self.assertIs(rows["maintenance_mode"], True)
        self.assertEqual(rows["dispatch_orders"], "T1=A9")

    def test_parse_error_reports_and_does_not_step(self) -> None:
        harness = CtcTestHarness(LocalLink())
        harness.setInput("switch_states", "SW1=sideways")
        harness.setInput("dispatch_orders", "T1=A9")
        harness.send()
        self.assertTrue(harness.statusIsError)
        self.assertIn("switch_states", harness.status)
        names = {row["name"] for row in harness.outputs}
        self.assertNotIn("authority[T1]", names)


if __name__ == "__main__":
    unittest.main()
