"""The test UI drives the Train Model only through its interface."""

from dataclasses import replace
import math
import os
from pathlib import Path
import subprocess
import sys
import json
import time
import uuid

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket

from train_model.harness import TestHarnessState as Harness
from train_model.interface import Beacon
from train_model.link import (
    LinkError,
    SocketLink,
    TestLinkServer,
    inputs_from_wire,
    inputs_to_wire,
    outputs_from_wire,
    outputs_to_wire,
)
from train_model.model import InvalidInputError, InvalidTimeStepError
from train_model.state import TrainModelState
from tests.test_physics import make_inputs

TRAIN_MODEL = Path(__file__).resolve().parents[1]


@pytest.fixture
def app():
    return QCoreApplication.instance() or QCoreApplication([])


def wait_for(predicate, timeout=5.0):
    """Spin the event loop until ``predicate()`` holds."""
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        QCoreApplication.processEvents()
        time.sleep(0.005)


class RawClient:
    """A non-blocking peer, so the server can answer in this thread."""

    def __init__(self, name):
        self.socket = QLocalSocket()
        self.socket.connectToServer(name)
        self.messages = []
        self.next_id = 0
        wait_for(lambda: self.poll() or self.messages)

    def poll(self):
        while self.socket.canReadLine():
            line = bytes(self.socket.readLine().data()).strip()
            self.messages.append(json.loads(line))

    def pushes(self):
        return [m for m in self.messages if "id" not in m]

    def request(self, **request):
        self.next_id += 1
        request_id = self.next_id
        self.socket.write((json.dumps(dict(request, id=request_id))
                           + "\n").encode())

        def replied():
            self.poll()
            return any(m.get("id") == request_id for m in self.messages)

        wait_for(replied)
        return next(m for m in self.messages if m.get("id") == request_id)

    def step(self, inputs, dt=0.1, clear_passenger_brake=False):
        return self.request(
            op="step", dt=dt, inputs=inputs_to_wire(inputs),
            clear_passenger_brake=clear_passenger_brake,
        )


@pytest.fixture
def served(app):
    """A Train Model served on a private name, and one client."""
    name = f"train-model-test-{uuid.uuid4().hex}"
    state = TrainModelState()
    server = TestLinkServer(state, name)
    assert server.listen()
    yield state, server, RawClient(name)


# ---------------------------------------------------------------------- #
# Wire format
# ---------------------------------------------------------------------- #

def test_inputs_round_trip_exactly():
    plain = make_inputs(power_w=1234.5, station="GLENBURY")
    beacon = replace(plain, track=replace(
        plain.track, beacon=Beacon("Dormont", "R", True)
    ))
    for inputs in (plain, beacon):
        assert inputs_from_wire(inputs_to_wire(inputs)) == inputs


def test_nonfinite_inputs_survive_the_wire_for_the_model_to_reject():
    inputs = make_inputs(power_w=math.nan)
    back = inputs_from_wire(inputs_to_wire(inputs))
    assert math.isnan(back.controller.power_cmd_w)


def test_outputs_round_trip_exactly():
    state = TrainModelState()
    inputs = make_inputs(power_w=100000)
    inputs = replace(inputs, track=replace(
        inputs.track, beacon=Beacon("Dormont", "L", False)
    ))
    state.setFailure("signal_pickup_failure", True)
    outputs = state.step(0.1, inputs)
    assert outputs_from_wire(outputs_to_wire(outputs)) == outputs


# ---------------------------------------------------------------------- #
# The Train Model side of the link
# ---------------------------------------------------------------------- #

def outputs_of(message):
    assert message["op"] == "outputs", message
    return outputs_from_wire(message["outputs"])


def test_connect_pushes_the_current_outputs(served):
    state, _, client = served
    assert outputs_of(client.pushes()[0]) == state.outputs()


def test_step_replies_with_the_module_outputs(served):
    state, _, client = served
    outputs = outputs_of(client.step(make_inputs(power_w=100000)))
    assert outputs == state.outputs()
    assert outputs.controller.actual_speed_mps > 0


def test_rejected_step_replies_the_model_error_and_changes_nothing(served):
    state, _, client = served
    before = state.snapshot
    reply = client.step(make_inputs(power_w=-1))
    assert reply["op"] == "error" and reply["kind"] == "input"
    assert "nonnegative" in reply["message"]
    reply = client.step(make_inputs(), dt=0.0)
    assert reply["op"] == "error" and reply["kind"] == "time_step"
    assert state.snapshot == before


def test_rejected_step_keeps_the_passenger_latch(served):
    state, _, client = served
    state.applyEmergencyBrake()
    reply = client.step(make_inputs(power_w=-1), clear_passenger_brake=True)
    assert reply["op"] == "error"
    assert state.snapshot["passenger_ebrake_pulled"]
    client.step(make_inputs(), clear_passenger_brake=True)
    assert not state.snapshot["passenger_ebrake_pulled"]


def test_train_model_ui_actions_are_pushed_without_a_step(served):
    state, _, client = served
    state.applyEmergencyBrake()
    wait_for(lambda: client.poll() or len(client.pushes()) > 1)
    assert outputs_of(client.pushes()[-1]).controller.emergency_brake_active


def test_requests_are_answered_once(served):
    state, _, client = served
    reply = client.step(make_inputs(power_w=100000))
    assert outputs_of(reply) == state.outputs()
    client.poll()
    assert len(client.pushes()) == 1  # only the one sent on connect


def test_a_second_test_ui_is_refused(served):
    """One test UI at a time: a second would step the module (Kevin)."""
    _, server, client = served
    other = RawClient(server._name)
    assert other.messages[0]["op"] == "busy"
    assert "Another test UI" in other.messages[0]["message"]
    wait_for(lambda: other.socket.state()
             == QLocalSocket.LocalSocketState.UnconnectedState)
    # The first is still served.
    assert client.step(make_inputs())["op"] == "outputs"


def test_a_test_ui_that_takes_over_starts_a_fresh_train(served):
    """A new test UI's stand-ins start fresh; so does the train."""
    state, server, client = served
    for _ in range(20):
        client.step(make_inputs(power_w=480_000, station="GLENBURY"))
    state.setFailure("engine_failure", True)
    assert state.outputs().controller.actual_speed_mps > 0
    client.socket.disconnectFromServer()
    wait_for(lambda: not server._clients)
    taker = RawClient(server._name)
    served_outputs = outputs_of(taker.messages[-1])
    assert served_outputs.controller.actual_speed_mps == 0
    assert served_outputs.track.block_id == ""
    assert state.snapshot["clock"] == "00:00:00"
    assert not state.isFailed("engine_failure")


def test_the_first_test_ui_keeps_what_the_train_model_ui_set(served):
    """Before any test UI drives it, the train is not reset."""
    state, server, client = served
    client.socket.disconnectFromServer()
    wait_for(lambda: not server._clients)
    state.setFailure("brake_failure", True)
    state.applyEmergencyBrake()
    RawClient(server._name)
    assert state.isFailed("brake_failure")
    assert state.snapshot["passenger_ebrake_pulled"]


def test_a_refused_test_ui_takes_over_when_the_first_leaves(served):
    """Check a refused link says why, then connects once it is free."""
    _, server, client = served
    link = SocketLink(server._name)
    harness = Harness(link)
    wait_for(lambda: link.refusal != "")
    assert not link.connected and not harness.connected
    assert harness.disconnectedReason == "Another test UI open"
    assert not harness.sendInputs()
    assert "Another test UI" in harness.inputError
    client.socket.disconnectFromServer()
    wait_for(lambda: link.connected, timeout=5.0)
    assert link.refusal == ""
    assert harness.connected
    # Stepping over the link is covered with real processes below: here
    # a blocking request would wait on a server in this same thread.


def test_failures_are_set_only_in_the_train_model_window(served):
    """The test UI cannot set a failure; it sees only its effect."""
    state, _, client = served
    reply = client.request(op="set_failure", name="brake_failure",
                           active=True)
    assert reply["op"] == "error" and reply["kind"] == "request"
    assert not state.isFailed("brake_failure")
    reply = client.step(make_inputs(service=True))
    assert "failures" not in reply
    assert outputs_of(reply).controller.service_brake_active
    state.setFailure("brake_failure", True)
    wait_for(lambda: client.poll() or len(client.pushes()) > 1)
    pushed = client.pushes()[-1]
    assert "failures" not in pushed
    assert not outputs_of(pushed).controller.service_brake_active


def test_reset_and_unknown_requests(served):
    state, _, client = served
    client.step(make_inputs(power_w=100000))
    state.setFailure("engine_failure", True)
    outputs = outputs_of(client.request(op="reset"))
    assert outputs == state.outputs()
    assert outputs.controller.actual_speed_mps == 0
    assert state.activeFailureCount == 0
    reply = client.request(op="fly")
    assert reply["op"] == "error" and reply["kind"] == "request"


def test_a_second_train_model_does_not_take_over_the_link(served):
    _, server, client = served
    other = TestLinkServer(TrainModelState(), server._name)
    assert not other.listen()
    connected = QLocalSocket.LocalSocketState.ConnectedState
    assert client.socket.state() == connected


# ---------------------------------------------------------------------- #
# The test UI side of the link
# ---------------------------------------------------------------------- #

def test_requests_fail_cleanly_while_the_train_model_is_down(app):
    link = SocketLink(f"train-model-test-{uuid.uuid4().hex}")
    harness = Harness(link)
    assert not harness.connected
    with pytest.raises(LinkError):
        link.step(0.1, make_inputs())
    harness.setRunning(True)
    harness.advanceTick()
    assert not harness.running
    assert harness.tick == 0
    assert "not running" in harness.inputError
    assert all(row["value"] is None for row in harness.outputs)


# ---------------------------------------------------------------------- #
# The Train Model window's run state
# ---------------------------------------------------------------------- #

def test_running_follows_incoming_steps(app):
    state = TrainModelState()
    assert not state.running
    state.step(0.1, make_inputs())
    assert state.running
    wait_for(lambda: not state.running, timeout=3)


# ---------------------------------------------------------------------- #
# The real processes
# ---------------------------------------------------------------------- #

def test_both_windows_run_as_separate_processes(app):
    name = f"train-model-test-{uuid.uuid4().hex}"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "QT_QUICK_BACKEND": "software", "TRAIN_MODEL_LINK": name,
           "PYTHONDONTWRITEBYTECODE": "1"}

    def start(script):
        return subprocess.Popen(
            [sys.executable, script], cwd=TRAIN_MODEL, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    model = start("main.py")
    test_ui = start("test_ui.py")
    try:
        # Wait for the real test UI to hold the link: a probe is then
        # refused, as is a second test UI, until the first one closes.
        def test_ui_holds_the_link():
            try:
                probe = RawClient(name)
            except AssertionError:
                return False
            probe.socket.disconnectFromServer()
            return probe.messages[0]["op"] == "busy"
        wait_for(test_ui_holds_the_link, timeout=15)
        link = SocketLink(name)
        wait_for(lambda: link.refusal != "", timeout=5)
        assert not link.connected
        test_ui.terminate()
        test_ui.wait(10)
        wait_for(lambda: link.connected, timeout=15)
        harness = Harness(link)
        harness.setInput("power_command", 100000)
        assert harness.sendInputs()
        for _ in range(5):
            harness.advanceTick()
        assert link.outputs.controller.actual_speed_mps > 0
        with pytest.raises(InvalidInputError, match="nonnegative"):
            link.step(0.1, make_inputs(power_w=-1))
        with pytest.raises(InvalidTimeStepError):
            link.step(0.0, make_inputs())
        harness.resetModule()
        assert link.outputs.controller.actual_speed_mps == 0
        assert harness.inputError == ""
        model.terminate()
        model.wait(10)
        wait_for(lambda: not link.connected)
        assert harness.outputs[0]["value"] is None
    finally:
        for process in (model, test_ui):
            process.terminate()
            _, stderr = process.communicate(timeout=10)
            # A QML binding or load error is printed to stderr.
            assert stderr == "", stderr
