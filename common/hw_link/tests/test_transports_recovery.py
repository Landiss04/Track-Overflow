"""Real child-process and raw-mode pty tests; no real Pi is needed."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from common.hw_link.relay import HardwareRelay
from common.hw_link.transport import ProcessTransport, matches_identity
from utils.harness_protocol import step_message

APP = QCoreApplication.instance() or QCoreApplication([])


def until(predicate, timeout=7000):
    if predicate():
        return
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(2)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    timer.start()
    deadline.start(timeout)
    loop.exec()
    timer.stop()
    deadline.stop()
    assert predicate(), "timed out waiting for child Pi"


def request(tick):
    return step_message(
        tick + 10,
        tick,
        0.1,
        18000 + tick / 10,
        {
            "trains": {
                "R1": {
                    "line": "Red",
                    "inputs": {
                        "commanded_speed": 12,
                        "authority_blocks": 5,
                        "actual_speed": 0,
                        "emergency_brake_state": False,
                        "service_brake_state": False,
                        "door_state": [False, False],
                        "light_state": [True, True],
                        "cabin_temperature": 21,
                    },
                }
            }
        },
    )


def make_relay(tmp_path, *, pty=False, faults=None):
    transport = ProcessTransport(
        "train-controller-hw",
        tmp_path / "pi.jsonl",
        raw_pty=pty,
        fault_args=faults,
    )
    relay = HardwareRelay("train-controller-hw", transport)
    ready, replies, events, views, errors = [], [], [], [], []
    relay.ready.connect(lambda: ready.append(True))
    relay.reply.connect(replies.append)
    relay.diagnosticEvent.connect(events.append)
    relay.viewChanged.connect(views.append)
    transport.diagnostic.connect(errors.append)
    relay.start()
    until(lambda: bool(ready))
    return relay, replies, events, views, errors


@pytest.mark.parametrize(
    "pty",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                sys.platform != "linux", reason="Linux pty"
            ),
        ),
    ],
)
def test_real_process_stream_and_actions(tmp_path, pty):
    relay, replies, events, views, errors = make_relay(tmp_path, pty=pty)
    try:
        relay.submit_step(request(1))
        until(lambda: len(replies) == 1 and bool(views))
        relay.call_action(
            "set_state",
            {"train_id": "R1", "field": "target_temp_c", "value": 23},
        )
        assert views[-1]["trains"]["R1"]["state"]["target_temp_c"] == 23
        assert replies[0]["id"] == 11 and replies[0]["tick"] == 1
        assert not errors
    finally:
        relay.close()


@pytest.mark.parametrize("running", [False, True])
def test_reboot_repeats_pending_from_durable_cache_and_gain_policy(
    tmp_path, running
):
    relay, replies, events, views, errors = make_relay(
        tmp_path, faults=["--reboot-at-tick", "2"]
    )
    try:
        relay.set_clock_state({"clock_paused": not running})
        relay.submit_step(request(1))
        until(lambda: len(replies) == 1 and bool(views))
        for field, value in (("kp", 120000), ("ki", 1000)):
            relay.call_action(
                "set_state", {"train_id": "R1", "field": field, "value": value}
            )
        relay.call_action(
            "set_core", {"train_id": "R1", "field": "armed", "value": True}
        )
        relay.submit_step(request(2))
        until(lambda: len(replies) == 2)
        assert (replies[1]["id"], replies[1]["tick"]) == (12, 2)
        assert any("PI_RECOVERED" in event for event in events)
        assert any(
            ("GAINS_RESENT" if running else "GAINS_WAIT_ENGINEER") in event
            for event in events
        )
        # Read the durable transaction log: tick 2 was committed exactly once.
        import json

        entries = [
            json.loads(line)
            for line in (tmp_path / "pi.jsonl").read_text().splitlines()[1:]
        ]
        assert (
            sum(
                e["request"]["op"] == "STEP" and e["request"]["tick"] == 2
                for e in entries
            )
            == 1
        )
        relay.call_action(
            "set_state",
            {"train_id": "R1", "field": "target_temp_c", "value": 22},
        )
        assert views[-1]["trains"]["R1"]["core"]["armed"] is running
        assert not errors
    finally:
        relay.close()


def test_serial_identity_never_uses_com_number():
    class Info:
        def hasVendorIdentifier(self):
            return True

        def hasProductIdentifier(self):
            return True

        def vendorIdentifier(self):
            return 0x1D6B

        def productIdentifier(self):
            return 0x0104

        def serialNumber(self):
            return "TO-TRACK-CTRL-HW-01"

    assert matches_identity(Info(), "track-controller-hw")
    assert not matches_identity(Info(), "train-controller-hw")


def test_same_boot_unplug_resends_running_gains_only(tmp_path):
    from common.hw_link.agent import PiLinkServer
    from common.hw_link.transport import ByteTransport

    class InMemory(ByteTransport):
        def __init__(self):
            super().__init__()
            self.server = PiLinkServer("train-controller-hw")

        def start(self):
            self.connected.emit()

        def write(self, data):
            for reply in self.server.feed(data):
                self.received.emit(reply)

        def close(self):
            pass

    for running in (False, True):
        transport = InMemory()
        relay = HardwareRelay("train-controller-hw", transport)
        events = []
        relay.diagnosticEvent.connect(events.append)
        relay.start()
        relay.submit_step(request(1))
        for field, value in (("kp", 120000), ("ki", 8000)):
            relay.call_action(
                "set_state", {"train_id": "R1", "field": field, "value": value}
            )
        relay.call_action(
            "set_core", {"train_id": "R1", "field": "armed", "value": True}
        )
        relay.set_clock_state({"clock_paused": not running})
        transport.disconnected.emit()
        transport.start()
        assert transport.server.core.fleet.get("R1").armed
        expected = "GAINS_RESENT" if running else "GAINS_NOT_RESENT"
        assert any(expected in event for event in events)
        relay.close()


def test_second_loss_preserves_pending_and_original_classification(
    tmp_path,
):
    from common.hw_link import protocol as p
    from common.hw_link.transport import ByteTransport

    class Recording(ByteTransport):
        def __init__(self):
            super().__init__()
            self.written = []

        def start(self):
            pass

        def write(self, data):
            self.written.append(p.decode(data))

        def close(self):
            pass

    transport = Recording()
    relay = HardwareRelay("train-controller-hw", transport)
    relay._ever_ready = True
    relay._online = relay._ready = True
    relay._boot = "first-boot"
    relay._history = [
        p.message(p.ACTION, 1001, action="load_program", args={})
    ]
    pending = request(7)
    relay._inflight = pending
    relay.set_clock_state({"clock_paused": False})
    relay._disconnected()

    def handshake(boot):
        return p.message(
            p.HELLO,
            1000,
            protocol=p.VERSION,
            module=relay.module,
            session=relay.session,
            agent_version="1",
            agent_hash=relay.expected_agent_hash,
            boot=boot,
            resumed=True,
        )

    relay._handle(handshake("second-boot"))
    assert relay._recovering and relay._saved_inflight == pending
    relay.set_clock_state({"clock_paused": True})
    relay._disconnected()
    relay._handle(handshake("third-boot"))
    assert relay._saved_inflight == pending and relay._lost_running
    while relay._recovering:
        active = relay._inflight
        relay._handle(p.message(p.ACK, active["id"], active["tick"]))
    assert transport.written[-1] == pending
    relay.close()


def test_rejected_action_not_replayed_as_accepted_history(tmp_path):
    relay, replies, events, views, errors = make_relay(tmp_path)
    try:
        with pytest.raises(ValueError):
            relay.call_action("not_a_real_action", {})
        assert not any(
            frame.get("action") == "not_a_real_action"
            for frame in relay._history
        )
    finally:
        relay.close()


@pytest.mark.parametrize(
    "args",
    [
        ["--pi-reboot-at-tick", "2"],
        ["--test-pi", "automatic"],
    ],
)
def test_host_rejects_implicit_or_invalid_simulation(args):
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "track_overflow.py",
            "--module",
            "train-controller-hw",
            "--harness",
            "unused",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "error:" in result.stderr


def test_missing_production_pi_holds_readiness_without_fallback(monkeypatch):
    from common.hw_link.transport import QSerialPortInfo, SerialTransport

    monkeypatch.setattr(QSerialPortInfo, "availablePorts", lambda: [])
    transport = SerialTransport("track-controller-hw")
    relay = HardwareRelay("track-controller-hw", transport)
    ready = []
    relay.ready.connect(lambda: ready.append(True))
    try:
        relay.start()
        assert transport.retry.isActive()
        assert not transport.port.isOpen()
        assert not ready and not relay._ready
        assert relay.transport is transport
    finally:
        relay.close()


def test_retired_or_unarmed_display_clears_saved_engineer_gains():
    from common.hw_link.transport import ByteTransport

    class Idle(ByteTransport):
        def start(self):
            pass

        def write(self, data):
            pass

        def close(self):
            pass

    relay = HardwareRelay("train-controller-hw", Idle())
    commissioned = {"core": {"armed": True}, "state": {"kp": 12, "ki": 8}}
    relay._take_view({"trains": {"R1": commissioned}})
    assert relay._gains == {"R1": [12, 8]}
    relay._take_view({"trains": {}})
    assert relay._gains == {}
    reused = {"core": {"armed": False}, "state": {"kp": 12, "ki": 8}}
    relay._take_view({"trains": {"R1": reused}})
    assert relay._gains == {}
    relay.close()


def test_retire_and_reuse_before_next_view_cannot_recover_old_gains():
    from common.hw_link import protocol as p
    from common.hw_link.transport import ByteTransport

    class Recording(ByteTransport):
        def __init__(self):
            super().__init__()
            self.frames = []

        def start(self):
            pass

        def write(self, data):
            self.frames.append(p.decode(data))

        def close(self):
            pass

    transport = Recording()
    relay = HardwareRelay("train-controller-hw", transport)
    relay._ever_ready = True
    relay._boot = "first-boot"
    relay._gains = {"R1": [120000, 8000]}
    retired = request(2)
    retired["inputs"] = {"trains": {}}
    relay._inflight = retired
    relay._handle(
        p.message("OUTPUTS", retired["id"], 2, outputs={"trains": {}})
    )
    assert relay._gains == {}
    reused = request(3)
    relay._inflight = reused
    relay._handle(
        p.message("OUTPUTS", reused["id"], 3, outputs={"trains": {"R1": {}}})
    )
    assert relay._gains == {}  # No VIEW arrived between either reply.
    relay.set_clock_state({"clock_paused": False})
    relay._disconnected()
    relay._handle(
        p.message(
            p.HELLO,
            protocol=p.VERSION,
            module=relay.module,
            session=relay.session,
            agent_version="1",
            agent_hash=relay.expected_agent_hash,
            boot="second-boot",
            resumed=True,
        )
    )
    assert transport.frames[-1]["action"] == "recovery_gains"
    assert transport.frames[-1]["args"] == {"trains": {}}
    relay.close()


@pytest.mark.parametrize("count", [0, 2])
def test_missing_or_ambiguous_pi_names_identity_and_repeats(
    monkeypatch, count
):
    from common.hw_link import transport as module

    class Port:
        def __init__(self, name):
            self.name = name

        def systemLocation(self):
            return self.name

    ports = [Port(f"/dev/ttyACM{index}") for index in range(count)]
    monkeypatch.setattr(
        module.QSerialPortInfo, "availablePorts", lambda: ports
    )
    monkeypatch.setattr(module, "matches_identity", lambda *_args: True)
    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    transport = module.SerialTransport("track-controller-hw")
    events = []
    transport.diagnostic.connect(events.append)
    try:
        transport.start()
        assert len(events) == 1
        assert "track-controller-hw" in events[0]
        assert "TO-TRACK-CTRL-HW-01" in events[0]
        assert "1d6b:0104" in events[0]
        assert f"matches={count}" in events[0]
        for port in ports:
            assert port.systemLocation() in events[0]
        transport._find()
        assert len(events) == 1
        now[0] += 5.0
        transport._find()
        assert len(events) == 2
        assert not transport.port.isOpen()
    finally:
        transport.close()


def test_history_keeps_only_configuration(tmp_path):
    from common.hw_link.relay import REPLAYED_ACTIONS

    relay, replies, events, views, errors = make_relay(tmp_path)
    try:
        relay.call_action("test_engineer_gains", {"kp": 1, "ki": 2})
        for tick in range(1, 4):
            relay.submit_step(request(tick))
        until(lambda: len(replies) == 3)
        relay.call_action(
            "set_state", {"train_id": "R1", "field": "kp", "value": 5}
        )
        assert [frame["action"] for frame in relay._history] == [
            "test_engineer_gains"
        ]
        assert {f["action"] for f in relay._history} <= REPLAYED_ACTIONS
        assert not hasattr(relay, "metrics")
    finally:
        relay.close()
