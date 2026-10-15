"""Tests for the CTC window's host of the CTC module.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from ctc.interface import (  # noqa: E402
    BlockOccupancy,
    CrossingReport,
    CtcInputs,
    CtcSnapshot,
    SwitchReport,
    TrackControllerInputs,
    TrackModelInputs,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
from ctc_ui.display import MPS_TO_MPH  # noqa: E402
from ctc_ui.sim_clock import SimulationClockBridge  # noqa: E402
from tests.occupancy import At, at, place, reports  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])


def _green(tickets: int) -> TrackModelInputs:
    """Track Model inputs: tickets sold at Glenbury, a Green station."""
    return TrackModelInputs({"GLENBURY": tickets})


def _sold(snap: CtcSnapshot, station: str = "GLENBURY") -> int:
    """Tickets sold so far at one station."""
    return snap.tickets_sold[station]


def _report(host: CtcHost, module: StubCtcOffice, *trains: At,
            **others) -> None:
    """Have the module follow ``trains`` where they are, and hand the
    window the Track Controller's report of them (occupancy only)."""
    place(module, *trains)
    host._receive_inputs(reports(*trains, **others))


def _host() -> tuple[CtcHost, StubCtcOffice, SimulationClockBridge]:
    module = StubCtcOffice()
    host = CtcHost(module)
    clock = SimulationClockBridge()
    host.follow_clock(clock)
    return host, module, clock


class ClockSpeedupTest(unittest.TestCase):
    """The window's clock speed is the module's clock_speedup output."""

    def test_clock_speed_drives_clock_speedup(self) -> None:
        host, module, clock = _host()
        changes: list[bool] = []
        host.clockSpeedupChanged.connect(
            lambda: changes.append(host.clockSpeedup))
        self.assertFalse(module.snapshot().outputs.clock_speedup)

        clock.setSpeed(10)
        self.assertTrue(module.snapshot().outputs.clock_speedup)
        # Pausing re-announces the speed; it is not a change.
        clock.pause()
        clock.setSpeed(1)
        self.assertFalse(module.snapshot().outputs.clock_speedup)
        self.assertEqual(changes[-1], False)
        self.assertIn(True, changes)


class TickTest(unittest.TestCase):
    """The clock steps the module with the latest inputs."""

    def test_inputs_wait_for_a_tick_and_tickets_count_once(self) -> None:
        host, module, clock = _host()
        inputs = CtcInputs(
            track_controller=TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "3", True),)),
            track_model=_green(4))
        host._receive_inputs(inputs)
        # Paused: the update is staged. The window keeps showing the last
        # applied reports, with a notice, until the clock runs.
        self.assertEqual(host.mapTrains, [])
        self.assertIsNone(module.snapshot().inputs)
        self.assertTrue(module.snapshot().inputs_staged)
        self.assertIn("staged", " ".join(host.notices))

        for _ in range(3):
            clock.clock.tick()
        self.assertEqual(host.mapTrains, [
            {"train": "", "line": "Green", "block": "3", "fraction": 0.5}])
        self.assertEqual(host.notices, [])
        snap = module.snapshot()
        self.assertEqual(_sold(snap), 4)
        self.assertAlmostEqual(snap.elapsed_s, 0.3)
        self.assertEqual(
            snap.inputs.track_controller.occupancy[0].block_id, "3")


class PanelDataTest(unittest.TestCase):
    """What the panels read, and what their actions do."""

    def test_block_states_never_show_a_failure(self) -> None:
        host, module, clock = _host()
        host.setMaintenanceMode(True)
        # Green 1 and 2 occupied with no train in them: the module
        # infers failures, which the window shows only as occupied.
        _report(host, module, occupied=[("Green", "1"), ("Green", "2")],
                crossings=[CrossingReport("Green", "19", "active")])
        clock.clock.tick()
        # Green 1 is occupied, so its closure waits; Green 5 is clear.
        self.assertEqual(host.closeBlock("Green", "1"), "")
        self.assertEqual(host.closeBlock("Green", "5"), "")
        # Occupancy is drawn as trains, not a block state.
        self.assertEqual(host.blockStates, {"Green:5": "closed"})
        self.assertEqual(host.crossingStates, {"Green:19": "active"})
        self.assertEqual(
            [(r["block"], r["state"]) for r in host.closures],
            [("Green 1", "Closing \u2014 train in block"),
             ("Green 5", "Closed")])
        self.assertEqual(
            [(t["train"], t["block"]) for t in host.mapTrains],
            [("", "1"), ("", "2")])

    def test_map_trains(self) -> None:
        host, module, clock = _host()
        place(module, at("T1", "3"))
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "3", True),
                           BlockOccupancy("Red", "8", True),
                           BlockOccupancy("Red", "9", False)))))
        clock.clock.tick()
        self.assertEqual(host.mapTrains, [
            # Where in its block is not known: drawn at the middle.
            {"train": "T1", "line": "Green", "block": "3",
             "fraction": 0.5},
            # Occupied with no train in it: an unnamed train.
            {"train": "", "line": "Red", "block": "8", "fraction": 0.5}])

    def test_a_train_crossing_into_the_next_block(self) -> None:
        # Green 3 runs to 2. Once T1 has had time to cross 3, 2 becoming
        # occupied is T1, which then holds both until 3 clears.
        host, module, clock = _host()
        host.dispatchTrain("T1", "Green", "1", "")
        _report(host, module, at("T1", "3"))
        for _ in range(200):                # 20 s
            clock.clock.tick()
        host._receive_inputs(reports(occupied=[("Green", "3"),
                                               ("Green", "2")]))
        clock.clock.tick()
        self.assertEqual(host.trainDetail("T1")["block"], "3\u21922")
        self.assertEqual(
            [(t["train"], t["block"]) for t in host.mapTrains],
            [("T1", "2")])
        host._receive_inputs(reports(occupied=[("Green", "2")]))
        clock.clock.tick()
        self.assertEqual(host.trainDetail("T1")["block"], "2")

    def test_actions_return_errors_as_text(self) -> None:
        host, module, _ = _host()
        self.assertIn("maintenance", host.setSwitch("Green", "12", 1))
        host.setMaintenanceMode(True)
        self.assertEqual(host.setSwitch("Green", "12", 1), "")
        self.assertEqual(host.switchDetail("Green", "12"), {
            "normal": "12-13", "reverse": "1-13",
            "reported": "—", "commanded": "reverse"})
        self.assertIn("08:30", host.dispatchTrain("T1", "Green", "65",
                                                  "8.30"))
        self.assertIn("has no block", host.closeBlock("Red", "150"))
        self.assertEqual(host.dispatchTrain("T1", "Green", "65", "08:30"),
                         "")
        self.assertEqual(module.snapshot().orders[0].arrival_s, 30600.0)

    def test_trains_merge_tracking_and_orders(self) -> None:
        host, module, clock = _host()
        _report(host, module, at("T1", "9"))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "65", "08:30")
        host.dispatchTrain("T2", "Red", "7", "")
        rows = {row["train"]: row for row in host.trains}
        self.assertEqual(rows["T1"]["block"], "9")
        # Its actual speed is never known; what the CTC suggests is.
        self.assertNotIn("speed", rows["T1"])
        (suggestion,) = module.snapshot().outputs.track_controller \
            .suggestions
        self.assertEqual(rows["T1"]["suggestedSpeed"],
                         f"{suggestion.suggested_speed_mps * MPS_TO_MPH:.1f}")
        self.assertEqual((rows["T1"]["status"], rows["T2"]["status"]),
                         ("En route", "In yard"))
        self.assertEqual(rows["T1"]["destination"], "Glenbury (65)")
        self.assertEqual(rows["T1"]["eta"], "08:30")
        # Green 9 toward 65 runs down to 1, then through switch 12 (1 to
        # 13), which nothing has reported set: authority ends at 1.
        self.assertEqual(rows["T1"]["authority"], "8 (to 1)")
        self.assertEqual(rows["T1"]["authorityBlocks"], "8")
        self.assertEqual(rows["T1"]["authorityEnd"], "Block 1")
        self.assertEqual(rows["T1"]["authorityLimit"], "Switch 12 not set")
        self.assertEqual(rows["T2"]["block"], "—")
        self.assertEqual(rows["T2"]["authority"], "—")
        self.assertEqual(
            [o["value"] for o in host.trainOptions("Green")], ["T1", "T3"])

    def test_selected_train_route(self) -> None:
        # T1 on Green 30 toward 37, T2 standing on 32: authority 1.
        host, module, clock = _host()
        _report(host, module, at("T1", "30"), at("T2", "32"))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "37", "")
        states = host.routeStates("T1")
        self.assertEqual(states["Green:31"], "authority")
        self.assertEqual(states["Green:32"], "beyond")
        self.assertEqual(states["Green:37"], "beyond")
        self.assertNotIn("Green:30", states)      # its own block
        detail = host.routeDetail("T1")
        self.assertEqual(detail["chips"], [
            {"block": "30", "occupancy": "occupied"},
            {"block": "31", "occupancy": "free"},
            {"block": "32", "occupancy": "occupied"}])
        self.assertEqual(detail["summary"], "Authority ends at block 31; "
                         "6 more to its destination, block 37.")
        # No order, no route.
        self.assertEqual(host.routeStates("T2"), {})
        self.assertEqual(host.routeDetail("T2")["chips"], [])

    def test_long_authority_chips_are_capped(self) -> None:
        host, module, clock = _host()
        _report(host, module, at("T1", "63"))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "75", "")
        chips = host.routeDetail("T1")["chips"]
        # Own block, eight within authority, then the other four.
        self.assertEqual(len(chips), 10)
        self.assertEqual(chips[-1], {"more": 4})
        self.assertEqual(host.routeDetail("T1")["summary"],
                         "Authority runs to its destination, block 75.")

    def test_authority_held_by_another_train(self) -> None:
        # T1 and T2 face each other on Green F, both bound for 24.
        host, module, clock = _host()
        _report(host, module, at("T1", "20"), at("T2", "28"))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "24", "")
        host.dispatchTrain("T2", "Green", "24", "")
        self.assertEqual(host.trainDetail("T2")["authorityLimit"],
                         "Block 24 held by T1")

    def test_reversal_alerts(self) -> None:
        # T5 on Red 28 cannot move (29 failed); T4 behind it wants 31,
        # which only reversing would reach.
        host, module, clock = _host()
        trains = (at("T4", "20", "Red"), at("T5", "28", "Red"))
        switches = [SwitchReport("Red", "27", "normal")]
        failed = reports(*trains, occupied=[("Red", "29")],
                         switches=switches)
        _report(host, module, *trains, occupied=[("Red", "29")],
                switches=switches)
        host.dispatchTrain("T4", "Red", "31", "")
        host.dispatchTrain("T5", "Red", "45", "")
        clock.clock.tick()
        clock.clock.tick()
        alerts = {a["train"]: a for a in host.reversalAlerts}
        self.assertEqual(alerts["T4"], {
            "train": "T4", "line": "Red", "reverseAt": "33",
            "destination": "31",
            "blockedBy": "T5 is standing in block 28 and is not moving"})
        # The failure shows only as an occupied block.
        self.assertEqual(alerts["T5"]["blockedBy"], "block 29 is occupied")
        self.assertIn("reversing at block 33",
                      host.routeDetail("T4")["summary"])
        # Dismissed: gone until the situation clears and comes back.
        host.dismissReversal("T4")
        self.assertEqual([a["train"] for a in host.reversalAlerts], ["T5"])
        host._receive_inputs(reports(*trains, switches=switches))
        clock.clock.tick()
        clock.clock.tick()
        self.assertEqual(host.reversalAlerts, [])
        # Too soon for T5 to have got there: a failure again.
        host._receive_inputs(failed)
        clock.clock.tick()
        clock.clock.tick()
        self.assertIn("T4", [a["train"] for a in host.reversalAlerts])

    def test_closing_a_closed_block_says_so(self) -> None:
        host, module, clock = _host()
        module.set_maintenance_mode(True)
        self.assertEqual(host.closureState("Green", "5"), "")
        self.assertEqual(host.closeBlock("Green", "5"), "")
        self.assertEqual(host.closureState("Green", "5"), "closed")
        self.assertEqual(host.closeBlock("Green", "5"),
                         "Green 5 is already closed.")
        # A block with a train in it is closing until the train leaves.
        _report(host, module, at("T1", "9"))
        clock.clock.tick()
        self.assertEqual(host.closeBlock("Green", "9"), "")
        self.assertEqual(host.closureState("Green", "9"), "closing")
        self.assertEqual(host.closeBlock("Green", "9"),
                         "Green 9 is already closing.")

    def test_authority_limit_at_the_destination(self) -> None:
        host, module, clock = _host()
        _report(host, module, at("T1", "30"))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "30", "")
        row = host.trainDetail("T1")
        self.assertEqual(row["authority"], "0 (to 30)")
        self.assertEqual(row["authorityLimit"], "At destination")

    def test_throughput_per_line(self) -> None:
        host, _, clock = _host()
        self.assertEqual(host.throughput, {"Green": "—",
                                           "Red": "—"})
        # Per line is the sum over the line's stations.
        host._receive_inputs(CtcInputs(track_model=TrackModelInputs({
            "GLENBURY": 20, "DORMONT": 10, "SHADYSIDE": 6})))
        for _ in range(3600):          # six simulated minutes of ticks
            clock.clock.tick()
        # Sales count once, on the first tick: 30 in a tenth of an hour.
        self.assertEqual(host.throughput, {"Green": "300", "Red": "60"})
        self.assertEqual(
            [(r["line"], r["tickets"]) for r in host.throughputRows],
            [("Green", "300"), ("Red", "60")])

    def test_history_buckets_sales_by_clock_hour(self) -> None:
        host, _, clock = _host()           # the clock starts at 05:00

        def sell(station: str, tickets: int, at_s: float) -> None:
            clock.clock.reset(at_s)
            host._receive_inputs(CtcInputs(track_model=TrackModelInputs(
                {station: tickets})))
            clock.clock.tick()

        sell("GLENBURY", 10, 5 * 3600)
        sell("DORMONT", 5, 5 * 3600 + 1800)
        sell("SHADYSIDE", 4, 7 * 3600)
        history = host.throughputHistory
        # Twelve hours from the start hour, 05:00 to 16:00.
        self.assertEqual(history["hours"][0], "05:00")
        self.assertEqual(history["hours"][-1], "16:00")
        counts = {s["line"]: s["counts"] for s in history["series"]}
        self.assertEqual(counts["Green"][:3], [15, 0, 0])
        self.assertEqual(counts["Red"][:3], [0, 0, 4])
        self.assertEqual((history["peak"], history["current"]), (15, 2))

        # Past 12 hours the window follows the current hour, across
        # midnight: 05:00 drops out.
        sell("SHADYSIDE", 1, 24 * 3600 + 900)        # 00:15 the next day
        history = host.throughputHistory
        self.assertEqual((history["hours"][0], history["hours"][-1]),
                         ("13:00", "00:00"))
        counts = {s["line"]: s["counts"] for s in history["series"]}
        self.assertEqual(sum(counts["Green"]), 0)
        self.assertEqual(counts["Red"][-1], 1)

    def test_test_ui_changes_reach_the_window(self) -> None:
        # The link server's changed signal makes the panels re-read.
        host, module, _ = _host()
        seen: list[bool] = []
        host.stateChanged.connect(lambda: seen.append(True))
        module.set_maintenance_mode(True)
        module.set_block_closed("Red", "2", True)
        host._server.changed.emit()
        self.assertEqual(seen, [True])
        self.assertEqual(host.blockStates, {"Red:2": "closed"})

    def test_closing_block_is_shown_once_and_not_as_closed(self) -> None:
        # closed_blocks lists a closing block too; the window still
        # shows it once, as closing, with its train on the map.
        host, module, clock = _host()
        _report(host, module, at("T1", "65"))
        clock.clock.tick()
        module.set_maintenance_mode(True)
        module.set_block_closed("Green", "65", True)
        self.assertEqual(
            [(r["block"], r["pending"]) for r in host.closures],
            [("Green 65", True)])
        self.assertEqual(host.blockStates, {})
        self.assertTrue(host.maintenanceMode)


if __name__ == "__main__":
    unittest.main()
