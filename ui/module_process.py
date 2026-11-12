"""The Train Model process the central harness starts.

``track_overflow.py --module train-model --harness <server>`` runs
this. It holds every train's Train Model in one fleet, shows the Train
Model window, and steps the trains once per ``STEP`` from the harness
(D005, D006). Closing the window hides it; only the harness ends the
process.

Each ``STEP``'s inputs hold every train in service, each with its
line and its inputs in the JSON form of ``train_model.wire``::

    {"trains": {"G1": {"line": "Green",
                       "controller": {...}, "track": {...}}}}

A train named for the first time joins the fleet, and a train no
longer named leaves it: the CTC Office releases and retires trains,
and the harness keeps the roster (D022). Each train steps on its own
inputs. A train whose inputs are invalid does not step this tick; the
others do, and the reply names it (``modules/train-model.md``)::

    {"trains": {"G1": {"controller": {...}, "track": {...}}},
     "rejected": {"G2": "reason"}}

A rejected train's outputs are its last ones, unchanged.
"""

from __future__ import annotations

__all__ = ["TrainModelProcess", "main"]

import argparse
import signal
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from train_model.app import run_window
from train_model.fleet import TrainModelFleet
from train_model.model import TrainModelError
from train_model.wire import decode_inputs, encode_outputs
from utils.module_link import ModuleLink, TickRejectedError
from utils.module_window import keep_windows_open

#: This module's name, as the harness knows it.
MODULE_NAME = "train-model"

EXIT_QUIT = 0
EXIT_HARNESS_LOST = 2


class TrainModelProcess(QObject):
    """Drive a ``TrainModelFleet`` from the harness."""

    #: The harness ended the process, or went away; the exit code.
    finished = Signal(int)

    def __init__(
        self,
        fleet: TrainModelFleet,
        server_name: str,
        parent: QObject | None = None,
    ) -> None:
        """Prepare to drive ``fleet``; ``start`` connects.

        Args:
            fleet: The trains the window shows.
            server_name: The harness's local server.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._fleet = fleet
        self._epochs: dict[str, float] = {}
        self._link = ModuleLink(MODULE_NAME, server_name, self.step, self)
        self._link.quitRequested.connect(
            lambda: self.finished.emit(EXIT_QUIT)
        )
        self._link.harnessLost.connect(
            lambda: self.finished.emit(EXIT_HARNESS_LOST)
        )

    def start(self) -> None:
        """Connect, and say ``READY`` once the event loop runs."""
        self._link.connect_to_harness()
        QTimer.singleShot(0, self._link.announce_ready)

    def step(
        self,
        tick: int,
        dt: float,
        sim_time_s: float,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Follow the roster in ``inputs``, then step each train.

        Raises:
            TickRejectedError: If ``inputs`` has no ``trains`` object.
        """
        trains = inputs.get("trains")
        if not isinstance(trains, Mapping):
            raise TickRejectedError("inputs must hold a trains object")
        self._follow_roster(trains)
        self._fleet.set_harness_time(sim_time_s)
        outputs: dict[str, Any] = {}
        rejected: dict[str, str] = {}
        for train_id in self._fleet.ids():
            state = self._fleet.get(train_id)
            # First roster appearance, including a rejected first step.
            # Never realign this epoch to hide a missed physical tick.
            self._epochs.setdefault(train_id, sim_time_s - dt)
            try:
                train_inputs = decode_inputs(trains[train_id])
                state.validate_inputs(dt, train_inputs)
            except TrainModelError as error:
                rejected[train_id] = str(error)
                outputs[train_id] = encode_outputs(state.outputs())
                continue
            outputs[train_id] = encode_outputs(state.step(dt, train_inputs))
        if tick % 15 == 0:
            for train_id in self._fleet.ids():
                state = self._fleet.get(train_id)
                drift_s = (
                    self._epochs[train_id] + state.elapsed_s - sim_time_s
                )
                if state.set_clock_drift(drift_s, tick):
                    # Normal process diagnostics; the harness owns the log.
                    print(
                        f"[{MODULE_NAME}] train {train_id!r} clock drift "
                        f"{drift_s:+.9f} s at tick {tick}",
                        file=sys.stderr, flush=True,
                    )
        reply: dict[str, Any] = {"trains": outputs}
        if rejected:
            reply["rejected"] = rejected
        return reply

    def _follow_roster(self, trains: Mapping[str, Any]) -> None:
        # Retired trains leave, released ones join, with their line.
        for train_id in self._fleet.ids():
            if train_id not in trains:
                self._fleet.remove(train_id)
                self._epochs.pop(train_id, None)
        for train_id, entry in trains.items():
            if train_id not in self._fleet:
                line = entry.get("line", "") if isinstance(
                    entry, Mapping) else ""
                self._fleet.add(train_id, str(line))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Train Model process until the harness ends it.

    Args:
        argv: Options after ``--module train-model``.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(
        prog="track_overflow.py --module train-model",
        description="The Train Model process the harness starts.",
    )
    parser.add_argument(
        "--harness", required=True, help="the harness's local server"
    )
    options = parser.parse_args(argv)
    # Only the harness ends a module (D005); Ctrl+C in the console is
    # the harness's to handle.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    def build_context() -> dict[str, QObject]:
        # run_window has made the application by now.
        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            raise RuntimeError("the Train Model needs a QGuiApplication")
        keep_windows_open(app)
        fleet = TrainModelFleet()
        process = TrainModelProcess(fleet, options.harness, parent=fleet)
        process.finished.connect(app.exit)
        process.start()
        return {"fleet": fleet}

    return run_window("Train Model", "Main.qml", build_context)
