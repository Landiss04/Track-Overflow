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
    BlockOccupancy,
    BlockRef,
    CrossingReport,
    CtcInputs,
    CtcSnapshot,
    DispatchOrder,
    NewTrain,
    SwitchCommand,
    SwitchReport,
    TrackModelInputs,
    TrackControllerInputs,
    WaysideStatus,
)
from ctc.link import STANDALONE_DT_S as DT_S, LocalLink  # noqa: E402
from ctc.model import (  # noqa: E402
    SUGGESTED_SPEED_MARGIN_MPS,
    InvalidInputError,
    InvalidTimeStepError,
    MaintenanceModeRequiredError,
)
from ctc_ui.display import (  # noqa: E402
    TimeOfDayError,
    format_time_of_day,
    parse_time_of_day,
)
from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.test_harness import (  # noqa: E402
    MPS_TO_MPH,
    CtcTestHarness,
)
from tests.occupancy import own_block, ready_office, reports  # noqa: E402


def _green(tickets: int) -> TrackModelInputs:
    """Track Model inputs: tickets sold at Glenbury, a Green station."""
    return TrackModelInputs({"GLENBURY": tickets})


def _sold(snap: CtcSnapshot, station: str = "GLENBURY") -> int:
    """Tickets sold so far at one station."""
    return snap.tickets_sold[station]


_LAYOUT = load_layout()


def _suggested(line: str, block_id: str) -> int:
    """The suggested speed in a block: its limit in whole m/s, less the
    margin."""
    (limit,) = [b.speed_limit_kmh for b in _LAYOUT[line].blocks
                if b.block_id == block_id]
    return int(limit / 3.6) - SUGGESTED_SPEED_MARGIN_MPS


def _outputs(harness: CtcTestHarness) -> dict[str, object]:
    return {row["name"]: row["value"] for row in harness.outputs}


class StubModuleTest(unittest.TestCase):

    def test_dispatch_becomes_suggestion_and_authority(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "65", arrival_s=8 * 3600)
        # The CTC releases T1 from the yard (D022). Not on the track
        # yet (the yard is a black box): no suggestion.
        out = ctc.step(DT_S, reports())
        self.assertEqual(out.track_controller.suggestions, ())
        self.assertEqual(out.new_trains, (NewTrain("T1", "Green"),))
        # Green 63, the yard exit, becomes occupied: T1 has left the yard.
        out = ctc.step(DT_S, reports(occupied=[("Green", "63")]))
        self.assertEqual(out.new_trains, ())
        suggestion = own_block(out.track_controller.suggestions)
        # And one for the next block on its route, authority one less.
        self.assertEqual(
            [(s.block_id, s.authority_blocks)
             for s in out.track_controller.suggestions
             if s is not suggestion], [("64", 1)])
        # Two blocks ahead of 63 to the destination: 64 and 65. The
        # suggestion says where T1 is, for the Track Controller, which
        # sees only occupancy.
        self.assertEqual(
            (suggestion.train_id, suggestion.line, suggestion.block_id,
             suggestion.authority_blocks), ("T1", "Green", "63", 2))
        self.assertIs(type(suggestion.authority_blocks), int)
        # A little under Green 63's limit: whole m/s, less the margin.
        self.assertEqual(suggestion.suggested_speed_mps,
                         _suggested("Green", "63"))
        # A whole number of m/s, sent to the Track Controller as an int.
        self.assertIs(type(suggestion.suggested_speed_mps), int)
        self.assertEqual(ctc.snapshot().orders,
                         (DispatchOrder("T1", "Green", "65", 28800.0),))

    def test_dispatch_again_reroutes(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "65", arrival_s=8 * 3600)
        ctc.dispatch("T1", "Green", "73")
        (order,) = ctc.snapshot().orders
        self.assertEqual((order.destination_block_id, order.arrival_s),
                         ("73", None))

    def test_blocks_are_checked_against_the_layout(self) -> None:
        ctc = ready_office()
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
        ctc = ready_office()
        ctc.step(DT_S, reports())                  # a ready Track Controller
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Red", "12", True)
        ctc.set_block_closed("Green", "12", True)
        ctc.set_block_closed("Green", "2", True)
        ctc.set_block_closed("Green", "2", False)
        closed = ctc.snapshot().outputs.track_controller.closed_blocks
        self.assertEqual(closed, (BlockRef("Green", "12"),
                                  BlockRef("Red", "12")))

    def test_switches_only_in_maintenance_mode(self) -> None:
        ctc = ready_office()
        with self.assertRaises(MaintenanceModeRequiredError):
            ctc.set_switch("Green", "12", "reverse")
        ctc.set_maintenance_mode(True)
        ctc.set_switch("Green", "12", "reverse")
        ctc.set_switch("Red", "9", "normal")
        track = ctc.step(DT_S, reports()).track_controller
        self.assertTrue(ctc.snapshot().maintenance_mode)
        # The mode itself is not sent to the Track Controller.
        self.assertFalse(hasattr(track, "maintenance_mode"))
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
        ctc = ready_office()
        ctc.set_maintenance_mode(True)
        for line, switch_id, position in (
                ("Green", "13", "normal"),        # no switch on block 13
                ("Red", "12", "normal"),          # Green has 12, not Red
                ("Green", "12", "sideways")):
            with self.subTest(line=line, switch=switch_id):
                with self.assertRaises(InvalidInputError):
                    ctc.set_switch(line, switch_id,
                                   position)  # type: ignore[arg-type]

    def test_clock_speedup_output(self) -> None:
        ctc = ready_office()
        self.assertFalse(ctc.step(DT_S, CtcInputs()).clock_speedup)
        ctc.set_clock_speedup(True)
        self.assertTrue(ctc.step(DT_S, CtcInputs()).clock_speedup)
        ctc.set_clock_speedup(False)
        self.assertFalse(ctc.snapshot().outputs.clock_speedup)

    def test_clock_paused_output(self) -> None:
        # The simulation starts paused, until the dispatcher runs it.
        ctc = ready_office()
        self.assertTrue(ctc.snapshot().outputs.clock_paused)
        ctc.set_clock_paused(False)
        self.assertFalse(ctc.step(DT_S, CtcInputs()).clock_paused)
        # No step happens while paused: the snapshot says so at once.
        ctc.set_clock_paused(True)
        self.assertTrue(ctc.snapshot().outputs.clock_paused)
        with self.assertRaises(InvalidInputError):
            ctc.set_clock_paused("no")  # type: ignore[arg-type]

    def test_bad_dt_rejected(self) -> None:
        ctc = ready_office()
        for dt in (0.0, -0.1, math.inf, math.nan):
            with self.assertRaises(InvalidTimeStepError):
                ctc.step(dt, CtcInputs())

    def test_invalid_inputs_change_no_state(self) -> None:
        ctc = ready_office()
        ctc.step(DT_S, CtcInputs(track_model=_green(3)))
        before = ctc.snapshot()
        for bad_track in (
            TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "151", True),)),
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
        ctc = ready_office()
        for sold in (2, 3):
            ctc.step(DT_S, CtcInputs(track_model=_green(sold)))
        snap = ctc.snapshot()
        self.assertEqual(_sold(snap), 5)
        self.assertAlmostEqual(snap.elapsed_s, 2 * DT_S)

    def test_ticket_sales_total_per_station(self) -> None:
        # Each station reports its own sales since the last report; a
        # station that sold none is left out.
        ctc = ready_office()
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(
            {"DORMONT": 3, "SHADYSIDE": 1})))
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(
            {"SHADYSIDE": 5})))
        sold = ctc.snapshot().tickets_sold
        self.assertEqual((sold["DORMONT"], sold["SHADYSIDE"]), (3, 6))
        # Every named station has a total, zero until it sells.
        self.assertEqual(sold["GLENBURY"], 0)
        self.assertEqual(len(sold), 20)

    def test_bad_ticket_sales_rejected(self) -> None:
        ctc = ready_office()
        for sales in ({"NOWHERE": 1},       # no such station
                      {"dormont": 1},       # names are exact
                      {"DORMONT": -1},
                      {"DORMONT": 1.5},
                      {"DORMONT": True},
                      {7: 1},
                      [("DORMONT", 1)]):    # not a map
            with self.subTest(sales=sales):
                with self.assertRaises(InvalidInputError):
                    ctc.step(DT_S, CtcInputs(
                        track_model=TrackModelInputs(sales)))  # type: ignore

    def test_ticket_sales_are_copied(self) -> None:
        # A later change to the caller's dict changes nothing.
        ctc = ready_office()
        sales = {"DORMONT": 2}
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(sales)))
        sales["DORMONT"] = 99
        inputs = ctc.snapshot().inputs
        assert inputs is not None
        self.assertEqual(inputs.track_model.ticket_sales, {"DORMONT": 2})

    def test_bad_arrival_rejected(self) -> None:
        ctc = ready_office()
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
    (index,) = [len(r["entries"]) - 1 for r in harness.inputs
                if r["name"] == row]
    for key, value in fields.items():
        harness.setEntryField(row, index, key, value)


def _entries(harness: CtcTestHarness, row: str) -> list[dict[str, object]]:
    (found,) = [r["entries"] for r in harness.inputs if r["name"] == row]
    return found


class HarnessEntryTest(unittest.TestCase):
    """List rows are tables of entries picked from the track layout."""

    def test_only_track_controller_inputs(self) -> None:
        # Dispatcher actions are taken in the CTC window, and ticket
        # sales come from the Track Model: neither is forced here.
        harness = CtcTestHarness(LocalLink())
        rows = {r["name"]: r for r in harness.inputs}
        self.assertEqual(list(rows), ["waysides", "occupied_blocks",
                                      "switch_states", "crossing_states"])
        self.assertFalse(hasattr(harness, "dispatcherInputs"))
        # No wayside has reported at first, as at startup.
        self.assertEqual((rows["waysides"]["kind"],
                          rows["waysides"]["entries"]), ("list", []))
        self.assertEqual([f["key"] for f in rows["waysides"]["fields"]],
                         ["wayside", "line", "ready", "reason"])
        self.assertEqual(rows["occupied_blocks"]["kind"], "list")
        self.assertEqual(
            [f["key"] for f in rows["occupied_blocks"]["fields"]],
            ["line", "block"])
        self.assertEqual(rows["occupied_blocks"]["noun"], "block")
        greens = harness.layoutOptions["block"]["Green"]
        self.assertIn({"value": "2", "text": "2 · Pioneer"}, greens)
        self.assertEqual(harness.layoutOptions["switch"]["Green"][0],
                         {"value": "12", "text": "12 (12-13; 1-13)"})

    def test_new_entries_start_on_real_places(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "occupied_blocks")
        _add(harness, "switch_states")
        _add(harness, "crossing_states")
        self.assertEqual(_entries(harness, "occupied_blocks"),
                         [{"line": "Green", "block": "1"}])
        self.assertEqual(_entries(harness, "switch_states")[0]["switch"],
                         "12")
        self.assertEqual(_entries(harness, "crossing_states")[0]
                         ["crossing"], "19")

    def test_changing_line_repicks_from_that_line(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "switch_states", position="reverse")
        harness.setEntryField("switch_states", 0, "line", "Red")
        self.assertEqual(_entries(harness, "switch_states"),
                         [{"line": "Red", "switch": "9",
                           "position": "reverse"}])

    def test_remove_entry(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "occupied_blocks", block="5")
        _add(harness, "occupied_blocks", block="6")
        harness.removeEntry("occupied_blocks", 0)
        self.assertEqual(_entries(harness, "occupied_blocks"),
                         [{"line": "Green", "block": "6"}])

    def test_dropdown_edits_republish_rows(self) -> None:
        # Every field is a dropdown, drawn from its row: an edit must
        # re-publish the rows.
        harness = CtcTestHarness(LocalLink())
        _add(harness, "occupied_blocks")
        published: list[bool] = []
        harness.inputsChanged.connect(lambda: published.append(True))
        harness.setEntryField("occupied_blocks", 0, "block", "4")
        self.assertEqual(published, [True])

    def test_reset_clears_every_row(self) -> None:
        harness = CtcTestHarness(LocalLink())
        _add(harness, "waysides")
        _add(harness, "occupied_blocks")
        _add(harness, "crossing_states")
        harness.resetInputs()
        self.assertEqual([r["entries"] for r in harness.inputs],
                         [[], [], [], []])


class HarnessSendTest(unittest.TestCase):

    def test_waysides_are_sent(self) -> None:
        # A new wayside gets the next free ID; one not ready says why.
        link = LocalLink()
        harness = CtcTestHarness(link)
        _add(harness, "waysides")
        _add(harness, "waysides", ready="not ready",
             reason="no PLC program")
        harness.send()
        self.assertFalse(harness.statusIsError, harness.status)
        self.assertEqual(link.snapshot().inputs.track_controller.waysides, (
            WaysideStatus("W1", "Green", True),
            WaysideStatus("W2", "Green", False, "no PLC program")))

    def test_occupancy_is_sent(self) -> None:
        link = LocalLink()
        harness = CtcTestHarness(link)
        _add(harness, "occupied_blocks", line="Red", block="7")
        _add(harness, "occupied_blocks", block="5")
        harness.send()
        self.assertFalse(harness.statusIsError, harness.status)
        inputs = link.snapshot().inputs
        self.assertEqual([(o.line, o.block_id, o.occupied)
                          for o in inputs.track_controller.occupancy],
                         [("Red", "7", True), ("Green", "5", True)])
        self.assertEqual(dict(inputs.track_model.ticket_sales), {})

    def test_outputs_show_what_the_window_did(self) -> None:
        # Dispatching, closing blocks, setting switches and the clock
        # speed happen in the CTC window; the test UI reads the outputs.
        link = LocalLink()
        # A train can be dispatched only on a line that is ready.
        link.set_inputs(reports())
        link.dispatch("T1", "Green", "65", 8 * 3600)
        link.set_inputs(reports(ready=False))
        link.set_maintenance_mode(True)
        link.set_block_closed("Green", "5", True)
        link.set_switch("Green", "12", "reverse")
        link.set_clock_speedup(True)
        harness = CtcTestHarness(link)
        # The Track Controller is not ready: nothing is sent to it.
        rows = _outputs(harness)
        self.assertEqual((rows["closed_blocks"], rows["switch_commands"]),
                         ("", ""))
        _add(harness, "waysides")       # W1, Green, ready
        harness.send()
        self.assertEqual(link.snapshot().inputs.track_controller.waysides,
                         (WaysideStatus("W1", "Green", True),))
        rows = _outputs(harness)
        # Still in the yard: no speed or authority yet.
        self.assertNotIn("authority[T1]", rows)
        self.assertEqual(rows["closed_blocks"], "Green:5")
        self.assertEqual(rows["switch_commands"], "Green:12=reverse")
        self.assertTrue(rows["clock_speedup"])
        self.assertTrue(rows["clock_paused"])
        self.assertFalse([name for name in rows
                          if name.startswith("tickets_sold")])

        # T1 leaves the yard into Green 63, two blocks from 65.
        _add(harness, "occupied_blocks", block="63")
        harness.send()
        rows = _outputs(harness)
        self.assertEqual(rows["block[T1]"], "Green:63")
        self.assertEqual(rows["authority[T1]"], 2)
        self.assertAlmostEqual(rows["suggested_speed[T1]"],
                               round(_suggested("Green", "63")
                                     * MPS_TO_MPH, 1))
        # Sending the Track Controller inputs changes no dispatcher
        # state.
        snap = link.snapshot()
        self.assertEqual([o.train_id for o in snap.orders], ["T1"])
        self.assertTrue(snap.maintenance_mode)

    def test_unknown_block_is_reported_and_not_stepped(self) -> None:
        # The table only offers real blocks; the module still checks.
        link = LocalLink()
        harness = CtcTestHarness(link)
        _add(harness, "occupied_blocks", line="Red")
        harness.setEntryField("occupied_blocks", 0, "block", "150")
        harness.send()
        self.assertTrue(harness.statusIsError)
        self.assertIn("150", harness.status)
        self.assertEqual(link.snapshot().elapsed_s, 0.0)


if __name__ == "__main__":
    unittest.main()
