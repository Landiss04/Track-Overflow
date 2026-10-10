"""The test UI's link to the Train Model.

The test UI stands in for the Track Model, the Train Controller and the
clock, and runs as its own process. It drives the Train Model only
through the module boundary: ``step(dt, TrainModelInputs)`` returning
``TrainModelOutputs``. Once the system is integrated, the central
harness calls that same :meth:`TrainModelState.step` in place of this
link, and the test UI and this file are removed with no change to the
module.

One test UI at a time drives the Train Model: a second would step it
too, so the server refuses it with ``{"op": "busy"}`` until the first
leaves (Kevin). A test UI that takes over a train another one drove
gets it reset, to match its own fresh stand-ins (Kevin).

Two test-only commands ride alongside ``step``; integration never uses
them: clear the passenger brake latch (folded into a step so an invalid
step leaves the latch alone), and reset the module. Failures are set
only in the Train Model UI; the test UI sees their effect in the
outputs.

Wire format: newline-delimited JSON over a local socket (a named pipe on
Windows, a socket file elsewhere). Every request carries an ``id`` and
gets one reply with that ``id``: ``{"op": "outputs", "outputs":
...}`` or ``{"op": "error", ...}``. The server also pushes ``{"op":
"outputs"}`` with no ``id`` on connect and whenever a Train Model UI
action, a passenger pull or a failure, changes the outputs between
steps. Each line is handled on its own: one that is not a JSON object,
or a request with no integer ``id``, gets an error reply and is not
acted on, and the lines after it are still served.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Mapping

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from train_model.interface import (
    Beacon,
    ControllerCommands,
    ControllerOutputs,
    TrackInfo,
    TrackInputs,
    TrackOutputs,
    TrackSignal,
    TrainModelInputs,
    TrainModelOutputs,
)
from train_model.model import InvalidInputError, InvalidTimeStepError
from train_model.state import TrainModelState

#: Local socket name; the environment variable lets tests run beside a
#: Train Model that is already open.
SERVER_NAME = os.environ.get("TRAIN_MODEL_LINK", "trains-train-model")

_RECONNECT_MS = 1000
_REPLY_TIMEOUT_MS = 2000

#: Why the server refused a second test UI.
BUSY_MESSAGE = "Another test UI is connected to this Train Model"


class LinkError(Exception):
    """The Train Model could not be reached or failed to answer."""


# ---------------------------------------------------------------------- #
# Interface types on the wire
# ---------------------------------------------------------------------- #

def _beacon(data: Mapping[str, Any] | None) -> Beacon | None:
    return None if data is None else Beacon(**data)


def inputs_to_wire(inputs: TrainModelInputs) -> dict[str, Any]:
    """Encode inputs as plain JSON-ready data."""
    return dataclasses.asdict(inputs)


def inputs_from_wire(data: Mapping[str, Any]) -> TrainModelInputs:
    """Rebuild inputs exactly as the producer built them."""
    track = data["track"]
    return TrainModelInputs(
        controller=ControllerCommands(**data["controller"]),
        track=TrackInputs(
            track_info=TrackInfo(**track["track_info"]),
            track_signal=TrackSignal(**track["track_signal"]),
            beacon=_beacon(track["beacon"]),
            passengers_boarded=track["passengers_boarded"],
        ),
    )


def outputs_to_wire(outputs: TrainModelOutputs) -> dict[str, Any]:
    """Encode outputs as plain JSON-ready data."""
    return dataclasses.asdict(outputs)


def outputs_from_wire(data: Mapping[str, Any]) -> TrainModelOutputs:
    """Rebuild outputs exactly as the module produced them."""
    controller = dict(data["controller"])
    controller["beacon"] = _beacon(controller["beacon"])
    return TrainModelOutputs(
        controller=ControllerOutputs(**controller),
        track=TrackOutputs(**data["track"]),
    )


def _write(socket: QLocalSocket, message: Mapping[str, Any]) -> None:
    socket.write((json.dumps(message) + "\n").encode())


def _parse_line(data: bytes) -> tuple[dict[str, Any] | None, str]:
    """Decode one wire line: the message, or None and why not."""
    try:
        message = json.loads(data.decode("utf-8"))
    except UnicodeError:
        return None, "not UTF-8"
    except ValueError as exc:
        return None, f"not JSON: {exc}"
    except RecursionError:
        return None, "nested too deeply"
    if not isinstance(message, dict):
        return None, "not a JSON object"
    return message, ""


def _usable_id(message: Mapping[str, Any]) -> int | None:
    """The request's id, if it is a JSON integer; bool is not."""
    request_id = message.get("id")
    if isinstance(request_id, int) and not isinstance(request_id, bool):
        return request_id
    return None


def _lines(socket: QLocalSocket) -> list[bytes]:
    """Every complete, nonblank line waiting on ``socket``."""
    lines = []
    while socket.canReadLine():
        line = bytes(socket.readLine().data()).strip()
        if line:
            lines.append(line)
    return lines


# ---------------------------------------------------------------------- #
# Test UI side
# ---------------------------------------------------------------------- #

class LocalLink(QObject):
    """The link with the Train Model in the same process. For tests."""

    outputsChanged = Signal()
    connectedChanged = Signal()

    def __init__(
        self, state: TrainModelState, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._state = state
        state.snapshotChanged.connect(self.outputsChanged)
        state.failuresChanged.connect(self.outputsChanged)

    @property
    def connected(self) -> bool:
        """Always reachable."""
        return True

    @property
    def outputs(self) -> TrainModelOutputs | None:
        """The module's current outputs."""
        return self._state.outputs()

    def step(
        self, dt: float, inputs: TrainModelInputs, *,
        clear_passenger_brake: bool = False,
    ) -> TrainModelOutputs:
        """Advance the module one tick."""
        return self._state.step(
            dt, inputs, override_passenger_brake=clear_passenger_brake
        )

    def reset(self) -> None:
        """Test only: replace the module with a fresh one."""
        self._state.reset()


class SocketLink(QObject):
    """The link with the Train Model in another process.

    Requests block until the reply arrives; a local round trip is far
    shorter than a tick. While the Train Model is down every request
    raises :class:`LinkError` and the link keeps trying to connect.
    """

    outputsChanged = Signal()
    connectedChanged = Signal()

    def __init__(
        self, name: str = SERVER_NAME, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._outputs: TrainModelOutputs | None = None
        self._refusal = ""
        self._replies: dict[int, dict[str, Any]] = {}
        self._next_id = 0
        self._socket = QLocalSocket(self)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._drain)
        # Retry until the Train Model is up, and again if it restarts.
        self._retry = QTimer(self)
        self._retry.setInterval(_RECONNECT_MS)
        self._retry.timeout.connect(self._connect)
        self._retry.start()
        self._connect()

    @property
    def connected(self) -> bool:
        """Whether the Train Model is reachable and serving this link.

        A connection counts once the Train Model has sent its outputs,
        so one it refuses never shows as connected.
        """
        return self._outputs is not None and (
            self._socket.state()
            == QLocalSocket.LocalSocketState.ConnectedState
        )

    @property
    def refusal(self) -> str:
        """Why the Train Model last refused this link; empty if not."""
        return self._refusal

    @property
    def outputs(self) -> TrainModelOutputs | None:
        """The last outputs received; None while disconnected."""
        return self._outputs

    def step(
        self, dt: float, inputs: TrainModelInputs, *,
        clear_passenger_brake: bool = False,
    ) -> TrainModelOutputs:
        """Advance the module one tick and return its outputs."""
        self._call({
            "op": "step",
            "dt": dt,
            "inputs": inputs_to_wire(inputs),
            "clear_passenger_brake": clear_passenger_brake,
        })
        assert self._outputs is not None
        return self._outputs

    def reset(self) -> None:
        """Test only: replace the module with a fresh one."""
        self._call({"op": "reset"})

    def _connect(self) -> None:
        unconnected = QLocalSocket.LocalSocketState.UnconnectedState
        if self._socket.state() == unconnected:
            self._socket.connectToServer(self._name)

    def _on_disconnected(self) -> None:
        # A refused or dropped-before-served link was never connected.
        if self._outputs is None:
            return
        self._outputs = None
        self.connectedChanged.emit()
        self.outputsChanged.emit()

    def _call(self, request: dict[str, Any]) -> None:
        if not self.connected:
            raise LinkError(self._refusal or "Train Model is not running")
        self._next_id += 1
        request_id = self._next_id
        _write(self._socket, dict(request, id=request_id))
        self._socket.flush()
        while True:
            # Drain first: the reply may already be buffered.
            self._drain()
            if request_id in self._replies:
                break
            if not self._socket.waitForReadyRead(_REPLY_TIMEOUT_MS):
                raise LinkError("Train Model did not respond")
        reply = self._replies.pop(request_id)
        if reply["op"] == "error":
            raise _error_from_wire(reply)

    def _drain(self) -> None:
        for line in _lines(self._socket):
            # A line that is not a message is skipped: it must not stop
            # the lines after it.
            message, _ = _parse_line(line)
            if message is None:
                continue
            if message.get("op") == "busy":
                self._refusal = message["message"]
                self.connectedChanged.emit()
            if message.get("op") == "outputs":
                served = self._outputs is None
                self._outputs = outputs_from_wire(message["outputs"])
                if served:
                    self._refusal = ""
                    self.connectedChanged.emit()
                self.outputsChanged.emit()
            if "id" in message:
                self._replies[message["id"]] = message


def _error_from_wire(reply: Mapping[str, Any]) -> Exception:
    kind, message = reply["kind"], reply["message"]
    if kind == "time_step":
        return InvalidTimeStepError(message)
    if kind == "input":
        return InvalidInputError(message)
    return LinkError(message)


# ---------------------------------------------------------------------- #
# Train Model side
# ---------------------------------------------------------------------- #

class TestLinkServer(QObject):
    """Serves the Train Model to test UIs over a local socket."""

    __test__ = False  # not a pytest test class

    def __init__(
        self,
        state: TrainModelState,
        name: str = SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._name = name
        self._clients: list[QLocalSocket] = []
        self._requester: QLocalSocket | None = None
        # Whether a test UI has stepped the train since it was last
        # reset; the next test UI to take over then starts it fresh.
        self._driven = False
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)
        state.snapshotChanged.connect(self._push)
        state.failuresChanged.connect(self._push)

    def listen(self) -> bool:
        """Listen, unless another Train Model already serves the name."""
        probe = QLocalSocket()
        probe.connectToServer(self._name)
        if probe.waitForConnected(200):
            probe.disconnectFromServer()
            return False
        # Nothing answers: clear a socket file left by a crashed run.
        QLocalServer.removeServer(self._name)
        return self._server.listen(self._name)

    def _outputs_message(self) -> dict[str, Any]:
        return {
            "op": "outputs",
            "outputs": outputs_to_wire(self._state.outputs()),
        }

    def _accept(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if self._clients:
                # One test UI at a time: a second would step the module
                # too, its commands alternating with the first's.
                _write(socket, {"op": "busy", "message": BUSY_MESSAGE})
                socket.disconnectFromServer()
                socket.disconnected.connect(socket.deleteLater)
                continue
            if self._driven:
                # A new test UI takes over a train another one drove.
                # Its stand-ins start fresh, so the train does too
                # (Kevin).
                self._state.reset()
                self._driven = False
            self._clients.append(socket)
            # Bound slots, not lambdas: Qt drops these connections when
            # the server is destroyed, before its sockets die with it.
            socket.readyRead.connect(self._on_ready_read)
            socket.disconnected.connect(self._on_disconnected)
            socket.disconnected.connect(socket.deleteLater)
            _write(socket, self._outputs_message())

    @Slot()
    def _on_disconnected(self) -> None:
        socket = self.sender()
        if socket in self._clients:
            self._clients.remove(socket)

    @Slot()
    def _on_ready_read(self) -> None:
        socket = self.sender()
        if isinstance(socket, QLocalSocket):
            self._receive(socket)

    def _push(self) -> None:
        # The requester gets these outputs in its reply instead. Every
        # train changes during a step, so build the message only when
        # someone else will read it: building it per train is quadratic.
        others = [s for s in self._clients if s is not self._requester]
        if not others:
            return
        message = self._outputs_message()
        for socket in others:
            _write(socket, message)

    def _receive(self, socket: QLocalSocket) -> None:
        # Answer each line on its own, in order: a malformed line gets
        # an error reply and never blocks the lines after it.
        for line in _lines(socket):
            request, reason = _parse_line(line)
            if request is None:
                _write(socket, {"op": "error", "kind": "request",
                                "message": reason})
                continue
            request_id = _usable_id(request)
            if request_id is None:
                # No reply could be matched to it, so do not act on it.
                _write(socket, {"op": "error", "kind": "request",
                                "message": "no integer id"})
                continue
            self._requester = socket
            try:
                reply = self._handle(request)
            finally:
                self._requester = None
            _write(socket, dict(reply, id=request_id))

    def _handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        op = request.get("op")
        try:
            if op == "step":
                # A truthy string must not clear the passenger latch.
                if not isinstance(request["clear_passenger_brake"], bool):
                    raise LinkError(
                        "clear_passenger_brake must be true or false")
                self._state.step(
                    request["dt"],
                    inputs_from_wire(request["inputs"]),
                    override_passenger_brake=request[
                        "clear_passenger_brake"
                    ],
                )
                self._driven = True
            elif op == "reset":
                self._state.reset()
                self._driven = False
            else:
                raise LinkError(f"unknown request: {op!r}")
        except InvalidTimeStepError as exc:
            return {"op": "error", "kind": "time_step", "message": str(exc)}
        except (InvalidInputError, ValueError) as exc:
            return {"op": "error", "kind": "input", "message": str(exc)}
        except (KeyError, TypeError, LinkError) as exc:
            return {"op": "error", "kind": "request", "message": str(exc)}
        return self._outputs_message()
