"""Values the wire cannot carry, and lines that break the framing.

Covers both ends: ``utils.harness_protocol`` refuses numbers past the
range of a double and text that is not valid Unicode, whichever way
they travel; a line past the length limit costs only itself; a module
whose reply cannot be sent still answers its ``STEP``; and the event
log writes any text without raising.

Run from the repository root with ``python -m unittest discover utils``.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from typing import Any

from utils.event_log import EventLog
from utils.harness_protocol import (
    REJECTED,
    LineBuffer,
    ProtocolError,
    decode,
    encode,
    outputs_message,
    rejected_message,
    step_message,
)
from utils.module_link import ModuleLink, TickRejectedError
from utils.tests.test_module_link import _FakeHarness, wait_until

QUIT_PREFIX = b'{"op": "QUIT", "id": 0, "tick": 0, "value": '


def quit_with(value: bytes) -> bytes:
    """Return a ``QUIT`` line carrying one extra raw JSON value."""
    return QUIT_PREFIX + value + b"}"


class NumberRangeTest(unittest.TestCase):
    """Only numbers a double can hold cross the wire."""

    def test_overflowing_float_text_is_refused(self) -> None:
        # Valid JSON text that Python reads as infinity.
        for text in (b"1e999", b"-1e999", b"1.5e309"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ProtocolError, "out of range"):
                    decode(quit_with(text))

    def test_integer_past_a_double_is_refused(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "out of range"):
            decode(quit_with(b"9" * 400))
        with self.assertRaises(ProtocolError):
            decode(quit_with(b"9" * 5000))

    def test_large_finite_numbers_still_decode(self) -> None:
        for text, value in (
            (b"1.7e308", 1.7e308),
            (b"-1e-320", -1e-320),
            (str(10**300).encode(), 10**300),
        ):
            with self.subTest(text=text[:12]):
                self.assertEqual(decode(quit_with(text))["value"], value)

    def test_infinite_outputs_are_refused_on_encode(self) -> None:
        with self.assertRaises(ProtocolError):
            encode(outputs_message(1, 1, {"v": float("inf")}))


class UnicodeTest(unittest.TestCase):
    """Text crosses the wire only if it is valid Unicode."""

    def test_escaped_lone_surrogate_is_refused(self) -> None:
        for escape in (b'"\\udcff"', b'"a\\ud800b"', b'"\\uDFFF"'):
            with self.subTest(escape=escape):
                with self.assertRaisesRegex(ProtocolError, "Unicode"):
                    decode(quit_with(escape))

    def test_lone_surrogate_in_a_key_is_refused(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "Unicode"):
            decode(
                b'{"op": "QUIT", "id": 0, "tick": 0, "v": {"\\udcff": 1}}'
            )

    def test_surrogate_pairs_and_escaped_backslashes_decode(self) -> None:
        self.assertEqual(
            decode(quit_with(b'"\\ud83d\\ude82"'))["value"], "\U0001f682"
        )
        # A literal backslash before "ud800" is not an escape.
        self.assertEqual(
            decode(quit_with(b'"\\\\ud800"'))["value"], "\\ud800"
        )

    def test_lone_surrogate_is_refused_on_encode(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "Unicode"):
            encode(rejected_message(1, 1, "file \udcff"))

    def test_non_ascii_text_round_trips(self) -> None:
        message = rejected_message(1, 1, "Track Controller — SW, 15 °C")
        self.assertEqual(decode(encode(message)), message)


class FramingTest(unittest.TestCase):
    """A line past the limit is reported in place; the rest arrive."""

    def test_lines_around_an_overlong_line_arrive(self) -> None:
        lines = LineBuffer(max_line_bytes=8).feed(
            b'{"a":1}\n0123456789\n{"b":2}\n'
        )
        self.assertEqual(lines[0], b'{"a":1}')
        self.assertIsInstance(lines[1], ProtocolError)
        self.assertEqual(lines[2], b'{"b":2}')
        self.assertEqual(len(lines), 3)

    def test_overlong_line_in_pieces_is_reported_once(self) -> None:
        buffer = LineBuffer(max_line_bytes=8)
        first = buffer.feed(b'{"a":1}\n0123456789')
        self.assertEqual(first[0], b'{"a":1}')
        self.assertIsInstance(first[1], ProtocolError)
        self.assertEqual(buffer.feed(b"0123456789"), [])
        self.assertEqual(buffer.feed(b"0123\n{}\n"), [b"{}"])


class ModuleRepliesTest(unittest.TestCase):
    """A module answers every STEP, whatever its outputs hold."""

    def setUp(self) -> None:
        self.harness = _FakeHarness()
        self.addCleanup(self.harness.close)
        self.result: Any = {}
        self.link = ModuleLink("train-model", self.harness.name, self.step)
        self.addCleanup(self.link.close)
        self.losses: list[bool] = []
        self.link.harnessLost.connect(lambda: self.losses.append(True))
        self.link.announce_ready()
        self.link.connect_to_harness()
        self.assertTrue(wait_until(lambda: len(self.harness.received) == 1))

    def step(self, *_args: Any) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def reply_to(self, request: int, tick: int) -> dict[str, Any]:
        count = len(self.harness.received)
        self.harness.send(step_message(request, tick, 0.1, 18000.0, {}))
        self.assertTrue(
            wait_until(lambda: len(self.harness.received) > count)
        )
        return self.harness.received[-1]

    def test_unsendable_outputs_are_rejected(self) -> None:
        # Infinity, a huge integer, and text that is not Unicode.
        for kind, outputs in (
            ("infinity", {"v": float("inf")}),
            ("huge integer", {"v": 10**5000}),
            ("lone surrogate", {"v": "\udcff"}),
        ):
            with self.subTest(kind=kind):
                self.result = outputs
                reply = self.reply_to(3, 3)
                self.assertEqual(reply["op"], REJECTED)
                self.assertEqual((reply["id"], reply["tick"]), (3, 3))

    def test_rejection_reason_that_is_not_unicode_still_goes(self) -> None:
        # The reason itself held the bad text: the rejection failed to
        # encode and the STEP went unanswered.
        self.result = TickRejectedError("no layout \udcff")
        reply = self.reply_to(4, 4)
        self.assertEqual(reply["op"], REJECTED)
        self.assertEqual(reply["reason"], "no layout \\udcff")
        self.result = ValueError("bad \udcff")
        reply = self.reply_to(5, 5)
        self.assertEqual(reply["reason"], "ValueError: bad \\udcff")

    def test_overlong_line_from_the_harness_costs_only_itself(self) -> None:
        # The link used to give up on the harness, and the module quit.
        assert self.harness.socket is not None
        self.harness.socket.write(b"x" * (8 * 1024 * 1024 + 1) + b"\n")
        reply = self.reply_to(6, 6)
        self.assertEqual(reply["op"], "OUTPUTS")
        self.assertEqual(self.losses, [])


class EventLogTextTest(unittest.TestCase):
    """The event log writes any text, and never raises on it."""

    def test_lone_surrogate_is_escaped_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.csv"
            with EventLog(path) as log:
                log.write(
                    sim_time_s=1.0,
                    tick=1,
                    source="train-model",
                    event="TICK_REJECTED",
                    detail="bad \udcff",
                )
            with path.open(newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))
        self.assertEqual(rows[1][-1], "bad \\udcff")


if __name__ == "__main__":
    unittest.main()
