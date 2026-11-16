"""Tests for a train's queued stops in Manual mode (``queue_stop``,
``remove_stop``, ``move_stop``).

A train's itinerary is its order (the stop it is heading for) and the
stops queued after it. It dwells ``DWELL_S`` (D007) once stopped at a
stop, then heads for the next; after the last it stays there.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import DispatchOrder  # noqa: E402
from ctc.model import (  # noqa: E402
    MAX_STOPS,
    InvalidInputError,
    InvalidTimeStepError,
    StubCtcOffice,
    UnsafeActionError,
)
from ctc.schedule import load_schedule  # noqa: E402
from ctc.scheduler import DWELL_S  # noqa: E402
from tests.occupancy import at, ready_office, reports, step_at  # noqa: E402
from tests.realistic_railway import RealisticRailway  # noqa: E402

_SCHEDULE = Path(__file__).resolve().parents[2] / "utils" / "schedule_v4.json"


def _order(ctc: StubCtcOffice, train_id: str = "T1") -> str | None:
    return {o.train_id: o.destination_block_id
            for o in ctc.snapshot().orders}.get(train_id)


def _queued(ctc: StubCtcOffice, train_id: str = "T1") -> list[str]:
    return [s.destination_block_id for s in ctc.snapshot().queued_stops
            if s.train_id == train_id]


def _stops(ctc: StubCtcOffice, train_id: str = "T1") -> list[str]:
    order = _order(ctc, train_id)
    return ([order] if order else []) + _queued(ctc, train_id)


def _wait(ctc: StubCtcOffice, seconds: float, *trains,
          step_s: float = 1.0) -> None:
    """Step ``seconds`` with ``trains`` standing where they are."""
    elapsed = 0.0
    while elapsed < seconds - 1e-9:
        step_at(ctc, *trains, dt=step_s)
        elapsed += step_s


def _stop(ctc: StubCtcOffice, train: str, block: str) -> None:
    """Step with ``train`` at ``block`` until the CTC takes it to have
    stopped there: the fastest it could still be going, braking since it
    was told to stop, is 0 (``_at_a_stand``). Its dwell starts then."""
    for _ in range(120):
        step_at(ctc, at(train, block), dt=1.0)
        if ctc._tracker.trains[train].speed_mps <= 0:
            return
    raise AssertionError(f"{train} never stopped at {block}")


def _three_stops(train: str = "T1") -> StubCtcOffice:
    """T1 on Green 62, heading for Glenbury (65), then Dormont (73),
    then Mt Lebanon (77)."""
    ctc = ready_office()
    step_at(ctc, at(train, "62"))
    ctc.queue_stop(train, "Green", "65", 5 * 3600 + 600)
    ctc.queue_stop(train, "Green", "73", 5 * 3600 + 1200)
    ctc.queue_stop(train, "Green", "77")
    return ctc


class QueueStopTest(unittest.TestCase):
    """Adding stops."""

    def test_a_train_with_no_order_is_dispatched_to_its_first_stop(
            self) -> None:
        ctc = ready_office()
        ctc.queue_stop("G1", "Green", "65", 5 * 3600 + 600)
        self.assertEqual(ctc.snapshot().orders, (DispatchOrder(
            "G1", "Green", "65", 5 * 3600 + 600),))
        self.assertEqual(ctc.snapshot().queued_stops, ())

    def test_later_stops_queue_after_the_last_with_their_arrival(
            self) -> None:
        ctc = _three_stops()
        self.assertEqual(_stops(ctc), ["65", "73", "77"])
        self.assertEqual(
            [(s.destination_block_id, s.arrival_s)
             for s in ctc.snapshot().queued_stops],
            [("73", 5 * 3600 + 1200), ("77", None)])

    def test_a_stop_may_be_any_block_of_the_line(self) -> None:
        ctc = _three_stops()
        ctc.queue_stop("T1", "Green", "70")      # not a station
        self.assertEqual(_stops(ctc), ["65", "73", "77", "70"])

    def test_refused_like_a_dispatch(self) -> None:
        ctc = _three_stops()
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "100", True)
        with self.assertRaisesRegex(UnsafeActionError, "closed"):
            ctc.queue_stop("T1", "Green", "100")
        with self.assertRaises(UnsafeActionError):
            ctc.queue_stop("T1", "Red", "16")    # another line
        with self.assertRaises(InvalidInputError):
            ctc.queue_stop("T1", "Green", "999")
        with self.assertRaises(InvalidInputError):
            ctc.queue_stop("T1", "Green", "88", float("nan"))
        self.assertEqual(_stops(ctc), ["65", "73", "77"])

    def test_not_on_another_line_than_its_order_in_the_yard(self) -> None:
        ctc = ready_office()
        ctc.queue_stop("G1", "Green", "65")      # waiting in the yard
        with self.assertRaisesRegex(UnsafeActionError, "Green line"):
            ctc.queue_stop("G1", "Red", "16")
        self.assertEqual(_stops(ctc, "G1"), ["65"])

    def test_the_same_block_as_the_last_stop_is_refused(self) -> None:
        ctc = _three_stops()
        with self.assertRaisesRegex(InvalidInputError, "last stop"):
            ctc.queue_stop("T1", "Green", "77")

    def test_at_most_max_stops(self) -> None:
        ctc = ready_office()
        blocks = [str(b) for b in range(64, 64 + MAX_STOPS)]
        for block in blocks:
            ctc.queue_stop("T1", "Green", block)
        self.assertEqual(_stops(ctc), blocks)
        with self.assertRaisesRegex(InvalidInputError, str(MAX_STOPS)):
            ctc.queue_stop("T1", "Green", "100")

    def test_not_for_a_run_of_the_loaded_schedule(self) -> None:
        ctc = ready_office()
        ctc.load_schedule(load_schedule(_SCHEDULE))
        ctc.set_automatic_mode(True)
        ctc.step(0.1, reports())
        run = next(o.train_id for o in ctc.snapshot().orders)
        with self.assertRaisesRegex(InvalidInputError, "schedule"):
            ctc.queue_stop(run, "Green", "100")


class AdvanceTest(unittest.TestCase):
    """A train dwells at each stop, then heads for the next."""

    def test_dwells_at_each_stop_then_heads_for_the_next(self) -> None:
        ctc = _three_stops()
        # Not there yet: no dwell counts.
        _wait(ctc, 2 * DWELL_S, at("T1", "64"))
        self.assertEqual(_stops(ctc), ["65", "73", "77"])
        # Stopped at Glenbury: on to Dormont after the dwell, not before.
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S - 2, at("T1", "65"))
        self.assertEqual(_order(ctc), "65")
        _wait(ctc, 3, at("T1", "65"))
        self.assertEqual(_stops(ctc), ["73", "77"])
        (limit,) = ctc.snapshot().authorities
        self.assertEqual(limit.route[-1], "73")
        _stop(ctc, "T1", "73")
        _wait(ctc, DWELL_S + 1, at("T1", "73"))
        self.assertEqual(_stops(ctc), ["77"])

    def test_stays_at_its_last_stop(self) -> None:
        ctc = _three_stops()
        for block in ("65", "73", "77"):
            _stop(ctc, "T1", block)
            _wait(ctc, DWELL_S + 1, at("T1", block))
        _wait(ctc, 10 * DWELL_S, at("T1", "77"))
        self.assertEqual(_stops(ctc), ["77"])
        (limit,) = ctc.snapshot().authorities
        self.assertEqual((limit.blocks, limit.reason), (0, "destination"))

    def test_a_block_stop_is_dwelt_at_as_well(self) -> None:
        ctc = ready_office()
        step_at(ctc, at("T1", "68"))
        ctc.queue_stop("T1", "Green", "70")
        ctc.queue_stop("T1", "Green", "73")
        _stop(ctc, "T1", "70")
        _wait(ctc, DWELL_S - 2, at("T1", "70"))
        self.assertEqual(_order(ctc), "70")
        _wait(ctc, 3, at("T1", "70"))
        self.assertEqual(_stops(ctc), ["73"])

    def test_a_train_in_the_yard_does_not_move_on(self) -> None:
        ctc = ready_office()
        ctc.queue_stop("G1", "Green", "65")
        ctc.queue_stop("G1", "Green", "73")
        # The yard exit is held, so G1 stays in the yard.
        _wait(ctc, 3 * DWELL_S, at("T9", "63"))
        self.assertEqual(_stops(ctc, "G1"), ["65", "73"])

    def test_a_lost_train_does_not_move_on(self) -> None:
        ctc = _three_stops()
        step_at(ctc, at("T1", "65"))
        # Its block clears outside the yard: lost.
        _wait(ctc, 3 * DWELL_S)
        self.assertIn("T1", ctc.snapshot().lost_trains)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])

    def test_moves_on_in_automatic_mode_too_and_keeps_its_stops(
            self) -> None:
        ctc = _three_stops()
        ctc.set_automatic_mode(True)
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S + 1, at("T1", "65"))
        self.assertEqual(_stops(ctc), ["73", "77"])
        ctc.set_automatic_mode(False)
        self.assertEqual(_stops(ctc), ["73", "77"])

    def test_waits_for_a_line_not_ready(self) -> None:
        ctc = _three_stops()
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S - 1, at("T1", "65"))
        for _ in range(5):
            ctc.step(1.0, reports(at("T1", "65"), ready=False))
        self.assertEqual(_order(ctc), "65")
        step_at(ctc, at("T1", "65"))
        self.assertEqual(_stops(ctc), ["73", "77"])


class RemoveStopTest(unittest.TestCase):
    """Removing a stop."""

    def test_a_queued_stop(self) -> None:
        ctc = _three_stops()
        ctc.remove_stop("T1", 1)
        self.assertEqual(_stops(ctc), ["65", "77"])

    def test_the_stop_it_heads_for_sends_it_on_to_the_next(self) -> None:
        ctc = _three_stops()
        step_at(ctc, at("T1", "63"))
        ctc.remove_stop("T1", 0)
        self.assertEqual(_stops(ctc), ["73", "77"])
        self.assertEqual(ctc.snapshot().orders[0].arrival_s,
                         5 * 3600 + 1200)
        step_at(ctc, at("T1", "63"))
        (limit,) = ctc.snapshot().authorities
        self.assertEqual(limit.route[-1], "73")

    def test_retargeting_never_gives_authority_past_another_train(
            self) -> None:
        ctc = _three_stops()
        step_at(ctc, at("T1", "64"), at("T2", "68"))
        ctc.remove_stop("T1", 0)
        step_at(ctc, at("T1", "64"), at("T2", "68"))
        limit = {a.train_id: a for a in ctc.snapshot().authorities}["T1"]
        self.assertEqual(limit.route[-1], "73")
        # One empty block between trains: 65 and 66 at most.
        self.assertLessEqual(limit.blocks, 2)
        self.assertNotIn("68", limit.route[1:limit.blocks + 1])

    def test_its_only_stop_is_refused(self) -> None:
        ctc = ready_office()
        ctc.queue_stop("T1", "Green", "65")
        with self.assertRaisesRegex(InvalidInputError, "only stop"):
            ctc.remove_stop("T1", 0)
        self.assertEqual(_stops(ctc), ["65"])

    def test_a_stop_that_is_not_there_is_refused(self) -> None:
        ctc = _three_stops()
        for index in (3, -1, True, "1", 1.0):
            with self.subTest(index=index), \
                    self.assertRaises(InvalidInputError):
                ctc.remove_stop("T1", index)
        with self.assertRaises(InvalidInputError):
            ctc.remove_stop("T9", 0)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])

    def test_refused_and_unchanged_if_the_next_cannot_be_dispatched(
            self) -> None:
        ctc = _three_stops()
        ctc.stage_inputs(reports(at("T1", "62"), ready=False))
        with self.assertRaisesRegex(UnsafeActionError, "not ready"):
            ctc.remove_stop("T1", 0)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])
        ctc.remove_stop("T1", 2)      # a queued stop: nothing dispatched
        self.assertEqual(_stops(ctc), ["65", "73"])


class MoveStopTest(unittest.TestCase):
    """Reordering stops."""

    def test_queued_stops(self) -> None:
        ctc = _three_stops()
        ctc.move_stop("T1", 2, 1)
        self.assertEqual(_stops(ctc), ["65", "77", "73"])

    def test_a_new_first_stop_is_the_one_it_heads_for_at_once(
            self) -> None:
        ctc = _three_stops()
        ctc.move_stop("T1", 1, 0)
        self.assertEqual(_stops(ctc), ["73", "65", "77"])
        self.assertEqual(ctc.snapshot().orders[0], DispatchOrder(
            "T1", "Green", "73", 5 * 3600 + 1200))
        step_at(ctc, at("T1", "62"))
        (limit,) = ctc.snapshot().authorities
        self.assertEqual(limit.route[-1], "73")

    def test_moving_the_first_down_retargets_it(self) -> None:
        ctc = _three_stops()
        ctc.move_stop("T1", 0, 2)
        self.assertEqual(_stops(ctc), ["73", "77", "65"])

    def test_a_dwell_under_way_restarts_with_a_new_first_stop(self) -> None:
        ctc = _three_stops()
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S - 2, at("T1", "65"))
        ctc.move_stop("T1", 2, 1)        # not the first: dwell goes on
        _wait(ctc, 3, at("T1", "65"))
        self.assertEqual(_stops(ctc), ["77", "73"])

    def test_out_of_range_is_refused(self) -> None:
        ctc = _three_stops()
        with self.assertRaises(InvalidInputError):
            ctc.move_stop("T1", 0, 3)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])

    def test_refused_and_unchanged_if_the_new_first_cannot_be_dispatched(
            self) -> None:
        ctc = _three_stops()
        ctc.stage_inputs(reports(at("T1", "62"), ready=False))
        with self.assertRaises(UnsafeActionError):
            ctc.move_stop("T1", 2, 0)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])


class StaleListTest(unittest.TestCase):
    """An action on the stops as the dispatcher saw them is refused,
    and changes nothing, once the train has moved on: an index then
    names another stop."""

    def test_remove_with_the_stops_shown(self) -> None:
        ctc = _three_stops()
        ctc.remove_stop("T1", 1, ["65", "73", "77"])
        self.assertEqual(_stops(ctc), ["65", "77"])

    def test_remove_after_the_train_moved_on_is_refused(self) -> None:
        ctc = _three_stops()
        shown = _stops(ctc)                 # 65, 73, 77
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S + 1, at("T1", "65"))
        self.assertEqual(_stops(ctc), ["73", "77"])
        # The dispatcher meant 73 (stop 2 as shown); stop 2 is now 77.
        with self.assertRaisesRegex(InvalidInputError, "changed"):
            ctc.remove_stop("T1", 1, shown)
        self.assertEqual(_stops(ctc), ["73", "77"])

    def test_move_after_the_train_moved_on_is_refused(self) -> None:
        ctc = _three_stops()
        shown = _stops(ctc)
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S + 1, at("T1", "65"))
        # ▲ on 73 (stop 2 as shown) would now move 77 ahead of 73.
        with self.assertRaisesRegex(InvalidInputError, "changed"):
            ctc.move_stop("T1", 1, 0, shown)
        self.assertEqual(_stops(ctc), ["73", "77"])

    def test_expected_must_be_block_ids(self) -> None:
        ctc = _three_stops()
        for expected in ("65", [65, 73, 77]):
            with self.subTest(expected=expected), \
                    self.assertRaises(InvalidInputError):
                ctc.remove_stop("T1", 1, expected)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])


class RejectedStepTest(unittest.TestCase):
    """A refused step changes nothing: not the stops, nor a dwell."""

    def test_the_stops_and_the_dwell_stand(self) -> None:
        ctc = _three_stops()
        _stop(ctc, "T1", "65")
        _wait(ctc, DWELL_S - 2, at("T1", "65"))
        before = (dict(ctc._queues), dict(ctc._dwell_since),
                  ctc.snapshot().orders)
        for dt in (0.0, float("nan")):
            with self.assertRaises(InvalidTimeStepError):
                ctc.step(dt, reports(at("T1", "65")))
        with self.assertRaises(InvalidInputError):
            ctc.step(5.0, reports(at("T1", "999")))
        self.assertEqual((dict(ctc._queues), dict(ctc._dwell_since),
                          ctc.snapshot().orders), before)


class CanStopTest(unittest.TestCase):
    """A new first stop never takes back authority a moving train can
    no longer stop within: it would run past it, into blocks then free
    for other trains."""

    def _moving(self) -> StubCtcOffice:
        # T1 on its way from 62 through 63 to 64, told to keep going.
        ctc = _three_stops()
        for block in ("63", "64"):
            step_at(ctc, at("T1", block))
        ctc.queue_stop("T1", "Green", "64")
        return ctc

    def test_a_stop_further_on_is_taken(self) -> None:
        ctc = self._moving()
        ctc.remove_stop("T1", 0)
        self.assertEqual(_stops(ctc), ["73", "77", "64"])

    def test_the_block_it_is_running_through_is_refused(self) -> None:
        ctc = self._moving()
        (limit,) = ctc.snapshot().authorities
        self.assertGreater(limit.blocks, 0)
        with self.assertRaisesRegex(UnsafeActionError, "too fast"):
            ctc.move_stop("T1", 3, 0)
        self.assertEqual(_stops(ctc), ["65", "73", "77", "64"])

    def test_a_standing_train_can_be_sent_anywhere(self) -> None:
        ctc = _three_stops()
        ctc.queue_stop("T1", "Green", "62")
        # At a stand at Glenbury, before its dwell is up.
        _stop(ctc, "T1", "65")
        ctc.move_stop("T1", 3, 0)
        self.assertEqual(_stops(ctc), ["62", "65", "73", "77"])


class ScheduleTest(unittest.TestCase):
    """A manual train that a loaded schedule then runs (same train ID)
    makes the schedule's stops, never queued ones."""

    def test_loading_drops_the_queue_of_a_train_the_schedule_runs(
            self) -> None:
        ctc = ready_office()
        step_at(ctc, at("G1", "62"))
        for block in ("65", "70", "73"):
            ctc.queue_stop("G1", "Green", block)
        ctc.queue_stop("G9", "Green", "65")
        ctc.queue_stop("G9", "Green", "70")
        ctc.load_schedule(load_schedule(_SCHEDULE))
        self.assertEqual(_queued(ctc, "G1"), [])
        self.assertEqual(_stops(ctc, "G1"), ["65"])
        if "G9" not in ctc._auto.progress:
            self.assertEqual(_stops(ctc, "G9"), ["65", "70"])

    def test_a_run_is_never_sent_on_by_a_queue(self) -> None:
        ctc = ready_office()
        ctc.load_schedule(load_schedule(_SCHEDULE))
        ctc.set_automatic_mode(True)
        ctc.step(0.1, reports())
        run = next(o for o in ctc.snapshot().orders)
        # A queue that got onto a run some other way.
        ctc._queues[run.train_id] = [DispatchOrder(
            run.train_id, run.line, "70")]
        ctc.step(0.1, reports())
        self.assertEqual(_queued(ctc, run.train_id), [])


class OtherActionsTest(unittest.TestCase):
    """Dispatch, return to yard, closures and retirement."""

    def test_a_reroute_replaces_the_stop_it_heads_for_only(self) -> None:
        ctc = _three_stops()
        ctc.dispatch("T1", "Green", "70")
        self.assertEqual(_stops(ctc), ["70", "73", "77"])

    def test_return_to_yard_queues_the_yard_last(self) -> None:
        # The yard (57) goes after the stops it has, which it still
        # makes (Landis 2026-11-16).
        ctc = _three_stops()
        ctc.return_to_yard("T1")
        self.assertEqual(_stops(ctc), ["65", "73", "77", "57"])
        snap = ctc.snapshot()
        self.assertEqual((snap.returning_trains, snap.yard_queued),
                         ((), ("T1",)))
        with self.assertRaisesRegex(InvalidInputError, "already"):
            ctc.return_to_yard("T1")

    def test_the_yard_stays_last(self) -> None:
        ctc = _three_stops()
        ctc.return_to_yard("T1")
        # A stop queued now goes before the yard.
        ctc.queue_stop("T1", "Green", "70")
        self.assertEqual(_stops(ctc), ["65", "73", "77", "70", "57"])
        # Neither the yard nor a stop after it.
        for move in ((4, 1), (3, 4)):
            with self.subTest(move=move):
                with self.assertRaisesRegex(InvalidInputError, "last"):
                    ctc.move_stop("T1", *move)
                self.assertEqual(_stops(ctc),
                                 ["65", "73", "77", "70", "57"])
        # The other stops still move among themselves.
        ctc.move_stop("T1", 3, 1)
        self.assertEqual(_stops(ctc), ["65", "70", "73", "77", "57"])

    def test_it_goes_back_once_the_yard_is_next(self) -> None:
        ctc = _three_stops()
        ctc.return_to_yard("T1")
        for _ in range(3):
            ctc.remove_stop("T1", 0)
        self.assertEqual(_stops(ctc), ["57"])
        snap = ctc.snapshot()
        self.assertEqual((snap.returning_trains, snap.yard_queued),
                         (("T1",), ()))
        # A stop given now goes before the yard: it is no longer on its
        # way back, but still will be.
        ctc.queue_stop("T1", "Green", "65")
        self.assertEqual(_stops(ctc), ["65", "57"])
        snap = ctc.snapshot()
        self.assertEqual((snap.returning_trains, snap.yard_queued),
                         ((), ("T1",)))

    def test_removing_the_yard_withdraws_the_return(self) -> None:
        ctc = _three_stops()
        ctc.return_to_yard("T1")
        ctc.remove_stop("T1", 3)
        self.assertEqual(_stops(ctc), ["65", "73", "77"])
        self.assertEqual(ctc.snapshot().yard_queued, ())
        # It can be sent back again.
        ctc.return_to_yard("T1")
        self.assertEqual(_stops(ctc), ["65", "73", "77", "57"])

    def test_after_its_last_dwell_it_heads_for_the_yard(self) -> None:
        ctc = ready_office()
        step_at(ctc, at("T1", "62"))
        ctc.queue_stop("T1", "Green", "65")
        ctc.return_to_yard("T1")
        self.assertEqual(_stops(ctc), ["65", "57"])
        _wait(ctc, DWELL_S + 2, at("T1", "65"))
        self.assertEqual(_stops(ctc), ["57"])
        self.assertEqual(ctc.snapshot().returning_trains, ("T1",))

    def test_closing_the_stop_it_heads_for_sends_it_on(self) -> None:
        ctc = _three_stops()
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "65", True)
        self.assertEqual(_stops(ctc), ["73", "77"])
        self.assertEqual(
            [(c.train_id, c.destination_block_id)
             for c in ctc.snapshot().cancelled_orders], [("T1", "65")])

    def test_closing_a_queued_stop_drops_it(self) -> None:
        ctc = _three_stops()
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "73", True)
        self.assertEqual(_stops(ctc), ["65", "77"])
        self.assertEqual(len(ctc.snapshot().cancelled_orders), 1)

    def test_closing_every_stop_drops_the_order(self) -> None:
        ctc = ready_office()
        ctc.queue_stop("T1", "Green", "65")
        ctc.set_maintenance_mode(True)
        ctc.set_block_closed("Green", "65", True)
        self.assertEqual(_stops(ctc), [])

    def test_retirement_drops_its_stops(self) -> None:
        ctc = ready_office()
        step_at(ctc, at("T1", "56"))
        # With no stops, it goes back at once.
        ctc.return_to_yard("T1")
        self.assertEqual(ctc.snapshot().returning_trains, ("T1",))
        _wait(ctc, 5, at("T1", "57"))
        self.assertEqual(_stops(ctc), [])
        self.assertEqual(ctc.snapshot().queued_stops, ())


def _drive(line: str, stops: list[str], reorder: bool = False,
           max_s: float = 1800) -> list[tuple[float, str, str]]:
    """One manual train given ``stops`` on ``line`` of the realistic
    railway (``realistic_railway``: real waysides, trains that take time
    to stop). Returns what happened: ``(time, "stopped", block)`` each
    time it comes to a stand at its stop, ``(time, "order", block)`` each
    time its order changes. With ``reorder``, once it is on its way to
    its second stop the third is moved ahead of it."""
    ctc = ready_office()
    railway = RealisticRailway(ctc, line)
    train_id = f"{line[0]}1"
    for block in stops:
        ctc.queue_stop(train_id, line, block)
    events: list[tuple[float, str, str]] = []
    order, stood, reordered = None, None, False
    while railway.now < max_s:
        railway.tick()
        train = railway.trains.get(train_id)
        now = _order(ctc, train_id)
        if now != order:
            order = now
            events.append((railway.now, "order", now))
        here = (train.block if train is not None and train.speed_mps == 0
                and train.block == order else None)
        if here != stood:
            stood = here
            if here is not None:
                events.append((railway.now, "stopped", here))
        if (reorder and not reordered and order == stops[1]
                and train is not None and train.block != stops[0]):
            ctc.move_stop(train_id, 1, 0)
            reordered = True
        if (here == order and not _queued(ctc, train_id)
                and len([e for e in events if e[1] == "stopped"])
                >= len(stops)):
            break
    assert not railway.result.overruns, railway.result.summary()
    return events


#: The realistic railway's trains' reaction before they brake.
RAILWAY_REACTION_S = 1.0


class RealisticRailwayTest(unittest.TestCase):
    """A manual train through its queued stops on the realistic railway,
    with the real waysides."""

    def test_green_visits_its_stops_in_order_and_dwells_at_each(
            self) -> None:
        events = _drive("Green", ["65", "73", "77"])
        stopped = [(t, b) for t, kind, b in events if kind == "stopped"]
        self.assertEqual([b for _, b in stopped], ["65", "73", "77"])
        orders = [(t, b) for t, kind, b in events if kind == "order"]
        self.assertEqual([b for _, b in orders], ["65", "73", "77"])
        # Sent on only after a dwell from when it stopped. The CTC sees
        # only occupancy, so it takes the train to have stopped when it
        # could have, braking as the CTC assumes from the moment it was
        # told 0; a train that reacts a moment later stops a moment
        # later (its 1 s reaction). The Train Controller holds the full
        # dwell itself (D007).
        for (stood_s, block), (sent_s, _) in zip(stopped, orders[1:]):
            with self.subTest(block=block):
                self.assertGreaterEqual(sent_s - stood_s,
                                        DWELL_S - RAILWAY_REACTION_S)

    def test_a_stop_it_cannot_stop_for_is_refused_and_never_overrun(
            self) -> None:
        # G1 runs for Mt Lebanon (77) at full speed; halfway through 66
        # the dispatcher moves block 67, just ahead, to the top. The
        # train could not stop there: refused, and it runs on to 77
        # first.
        ctc = ready_office()
        railway = RealisticRailway(ctc, "Green")
        ctc.queue_stop("G1", "Green", "77")
        ctc.queue_stop("G1", "Green", "67")
        refused = None
        while railway.now < 300 and refused is None:
            railway.tick()
            train = railway.trains.get("G1")
            if (train is not None and train.block == "66"
                    and train.pos_m > 100 and train.speed_mps > 15):
                with self.assertRaisesRegex(UnsafeActionError,
                                            "too fast") as caught:
                    ctc.move_stop("G1", 1, 0)
                refused = caught
        self.assertIsNotNone(refused)
        self.assertEqual(_stops(ctc, "G1"), ["77", "67"])
        while railway.now < 400:
            railway.tick()
        self.assertEqual(railway.result.overruns, [])
        # It made Mt Lebanon, then went on for 67.
        self.assertEqual(_stops(ctc, "G1"), ["67"])

    def test_red_reordered_on_its_way_takes_the_new_next_stop(
            self) -> None:
        events = _drive("Red", ["16", "21", "25"], reorder=True)
        self.assertEqual(
            [b for _, kind, b in events if kind == "stopped"],
            ["16", "25", "21"])


if __name__ == "__main__":
    unittest.main()
