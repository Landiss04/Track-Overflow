"""Tests for the harness wire protocol in ``utils.harness_protocol``.

Run from the repository root with ``python -m unittest discover utils``.
"""

from __future__ import annotations

import json
import unittest

from utils.harness_protocol import (
    OUTPUTS,
    PROTOCOL_VERSION,
    QUIT,
    READY,
    REJECTED,
    STATE,
    STEP,
    LineBuffer,
    ProtocolError,
    decode,
    encode,
    outputs_message,
    quit_message,
    ready_message,
    rejected_message,
    state_message,
    step_message,
)


class RoundTripTest(unittest.TestCase):
    """Every message survives encode then decode unchanged."""

    def test_every_message_round_trips(self) -> None:
        messages = [
            step_message(41, 12, 0.1, 18001.2, {"ctc-office": {"tick": 11}}),
            quit_message(12),
            ready_message("track-model"),
            outputs_message(41, 12, {"clock_paused": False}),
            rejected_message(41, 12, "grade out of range"),
            state_message(12, {"clock_paused": True}),
        ]
        for message in messages:
            with self.subTest(op=message["op"]):
                self.assertEqual(decode(encode(message)), message)

    def test_a_message_is_one_line(self) -> None:
        line = encode(rejected_message(1, 1, "two\nlines"))
        self.assertTrue(line.endswith(b"\n"))
        self.assertEqual(line.count(b"\n"), 1)

    def test_ops_are_capitals(self) -> None:
        for op in (STEP, QUIT, READY, OUTPUTS, REJECTED, STATE):
            self.assertEqual(op, op.upper())

    def test_ready_carries_the_protocol_version(self) -> None:
        message = ready_message("ctc-office")
        self.assertEqual(message["protocol"], PROTOCOL_VERSION)
        self.assertEqual((message["id"], message["tick"]), (0, 0))


class ValidationTest(unittest.TestCase):
    """Malformed lines and messages are refused with a reason."""

    def assert_refused(self, line: bytes) -> None:
        with self.assertRaises(ProtocolError):
            decode(line)

    def test_not_json(self) -> None:
        self.assert_refused(b"{not json")

    def test_not_utf8(self) -> None:
        self.assert_refused(b'{"op": "\xff"}')

    def test_not_an_object(self) -> None:
        self.assert_refused(b"[1, 2]")

    def test_unknown_op(self) -> None:
        self.assert_refused(b'{"op": "step", "id": 1, "tick": 1}')

    def test_id_and_tick_must_be_non_negative_integers(self) -> None:
        for bad in ('"1"', "-1", "1.5", "true", "null"):
            with self.subTest(value=bad):
                self.assert_refused(
                    f'{{"op": "QUIT", "id": {bad}, "tick": 0}}'.encode()
                )
                self.assert_refused(
                    f'{{"op": "QUIT", "id": 0, "tick": {bad}}}'.encode()
                )

    def test_step_needs_a_positive_finite_dt(self) -> None:
        good = step_message(1, 1, 0.1, 18000.1, {})
        for bad in (0, -0.1, "0.1", True):
            with self.subTest(dt=bad):
                line = json.dumps({**good, "dt": bad}).encode()
                self.assert_refused(line)

    def test_nan_and_infinity_are_refused(self) -> None:
        self.assert_refused(
            b'{"op": "STEP", "id": 1, "tick": 1, "dt": NaN,'
            b' "sim_time_s": 1, "inputs": {}}'
        )
        self.assert_refused(
            b'{"op": "STEP", "id": 1, "tick": 1, "dt": 0.1,'
            b' "sim_time_s": Infinity, "inputs": {}}'
        )
        with self.assertRaises(ProtocolError):
            encode(step_message(1, 1, 0.1, float("nan"), {}))

    def test_missing_field(self) -> None:
        self.assert_refused(b'{"op": "OUTPUTS", "id": 1, "tick": 1}')

    def test_reason_must_not_be_empty(self) -> None:
        with self.assertRaises(ProtocolError):
            encode(rejected_message(1, 1, ""))

    def test_unencodable_value(self) -> None:
        with self.assertRaises(ProtocolError):
            encode(outputs_message(1, 1, {"value": object()}))


class LineBufferTest(unittest.TestCase):
    """Bytes arriving in pieces come out as whole lines."""

    def test_split_and_joined_lines(self) -> None:
        buffer = LineBuffer()
        self.assertEqual(buffer.feed(b'{"a":'), [])
        self.assertEqual(buffer.feed(b' 1}\n{"b": 2}\n{"c"'), [
            b'{"a": 1}',
            b'{"b": 2}',
        ])
        self.assertEqual(buffer.feed(b": 3}\n"), [b'{"c": 3}'])

    def test_blank_lines_are_skipped(self) -> None:
        self.assertEqual(LineBuffer().feed(b"\n\r\n  \n{}\n"), [b"{}"])

    def test_overlong_line_is_refused_and_cleared(self) -> None:
        buffer = LineBuffer(max_line_bytes=8)
        with self.assertRaises(ProtocolError):
            buffer.feed(b"0123456789")
        self.assertEqual(buffer.feed(b"{}\n"), [b"{}"])

    def test_overlong_complete_line_is_refused(self) -> None:
        with self.assertRaises(ProtocolError):
            LineBuffer(max_line_bytes=4).feed(b"0123456789\n")


if __name__ == "__main__":
    unittest.main()
