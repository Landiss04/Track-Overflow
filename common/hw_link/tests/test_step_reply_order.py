"""A STEP reply is completely written before its periodic VIEW is built.

These drive ``agent.main()`` over fake stdio file descriptors, a fake core
and a fake wall clock, and record one trace of core calls, encodes and
(partial) writes, so the order is observed on the production send path.
"""

import types

import pytest
from common.hw_link import agent
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
from common.hw_link.tests.test_protocol_agent import hello, step

MODULE = "train-controller-hw"


class FakeCore:
    """Records every call; each step takes 0.125 s of wall clock."""

    def __init__(self, trace, clock, fail_view=False):
        self.trace, self.clock, self.fail_view = trace, clock, fail_view
        self.steps = 0

    def step(self, request):
        self.steps += 1
        self.trace.append(("step", request["tick"]))
        self.clock[0] += 0.125
        return {"tick": request["tick"], "speed": 1.5, "name": "Ünï ✓"}

    def action(self, name, args):
        self.trace.append(("action", name))
        return {"done": name, "args": args}

    def view(self):
        self.trace.append(("view", self.steps))
        if self.fail_view:
            raise RuntimeError("display broke")
        return {"steps": self.steps}


class Delegate:
    """A module stand-in: given names overridden, the rest real."""

    def __init__(self, real, **names):
        self._real = real
        self.__dict__.update(names)

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture
def rig(monkeypatch, tmp_path):
    trace, clock = [], [10.0]
    rig = types.SimpleNamespace(
        trace=trace, clock=clock, journal=tmp_path / "journal", fail_view=False
    )
    monkeypatch.setattr(
        agent,
        "make_core",
        lambda module: FakeCore(trace, clock, rig.fail_view),
    )
    monkeypatch.setattr(
        agent, "time", Delegate(agent.time, monotonic=lambda: clock[0])
    )
    real_encode = p.encode

    def encode(message):
        trace.append(("encode", message["op"], message["tick"]))
        return real_encode(message)

    monkeypatch.setattr(p, "encode", encode)
    monkeypatch.setattr(agent, "keep_full_speed", lambda: None)

    def run(*chunks, write_size=5):
        """Feed ``chunks`` as successive reads; return the bytes written."""
        reads = list(chunks)
        written = bytearray()

        def read(fd, size):
            assert fd == 100
            return reads.pop(0) if reads else b""

        def write(fd, data):
            assert fd == 101
            # A short positive write, so starting a line is not finishing it.
            piece = bytes(data[:write_size])
            written.extend(piece)
            journal = rig.journal.read_bytes() if rig.journal.exists() else b""
            trace.append(("write", bytes(written), journal))
            return len(piece)

        monkeypatch.setattr(agent, "os", Delegate(agent.os, read=read, write=write))
        stdio = types.SimpleNamespace(
            stdin=types.SimpleNamespace(fileno=lambda: 100),
            stdout=types.SimpleNamespace(fileno=lambda: 101),
        )
        monkeypatch.setattr(agent, "sys", stdio)
        rig.result = agent.main(
            ["--module", MODULE, "--journal", str(rig.journal)]
        )
        return bytes(written)

    rig.run = run
    return rig


def lines(data):
    return [p.decode(line) for line in data.split(b"\n")[:-1]]


def completed(rig, predicate):
    """Trace index of the first write that finishes a matching line."""
    for index, event in enumerate(rig.trace):
        if event[0] == "write" and any(map(predicate, lines(event[1]))):
            return index
    raise AssertionError("no matching line was completely written")


def first(rig, event):
    return next(i for i, e in enumerate(rig.trace) if e[: len(event)] == event)


def is_outputs(tick):
    return lambda m: m["op"] == "OUTPUTS" and m["tick"] == tick


def test_step_reply_is_fully_written_before_view_is_built(rig):
    written = rig.run(p.encode(hello()) + p.encode(step(1)))

    assert [e for e in rig.trace if e[0] == "step"] == [("step", 1)]
    done = completed(rig, is_outputs(1))
    began = next(
        i
        for i, e in enumerate(rig.trace)
        if e[0] == "write" and b'"OUTPUTS"' in e[1]
    )
    # More than one positive write carried the reply line.
    assert done > began
    # Journalled before any byte of the acknowledgement went out.
    journal = rig.trace[began][2].splitlines()
    assert [line for line in journal if b'"STEP"' in line]
    assert b'"OUTPUTS"' in journal[-1]
    # The periodic VIEW is built and encoded only after the full reply.
    assert done < first(rig, ("view",))
    assert done < first(rig, ("encode", p.VIEW))
    assert [(m["op"], m["tick"]) for m in lines(written)] == [
        (p.HELLO, 0),
        ("OUTPUTS", 1),
        (p.VIEW, 1),
    ]
    assert lines(written)[2]["view"] == {"steps": 1}
    assert lines(written)[1]["outputs"]["name"] == "Ünï ✓"
    assert rig.result == 0


def test_one_chunk_keeps_order_throttle_and_action_view(rig):
    action = p.message(p.ACTION, 50, 1, action="set_gains", args={"kp": 2})
    written = rig.run(
        p.encode(hello())
        + p.encode(step(1))
        + p.encode(action)
        + p.encode(step(2))
        + p.encode(step(3))
    )
    replies = lines(written)
    # Steps end at 10.125, 10.25 and 10.375 s: only 0.125 s after the
    # first VIEW, step 2 gets none; step 3, 0.25 s after, does.
    assert [(m["op"], m["tick"]) for m in replies] == [
        (p.HELLO, 0),
        ("OUTPUTS", 1),
        (p.VIEW, 1),
        (p.ACK, 1),
        ("OUTPUTS", 2),
        ("OUTPUTS", 3),
        (p.VIEW, 3),
    ]
    assert replies[2]["view"] == {"steps": 1}
    assert replies[3]["id"] == 50
    assert replies[3]["result"] == {"done": "set_gains", "args": {"kp": 2}}
    assert replies[3]["view"] == {"steps": 1}
    assert replies[6]["view"] == {"steps": 3}
    for tick in (1, 3):
        view_encoded = next(
            i
            for i, e in enumerate(rig.trace)
            if e[:3] == ("encode", p.VIEW, tick)
        )
        assert completed(rig, is_outputs(tick)) < view_encoded
    assert [e[1] for e in rig.trace if e[0] == "step"] == [1, 2, 3]


def test_duplicate_step_is_answered_from_cache_without_executing(rig):
    written = rig.run(p.encode(hello()) + p.encode(step(1)), p.encode(step(1)))
    outputs = [
        line for line in written.split(b"\n") if b'"OUTPUTS"' in line
    ]
    assert len(outputs) == 2 and outputs[0] == outputs[1]
    assert [e for e in rig.trace if e[0] == "step"] == [("step", 1)]


def test_view_failure_after_sent_reply_cannot_reexecute_or_contradict(rig):
    rig.fail_view = True
    with pytest.raises(RuntimeError, match="display broke"):
        rig.run(p.encode(hello()) + p.encode(step(1)))
    written = rig.trace[completed(rig, is_outputs(1))][1]
    sent = [m for m in lines(written) if m["op"] == "OUTPUTS"]
    assert len(sent) == 1 and sent[0]["id"] == step(1)["id"]
    assert [e for e in rig.trace if e[0] == "step"] == [("step", 1)]

    # The host resends the same STEP to the restarted agent.
    rig.fail_view = False
    restarted = PiLinkServer(MODULE, rig.journal)
    executed = len([e for e in rig.trace if e[0] == "step"])
    restarted.handle(hello())
    assert restarted.handle(step(1)) == sent
    assert len([e for e in rig.trace if e[0] == "step"]) == executed


def test_handle_and_feed_still_return_lists(rig):
    server = PiLinkServer(MODULE)
    replies = server.handle(hello())
    assert isinstance(replies, list) and replies[0]["op"] == p.HELLO
    fed = server.feed(p.encode(step(1)) + p.encode(step(2)))
    assert isinstance(fed, list) and all(isinstance(b, bytes) for b in fed)
    assert [(p.decode(b)["op"], p.decode(b)["tick"]) for b in fed] == [
        ("OUTPUTS", 1),
        (p.VIEW, 1),
        ("OUTPUTS", 2),
    ]
    assert server.handle(step(2)) == [p.decode(fed[2])]
