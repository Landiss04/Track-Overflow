"""Tests for the train events in the CTC Office's outputs (D022; R35,
R46, R47): ``new_trains`` when it releases a train from the yard, and
``retired_trains`` when a train sent back to the yard has stopped at the
yard entry block. Each event is in the outputs of exactly one step.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.interface import (  # noqa: E402
    CtcOutputs,
    NewTrain,
    RetiredTrain,
    TrackControllerOutputs,
    TrainSuggestion,
)
from ctc.model import StubCtcOffice  # noqa: E402
from ctc.schedule import Schedule, load_schedule  # noqa: E402
from ctc.scheduler import TO_YARD, Progress  # noqa: E402
from ctc.wire import outputs_from_wire, to_wire  # noqa: E402
from tests.occupancy import ready_office, reports  # noqa: E402

SCHEDULE = load_schedule(
    Path(__file__).resolve().parents[2] / "utils" / "schedule_v4.json")


def _step(ctc: StubCtcOffice, *blocks: str, line: str = "Green",
          dt: float = 1.0, ready: bool = True,
          others: tuple[tuple[str, str], ...] = ()) -> CtcOutputs:
    """Step with ``blocks`` of ``line`` (and ``others``) occupied."""
    return ctc.step(dt, reports(
        occupied=[(line, b) for b in blocks] + list(others), ready=ready))


def _released(out: CtcOutputs) -> list[tuple[str, str]]:
    return [(t.train_id, t.line) for t in out.new_trains]


def _retired(out: CtcOutputs) -> list[str]:
    return [t.train_id for t in out.retired_trains]


class ReleaseTest(unittest.TestCase):
    """The CTC releases a waiting train from the yard, and reports it
    once, only when R46's conditions hold."""

    def test_released_once_then_found_at_the_exit_block(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        self.assertEqual(_released(_step(ctc)), [("T1", "Green")])
        # Not again, while it is on its way out or once it is on track.
        self.assertEqual(_released(_step(ctc)), [])
        out = _step(ctc, "63")
        self.assertEqual(_released(out), [])
        self.assertEqual([t.train_id for t in ctc.snapshot().trains],
                         ["T1"])
        for _ in range(5):
            self.assertEqual(_released(_step(ctc, "63")), [])
        # The snapshot repeats only the last step's events: none.
        self.assertEqual(ctc.snapshot().outputs.new_trains, ())

    def test_snapshot_repeats_the_last_steps_events(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Red", "7")
        out = _step(ctc, line="Red")
        self.assertEqual(out.new_trains, (NewTrain("T1", "Red"),))
        self.assertEqual(ctc.snapshot().outputs, out)

    def test_not_while_the_line_is_not_ready(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        for _ in range(3):
            self.assertEqual(_released(_step(ctc, ready=False)), [])
        self.assertEqual(_released(_step(ctc)), [("T1", "Green")])

    def test_not_while_the_exit_block_is_occupied(self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        # 63 is occupied with no train released: a failure. T1 waits.
        ctc.stage_inputs(reports(occupied=[("Green", "63")]))
        for _ in range(3):
            self.assertEqual(_released(_step(ctc, "63")), [])
        self.assertEqual(ctc.snapshot().trains, ())
        self.assertEqual(_released(_step(ctc)), [("T1", "Green")])

    def test_not_while_a_train_is_authorized_into_it(self) -> None:
        # T2 in Green 62 is sent through 63: its authority holds 63.
        ctc = ready_office()
        ctc.place_train("T2", "Green", "62")
        ctc.dispatch("T2", "Green", "64")
        ctc.dispatch("T1", "Green", "70")
        out = _step(ctc, "62")
        self.assertEqual(_released(out), [])
        (limit,) = [a for a in ctc.snapshot().authorities
                    if a.train_id == "T2"]
        self.assertIn("63", limit.route[1:limit.blocks + 1])
        # T2 passes through 63 and on to 64; then T1 may go.
        for blocks in (("62", "63"), ("63",), ("63", "64")):
            ctc.place_train("T2", "Green", blocks[-1])
            self.assertEqual(_released(_step(ctc, *blocks)), [])
        ctc.place_train("T2", "Green", "64")
        self.assertEqual(_released(_step(ctc, "64")), [("T1", "Green")])

    def test_not_while_the_scheduler_holds_the_run(self) -> None:
        runs = tuple(t for t in SCHEDULE.trains
                     if t.line == "Green" and t.train_id == "1")
        ctc = ready_office()
        ctc.load_schedule(Schedule("G1 only", runs))
        ctc.set_automatic_mode(True)
        # G1 is due and ordered, but 63 is occupied (a failure).
        ctc.stage_inputs(reports(occupied=[("Green", "63")]))
        self.assertEqual(_released(_step(ctc, "63")), [])
        self.assertEqual([o.train_id for o in ctc.snapshot().orders],
                         ["G1"])
        # The dispatcher pauses automatic dispatch: the run holds.
        ctc.set_dispatch_paused(True)
        self.assertEqual(_released(_step(ctc)), [])
        self.assertEqual(_released(_step(ctc)), [])
        # Outside automatic mode the schedule holds too.
        ctc.set_dispatch_paused(False)
        ctc.set_automatic_mode(False)
        self.assertEqual(_released(_step(ctc)), [])
        ctc.set_automatic_mode(True)
        self.assertEqual(_released(_step(ctc)), [("G1", "Green")])

    def test_one_per_line_at_a_time_most_behind_schedule_first(
            self) -> None:
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        ctc.dispatch("T2", "Green", "70", arrival_s=8 * 3600)
        ctc.dispatch("T3", "Red", "7")
        out = _step(ctc)
        # One per line: T2 has a requested arrival, so it goes first.
        self.assertEqual(sorted(_released(out)),
                         [("T2", "Green"), ("T3", "Red")])
        # T1 waits while T2 is released but not yet out, and while it
        # holds 63.
        self.assertEqual(_released(_step(ctc)), [])
        self.assertEqual(_released(_step(ctc, "63")), [])
        for _ in range(10):
            self.assertEqual(_released(_step(ctc, "63")), [])
        self.assertEqual(_released(_step(ctc, "63", "64")), [])
        # 63 clear, T2 in 64 and its authority runs on from there.
        self.assertEqual(_released(_step(ctc, "64")), [("T1", "Green")])

    def test_a_released_train_holds_its_exit_block(self) -> None:
        # Released, not yet seen: no other train is given 63.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        _step(ctc)
        ctc.place_train("T2", "Green", "62")
        ctc.dispatch("T2", "Green", "64")
        _step(ctc, "62")
        (limit,) = [a for a in ctc.snapshot().authorities
                    if a.train_id == "T2"]
        self.assertEqual((limit.blocks, limit.reason, limit.at,
                          limit.held_by), (0, "reserved", "63", "T1"))

    def test_only_a_released_train_is_found_leaving_the_yard(self) -> None:
        # 63 becomes occupied on the step T1 is ordered, before the
        # CTC has released it: that is not T1.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        out = _step(ctc, "63")
        self.assertEqual((_released(out), ctc.snapshot().trains), ([], ()))

    def test_ids_are_the_ctcs(self) -> None:
        ctc = ready_office()
        ctc.dispatch("  Train 7 ", "Green", "70")
        self.assertEqual(_released(_step(ctc)), [("Train 7", "Green")])


class RetireTest(unittest.TestCase):
    """A run sent back to the yard is retired at the yard entry block
    once it has stopped there, with authority 0 at its destination."""

    def _to_yard(self) -> StubCtcOffice:
        # G1 on its way back to the yard, in Green 56, sent to 57.
        runs = tuple(t for t in SCHEDULE.trains
                     if t.line == "Green" and t.train_id == "1")
        ctc = ready_office()
        ctc.load_schedule(Schedule("G1 only", runs))
        ctc.set_automatic_mode(True)
        stops = len(ctc._auto.plans[0].stops)
        ctc._auto.progress["G1"] = Progress(TO_YARD, stops)
        ctc.dispatch("G1", "Green", "57")
        ctc.place_train("G1", "Green", "56")
        return ctc

    def test_retired_once_when_stopped_at_the_yard_entry(self) -> None:
        ctc = self._to_yard()
        for _ in range(10):
            out = _step(ctc, "56")
            self.assertEqual(_retired(out), [])
        # It crosses into 57, its destination: still moving.
        self.assertEqual(_retired(_step(ctc, "56", "57")), [])
        out = _step(ctc, "57", dt=0.5)
        self.assertEqual(_retired(out), [])
        (here,) = out.track_controller.suggestions
        self.assertEqual((here.block_id, here.authority_blocks), ("57", 0))
        # Once it can no longer be moving, braking at the service rate
        # since it was told to stop, it is retired: once.
        events = []
        for _ in range(20):
            events += _retired(_step(ctc, "57", dt=0.5))
        self.assertEqual(events, ["G1"])
        # Retired: nothing more is sent for it, and its order is gone.
        snap = ctc.snapshot()
        self.assertEqual(snap.outputs.track_controller.suggestions, ())
        self.assertEqual(snap.orders, ())
        # The harness removes it, which clears 57: the run is done, the
        # train is not lost, and nothing is released or retired again.
        out = _step(ctc)
        self.assertEqual((_retired(out), _released(out)), ([], []))
        snap = ctc.snapshot()
        self.assertEqual(snap.lost_trains, ())
        self.assertEqual(snap.trains, ())
        (run,) = snap.scheduled_runs
        self.assertEqual(run.status, "done")
        for _ in range(3):
            out = _step(ctc)
            self.assertEqual((_retired(out), _released(out)), ([], []))

    def test_not_retired_short_of_the_yard_entry(self) -> None:
        ctc = self._to_yard()
        for _ in range(30):
            self.assertEqual(_retired(_step(ctc, "56")), [])

    def test_a_manual_train_at_57_is_not_retired(self) -> None:
        # Not sent back to the yard (no return-to-yard action): a train
        # whose destination is Overbrook stops there and stays.
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "57")
        ctc.place_train("T1", "Green", "57")
        for _ in range(30):
            self.assertEqual(_retired(_step(ctc, "57")), [])
        self.assertEqual([t.train_id for t in ctc.snapshot().trains],
                         ["T1"])


class WireTest(unittest.TestCase):
    """The events in JSON, as the harness's roster reads them."""

    def test_round_trip_and_shape(self) -> None:
        out = CtcOutputs(
            track_controller=TrackControllerOutputs(suggestions=(
                TrainSuggestion("G1", "Green", "63", 18, 2),
                TrainSuggestion("G1", "Green", "64", 17, 1))),
            new_trains=(NewTrain("G1", "Green"), NewTrain("R1", "Red")),
            retired_trains=(RetiredTrain("G2"),))
        data = json.loads(json.dumps(to_wire(out)))
        self.assertEqual(data["new_trains"],
                         [{"train_id": "G1", "line": "Green"},
                          {"train_id": "R1", "line": "Red"}])
        self.assertEqual(data["retired_trains"], [{"train_id": "G2"}])
        self.assertEqual(outputs_from_wire(data), out)

    def test_left_out_is_no_events(self) -> None:
        out = outputs_from_wire({"clock_paused": False})
        self.assertEqual((out.new_trains, out.retired_trains), ((), ()))

    def test_the_roster_applies_them(self) -> None:
        from common.harness.roster import Roster
        roster = Roster("ctc-office")
        ctc = ready_office()
        ctc.dispatch("T1", "Green", "70")
        roster.apply(to_wire(_step(ctc)), 1.0)
        for _ in range(3):
            events = roster.apply(to_wire(_step(ctc)), 2.0)
            self.assertEqual(events, [])
        self.assertEqual([(t.train_id, t.line) for t in roster],
                         [("T1", "Green")])


if __name__ == "__main__":
    unittest.main()
