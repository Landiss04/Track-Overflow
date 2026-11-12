"""The test UI's stand-ins send the CTC Office's route requests."""

from __future__ import annotations

import unittest

from PySide6.QtCore import QCoreApplication, QObject, Signal

from track_ctrl_hw.harness import TestHarness
from track_ctrl_hw.interface import BlockRef

from tests.support import territory

APP = QCoreApplication.instance() or QCoreApplication([])


class StubLink(QObject):
    """A Track Controller that serves Green wayside 1 and steps nothing."""

    connectedChanged = Signal()
    territoriesChanged = Signal()
    outputsChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.territories = [territory(1)]
        self.connected = False
        self.refusal = ""
        self.line = "Green"
        self.outputs = None

    def close(self) -> None:
        pass


def label(number: str) -> str:
    (key,) = [k for k in territory(1).keys if k.block_id == number]
    return key.label


class RouteRequests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = TestHarness(StubLink())  # type: ignore[arg-type]
        self.addCleanup(self.harness.close)

    def rows(self) -> dict[str, dict]:
        model = self.harness._ctc_inputs
        return {row["name"]: row for row in model._rows}

    def test_a_route_request_is_sent_for_the_switch(self) -> None:
        self.harness.selectBlock(label("12"))
        self.assertTrue(self.rows()["route_request"]["applies"])
        self.harness.setInput("ctc", "route_request", "REVERSE")
        sent = self.harness.build_inputs(0.0)
        self.assertEqual(sent.ctc.route_requests,
                         {BlockRef("Green", "12"): "reverse"})
        self.assertEqual(sent.ctc.switch_commands, {})
        self.assertEqual(self.harness.routeRequestsText, "Green:12=reverse")

    def test_none_sends_no_request(self) -> None:
        self.harness.selectBlock(label("12"))
        self.harness.setInput("ctc", "route_request", "REVERSE")
        self.harness.setInput("ctc", "route_request", "NONE")
        self.assertEqual(self.harness.build_inputs(0.0).ctc.route_requests,
                         {})
        self.assertEqual(self.harness.routeRequestsText, "")

    def test_a_block_without_a_switch_has_no_request(self) -> None:
        self.harness.selectBlock(label("3"))
        self.assertFalse(self.rows()["route_request"]["applies"])
