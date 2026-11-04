"""Pi codec: fixed wire bytes, accepted normalisation and strict refusals.

Expected lines are written out literally, so a codec change cannot pass
just by encode and decode agreeing with each other.
"""

import pytest
from common.hw_link import protocol as p
from utils import harness_protocol as hp

QUIT = b'{"op":"QUIT","id":0,"tick":0'
HELLO = (
    b'{"op":"HELLO","id":1,"tick":0,"module":"train-controller-hw",'
    b'"session":"s","protocol":1,"agent_version":"v","agent_hash":"h"}\n'
)

WIRE = [
    (
        p.message(
            p.HELLO,
            1,
            module="train-controller-hw",
            session="s",
            protocol=p.VERSION,
            agent_version="v",
            agent_hash="h",
        ),
        HELLO,
    ),
    (
        p.message(p.ACTION, 7, 3, action="set_gains", args={"kp": 2.5, "t": "T1"}),
        b'{"op":"ACTION","id":7,"tick":3,"action":"set_gains",'
        b'"args":{"kp":2.5,"t":"T1"}}\n',
    ),
    (
        p.message(p.ACK, 7, 3, result={"ok": True}, view={"x": None}),
        b'{"op":"ACK","id":7,"tick":3,"result":{"ok":true},"view":{"x":null}}\n',
    ),
    (
        p.message(p.VIEW, 0, 5, view={"a": [1, 2.5, -2], "t": "Ü✓ 🚆"}),
        b'{"op":"VIEW","id":0,"tick":5,"view":{"a":[1,2.5,-2],'
        b'"t":"\xc3\x9c\xe2\x9c\x93 \xf0\x9f\x9a\x86"}}\n',
    ),
    (
        p.message(p.VIEW, 0, 0, view={"q": 'a"b\\c\n\t\x00'}),
        rb'{"op":"VIEW","id":0,"tick":0,"view":{"q":"a\"b\\c\n\t\u0000"}}'
        + b"\n",
    ),
    (
        hp.step_message(11, 1, 0.1, 18000.1, {"trains": {"T1": {"cmd": [3, -0.5]}}}),
        b'{"op":"STEP","id":11,"tick":1,"dt":0.1,"sim_time_s":18000.1,'
        b'"inputs":{"trains":{"T1":{"cmd":[3,-0.5]}}}}\n',
    ),
    (
        hp.outputs_message(
            11, 1, {"T1": {"power_w": 1e300, "doors": [False, True]}}
        ),
        b'{"op":"OUTPUTS","id":11,"tick":1,'
        b'"outputs":{"T1":{"power_w":1e+300,"doors":[false,true]}}}\n',
    ),
    (
        hp.rejected_message(4, 2, "not ready"),
        b'{"op":"REJECTED","id":4,"tick":2,"reason":"not ready"}\n',
    ),
    (hp.quit_message(9), b'{"op":"QUIT","id":0,"tick":9}\n'),
]


@pytest.mark.parametrize("message, line", WIRE)
def test_wire_bytes_are_compact_and_stable(message, line):
    assert p.encode(message) == line
    assert p.decode(line) == message
    # A request's identity is its re-encoded decoded form.
    assert p.encode(p.decode(line)) == line
    if message["op"] not in (p.HELLO, p.ACTION, p.ACK, p.VIEW):
        assert hp.encode(message) == line
        assert hp.decode(line) == p.decode(line)


@pytest.mark.parametrize(
    "view, expected",
    [
        ({"pos": (1, 2)}, {"pos": [1, 2]}),
        ({"x": [(1, (2,))]}, {"x": [[1, [2]]]}),
        ({1: "a"}, {"1": "a"}),
        ({True: "a"}, {"true": "a"}),
        ({None: "a"}, {"null": "a"}),
        ({2.5: "a"}, {"2.5": "a"}),
        # Keys that coincide once coerced: the receiver keeps the last.
        ({1: "a", "1": "b"}, {"1": "b"}),
        ({"big": 2**1000, "tiny": 5e-324}, {"big": 2**1000, "tiny": 5e-324}),
    ],
)
def test_accepted_normalisation_round_trips(view, expected):
    assert p.decode(p.encode(p.message(p.VIEW, view=view)))["view"] == expected


def step_line(**fields):
    body = {"op": "STEP", "id": 1, "tick": 1, "dt": 0.1, "sim_time_s": 0.1}
    body["inputs"] = {}
    body.update(fields)
    return repr(body).replace("'", '"').encode()


@pytest.mark.parametrize(
    "line",
    [
        b"\xff",
        QUIT + b',"x":"\xff"}',
        b"{",
        QUIT,
        b"[]",
        b"1",
        b'"x"',
        b"null",
        b'{"op":"NOPE","id":0,"tick":0}',
        b'{"op":5,"id":0,"tick":0}',
        b'{"id":0,"tick":0}',
        b'{"op":"QUIT","tick":0}',
        b'{"op":"QUIT","id":0}',
        b'{"op":"QUIT","id":true,"tick":0}',
        b'{"op":"QUIT","id":0,"tick":true}',
        b'{"op":"QUIT","id":-1,"tick":0}',
        b'{"op":"QUIT","id":0,"tick":-1}',
        b'{"op":"QUIT","id":1.5,"tick":0}',
        step_line(dt=0),
        step_line(dt=-0.1),
        step_line(dt="x"),
        step_line(inputs=[]),
        b'{"op":"STEP","id":1,"tick":1,"dt":0.1,"sim_time_s":0.1}',
        QUIT + b',"x":NaN}',
        QUIT + b',"x":Infinity}',
        QUIT + b',"x":-Infinity}',
        QUIT + b',"x":1e999}',
        QUIT + b',"x":1' + b"0" * 399 + b"}",
        QUIT + rb',"x":"\ud800"}',
        QUIT + rb',"\udc00":1}',
        QUIT + b',"x":' + b"[" * 100000 + b"]" * 100000 + b"}",
        HELLO.replace(b',"agent_hash":"h"', b""),
        HELLO.replace(b"train-controller-hw", b"x"),
        HELLO.replace(b'"protocol":1', b'"protocol":"1"'),
        HELLO.replace(b'"session":"s"', b'"session":""'),
        HELLO.replace(b'"id":1', b'"id":true'),
        b'{"op":"ACTION","id":2,"tick":0,"action":""}',
        b'{"op":"ACTION","id":2,"tick":0,"action":"a","args":[]}',
        b'{"op":"VIEW","id":0,"tick":0}',
        b'{"op":"VIEW","id":0,"tick":0,"view":[]}',
        b'{"op":"ACK","id":-2,"tick":0}',
    ],
)
def test_decode_refuses_with_protocol_error(line):
    with pytest.raises(hp.ProtocolError):
        p.decode(line)


def circular():
    value = {}
    value["self"] = value
    return value


@pytest.mark.parametrize(
    "message",
    [
        p.message(p.VIEW, view={"a": [float("nan")]}),
        p.message(p.VIEW, view={"a": {"b": float("-inf")}}),
        hp.outputs_message(1, 1, {"x": {"y": float("inf")}}),
        p.message(p.VIEW, view={"t": "\ud800"}),
        p.message(p.VIEW, view={"\ud800": 1}),
        hp.outputs_message(1, 1, {"t": "\udcff"}),
        p.message(p.VIEW, view={"o": object()}),
        p.message(p.VIEW, view={"s": {1, 2}}),
        p.message(p.VIEW, view=circular()),
        p.message(p.ACK, True, 0),
        p.message(p.ACK, -1, 0),
        p.message(p.ACK, 0, -1),
        p.message("NOPE"),
        p.message(p.HELLO, 1, module="train-controller-hw"),
        p.message(p.ACTION, 1, action="a", args=[]),
        hp.step_message(1, 1, 0, 0.0, {}),
        hp.step_message(1, 1, float("nan"), 0.0, {}),
        {"op": "OUTPUTS", "id": 1, "tick": 1},
        hp.quit_message(-1),
    ],
)
def test_encode_refuses_with_protocol_error(message):
    with pytest.raises(hp.ProtocolError):
        p.encode(message)


@pytest.mark.parametrize("message, line", WIRE[:5])
def test_pi_ops_stay_out_of_the_shared_codec(message, line):
    with pytest.raises(hp.ProtocolError):
        hp.encode(message)
    with pytest.raises(hp.ProtocolError):
        hp.decode(line)
    assert p.decode(line) == message


@pytest.mark.parametrize("ending", [b"", b"\n", b"\r\n"])
def test_decode_with_or_without_newline(ending):
    assert p.decode(HELLO.rstrip(b"\n") + ending) == WIRE[0][0]
