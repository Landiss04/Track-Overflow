"""Tests for the CTC Office's safety rules and input checks.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.actions import apply_action  # noqa: E402
from ctc.interface import (  # noqa: E402
    BlockOccupancy,
    BlockRef,
    CancelledOrder,
    CrossingReport,
    CtcInputs,
    SwitchReport,
    TrackControllerInputs,
    TrackFailureReport,
    TrainReport,
)
from ctc.link import LocalLink  # noqa: E402
from ctc.model import (  # noqa: E402
    InvalidInputError,
    InvalidTimeStepError,
    MaintenanceModeRequiredError,
    StubCtcOffice,
    UnsafeActionError,
)
from ctc.schedule import parse_schedule  # noqa: E402
from ctc.wire import WireFormatError, inputs_from_wire  # noqa: E402
from ctc_ui.test_harness import CtcTestHarness  # noqa: E402

DT_S = 0.1


def _report(*trains: TrainReport, occupancy=(), failures=()) -> CtcInputs:
    return CtcInputs(track_controller=TrackControllerInputs(
        trains=trains, occupancy=occupancy, failures=failures))


def _maintenance() -> StubCtcOffice:
    ctc = StubCtcOffice()
    ctc.set_maintenance_mode(True)
    return ctc


class AuthoritySafetyTest(unittest.TestCase):
    """No authority into a closed, closing or failed block, or onto
    another line than the train's own."""

    def test_no_authority_into_a_closed_block(self) -> None:
        ctc = _maintenance()
        ctc.set_block_closed("Green", "65", True)
        with self.assertRaisesRegex(UnsafeActionError, "closed"):
            ctc.dispatch("T1", "Green", "65")
        self.assertEqual(ctc.snapshot().orders, ())

    def test_no_authority_into_a_failed_block(self) -> None:
        ctc = StubCtcOffice()
        ctc.step(DT_S, _report(failures=(
            TrackFailureReport("Green", "73", "broken_rail"),)))
        with self.assertRaisesRegex(UnsafeActionError, "broken rail"):
            ctc.dispatch("T1", "Green", "73")

    def test_staged_failure_blocks_dispatch_but_cancels_nothing_yet(
            self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "73")
        ctc.stage_inputs(_report(failures=(
            TrackFailureReport("Green", "73", "power"),)))
        # Safety checks use the staged report at once...
        with self.assertRaises(UnsafeActionError):
            ctc.dispatch("T2", "Green", "73")
        # ...but nothing propagates until the next step.
        self.assertEqual([o.train_id for o in ctc.snapshot().orders],
                         ["T1"])
        ctc.step(DT_S, _report(failures=(
            TrackFailureReport("Green", "73", "power"),)))
        snap = ctc.snapshot()
        self.assertEqual(snap.orders, ())
        self.assertEqual(snap.cancelled_orders, (CancelledOrder(
            "T1", "Green", "73", "track failure: power"),))

    def test_no_authority_onto_another_line(self) -> None:
        ctc = StubCtcOffice()
        ctc.step(DT_S, _report(TrainReport("T5", "Green", "62", 0, 0)))
        with self.assertRaisesRegex(UnsafeActionError, "Green line"):
            ctc.dispatch("T5", "Red", "7")
        ctc.dispatch("T5", "Green", "65")
        # A train not reported anywhere yet may go to either line.
        ctc.dispatch("T9", "Red", "7")


class SwitchSafetyTest(unittest.TestCase):

    def test_no_switch_under_a_train(self) -> None:
        for occupied in (
                _report(TrainReport("T1", "Green", "12", 0, 0)),
                _report(occupancy=(BlockOccupancy("Green", "12", True),))):
            with self.subTest(occupied=occupied):
                ctc = _maintenance()
                ctc.step(DT_S, occupied)
                with self.assertRaisesRegex(UnsafeActionError, "occupied"):
                    ctc.set_switch("Green", "12", "reverse")
                ctc.step(DT_S, CtcInputs())          # the train left
                ctc.set_switch("Green", "12", "reverse")


class ClosureTest(unittest.TestCase):
    """Closures are maintenance-only and wait for a train to leave."""

    def test_close_and_reopen_need_maintenance_mode(self) -> None:
        ctc = StubCtcOffice()
        for closed in (True, False):
            with self.assertRaises(MaintenanceModeRequiredError):
                ctc.set_block_closed("Green", "5", closed)

    def test_closing_a_clear_block_cancels_orders_into_it(self) -> None:
        ctc = _maintenance()
        ctc.dispatch("T1", "Green", "65")
        ctc.set_block_closed("Green", "65", True)
        snap = ctc.snapshot()
        self.assertEqual(snap.outputs.track_controller.closed_blocks,
                         (BlockRef("Green", "65"),))
        self.assertEqual(snap.cancelled_orders, (CancelledOrder(
            "T1", "Green", "65", "block closed"),))

    def test_occupied_block_closes_once_the_train_leaves(self) -> None:
        ctc = _maintenance()
        ctc.step(DT_S, _report(TrainReport("T1", "Green", "65", 0, 0)))
        ctc.dispatch("T2", "Green", "65")
        ctc.set_block_closed("Green", "65", True)
        snap = ctc.snapshot()
        # Pending: not closed yet, orders into it cancelled at once.
        self.assertEqual(snap.outputs.track_controller.closed_blocks, ())
        self.assertEqual(snap.pending_closures, (BlockRef("Green", "65"),))
        self.assertEqual(snap.cancelled_orders[0].reason, "block closing")
        with self.assertRaisesRegex(UnsafeActionError, "closing"):
            ctc.dispatch("T3", "Green", "65")
        # Leaving maintenance keeps the pending closure.
        ctc.set_maintenance_mode(False)
        ctc.step(DT_S, _report(TrainReport("T1", "Green", "65", 50, 0)))
        self.assertEqual(ctc.snapshot().pending_closures,
                         (BlockRef("Green", "65"),))
        ctc.step(DT_S, _report(TrainReport("T1", "Green", "66", 0, 0)))
        snap = ctc.snapshot()
        self.assertEqual(snap.pending_closures, ())
        self.assertEqual(snap.outputs.track_controller.closed_blocks,
                         (BlockRef("Green", "65"),))

    def test_reopen_cancels_a_pending_closure(self) -> None:
        ctc = _maintenance()
        ctc.step(DT_S, _report(TrainReport("T1", "Green", "65", 0, 0)))
        ctc.set_block_closed("Green", "65", True)
        ctc.set_block_closed("Green", "65", False)
        ctc.step(DT_S, CtcInputs())
        snap = ctc.snapshot()
        self.assertEqual(snap.pending_closures, ())
        self.assertEqual(snap.outputs.track_controller.closed_blocks, ())


class InputCheckTest(unittest.TestCase):
    """Every reported value is checked, not just its block."""

    def test_bad_values_rejected(self) -> None:
        cases = {
            "switch position": TrackControllerInputs(
                switches=(SwitchReport("Green", "12", "sideways"),)),
            "crossing state": TrackControllerInputs(
                crossings=(CrossingReport("Green", "19", "blinking"),)),
            "failure kind": TrackControllerInputs(
                failures=(TrackFailureReport("Green", "5", "gremlins"),)),
            "occupancy flag": TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "5", "no"),)),
            "negative offset": TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "3", -1.0, 0),)),
            "offset past the block": TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "3", 100.5, 0),)),
            "negative speed": TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "3", 0, -2.2),)),
            "contradictory switch": TrackControllerInputs(switches=(
                SwitchReport("Green", "12", "normal"),
                SwitchReport("Green", "12", "reverse"))),
            "contradictory occupancy": TrackControllerInputs(occupancy=(
                BlockOccupancy("Green", "5", True),
                BlockOccupancy("Green", "5", False))),
        }
        for label, track in cases.items():
            with self.subTest(label), self.assertRaises(InvalidInputError):
                StubCtcOffice().step(DT_S,
                                     CtcInputs(track_controller=track))

    def test_repeated_identical_reports_are_fine(self) -> None:
        StubCtcOffice().step(DT_S, CtcInputs(
            track_controller=TrackControllerInputs(
                switches=(SwitchReport("Green", "12", "normal"),
                          SwitchReport("Green", "12", "normal")),
                occupancy=(BlockOccupancy("Green", "5", True),
                           BlockOccupancy("Green", "5", True)))))

    def test_offset_at_the_block_end_is_fine(self) -> None:
        # Green 3 is 100 m long.
        StubCtcOffice().step(DT_S, _report(
            TrainReport("T1", "Green", "3", 100.0, 0)))

    def test_train_ids_are_trimmed(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch(" T1 ", "Green", "65")
        ctc.dispatch("T1", "Green", "73")
        self.assertEqual([(o.train_id, o.destination_block_id)
                          for o in ctc.snapshot().orders], [("T1", "73")])
        ctc.step(DT_S, _report(TrainReport(" T2", "Green", "62", 0, 0)))
        self.assertEqual(
            ctc.snapshot().inputs.track_controller.trains[0].train_id, "T2")
        ctc.cancel_dispatch(" T1")
        self.assertEqual(ctc.snapshot().orders, ())

    def test_dt_must_be_a_real_number(self) -> None:
        for dt in (True, "0.1"):
            with self.subTest(dt=dt), self.assertRaises(InvalidTimeStepError):
                StubCtcOffice().step(dt, CtcInputs())  # type: ignore

    def test_schedule_stops_must_be_on_the_layout(self) -> None:
        def schedule(line: str, block: str):
            return parse_schedule({"time_unit": "s", "lines": [
                {"line": line, "trains": [{"train_id": "1", "stops": [
                    {"block_id": block, "arrival_s": 0}]}]}]})
        for line, block in (("Green", "999"), ("Blue", "1")):
            with self.subTest(line=line), self.assertRaises(
                    InvalidInputError):
                StubCtcOffice().load_schedule(schedule(line, block))
        StubCtcOffice().load_schedule(schedule("Green", "65"))


class StrictActionTest(unittest.TestCase):
    """Actions sent over a link take real booleans only."""

    def test_string_false_is_not_true(self) -> None:
        ctc = _maintenance()
        for op, args in (
                ("set_block_closed", {"line": "Green", "block_id": "3",
                                      "closed": "false"}),
                ("set_maintenance_mode", {"active": "false"}),
                ("set_clock_speedup", {"active": 0})):
            with self.subTest(op=op), self.assertRaises(InvalidInputError):
                apply_action(ctc, op, args)
        snap = ctc.snapshot()
        self.assertEqual(snap.outputs.track_controller.closed_blocks, ())
        self.assertTrue(snap.outputs.track_controller.maintenance_mode)

    def test_wrongly_shaped_inputs_are_a_clear_error(self) -> None:
        for bad in ([], {"track_controller": []},
                    {"track_controller": {"trains": {"x": 1}}},
                    {"track_controller": {"trains": [5]}}):
            with self.subTest(bad=bad), self.assertRaises(WireFormatError):
                inputs_from_wire(bad)  # type: ignore[arg-type]


class AtomicSendTest(unittest.TestCase):
    """A test UI Send is applied all or nothing."""

    @staticmethod
    def _add(harness: CtcTestHarness, row: str, **fields: object) -> None:
        harness.addEntry(row)
        (index,) = [len(r["entries"]) - 1
                    for r in harness.inputs + harness.dispatcherInputs
                    if r["name"] == row]
        for key, value in fields.items():
            harness.setEntryField(row, index, key, value)

    def test_rejected_part_rejects_the_whole_send(self) -> None:
        cases = {
            "two trains in one block": lambda h: (
                self._add(h, "train_reports", block="12"),
                self._add(h, "train_reports", block="12")),
            "switch outside maintenance": lambda h: self._add(
                h, "switch_commands", position="reverse"),
        }
        for label, make_bad in cases.items():
            with self.subTest(label):
                link = LocalLink()
                harness = CtcTestHarness(link)
                self._add(harness, "dispatch_orders", block="65")
                make_bad(harness)
                before = link.snapshot()
                harness.send()
                self.assertTrue(harness.statusIsError)
                self.assertEqual(link.snapshot(), before)

    def test_inputs_apply_before_actions(self) -> None:
        # A failure reported in the same Send already blocks an order
        # into that block.
        link = LocalLink()
        harness = CtcTestHarness(link)
        self._add(harness, "track_failures", block="65")
        self._add(harness, "dispatch_orders", block="65")
        harness.send()
        self.assertIn("track failure", harness.status)
        self.assertEqual(link.snapshot().orders, ())


if __name__ == "__main__":
    unittest.main()
