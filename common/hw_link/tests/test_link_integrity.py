"""Damaged link lines are refused, and a lost reply is asked for again."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.relay import HardwareRelay
from common.hw_link.tests.test_protocol_agent import hello
from common.hw_link.tests.test_transports_recovery import request, until
from common.hw_link.transport import ByteTransport
from utils.harness_protocol import ProtocolError


def wire(message):
    return p.frame(p.encode(message))


def read(line):
    return p.decode(p.unframe(line.rstrip(b"\n")))


def test_frame_round_trip():
    message = request(3)
    assert read(wire(message)) == message


@pytest.mark.parametrize(
    "damage",
    [
        # A chunk lost mid-line, as seen on the USB link.
        lambda line: line[:40] + line[90:],
        # Still valid JSON, but not what was sent.
        lambda line: line.replace(b'"tick":3', b'"tick":4', 1),
        # No checksum at all.
        lambda line: line[9:],
    ],
)
def test_damaged_line_is_refused(damage):
    with pytest.raises(ProtocolError):
        p.unframe(damage(wire(request(3))).rstrip(b"\n"))


def test_agent_answers_framed_and_skips_damaged_requests():
    logs = []
    server = PiLinkServer("train-controller-hw", log=logs.append)
    damaged = wire(request(1)).replace(b'"tick":1', b'"tick":9', 1)
    replies = server.feed(wire(hello()) + damaged)
    assert [read(line)["op"] for line in replies] == [p.HELLO]
    assert any("SKIPPED_LINE" in line for line in logs)


class Recording(ByteTransport):
    def __init__(self):
        super().__init__()
        self.sent = []

    def start(self):
        pass

    def write(self, data):
        self.sent.append(read(data))

    def close(self):
        pass


def running(transport):
    relay = HardwareRelay("track-controller-hw", transport)
    relay._ever_ready = relay._online = relay._ready = True
    replies, events = [], []
    relay.reply.connect(replies.append)
    relay.diagnosticEvent.connect(events.append)
    return relay, replies, events


def outputs(frame):
    return wire(
        p.message(
            "OUTPUTS", frame["id"], frame["tick"], outputs={"pad": "x" * 200}
        )
    )


def test_damaged_reply_is_asked_for_again_and_delivered_once():
    transport = Recording()
    relay, replies, events = running(transport)
    try:
        relay.submit_step(request(1))
        good = outputs(request(1))
        relay._received(good[:30] + good[60:])
        assert [frame["tick"] for frame in transport.sent] == [1, 1]
        assert any("PI_RESENT" in event for event in events)
        relay._received(good)
        relay._received(good)  # the answer to the first copy, arriving late
        assert [reply["tick"] for reply in replies] == [1]
    finally:
        relay.close()


def test_cut_view_is_not_a_reason_to_resend():
    transport = Recording()
    relay, replies, events = running(transport)
    try:
        relay.submit_step(request(1))
        view = wire(p.message(p.VIEW, tick=1, view={"x": "y" * 200}))
        relay._received(view[:40] + view[120:])
        assert [frame["tick"] for frame in transport.sent] == [1]
        assert any("PI_SKIPPED_LINE" in event for event in events)
    finally:
        relay.close()


def test_unanswered_request_is_sent_again(monkeypatch):
    monkeypatch.setattr(HardwareRelay, "REPLY_TIMEOUT_MS", 20)
    transport = Recording()
    relay, replies, events = running(transport)
    try:
        relay.submit_step(request(1))
        until(lambda: len(transport.sent) >= 2, timeout=2000)
        assert [frame["tick"] for frame in transport.sent[:2]] == [1, 1]
        relay._received(outputs(request(1)))
        sent = len(transport.sent)
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
        assert [reply["tick"] for reply in replies] == [1]
        assert len(transport.sent) == sent
    finally:
        relay.close()


def test_cut_reply_is_resent_from_the_pi_cache_and_runs_once(tmp_path):
    journal = tmp_path / "pi.jsonl"

    class Lossy(ByteTransport):
        """The real agent behind a link that cuts its first STEP reply."""

        def __init__(self):
            super().__init__()
            self.server = PiLinkServer("train-controller-hw", journal)
            self.cut = False

        def start(self):
            self.connected.emit()

        def write(self, data):
            for line in self.server.feed(data):
                if not self.cut and b'"OUTPUTS"' in line:
                    self.cut = True
                    line = line[:50] + line[120:]
                self.received.emit(line)

        def close(self):
            pass

    transport = Lossy()
    relay = HardwareRelay("train-controller-hw", transport)
    replies = []
    relay.reply.connect(replies.append)
    relay.start()
    try:
        relay.submit_step(request(1))
        relay.submit_step(request(2))
        assert [reply["tick"] for reply in replies] == [1, 2]
        steps = [
            entry["request"]["tick"]
            for entry in map(json.loads, journal.read_text().splitlines()[1:])
        ]
        assert steps == [1, 2]
    finally:
        relay.close()
        transport.server.close()
