"""Local server that lets a separate test UI stimulate this controller.

The Track Controller UI listens on a named pipe; the test UI connects to
it as its own process. Nothing here is a network socket: a named pipe is
reachable only from the same machine and the same user, which keeps the
module inside REQ-DSN-003 (no network connections required).

Framing is one JSON object per line. Every request is answered with an
``ack`` or an ``error``, and a full ``snapshot`` is pushed to every
client whenever anything the test UI displays has changed.

The vocabulary itself lives in :mod:`track_ctrl.stimulus`; this module
only moves bytes and keeps the "who owns the inputs" flag honest.
"""

from __future__ import annotations

import json
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from track_ctrl.state import TrackControllerState
from track_ctrl.stimulus import (
    SERVER_NAME,
    StimulusError,
    apply_physical,
    apply_user,
    build_snapshot,
)

#: A client that sends more than this without a newline is dropped.
MAX_LINE_BYTES = 1_000_000

#: Pushes are coalesced over this window, in milliseconds, so a burst of
#: state changes becomes one snapshot rather than a flood.
PUSH_INTERVAL_MS = 40


class _PipeServer(QLocalServer):
    """A ``QLocalServer`` whose client sockets are created from Python.

    The stock server builds each client's ``QLocalSocket`` in C++ and
    PySide wraps it on the fly. Those wrappers can outlive the object
    they wrap, and when a later socket reuses the same address PySide
    hands back the dead wrapper ("Internal C++ object already
    deleted"), so a client occasionally connects and is never served.
    Creating the socket here gives PySide a wrapper whose lifetime it
    tracks from the start.
    """

    clientConnected = Signal(QLocalSocket)

    def incomingConnection(self, socketDescriptor: int) -> None:
        socket = QLocalSocket(self)
        if socket.setSocketDescriptor(socketDescriptor):
            self.clientConnected.emit(socket)
        else:
            socket.deleteLater()


class StimulusServer(QObject):
    """Accepts test-UI connections and applies their stimuli."""

    def __init__(
        self,
        state: TrackControllerState,
        name: str = SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._name = name
        self._server = _PipeServer(self)
        self._server.clientConnected.connect(self._accept)
        self._buffers: dict[QLocalSocket, bytearray] = {}

        self._push_timer = QTimer(self)
        self._push_timer.setSingleShot(True)
        self._push_timer.setInterval(PUSH_INTERVAL_MS)
        self._push_timer.timeout.connect(self._push_all)

        for signal in (
            state.controllerChanged,
            state.selectionChanged,
            state.bufferChanged,
            state.tabChanged,
            state.maintenanceChanged,
            state.externalChanged,
        ):
            signal.connect(self._schedule_push)

    @property
    def name(self) -> str:
        """The pipe name clients connect to."""
        return self._name

    @property
    def client_count(self) -> int:
        """How many test UIs are connected."""
        return len(self._buffers)

    def start(self) -> bool:
        """Begin listening. Returns ``False`` if the pipe cannot be opened."""
        # A crashed run can leave the name registered; remove it so a
        # restart does not fail with "address in use".
        QLocalServer.removeServer(self._name)
        return self._server.listen(self._name)

    def error_text(self) -> str:
        """Why :meth:`start` failed."""
        return self._server.errorString()

    def stop(self) -> None:
        """Drop every client and stop listening."""
        for socket in list(self._buffers):
            if not shiboken6.isValid(socket):
                continue
            # Detach first: a handler firing after shutdown would run
            # against objects that are already being torn down.
            for signal in (socket.readyRead, socket.disconnected):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass
            socket.disconnectFromServer()
            socket.deleteLater()
        self._buffers.clear()
        self._push_timer.stop()
        self._server.close()
        self._state.set_external_control(False)

    # --- connections --------------------------------------------------

    def _accept(self, socket: QLocalSocket) -> None:
        self._buffers[socket] = bytearray()
        socket.readyRead.connect(lambda s=socket: self._on_ready(s))
        socket.disconnected.connect(lambda s=socket: self._on_gone(s))
        self._state.set_external_control(True)
        self._send(socket, build_snapshot(self._state))
        # readyRead only fires when new bytes arrive. A client that
        # wrote before this handler was attached would otherwise sit
        # unread forever, so drain whatever is already waiting.
        self._on_ready(socket)

    def _on_gone(self, socket: QLocalSocket) -> None:
        self._buffers.pop(socket, None)
        if shiboken6.isValid(socket):
            socket.deleteLater()
        # The last test UI leaving hands the inputs back to the stand-in.
        self._state.set_external_control(bool(self._buffers))

    def _on_ready(self, socket: QLocalSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        if not shiboken6.isValid(socket):
            # Qt deleted it under us (server teardown); forget it.
            self._buffers.pop(socket, None)
            return
        buffer.extend(socket.readAll().data())
        if len(buffer) > MAX_LINE_BYTES and b"\n" not in buffer:
            socket.disconnectFromServer()
            return
        while True:
            end = buffer.find(b"\n")
            if end < 0:
                break
            raw = bytes(buffer[:end])
            del buffer[: end + 1]
            if raw.strip():
                self._handle(socket, raw)

    # --- requests -----------------------------------------------------

    def _handle(self, socket: QLocalSocket, raw: bytes) -> None:
        request_id: Any = None
        try:
            message = json.loads(raw.decode("utf-8"))
            if not isinstance(message, dict):
                raise StimulusError("a message must be a JSON object")
            request_id = message.get("id")
            kind = message.get("type")

            if kind == "physical":
                note = apply_physical(self._state.system, message)
                self._state.notify_external_change(note)
            elif kind == "user":
                note = apply_user(self._state, message)
            elif kind == "hello":
                note = "hello"
            else:
                raise StimulusError(f"unknown message type: {kind!r}")
        except (StimulusError, ValueError) as error:
            self._send(
                socket,
                {"type": "error", "id": request_id, "message": str(error)},
            )
            return

        self._send(socket, {"type": "ack", "id": request_id, "note": note})
        self._schedule_push()

    # --- output -------------------------------------------------------

    def _send(self, socket: QLocalSocket, payload: dict[str, Any]) -> None:
        if not shiboken6.isValid(socket):
            return
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        socket.write(line.encode("utf-8"))
        socket.flush()

    def _schedule_push(self) -> None:
        if self._buffers and not self._push_timer.isActive():
            self._push_timer.start()

    def _push_all(self) -> None:
        if not self._buffers:
            return
        snapshot = build_snapshot(self._state)
        for socket in list(self._buffers):
            self._send(socket, snapshot)
