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
                    "emergency_brake_state": False,
                    "service_brake_state": False,
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
    rebooted.handle(hello())
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
    # Every latch, timer and integral the core keeps, whatever it names
    # them.
    kept = {k: v for k, v in vars(before).items() if k != "state"}
    assert kept == {k: v for k, v in vars(after).items() if k != "state"}
    count = after._dwell_ticks
    restored.handle(frame)
    assert after._dwell_ticks == count


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


def test_view_messages_are_throttled_by_wall_time(monkeypatch):
    import common.hw_link.agent as agent

    now = [10.0]
    monkeypatch.setattr(agent.time, "monotonic", lambda: now[0])
    server = PiLinkServer("train-controller-hw")
    server.handle(hello())
    assert any(r["op"] == p.VIEW for r in server.handle(step(1)))
    for tick in range(2, 12):
        now[0] += 0.005  # 200 ticks/sec still produces only 5Hz VIEW.
        assert not any(r["op"] == p.VIEW for r in server.handle(step(tick)))
    now[0] = 10.199
    assert not any(r["op"] == p.VIEW for r in server.handle(step(12)))
    now[0] = 10.201
    assert any(r["op"] == p.VIEW for r in server.handle(step(13)))


def test_restored_session_requires_fresh_successful_hello(tmp_path):
    journal = tmp_path / "journal"
    server = PiLinkServer("train-controller-hw", journal)
    server.handle(hello())
    server.handle(step())
    rebooted = PiLinkServer("train-controller-hw", journal)
    assert rebooted.handle(step(2))[0]["reason"] == "HELLO required"
    assert rebooted.handle(hello(version=999))[0]["op"] == "REJECTED"
    assert rebooted.handle(step(2))[0]["reason"] == "HELLO required"
    rebooted.handle(hello())
    assert rebooted.handle(step(2))[0]["op"] == "OUTPUTS"


def run_with_actions(journal, ticks):
    # A train, its gains set by actions, then ``ticks`` steps.
    from common.hw_link.tests.test_transports_recovery import request

    server = PiLinkServer("train-controller-hw", journal)
    server.handle(hello())
    server.handle(request(1))
    actions = [
        p.message(
            p.ACTION,
            100 + index,
            action="set_state",
            args={"train_id": "R1", "field": field, "value": value},
        )
        for index, (field, value) in enumerate((("kp", 120000), ("ki", 8000)))
    ]
    replies = [server.handle(action)[0] for action in actions]
    for tick in range(2, ticks + 1):
        server.handle(request(tick))
    return server, actions, replies


@pytest.mark.parametrize("ticks", [23, 230])
def test_checkpoint_bounds_journal_cache_and_restart(
    tmp_path, monkeypatch, ticks
):
    import common.hw_link.agent as agent
    from common.hw_link.tests.test_transports_recovery import request

    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 5)
    journal = tmp_path / "journal"
    server, actions, replies = run_with_actions(journal, ticks)
    last = server.handle(request(ticks))
    # Disk and memory stay flat however long the run.
    assert len(journal.read_text().splitlines()) <= 1 + 5
    assert len(list(tmp_path.glob("journal.ckpt*"))) == 1
    assert [k for k in server.cache if k[0] == "STEP"] == [
        ("STEP", ticks + 10, ticks)
    ]
    # A restart replays at most one checkpoint interval.
    executed = []
    original = PiLinkServer._execute
    monkeypatch.setattr(
        PiLinkServer,
        "_execute",
        lambda self, request: executed.append(request) or original(
            self, request
        ),
    )
    rebooted = PiLinkServer("train-controller-hw", journal)
    assert len(executed) <= 5
    before, after = server.core.fleet.get("R1"), rebooted.core.fleet.get("R1")
    assert vars(before.state) == vars(after.state)
    assert {k: v for k, v in vars(before).items() if k != "state"} == {
        k: v for k, v in vars(after).items() if k != "state"
    }
    # A resumed agent still answers the loads and the pending step from
    # its cache.
    assert rebooted.handle(hello())[0]["resumed"]
    assert [rebooted.handle(action)[0] for action in actions] == replies
    # Journal replies come back with lists for tuples: compare the wire.
    resent = rebooted.handle(request(ticks))
    assert [p.encode(m) for m in resent] == [p.encode(last[0])]
    assert not executed[5:]


def test_stale_agent_hash_starts_fresh(tmp_path, monkeypatch):
    import common.hw_link.agent as agent

    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 5)
    journal = tmp_path / "journal"
    run_with_actions(journal, 12)
    lines = journal.read_text().splitlines()
    header = json.loads(lines[0])
    header["agent_hash"] = "older-bundle"
    journal.write_text("\n".join([json.dumps(header), *lines[1:]]) + "\n")
    logs = []
    rebooted = PiLinkServer("train-controller-hw", journal, logs.append)
    assert rebooted.session is None and "R1" not in rebooted.core.fleet
    assert any("JOURNAL_STALE" in line for line in logs)
    assert not rebooted.handle(hello())[0]["resumed"]
    assert not list(tmp_path.glob("journal.ckpt*"))


def test_crash_mid_checkpoint_keeps_previous_checkpoint(tmp_path, monkeypatch):
    import common.hw_link.agent as agent
    from common.hw_link.tests.test_transports_recovery import request

    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 5)
    journal = tmp_path / "journal"
    server, _, _ = run_with_actions(journal, 8)
    # Power lost after the next checkpoint was written, before the
    # journal moved onto it.
    seq = server._checkpoint_seq
    (tmp_path / f"journal.ckpt{seq + 1}").write_bytes(b"half written")
    rebooted = PiLinkServer("train-controller-hw", journal)
    assert rebooted._checkpoint_seq == seq
    assert vars(rebooted.core.fleet.get("R1").state) == vars(
        server.core.fleet.get("R1").state
    )
    rebooted.handle(hello())
    for tick in range(9, 14):
        rebooted.handle(request(tick))
    assert rebooted._checkpoint_seq == seq + 1
    assert rebooted.core.fleet.get("R1").state.kp == 120000
