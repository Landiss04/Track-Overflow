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
    TrackControllerOutputs,
)
from ctc.model import (  # noqa: E402
    InvalidInputError,
    InvalidTimeStepError,
    MaintenanceModeRequiredError,
    StubCtcOffice,
    UnsafeActionError,
)
from ctc.schedule import parse_schedule  # noqa: E402
from ctc.track_layout import load_layout  # noqa: E402
from ctc.wire import WireFormatError, inputs_from_wire  # noqa: E402
from tests.occupancy import DT_S, at, reports, step_at  # noqa: E402

_GREEN = load_layout()["Green"]


def _maintenance() -> StubCtcOffice:
    """A CTC in maintenance mode, with a ready Track Controller."""
    ctc = StubCtcOffice()
    step_at(ctc)
    ctc.set_maintenance_mode(True)
    return ctc


class AuthoritySafetyTest(unittest.TestCase):
    """No authority into a closed, closing or failed block, or onto
    another line than the train's own. A failed block is one the CTC
    infers from occupancy, and the UIs never show it as one: an order
    into it is taken and kept, and the train waits short of it."""

    def test_no_authority_into_a_closed_block(self) -> None:
        ctc = _maintenance()
        ctc.set_block_closed("Green", "65", True)
        with self.assertRaisesRegex(UnsafeActionError, "closed"):
            ctc.dispatch("T1", "Green", "65")
        self.assertEqual(ctc.snapshot().orders, ())

    def test_an_order_into_an_inferred_failure_is_kept(self) -> None:
        # Green 73 occupied with no train in it: a failure.
        ctc = StubCtcOffice()
        step_at(ctc, occupied=[("Green", "73")])
        ctc.dispatch("T1", "Green", "73")
        step_at(ctc, at("T1", "70"), occupied=[("Green", "73")])
        snap = ctc.snapshot()
        self.assertEqual([o.train_id for o in snap.orders], ["T1"])
        self.assertEqual(snap.cancelled_orders, ())
        (limit,) = snap.authorities
        self.assertEqual((limit.blocks, limit.reason, limit.at),
                         (2, "occupied", "73"))
        # It clears: the train may go on in.
        step_at(ctc, at("T1", "70"))
        self.assertEqual(ctc.snapshot().authorities[0].blocks, 3)

    def test_no_authority_onto_another_line(self) -> None:
        ctc = StubCtcOffice()
        step_at(ctc, at("T5", "62"))
        with self.assertRaisesRegex(UnsafeActionError, "Green line"):
            ctc.dispatch("T5", "Red", "7")
        ctc.dispatch("T5", "Green", "65")
        # A train not on the track yet may go to either line.
        ctc.dispatch("T9", "Red", "7")


class TrackControllerReadyTest(unittest.TestCase):
    """The waysides are vital: the CTC sends the Track Controller nothing
    until it reports ready (a PLC program on every wayside)."""

    def _set_up(self) -> StubCtcOffice:
        # T1 out of the yard on Green 63 toward 65; a closure and a
        # switch command made in maintenance mode.
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "65")
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "5", True)
        ctc.set_switch("Green", "12", "reverse")
        ctc.place_train("T1", "Green", "63")
        return ctc

    def test_nothing_is_sent_until_ready(self) -> None:
        ctc = self._set_up()
        for not_ready in (CtcInputs(), reports(at("T1", "63"),
                                               ready=False)):
            with self.subTest(inputs=not_ready):
                out = ctc.step(DT_S, not_ready)
                self.assertEqual(out.track_controller,
                                 TrackControllerOutputs())
                # Kept, and shown: only not sent.
                snap = ctc.snapshot()
                self.assertEqual(snap.closed_blocks,
                                 (BlockRef("Green", "5"),))
                self.assertEqual(len(snap.switch_commands), 1)
                (limit,) = snap.authorities
                self.assertEqual((limit.blocks, limit.reason),
                                 (0, "not ready"))
        # Ready: everything goes out.
        track = ctc.step(DT_S, reports(at("T1", "63"))).track_controller
        (suggestion,) = track.suggestions
        self.assertEqual((suggestion.block_id, suggestion.authority_blocks),
                         ("63", 2))
        self.assertEqual(track.closed_blocks, (BlockRef("Green", "5"),))
        self.assertEqual(len(track.switch_commands), 1)
        # Ready lost (a new line loaded, say): nothing again.
        out = ctc.step(DT_S, reports(at("T1", "63"), ready=False))
        self.assertEqual(out.track_controller, TrackControllerOutputs())

    def test_no_train_moves_while_not_ready(self) -> None:
        # With no authority sent, 64 becoming occupied is not T1.
        ctc = self._set_up()
        for _ in range(30):
            ctc.step(1.0, reports(at("T1", "63"), ready=False))
        ctc.step(1.0, reports(at("T1", "63"), occupied=[("Green", "64")],
                              ready=False))
        self.assertEqual([t.blocks for t in ctc.snapshot().trains],
                         [("63",)])

    def test_ready_must_be_true_or_false(self) -> None:
        for ready in ("true", 1, None):
            with self.subTest(ready=ready), \
                    self.assertRaises(InvalidInputError):
                StubCtcOffice().step(DT_S, CtcInputs(
                    track_controller=TrackControllerInputs(
                        ready=ready)))  # type: ignore[arg-type]
        # Over the wire too: a string is not a boolean.
        with self.assertRaises(InvalidInputError):
            StubCtcOffice().step(DT_S, inputs_from_wire(
                {"track_controller": {"ready": "true"}}))


class SuggestedSpeedTest(unittest.TestCase):
    """Suggested speed stays under the current block's speed limit."""

    def test_a_little_under_the_current_block_limit(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "65")
        # Green 117 is limited to 15 km/h (4.2 m/s): suggest 3 m/s.
        out = step_at(ctc, at("T1", "117"))
        self.assertEqual(out.track_controller.suggestions[0]
                         .suggested_speed_mps, 3)

    def test_never_above_any_block_limit(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "65")
        for block in range(1, 151):
            out = step_at(ctc, at("T1", str(block)))
            (suggestion,) = out.track_controller.suggestions
            limit_mps = [b.speed_limit_kmh for b in
                         _GREEN.blocks if b.block_id == str(block)][0] / 3.6
            with self.subTest(block=block):
                self.assertLess(suggestion.suggested_speed_mps, limit_mps)

    def test_no_suggestion_before_the_train_is_on_the_track(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T9", "Green", "65")
        self.assertEqual(ctc.step(DT_S, CtcInputs())
                         .track_controller.suggestions, ())
        self.assertEqual([o.train_id for o in ctc.snapshot().orders],
                         ["T9"])


class SwitchSafetyTest(unittest.TestCase):

    def test_no_switch_under_a_train(self) -> None:
        # A train the CTC follows, or occupancy it cannot explain.
        for trains, occupied in (((at("T1", "12"),), ()),
                                 ((), (("Green", "12"),))):
            with self.subTest(trains=trains):
                ctc = _maintenance()
                step_at(ctc, *trains, occupied=occupied)
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

    def test_listed_until_reopened_even_out_of_maintenance(self) -> None:
        # The list is what locks the Track Controller out of a block:
        # leaving maintenance mode keeps it, reopening clears it.
        ctc = _maintenance()
        ctc.set_block_closed("Green", "5", True)
        ctc.set_block_closed("Red", "2", True)
        ctc.set_maintenance_mode(False)
        out = step_at(ctc)
        self.assertEqual(out.track_controller.closed_blocks,
                         (BlockRef("Green", "5"), BlockRef("Red", "2")))
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "5", False)
        out = step_at(ctc)
        self.assertEqual(out.track_controller.closed_blocks,
                         (BlockRef("Red", "2"),))

    def test_occupied_block_closes_once_the_train_leaves(self) -> None:
        ctc = _maintenance()
        step_at(ctc, at("T1", "65"))
        ctc.dispatch("T2", "Green", "65")
        ctc.set_block_closed("Green", "65", True)
        snap = ctc.snapshot()
        # Pending: not closed yet, orders into it cancelled at once, and
        # already listed for the Track Controller, which may not
        # override it from now on.
        self.assertEqual(snap.outputs.track_controller.closed_blocks,
                         (BlockRef("Green", "65"),))
        self.assertEqual(snap.pending_closures, (BlockRef("Green", "65"),))
        self.assertEqual(snap.cancelled_orders[0].reason, "block closing")
        with self.assertRaisesRegex(UnsafeActionError, "closing"):
            ctc.dispatch("T3", "Green", "65")
        # Leaving maintenance keeps the pending closure.
        ctc.set_maintenance_mode(False)
        step_at(ctc, at("T1", "65"))
        self.assertEqual(ctc.snapshot().pending_closures,
                         (BlockRef("Green", "65"),))
        step_at(ctc, at("T1", "66"))
        snap = ctc.snapshot()
        self.assertEqual(snap.pending_closures, ())
        self.assertEqual(snap.outputs.track_controller.closed_blocks,
                         (BlockRef("Green", "65"),))

    def test_reopen_cancels_a_pending_closure(self) -> None:
        ctc = _maintenance()
        step_at(ctc, at("T1", "65"))
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
            "occupancy flag": TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "5", "no"),)),
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

    def test_train_ids_are_trimmed(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch(" T1 ", "Green", "65")
        ctc.dispatch("T1", "Green", "73")
        self.assertEqual([(o.train_id, o.destination_block_id)
                          for o in ctc.snapshot().orders], [("T1", "73")])
        ctc.place_train(" T2", "Green", "62")
        self.assertEqual(ctc.snapshot().trains[0].train_id, "T2")
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
        self.assertTrue(snap.maintenance_mode)

    def test_wrongly_shaped_inputs_are_a_clear_error(self) -> None:
        for bad in ([], {"track_controller": []},
                    {"track_controller": {"occupancy": {"x": 1}}},
                    {"track_controller": {"occupancy": [5]}}):
            with self.subTest(bad=bad), self.assertRaises(WireFormatError):
                inputs_from_wire(bad)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
