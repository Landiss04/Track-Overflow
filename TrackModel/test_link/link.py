"""Local-socket link between the Track Model process and the test UI.

Newline-delimited JSON over a ``QLocalServer`` (a named pipe on Windows).

Requests, from the test UI::

    {"op": "step", "dt": 0.1, "inputs": {...}}
    {"op": "set_block_failure", "block_id": "...", "failure": "POWER"}
    {"op": "edit_block", "block_id": "...", "edit": {...}}
    {"op": "reset"}

Every reply is ``{"ok": true, "outputs": {...}}`` or
``{"ok": false, "error": "..."}``. The server also pushes
``{"event": "outputs", "outputs": {...}}`` when a client connects and
after every Track Model UI action, so the test UI sees a failure injected
between steps at once, even while its clock is held.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from test_link.codec import (
    Json,
    decode_block_edit,
    decode_inputs,
    decode_outputs,
    encode_block_edit,
    encode_inputs,
    encode_outputs,
)
from track_model.interface import (
    BlockEdit,
    TrackFailure,
    TrackModel,
    TrackModelError,
    TrackModelInputs,
)

SERVER_NAME = "track-overflow-track-model"
RECONNECT_MS = 1000


def _send(socket: QLocalSocket, message: Json) -> None:
    # One JSON object per line.
    socket.write((json.dumps(message) + "\n").encode("utf-8"))
    socket.flush()


class _LineReader:
    """Splits a socket's byte stream into JSON messages."""

    def __init__(self) -> None:
        self._buffer = b""

    def feed(self, data: bytes) -> list[Json]:
        """Add received bytes; return every complete message."""
        self._buffer += data
        *lines, self._buffer = self._buffer.split(b"\n")
        return [json.loads(line) for line in lines if line.strip()]


class LinkServer(QObject):
    """Serves one Track Model to test UI clients."""

    #: A step arrived. The Track Model UI uses it for Running/Paused.
    stepped = Signal()
    #: The model changed: a step, failure, edit or reset.
    changed = Signal()

    def __init__(self, model: TrackModel, parent: QObject | None = None):
        super().__init__(parent)
        self._model = model
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._readers: dict[QLocalSocket, _LineReader] = {}

    @property
    def model(self) -> TrackModel:
        """The Track Model this server drives."""
        return self._model

    def listen(self) -> bool:
        """Start listening, clearing a pipe a crashed run left behind."""
        QLocalServer.removeServer(SERVER_NAME)
        return self._server.listen(SERVER_NAME)

    def close(self) -> None:
        """Stop listening and drop every client.

        Signals are blocked first, so a socket torn down here never calls
        back into a Python object that is already gone.
        """
        self._server.close()
        for socket in list(self._readers):
            socket.blockSignals(True)
            socket.abort()
            socket.deleteLater()
        self._readers.clear()

    def notify_outputs(self) -> None:
        """Push the current outputs to every connected test UI."""
        message = {
            "event": "outputs",
            "outputs": encode_outputs(self._model.snapshot().outputs),
        }
        for socket in self._readers:
            _send(socket, message)

    def _on_new_connection(self) -> None:
        # Greet a new client with the current outputs.
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._readers[socket] = _LineReader()
            socket.readyRead.connect(lambda s=socket: self._on_ready(s))
            socket.disconnected.connect(lambda s=socket: self._drop(s))
            _send(socket, {
                "event": "outputs",
                "outputs": encode_outputs(self._model.snapshot().outputs),
            })

    def _drop(self, socket: QLocalSocket) -> None:
        # Forget a client that went away.
        self._readers.pop(socket, None)
        socket.deleteLater()

    def _on_ready(self, socket: QLocalSocket) -> None:
        # Answer every complete request.
        reader = self._readers.get(socket)
        if reader is None:
            return
        for request in reader.feed(bytes(socket.readAll().data())):
            _send(socket, self._handle(request))

    def _handle(self, request: Json) -> Json:
        # Run one request against the model; never raise to Qt.
        op = request.get("op")
        try:
            if op == "step":
                outputs = self._model.step(
                    float(request["dt"]), decode_inputs(request["inputs"])
                )
                self.stepped.emit()
            elif op == "set_block_failure":
                self._model.set_block_failure(
                    str(request["block_id"]), TrackFailure[request["failure"]]
                )
                outputs = self._model.snapshot().outputs
            elif op == "edit_block":
                self._model.edit_block(
                    str(request["block_id"]),
                    decode_block_edit(request["edit"]),
                )
                outputs = self._model.snapshot().outputs
            elif op == "reset":
                self._model.reset()
                outputs = self._model.snapshot().outputs
            else:
                return {"ok": False, "error": f"unknown op {op!r}"}
        except (TrackModelError, KeyError, ValueError, TypeError) as error:
            return {"ok": False, "error": f"{op}: {error}"}
        self.changed.emit()
        return {"ok": True, "outputs": encode_outputs(outputs)}


class LinkClient(QObject):
    """The test UI's end of the link. Reconnects until the server is up."""

    #: Decoded ``TrackModelOutputs``, from a reply or a pushed event.
    outputsReceived = Signal(object)
    errorReceived = Signal(str)
    connectionChanged = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket = QLocalSocket(self)
        self._reader = _LineReader()
        self._socket.readyRead.connect(self._on_ready)
        self._socket.connected.connect(lambda: self._set_connected(True))
        self._socket.disconnected.connect(lambda: self._set_connected(False))
        self._socket.errorOccurred.connect(lambda _e: self._retry())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RECONNECT_MS)
        self._timer.timeout.connect(self.connect_to_server)
        self._connected = False
        self._closed = False

    @property
    def connected(self) -> bool:
        """Whether the Track Model process is reachable."""
        return self._connected

    def close(self) -> None:
        """Disconnect and stop retrying, without emitting."""
        self._closed = True
        self._timer.stop()
        self._socket.blockSignals(True)
        self._socket.abort()
        self._connected = False

    def connect_to_server(self) -> None:
        """Try to reach the Track Model process."""
        unconnected = QLocalSocket.LocalSocketState.UnconnectedState
        if not self._closed and self._socket.state() == unconnected:
            self._reader = _LineReader()
            self._socket.connectToServer(SERVER_NAME)

    def step(self, dt: float, inputs: TrackModelInputs) -> bool:
        """Send one tick. Returns False if not connected."""
        return self._request(
            {"op": "step", "dt": dt, "inputs": encode_inputs(inputs)}
        )

    def set_block_failure(self, block_id: str, failure: TrackFailure) -> bool:
        """Test-only: inject or clear a failure."""
        return self._request({
            "op": "set_block_failure",
            "block_id": block_id,
            "failure": failure.name,
        })

    def edit_block(self, block_id: str, edit: BlockEdit) -> bool:
        """Test-only: override a block's stats."""
        return self._request({
            "op": "edit_block",
            "block_id": block_id,
            "edit": encode_block_edit(edit),
        })

    def reset(self) -> bool:
        """Test-only: reset the module."""
        return self._request({"op": "reset"})

    def _request(self, message: Json) -> bool:
        # Send if connected; the reply arrives through _on_ready.
        if not self._connected:
            return False
        _send(self._socket, message)
        return True

    def _on_ready(self, *_args: Any) -> None:
        # Decode replies and pushed events.
        for message in self._reader.feed(bytes(self._socket.readAll().data())):
            if message.get("ok") is False:
                self.errorReceived.emit(str(message.get("error")))
            elif "outputs" in message:
                self.outputsReceived.emit(decode_outputs(message["outputs"]))

    def _set_connected(self, connected: bool) -> None:
        # Track the connection and retry after a drop.
        if connected != self._connected:
            self._connected = connected
            self.connectionChanged.emit(connected)
        if not connected:
            self._retry()

    def _retry(self) -> None:
        # Try again shortly; the Track Model process may start later.
        if not self._closed and not self._timer.isActive():
            self._timer.start()
