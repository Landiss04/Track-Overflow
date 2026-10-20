"""Each run's event log is a file of its own, in ``utils.event_log``.

Two runs started in the same second used to get the same file name,
and the later one replaced the earlier's log.

Run from the repository root with ``python -m unittest discover utils``.
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from utils.event_log import EventLog, log_file_name

STARTED = datetime(2026, 10, 20, 14, 5, 9)
LAUNCHES = 6

# One launch: start a log for STARTED in a folder and log one row.
_LAUNCH = """
import sys
from datetime import datetime
from pathlib import Path
from utils.event_log import EventLog
started = datetime.fromisoformat(sys.argv[2])
with EventLog.create(Path(sys.argv[1]), started) as log:
    log.write(sim_time_s=0.0, tick=0, source=sys.argv[3], event="RAN")
"""


def sources(path: Path) -> list[str]:
    """Return the source of every row in a log."""
    with path.open(newline="", encoding="utf-8") as file:
        return [row["source"] for row in csv.DictReader(file)]


class SameSecondTest(unittest.TestCase):
    """Runs started in the same second keep separate logs."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name) / "logs"

    def test_first_name_is_unchanged(self) -> None:
        self.assertEqual(
            log_file_name(STARTED), "events-20261020-140509.csv"
        )
        with EventLog.create(self.folder, STARTED) as log:
            self.assertEqual(log.path.name, log_file_name(STARTED))

    def test_second_run_gets_its_own_file(self) -> None:
        with EventLog.create(self.folder, STARTED) as first:
            first.write(sim_time_s=0.0, tick=0, source="first", event="RAN")
        with EventLog.create(self.folder, STARTED) as second:
            second.write(sim_time_s=0.0, tick=0, source="second", event="RAN")
        self.assertEqual(second.path.name, "events-20261020-140509-2.csv")
        self.assertEqual(sources(first.path), ["first"])
        self.assertEqual(sources(second.path), ["second"])

    def test_simultaneous_launches_never_share_a_file(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        launches = [
            subprocess.Popen(
                [sys.executable, "-c", _LAUNCH, str(self.folder),
                 STARTED.isoformat(), f"run-{n}"],
                cwd=repo,
            )
            for n in range(LAUNCHES)
        ]
        for launch in launches:
            self.assertEqual(launch.wait(timeout=30), 0)
        paths = sorted(self.folder.glob("events-20261020-140509*.csv"))
        self.assertEqual(len(paths), LAUNCHES)
        rows = sorted(source for path in paths for source in sources(path))
        self.assertEqual(rows, [f"run-{n}" for n in range(LAUNCHES)])


if __name__ == "__main__":
    unittest.main()
