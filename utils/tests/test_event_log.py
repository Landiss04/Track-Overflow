"""Tests for the CSV event log in ``utils.event_log``.

Run from the repository root with ``python -m unittest discover utils``.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from utils.event_log import COLUMNS, EventLog, log_file_name


class EventLogTest(unittest.TestCase):
    """Rows land in the file at once, in CSV, after a header."""

    def setUp(self) -> None:
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.path = Path(self._folder.name) / "logs" / "events.csv"

    def read_rows(self) -> list[list[str]]:
        with self.path.open(newline="", encoding="utf-8") as log_file:
            return list(csv.reader(log_file))

    def test_header_then_rows_flushed_at_once(self) -> None:
        with EventLog(self.path) as log:
            log.write(
                sim_time_s=18000.1,
                tick=1,
                source="ctc",
                event="TICK_REJECTED",
                detail="bad input, with a comma",
            )
            # Readable before the log is closed: every row is flushed.
            rows = self.read_rows()
        self.assertEqual(rows[0], list(COLUMNS))
        row = dict(zip(COLUMNS, rows[1]))
        self.assertEqual(row["sim_time_s"], "18000.1")
        self.assertEqual(row["time_of_day"], "05:00:00")
        self.assertEqual(row["tick"], "1")
        self.assertEqual(row["source"], "ctc")
        self.assertEqual(row["event"], "TICK_REJECTED")
        self.assertEqual(row["detail"], "bad input, with a comma")
        datetime.fromisoformat(row["wall_time"])

    def test_time_of_day_wraps_at_midnight(self) -> None:
        with EventLog(self.path) as log:
            log.write(
                sim_time_s=86400 + 3661.5,
                tick=1,
                source="harness",
                event="CLOCK_PAUSED",
            )
        self.assertEqual(self.read_rows()[1][2], "01:01:01")

    def test_writes_after_close_are_ignored(self) -> None:
        log = EventLog(self.path)
        log.close()
        self.assertTrue(log.closed)
        log.write(sim_time_s=0, tick=0, source="harness", event="IGNORED")
        self.assertEqual(len(self.read_rows()), 1)

    def test_file_name_carries_the_start_time(self) -> None:
        name = log_file_name(datetime(2026, 10, 20, 3, 4, 5))
        self.assertEqual(name, "events-20261020-030405.csv")


if __name__ == "__main__":
    unittest.main()
