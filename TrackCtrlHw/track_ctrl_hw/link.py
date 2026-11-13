"""The link between the Track Controller window and its test UI.

The two run as separate processes (decision D010 sets the pattern). The
Track Controller window hosts the module and a ``TestLinkServer``. The
test UI stands in for the CTC Office, the Track Model and the clock,
and drives the module through ``TestLinkClient`` using only the module
boundary: ``step(dt, inputs)`` returning the outputs. Integrated, the
central harness calls ``TrackController.step`` directly instead; the
test UI and this file stay, so the module can still be demonstrated on
its own, and the module never depends on them.

Wire format: one JSON object per line over a Qt local socket, a named
pipe on Windows and a socket file elsewhere, never a network
connection. The same convention as the Train Model and CTC Office test
links.

- Test UI to Track Controller: ``{"id": 7, "op": "step", "dt": 0.1,
  "inputs": {...}}`` or ``{"id": 8, "op": "reset"}``.
- Each request gets one reply with its ``id``: ``{"op": "outputs",
  "outputs": {...}}`` or ``{"op": "error", "kind": ..., "message":
  ...}``.
- The Track Controller also pushes, with no ``id``: ``{"op":
  "territories", ...}`` on connect and whenever a database is loaded,
  and ``{"op": "outputs", ...}`` on connect.

One test UI at a time: a second is refused with ``{"op": "busy"}``.
Every line is checked on its own; a malformed one gets an error reply
and never blocks the lines after it.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from track_ctrl_hw.controller import HwTrackController
from track_ctrl_hw.errors import (
    InvalidInputError,
    InvalidTimeStepError,
    TrackControllerError,
    WireFormatError,
)
from track_ctrl_hw.interface import (
    Territory,
    TrackControllerInputs,
    TrackControllerOutputs,
)
from track_ctrl_hw.wire import (
    inputs_from_wire,
    inputs_to_wire,
    outputs_from_wire,
    outputs_to_wire,
    territory_from_wire,
    territory_to_wire,
)

#: Local socket name; the environment variable lets tests run beside a
#: Track Controller that is already open.
SERVER_NAME = os.environ.get(
    "TRACK_CTRL_HW_LINK", "trains-track-controller-hw"
)

BUSY_MESSAGE = "Another test UI is connected to this Track Controller."

_PROBE_TIMEOUT_MS = 300
_RECONNECT_MS = 1000
_REPLY_TIMEOUT_MS = 2000


class LinkError(TrackControllerError):
    """The Track Controller could not be reached or did not answer."""


def _send(socket: QLocalSocket, message: Mapping[str, Any]) -> None:
    socket.write((json.dumps(message) + "\n").encode("utf-8"))
    socket.flush()


def _read_lines(socket: QLocalSocket) -> list[bytes]:
    # Every complete, non-blank line waiting; a partial line stays
    # buffered in the socket until the rest arrives.
    lines = []
    while socket.canReadLine():
        line = bytes(socket.readLine().data()).strip()
        if line:
            lines.append(line)
    return lines


def _decode(line: bytes) -> tuple[dict[str, Any] | None, str]:
    # One wire line as a message, or None and the reason it is not one.
    try:
        message = json.loads(line.decode("utf-8"))
    except UnicodeDecodeError:
        return None, "not UTF-8"
    except ValueError as error:
        return None, f"not JSON: {error}"
    except RecursionError:
        return None, "nested too deeply"
    if not isinstance(message, dict):
        return None, "not a JSON object"
    return message, ""


def _request_id(message: Mapping[str, Any]) -> int | None:
    value = message.get("id")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


# ------------------------------------------------------------------ #
# Track Controller side
# ------------------------------------------------------------------ #

class TestLinkServer(QObject):
    """Serves the Track Controller module to one test UI."""

    __test__ = False  # not a pytest test class

    #: A step from the test UI was applied to the module.
    stepped = Signal()
    #: The module was reset by the test UI.
    reset = Signal()
    connectedChanged = Signal()

    def __init__(
        self,
        controller: HwTrackController,
        name: str = SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._name = name
        self._client: QLocalSocket | None = None
        self._outputs: TrackControllerOutputs | None = None
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)

    @property
    def connected(self) -> bool:
        """Whether a test UI is connected."""
        return self._client is not None

    @property
    def outputs(self) -> TrackControllerOutputs | None:
        """Outputs of the last step the test UI sent."""
        return self._outputs

    def listen(self) -> bool:
        """Start serving. False if another Track Controller serves the
        name already; a socket left behind by a crash is cleared."""
        probe = QLocalSocket()
        probe.connectToServer(self._name)
        if probe.waitForConnected(_PROBE_TIMEOUT_MS):
            probe.abort()
            return False
        probe.abort()
        QLocalServer.removeServer(self._name)
        return self._server.listen(self._name)

    def close(self) -> None:
        """Stop serving and drop the test UI, before shutdown."""
        client, self._client = self._client, None
        if client is not None:
            client.readyRead.disconnect(self._on_ready_read)
            client.disconnected.disconnect(self._on_disconnected)
            client.abort()
            client.deleteLater()
        self._server.close()

    def push_territories(self) -> None:
        """Send the loaded territories to the test UI, if one is here."""
        if self._client is not None:
            _send(self._client, self._territories_message())

    def _territories_message(self) -> dict[str, Any]:
        snapshot = self._controller.snapshot()
        return {
            "op": "territories",
            "line": snapshot.line,
            "territories": [
                territory_to_wire(wayside.territory)
                for wayside in snapshot.waysides
            ],
        }

    def _accept(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if self._client is not None:
                # One test UI at a time: a second would step the module
                # too, its ticks interleaved with the first's.
                _send(socket, {"op": "busy", "message": BUSY_MESSAGE})
                socket.disconnected.connect(socket.deleteLater)
                socket.disconnectFromServer()
                continue
            self._client = socket
            # Bound slots rather than lambdas, so nothing outlives the
            # server holding a socket Qt has already freed.
            socket.readyRead.connect(self._on_ready_read)
            socket.disconnected.connect(self._on_disconnected)
            _send(socket, self._territories_message())
            if self._outputs is not None:
                _send(socket, {
                    "op": "outputs",
                    "outputs": outputs_to_wire(self._outputs),
                })
            self.connectedChanged.emit()

    @Slot()
    def _on_disconnected(self) -> None:
        socket = self.sender()
        if socket is not None and socket is self._client:
            self._client = None
            socket.deleteLater()
            self.connectedChanged.emit()

    @Slot()
    def _on_ready_read(self) -> None:
        socket = self.sender()
        if not isinstance(socket, QLocalSocket) or socket is not self._client:
            return
        stepped = False
        for line in _read_lines(socket):
            request, reason = _decode(line)
            if request is None:
                _send(socket, {"op": "error", "kind": "request",
                               "message": reason})
                continue
            request_id = _request_id(request)
            if request_id is None:
                # No reply could be matched to it, so it is not acted on.
                _send(socket, {"op": "error", "kind": "request",
                               "message": "no integer id"})
                continue
            reply, kind = self._handle(request)
            stepped |= kind == "step"
            if kind == "reset":
                self.reset.emit()
            _send(socket, dict(reply, id=request_id))
        if stepped:
            self.stepped.emit()

    def _handle(
        self, request: Mapping[str, Any]
    ) -> tuple[dict[str, Any], str]:
        op = request.get("op")
        try:
            if op == "step":
                inputs = inputs_from_wire(request.get("inputs"))
                outputs = self._controller.step(request.get("dt"), inputs)
                self._outputs = outputs
                return {
                    "op": "outputs",
                    "outputs": outputs_to_wire(outputs),
                }, "step"
            if op == "reset":
                self._controller.reset()
                self._outputs = None
                return {"op": "outputs", "outputs": None}, "reset"
            raise WireFormatError(f"unknown request {op!r}")
        except InvalidTimeStepError as error:
            return {"op": "error", "kind": "time_step",
                    "message": str(error)}, ""
        except (InvalidInputError, WireFormatError) as error:
            return {"op": "error", "kind": "input", "message": str(error)}, ""


# ------------------------------------------------------------------ #
# Test UI side
# ------------------------------------------------------------------ #

class TestLinkClient(QObject):
    """The test UI's connection to a running Track Controller.

    Requests block until their reply arrives; a local round trip takes
    far less than a tick. While no Track Controller is running every
    request raises ``LinkError`` and the client keeps trying to connect.
    """

    __test__ = False  # not a pytest test class

    connectedChanged = Signal()
    territoriesChanged = Signal()
    outputsChanged = Signal()

    def __init__(
        self, name: str = SERVER_NAME, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._served = False
        self._refusal = ""
        self._line: str | None = None
        self._territories: tuple[Territory, ...] = ()
        self._outputs: TrackControllerOutputs | None = None
        self._replies: dict[int, dict[str, Any]] = {}
        self._next_id = 0
        self._socket = QLocalSocket(self)
        self._socket.readyRead.connect(self._drain)
        self._socket.disconnected.connect(self._on_disconnected)
        self._retry = QTimer(self)
        self._retry.setInterval(_RECONNECT_MS)
        self._retry.timeout.connect(self._connect)
        self._retry.start()
        self._connect()

    @property
    def connected(self) -> bool:
        """Whether a Track Controller is serving this test UI.

        It counts once the Track Controller has sent its territories,
        so a test UI it refused never shows as connected.
        """
        return self._served and (
            self._socket.state()
            == QLocalSocket.LocalSocketState.ConnectedState
        )

    @property
    def refusal(self) -> str:
        """Why the Track Controller last refused this test UI, or ""."""
        return self._refusal

    @property
    def line(self) -> str | None:
        """The line the Track Controller runs, once it has one."""
        return self._line

    @property
    def territories(self) -> tuple[Territory, ...]:
        """Every loaded wayside's territory, in load order."""
        return self._territories

    @property
    def outputs(self) -> TrackControllerOutputs | None:
        """The last outputs received; None until a step is answered."""
        return self._outputs

    def step(
        self, dt: float, inputs: TrackControllerInputs
    ) -> TrackControllerOutputs:
        """Scan the module once and return its outputs.

        Raises:
            LinkError: If no Track Controller answers.
            InvalidTimeStepError: If the module rejects ``dt``.
            InvalidInputError: If the module rejects the inputs.
        """
        reply = self._call({
            "op": "step", "dt": dt, "inputs": inputs_to_wire(inputs),
        })
        outputs = outputs_from_wire(reply.get("outputs"))
        self._outputs = outputs
        self.outputsChanged.emit()
        return outputs

    def reset(self) -> None:
        """Test only: return the module to its state after loading."""
        self._call({"op": "reset"})
        self._outputs = None
        self.outputsChanged.emit()

    def close(self) -> None:
        """Disconnect and stop retrying, before shutdown."""
        self._retry.stop()
        self._socket.readyRead.disconnect(self._drain)
        self._socket.disconnected.disconnect(self._on_disconnected)
        self._socket.abort()

    def _connect(self) -> None:
        unconnected = QLocalSocket.LocalSocketState.UnconnectedState
        if self._socket.state() == unconnected:
            self._socket.connectToServer(self._name)

    @Slot()
    def _on_disconnected(self) -> None:
        if not self._served:
            return
        self._served = False
        self._outputs = None
        self.connectedChanged.emit()
        self.outputsChanged.emit()

    def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.connected:
            raise LinkError(self._refusal or "The Track Controller is not "
                            "running. Start it, then load a database.")
        self._next_id += 1
        request_id = self._next_id
        _send(self._socket, dict(request, id=request_id))
        while True:
            # The reply may already be buffered: drain before waiting.
            self._drain()
            if request_id in self._replies:
                break
            if not self._socket.waitForReadyRead(_REPLY_TIMEOUT_MS):
                raise LinkError("The Track Controller did not answer.")
        reply = self._replies.pop(request_id)
        if reply.get("op") == "error":
            message = str(reply.get("message", "request rejected"))
            if reply.get("kind") == "time_step":
                raise InvalidTimeStepError(message)
            if reply.get("kind") == "input":
                raise InvalidInputError(message)
            raise LinkError(message)
        return reply

    @Slot()
    def _drain(self) -> None:
        for line in _read_lines(self._socket):
            message, _ = _decode(line)
            if message is None:
                continue   # one bad line must not stop the rest
            op = message.get("op")
            request_id = _request_id(message)
            if request_id is not None:
                self._replies[request_id] = message
            elif op == "busy":
                self._refusal = str(message.get("message", BUSY_MESSAGE))
                self.connectedChanged.emit()
            elif op == "territories":
                self._take_territories(message)
            elif op == "outputs":
                try:
                    self._outputs = outputs_from_wire(message.get("outputs"))
                except WireFormatError:
                    continue
                self.outputsChanged.emit()

    def _take_territories(self, message: Mapping[str, Any]) -> None:
        raw = message.get("territories")
        if not isinstance(raw, list):
            return
        try:
            territories = tuple(territory_from_wire(item) for item in raw)
        except WireFormatError:
            return
        line = message.get("line")
        self._line = line if isinstance(line, str) else None
        self._territories = territories
        first_contact = not self._served
        self._served = True
        self._refusal = ""
        if first_contact:
            self.connectedChanged.emit()
        self.territoriesChanged.emit()
