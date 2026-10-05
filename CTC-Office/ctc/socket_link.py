"""Socket link between the CTC test UI and a running CTC Office.

The CTC Office window hosts the module and a ``CtcLinkServer``. The test
UI, a separate process, connects with ``SocketLink``, which implements
the same ``CtcLink`` protocol as ``LocalLink``, so both windows act on
one live CTC module.

Wire format: newline-delimited JSON over a Qt local socket (a named pipe
on Windows, a socket file elsewhere; never a network connection). Each
request carries an ``id`` and gets one reply with that ``id``:
``{"op": "snapshot", "snapshot": {...}}`` or ``{"op": "error", ...}``.
The server also pushes ``{"op": "snapshot"}`` with no ``id`` on connect
and whenever the CTC UI changes the module between requests.

Like ``LocalLink``, this exists only for testing. At integration the
central harness calls the module directly.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping

import shiboken6
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ctc.interface import (
    CtcInputs,
    CtcOffice,
    CtcOutputs,
    CtcSnapshot,
    SwitchPosition,
)
from ctc.model import CtcError
from ctc.wire import inputs_from_wire, snapshot_from_wire, to_wire

#: Local socket name. The environment variable lets tests use their own.
SERVER_NAME = os.environ.get("CTC_LINK", "trains-ctc-office")

_RECONNECT_MS = 1000
# The fixed time step (decision D006), when no clock steps the module.
_FIXED_DT_S = 0.1
_REPLY_TIMEOUT_MS = 2000


class LinkError(CtcError):
    """The CTC Office could not be reached or did not answer."""


class RemoteCtcError(CtcError):
    """The CTC Office rejected a request; the message is its error."""


def _write(socket: QLocalSocket, message: Mapping[str, Any]) -> None:
    socket.write((json.dumps(message) + "\n").encode("utf-8"))
    socket.flush()


class _LineReader:
    """Splits a socket's byte stream into JSON messages."""

    def __init__(self) -> None:
        self._buffer = b""

    def read(self, socket: QLocalSocket) -> list[dict[str, Any]]:
        self._buffer += bytes(socket.readAll().data())
        messages = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            if line.strip():
                messages.append(json.loads(line))
        return messages


# -------------------------------------------------------------------- #
# Server, in the CTC Office process
# -------------------------------------------------------------------- #

class CtcLinkServer(QObject):
    """Serves one CTC module to test UI clients.

    ``set_inputs`` receives the inputs a test UI sends, for whatever
    steps the module (the CTC window's clock). Without it, new inputs
    step the module one fixed tick. ``changed`` fires after any request
    that changed the module or its inputs.
    """

    changed = Signal()

    def __init__(self, module: CtcOffice, name: str = SERVER_NAME,
                 parent: QObject | None = None,
                 set_inputs: Callable[[CtcInputs], None] | None = None,
                 ) -> None:
        super().__init__(parent)
        self._module = module
        self._name = name
        self._set_inputs = set_inputs
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)
        self._clients: dict[QLocalSocket, _LineReader] = {}

    def listen(self) -> bool:
        """Start serving; clears a stale socket left by a crash."""
        if self._server.listen(self._name):
            return True
        QLocalServer.removeServer(self._name)
        return self._server.listen(self._name)

    def close(self) -> None:
        """Stop serving and drop every client, before shutdown.

        Each client's signals are disconnected first: during teardown Qt
        deletes the sockets, and a "disconnected" handler must not run
        against an object that is already gone.
        """
        for client in list(self._clients):
            if shiboken6.isValid(client):
                client.readyRead.disconnect()
                client.disconnected.disconnect()
                client.abort()
        self._clients.clear()
        self._server.close()

    def push(self) -> None:
        """Send the current snapshot to every client."""
        message = self._snapshot_message()
        for client in list(self._clients):
            _write(client, message)

    def _snapshot_message(self) -> dict[str, Any]:
        return {"op": "snapshot", "snapshot": to_wire(self._module.snapshot())}

    def _accept(self) -> None:
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            self._clients[client] = _LineReader()
            client.readyRead.connect(lambda c=client: self._receive(c))
            client.disconnected.connect(lambda c=client: self._drop(c))
            _write(client, self._snapshot_message())

    def _drop(self, client: QLocalSocket) -> None:
        self._clients.pop(client, None)
        # Qt may already have deleted it (server shutdown).
        if shiboken6.isValid(client):
            client.deleteLater()

    def _receive(self, client: QLocalSocket) -> None:
        reader = self._clients.get(client)
        if reader is None:
            return
        changed = False
        for request in reader.read(client):
            reply = self._handle(request)
            changed |= (reply["op"] == "snapshot"
                        and request.get("op") != "snapshot")
            reply["id"] = request.get("id")
            _write(client, reply)
        if changed:
            self.changed.emit()

    def _handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        op = request.get("op")
        args = request.get("args", {})
        try:
            if op == "step":
                self._module.step(float(args["dt"]),
                                  inputs_from_wire(args["inputs"]))
            elif op == "set_inputs":
                inputs = inputs_from_wire(args["inputs"])
                self._module.validate_inputs(inputs)
                if self._set_inputs is None:
                    self._module.step(_FIXED_DT_S, inputs)
                else:
                    self._set_inputs(inputs)
            elif op == "dispatch":
                arrival = args.get("arrival_s")
                self._module.dispatch(
                    args["train_id"], args["line"],
                    args["destination_block_id"],
                    None if arrival is None else float(arrival))
            elif op == "cancel_dispatch":
                self._module.cancel_dispatch(args["train_id"])
            elif op == "set_block_closed":
                self._module.set_block_closed(args["line"],
                                              args["block_id"],
                                              bool(args["closed"]))
            elif op == "set_switch":
                self._module.set_switch(args["line"], args["switch_id"],
                                        args["position"])
            elif op == "release_switch":
                self._module.release_switch(args["line"],
                                            args["switch_id"])
            elif op == "set_maintenance_mode":
                self._module.set_maintenance_mode(bool(args["active"]))
            elif op == "set_clock_speedup":
                self._module.set_clock_speedup(bool(args["active"]))
            elif op != "snapshot":
                return {"op": "error", "message": f"unknown op {op!r}"}
        except (CtcError, KeyError, TypeError, ValueError) as error:
            return {"op": "error", "message": str(error)}
        return self._snapshot_message()


# -------------------------------------------------------------------- #
# Client, in the test UI process
# -------------------------------------------------------------------- #

class SocketLink(QObject):
    """A ``CtcLink`` to the CTC Office running in its own window.

    Calls block until the reply arrives (local pipe, milliseconds).
    Snapshots the server pushes between calls arrive through
    ``snapshotChanged``. The link reconnects by itself.
    """

    connectedChanged = Signal()
    snapshotChanged = Signal()

    #: The CTC UI is attached and owns its controls (maintenance).
    ctc_ui_attached = True

    def __init__(self, name: str = SERVER_NAME,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._socket = QLocalSocket(self)
        self._reader = _LineReader()
        self._next_id = 0
        self._in_call = False
        self._snapshot: CtcSnapshot | None = None
        self._socket.connected.connect(self.connectedChanged)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._drain)
        self._retry = QTimer(self)
        self._retry.setInterval(_RECONNECT_MS)
        self._retry.timeout.connect(self._connect)
        self._retry.start()
        self._connect()

    @property
    def connected(self) -> bool:
        return (self._socket.state()
                == QLocalSocket.LocalSocketState.ConnectedState)

    def step(self, dt: float, inputs: CtcInputs) -> CtcOutputs:
        return self._call("step", dt=dt, inputs=to_wire(inputs)).outputs

    def snapshot(self) -> CtcSnapshot:
        if self._snapshot is None:
            return self._call("snapshot")
        return self._snapshot

    def set_inputs(self, inputs: CtcInputs) -> None:
        self._call("set_inputs", inputs=to_wire(inputs))

    def dispatch(self, train_id: str, line: str,
                 destination_block_id: str,
                 arrival_s: float | None = None) -> None:
        self._call("dispatch", train_id=train_id, line=line,
                   destination_block_id=destination_block_id,
                   arrival_s=arrival_s)

    def cancel_dispatch(self, train_id: str) -> None:
        self._call("cancel_dispatch", train_id=train_id)

    def set_block_closed(self, line: str, block_id: str,
                         closed: bool) -> None:
        self._call("set_block_closed", line=line, block_id=block_id,
                   closed=closed)

    def set_switch(self, line: str, switch_id: str,
                   position: SwitchPosition) -> None:
        self._call("set_switch", line=line, switch_id=switch_id,
                   position=position)

    def release_switch(self, line: str, switch_id: str) -> None:
        self._call("release_switch", line=line, switch_id=switch_id)

    def set_maintenance_mode(self, active: bool) -> None:
        self._call("set_maintenance_mode", active=active)

    def set_clock_speedup(self, active: bool) -> None:
        self._call("set_clock_speedup", active=active)

    def reset(self) -> None:
        """Not available: the module belongs to the CTC Office."""

    def _connect(self) -> None:
        unconnected = QLocalSocket.LocalSocketState.UnconnectedState
        if self._socket.state() == unconnected:
            self._socket.connectToServer(self._name)

    def _on_disconnected(self) -> None:
        self._snapshot = None
        self.connectedChanged.emit()

    def _accept(self, messages: list[dict[str, Any]],
                want_id: int | None = None) -> dict[str, Any] | None:
        """Apply pushed snapshots; return the reply to ``want_id``."""
        reply = None
        for message in messages:
            if want_id is not None and message.get("id") == want_id:
                reply = message
            elif message.get("op") == "snapshot":
                self._snapshot = snapshot_from_wire(message["snapshot"])
                self.snapshotChanged.emit()
        return reply

    def _drain(self) -> None:
        if not self._in_call:
            self._accept(self._reader.read(self._socket))

    def _call(self, op: str, **args: Any) -> CtcSnapshot:
        if not self.connected:
            raise LinkError("The CTC Office is not running. Start it with "
                            "python -m ctc_ui from CTC-Office.")
        self._next_id += 1
        call_id = self._next_id
        self._in_call = True
        try:
            _write(self._socket, {"id": call_id, "op": op, "args": args})
            reply = self._accept(self._reader.read(self._socket), call_id)
            while reply is None:
                if not self._socket.waitForReadyRead(_REPLY_TIMEOUT_MS):
                    raise LinkError("The CTC Office did not answer.")
                reply = self._accept(self._reader.read(self._socket),
                                     call_id)
        finally:
            self._in_call = False
        if reply.get("op") == "error":
            raise RemoteCtcError(reply.get("message", "request rejected"))
        self._snapshot = snapshot_from_wire(reply["snapshot"])
        return self._snapshot
