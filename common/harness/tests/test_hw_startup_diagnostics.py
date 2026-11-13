"""Pi diagnostics remain visible before the all-module readiness barrier."""

import subprocess
import sys

import pytest
from PySide6.QtNetwork import QLocalSocket

from common.harness.modules import TRACK_CONTROLLER_HW, stub_specs
from common.harness.supervisor import ModuleSupervisor
from common.harness.tests.test_harness_system import wait_until
from utils.harness_protocol import encode, ready_message, state_message


def test_diagnostics_do_not_make_a_module_ready():
    supervisor = ModuleSupervisor(stub_specs())
    # Listen without spawning children, so this peer owns the HW connection.
    assert supervisor._server.listen(supervisor.server_name)
    messages, errors = [], []
    supervisor.diagnosticReceived.connect(lambda *args: messages.append(args))
    supervisor.protocolError.connect(lambda *args: errors.append(args))
    peer = QLocalSocket()
    peer.connectToServer(supervisor.server_name)
    assert wait_until(lambda: bool(supervisor._unidentified))
    try:
        peer.write(encode(state_message(0, {
            "module": TRACK_CONTROLLER_HW,
            "pi_event": {"event": "PI_SEARCH", "detail": "matches=0"},
        })))
        peer.flush()
        assert wait_until(lambda: bool(messages))
        assert messages == [(TRACK_CONTROLLER_HW, "PI_SEARCH", "matches=0")]
        assert not supervisor.ready_modules and not supervisor.all_ready
        peer.write(encode(ready_message(TRACK_CONTROLLER_HW)))
        peer.flush()
        assert wait_until(lambda: bool(supervisor.ready_modules))
        assert supervisor.ready_modules == (TRACK_CONTROLLER_HW,)
        assert not errors
    finally:
        peer.abort()
        supervisor.stop(0, timeout_s=0)


def test_system_measure_with_explicit_process_pis():
    result = subprocess.run([
        sys.executable, "-m", "common.harness.measure", "--system",
        "--test-pi", "process", "--speed", "1", "--seconds", "1",
    ], capture_output=True, text=True, timeout=80)
    # A slow CI machine may miss its budget; it must still measure and stop.
    assert result.returncode in (0, 1), result.stderr
    assert "The system as wired" in result.stdout, result.stderr
    assert "ticks:" in result.stdout and "round trip (ms):" in result.stdout
    assert "never started ticking" not in result.stderr


@pytest.mark.parametrize("args", [["--test-pi", "process"],
                                  ["--system", "--test-pi", "automatic"]])
def test_measure_rejects_implicit_simulation(args):
    from common.harness.measure import _parse_args

    with pytest.raises(SystemExit):
        _parse_args(args)


@pytest.mark.parametrize("state", [
    {"module": "ctc-office",
     "pi_event": {"event": "PI_SEARCH", "detail": "matches=0"}},
    {"module": TRACK_CONTROLLER_HW,
     "pi_event": {"event": "PI_SEARCH", "detail": 0}},
    {"module": TRACK_CONTROLLER_HW,
     "pi_event": {"event": "bad event", "detail": ""}},
])
def test_invalid_diagnostic_never_releases_readiness(state):
    supervisor = ModuleSupervisor(stub_specs())
    assert supervisor._server.listen(supervisor.server_name)
    errors, events = [], []
    supervisor.protocolError.connect(lambda *args: errors.append(args))
    supervisor.diagnosticReceived.connect(lambda *args: events.append(args))
    peer = QLocalSocket()
    peer.connectToServer(supervisor.server_name)
    assert wait_until(lambda: bool(supervisor._unidentified))
    try:
        peer.write(encode(state_message(0, state)))
        peer.flush()
        assert wait_until(lambda: bool(errors))
        assert not events and not supervisor.ready_modules
    finally:
        peer.abort()
        supervisor.stop(0, timeout_s=0)


def test_diagnostic_identity_cannot_rebind_at_ready():
    supervisor = ModuleSupervisor(stub_specs())
    assert supervisor._server.listen(supervisor.server_name)
    errors, events = [], []
    supervisor.protocolError.connect(lambda *args: errors.append(args))
    supervisor.diagnosticReceived.connect(lambda *args: events.append(args))
    peer = QLocalSocket()
    peer.connectToServer(supervisor.server_name)
    assert wait_until(lambda: bool(supervisor._unidentified))
    try:
        peer.write(encode(state_message(0, {
            "module": TRACK_CONTROLLER_HW,
            "pi_event": {"event": "PI_SEARCH", "detail": "matches=2"},
        })))
        peer.flush()
        assert wait_until(lambda: bool(events))
        peer.write(encode(ready_message("train-controller-hw")))
        peer.flush()
        assert wait_until(lambda: bool(errors))
        assert not supervisor.ready_modules
    finally:
        peer.abort()
        supervisor.stop(0, timeout_s=0)
