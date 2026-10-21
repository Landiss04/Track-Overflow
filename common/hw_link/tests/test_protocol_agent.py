"""Stream framing, durable duplicate suppression and Pi-only extensions."""

import json
import sys

import pytest
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
from utils.harness_protocol import ProtocolError, step_message


def hello(session="test", version=p.VERSION):
    return p.message(
        p.HELLO,
        1,
        module="train-controller-hw",
        session=session,
        protocol=version,
        agent_version="test",
        agent_hash="test-hash",
    )


def step(tick=1):
    return step_message(
        tick + 10, tick, 0.1, 18000 + tick / 10, {"trains": {}}
    )


def test_chunked_split_unicode_and_probes():
    logs = []
    server = PiLinkServer("train-controller-hw", log=logs.append)
    wire = b"AT+GMM\r\n" + p.encode(hello()) + p.encode(step())
    replies = []
    for byte in wire:
        replies.extend(server.feed(bytes([byte])))
    assert [p.decode(v)["op"] for v in replies] == [p.HELLO, "OUTPUTS", p.VIEW]
    assert len(logs) == 1 and "SKIPPED_LINE" in logs[0]


def test_version_and_identity_checked():
    server = PiLinkServer("train-controller-hw")
    assert server.handle(hello(version=999))[0]["op"] == "REJECTED"
    assert server.handle(step())[0]["reason"] == "HELLO required"
    with pytest.raises(ProtocolError):
        p.decode(
            b'{"op":"HELLO","id":1,"tick":0,"protocol":1,'
            b'"module":"train-controller-hw","session":"x"}'
        )


def test_duplicate_and_durable_reboot(tmp_path):
    journal = tmp_path / "agent.jsonl"
    server = PiLinkServer("train-controller-hw", journal)
    server.handle(hello())
    first = server.handle(step())[0]
    assert server.handle(step()) == [first]
    rebooted = PiLinkServer("train-controller-hw", journal)
    assert rebooted.handle(hello())[0]["resumed"]
    assert rebooted.handle(step()) == [first]
    conflict = step()
    conflict["dt"] = 0.2
    assert rebooted.handle(conflict)[0]["reason"].startswith(
        "request identity reused"
    )
    assert len(journal.read_text().splitlines()) == 2


def test_quit_resets_session_and_cache(tmp_path):
    server = PiLinkServer("train-controller-hw", tmp_path / "agent")
    server.handle(hello())
    server.handle(step())
    server.handle(p.message("QUIT"))
    assert not server.cache and server.session is None
    assert server.handle(step())[0]["reason"] == "HELLO required"


def test_partial_journal_tail_is_not_a_committed_tick(tmp_path):
    journal = tmp_path / "agent"
    server = PiLinkServer("train-controller-hw", journal)
    server.handle(hello())
    first = server.handle(step())[0]
    with journal.open("ab") as stream:
        stream.write(b'{"request":')
    rebooted = PiLinkServer("train-controller-hw", journal)
    rebooted.handle(hello())
    assert rebooted.handle(step()) == [first]
    assert journal.read_bytes().endswith(b"\n")


def test_roundtrip_preserves_state_and_rejects_nested_invalid():
    value = p.message(
        "STATE", state={"clock_paused": False, "nested": {"x": 2}}
    )
    assert p.decode(p.encode(value)) == value
    for invalid in (float("nan"), float("inf"), "\ud800"):
        broken = p.message("STATE", state={"nested": {"x": invalid}})
        with pytest.raises(ProtocolError):
            p.encode(broken)
        with pytest.raises(ProtocolError):
            p.decode(json.dumps(broken).encode())


def test_action_cache_restores_actual_train_state(tmp_path):
    server = PiLinkServer("train-controller-hw", tmp_path / "journal")
    server.handle(hello())
    request = step()
    request["inputs"] = {
        "trains": {
            "R1": {
                "line": "Red",
                "inputs": {
                    "commanded_speed": 12,
                    "authority_blocks": 5,
                    "actual_speed": 0,
                    "brake_state": [False, False],
                    "door_state": [False, False],
                    "light_state": [True, True],
                    "cabin_temperature": 21,
                },
            }
        }
    }
    server.handle(request)
    action = p.message(
        p.ACTION,
        100,
        action="set_state",
        args={"train_id": "R1", "field": "target_temp_c", "value": 23},
    )
    first = server.handle(action)[0]
    rebooted = PiLinkServer("train-controller-hw", tmp_path / "journal")
    assert rebooted.core.fleet.get("R1").state.target_temp_c == 23
    assert rebooted.handle(action) == [first]


def test_replayed_station_dwell_integral_and_latches_match_reference(tmp_path):
    from common.hw_link.tests.test_transports_recovery import request

    server = PiLinkServer("train-controller-hw", tmp_path / "journal")
    server.handle(hello())
    server.handle(request(1))
    for index, (field, value) in enumerate((("kp", 120000), ("ki", 8000))):
        server.handle(
            p.message(
                p.ACTION,
                100 + index,
                action="set_state",
                args={"train_id": "R1", "field": field, "value": value},
            )
        )
    server.handle(
        p.message(
            p.ACTION,
            102,
            action="set_core",
            args={"train_id": "R1", "field": "armed", "value": True},
        )
    )
    for tick in range(2, 9):
        frame = request(tick)
        frame["inputs"]["trains"]["R1"]["inputs"]["beacon_station"] = "TEST"
        server.handle(frame)
    before = server.core.fleet.get("R1")
    restored = PiLinkServer("train-controller-hw", tmp_path / "journal")
    after = restored.core.fleet.get("R1")
    assert vars(before.state) == vars(after.state)
    for name in (
        "_dwell_steps_left",
        "integral",
        "_brake_unanswered_s",
        "_station_pending",
        "_dwelling",
        "_closing",
        "_last_signal",
        "_sent_emergency",
        "_engine_window",
    ):
        assert getattr(before, name) == getattr(after, name)
    count = after._dwell_steps_left
    restored.handle(frame)
    assert after._dwell_steps_left == count


def test_agent_import_is_standard_library_only():
    import subprocess

    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "import common.hw_link.agent,sys; "
            "assert 'PySide6' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0 and run.stderr == ""
