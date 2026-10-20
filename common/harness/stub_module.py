"""A stand-in module process, for testing the harness (Phase 0).

A stub plays one module. It connects to the harness, says ``READY``,
and answers every ``STEP`` with outputs that show what it was given,
so a test can check the harness's tick fan-out, timing and edges
without any real module. Options script faults at chosen ticks: a slow
reply, a rejection, a duplicate reply, a crash.

Every stub's outputs hold:

- ``module``: the module it plays;
- ``tick``, ``dt`` and ``sim_time_s``: from the ``STEP`` it answers;
- ``steps``: how many steps it has taken; a rejected tick is not one;
- ``inputs_ticks``: for each producer in its inputs, the ``tick`` of
  that producer's outputs, which should be one tick behind;
- ``pad``: filler of ``--payload-bytes`` characters, if asked for.

The stub playing the CTC Office also reports ``clock_paused`` and
``clock_speedup``, as the CTC Office does. It starts paused, as the
clock does, and its options press Run, Pause and the speed toggle at
chosen moments. Run and the speed toggle pressed between ticks reach
the harness as ``STATE``. It also releases and retires trains on cue,
reporting them as the CTC Office does (D022): ``new_trains`` lists
``{"train_id", "line"}`` for each train released on a tick, and
``retired_trains`` lists ``{"train_id"}`` for each train retired.

Run it through the executable::

    python track_overflow.py --module stub --as ctc-office \\
        --harness <server> --run-on-ready

It exits with 0 on ``QUIT``, 2 if the harness goes away, and 3 when a
crash is scripted.
"""

from __future__ import annotations

__all__ = [
    "EXIT_HARNESS_LOST",
    "EXIT_QUIT",
    "EXIT_SCRIPTED_CRASH",
    "StubModule",
    "main",
]

import argparse
import os
import signal
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from common.harness.modules import CTC_OFFICE, MODULE_NAMES
from utils.module_link import ModuleLink, TickRejectedError

EXIT_QUIT = 0
EXIT_HARNESS_LOST = 2
EXIT_SCRIPTED_CRASH = 3

MILLISECONDS_PER_SECOND = 1000

# Options only the CTC Office's stub takes.
_CTC_OPTIONS = (
    "run_on_ready",
    "speedup_at_tick",
    "pause_at_tick",
    "resume_after_ms",
    "release_train",
    "retire_train",
)


class StubModule(QObject):
    """One stub module: its link, its state and its scripted faults."""

    #: The stub is done; carries the exit code.
    finished = Signal(int)

    def __init__(
        self,
        options: argparse.Namespace,
        parent: QObject | None = None,
    ) -> None:
        """Prepare a stub; ``start`` connects it.

        Args:
            options: Parsed command-line options.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._options = options
        self._steps = 0
        self._is_ctc = options.module == CTC_OFFICE
        self._paused = True
        self._speedup = options.speedup_at_tick == 0
        self._link = ModuleLink(
            options.module, options.harness, self.step, self
        )
        self._link.quitRequested.connect(
            lambda: self.finished.emit(EXIT_QUIT)
        )
        self._link.harnessLost.connect(
            lambda: self.finished.emit(EXIT_HARNESS_LOST)
        )

    def start(self) -> None:
        """Connect, then say ``READY`` after any scripted delay."""
        self._link.connect_to_harness()
        QTimer.singleShot(self._options.ready_delay_ms, self._announce)

    def step(
        self,
        tick: int,
        dt: float,
        sim_time_s: float,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Answer one ``STEP``, applying any fault scripted for it.

        Raises:
            TickRejectedError: If a rejection is scripted for ``tick``.
        """
        options = self._options
        if tick == options.exit_at_tick:
            print(
                f"[{options.module}] crash scripted at tick {tick}",
                file=sys.stderr,
                flush=True,
            )
            # No reply and no clean-up, as in a real crash.
            os._exit(EXIT_SCRIPTED_CRASH)
        if options.delay_ms and options.delay_at_tick in (None, tick):
            time.sleep(options.delay_ms / MILLISECONDS_PER_SECOND)
        if tick in options.reject_at_tick:
            raise TickRejectedError(f"rejection scripted at tick {tick}")
        self._steps += 1
        outputs: dict[str, Any] = {
            "module": options.module,
            "tick": tick,
            "steps": self._steps,
            "dt": dt,
            "sim_time_s": sim_time_s,
            "inputs_ticks": {
                producer: values.get("tick")
                for producer, values in inputs.items()
                if isinstance(values, Mapping)
            },
        }
        if options.payload_bytes:
            outputs["pad"] = "x" * options.payload_bytes
        if self._is_ctc:
            self._step_ctc(tick, outputs)
        if tick in options.duplicate_reply_at_tick:
            # After this reply is written, send it once more.
            QTimer.singleShot(0, self._send_reply_again)
        return outputs

    def _announce(self) -> None:
        # READY, then any Run or speed toggle pressed at startup.
        self._link.announce_ready()
        if not self._is_ctc:
            return
        if self._options.run_on_ready:
            self._paused = False
        if self._options.run_on_ready or self._speedup:
            self._link.push_state(self._clock_controls())

    def _step_ctc(self, tick: int, outputs: dict[str, Any]) -> None:
        # The CTC Office's header, pressed at the scripted ticks, and
        # the trains it releases and retires on them.
        options = self._options
        outputs["new_trains"] = [
            {"train_id": train_id, "line": line}
            for train_id, line, at_tick in options.release_train
            if at_tick == tick
        ]
        outputs["retired_trains"] = [
            {"train_id": train_id}
            for train_id, at_tick in options.retire_train
            if at_tick == tick
        ]
        if (
            options.speedup_at_tick is not None
            and tick >= options.speedup_at_tick
        ):
            self._speedup = True
        if tick == options.pause_at_tick:
            self._paused = True
            if options.resume_after_ms is not None:
                QTimer.singleShot(options.resume_after_ms, self._press_run)
        outputs.update(self._clock_controls())

    def _press_run(self) -> None:
        # Run pressed while the clock is paused: no step runs, so the
        # change goes as STATE.
        self._paused = False
        self._link.push_state(self._clock_controls())

    def _clock_controls(self) -> dict[str, bool]:
        # The CTC Office's two clock outputs.
        return {"clock_paused": self._paused, "clock_speedup": self._speedup}

    def _send_reply_again(self) -> None:
        # A duplicate of the last reply, same request ID and all.
        reply = self._link.last_reply
        if reply is not None:
            self._link.send(reply)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one stub module until the harness ends it.

    Args:
        argv: Options after ``--module stub``; defaults to the
            command line.

    Returns:
        The exit code.
    """
    options = _parse_args(argv)
    # Only the harness ends a module (G-RUN-7). Ctrl+C in a console
    # reaches every process attached to it, so the stub leaves it to
    # the harness, which sends QUIT.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    stub = StubModule(options)
    stub.finished.connect(app.exit)
    stub.start()
    return app.exec()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    # Options, checked; CTC-only options are refused for other roles.
    parser = argparse.ArgumentParser(
        prog="track_overflow.py --module stub",
        description="A stand-in module process for testing the harness.",
    )
    parser.add_argument(
        "--as",
        dest="module",
        required=True,
        choices=MODULE_NAMES,
        help="the module the stub plays",
    )
    parser.add_argument(
        "--harness",
        required=True,
        help="the harness's local server name",
    )
    parser.add_argument(
        "--ready-delay-ms",
        type=_non_negative,
        default=0,
        help="wait this long before saying READY",
    )
    parser.add_argument(
        "--delay-ms",
        type=_non_negative,
        default=0,
        help="take this long to answer a STEP",
    )
    parser.add_argument(
        "--delay-at-tick",
        type=_non_negative,
        help="delay only this tick's reply; every tick's if omitted",
    )
    parser.add_argument(
        "--reject-at-tick",
        type=_non_negative,
        action="append",
        default=[],
        help="reject this tick; may be repeated",
    )
    parser.add_argument(
        "--duplicate-reply-at-tick",
        type=_non_negative,
        action="append",
        default=[],
        help="send this tick's reply twice; may be repeated",
    )
    parser.add_argument(
        "--exit-at-tick",
        type=_non_negative,
        help="crash when this tick's STEP arrives, without replying",
    )
    parser.add_argument(
        "--payload-bytes",
        type=_non_negative,
        default=0,
        help="add this many bytes of filler to every reply",
    )
    ctc = parser.add_argument_group("CTC Office only")
    ctc.add_argument(
        "--run-on-ready",
        action="store_true",
        help="press Run right after READY",
    )
    ctc.add_argument(
        "--speedup-at-tick",
        type=_non_negative,
        help="ask for 10x from this tick on; 0 means from the start",
    )
    ctc.add_argument(
        "--pause-at-tick",
        type=_non_negative,
        help="press Pause during this tick",
    )
    ctc.add_argument(
        "--resume-after-ms",
        type=_non_negative,
        help="press Run this long after the scripted Pause",
    )
    ctc.add_argument(
        "--release-train",
        type=_release,
        action="append",
        default=[],
        metavar="ID:LINE@TICK",
        help="release a train from the yard on a tick; may be repeated",
    )
    ctc.add_argument(
        "--retire-train",
        type=_retire,
        action="append",
        default=[],
        metavar="ID@TICK",
        help="retire a train on a tick; may be repeated",
    )
    options = parser.parse_args(argv)
    if options.module != CTC_OFFICE:
        given = [
            name
            for name in _CTC_OPTIONS
            if getattr(options, name) is not None
            and getattr(options, name) is not False
            and getattr(options, name) != []
        ]
        if given:
            parser.error(
                f"only the {CTC_OFFICE} stub takes "
                + ", ".join("--" + name.replace("_", "-") for name in given)
            )
    if options.resume_after_ms is not None and options.pause_at_tick is None:
        parser.error("--resume-after-ms needs --pause-at-tick")
    return options


def _non_negative(text: str) -> int:
    # An option that counts ticks, bytes or milliseconds.
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {text}")
    return value


def _release(text: str) -> tuple[str, str, int]:
    # ID:LINE@TICK, such as G1:Green@1.
    train, _, tick = text.rpartition("@")
    train_id, _, line = train.partition(":")
    if not train_id or not line or not tick:
        raise argparse.ArgumentTypeError(
            f"expected ID:LINE@TICK, got {text!r}"
        )
    return train_id, line, _non_negative(tick)


def _retire(text: str) -> tuple[str, int]:
    # ID@TICK, such as G1@600.
    train_id, _, tick = text.rpartition("@")
    if not train_id or not tick:
        raise argparse.ArgumentTypeError(f"expected ID@TICK, got {text!r}")
    return train_id, _non_negative(tick)
