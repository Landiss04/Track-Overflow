"""The test link, across two real processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket

from track_ctrl_hw.errors import InvalidInputError, InvalidTimeStepError
from track_ctrl_hw.interface import CtcInputs, Suggestion
from track_ctrl_hw.link import BUSY_MESSAGE, TestLinkClient
from track_ctrl_hw.wire import inputs_to_wire

from tests.support import inputs, keys, loaded

MODULE_ROOT = Path(__file__).resolve().parents[1]
SERVER = MODULE_ROOT / "tests" / "link_server.py"


def _wait(app: QCoreApplication, done, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while not done():
        if time.monotonic() > deadline:
            return False
        app.processEvents()
        time.sleep(0.005)
    return True


class Link(unittest.TestCase):
    app: QCoreApplication

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.name = f"trains-tchw-test-{os.getpid()}-{time.monotonic_ns()}"
        self.server = subprocess.Popen(
            [sys.executable, str(SERVER), self.name, "60"],
            stdout=subprocess.PIPE, text=True, cwd=MODULE_ROOT,
        )
        assert self.server.stdout is not None
        self.assertEqual(self.server.stdout.readline().strip(), "ready")
        self.clients: list[TestLinkClient] = []

    def tearDown(self) -> None:
        for client in self.clients:
            client.close()
        self.server.terminate()
        self.server.wait(10)
        if self.server.stdout is not None:
            self.server.stdout.close()

    def connect(self) -> TestLinkClient:
        client = TestLinkClient(self.name)
        self.clients.append(client)
        self.assertTrue(_wait(self.app, lambda: client.connected))
        return client

    def test_remote_outputs_equal_local_ones(self) -> None:
        client = self.connect()
        self.assertEqual(client.line, "Green")
        self.assertEqual([t.wayside_id for t in client.territories], ["1"])
        local = loaded(1)
        for step, kwargs in enumerate((
            {"occupied": ["1"]},
            {"occupied": ["3", "4"], "suggestions": {"3": (30, 4)}},
            {"closed": ["7"], "suggestions": {"7": (5, 2), "8": (9, 1)}},
            {"maintenance": True, "switch_commands": {"12": "reverse"}},
            {"failures": {"19": "power"}, "occupied": ["18"]},
        )):
            sent = inputs(local, time_s=18000.0 + step / 10, **kwargs)
            with self.subTest(step=step):
                self.assertEqual(client.step(0.1, sent),
                                 local.step(0.1, sent))

    def test_rejections_come_back_typed(self) -> None:
        client = self.connect()
        local = loaded(1)
        with self.assertRaises(InvalidTimeStepError):
            client.step(0.0, inputs(local))
        bad = inputs(local)
        bad = type(bad)(time_s=bad.time_s, ctc=CtcInputs(
            suggestions={keys(local)["3"]: Suggestion(-4, 1)}))
        with self.assertRaises(InvalidInputError):
            client.step(0.1, bad)
        # The link still works after a rejection.
        self.assertEqual(len(client.step(0.1, inputs(local)).ctc_reports), 1)

    def test_one_test_ui_at_a_time(self) -> None:
        first = self.connect()
        second = TestLinkClient(self.name)
        self.clients.append(second)
        self.assertTrue(_wait(self.app, lambda: second.refusal != ""))
        self.assertFalse(second.connected)
        self.assertEqual(second.refusal, BUSY_MESSAGE)
        self.assertEqual(len(first.step(0.1, inputs(loaded(1))).ctc_reports),
                         1)

    def test_reset(self) -> None:
        client = self.connect()
        local = loaded(1)
        client.step(0.1, inputs(local, occupied=["1"]))
        client.reset()
        self.assertIsNone(client.outputs)
        out = client.step(0.1, inputs(local))
        self.assertEqual(set(out.track_model.switch_commands.values()),
                         {"normal"})

    def test_bad_lines_get_errors_and_do_not_block_good_ones(self) -> None:
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        self.assertTrue(socket.waitForConnected(2000))
        good = {"id": 5, "op": "step", "dt": 0.1,
                "inputs": inputs_to_wire(inputs(loaded(1)))}
        payload = b"".join(
            line + b"\n"
            for line in (
                b"not json",
                b"[1]",
                json.dumps({"op": "step"}).encode(),
                json.dumps(good).encode(),
            )
        )
        socket.write(payload)
        socket.flush()
        replies: list[dict] = []

        def drain() -> bool:
            while socket.canReadLine():
                replies.append(json.loads(bytes(socket.readLine().data())))
            return any(r.get("id") == 5 for r in replies)

        self.assertTrue(_wait(self.app, lambda: (
            socket.waitForReadyRead(50) or True) and drain()))
        errors = [r for r in replies if r.get("op") == "error"]
        self.assertEqual(len(errors), 3)
        answer = next(r for r in replies if r.get("id") == 5)
        self.assertEqual(answer["op"], "outputs")
        socket.abort()


if __name__ == "__main__":
    unittest.main()
