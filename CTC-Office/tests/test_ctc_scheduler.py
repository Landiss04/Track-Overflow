"""Tests for automatic dispatch from the schedule (``ctc.scheduler``).

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import ScheduledRun, SwitchReport  # noqa: E402
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.routing import build_graphs  # noqa: E402
from ctc.schedule import (  # noqa: E402
    Schedule,
    load_schedule,
    parse_schedule,
)
from ctc.scheduler import (  # noqa: E402
    DONE,
    DWELL_S,
    EN_ROUTE,
    SIMULATION_START_S,
    Progress,
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
RED_ORDER = ["7", "16", "21", "25", "35", "45", "48", "60"]


def _loaded(automatic: bool = True,
            schedule: Schedule = SCHEDULE) -> StubCtcOffice:
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
    same track both ways, one scheduled train at a time."""

    def test_the_zones(self) -> None:
        zones = _loaded()._auto.zones
        green: dict[str, set[str]] = {}
        for block, zone in zones["Green"].items():
            green.setdefault(zone, set()).add(block)
        # Up N and back down, through the loop O to Q; down D to F, round
        # A to C, and back up.
        self.assertEqual(sorted(green.values(), key=len), [
            {str(n) for n in range(77, 101)},
            {str(n) for n in range(1, 29)}])
        # Red: out from 16, round the loop at 52, and back to 16.
        self.assertEqual(set(zones["Red"]),
                         {str(n) for n in range(16, 67)})
        # The yards are outside them.
        self.assertNotIn("63", zones["Green"])
        self.assertNotIn("9", zones["Red"])

    def test_out_and_back_track_is_a_zone(self) -> None:
        # One path out along 1-2-3 and back: all of it. A path that only
        # passes one way is not.
        self.assertEqual(set(two_way_zones([("1", "2", "3", "2", "1")])),
                         {"1", "2", "3"})
        self.assertEqual(two_way_zones([("1", "2", "3")]), {})

    def test_held_until_the_zone_is_clear(self) -> None:
        # G1 is in N (77 to 100) on its way to Poplar (88). G2, done at
        # Dormont (73), would go into N for Mt Lebanon (77): it waits.
        ctc = _loaded()
        step_at(ctc)
        plans = {p.train_id: p for p in ctc._auto.plans}
        ctc._auto.progress["G1"] = Progress(
            EN_ROUTE, 3, at=plans["G1"].path.index("80"))
        ctc._auto.progress["G2"] = Progress(
            "dwelling", 1, at=plans["G2"].stop_indexes[1])
        ctc.dispatch("G2", "Green", "73")
        step_at(ctc, at("G1", "80"), at("G2", "73"), dt=DWELL_S)
        run = _run(ctc, "G2")
        self.assertEqual((run.status, run.stop_block_id), ("held", "77"))
        self.assertEqual(_order(ctc, "G2"), "73")
        # G1's run is over: N is clear, and G2 goes on.
        ctc._auto.progress["G1"] = Progress(DONE, 18)
        step_at(ctc, at("G2", "73"))
        self.assertEqual((_run(ctc, "G2").status, _order(ctc, "G2")),
                         ("en route", "77"))


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
                         ("65", "7"))

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
        # R1 heading for its last stop, South Hills Junction (60).
        ctc = _loaded()
        step_at(ctc)
        ctc._auto.progress["R1"] = Progress(EN_ROUTE, len(RED_ORDER) - 1)
        ctc.dispatch("R1", "Red", "60")
        step_at(ctc, at("R1", "60", "Red"))
        self.assertEqual(_run(ctc, "R1").status, "dwelling")
        step_at(ctc, at("R1", "60", "Red"), dt=DWELL_S)
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
    trains but occupancy and switch states. Enough runs that they queue
    for the two-way zones (four Green runs met head-on in N before the
    zones), and never more than one train in a zone."""

    def _run_line(self, line: str, run_ids: tuple[str, ...]) -> None:
        runs = tuple(t for t in SCHEDULE.trains
                     if t.line == line and t.train_id in run_ids)
        ctc = _loaded(schedule=Schedule("some runs", runs))
        railway = _Railway(ctc, line)
        zones = ctc._auto.zones[line]
        # Where each run dwelt, and for how long.
        dwells: dict[str, list[tuple[str, float]]] = {
            train_id_for(line, run_id): [] for run_id in run_ids}
        started: dict[str, tuple[str, float]] = {}
        dt = 2.0
        for _ in range(int(3 * 3600 / dt)):
            problem = railway.step(dt)
            self.assertIsNone(problem)
            in_zone: dict[str, set[str]] = {}
            for train_id, blocks in railway.trains.items():
                for block in blocks:
                    if block in zones:
                        in_zone.setdefault(zones[block], set()).add(train_id)
            self.assertTrue(all(len(trains) == 1
                                for trains in in_zone.values()), in_zone)
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
        expected = GREEN_ORDER if line == "Green" else RED_ORDER
        for train_id, stops in dwells.items():
            with self.subTest(train=train_id):
                # Its scheduled stations in track order, and no others.
                self.assertEqual([block for block, _ in stops], expected)
                self.assertTrue(all(seconds >= DWELL_S
                                    for _, seconds in stops), stops)

    def test_green(self) -> None:
        self._run_line("Green", ("1", "2", "3", "4"))

    def test_red(self) -> None:
        self._run_line("Red", ("1", "2", "3"))


if __name__ == "__main__":
    unittest.main()
