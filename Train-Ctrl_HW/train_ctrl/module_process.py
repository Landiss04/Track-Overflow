"""The Train Controller process the central harness starts.

``track_overflow.py --module train-controller-sw --harness <server>``
runs this for the Green Line's trains (D021). It holds every train's
controller in one ``TrainControllerFleet``, shows the console for
those trains, and steps the fleet once per ``STEP`` from the harness
(D005). The console does not step the trains itself
(``HARNESS_INTEGRATION.md``). Closing the console hides it; only the
harness ends the process.

Each ``STEP``'s inputs hold every train in service, each with its
line and its inputs in the keys ``read_inputs`` takes::

    {"trains": {"G1": {"line": "Green",
                       "inputs": {"commanded_speed": 12.0, ...}}}}

A train named for the first time joins the fleet, and a train no
longer named leaves it (D022). The reply holds each train's
``TrainModelCommands``, field by field::

    {"trains": {"G1": {"power_w": 0.0, "service_brake": false, ...}}}

The fleet steps all trains or none, so inputs it refuses reject the
whole tick. Each module reads the others' outputs from the tick before
(D017), so a command comes back in a Train Model report two ticks
later; the fleet is told so, and takes those reports of its own
emergency brake for what they are, not for passenger pulls.

A new train applies no power until an engineer sets its gains in the
console (D024). For automated tests only, ``--engineer-gains KP KI``
plays the engineer: it sets those gains on each train as it joins.
The harness never passes it in a real run.
"""

from __future__ import annotations

__all__ = ["TrainControllerProcess", "main"]

import argparse
import dataclasses
import signal
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from utils.module_link import ModuleLink, TickRejectedError
from utils.module_window import keep_windows_open

from .constants import ECHO_TICKS
from .control import ControllerCore
from .errors import TrainControllerError
from .fleet import TrainControllerFleet

#: The variants this process can run as, by module name.
MODULE_NAMES = ("train-controller-sw",)

EXIT_QUIT = 0
EXIT_HARNESS_LOST = 2


class TrainControllerProcess(QObject):
    """Drive a ``TrainControllerFleet`` from the harness."""

    #: The harness ended the process, or went away; the exit code.
    finished = Signal(int)

    def __init__(
        self,
        fleet: TrainControllerFleet,
        module: str,
        server_name: str,
        engineer_gains: tuple[float, float] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Prepare to drive ``fleet``; ``start`` connects.

        Args:
            fleet: The trains the console shows.
            module: This module's name, as the harness knows it.
            server_name: The harness's local server.
            engineer_gains: Tests only: Kp and Ki to set on each train
                as it joins, standing in for the engineer.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._fleet = fleet
        self._engineer_gains = engineer_gains
        self._link = ModuleLink(module, server_name, self.step, self)
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
        """Follow the roster in ``inputs``, then step every train.

        Raises:
            TickRejectedError: If the inputs are not shaped as above,
                or the fleet refuses them.
        """
        trains = inputs.get("trains")
        if not isinstance(trains, Mapping) or not all(
            isinstance(entry, Mapping)
            and isinstance(entry.get("inputs"), Mapping)
            for entry in trains.values()
        ):
            raise TickRejectedError(
                "inputs must hold a trains object, with inputs per train"
            )
        self._follow_roster(trains)
        try:
            commands = self._fleet.step_all(
                dt,
                {
                    train_id: dict(entry["inputs"])
                    for train_id, entry in trains.items()
                },
                sim_time_s,
            )
        except TrainControllerError as error:
            raise TickRejectedError(str(error)) from error
        return {
            "trains": {
                train_id: dataclasses.asdict(train_commands)
                for train_id, train_commands in commands.items()
            }
        }

    def _follow_roster(self, trains: Mapping[str, Any]) -> None:
        # Retired trains leave, released ones join, with their line.
        for train_id in self._fleet.ids():
            if train_id not in trains:
                self._fleet.remove(train_id)
        for train_id, entry in trains.items():
            if train_id not in self._fleet:
                core = self._fleet.add(train_id, str(entry.get("line", "")))
                if self._engineer_gains is not None:
                    _play_engineer(core, *self._engineer_gains)


def _play_engineer(core: ControllerCore, kp: float, ki: float) -> None:
    # Tests only: what ConsoleBackend.commission_gains does once an
    # engineer signs in and sets the gains.
    core.state.kp = max(0.0, kp)
    core.state.ki = max(0.0, ki)
    core.integral = 0.0
    core.armed = True


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Train Controller process until the harness ends it.

    Args:
        argv: ``--as <module>`` and the options after it.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(
        prog="track_overflow.py --module train-controller-sw",
        description="The Train Controller process the harness starts.",
    )
    parser.add_argument(
        "--as",
        dest="module",
        choices=MODULE_NAMES,
        default=MODULE_NAMES[0],
        help="the variant this process runs as",
    )
    parser.add_argument(
        "--harness", required=True, help="the harness's local server"
    )
    parser.add_argument(
        "--engineer-gains",
        nargs=2,
        type=float,
        metavar=("KP", "KI"),
        help="tests only: set these gains on each train as it joins",
    )
    options = parser.parse_args(argv)
    # Only the harness ends a module (D005); Ctrl+C in the console is
    # the harness's to handle.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    keep_windows_open(app)
    # Under the harness a command comes back in a report ECHO_TICKS
    # steps later.
    fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
    process = TrainControllerProcess(
        fleet,
        options.module,
        options.harness,
        engineer_gains=(
            None if options.engineer_gains is None
            else tuple(options.engineer_gains)
        ),
        parent=app,
    )
    process.finished.connect(app.exit)
    process.start()
    # Imported here: the console needs the repository root and this
    # folder on the import path, which the caller has set.
    from .app import run

    return run(console=True, bench=False, fleet=fleet)
