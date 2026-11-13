"""Tests for automatic dispatch from the schedule (``ctc.scheduler``).

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import math
from dataclasses import replace
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import ScheduledRun, SwitchReport  # noqa: E402
from ctc.model import (  # noqa: E402
    InvalidInputError,
    InvalidTimeStepError,
    StubCtcOffice,
)
from ctc.routing import build_graphs  # noqa: E402
from ctc.schedule import (  # noqa: E402
    Schedule,
    ScheduledTrain,
    load_schedule,
    parse_schedule,
)
from ctc.scheduler import (  # noqa: E402
    DONE,
    DWELL_S,
    EN_ROUTE,
    HELD,
    IN_YARD,
    QUEUED,
    SIMULATION_START_S,
    Progress,
    World,
    opposed,
    train_id_for,
    two_way_zones,
)
from ctc.track_layout import load_layout  # noqa: E402
from ctc.tracking import YARD_EXITS  # noqa: E402
from tests.occupancy import at, ready_office, reports, step_at  # noqa: E402

SCHEDULE = load_schedule(
    Path(__file__).resolve().parents[2] / "utils" / "schedule_v4.json")
_LAYOUT = load_layout()
_GRAPHS = build_graphs(_LAYOUT)

#: Green run 1's scheduled stations in the order the track reaches
#: them from the yard (63): up to 100, back through 85 to 77, on to 150,
#: down D to A, then up from 13 to 57, where the yard joins. 16 is a
#: station with no name.
GREEN_ORDER = ["65", "73", "77", "88", "96", "105", "123", "132", "141",
               "22", "16", "9", "2", "31", "39", "48", "57"]
#: Red run 1's, from the yard (9), which a train leaves toward 10 as the
#: Track Model runs it: up to 52, round the loop to South Hills Junction
#: (60), back down to 16, and through Shadyside (7) to the yard at 9.
RED_ORDER = ["16", "21", "25", "35", "45", "48", "60", "7"]

#: The file lists each run's stations in an order a run follows as given
#: (``FILE_*``): Green 1 goes to Pioneer (2) first, Red 1 to Shadyside
#: (7).
FILE_GREEN = ["2", "9", "16", "22", "31", "39", "48", "57", "65", "73",
              "77", "88", "96", "105", "123", "132", "141"]
FILE_RED = ["7", "16", "21", "25", "35", "45", "48", "60"]


def _track_ordered(schedule: Schedule) -> Schedule:
    """The schedule with each run's stops listed in track order from the
    yard (``GREEN_ORDER``, ``RED_ORDER``), its first entry kept first so
    that it leaves when it did: one lap a run, for the tests of how runs
    share the track."""
    order = {"Green": GREEN_ORDER, "Red": RED_ORDER}
    trains = []
    for train in schedule.trains:
        first, *rest = train.stops
        listed = order[train.line]
        rest.sort(key=lambda stop: (listed.index(stop.block_id)
                                    if stop.block_id in listed
                                    else len(listed)))
        trains.append(ScheduledTrain(train.line, train.train_id,
                                     (first, *rest)))
    return Schedule(schedule.source, tuple(trains))


#: The schedule in track order: what most tests here run.
TRACK_SCHEDULE = _track_ordered(SCHEDULE)


def _loaded(automatic: bool = True,
            schedule: Schedule = TRACK_SCHEDULE) -> StubCtcOffice:
    ctc = ready_office()
    ctc.load_schedule(schedule)
    ctc.set_automatic_mode(automatic)
    return ctc


def _run(ctc: StubCtcOffice, train_id: str) -> ScheduledRun:
    (found,) = [r for r in ctc.snapshot().scheduled_runs
                if r.train_id == train_id]
    return found


def _order(ctc: StubCtcOffice, train_id: str) -> str | None:
    orders = {o.train_id: o.destination_block_id
              for o in ctc.snapshot().orders}
    return orders.get(train_id)


class PlanTest(unittest.TestCase):
    """Each run is planned when the schedule loads."""

    def test_stations_in_file_order(self) -> None:
        # The file's order, whatever it costs: Green 1 goes to Pioneer
        # (2) first, through Glenbury (65) and every station before it
        # without stopping, and round again for Edgebrook (9).
        ctc = _loaded(schedule=SCHEDULE)
        plans = {p.train_id: p for p in ctc._auto.plans}
        self.assertEqual([s.block_id for s in plans["G1"].stops],
                         FILE_GREEN)
        self.assertEqual([s.block_id for s in plans["R1"].stops],
                         FILE_RED)
        to_pioneer = plans["G1"].path[:plans["G1"].stop_indexes[0] + 1]
        self.assertIn("65", to_pioneer)
        self.assertEqual((plans["G1"].yard_block_id,
                          plans["R1"].yard_block_id), ("57", "9"))

    def test_first_order_is_the_first_station(self) -> None:
        # G1's first order is Pioneer: no stop before it.
        ctc = _loaded(schedule=SCHEDULE)
        step_at(ctc)
        self.assertEqual(_order(ctc, "G1"), "2")
        self.assertEqual(_order(ctc, "R1"), "7")

    def test_stations_in_track_order(self) -> None:
        ctc = _loaded()
        plans = {p.train_id: p for p in ctc._auto.plans}
        self.assertEqual([s.block_id for s in plans["G1"].stops],
                         GREEN_ORDER)
        self.assertEqual([s.block_id for s in plans["R1"].stops],
                         RED_ORDER)
        # Green's last station is where the yard joins; Red runs back.
        self.assertEqual((plans["G1"].yard_block_id,
                          plans["R1"].yard_block_id), ("57", "9"))
        self.assertEqual(plans["G1"].unreachable, ())

    def test_only_scheduled_stations_are_stops(self) -> None:
        ctc = _loaded()
        (plan,) = [p for p in ctc._auto.plans if p.train_id == "G1"]
        stops = [s.block_id for s in plan.stops]
        # The file also times Green 1 and 113, which are not stations;
        # 16 is a station with no name.
        self.assertNotIn("1", stops)
        self.assertNotIn("113", stops)
        self.assertIn("16", stops)
        # Glenbury's other platform (114) is on the way but not
        # scheduled: the run goes through it.
        self.assertNotIn("114", stops)
        self.assertEqual(plan.stops[0].station, "GLENBURY")

    def test_passes_stations_it_is_not_scheduled_for(self) -> None:
        # A run scheduled at Glenbury (65) and Castle Shannon (96) only
        # goes straight from one to the other, through Dormont (73), Mt
        # Lebanon (77) and Poplar (88).
        ctc = _loaded(schedule=parse_schedule({
            "time_unit": "s", "lines": [{"line": "Green", "trains": [{
                "train_id": "1", "stops": [
                    {"block_id": "65", "station": "GLENBURY",
                     "arrival_s": 0},
                    {"block_id": "96", "station": "CASTLE SHANNON",
                     "arrival_s": 600}]}]}]}))
        (plan,) = ctc._auto.plans
        self.assertEqual([s.block_id for s in plan.stops], ["65", "96"])
        step_at(ctc)
        ctc.step(1.0, reports(occupied=[("Green", "63")]))
        step_at(ctc, at("G1", "65"))                # arrives: dwells
        step_at(ctc, at("G1", "65"), dt=DWELL_S)    # the dwell is over
        self.assertEqual(_order(ctc, "G1"), "96")
        (limit,) = ctc.snapshot().authorities
        self.assertTrue({"73", "77", "88"} <= set(limit.route))

    def test_due_times(self) -> None:
        ctc = _loaded()
        plans = {p.train_id: p for p in ctc._auto.plans}
        # Time zero is the simulation start, 05:00 (D017); runs leave
        # every three minutes.
        self.assertEqual(plans["G1"].departure_s, SIMULATION_START_S)
        self.assertEqual(plans["G2"].departure_s, SIMULATION_START_S + 180)
        # Glenbury is two 100 m blocks at 70 km/h from the yard exit.
        first = plans["G1"].stops[0].due_s - SIMULATION_START_S
        self.assertAlmostEqual(first, ctc._run_time_s(
            "Green", ("63", "64", "65")))
        due = [s.due_s for s in plans["G1"].stops]
        self.assertTrue(all(b - a >= DWELL_S for a, b in zip(due, due[1:])))

    def test_train_ids(self) -> None:
        runs = _loaded().snapshot().scheduled_runs
        self.assertEqual(sorted(r.train_id for r in runs if r.line == "Red"),
                         sorted(f"R{n}" for n in range(1, 11)))
        self.assertEqual(train_id_for("Green", "7"), "G7")


class ZoneTest(unittest.TestCase):
    """Runs are never sent to meet head-on: where their paths cross the
    same track both ways, trains go through it one way at a time."""

    def test_the_zones(self) -> None:
        zones = _loaded()._auto.zones
        green: dict[str, set[str]] = {}
        for block, zone in zones["Green"].items():
            green.setdefault(zone, set()).add(block)
        # Up N to 85 and back down; up from 13 to 28 and back down. The
        # loops beyond them (86 to 100, 1 to 12) are one way.
        self.assertEqual(sorted(green.values(), key=min), [
            {str(n) for n in range(13, 29)},
            {str(n) for n in range(77, 86)}])
        # Red: out from 16 to 52 and back, but out on the main line and
        # back on the sidings beside 28 to 32 and 39 to 43, which are one
        # way each; so is the loop 53 to 66.
        red: dict[str, set[str]] = {}
        for block, zone in zones["Red"].items():
            red.setdefault(zone, set()).add(block)
        self.assertEqual(sorted(red.values(), key=lambda z: int(min(z))), [
            {str(n) for n in range(16, 28)},
            {str(n) for n in range(33, 39)},
            {str(n) for n in range(44, 53)}])
        # The yards are outside them.
        self.assertNotIn("63", zones["Green"])
        self.assertNotIn("9", zones["Red"])

    def test_out_and_back_track_is_a_zone(self) -> None:
        # One path out along 1-2-3 and back: all of it. A path that only
        # passes one way is not, nor a loop it runs round (4 and 5).
        self.assertEqual(set(two_way_zones([("1", "2", "3", "2", "1")])),
                         {"1", "2", "3"})
        self.assertEqual(two_way_zones([("1", "2", "3")]), {})
        self.assertEqual(
            set(two_way_zones([("1", "2", "3", "4", "5", "3", "2", "1")])),
            {"1", "2", "3"})

    def _waiting_at_99_and_g9_in_yard(self):
        # G4 waits round the 86-100 loop (at 99) to come back through
        # N; G9 was ordered out through N before G4 got there and is
        # still in the yard: the state the schedule v4 run locked in.
        # As the file lists it, G9's first stop (Pioneer, 2) is beyond N.
        auto = _loaded(schedule=SCHEDULE)._auto
        plan = auto._plan["G4"]
        back = [s for s in auto._spans["G4"] if s[0] == "77"][1]
        wait = auto._loop_wait(plan, back)
        leg = next(i for i, index in enumerate(plan.stop_indexes)
                   if index > back[1])
        auto.progress["G4"] = Progress(HELD, leg=leg, at=wait, wait=wait)
        auto.progress["G9"] = Progress(IN_YARD, leg=0, at=-1)
        orders = {"G4": plan.stops[leg].block_id,
                  "G9": auto._plan["G9"].stops[0].block_id}
        return auto, plan.path[wait], orders

    def _world(self, heads, orders, released=frozenset()):
        return World(now_s=SIMULATION_START_S,
                     ready_lines=frozenset({"Green"}), heads=heads,
                     orders=orders, lost=frozenset(), released=released)

    def test_a_run_not_out_gives_up_its_pass_to_a_waiting_train(self):
        auto, head, orders = self._waiting_at_99_and_g9_in_yard()
        self.assertEqual(head, "99")
        actions = auto.step(self._world({"G4": head}, orders))
        # G9 waits in the yard; it is not sent again.
        self.assertEqual(auto.progress["G9"].status, HELD)
        self.assertEqual(auto.progress["G9"].wait, -1)
        self.assertNotIn("G9", [a.train_id for a in actions])
        # G4 then comes back through N.
        auto.step(self._world({"G4": head}, orders))
        self.assertEqual(auto.progress["G4"].status, EN_ROUTE)

    def test_a_run_coming_out_of_the_yard_keeps_its_pass(self):
        auto, head, orders = self._waiting_at_99_and_g9_in_yard()
        auto.step(self._world({"G4": head}, orders, frozenset({"G9"})))
        self.assertEqual(auto.progress["G9"].status, IN_YARD)
        self.assertEqual(auto.progress["G4"].status, HELD)

    def test_opposed(self) -> None:
        path = ("1", "2", "3", "4", "5", "3", "2", "1")
        out, back = ("1", 0, 2), ("1", 5, 7)
        self.assertTrue(opposed(path, out, path, back))
        self.assertFalse(opposed(path, out, path, out))
        self.assertFalse(opposed(path, out, path, ("2", 5, 7)))

    def _g1_in_n(self, ctc: StubCtcOffice, index: int, leg: int) -> None:
        ctc._auto.progress["G1"] = Progress(EN_ROUTE, leg, at=index)

    def _g2_done_at_dormont(self, ctc: StubCtcOffice) -> None:
        # G2, done at Dormont (73), would go into N for Mt Lebanon (77).
        plans = {p.train_id: p for p in ctc._auto.plans}
        ctc._auto.progress["G2"] = Progress(
            "dwelling", 1, at=plans["G2"].stop_indexes[1])
        ctc.dispatch("G2", "Green", "73")

    def test_held_until_the_zone_is_clear(self) -> None:
        # G1 is coming back down N (at 80) on its way to 105: G2 waits,
        # sent on to 75, a block short of N on the one-way track.
        ctc = _loaded()
        step_at(ctc)
        path = next(p for p in ctc._auto.plans if p.train_id == "G1").path
        back = path.index("80", path.index("100"))
        self._g1_in_n(ctc, back, GREEN_ORDER.index("105"))
        self._g2_done_at_dormont(ctc)
        step_at(ctc, at("G1", "80"), at("G2", "73"), dt=DWELL_S)
        run = _run(ctc, "G2")
        self.assertEqual((run.status, run.stop_block_id), ("held", "77"))
        self.assertEqual(_order(ctc, "G2"), "77")
        self.assertEqual(ctc._auto.hold_at("G2"), "75")
        # G1's run is over: N is clear, and G2 goes on.
        ctc._auto.progress["G1"] = Progress(DONE, 18)
        step_at(ctc, at("G2", "73"))
        self.assertEqual((_run(ctc, "G2").status, _order(ctc, "G2")),
                         ("en route", "77"))

    def test_trains_going_the_same_way_share_it(self) -> None:
        # G1 is going up N (at 80) to Poplar (88): G2 follows it in.
        ctc = _loaded()
        step_at(ctc)
        path = next(p for p in ctc._auto.plans if p.train_id == "G1").path
        self._g1_in_n(ctc, path.index("80"), GREEN_ORDER.index("88"))
        self._g2_done_at_dormont(ctc)
        step_at(ctc, at("G1", "80"), at("G2", "73"), dt=DWELL_S)
        self.assertEqual((_run(ctc, "G2").status, _order(ctc, "G2")),
                         ("en route", "77"))

    def _r1_turned(self) -> StubCtcOffice:
        """R1 done at South Hills Junction (60), round the loop, with R2
        following it out (at 46, in 44..52 on its way to Station Square)
        and R3 due in the yard."""
        ctc = _loaded()
        step_at(ctc)
        plans = {p.train_id: p for p in ctc._auto.plans}
        leg = RED_ORDER.index("60")
        ctc._auto.progress["R1"] = Progress(
            "dwelling", leg, at=plans["R1"].stop_indexes[leg])
        ctc.dispatch("R1", "Red", "60")
        ctc._auto.progress["R2"] = Progress(
            EN_ROUTE, RED_ORDER.index("48"),
            at=plans["R2"].path.index("46"))
        ctc.dispatch("R2", "Red", "48")
        ctc._auto.progress["R3"] = Progress(QUEUED)
        return ctc

    def test_no_pass_onto_one_way_track_with_no_room(self) -> None:
        # R4 and R5 are up on the main line beside the 67-71 siding (39 to
        # 43), which holds two a block apart. R6, coming up to Steel
        # Plaza (35) in 33..38, would stand in 33..38 with nowhere to go
        # on to: it waits short of it, at 31. Once R5 is on into 44..52,
        # it goes.
        ctc = _loaded()
        step_at(ctc)
        plans = {p.train_id: p for p in ctc._auto.plans}
        for train_id, block in (("R4", "42"), ("R5", "40")):
            ctc._auto.progress[train_id] = Progress(
                EN_ROUTE, RED_ORDER.index("45"),
                at=plans[train_id].path.index(block))
            ctc.dispatch(train_id, "Red", "45")
        ctc._auto.progress["R6"] = Progress(
            EN_ROUTE, RED_ORDER.index("35"),
            at=plans["R6"].path.index("30"), wait=plans["R6"].path.index("31"))
        ctc.dispatch("R6", "Red", "35")
        trains = [at("R4", "42", "Red"), at("R5", "40", "Red"),
                  at("R6", "30", "Red")]
        step_at(ctc, *trains)
        self.assertEqual(_run(ctc, "R6").status, HELD)
        self.assertEqual(ctc._auto.hold_at("R6"), "31")
        ctc._auto.progress["R5"] = replace(
            ctc._auto.progress["R5"], at=plans["R5"].path.index("44"))
        step_at(ctc, at("R4", "42", "Red"), at("R5", "44", "Red"),
                at("R6", "30", "Red"))
        self.assertEqual(_run(ctc, "R6").status, EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("R6"))

    def test_a_train_that_has_turned_waits_round_the_loop(self) -> None:
        # R1 would come back down 44..52 past R2: it is given its order on
        # to Shadyside (7), but its authority stops at 65, round the loop
        # (in at 53, out from 66) a block short of 66 (by switch 52),
        # where it waits. It is held only once it waits there.
        ctc = self._r1_turned()
        step_at(ctc, at("R1", "60", "Red"), at("R2", "46", "Red"),
                dt=DWELL_S)
        self.assertEqual((_run(ctc, "R1").status, _order(ctc, "R1")),
                         ("en route", "7"))
        self.assertEqual(ctc._auto.hold_at("R1"), "65")
        # Placed at 60, it came round the loop from 59.
        ctc._tracker.trains["R1"] = replace(ctc._tracker.trains["R1"],
                                            came_from="59")
        step_at(ctc, at("R1", "60", "Red"), at("R2", "46", "Red"))
        (limit,) = [a for a in ctc.snapshot().authorities
                    if a.train_id == "R1"]
        self.assertEqual((limit.end_block_id, limit.reason),
                         ("65", "held"))
        self.assertEqual(limit.route[-2:], ("64", "65"))
        self.assertEqual(_order(ctc, "R2"), "48")
        # R2 is round the loop too: R1 comes back, and R2 after it.
        plans = {p.train_id: p for p in ctc._auto.plans}
        ctc._auto.progress["R2"] = Progress(
            HELD, len(RED_ORDER) - 1, at=plans["R2"].path.index("64"),
            wait=plans["R2"].path.index("65"))
        step_at(ctc, at("R1", "65", "Red"), at("R2", "64", "Red"))
        self.assertEqual((_run(ctc, "R1").status, _order(ctc, "R1")),
                         ("en route", "7"))
        # It has 44..52 and claims only that: it goes on as far as the
        # siding beside 39..43, a block short of 33..38 (70).
        self.assertEqual(ctc._auto.hold_at("R1"), "70")

    def test_a_train_waiting_holds_out_only_its_own_stretch(self) -> None:
        # R1 waits at 65 to come back down 44..52, which R2 holds going
        # up. R3 is due; its way out starts with 16..27, not the stretch
        # R1 waits for, so it leaves: R1 and R3 pass at a siding.
        ctc = self._r1_turned()
        plans = {p.train_id: p for p in ctc._auto.plans}
        wait = plans["R1"].path.index("65")
        ctc._auto.progress["R1"] = Progress(
            HELD, len(RED_ORDER) - 1, at=wait, wait=wait)
        ctc.dispatch("R1", "Red", "7")
        step_at(ctc, at("R1", "65", "Red"), at("R2", "46", "Red"),
                dt=plans["R3"].departure_s - SIMULATION_START_S)
        self.assertEqual(ctc._auto.hold_at("R1"), "65")
        self.assertEqual(_run(ctc, "R3").status, "in yard")
        self.assertIsNotNone(_order(ctc, "R3"))


class DispatchTest(unittest.TestCase):
    """In automatic mode the runs carry themselves out."""

    def test_nothing_outside_automatic_mode(self) -> None:
        ctc = _loaded(automatic=False)
        step_at(ctc, dt=600)
        self.assertEqual(ctc.snapshot().orders, ())
        self.assertEqual(_run(ctc, "G1").status, "queued")

    def test_paused_holds_then_resumes(self) -> None:
        ctc = _loaded()
        ctc.set_dispatch_paused(True)
        step_at(ctc, dt=60)
        self.assertEqual(ctc.snapshot().orders, ())
        ctc.set_dispatch_paused(False)
        step_at(ctc)
        self.assertEqual((_order(ctc, "G1"), _order(ctc, "R1")),
                         ("65", "16"))

    def test_a_run_leaves_when_due(self) -> None:
        ctc = _loaded()
        step_at(ctc, dt=179)                           # 05:02:59
        self.assertEqual(_run(ctc, "G2").status, "queued")
        step_at(ctc, dt=1)                             # 05:03:00
        run = _run(ctc, "G2")
        self.assertEqual((run.status, run.stop_block_id, run.stop_station),
                         ("in yard", "65", "GLENBURY"))
        # Dispatched with the time it is due at its first stop.
        (order,) = [o for o in ctc.snapshot().orders if o.train_id == "G2"]
        self.assertEqual(order.arrival_s, run.stop_due_s)

    def test_stops_dwells_and_moves_on(self) -> None:
        ctc = _loaded()
        step_at(ctc)
        self.assertEqual(_run(ctc, "G1").status, "in yard")
        # Green 63 becomes occupied: G1 has left the yard.
        ctc.step(1.0, reports(occupied=[("Green", "63")]))
        self.assertEqual(_run(ctc, "G1").status, "en route")
        # It gets to Glenbury (65) and is held there for the dwell.
        step_at(ctc, at("G1", "65"))
        run = _run(ctc, "G1")
        self.assertEqual((run.status, run.stops_done), ("dwelling", 1))
        step_at(ctc, at("G1", "65"), dt=DWELL_S - 1)
        self.assertEqual(_order(ctc, "G1"), "65")
        step_at(ctc, at("G1", "65"), dt=1)
        self.assertEqual((_run(ctc, "G1").status, _order(ctc, "G1")),
                         ("en route", "73"))

    def test_a_closed_stop_is_skipped(self) -> None:
        ctc = _loaded()
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "65", True)
        step_at(ctc)
        run = _run(ctc, "G1")
        self.assertEqual((run.status, run.stop_block_id), ("in yard", "73"))
        self.assertEqual(_order(ctc, "G1"), "73")

    def test_manual_mode_holds_a_train_at_its_stop(self) -> None:
        ctc = _loaded()
        step_at(ctc)
        ctc.step(1.0, reports(occupied=[("Green", "63")]))
        step_at(ctc, at("G1", "65"))
        ctc.set_automatic_mode(False)
        step_at(ctc, at("G1", "65"), dt=300)
        self.assertEqual((_run(ctc, "G1").status, _order(ctc, "G1")),
                         ("dwelling", "65"))
        ctc.set_automatic_mode(True)
        step_at(ctc, at("G1", "65"))
        self.assertEqual(_order(ctc, "G1"), "73")

    def test_back_to_the_yard_and_done(self) -> None:
        # R1 heading for its last stop, Shadyside (7).
        ctc = _loaded()
        step_at(ctc)
        ctc._auto.progress["R1"] = Progress(EN_ROUTE, len(RED_ORDER) - 1)
        ctc.dispatch("R1", "Red", "7")
        step_at(ctc, at("R1", "7", "Red"))
        self.assertEqual(_run(ctc, "R1").status, "dwelling")
        step_at(ctc, at("R1", "7", "Red"), dt=DWELL_S)
        self.assertEqual((_run(ctc, "R1").status, _order(ctc, "R1")),
                         ("to yard", "9"))
        # Back at 9, then its block clears: it has gone into the yard.
        step_at(ctc, at("R1", "9", "Red"))
        step_at(ctc)
        run = _run(ctc, "R1")
        self.assertEqual((run.status, run.stops_done, run.stops_total),
                         ("done", 8, 8))
        self.assertIsNone(_order(ctc, "R1"))
        self.assertEqual(ctc.snapshot().lost_trains, ())


class ScheduleStartTest(unittest.TestCase):
    """A schedule's time zero is the moment the clock runs with it
    loaded, whatever the simulation time is then."""

    def _late(self, running: bool) -> StubCtcOffice:
        # Five minutes into the simulation, with no schedule yet.
        ctc = ready_office()
        if running:
            ctc.set_clock_paused(False)
        step_at(ctc, dt=300.0)
        ctc.set_automatic_mode(True)
        ctc.load_schedule(SCHEDULE)
        return ctc

    def test_loaded_while_paused_starts_at_run(self) -> None:
        ctc = self._late(running=False)
        self.assertIsNone(ctc.snapshot().schedule_start_s)
        ctc.set_clock_paused(False)
        start = SIMULATION_START_S + 300.0
        self.assertEqual(ctc.snapshot().schedule_start_s, start)
        # Each run keeps its offset from the new time zero.
        self.assertEqual(_run(ctc, "G2").departure_s, start + 180)

    def test_loaded_while_running_starts_at_once(self) -> None:
        ctc = self._late(running=True)
        start = SIMULATION_START_S + 300.0
        self.assertEqual(ctc.snapshot().schedule_start_s, start)
        self.assertEqual(_run(ctc, "G1").departure_s, start)

    def test_late_load_keeps_the_headway(self) -> None:
        # Loaded at 05:05, the runs due at 0 s and 180 s do not both
        # go at once: only the first is dispatched.
        ctc = self._late(running=True)
        step_at(ctc)
        self.assertEqual(_run(ctc, "G1").status, "in yard")
        self.assertEqual(_run(ctc, "G2").status, QUEUED)
        step_at(ctc, dt=180.0)
        self.assertNotEqual(_run(ctc, "G2").status, QUEUED)

    def test_a_new_schedule_starts_again(self) -> None:
        ctc = self._late(running=True)
        step_at(ctc, dt=120.0)
        ctc.load_schedule(SCHEDULE)
        self.assertEqual(ctc.snapshot().schedule_start_s,
                         SIMULATION_START_S + 420.0)


class HarnessTimeTest(unittest.TestCase):
    """Under the harness each step brings the simulation time (D017:
    unwrapped seconds, at the end of the step), and the CTC Office's
    time is that time. A tick it refused or never got does not put its
    schedule behind the harness's."""

    def test_its_time_is_the_harness_time(self) -> None:
        ctc = _loaded()
        ctc.step(0.1, reports(), sim_time_s=SIMULATION_START_S + 0.1)
        self.assertAlmostEqual(ctc.snapshot().elapsed_s, 0.1)
        # Three ticks it never saw: its time is the harness's still.
        ctc.step(0.1, reports(), sim_time_s=SIMULATION_START_S + 0.5)
        self.assertAlmostEqual(ctc.snapshot().elapsed_s, 0.5)
        # Past midnight, unwrapped.
        ctc.step(0.1, reports(), sim_time_s=SIMULATION_START_S + 86_400)
        self.assertAlmostEqual(ctc.snapshot().elapsed_s, 86_400)

    def test_a_refused_tick_does_not_put_the_schedule_behind(self) -> None:
        # G2 is due out of the yard at 05:03:00.
        ctc = _loaded()
        ctc.step(0.1, reports(), sim_time_s=SIMULATION_START_S + 179.9)
        self.assertEqual(_run(ctc, "G2").status, "queued")
        with self.assertRaises(InvalidInputError):
            ctc.step(0.1, reports(occupied=[("Green", "999")]),
                     sim_time_s=SIMULATION_START_S + 180.0)
        self.assertEqual(_run(ctc, "G2").status, "queued")
        ctc.step(0.1, reports(), sim_time_s=SIMULATION_START_S + 180.1)
        self.assertEqual(_run(ctc, "G2").status, "in yard")

    def test_a_bad_time_is_refused_and_changes_nothing(self) -> None:
        ctc = _loaded()
        ctc.step(0.1, reports(), sim_time_s=SIMULATION_START_S + 10)
        before = ctc.snapshot()
        for bad in (math.nan, math.inf, -math.inf, True, "18010.1",
                    SIMULATION_START_S + 10, SIMULATION_START_S + 5):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidTimeStepError):
                    ctc.step(0.1, reports(),
                             sim_time_s=bad)  # type: ignore[arg-type]
        self.assertEqual(ctc.snapshot(), before)

    def test_on_its_own_it_counts_its_steps(self) -> None:
        # The standalone window and the tests: no harness time.
        ctc = _loaded()
        ctc.step(1.0, reports())
        ctc.step(2.0, reports())
        self.assertEqual(ctc.snapshot().elapsed_s, 3.0)


class _Railway:
    """A stand-in for the rest of the system, for a whole run, as the
    harness will be: each train the CTC releases (``new_trains``) is
    put at its line's yard exit block, trains run at their suggested
    speed within their authority (holding both blocks for one step as
    they cross a boundary), the waysides throw switches for the trains'
    routes where no train is on them or authorized over them, and each
    train the CTC retires (``retired_trains``) is taken off the track."""

    def __init__(self, ctc: StubCtcOffice, line: str) -> None:
        self.ctc = ctc
        self.line = line
        self.graph = _GRAPHS[line]
        self.lengths = {b.block_id: b.length_m
                        for b in _LAYOUT[line].blocks}
        self.switches = {s: "normal" for s in _LAYOUT[line].switch_ids()}
        self.trains: dict[str, list[str]] = {}
        self.progress: dict[str, float] = {}
        self.reported: set[str] = set()
        # Every train released and retired, in order.
        self.released: list[str] = []
        self.retired: list[str] = []

    def occupied(self) -> set[str]:
        return {b for held in self.trains.values() for b in held}

    def step(self, dt: float) -> str | None:
        snap = self.ctc.snapshot()
        self._throw_switches(snap)
        self.reported = self.occupied()
        out = self.ctc.step(dt, reports(
            occupied=[(self.line, b) for b in self.reported],
            switches=[SwitchReport(self.line, s, p)
                      for s, p in self.switches.items()]))
        snap = self.ctc.snapshot()
        followed = {t.train_id: list(t.blocks) for t in snap.trains
                    if t.line == self.line}
        if followed != self.trains:
            return f"the CTC has {followed}, trains are {self.trains}"
        for gone in out.retired_trains:
            # The harness takes a retired train off the track.
            self.retired.append(gone.train_id)
            del self.trains[gone.train_id]
        exit_block = YARD_EXITS[self.line]
        for new in out.new_trains:
            # The harness puts a released train at the yard exit block,
            # which the CTC made sure was clear and held for it.
            if exit_block in self.occupied():
                return f"{new.train_id} released onto occupied {exit_block}"
            self.released.append(new.train_id)
            self.trains[new.train_id] = [exit_block]
            self.progress[new.train_id] = 0.0
        self._move(dt, out, snap)
        everything = [b for held in self.trains.values() for b in held]
        if len(set(everything)) != len(everything):
            return f"collision {self.trains}"
        return None

    def _throw_switches(self, snap) -> None:
        # A switch stays put while a train is authorized across it, or
        # stands on it.
        locked = set()
        for limit in snap.authorities:
            within = limit.route[:limit.blocks + 1]
            for a, b in zip(within, within[1:]):
                leg = self.graph.leg(a, b)
                if leg is not None:
                    locked.add(leg.switch_id)
        claims: dict[str, tuple[int, str]] = {}
        for limit in snap.authorities:
            for i, (a, b) in enumerate(zip(limit.route, limit.route[1:])):
                leg = self.graph.leg(a, b)
                if leg is not None and (leg.switch_id not in claims
                                        or claims[leg.switch_id][0] > i):
                    claims[leg.switch_id] = (i, leg.position)
        for switch_id, (_, position) in claims.items():
            if switch_id not in locked | self.occupied():
                self.switches[switch_id] = position

    def _move(self, dt: float, out, snap) -> None:
        # The speed for the block each train is in.
        speeds = {s.train_id: s.suggested_speed_mps
                  for s in out.track_controller.suggestions
                  if s.block_id == self.trains.get(s.train_id, [""])[-1]}
        limits = {a.train_id: a for a in snap.authorities}
        for train_id in sorted(self.trains):
            held = self.trains[train_id]
            if len(held) > 1:
                held.pop(0)
                continue
            limit = limits.get(train_id)
            length = self.lengths[held[-1]]
            self.progress[train_id] = min(
                length, self.progress[train_id]
                + speeds.get(train_id, 0) * dt)
            if self.progress[train_id] >= length and limit \
                    and limit.blocks:
                held.append(limit.route[1])
                self.progress[train_id] = 0.0


class EndToEndTest(unittest.TestCase):
    """Whole runs, start to finish, with nothing between the CTC and the
    trains but occupancy and switch states. Enough runs that they share
    the two-way zones (four Green runs met head-on in N before the
    zones), and never two trains in a zone going opposite ways."""

    def _run_line(self, line: str, run_ids: tuple[str, ...]) -> None:
        runs = tuple(t for t in SCHEDULE.trains
                     if t.line == line and t.train_id in run_ids)
        ctc = _loaded(schedule=Schedule("some runs", runs))
        self.ctc = ctc
        railway = _Railway(ctc, line)
        auto = ctc._auto
        plans = {p.train_id: p for p in auto.plans}
        most = 0
        # Where each run dwelt, and for how long.
        dwells: dict[str, list[tuple[str, float]]] = {
            train_id_for(line, run_id): [] for run_id in run_ids}
        started: dict[str, tuple[str, float]] = {}
        dt = 2.0
        for _ in range(int(3 * 3600 / dt)):
            problem = railway.step(dt)
            self.assertIsNone(problem)
            most = max(most, len(railway.trains))
            passes = []
            for train_id in railway.trains:
                at_ = auto.progress[train_id].at
                passes.extend(
                    (train_id, span)
                    for span in auto._spans[train_id]
                    if span[1] <= at_ <= span[2])
            for i, (a, span_a) in enumerate(passes):
                for b, span_b in passes[i + 1:]:
                    self.assertFalse(
                        a != b and opposed(plans[a].path, span_a,
                                           plans[b].path, span_b),
                        (a, span_a, b, span_b, railway.trains))
            snap = ctc.snapshot()
            for run in snap.scheduled_runs:
                if run.status == "dwelling" and run.train_id not in started:
                    started[run.train_id] = (run.stop_block_id,
                                             snap.elapsed_s)
                    self.assertEqual(
                        railway.trains[run.train_id][-1], run.stop_block_id)
                elif run.status != "dwelling" and run.train_id in started:
                    block, since = started.pop(run.train_id)
                    dwells[run.train_id].append(
                        (block, snap.elapsed_s - since))
            if all(r.status == "done" for r in snap.scheduled_runs):
                break
        statuses = {r.train_id: r.status for r in snap.scheduled_runs}
        self.assertEqual(set(statuses.values()), {"done"}, statuses)
        self.assertEqual(railway.trains, {})
        # Each run released once and retired once (D022).
        self.assertEqual(sorted(railway.released), sorted(dwells))
        self.assertEqual(sorted(railway.retired), sorted(dwells))
        # More than one train out at once.
        self.assertGreater(most, 1)
        expected = FILE_GREEN if line == "Green" else FILE_RED
        for train_id, stops in dwells.items():
            with self.subTest(train=train_id):
                # Its scheduled stations in the file's order, and no
                # others.
                self.assertEqual([block for block, _ in stops], expected)
                self.assertTrue(all(seconds >= DWELL_S
                                    for _, seconds in stops), stops)

    def test_green(self) -> None:
        self._run_line("Green", ("1", "2", "3", "4"))

    def test_red(self) -> None:
        self._run_line("Red", ("1", "2", "3"))

    def test_all_red_runs_pass_at_the_sidings(self) -> None:
        # All ten, three minutes apart: out on the main line, back on the
        # sidings beside 28 to 32 and 39 to 43, passing there. With one
        # zone from 16 to 52 they went one at a time, the last done at
        # 10:27; nor may the sidings and the main line beside them fill
        # up both ways at once (all ten stood still at 06:00).
        self._run_line("Red", tuple(str(n) for n in range(1, 11)))
        snap = self.ctc.snapshot()
        self.assertLess(snap.elapsed_s, 2 * 3600)


if __name__ == "__main__":
    unittest.main()
