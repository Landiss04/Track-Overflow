"""Malformed lines on the test UI's link are answered, never fatal.

Each line is handled on its own, in order: a bad one gets an error reply
and the lines after it are still served. Nothing escapes the server's
Qt slot, and the connection stays open.
"""

import json
import sys
import time
import uuid

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket

from train_model.link import TestLinkServer, inputs_to_wire
from train_model.state import TrainModelState
from tests.test_physics import make_inputs


@pytest.fixture
def served():
    """A Train Model served on a private name, recording any exception
    that escapes a Qt slot."""
    app = QCoreApplication.instance() or QCoreApplication([])
    escaped = []
    hook, sys.excepthook = sys.excepthook, (
        lambda kind, value, tb: escaped.append(repr(value)))
    state = TrainModelState()
    server = TestLinkServer(state, f"malformed-{uuid.uuid4().hex}")
    assert server.listen()
    socket = QLocalSocket()
    socket.connectToServer(server._name)
    replies = read(socket)  # the outputs sent on connect
    assert replies and replies[0]["op"] == "outputs"
    yield state, socket, escaped
    sys.excepthook = hook
    assert app is not None


def read(socket, timeout=2.0, want=1):
    """Spin until ``want`` lines arrive; return them parsed."""
    lines = []
    deadline = time.monotonic() + timeout
    while len(lines) < want and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        while socket.canReadLine():
            lines.append(json.loads(bytes(socket.readLine().data())))
        time.sleep(0.005)
    return lines


def send(socket, payload: bytes, want=1):
    socket.write(payload)
    socket.flush()
    return read(socket, want=want)


GOOD_STEP = json.dumps({"op": "step", "dt": 0.1, "id": 50,
                        "inputs": inputs_to_wire(make_inputs()),
                        "clear_passenger_brake": False}).encode() + b"\n"


@pytest.mark.parametrize(("payload", "has_id"), [
    (b"this is not json\n", False),
    (b"[1, 2, 3]\n", False),
    (b"5\n", False),
    (b"null\n", False),
    (b'{"op": "reset"}\n', False),
    (b'{"op": "reset", "id": true}\n', False),
    (b'{"op": "reset", "id": "7"}\n', False),
    (b'{"id": 4}\n', True),
    (b'{"op": "reset", "id": 1}{"op": "reset", "id": 2}\n', False),
    (b"\xff\xfe\xfa\n", False),
])
def test_each_malformed_line_gets_one_error_reply(served, payload, has_id):
    state, socket, escaped = served
    replies = send(socket, payload)
    assert len(replies) == 1, replies
    assert replies[0]["op"] == "error"
    assert replies[0]["kind"] == "request"
    assert ("id" in replies[0]) == has_id
    assert socket.state() == QLocalSocket.LocalSocketState.ConnectedState
    assert not escaped, escaped


def test_a_request_without_an_id_is_not_acted_on(served):
    state, socket, _ = served
    state.applyEmergencyBrake()
    send(socket, b'{"op": "reset"}\n')
    assert state.snapshot["passenger_ebrake_pulled"]


def test_a_good_line_after_a_bad_one_in_one_write_is_answered(served):
    _, socket, escaped = served
    replies = send(socket, b"garbage\n" + b'{"op": "reset", "id": 7}\n',
                   want=2)
    assert [r["op"] for r in replies] == ["error", "outputs"]
    assert replies[1]["id"] == 7
    assert not escaped, escaped


def test_after_every_kind_of_junk_a_step_is_served(served):
    _, socket, escaped = served
    junk = (b"x\n[1]\n{\"op\": \"reset\"}\n{\"id\": 4}\n\xff\n"
            b'{"a": 1}{"b": 2}\n')
    assert len(send(socket, junk, want=6)) == 6
    reply = send(socket, GOOD_STEP)
    assert reply[0]["op"] == "outputs" and reply[0]["id"] == 50
    assert not escaped, escaped
