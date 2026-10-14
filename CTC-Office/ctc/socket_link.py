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
import sys
import traceback
from typing import Any, Callable, Mapping, Sequence

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
from ctc.actions import Action, apply_action, apply_batch
from ctc.model import CtcError
from ctc.wire import (
    WireFormatError,
    inputs_from_wire,
    snapshot_from_wire,
    to_wire,
)

#: Local socket name. The environment variable lets tests use their own.
SERVER_NAME = os.environ.get("CTC_LINK", "trains-ctc-office")

_RECONNECT_MS = 1000
# How long to wait when checking for an already-running CTC Office.
_PROBE_TIMEOUT_MS = 300
# How long a request waits for a connection still being made.
_CONNECT_WAIT_MS = 1500
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

    def read(self, socket: QLocalSocket) -> list[Any]:
        """Every complete line, decoded; a line that is not JSON comes
        back as ``_BadLine`` instead of stopping the rest."""
        self._buffer += bytes(socket.readAll().data())
        messages: list[Any] = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            if line.strip():
                try:
                    messages.append(json.loads(line))
                # RecursionError: JSON nested too deep to read.
                except (ValueError, RecursionError) as error:
                    messages.append(_BadLine(str(error)))
        return messages


class _BadLine:
    """A received line that was not valid JSON."""

    def __init__(self, error: str) -> None:
        self.error = error


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

    @staticmethod
    def is_running(name: str = SERVER_NAME) -> bool:
        """True if a CTC Office is already serving under ``name``."""
        probe = QLocalSocket()
        probe.connectToServer(name)
        running = probe.waitForConnected(_PROBE_TIMEOUT_MS)
        probe.abort()
        return running

    def listen(self) -> bool:
        """Start serving. False if another CTC Office already serves
        under this name; a stale socket left by a crash is cleared."""
        if self.is_running(self._name):
            return False
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
            if isinstance(request, _BadLine):
                _write(client, {"op": "error", "id": None,
                                "message": f"not JSON: {request.error}"})
                continue
            if not isinstance(request, dict):
                _write(client, {"op": "error", "id": None,
                                "message": "a request must be an object"})
                continue
            reply = self._handle(request)
            changed |= (reply["op"] == "snapshot"
                        and request.get("op") != "snapshot")
            reply["id"] = request.get("id")
            _write(client, reply)
        if changed:
            self.changed.emit()

    def _take_inputs(self, module: CtcOffice, inputs: CtcInputs,
                     trial: bool) -> None:
        # The CTC window stages inputs for its clock; without a window,
        # inputs step the module one fixed tick.
        if self._set_inputs is None:
            module.step(_FIXED_DT_S, inputs)
        elif trial:
            module.stage_inputs(inputs)
        else:
            self._set_inputs(inputs)

    def _handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        op = request.get("op")
        args = request.get("args", {})
        try:
            if not isinstance(args, Mapping):
                raise WireFormatError("args must be an object")
            if op == "step":
                dt = args["dt"]
                if isinstance(dt, bool) or not isinstance(dt, (int, float)):
                    raise WireFormatError(f"dt must be a number, got {dt!r}")
                self._module.step(dt, inputs_from_wire(args["inputs"]))
            elif op == "set_inputs":
                self._take_inputs(self._module,
                                  inputs_from_wire(args["inputs"]), False)
            elif op == "batch":
                raw_inputs = args.get("inputs")
                actions = args.get("actions", [])
                if not isinstance(actions, list) or not all(
                        isinstance(a, list) and len(a) == 2
                        for a in actions):
                    raise WireFormatError(
                        "actions must be a list of [op, args] pairs")
                apply_batch(
                    self._module,
                    None if raw_inputs is None
                    else inputs_from_wire(raw_inputs),
                    [(str(a[0]), a[1]) for a in actions],
                    self._take_inputs)
            elif op != "snapshot":
                apply_action(self._module, str(op), args)
        except (CtcError, KeyError, TypeError, ValueError, OverflowError,
                RecursionError) as error:
            return {"op": "error", "message": str(error)}
        except Exception as error:  # pylint: disable=broad-except
            # A module bug. Still answer, so the client is not left
            # waiting and later requests on the connection keep their
            # replies; report it where the developer will see it.
            traceback.print_exc(file=sys.stderr)
            return {"op": "error",
                    "message": f"CTC Office internal error: {error!r}"}
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
    #: A connection attempt failed: no CTC Office is serving yet.
    connectionFailed = Signal()
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
        self._socket.errorOccurred.connect(
            lambda _error: self.connectionFailed.emit()
            if not self.connected else None)
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

    def apply_batch(self, inputs: CtcInputs | None,
                    actions: Sequence[Action]) -> None:
        self._call("batch",
                   inputs=None if inputs is None else to_wire(inputs),
                   actions=[[op, dict(args)] for op, args in actions])

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
        # Just started, or reconnecting: give the connection a moment
        # before calling the CTC Office absent.
        if not self.connected:
            self._connect()
            self._socket.waitForConnected(_CONNECT_WAIT_MS)
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
