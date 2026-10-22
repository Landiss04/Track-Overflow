"""End-to-end tests of the harness with seven stub module processes.

Each test class starts the harness and a stub process for every
module, scripts faults into the stubs, runs to a chosen tick, stops,
and then checks what the harness and the stubs saw. Each class takes
a few real seconds.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import csv
import sys
import tempfile
import time
import unittest
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PySide6.QtCore import QCoreApplication, QEventLoop  # noqa: E402
from PySide6.QtNetwork import QLocalSocket  # noqa: E402

from common.harness.core import REPLY_TIMEOUT_S, Harness  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    MODULE_NAMES,
    PRODUCERS,
    TRACK_CONTROLLER_HW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    stub_specs,
)
from utils.event_log import EventLog  # noqa: E402
from utils.harness_protocol import encode, ready_message  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

START_TIME_S = 18000.0
DT_S = 0.1
# Generous: seven processes start at once, on any machine.
WAIT_S = 60.0

# (tick, source, event, detail), as logged.
Event = tuple[int, str, str, str]


def wait_until(
    condition: Callable[[], bool], timeout_s: float = WAIT_S
) -> bool:
    """Run the event loop until ``condition`` holds or time runs out."""
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            return False
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    return True


def pause_for(seconds: float) -> None:
    """Run the event loop for ``seconds``."""
    wait_until(lambda: False, timeout_s=seconds)


class _Trial:
    """One harness run with stubs, and a record of what happened."""

    def __init__(
        self,
        options: Mapping[str, Sequence[str]],
        reply_timeout_s: float = REPLY_TIMEOUT_S,
    ) -> None:
        self._folder = tempfile.TemporaryDirectory()
        self.log_path = Path(self._folder.name) / "events.csv"
        self.log = EventLog(self.log_path)
        self.harness = Harness(
            stub_specs(options), self.log, reply_timeout_s=reply_timeout_s
        )
        self.events: list[Event] = []
        # Every module's outputs as each tick completed.
        self.outputs: dict[int, dict[str, Mapping[str, Any]]] = {}
        self.completed_at_s: dict[int, float] = {}
        self.late: list[list[str]] = []
        self.down: list[str] = []
        self.exit_codes: dict[str, int | None] = {}
        self.harness.eventLogged.connect(self._on_event)
        self.harness.tickCompleted.connect(self._on_tick)
        self.harness.modulesLate.connect(self.late.append)
        self.harness.moduleDown.connect(self.down.append)
        self.harness.start()

    def _on_event(self, source: str, event: str, detail: str) -> None:
        self.events.append(
            (self.harness.clock.tick_count, source, event, detail)
        )

    def _on_tick(self, tick: int, _round_trip_s: float) -> None:
        self.outputs[tick] = self.harness.outputs
        self.completed_at_s[tick] = time.perf_counter()

    def run_to_tick(self, tick: int) -> None:
        """Wait until ``tick`` has completed."""
        if not wait_until(lambda: tick in self.outputs):
            raise AssertionError(
                f"tick {tick} never completed; events: {self.events}"
            )

    def find(self, event: str) -> list[Event]:
        """Return every logged ``event``."""
        return [each for each in self.events if each[2] == event]

    def stop(self) -> None:
        """Stop the harness and close the log."""
        self.exit_codes = self.harness.stop()
        self.log.close()

    def clean_up(self) -> None:
        """Stop, if not stopped yet, and remove the log folder."""
        self.stop()
        self._folder.cleanup()


class NormalRunTest(unittest.TestCase):
    """A run with every fault the run survives, one at a time.

    The CTC Office presses Run as soon as it is ready, asks for 10x
    from tick 3, and pauses for 300 ms at tick 10. The Train Model is
    ready last, and rejects tick 6. The Track Model sends its reply to
    tick 5 twice. Two strangers try to connect.
    """

    LAST_TICK = 20

    @classmethod
    def setUpClass(cls) -> None:
        cls.trial = _Trial(
            {
                CTC_OFFICE: [
                    "--run-on-ready",
                    "--speedup-at-tick", "3",
                    "--pause-at-tick", "10",
                    "--resume-after-ms", "300",
                ],
                TRAIN_MODEL: [
                    "--ready-delay-ms", "400",
                    "--reject-at-tick", "6",
                ],
                TRACK_MODEL: ["--duplicate-reply-at-tick", "5"],
            }
        )
        cls.addClassCleanup(cls.trial.clean_up)
        if not wait_until(lambda: cls.trial.find("ALL_READY")):
            raise AssertionError(f"never ready: {cls.trial.events}")
        cls.strangers = [
            cls._connect_stranger("nonsense"),
            cls._connect_stranger(CTC_OFFICE),
        ]
        cls.trial.run_to_tick(cls.LAST_TICK)
        cls.trial.stop()

    @classmethod
    def _connect_stranger(cls, module: str) -> QLocalSocket:
        # A process that claims to be a module, after the real ones.
        socket = QLocalSocket()
        socket.connectToServer(cls.trial.harness.server_name)
        socket.write(encode(ready_message(module)))
        socket.flush()
        return socket

    def test_ticks_run_in_order_without_gaps(self) -> None:
        ticks = sorted(self.trial.outputs)
        self.assertEqual(ticks, list(range(1, len(ticks) + 1)))
        self.assertGreaterEqual(ticks[-1], self.LAST_TICK)

    def test_every_module_answers_every_tick(self) -> None:
        for tick, outputs in self.trial.outputs.items():
            for name in MODULE_NAMES:
                rejected = name == TRAIN_MODEL and tick == 6
                with self.subTest(tick=tick, module=name):
                    self.assertEqual(
                        outputs[name]["tick"], tick - 1 if rejected else tick
                    )

    def test_each_step_carries_dt_and_unwrapped_time(self) -> None:
        for tick, outputs in self.trial.outputs.items():
            for name, values in outputs.items():
                if values["tick"] != tick:
                    continue
                with self.subTest(tick=tick, module=name):
                    self.assertEqual(values["dt"], DT_S)
                    self.assertAlmostEqual(
                        values["sim_time_s"], START_TIME_S + DT_S * tick
                    )

    def test_inputs_are_the_outputs_of_the_tick_before(self) -> None:
        for tick, outputs in self.trial.outputs.items():
            for name in MODULE_NAMES:
                values = outputs[name]
                if values["tick"] != tick:
                    continue
                expected = {
                    producer: tick - 1
                    for producer in PRODUCERS[name]
                    if tick > 1
                }
                if TRAIN_MODEL in expected and tick == 7:
                    # It rejected tick 6, so tick 5's outputs stand.
                    expected[TRAIN_MODEL] = 5
                with self.subTest(tick=tick, module=name):
                    self.assertEqual(values["inputs_ticks"], expected)

    def test_clock_waits_until_every_module_is_ready(self) -> None:
        events = [(source, event) for _, source, event, _ in self.trial.events]
        all_ready = events.index(("harness", "ALL_READY"))
        resumed = events.index(("harness", "CLOCK_RESUMED"))
        self.assertLess(all_ready, resumed)
        # The CTC Office pressed Run long before the Train Model was
        # ready, and nothing ticked until then.
        self.assertLess(
            events.index((CTC_OFFICE, "MODULE_READY")),
            events.index((TRAIN_MODEL, "MODULE_READY")),
        )
        before = self.trial.events[:resumed]
        self.assertTrue(all(each[0] == 0 for each in before))

    def test_ctc_office_speedup_sets_10x(self) -> None:
        self.assertEqual(
            self.trial.find("SPEED_CHANGED"),
            [(3, "harness", "SPEED_CHANGED", "10x")],
        )
        self.assertEqual(self.trial.harness.clock.speed, 10)

    def test_ctc_office_pause_and_resume(self) -> None:
        self.assertEqual(
            self.trial.find("CLOCK_PAUSED"),
            [(10, "harness", "CLOCK_PAUSED", f"paused by {CTC_OFFICE}")],
        )
        resumed = self.trial.find("CLOCK_RESUMED")
        self.assertEqual([each[0] for each in resumed], [0, 10])
        held_s = self.trial.completed_at_s[11] - self.trial.completed_at_s[10]
        self.assertGreaterEqual(held_s, 0.25)

    def test_rejected_tick_keeps_the_outputs_before(self) -> None:
        self.assertEqual(
            self.trial.find("TICK_REJECTED"),
            [
                (
                    6,
                    TRAIN_MODEL,
                    "TICK_REJECTED",
                    "rejection scripted at tick 6",
                )
            ],
        )
        self.assertEqual(self.trial.outputs[6][TRAIN_MODEL]["tick"], 5)
        # The tick is skipped, and the run goes on.
        self.assertEqual(self.trial.outputs[7][TRAIN_MODEL]["steps"], 6)

    def test_duplicate_reply_is_used_once(self) -> None:
        unexpected = self.trial.find("UNEXPECTED_REPLY")
        self.assertEqual([each[1] for each in unexpected], [TRACK_MODEL])
        self.assertIn("of tick 5", unexpected[0][3])
        for tick, outputs in self.trial.outputs.items():
            self.assertEqual(outputs[TRACK_MODEL]["steps"], tick)

    def test_strangers_are_refused(self) -> None:
        details = sorted(each[3] for each in self.trial.find("PROTOCOL_ERROR"))
        self.assertEqual(
            details,
            [
                "refused a connection: ctc-office is already connected",
                "refused a connection: no module 'nonsense' is expected",
            ],
        )
        for socket in self.strangers:
            self.assertEqual(
                socket.state(), QLocalSocket.LocalSocketState.UnconnectedState
            )

    def test_shutdown_ends_every_module_cleanly(self) -> None:
        self.assertEqual(self.trial.exit_codes, dict.fromkeys(MODULE_NAMES, 0))
        exited = self.trial.find("MODULE_EXITED")
        self.assertEqual(
            sorted((each[1], each[3]) for each in exited),
            sorted((name, "exit code 0") for name in MODULE_NAMES),
        )
        self.assertEqual(self.trial.events[-1][2], "HARNESS_STOPPED")

    def test_event_log_holds_every_event(self) -> None:
        with self.trial.log_path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(
            [
                (int(row["tick"]), row["source"], row["event"], row["detail"])
                for row in rows
            ],
            self.trial.events,
        )


class LateReplyTest(unittest.TestCase):
    """A reply past the timeout pauses the clock until it comes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.trial = _Trial(
            {
                CTC_OFFICE: ["--run-on-ready", "--speedup-at-tick", "0"],
                TRACK_CONTROLLER_HW: [
                    "--delay-ms", "700",
                    "--delay-at-tick", "4",
                ],
            },
            reply_timeout_s=0.3,
        )
        cls.addClassCleanup(cls.trial.clean_up)
        cls.trial.run_to_tick(8)
        cls.trial.stop()

    def test_late_module_is_named(self) -> None:
        self.assertEqual(self.trial.late, [[TRACK_CONTROLLER_HW]])
        self.assertEqual(
            self.trial.find("REPLY_LATE"),
            [
                (
                    4,
                    TRACK_CONTROLLER_HW,
                    "REPLY_LATE",
                    "no reply to tick 4 after 0.3 s",
                )
            ],
        )

    def test_clock_pauses_then_resumes_when_the_reply_comes(self) -> None:
        events = [(tick, event) for tick, _, event, _ in self.trial.events]
        paused = events.index((4, "CLOCK_PAUSED"))
        received = events.index((4, "LATE_REPLY_RECEIVED"))
        resumed = events.index((4, "CLOCK_RESUMED"))
        self.assertLess(paused, received)
        self.assertLess(received, resumed)
        self.assertEqual(
            self.trial.events[paused][3], f"waiting on {TRACK_CONTROLLER_HW}"
        )

    def test_nothing_is_lost(self) -> None:
        for tick in range(1, 9):
            for name in MODULE_NAMES:
                with self.subTest(tick=tick, module=name):
                    self.assertEqual(
                        self.trial.outputs[tick][name]["steps"], tick
                    )
        self.assertEqual(self.trial.exit_codes, dict.fromkeys(MODULE_NAMES, 0))


class CrashTest(unittest.TestCase):
    """A module that dies holds the clock for the rest of the run."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.trial = _Trial(
            {
                CTC_OFFICE: ["--run-on-ready", "--speedup-at-tick", "0"],
                TRAIN_CONTROLLER_SW: ["--exit-at-tick", "4"],
            }
        )
        cls.addClassCleanup(cls.trial.clean_up)
        cls.trial.run_to_tick(4)
        if not wait_until(lambda: cls.trial.find("MODULE_EXITED")):
            raise AssertionError(f"no exit seen: {cls.trial.events}")
        # Long enough for 30 ticks at 10x, were the clock running.
        pause_for(0.3)
        cls.tick_after_crash = cls.trial.harness.clock.tick_count
        cls.trial.stop()

    def test_crash_is_logged_and_holds_the_clock(self) -> None:
        self.assertEqual(self.trial.down, [TRAIN_CONTROLLER_SW])
        exits = [
            each[1:] for each in self.trial.find("MODULE_EXITED")
            if each[3] != "exit code 0"
        ]
        self.assertEqual(
            exits, [(TRAIN_CONTROLLER_SW, "MODULE_EXITED", "exit code 3")]
        )
        self.assertEqual(
            self.trial.find("CLOCK_PAUSED")[0][2:],
            ("CLOCK_PAUSED", f"down: {TRAIN_CONTROLLER_SW}"),
        )
        self.assertEqual(self.tick_after_crash, 4)

    def test_tick_in_flight_finishes_without_the_module(self) -> None:
        outputs = self.trial.outputs[4]
        for name in MODULE_NAMES:
            with self.subTest(module=name):
                expected = 3 if name == TRAIN_CONTROLLER_SW else 4
                self.assertEqual(outputs[name]["tick"], expected)

    def test_other_modules_end_cleanly(self) -> None:
        expected = dict.fromkeys(MODULE_NAMES, 0)
        expected[TRAIN_CONTROLLER_SW] = 3
        self.assertEqual(self.trial.exit_codes, expected)


class StopDuringStartupTest(unittest.TestCase):
    """Stopping while a module is still loading ends it at once."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.trial = _Trial({TRAIN_MODEL: ["--ready-delay-ms", "30000"]})
        cls.addClassCleanup(cls.trial.clean_up)
        others = len(MODULE_NAMES) - 1
        if not wait_until(
            lambda: len(cls.trial.find("MODULE_READY")) == others
        ):
            raise AssertionError(f"never ready: {cls.trial.events}")
        # Long enough for the loading module to have connected.
        pause_for(0.3)
        started_s = time.perf_counter()
        cls.trial.stop()
        cls.stop_s = time.perf_counter() - started_s

    def test_every_module_quits_without_being_killed(self) -> None:
        codes = dict(self.trial.exit_codes)
        # Connected, it is told to quit (0); not yet connected, it
        # finds no harness (2). Either way it ends by itself.
        self.assertIn(codes.pop(TRAIN_MODEL), (0, 2))
        self.assertEqual(set(codes.values()), {0})
        self.assertEqual(self.trial.find("MODULE_KILLED"), [])
        self.assertLess(self.stop_s, 3.0)

    def test_clock_never_ran(self) -> None:
        self.assertEqual(self.trial.outputs, {})
        self.assertEqual(self.trial.find("CLOCK_RESUMED"), [])


if __name__ == "__main__":
    unittest.main()
