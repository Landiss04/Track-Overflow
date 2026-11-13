"""The journal is appended through one open handle, not one open per tick."""

import json
from pathlib import Path

import pytest
from common.hw_link import agent, protocol as p
from common.hw_link.agent import PiLinkServer
from utils.harness_protocol import step_message

MODULE = "train-controller-hw"


def hello():
    return p.message(
        p.HELLO, 1, module=MODULE, session="s", protocol=p.VERSION,
        agent_version="t", agent_hash="t",
    )


def step(tick):
    return step_message(tick + 10, tick, 0.1, 18000 + tick / 10, {"trains": {}})


@pytest.fixture
def opens(monkeypatch):
    """Count appends opened on any journal."""
    calls = []
    real = Path.open

    def counting(self, mode="r", *args, **kwargs):
        if mode == "ab":
            calls.append(self.name)
        return real(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting)
    return calls


def test_many_records_open_the_journal_once(tmp_path, opens):
    server = PiLinkServer(MODULE, tmp_path / "j.jsonl", durable=False)
    server.handle(hello())
    for tick in range(1, 31):
        server.handle(step(tick))
    server.close()
    assert opens == ["j.jsonl"]
    lines = (tmp_path / "j.jsonl").read_bytes().splitlines()
    assert [json.loads(l)["request"]["tick"] for l in lines[1:]] == list(
        range(1, 31)
    )


def test_a_checkpoint_replaces_the_file_and_appends_resume(
    tmp_path, opens, monkeypatch
):
    monkeypatch.setattr(agent, "CHECKPOINT_TICKS", 5)
    journal = tmp_path / "j.jsonl"
    server = PiLinkServer(MODULE, journal, durable=False)
    server.handle(hello())
    for tick in range(1, 13):
        server.handle(step(tick))
        server.settle()
    server.close()
    ticks = [json.loads(l).get("request", {}).get("tick")
             for l in journal.read_bytes().splitlines()[1:]]
    assert ticks == [11, 12]  # after the checkpoint at tick 10
    restored = PiLinkServer(MODULE, journal, durable=False)
    assert restored._applied == ["STEP", 22, 12]
    restored.close()
    # Initial, then once after each of the checkpoints at ticks 5 and 10.
    assert opens.count("j.jsonl") == 3
