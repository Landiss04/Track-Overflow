"""Tests for loading a schedule into the CTC and listing queued trains.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402

from ctc.model import StubCtcOffice  # noqa: E402
from ctc.schedule import ScheduleError, load_schedule, parse_schedule  # noqa
from ctc.wire import snapshot_from_wire, to_wire  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402

SCHEDULE = Path(__file__).resolve().parents[2] / "utils" / "schedule_v4.json"


class ScheduleLoadingTest(unittest.TestCase):

    def test_real_schedule_queues_every_run_in_time_order(self) -> None:
        ctc = StubCtcOffice()
        ctc.load_schedule(load_schedule(SCHEDULE))
        queued = ctc.snapshot().queued_trains
        self.assertEqual(len(queued), 20)
        times = [q.departure_s for q in queued]
        self.assertEqual(times, sorted(times))
        self.assertEqual({q.line for q in queued}, {"Green", "Red"})

    def test_queued_trains_cross_the_wire(self) -> None:
        ctc = StubCtcOffice()
        ctc.load_schedule(load_schedule(SCHEDULE))
        snap = ctc.snapshot()
        self.assertEqual(snapshot_from_wire(to_wire(snap)), snap)

    def test_malformed_schedules_rejected(self) -> None:
        bad = {
            "not a schedule": {"lines": []},
            "no trains": {"time_unit": "s", "lines": []},
            "int block id": {"time_unit": "s", "lines": [
                {"line": "Green", "trains": [{"train_id": "1", "stops": [
                    {"block_id": 1, "arrival_s": 0}]}]}]},
            "negative time": {"time_unit": "s", "lines": [
                {"line": "Green", "trains": [{"train_id": "1", "stops": [
                    {"block_id": "1", "arrival_s": -5}]}]}]},
        }
        for case, data in bad.items():
            with self.subTest(case=case), self.assertRaises(ScheduleError):
                parse_schedule(data)


class HostDeparturesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_rows_and_bad_file_keeps_schedule(self) -> None:
        host = CtcHost()
        host.loadSchedule(QUrl.fromLocalFile(str(SCHEDULE)))
        self.assertEqual(host.scheduleFile, "schedule_v4.json")
        self.assertEqual(host.scheduleError, "")
        rows = host.departures
        self.assertEqual(rows[0], {"time": "+0:00", "train": "Green 1",
                                   "status": "Queued"})
        self.assertEqual(rows[2]["time"], "+3:00")

        layout = SCHEDULE.parents[1] / "TrackModel" / "green_line.json"
        host.loadSchedule(QUrl.fromLocalFile(str(layout)))
        self.assertIn("not a schedule file", host.scheduleError)
        self.assertEqual(host.scheduleFile, "schedule_v4.json")
        self.assertEqual(len(host.departures), 20)


if __name__ == "__main__":
    unittest.main()
