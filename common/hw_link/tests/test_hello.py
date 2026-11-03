"""Shared HELLO matching preserves each host caller's admission policy."""

import json

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from common.hw_link import bringup, protocol as p
from common.hw_link.manifest import AGENT_VERSION
from common.hw_link.relay import HardwareRelay
from common.hw_link.transport import ByteTransport

EXPECTED = dict(
    module="train-controller-hw",
    session="session",
    agent_version=AGENT_VERSION,
    agent_hash="bundle",
)
MISMATCHES = [
    ("op", p.ACK),
    ("module", "track-controller-hw"),
    ("protocol", p.VERSION + 1),
    ("session", "another-session"),
    ("agent_version", "another-version"),
    ("agent_hash", "another-bundle"),
]


def test_shared_hello_accepts_matching_reply_without_boot():
    reply = p.decode(
        p.encode(p.message(p.HELLO, protocol=p.VERSION, **EXPECTED))
    )
    assert p.matches_hello(reply, **EXPECTED)


@pytest.mark.parametrize("field,value", MISMATCHES)
def test_shared_hello_rejects_each_mismatch(field, value):
    reply = p.message(p.HELLO, protocol=p.VERSION, **EXPECTED)
    reply[field] = value
    assert not p.matches_hello(p.decode(p.encode(reply)), **EXPECTED)


@pytest.mark.parametrize("field", ["op", *EXPECTED, "protocol"])
def test_shared_hello_does_not_match_missing_identity(field):
    reply = p.message(p.HELLO, protocol=p.VERSION, **EXPECTED)
    del reply[field]
    assert not p.matches_hello(reply, **EXPECTED)


class IdleTransport(ByteTransport):
    def start(self):
        pass

    def write(self, data):
        pass

    def close(self):
        pass


class RecordingTransport(IdleTransport):
    def __init__(self):
        super().__init__()
        self.sent = []

    def write(self, data):
        self.sent.append(data)

    def hellos(self):
        return sum(
            p.decode(line)["op"] == p.HELLO
            for data in self.sent
            for line in data.split(b"\n")
            if line
        )


def wait_ms(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_hello_survives_a_partial_line_left_by_a_closed_host():
    # A host that closes the port mid-write leaves an unterminated line on
    # the Pi; the next host's HELLO must not be glued onto it.
    from common.hw_link.agent import PiLinkServer

    transport = RecordingTransport()
    relay = HardwareRelay("track-controller-hw", transport)
    server = PiLinkServer("track-controller-hw")
    try:
        server.feed(b'{"op":"ACTION","id":7,"args":{"territory":{"blo')
        transport.connected.emit()
        replies = [
            p.decode(line)
            for data in transport.sent
            for line in server.feed(data)
        ]
        assert any(
            reply["op"] == p.HELLO and reply["session"] == relay.session
            for reply in replies
        )
    finally:
        relay.close()


@pytest.mark.parametrize(
    "field,value", [*MISMATCHES[1:], ("boot", None), ("boot", "")]
)
def test_relay_keeps_identity_diagnostic_and_requires_boot(
    monkeypatch, field, value
):
    monkeypatch.setattr("common.hw_link.relay.expected_hash", lambda: "bundle")
    relay = HardwareRelay(EXPECTED["module"], IdleTransport())
    ready, events = [], []
    relay.ready.connect(lambda: ready.append(True))
    relay.diagnosticEvent.connect(events.append)
    reply = p.message(
        p.HELLO,
        protocol=p.VERSION,
        **dict(EXPECTED, session=relay.session),
        boot="first-boot",
    )
    bad_reply = dict(reply, **{field: value})
    if field == "boot" and value is None:
        del bad_reply["boot"]
    try:
        relay._received(p.encode(bad_reply))
        assert not ready
        assert relay._boot is None
        assert events == [
            "PI_HELLO_REJECTED identity, version or bundle hash mismatch"
        ]
        relay._received(p.encode(reply))
        assert ready == [True]
        assert relay._boot == "first-boot"
    finally:
        relay.close()


def hello_reply(relay):
    return p.encode(
        p.message(
            p.HELLO,
            protocol=p.VERSION,
            **dict(EXPECTED, session=relay.session),
            boot="first-boot",
        )
    )


def test_relay_resends_hello_until_the_pi_answers(monkeypatch):
    # Bytes sent while the Pi agent has no tty open are discarded.
    monkeypatch.setattr("common.hw_link.relay.expected_hash", lambda: "bundle")
    monkeypatch.setattr(HardwareRelay, "HELLO_RETRY_MS", 20)
    QCoreApplication.instance() or QCoreApplication([])
    transport = RecordingTransport()
    relay = HardwareRelay(EXPECTED["module"], transport)
    ready = []
    relay.ready.connect(lambda: ready.append(True))
    try:
        transport.connected.emit()
        wait_ms(110)
        assert transport.hellos() >= 3
        relay._received(hello_reply(relay))
        assert ready == [True]
        answered = transport.hellos()
        wait_ms(110)
        assert transport.hellos() == answered
    finally:
        relay.close()


def test_reply_to_a_retried_hello_is_not_a_reconnect(monkeypatch):
    monkeypatch.setattr("common.hw_link.relay.expected_hash", lambda: "bundle")
    transport = RecordingTransport()
    relay = HardwareRelay(EXPECTED["module"], transport)
    ready, events = [], []
    relay.ready.connect(lambda: ready.append(True))
    relay.diagnosticEvent.connect(events.append)
    try:
        transport.connected.emit()
        relay._received(hello_reply(relay))
        relay._history.append(p.message(p.ACTION, 5, action="load_program"))
        sent = len(transport.sent)
        relay._received(hello_reply(relay))
        assert ready == [True]
        assert not relay._recovering
        assert len(transport.sent) == sent
        assert [e for e in events if e.startswith("PI_HELLO ")] == [
            events[1]
        ]
    finally:
        relay.close()


@pytest.mark.parametrize("mismatch", [None, *MISMATCHES])
def test_bringup_hello_identity_and_optional_boot(
    monkeypatch, capsys, mismatch
):
    # Exercise the probe's receive/decode path with no workload or hardware.
    app = QCoreApplication.instance() or QCoreApplication([])

    class Peer(IdleTransport):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def start(self):
            QTimer.singleShot(0, self.connected.emit)

        def write(self, data):
            request = p.decode(data)
            reply = p.message(
                p.HELLO,
                protocol=p.VERSION,
                **dict(EXPECTED, session=request["session"]),
            )
            if mismatch is not None:
                field, value = mismatch
                reply[field] = value
            QTimer.singleShot(0, lambda: self.received.emit(p.encode(reply)))

    monkeypatch.setattr(bringup, "ProcessTransport", Peer)
    monkeypatch.setattr(bringup, "expected_hash", lambda: "bundle")
    result = bringup.main(
        ["--module", EXPECTED["module"], "--transport", "process"]
    )
    output = json.loads(capsys.readouterr().out)
    assert result == int(mismatch is not None)
    assert output["error"] == (
        "HELLO identity/version/session/bundle hash mismatch"
        if mismatch is not None
        else None
    )
    assert (output["hello_s"] is not None) == (mismatch is None)
    assert app is not None  # Keep the Qt application alive through main().
