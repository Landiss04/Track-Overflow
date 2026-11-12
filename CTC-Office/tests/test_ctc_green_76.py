"""Tests for how the CTC Office dispatches Green trains round switch 76.

Switch 76 is '76-77;77-101': normal 76 to 77, reverse 77 to 101 (77 is
its points block and Mt Lebanon station). Section N (77 to 85) is a
two-way zone: trains go up it, round the one-way loop 86 to 100, and come
back down it and out through 76 reverse to 101. These tests put trains
where they would be and check what the scheduler and the model make of
it: authorities, hold reasons, route requests and run statuses.

Facts about the Green wayside that the CTC cannot see are written into
the full-schedule test's stand-in railway, not assumed by the other
tests: it sets 76 only as the CTC asks and not while 76 or 77 is
occupied, and it zeroes the train on 75 while more than five of the
blocks 76 to 100 are occupied.

Run from the repo root with ``python -m pytest CTC-Office/tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import SwitchReport  # noqa: E402
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.schedule import Schedule  # noqa: E402
from ctc.scheduler import (  # noqa: E402
    DWELL_S,
    DWELLING,
    EN_ROUTE,
    HELD,
    SIMULATION_START_S,
    Progress,
)
from tests.occupancy import at, ready_office, step_at  # noqa: E402
from tests.test_ctc_scheduler import (  # noqa: E402
    GREEN_ORDER,
    SCHEDULE,
    _GRAPHS,
    _Railway,
    _loaded,
)

#: Wayside's congestion threshold: it zeroes the train on 75 while more
#: than this many of the blocks 76 to 100 are occupied.
WAYSIDE_LIMIT = 5


def _normal() -> list[SwitchReport]:
    return [SwitchReport("Green", "76", "normal")]


def _reverse() -> list[SwitchReport]:
    return [SwitchReport("Green", "76", "reverse")]


def _limit(ctc: StubCtcOffice, train_id: str):
    (found,) = [a for a in ctc.snapshot().authorities
                if a.train_id == train_id]
    return found


def _requests(ctc: StubCtcOffice) -> dict[str, str]:
    """The Green switch positions the CTC asks the Track Controller for."""
    return {c.switch_id: c.position
            for c in ctc.snapshot().outputs.track_controller.route_requests
            if c.line == "Green"}


def _status(ctc: StubCtcOffice, train_id: str) -> str:
    (run,) = [r for r in ctc.snapshot().scheduled_runs
              if r.train_id == train_id]
    return run.status


def _plans(ctc: StubCtcOffice):
    return {p.train_id: p for p in ctc._auto.plans}


def _down_in_n(ctc: StubCtcOffice, block: str = "80",
               train_id: str = "G1") -> None:
    """``train_id`` coming back down N at ``block`` on its way to 105."""
    path = _plans(ctc)[train_id].path
    ctc._auto.progress[train_id] = Progress(
        EN_ROUTE, GREEN_ORDER.index("105"),
        at=path.index(block, path.index("100")))
    ctc.dispatch(train_id, "Green", "105")


def _up_to_mt_lebanon(ctc: StubCtcOffice, train_id: str,
                      block: str) -> None:
    """``train_id`` on its way up to Mt Lebanon (77), at ``block``."""
    ctc._auto.progress[train_id] = Progress(
        EN_ROUTE, GREEN_ORDER.index("77"),
        at=_plans(ctc)[train_id].path.index(block))
    ctc.dispatch(train_id, "Green", "77")


def _done_at_dormont(ctc: StubCtcOffice, train_id: str) -> None:
    """``train_id`` done at Dormont (73): next, Mt Lebanon through N."""
    ctc._auto.progress[train_id] = Progress(
        DWELLING, GREEN_ORDER.index("73"),
        at=_plans(ctc)[train_id].stop_indexes[GREEN_ORDER.index("73")])
    ctc.dispatch(train_id, "Green", "73")


def _in_the_loop(ctc: StubCtcOffice, train_id: str, block: str) -> None:
    """``train_id`` sent up N and round the loop, now at ``block`` in it,
    heading for 105."""
    auto = ctc._auto
    plan = _plans(ctc)[train_id]
    back = [s for s in auto._spans[train_id] if s[0] == "77"][1]
    auto.progress[train_id] = Progress(
        EN_ROUTE, GREEN_ORDER.index("105"), at=plan.path.index(block),
        wait=auto._loop_wait(plan, back))
    ctc.dispatch(train_id, "Green", "105")


class DownTrainTest(unittest.TestCase):
    """A train coming back down N goes out through 76 reverse."""

    def _down(self, block: str, switches) -> StubCtcOffice:
        ctc = ready_office()
        ctc.dispatch("G1", "Green", "105")
        step_at(ctc, at("G1", block), switches=switches)
        step_at(ctc, at("G1", block), switches=switches)
        return ctc

    def test_waits_short_of_76_normal_and_asks_for_reverse(self) -> None:
        # On 79 with 76 normal: authority stops at 78, a block short of
        # 77, which locks the switch, because 76 is not set for it.
        ctc = self._down("79", _normal())
        limit = _limit(ctc, "G1")
        self.assertEqual((limit.end_block_id, limit.reason, limit.at),
                         ("78", "switch", "76"))
        self.assertEqual(limit.route[:limit.blocks + 1], ("79", "78"))
        self.assertEqual(_requests(ctc).get("76"), "reverse")

    def test_on_78_it_has_no_authority_and_still_asks(self) -> None:
        ctc = self._down("78", _normal())
        limit = _limit(ctc, "G1")
        self.assertEqual((limit.blocks, limit.end_block_id, limit.reason,
                          limit.at), (0, "78", "switch", "76"))
        self.assertEqual(_requests(ctc).get("76"), "reverse")

    def test_goes_through_77_once_76_reports_reverse(self) -> None:
        ctc = self._down("79", _reverse())
        limit = _limit(ctc, "G1")
        self.assertEqual((limit.end_block_id, limit.reason),
                         ("105", "destination"))
        self.assertEqual(limit.route[:5], ("79", "78", "77", "101", "102"))
        self.assertEqual(limit.blocks, 7)
        self.assertEqual(_requests(ctc).get("76"), "reverse")


class UpTrainTest(unittest.TestCase):
    """An up-train from 75 waits while a down-train is in N."""

    def _g2_at_75_with_g1_in_n(self) -> StubCtcOffice:
        ctc = _loaded()
        step_at(ctc)
        _down_in_n(ctc, "80")
        _done_at_dormont(ctc, "G2")
        step_at(ctc, at("G1", "80"), at("G2", "73"), dt=DWELL_S,
                switches=_normal())
        for block in ("74", "75"):
            step_at(ctc, at("G1", "80"), at("G2", block),
                    switches=_normal())
            step_at(ctc, at("G1", "80"), at("G2", block),
                    switches=_normal())
        return ctc

    def test_held_at_75_while_a_down_train_is_in_n(self) -> None:
        ctc = self._g2_at_75_with_g1_in_n()
        self.assertEqual(_status(ctc, "G2"), HELD)
        self.assertEqual(ctc._auto.hold_at("G2"), "75")
        limit = _limit(ctc, "G2")
        self.assertEqual((limit.blocks, limit.end_block_id, limit.reason),
                         (0, "75", "held"))
        # The down-train's request stands: G2 asks for no other position
        # of 76.
        self.assertEqual(_requests(ctc).get("76"), "reverse")

    def test_the_down_train_is_not_held_by_it(self) -> None:
        ctc = self._g2_at_75_with_g1_in_n()
        self.assertEqual(_status(ctc, "G1"), EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("G1"))
        self.assertEqual(_limit(ctc, "G1").reason, "switch")

    def test_released_once_the_down_train_is_onto_101(self) -> None:
        ctc = self._g2_at_75_with_g1_in_n()
        for block in ("78", "77"):
            step_at(ctc, at("G1", block), at("G2", "75"),
                    switches=_reverse())
            # Still in N (77 is its last block): G2 waits.
            self.assertEqual(_status(ctc, "G2"), HELD, block)
            self.assertEqual(_limit(ctc, "G2").reason, "held", block)
        step_at(ctc, at("G1", "101"), at("G2", "75"), switches=_reverse())
        self.assertEqual(_status(ctc, "G2"), EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("G2"))
        # It asks for 76 normal, and has authority once 76 reports it.
        self.assertEqual(_requests(ctc).get("76"), "normal")
        limit = _limit(ctc, "G2")
        self.assertEqual((limit.blocks, limit.reason, limit.at),
                         (0, "switch", "76"))
        # (G1 on 101 is next to 77, which keeps G2's authority one
        # block short of it; one block on, 77 is free for it.)
        step_at(ctc, at("G1", "102"), at("G2", "75"), switches=_normal())
        limit = _limit(ctc, "G2")
        self.assertEqual(limit.route[:3], ("75", "76", "77"))
        self.assertEqual((limit.blocks, limit.end_block_id, limit.reason),
                         (2, "77", "destination"))


class UpTrainsFollowingTest(unittest.TestCase):
    """Up-trains share N and the approach to it: only the direction rule
    holds a train at 75."""

    def _two_up(self, first: str, second: str) -> StubCtcOffice:
        ctc = _loaded()
        step_at(ctc)
        _up_to_mt_lebanon(ctc, "G1", first)
        _up_to_mt_lebanon(ctc, "G2", second)
        for _ in range(2):
            step_at(ctc, at("G1", first), at("G2", second),
                    switches=_normal())
        return ctc

    def _assert_not_held(self, ctc: StubCtcOffice) -> None:
        for train_id in ("G1", "G2"):
            self.assertEqual(_status(ctc, train_id), EN_ROUTE, train_id)
            self.assertIsNone(ctc._auto.hold_at(train_id), train_id)
            self.assertNotEqual(_limit(ctc, train_id).reason, "held")

    def test_follower_keeps_an_empty_block(self) -> None:
        # G1 on 75, G2 on 73: G2 may not go to 74, next to G1.
        ctc = self._two_up("75", "73")
        self._assert_not_held(ctc)
        self.assertEqual(_limit(ctc, "G1").route[:3], ("75", "76", "77"))
        self.assertEqual(_limit(ctc, "G1").blocks, 2)
        follower = _limit(ctc, "G2")
        self.assertEqual((follower.blocks, follower.reason, follower.at),
                         (0, "occupied", "75"))
        self.assertEqual(_requests(ctc).get("76"), "normal")

    def test_follower_closes_up_as_the_leader_goes(self) -> None:
        # G1 on 76: G2 on 74 stays; G1 on 77: G2 may go to 75, leaving 76
        # empty.
        ctc = self._two_up("76", "74")
        self.assertEqual(_limit(ctc, "G2").blocks, 0)
        step_at(ctc, at("G1", "77"), at("G2", "74"), switches=_normal())
        self.assertEqual(_status(ctc, "G1"), DWELLING)
        follower = _limit(ctc, "G2")
        self.assertEqual((follower.blocks, follower.end_block_id),
                         (1, "75"))
        self.assertEqual(_status(ctc, "G2"), EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("G2"))

    def test_nothing_is_held_when_n_is_empty(self) -> None:
        # No train in N or waiting at 99: a run done at Dormont goes on
        # to Mt Lebanon, and is not held on the way.
        ctc = _loaded()
        step_at(ctc)
        _done_at_dormont(ctc, "G2")
        step_at(ctc, at("G2", "73"), dt=DWELL_S, switches=_normal())
        self.assertEqual(_status(ctc, "G2"), EN_ROUTE)
        for block in ("74", "75"):
            step_at(ctc, at("G2", block), switches=_normal())
            self.assertEqual(_status(ctc, "G2"), EN_ROUTE, block)
            self.assertIsNone(ctc._auto.hold_at("G2"), block)
            self.assertNotEqual(_limit(ctc, "G2").reason, "held", block)

    def test_a_same_way_train_in_n_does_not_hold_it(self) -> None:
        # G1 is going up N (at 80) to Poplar (88); G2 on 75 follows.
        ctc = _loaded()
        step_at(ctc)
        path = _plans(ctc)["G1"].path
        ctc._auto.progress["G1"] = Progress(
            EN_ROUTE, GREEN_ORDER.index("88"), at=path.index("80"))
        ctc.dispatch("G1", "Green", "88")
        _up_to_mt_lebanon(ctc, "G2", "75")
        for _ in range(2):
            step_at(ctc, at("G1", "80"), at("G2", "75"),
                    switches=_normal())
        self.assertEqual(_status(ctc, "G2"), EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("G2"))
        self.assertGreater(_limit(ctc, "G2").blocks, 0)


class ReturningTrainTest(unittest.TestCase):
    """A train waiting at 99 to come back down N has it next."""

    def _g4_waiting_g3_up_in_n_g5_at_73(self) -> StubCtcOffice:
        # G3 is up N (at 80) for Poplar, so G4, round the loop, waits at
        # 99; G5 is done at Dormont and would go up N for the first time.
        ctc = _loaded()
        step_at(ctc)
        auto = ctc._auto
        plans = _plans(ctc)
        path = plans["G3"].path
        auto.progress["G3"] = Progress(
            EN_ROUTE, GREEN_ORDER.index("88"), at=path.index("80"))
        ctc.dispatch("G3", "Green", "88")
        back = [s for s in auto._spans["G4"] if s[0] == "77"][1]
        wait = auto._loop_wait(plans["G4"], back)
        leg = next(i for i, index in enumerate(plans["G4"].stop_indexes)
                   if index > back[1])
        self.assertEqual(plans["G4"].path[wait], "99")
        auto.progress["G4"] = Progress(HELD, leg=leg, at=wait, wait=wait)
        ctc.dispatch("G4", "Green", GREEN_ORDER[leg])
        _done_at_dormont(ctc, "G5")
        step_at(ctc, at("G3", "80"), at("G4", "99"), at("G5", "73"),
                dt=DWELL_S)
        return ctc

    def test_a_first_entry_waits_for_it_even_behind_a_same_way_train(
            self) -> None:
        ctc = self._g4_waiting_g3_up_in_n_g5_at_73()
        # G5 goes the way G3 does, but G4 waiting at 99 comes back the
        # other way: G5 is held, sent on to 75 and no further.
        self.assertEqual(_status(ctc, "G5"), HELD)
        for _ in range(2):
            step_at(ctc, at("G3", "80"), at("G4", "99"), at("G5", "75"))
        self.assertEqual(ctc._auto.hold_at("G5"), "75")
        limit = _limit(ctc, "G5")
        self.assertEqual((limit.blocks, limit.end_block_id, limit.reason),
                         (0, "75", "held"))
        self.assertEqual(_status(ctc, "G4"), HELD)

    def test_released_once_the_returning_train_has_cleared_n(self) -> None:
        ctc = self._g4_waiting_g3_up_in_n_g5_at_73()
        auto = ctc._auto
        for _ in range(2):
            step_at(ctc, at("G3", "80"), at("G4", "99"), at("G5", "75"))
        # G3 is round the loop: G4 comes back, 85 set for it.
        auto.progress["G3"] = Progress(
            EN_ROUTE, GREEN_ORDER.index("96"),
            at=_plans(ctc)["G3"].path.index("90"))
        ctc.dispatch("G3", "Green", "96")
        step_at(ctc, at("G3", "90"), at("G4", "99"), at("G5", "75"))
        step_at(ctc, at("G3", "90"), at("G4", "99"), at("G5", "75"))
        self.assertEqual(_status(ctc, "G4"), EN_ROUTE)
        # While it is in N coming down, G5 still waits.
        for block in ("85", "78", "77"):
            step_at(ctc, at("G3", "90"), at("G4", block), at("G5", "75"),
                    switches=_reverse())
            self.assertEqual(_status(ctc, "G5"), HELD, block)
            self.assertEqual(_limit(ctc, "G5").blocks, 0, block)
        # G4 is onto 101: G5 goes, and asks for 76 normal.
        step_at(ctc, at("G3", "90"), at("G4", "101"), at("G5", "75"),
                switches=_reverse())
        self.assertEqual(_status(ctc, "G5"), EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("G5"))
        self.assertEqual(_requests(ctc).get("76"), "normal")


class LoopCapTest(unittest.TestCase):
    """The scheduler lets only so many trains into the loop at once."""

    def _loop_count(self, ctc: StubCtcOffice) -> int:
        auto = ctc._auto
        return sum(auto._in_loop(plan, "77") for plan in auto.plans)

    def test_the_cap_on_schedule_v4_is_four(self) -> None:
        # The loop holds seven, a block apart; LOOP_LIMITS lets in four,
        # under the Green wayside's limit of five in 76 to 100.
        for name, schedule in (("file order", SCHEDULE),
                               ("track order", None)):
            with self.subTest(order=name):
                ctc = (_loaded(schedule=schedule) if schedule is not None
                       else _loaded())
                auto = ctc._auto
                plan = auto._plan["G1"]
                span = [s for s in auto._spans["G1"] if s[0] == "77"][0]
                self.assertEqual(plan.path[span[1]:span[2] + 1][0], "77")
                self.assertEqual(auto._loop_room(plan, span), 4)

    # Loop blocks the placed trains stand on, one apart.
    LOOP_BLOCKS = ("87", "89", "91", "93", "95", "97", "99")

    def _loop_with(self, count: int) -> StubCtcOffice:
        """``count`` trains in the loop, and G8 done at Dormont."""
        ctc = _loaded()
        step_at(ctc)
        placed = []
        for number, block in zip(range(1, count + 1), self.LOOP_BLOCKS):
            train_id = f"G{number}"
            _in_the_loop(ctc, train_id, block)
            placed.append(at(train_id, block))
        _done_at_dormont(ctc, "G8")
        step_at(ctc, *placed, at("G8", "73"), dt=DWELL_S)
        # G8 is not counted until it is let in.
        self.assertEqual(self._loop_count(ctc)
                         - (_status(ctc, "G8") == EN_ROUTE), count)
        return ctc

    def test_a_full_loop_holds_the_next_train_at_75(self) -> None:
        ctc = self._loop_with(4)
        self.assertEqual(_status(ctc, "G8"), HELD)
        self.assertEqual(ctc._auto.hold_at("G8"), "75")

    def test_one_place_left_lets_it_in(self) -> None:
        ctc = self._loop_with(3)
        self.assertEqual(_status(ctc, "G8"), EN_ROUTE)
        self.assertIsNone(ctc._auto.hold_at("G8"))

    def test_a_place_freed_lets_the_held_train_in(self) -> None:
        ctc = self._loop_with(4)
        self.assertEqual(_status(ctc, "G8"), HELD)
        # G4 is back in N: it no longer counts in the loop.
        auto = ctc._auto
        auto.progress["G4"] = Progress(
            EN_ROUTE, GREEN_ORDER.index("105"),
            at=_plans(ctc)["G4"].path.index(
                "85", _plans(ctc)["G4"].path.index("100")))
        placed = [at(f"G{n}", b) for n, b in
                  zip(range(1, 4), self.LOOP_BLOCKS)]
        step_at(ctc, *placed, at("G4", "85"), at("G8", "73"))
        self.assertLess(self._loop_count(ctc), 4)

    def test_new_entries_wait_while_76_to_100_would_hold_over_five(
            self) -> None:
        # With six trains in 76 to 100 the Green wayside zeroes the train
        # on 75 whatever authority the CTC gives it, and the CTC cannot
        # see that: given its pass into N, that train would hold N, which
        # the trains round the loop wait for. The cap of four keeps the
        # CTC from ever sending it.
        ctc = self._loop_with(6)
        self.assertEqual(_status(ctc, "G8"), HELD)
        self.assertEqual(ctc._auto.hold_at("G8"), "75")


class _Green76Railway(_Railway):
    """The Green line as the Track Model and wayside make it, for the
    parts the CTC depends on at 76: every switch is set only to the CTC's
    request and never while a block that locks it is occupied; the train
    on 75 is held (zero speed, and it does not go on) while more than
    ``WAYSIDE_LIMIT`` of the blocks 76 to 100 are occupied."""

    def __init__(self, ctc: StubCtcOffice) -> None:
        super().__init__(ctc, "Green")
        self.requests: dict[str, str] = {}
        # Most trains seen at once in 76 to 100.
        self.most_in_76_100 = 0

    def _in_76_100(self) -> int:
        # What the wayside counts: the Track Model reports one block per
        # train, the block it is in (``_controller_outputs``).
        return sum(1 for blocks in self.trains.values()
                   if 76 <= int(blocks[-1]) <= 100)

    def _crowded(self) -> bool:
        return self._in_76_100() > WAYSIDE_LIMIT

    def step(self, dt: float) -> str | None:
        problem = super().step(dt)
        self.requests = {
            c.switch_id: c.position
            for c in self.ctc.snapshot().outputs.track_controller
            .route_requests if c.line == self.line}
        self.most_in_76_100 = max(self.most_in_76_100, self._in_76_100())
        return problem

    def _throw_switches(self, snap) -> None:
        occupied = self.occupied()
        for switch_id, position in self.requests.items():
            if (self.switches[switch_id] != position
                    and not self.graph.locking_blocks(switch_id)
                    & occupied):
                self.switches[switch_id] = position

    def _move(self, dt: float, out, snap) -> None:
        speeds = {s.train_id: s.suggested_speed_mps
                  for s in out.track_controller.suggestions
                  if s.block_id == self.trains.get(s.train_id, [""])[-1]}
        limits = {a.train_id: a for a in snap.authorities}
        crowded = self._crowded()
        for train_id in sorted(self.trains):
            held = self.trains[train_id]
            if len(held) > 1:
                held.pop(0)
                continue
            limit = limits.get(train_id)
            speed = speeds.get(train_id, 0)
            if held[-1] == "75" and crowded:
                speed = 0
            length = self.lengths[held[-1]]
            self.progress[train_id] = min(
                length, self.progress[train_id] + speed * dt)
            if (self.progress[train_id] >= length and limit and limit.blocks
                    and not (held[-1] == "75" and crowded)):
                held.append(limit.route[1])
                self.progress[train_id] = 0.0


class FullGreenScheduleTest(unittest.TestCase):
    """All ten Green runs of schedule_v4, with the CTC and a railway that
    obeys the wayside's rules at 76 and nothing else between them."""

    DT = 4.0
    #: Latest finish: 09:30, in seconds after the 05:00 start.
    FINISH_BY_S = 4.5 * 3600
    #: Longest a train may stand with no authority near 76 or 99 to 101.
    STAND_MAX_S = 600
    #: No train changing block for this long ends the run: it is stuck.
    DEADLOCK_S = 1800
    NEAR_76 = ("74", "75", "76", "77", "78", "99", "100", "101")

    @classmethod
    def setUpClass(cls) -> None:
        runs = tuple(t for t in SCHEDULE.trains if t.line == "Green")
        cls.ctc = _loaded(schedule=Schedule("Green", runs))
        railway = _Green76Railway(cls.ctc)
        cls.railway = railway
        cls.problem = None
        cls.elapsed_s = 0.0
        cls.finished = False
        cls.deadlocked = False
        cls.stood: tuple[str, str, float] | None = None
        cls.worst_stand = (0.0, "", "")
        cls.most_in_loop = 0
        cls.room = None
        standing: dict[str, tuple[str, float]] = {}
        last_heads: dict[str, tuple[str, ...]] = {}
        last_move_s = 0.0
        for _ in range(int(cls.FINISH_BY_S / cls.DT)):
            cls.problem = railway.step(cls.DT)
            if cls.problem is not None:
                break
            cls.elapsed_s += cls.DT
                    # The schedule is planned again when it starts.
            auto = cls.ctc._auto
            if cls.room is None:
                cls.room = auto._loop_room(
                    auto._plan["G1"],
                    [s for s in auto._spans["G1"] if s[0] == "77"][0])
            cls.most_in_loop = max(cls.most_in_loop, sum(
                auto._in_loop(plan, "77") for plan in auto.plans))
            snap = cls.ctc.snapshot()
            limits = {a.train_id: a for a in snap.authorities}
            for train_id, blocks in railway.trains.items():
                limit = limits.get(train_id)
                block = blocks[-1]
                if (limit is not None and limit.blocks == 0
                        and limit.reason != "destination"
                        and block in cls.NEAR_76):
                    since = (standing[train_id][1]
                             if train_id in standing
                             and standing[train_id][0] == block else 0.0)
                    standing[train_id] = (block, since + cls.DT)
                    if standing[train_id][1] > cls.worst_stand[0]:
                        cls.worst_stand = (standing[train_id][1], train_id,
                                           block)
                    if (standing[train_id][1] > cls.STAND_MAX_S
                            and cls.stood is None):
                        cls.stood = (train_id, block, standing[train_id][1])
                else:
                    standing.pop(train_id, None)
            heads = {t: tuple(b) for t, b in railway.trains.items()}
            if heads != last_heads:
                last_heads, last_move_s = heads, cls.elapsed_s
            elif cls.elapsed_s - last_move_s > cls.DEADLOCK_S:
                cls.deadlocked = True
                break
            if all(r.status == "done" for r in snap.scheduled_runs):
                cls.finished = True
                break

    def _clock(self) -> str:
        t = int(SIMULATION_START_S + self.elapsed_s)
        return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"

    def test_the_railway_follows_the_ctc(self) -> None:
        self.assertIsNone(self.problem)

    def test_loop_never_over_its_cap(self) -> None:
        # What the scheduler lets into N heading up or round the loop,
        # and the loop's blocks themselves.
        self.assertEqual(self.room, 4)
        self.assertLessEqual(self.most_in_loop, self.room)
        self.assertGreater(self.most_in_loop, 0)

    def test_the_wayside_never_has_to_hold_75(self) -> None:
        # The Green wayside holds the train on 75 while more than five
        # of 76 to 100 are occupied: the CTC never lets it get there.
        self.assertLessEqual(self.railway.most_in_76_100, WAYSIDE_LIMIT)

    def test_all_ten_runs_finish_by_0930(self) -> None:
        # With seven let into the loop, six trains stood in 76 to 100,
        # the wayside zeroed the train on 75, and it held N, which the
        # trains round the loop waited for: a deadlock. LOOP_LIMITS (4)
        # keeps 76 to 100 under the wayside's limit.
        snap = self.ctc.snapshot()
        statuses = {r.train_id: r.status for r in snap.scheduled_runs}
        self.assertTrue(self.finished,
                        f"{'deadlocked' if self.deadlocked else 'ran out'}"
                        f" at {self._clock()}: {statuses}; trains "
                        f"{self.railway.trains}")
        self.assertLessEqual(self.elapsed_s, self.FINISH_BY_S)

    def test_no_train_stands_with_no_authority_near_76(self) -> None:
        # A run used to keep a pass into N it claimed while still far
        # from it, and a train waiting at 99 to come back waited for it
        # (G1 over 1000 s at 99). Such a run now gives the pass up while
        # it is not in N yet (``AutoDispatcher._reach``).
        self.assertIsNone(
            self.stood,
            f"(train, block, seconds) stood with no authority past "
            f"{self.STAND_MAX_S} s: first {self.stood}; longest "
            f"(seconds, train, block) {self.worst_stand}; trains now "
            f"{self.railway.trains}")


if __name__ == "__main__":
    unittest.main()
