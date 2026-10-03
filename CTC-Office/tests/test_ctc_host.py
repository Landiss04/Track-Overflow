"""Tests for the CTC window's host of the CTC module.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from ctc.model import StubCtcOffice  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
from ctc_ui.sim_clock import SimulationClockBridge  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])


class ClockSpeedupTest(unittest.TestCase):
    """The window's clock speed is the module's clock_speedup output."""

    def test_clock_speed_drives_clock_speedup(self) -> None:
        module = StubCtcOffice()
        host = CtcHost(module)
        clock = SimulationClockBridge()
        changes: list[bool] = []
        host.clockSpeedupChanged.connect(
            lambda: changes.append(host.clockSpeedup))
        host.follow_clock(clock)
        self.assertFalse(module.snapshot().outputs.clock_speedup)

        clock.setSpeed(10)
        self.assertTrue(module.snapshot().outputs.clock_speedup)
        # Pausing re-announces the speed; it is not a change.
        clock.pause()
        clock.setSpeed(1)
        self.assertFalse(module.snapshot().outputs.clock_speedup)
        self.assertEqual(changes, [True, False])


if __name__ == "__main__":
    unittest.main()
