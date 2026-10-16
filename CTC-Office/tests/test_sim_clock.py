"""Tests for the CTC Office's simulation clock bridge.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402

from ctc_ui.sim_clock import SimulationClockBridge  # noqa: E402
from utils.system_clock import InvalidClockSettingError  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])


def _spin(ms: int) -> None:
    # Run the Qt event loop for ``ms`` milliseconds.
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class SimulationClockBridgeTest(unittest.TestCase):
    """The bridge exposes and controls the shared clock."""

    def setUp(self) -> None:
        """Create a bridge with its own clock."""
        self.bridge = SimulationClockBridge()
        self.changes: dict[str, int] = {"time": 0, "paused": 0, "speed": 0}
        self.bridge.timeTextChanged.connect(lambda: self._count("time"))
        self.bridge.pausedChanged.connect(lambda: self._count("paused"))
        self.bridge.speedChanged.connect(lambda: self._count("speed"))

    def _count(self, name: str) -> None:
        # Tally one change notification.
        self.changes[name] += 1

    def test_starts_paused_at_five_am(self) -> None:
        """Start held at 05:00:00, 1x."""
        self.assertEqual(self.bridge.timeText, "05:00:00")
        self.assertTrue(self.bridge.paused)
        self.assertEqual(self.bridge.speed, 1)

    def test_runs_in_real_time(self) -> None:
        """Show about 1 simulated second after 1 real second at 1x."""
        self.bridge.resume()
        _spin(1050)
        self.assertEqual(self.bridge.timeText, "05:00:01")

    def test_ten_x_runs_faster(self) -> None:
        """Advance about 10 simulated seconds per real second at 10x."""
        self.bridge.setSpeed(10)
        self.bridge.resume()
        _spin(1050)
        self.assertAlmostEqual(
            self.bridge.clock.elapsed_s, 10.0, delta=0.6
        )
        self.assertEqual(self.bridge.speed, 10)

    def test_pause_holds_time(self) -> None:
        """Leave the shown time unchanged while paused."""
        self.bridge.resume()
        _spin(300)
        self.bridge.pause()
        held = self.bridge.timeText
        elapsed_s = self.bridge.clock.elapsed_s
        _spin(1200)
        self.assertTrue(self.bridge.paused)
        self.assertEqual(self.bridge.timeText, held)
        self.assertEqual(self.bridge.clock.elapsed_s, elapsed_s)

    def test_notifies_on_state_changes(self) -> None:
        """Notify QML when pause or speed changes."""
        self.bridge.resume()
        self.bridge.setSpeed(10)
        self.assertGreaterEqual(self.changes["paused"], 1)
        self.assertGreaterEqual(self.changes["speed"], 1)

    def test_time_text_notifies_once_per_second(self) -> None:
        """Notify on each new shown second, not on every tick."""
        self.bridge.setSpeed(10)
        self.bridge.resume()
        _spin(1050)
        shown_seconds = int(self.bridge.clock.elapsed_s)
        self.assertLessEqual(self.changes["time"], shown_seconds + 1)
        self.assertGreater(self.bridge.clock.tick_count, shown_seconds)

    def test_rejects_unsupported_speed(self) -> None:
        """Refuse any speed other than 1 or 10."""
        with self.assertRaises(InvalidClockSettingError):
            self.bridge.setSpeed(5)
        self.assertEqual(self.bridge.speed, 1)


if __name__ == "__main__":
    unittest.main()
