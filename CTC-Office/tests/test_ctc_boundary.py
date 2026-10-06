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

from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402

from ctc.interface import (  # noqa: E402
    BlockRef,
    CrossingReport,
    CtcInputs,
    CtcSnapshot,
    DispatchOrder,
    SwitchCommand,
    SwitchReport,
    TicketSales,
    TrackModelInputs,
    TrainReport,
    TrackControllerInputs,
)
from ctc.link import STANDALONE_DT_S as DT_S, LocalLink  # noqa: E402
from ctc.model import (  # noqa: E402
    SUGGESTED_SPEED_MARGIN_MPS,
    InvalidInputError,
    InvalidTimeStepError,
    MaintenanceModeRequiredError,
    StubCtcOffice,
)
from ctc_ui.display import (  # noqa: E402
    TimeOfDayError,
    format_time_of_day,
    parse_time_of_day,
)
from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.test_harness import (  # noqa: E402
    M_TO_FT,
    MPS_TO_MPH,
    CtcTestHarness,
)


def _green(tickets: int) -> TrackModelInputs:
    """Track Model inputs with Green line ticket sales."""
    return TrackModelInputs((TicketSales("Green", tickets),))


def _sold(snap: CtcSnapshot, line: str = "Green") -> int:
    """Tickets sold so far on one line."""
    return {t.line: t.tickets for t in snap.tickets_sold}[line]


_LAYOUT = load_layout()


def _suggested(line: str, block_id: str) -> int:
    """The suggested speed in a block: its limit in whole m/s, less the
    margin."""
    (limit,) = [b.speed_limit_kmh for b in _LAYOUT[line].blocks
                if b.block_id == block_id]
    return int(limit / 3.6) - SUGGESTED_SPEED_MARGIN_MPS


def _values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "occupied_blocks": "", "train_reports": "", "switch_states": "",
        "crossing_states": "", "track_failures": "", "ticket_sales": 0,
    }
    values.update(overrides)
    return values


def _outputs(harness: CtcTestHarness) -> dict[str, object]:
    return {row["name"]: row["value"] for row in harness.outputs}


class StubModuleTest(unittest.TestCase):

    def test_dispatch_becomes_suggestion_and_authority(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "65", arrival_s=8 * 3600)
        # Not on the track yet (the yard is a black box): no suggestion.
        out = ctc.step(DT_S, CtcInputs())
        self.assertEqual(out.track_controller.suggestions, ())
        out = ctc.step(DT_S, CtcInputs(
            track_controller=TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "62", 0.0, 0.0),))))
        (suggestion,) = out.track_controller.suggestions
        self.assertEqual(
            (suggestion.train_id, suggestion.line,
             suggestion.authority_block_id), ("T1", "Green", "65"))
        # A little under Green 62's limit: whole m/s, less the margin.
        self.assertEqual(suggestion.suggested_speed_mps,
                         _suggested("Green", "62"))
        # A whole number of m/s, sent to the Track Controller as an int.
        self.assertIs(type(suggestion.suggested_speed_mps), int)
        self.assertEqual(ctc.snapshot().orders,
                         (DispatchOrder("T1", "Green", "65", 28800.0),))

    def test_dispatch_again_reroutes(self) -> None:
        ctc = StubCtcOffice()
        ctc.dispatch("T1", "Green", "65", arrival_s=8 * 3600)
        ctc.dispatch("T1", "Green", "73")
        (order,) = ctc.snapshot().orders
        self.assertEqual((order.destination_block_id, order.arrival_s),
                         ("73", None))

    def test_blocks_are_checked_against_the_layout(self) -> None:
        ctc = StubCtcOffice()
        ctc.set_maintenance_mode(True)
        # Red has 76 blocks, Green 150: the same number, different lines.
        ctc.set_block_closed("Green", "150", True)
        for line, block in (("Red", "150"), ("Blue", "1"), ("Green", "")):
            with self.subTest(line=line, block=block):
                with self.assertRaises(InvalidInputError):
                    ctc.set_block_closed(line, block, True)
                with self.assertRaises(InvalidInputError):
                    ctc.dispatch("T1", line, block)

    def test_closed_blocks_carry_their_line(self) -> None:
        ctc = StubCtcOffice()
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Red", "12", True)
        ctc.set_block_closed("Green", "12", True)
        ctc.set_block_closed("Green", "2", True)
        ctc.set_block_closed("Green", "2", False)
        closed = ctc.snapshot().outputs.track_controller.closed_blocks
        self.assertEqual(closed, (BlockRef("Green", "12"),
                                  BlockRef("Red", "12")))

    def test_switches_only_in_maintenance_mode(self) -> None:
        ctc = StubCtcOffice()
        with self.assertRaises(MaintenanceModeRequiredError):
            ctc.set_switch("Green", "12", "reverse")
        ctc.set_maintenance_mode(True)
        ctc.set_switch("Green", "12", "reverse")
        ctc.set_switch("Red", "9", "normal")
        track = ctc.step(DT_S, CtcInputs()).track_controller
        self.assertTrue(track.maintenance_mode)
        self.assertEqual(track.switch_commands, (
            SwitchCommand("Green", "12", "reverse"),
            SwitchCommand("Red", "9", "normal")))
        ctc.release_switch("Red", "9")
        self.assertEqual(len(ctc.snapshot().outputs.track_controller
                             .switch_commands), 1)
        # Leaving maintenance mode hands every switch back.
        ctc.set_maintenance_mode(False)
        self.assertEqual(
            ctc.snapshot().outputs.track_controller.switch_commands, ())

    def test_bad_switch_commands_rejected(self) -> None:
        ctc = StubCtcOffice()
        ctc.set_maintenance_mode(True)
        for line, switch_id, position in (
                ("Green", "13", "normal"),        # no switch on block 13
                ("Red", "12", "normal"),          # Green has 12, not Red
                ("Green", "12", "sideways")):
            with self.subTest(line=line, switch=switch_id):
                with self.assertRaises(InvalidInputError):
                    ctc.set_switch(line, switch_id,
                                   position)  # type: ignore[arg-type]

    def test_two_trains_cannot_share_a_block(self) -> None:
        # Safety: trains must not collide, so the report is rejected and
        # nothing is applied.
        ctc = StubCtcOffice()
        before = ctc.snapshot()
        same_block = CtcInputs(track_controller=TrackControllerInputs(
            trains=(TrainReport("T1", "Green", "12", 0.0, 0.0),
                    TrainReport("T2", "Green", "12", 40.0, 5.0))))
        with self.assertRaisesRegex(InvalidInputError,
                                    "T1 and T2 .* Green block 12"):
            ctc.step(DT_S, same_block)
        self.assertEqual(ctc.snapshot(), before)
        twice = CtcInputs(track_controller=TrackControllerInputs(
            trains=(TrainReport("T1", "Green", "12", 0.0, 0.0),
                    TrainReport("T1", "Green", "13", 0.0, 0.0))))
        with self.assertRaisesRegex(InvalidInputError, "reported twice"):
            ctc.validate_inputs(twice)
        # The same block number on the other line is a different block.
        ctc.step(DT_S, CtcInputs(track_controller=TrackControllerInputs(
            trains=(TrainReport("T1", "Green", "12", 0.0, 0.0),
                    TrainReport("T2", "Red", "12", 0.0, 0.0)))))

    def test_clock_speedup_output(self) -> None:
        ctc = StubCtcOffice()
        self.assertFalse(ctc.step(DT_S, CtcInputs()).clock_speedup)
        ctc.set_clock_speedup(True)
        self.assertTrue(ctc.step(DT_S, CtcInputs()).clock_speedup)
        ctc.set_clock_speedup(False)
        self.assertFalse(ctc.snapshot().outputs.clock_speedup)

    def test_bad_dt_rejected(self) -> None:
        ctc = StubCtcOffice()
        for dt in (0.0, -0.1, math.inf, math.nan):
            with self.assertRaises(InvalidTimeStepError):
                ctc.step(dt, CtcInputs())

    def test_invalid_inputs_change_no_state(self) -> None:
        ctc = StubCtcOffice()
        ctc.step(DT_S, CtcInputs(track_model=_green(3)))
        before = ctc.snapshot()
        for bad_track in (
            TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "1", math.nan, 1.0),)),
            TrackControllerInputs(
                switches=(SwitchReport("Green", "13", "normal"),)),
            TrackControllerInputs(
                crossings=(CrossingReport("Red", "19", "active"),)),
        ):
            bad = CtcInputs(track_controller=bad_track,
                            track_model=_green(5))
            with self.subTest(bad=bad_track):
                with self.assertRaises(InvalidInputError):
                    ctc.step(DT_S, bad)
                with self.assertRaises(InvalidInputError):
                    ctc.validate_inputs(bad)
                self.assertEqual(ctc.snapshot(), before)

    def test_tickets_accumulate(self) -> None:
        ctc = StubCtcOffice()
        for sold in (2, 3):
            ctc.step(DT_S, CtcInputs(track_model=_green(sold)))
        snap = ctc.snapshot()
        self.assertEqual(_sold(snap), 5)
        self.assertAlmostEqual(snap.elapsed_s, 2 * DT_S)

    def test_ticket_sales_total_per_line(self) -> None:
        ctc = StubCtcOffice()
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs((
            TicketSales("Green", 3), TicketSales("Red", 1)))))
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs((
            TicketSales("Red", 5),))))
        self.assertEqual(ctc.snapshot().tickets_sold, (
            TicketSales("Green", 3), TicketSales("Red", 6)))

    def test_bad_ticket_sales_rejected(self) -> None:
        ctc = StubCtcOffice()
        for sales in ((TicketSales("Blue", 1),),
                      (TicketSales("Red", -1),),
                      (TicketSales("Red", 1.5),),         # type: ignore
                      (TicketSales("Red", 1), TicketSales("Red", 2))):
            with self.subTest(sales=sales):
                with self.assertRaises(InvalidInputError):
                    ctc.step(DT_S, CtcInputs(
                        track_model=TrackModelInputs(sales)))

    def test_bad_arrival_rejected(self) -> None:
        ctc = StubCtcOffice()
        for arrival in (-1.0, 86400.0, math.nan):
            with self.subTest(arrival=arrival):
                with self.assertRaises(InvalidInputError):
                    ctc.dispatch("T1", "Green", "65", arrival)
        with self.assertRaises(InvalidInputError):
            ctc.dispatch(" ", "Green", "65")


class TimeOfDayTest(unittest.TestCase):

    def test_round_trip(self) -> None:
        self.assertEqual(parse_time_of_day("08:30"), 30600.0)
        self.assertEqual(parse_time_of_day("23:59:59"), 86399.0)
        self.assertEqual(format_time_of_day(30600), "08:30")
        self.assertEqual(format_time_of_day(30605), "08:30:05")

    def test_rejects_non_times(self) -> None:
        for text in ("8.30", "24:00", "12:60", "noon", ""):
            with self.subTest(text=text), self.assertRaises(TimeOfDayError):
                parse_time_of_day(text)


def _add(harness: CtcTestHarness, row: str, **fields: object) -> None:
    """Add an entry to a list row and set some of its fields, as the
    test UI's table does."""
    harness.addEntry(row)
    (index,) = [len(r["entries"]) - 1
                for r in harness.inputs + harness.dispatcherInputs
                if r["name"] == row]
    for key, value in fields.items():
        harness.setEntryField(row, index, key, value)


def _entries(harness: CtcTestHarness, row: str) -> list[dict[str, object]]:
    (found,) = [r["entries"] for r in
                harness.inputs + harness.dispatcherInputs
                if r["name"] == row]
    return found


class HarnessEntryTest(unittest.TestCase):
    """List rows are tables of entries picked from the track layout."""

    def test_rows_carry_their_columns(self) -> None:
        harness = CtcTestHarness(LocalLink())
        rows = {r["name"]: r for r in harness.inputs}
        self.assertEqual(rows["occupied_blocks"]["kind"], "list")
        self.assertEqual([f["key"] for f in rows["train_reports"]["fields"]],
                         ["train", "line", "block", "offset_ft",
                          "speed_mph"])
        self.assertEqual(rows["occupied_blocks"]["noun"], "block")
        self.assertEqual(rows["ticket_sales"]["kind"], "int")
        greens = harness.layoutOptions["block"]["Green"]
        self.assertIn({"value": "2", "text": "2 · Pioneer"}, greens)
        self.assertEqual(harness.layoutOptions["switch"]["Green"][0],
                         {"value": "12", "text": "12 (12-13; 1-13)"})

    def test_new_entries_start_on_real_places(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "occupied_blocks")
        _add(harness, "switch_states")
        _add(harness, "crossing_states")
        _add(harness, "train_reports")
        _add(harness, "train_reports")
        self.assertEqual(_entries(harness, "occupied_blocks"),
                         [{"line": "Green", "block": "1"}])
        self.assertEqual(_entries(harness, "switch_states")[0]["switch"],
                         "12")
        self.assertEqual(_entries(harness, "crossing_states")[0]
                         ["crossing"], "19")
        self.assertEqual([e["train"] for e in
                          _entries(harness, "train_reports")],
                         ["T1", "T2"])

    def test_changing_line_repicks_from_that_line(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "switch_states", position="reverse")
        harness.setEntryField("switch_states", 0, "line", "Red")
        self.assertEqual(_entries(harness, "switch_states"),
                         [{"line": "Red", "switch": "9",
                           "position": "reverse"}])

    def test_remove_entry(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "closed_blocks", block="5")
        _add(harness, "closed_blocks", block="6")
        harness.removeEntry("closed_blocks", 0)
        self.assertEqual(_entries(harness, "closed_blocks"),
                         [{"line": "Green", "block": "6"}])

    def test_inputs_are_sent_in_si(self) -> None:
        link = LocalLink()
        harness = CtcTestHarness(link)
        _add(harness, "train_reports", block="3", offset_ft=328.084,
             speed_mph=22.36936)
        _add(harness, "occupied_blocks", line="Red", block="7")
        _add(harness, "track_failures", block="5", kind="power")
        harness.send()
        self.assertFalse(harness.statusIsError, harness.status)
        track = link.snapshot().inputs.track_controller
        (train,) = track.trains
        self.assertEqual((train.train_id, train.line, train.block_id),
                         ("T1", "Green", "3"))
        self.assertAlmostEqual(train.offset_m, 328.084 / M_TO_FT)
        self.assertAlmostEqual(train.speed_mps, 22.36936 / MPS_TO_MPH)
        self.assertEqual((track.occupancy[0].line,
                          track.occupancy[0].block_id), ("Red", "7"))
        self.assertEqual(track.failures[0].kind, "power")

    def test_bad_entries_are_reported(self) -> None:
        for row, fields, message in (
                ("train_reports", {"train": " "}, "enter a train ID"),
                ("train_reports", {"speed_mph": "fast"}, "not a number"),
                ("dispatch_orders", {"arrival": "8.30"}, "not a time")):
            with self.subTest(row=row, fields=fields):
                harness = CtcTestHarness(LocalLink())
                _add(harness, row, **fields)
                harness.send()
                self.assertTrue(harness.statusIsError)
                self.assertIn(message, harness.status)
                self.assertIn(f"{row} entry 1", harness.status)

    def test_typed_edits_keep_focus(self) -> None:
        # Typed fields are not re-published (the editor would lose focus);
        # dropdowns and the list of entries are.
        harness = CtcTestHarness(LocalLink())
        _add(harness, "train_reports")
        published: list[bool] = []
        harness.inputsChanged.connect(lambda: published.append(True))
        harness.setEntryField("train_reports", 0, "speed_mph", 12.0)
        harness.setEntryField("train_reports", 0, "train", "T7")
        self.assertEqual(published, [])
        harness.setEntryField("train_reports", 0, "block", "4")
        self.assertEqual(published, [True])
        self.assertEqual(_entries(harness, "train_reports")[0]["train"],
                         "T7")


class HarnessSendTest(unittest.TestCase):

    def test_send_applies_dispatcher_and_reads_outputs(self) -> None:
        harness = CtcTestHarness(LocalLink())
        # Both trains on the track, so they get speed and authority.
        _add(harness, "train_reports", train="T1", block="62")
        _add(harness, "train_reports", train="T2", line="Red", block="40")
        _add(harness, "dispatch_orders", block="65")
        _add(harness, "dispatch_orders", line="Red", block="7",
             arrival="09:15")
        _add(harness, "closed_blocks", block="5")
        # Maintenance mode and a switch in the same Send: maintenance
        # mode is applied first, so the switch is accepted.
        harness.setInput("maintenance_mode", True)
        _add(harness, "switch_commands", position="reverse")
        harness.setInput("clock_speedup", True)
        harness.setInput("ticket_sales", 7)
        harness.setInputChoice("ticket_sales", "Red")
        harness.send()
        self.assertFalse(harness.statusIsError, harness.status)
        rows = _outputs(harness)
        self.assertEqual(rows["authority[T1]"], "Green:65")
        self.assertEqual(rows["authority[T2]"], "Red:7")
        self.assertAlmostEqual(rows["suggested_speed[T1]"],
                               round(_suggested("Green", "62")
                                     * MPS_TO_MPH, 1))
        self.assertEqual(rows["closed_blocks"], "Green:5")
        self.assertEqual(rows["switch_commands"], "Green:12=reverse")
        self.assertTrue(rows["maintenance_mode"])
        self.assertTrue(rows["clock_speedup"])
        self.assertEqual(rows["tickets_sold[Red]"], 7)
        self.assertEqual(rows["tickets_sold[Green]"], 0)

        # Removing an order on the next Send cancels it.
        harness.removeEntry("dispatch_orders", 0)
        harness.send()
        names = {row["name"] for row in harness.outputs}
        self.assertNotIn("authority[T1]", names)
        self.assertIn("authority[T2]", names)

    def test_switch_outside_maintenance_is_an_error(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "switch_commands", position="reverse")
        harness.send()
        self.assertTrue(harness.statusIsError)
        self.assertIn("maintenance", harness.status)

    def test_unedited_rows_mirror_the_module(self) -> None:
        # Changes made elsewhere (the CTC window) show up in the
        # dispatcher rows, unless the row was edited and not yet sent.
        link = LocalLink()
        harness = CtcTestHarness(link)
        _add(harness, "dispatch_orders", train="T9", block="2")
        link.set_maintenance_mode(True)
        link.set_block_closed("Red", "3", True)
        link.dispatch("T1", "Green", "65", 30600.0)
        harness.send()
        self.assertEqual(_entries(harness, "closed_blocks"),
                         [{"line": "Red", "block": "3"}])
        # The edited orders row won: T1 was cancelled by the Send.
        self.assertEqual(_entries(harness, "dispatch_orders"),
                         [{"train": "T9", "line": "Green", "block": "2",
                           "arrival": ""}])
        link.dispatch("T1", "Green", "65", 30600.0)
        harness._refresh()
        self.assertIn({"train": "T1", "line": "Green", "block": "65",
                       "arrival": "08:30"},
                      _entries(harness, "dispatch_orders"))

    def test_toggle_edit_republishes_rows(self) -> None:
        # A toggle draws itself from its row, so a bool edit must
        # re-publish the rows.
        harness = CtcTestHarness(LocalLink())
        published: list[bool] = []
        harness.inputsChanged.connect(lambda: published.append(True))
        harness.setInput("maintenance_mode", True)
        self.assertEqual(published, [True])
        rows = {r["name"]: r for r in harness.dispatcherInputs}
        self.assertIs(rows["maintenance_mode"]["value"], True)

    def test_error_does_not_step(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "dispatch_orders", block="65")
        _add(harness, "train_reports", speed_mph="fast")
        harness.send()
        self.assertTrue(harness.statusIsError)
        names = {row["name"] for row in harness.outputs}
        self.assertNotIn("authority[T1]", names)

    def test_numbers_from_qml_are_accepted(self) -> None:
        # QML has one number type: an int row's 10 arrives as 10.0. It
        # used to fail "ticket_sales must be a whole number >= 0".
        QCoreApplication.instance() or QCoreApplication([])
        harness = CtcTestHarness(LocalLink())
        engine = QQmlEngine()
        engine.rootContext().setContextProperty("harness", harness)
        component = QQmlComponent(engine)
        component.setData(b'''import QtQml
QtObject { Component.onCompleted: {
    harness.setInput("ticket_sales",
                     Number.fromLocaleString(Qt.locale("C"), "10"));
    harness.addEntry("train_reports");
    harness.setEntryField("train_reports", 0, "speed_mph",
                          Number.fromLocaleString(Qt.locale("C"), "25"));
    harness.send();
} }''', QUrl())
        self.assertIsNotNone(component.create(), component.errorString())
        self.assertFalse(harness.statusIsError, harness.status)
        self.assertEqual(_outputs(harness)["tickets_sold[Green]"], 10)
        # A fraction is still rejected.
        harness.setInput("ticket_sales", 2.5)
        harness.send()
        self.assertIn("whole number", harness.status)

    def test_two_trains_in_one_block_is_refused(self) -> None:
        link = LocalLink()
        harness = CtcTestHarness(link)
        _add(harness, "train_reports", block="12")
        _add(harness, "train_reports", block="12")
        harness.send()
        self.assertTrue(harness.statusIsError)
        self.assertIn("cannot occupy one block", harness.status)
        self.assertIsNone(link.snapshot().inputs)      # nothing applied

    def test_unknown_block_is_reported(self) -> None:
        # The table only offers real blocks; the module still checks.
        harness = CtcTestHarness(LocalLink())
        _add(harness, "occupied_blocks", line="Red")
        harness.setEntryField("occupied_blocks", 0, "block", "150")
        harness.send()
        self.assertTrue(harness.statusIsError)
        self.assertIn("150", harness.status)


if __name__ == "__main__":
    unittest.main()
