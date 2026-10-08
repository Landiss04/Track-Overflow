"""Tests for the CTC window's host of the CTC module.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import dataclasses
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
    TrackFailureReport,
    TicketSales,
    TrackModelInputs,
    TrainReport,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
from ctc_ui.sim_clock import SimulationClockBridge  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])


def _green(tickets: int) -> TrackModelInputs:
    """Track Model inputs with Green line ticket sales."""
    return TrackModelInputs((TicketSales("Green", tickets),))


def _sold(snap: CtcSnapshot, line: str = "Green") -> int:
    """Tickets sold so far on one line."""
    return {t.line: t.tickets for t in snap.tickets_sold}[line]


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

    def test_block_states_show_the_most_urgent(self) -> None:
        host, _, clock = _host()
        host.setMaintenanceMode(True)
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(
                occupancy=(BlockOccupancy("Green", "1", True),
                           BlockOccupancy("Green", "2", True)),
                trains=(TrainReport("T1", "Red", "4", 0.0, 5.0),),
                crossings=(CrossingReport("Green", "19", "active"),),
                failures=(TrackFailureReport("Green", "2", "power"),))))
        clock.clock.tick()
        # Green 1 is occupied, so its closure waits; Green 5 is clear.
        self.assertEqual(host.closeBlock("Green", "1"), "")
        self.assertEqual(host.closeBlock("Green", "5"), "")
        # Occupancy is drawn as trains, not a block state.
        self.assertEqual(host.blockStates, {
            "Green:5": "closed", "Green:2": "failure"})
        self.assertEqual(host.crossingStates, {"Green:19": "active"})
        self.assertEqual(
            [(r["block"], r["state"]) for r in host.closures],
            [("Green 1", "Closing \u2014 train in block"),
             ("Green 2", "Power failure"), ("Green 5", "Closed")])

    def test_map_trains(self) -> None:
        host, _, clock = _host()
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(
                # Green 3 is 100 m long: 25 m in is a quarter of the way.
                trains=(TrainReport("T1", "Green", "3", 25.0, 5.0),),
                occupancy=(BlockOccupancy("Green", "3", True),
                           BlockOccupancy("Red", "8", True),
                           BlockOccupancy("Red", "9", False)))))
        clock.clock.tick()
        self.assertEqual(host.mapTrains, [
            {"train": "T1", "line": "Green", "block": "3",
             "fraction": 0.25},
            # Occupied with no train reported: an unnamed train.
            {"train": "", "line": "Red", "block": "8", "fraction": 0.5}])

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

    def test_trains_merge_reports_and_orders(self) -> None:
        host, _, clock = _host()
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "9", 0.0, 10.0),))))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "65", "08:30")
        host.dispatchTrain("T2", "Red", "7", "")
        rows = {row["train"]: row for row in host.trains}
        self.assertEqual(rows["T1"]["block"], "9")
        self.assertEqual(rows["T1"]["speed"], "22.4")         # mph
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
        host, _, clock = _host()
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(trains=(
                TrainReport("T1", "Green", "30", 0.0, 0.0),
                TrainReport("T2", "Green", "32", 0.0, 0.0)))))
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
        host, _, clock = _host()
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(trains=(
                TrainReport("T1", "Green", "63", 0.0, 0.0),))))
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
        host, _, clock = _host()
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(trains=(
                TrainReport("T1", "Green", "20", 0.0, 0.0),
                TrainReport("T2", "Green", "28", 0.0, 0.0)))))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "24", "")
        host.dispatchTrain("T2", "Green", "24", "")
        self.assertEqual(host.trainDetail("T2")["authorityLimit"],
                         "Block 24 held by T1")

    def test_reversal_alerts(self) -> None:
        # T5 on Red 28 cannot move (29 failed); T4 behind it wants 31,
        # which only reversing would reach.
        host, module, clock = _host()
        reports = CtcInputs(track_controller=TrackControllerInputs(
            trains=(TrainReport("T4", "Red", "20", 0.0, 0.0),
                    TrainReport("T5", "Red", "28", 0.0, 0.0)),
            failures=(TrackFailureReport("Red", "29", "power"),),
            switches=(SwitchReport("Red", "27", "normal"),)))
        host._receive_inputs(reports)
        host.dispatchTrain("T4", "Red", "31", "")
        host.dispatchTrain("T5", "Red", "45", "")
        clock.clock.tick()
        clock.clock.tick()
        alerts = {a["train"]: a for a in host.reversalAlerts}
        self.assertEqual(alerts["T4"], {
            "train": "T4", "line": "Red", "reverseAt": "33",
            "destination": "31",
            "blockedBy": "T5 is standing in block 28 and is not moving"})
        self.assertEqual(alerts["T5"]["blockedBy"], "block 29 has failed")
        self.assertIn("reversing at block 33",
                      host.routeDetail("T4")["summary"])
        # Dismissed: gone until the situation clears and comes back.
        host.dismissReversal("T4")
        self.assertEqual([a["train"] for a in host.reversalAlerts], ["T5"])
        host._receive_inputs(dataclasses.replace(
            reports, track_controller=dataclasses.replace(
                reports.track_controller, failures=())))
        clock.clock.tick()
        clock.clock.tick()
        self.assertEqual(host.reversalAlerts, [])
        host._receive_inputs(reports)
        clock.clock.tick()
        clock.clock.tick()
        self.assertIn("T4", [a["train"] for a in host.reversalAlerts])

    def test_authority_limit_at_the_destination(self) -> None:
        host, _, clock = _host()
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "30", 0.0, 0.0),))))
        clock.clock.tick()
        host.dispatchTrain("T1", "Green", "30", "")
        row = host.trainDetail("T1")
        self.assertEqual(row["authority"], "0 (to 30)")
        self.assertEqual(row["authorityLimit"], "At destination")

    def test_throughput_per_line(self) -> None:
        host, _, clock = _host()
        self.assertEqual(host.throughput, {"Green": "—",
                                           "Red": "—"})
        host._receive_inputs(CtcInputs(track_model=TrackModelInputs((
            TicketSales("Green", 30), TicketSales("Red", 6)))))
        for _ in range(3600):          # six simulated minutes of ticks
            clock.clock.tick()
        # Sales count once, on the first tick: 30 in a tenth of an hour.
        self.assertEqual(host.throughput, {"Green": "300", "Red": "60"})
        self.assertEqual(
            [(r["line"], r["tickets"]) for r in host.throughputRows],
            [("Green", "300"), ("Red", "60")])

    def test_history_buckets_sales_by_clock_hour(self) -> None:
        host, _, clock = _host()           # the clock starts at 05:00

        def sell(line: str, tickets: int, at_s: float) -> None:
            clock.clock.reset(at_s)
            host._receive_inputs(CtcInputs(track_model=TrackModelInputs(
                (TicketSales(line, tickets),))))
            clock.clock.tick()

        sell("Green", 10, 5 * 3600)
        sell("Green", 5, 5 * 3600 + 1800)
        sell("Red", 4, 7 * 3600)
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
        sell("Red", 1, 24 * 3600 + 900)          # 00:15 the next day
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
        host._receive_inputs(CtcInputs(
            track_controller=TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "65", 0.0, 0.0),))))
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
