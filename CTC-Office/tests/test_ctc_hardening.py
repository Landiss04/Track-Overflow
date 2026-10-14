"""Tests that malformed or extreme input is rejected cleanly, as the
CTC Office's own errors, never as a crash.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ctc.actions import apply_action  # noqa: E402
from ctc.interface import (  # noqa: E402
    BlockOccupancy,
    CtcInputs,
    TicketSales,
    TrackControllerInputs,
    TrackModelInputs,
    TrainReport,
)
from ctc.model import (  # noqa: E402
    MAX_TICKETS,
    MAX_TRAIN_ID_LENGTH,
    InvalidInputError,
    InvalidTimeStepError,
    StubCtcOffice,
)
from ctc.schedule import (  # noqa: E402
    Schedule,
    ScheduleError,
    ScheduledTrain,
    parse_schedule,
)

DT_S = 0.1
HUGE = 10**400       # an int too big for a float


def _trains(*trains: Any) -> CtcInputs:
    return CtcInputs(track_controller=TrackControllerInputs(
        trains=trains))  # type: ignore[arg-type]


class NumberTest(unittest.TestCase):

    def test_huge_numbers_are_rejected(self) -> None:
        ctc = StubCtcOffice()
        with self.assertRaises(InvalidTimeStepError):
            ctc.step(HUGE, CtcInputs())
        for offset, speed in ((HUGE, 0.0), (0.0, HUGE)):
            with self.subTest(offset=offset, speed=speed), \
                    self.assertRaises(InvalidInputError):
                ctc.step(DT_S, _trains(
                    TrainReport("T1", "Green", "5", offset, speed)))
        with self.assertRaises(InvalidInputError):
            apply_action(ctc, "dispatch", {
                "train_id": "T1", "line": "Green",
                "destination_block_id": "5", "arrival_s": HUGE})

    def test_elapsed_time_stays_finite(self) -> None:
        ctc = StubCtcOffice()
        ctc.step(1e308, CtcInputs())
        with self.assertRaises(InvalidTimeStepError):
            ctc.step(1e308, CtcInputs())
        self.assertEqual(ctc.snapshot().elapsed_s, 1e308)

    def test_ticket_sales_are_bounded(self) -> None:
        ctc = StubCtcOffice()
        for tickets in (MAX_TICKETS + 1, 2**63, -1):
            with self.subTest(tickets=tickets), \
                    self.assertRaises(InvalidInputError):
                ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(
                    (TicketSales("Green", tickets),))))
        ctc.step(DT_S, CtcInputs(track_model=TrackModelInputs(
            (TicketSales("Green", MAX_TICKETS),))))


class ShapeTest(unittest.TestCase):
    """Inputs that are not the boundary types are rejected before they
    are read, and change nothing."""

    def test_wrong_types_are_rejected(self) -> None:
        ctc = StubCtcOffice()
        before = ctc.snapshot()
        for bad in (None, {}, _trains(None), _trains("abc"),
                    CtcInputs(track_controller=TrackControllerInputs(
                        trains="abc")),  # type: ignore[arg-type]
                    CtcInputs(track_controller=TrackControllerInputs(
                        trains=(t for t in ())))):  # type: ignore
            with self.subTest(inputs=bad):
                for call in (ctc.validate_inputs, ctc.stage_inputs,
                             lambda i: ctc.step(DT_S, i)):
                    with self.assertRaises(InvalidInputError):
                        call(bad)  # type: ignore[arg-type]
        self.assertEqual(ctc.snapshot(), before)

    def test_lists_are_taken_as_tuples(self) -> None:
        ctc = StubCtcOffice()
        listed = [TrainReport("T1", "Green", "5", 0.0, 0.0)]
        ctc.step(DT_S, CtcInputs(track_controller=TrackControllerInputs(
            trains=listed)))  # type: ignore[arg-type]
        inputs = ctc.snapshot().inputs
        assert inputs is not None
        self.assertIsInstance(inputs.track_controller.trains, tuple)


class ReportTest(unittest.TestCase):

    def test_an_empty_block_with_a_train_in_it_is_rejected(self) -> None:
        ctc = StubCtcOffice()
        with self.assertRaisesRegex(InvalidInputError, "unoccupied"):
            ctc.step(DT_S, CtcInputs(track_controller=TrackControllerInputs(
                trains=(TrainReport("T1", "Green", "5", 0.0, 0.0),),
                occupancy=(BlockOccupancy("Green", "5", False),))))

    def test_train_ids(self) -> None:
        ctc = StubCtcOffice()
        for bad in ("T\n1", "T\x001", "T" * (MAX_TRAIN_ID_LENGTH + 1)):
            with self.subTest(train_id=bad):
                with self.assertRaises(InvalidInputError):
                    ctc.dispatch(bad, "Green", "5")
                with self.assertRaises(InvalidInputError):
                    ctc.step(DT_S, _trains(
                        TrainReport(bad, "Green", "5", 0.0, 0.0)))
        # Printable text of any script is fine.
        ctc.dispatch("T" * MAX_TRAIN_ID_LENGTH, "Green", "5")
        ctc.dispatch("Tram 🚆", "Green", "6")


class ScheduleTest(unittest.TestCase):

    def _parse(self, lines: Any) -> None:
        parse_schedule({"time_unit": "s", "lines": lines})

    @staticmethod
    def _train(train_id: str, *times: int) -> dict[str, Any]:
        return {"train_id": train_id,
                "stops": [{"block_id": "5", "arrival_s": t} for t in times]}

    def test_malformed_files_are_schedule_errors(self) -> None:
        for lines in ([None], "abc", [{"line": "Green", "trains": None}],
                      [{"line": "Green", "trains": [None]}],
                      [{"line": "Green", "trains": [
                          {"train_id": "1", "stops": "abc"}]}]):
            with self.subTest(lines=lines), \
                    self.assertRaises(ScheduleError):
                self._parse(lines)

    def test_duplicate_trains_and_backward_times(self) -> None:
        with self.assertRaisesRegex(ScheduleError, "listed twice"):
            self._parse([{"line": "Green", "trains": [
                self._train("1", 0), self._train("1", 60)]}])
        with self.assertRaisesRegex(ScheduleError, "before the stop"):
            self._parse([{"line": "Green", "trains": [
                self._train("1", 60, 30)]}])

    def test_module_refuses_a_run_with_no_stops(self) -> None:
        ctc = StubCtcOffice()
        with self.assertRaisesRegex(InvalidInputError, "no stops"):
            ctc.load_schedule(Schedule("x", (
                ScheduledTrain("Green", "1", ()),)))
        ctc.snapshot()          # nothing half-loaded left to trip on


if __name__ == "__main__":
    unittest.main()
