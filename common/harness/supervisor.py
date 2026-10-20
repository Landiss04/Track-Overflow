"""Start the module processes and hold their links.

The supervisor listens on a local server whose name is unique to this
harness, starts every module process with ``--harness <name>``, and
learns which connection is which module from the ``READY`` it sends
first. A connection that names no expected module, names one already
connected, or speaks another protocol version is refused.

It reports each module's start, readiness, messages and end. ``stop``
asks every module to quit, waits, and ends any that do not (R64).
"""

from __future__ import annotations

__all__ = [
    "KILL_WAIT_S",
    "QUIT_TIMEOUT_S",
    "STARTUP_TIMEOUT_S",
    "HarnessStartError",
    "ModuleSupervisor",
]

import os
import time
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from common.harness.modules import (
    ModuleSpec,
    module_command,
    working_directory,
)
from utils.harness_protocol import (
    MODULE_TO_HARNESS,
    PROTOCOL_VERSION,
    READY,
    LineBuffer,
    ProtocolError,
    decode,
    encode,
    quit_message,
)

#: Real seconds every module has to say READY before it is reported.
STARTUP_TIMEOUT_S = 20.0
#: Real seconds modules have to end after ``QUIT``.
QUIT_TIMEOUT_S = 5.0
#: Real seconds to wait for a killed module to end.
KILL_WAIT_S = 2.0

MILLISECONDS_PER_SECOND = 1000


class HarnessStartError(RuntimeError):
    """The harness could not open its local server."""


class _Connection(QObject):
    """The harness's end of one module's socket.

    Lines are decoded as they arrive. A line that does not decode, or
    runs past the length limit, is reported and skipped; the lines
    after it are still read.
    """

    messageReceived = Signal(object, object)
    protocolError = Signal(object, str)
    disconnected = Signal(object)

    def __init__(self, socket: QLocalSocket, parent: QObject) -> None:
        """Wrap ``socket``; the connection owns it from now on."""
        super().__init__(parent)
        self.module: str | None = None
        self._closed = False
        self._socket = socket
        socket.setParent(self)
        self._buffer = LineBuffer()
        socket.readyRead.connect(self._on_ready_read)
        socket.disconnected.connect(lambda: self.disconnected.emit(self))

    def send(self, message: Mapping[str, Any]) -> bool:
        """Send one message; return False if the socket is closed."""
        if (
            self._socket.state()
            != QLocalSocket.LocalSocketState.ConnectedState
        ):
            return False
        self._socket.write(encode(message))
        self._socket.flush()
        return True

    def wait_until_written(self, timeout_s: float) -> None:
        """Block until everything sent has left, or ``timeout_s``."""
        if self._socket.bytesToWrite() > 0:
            self._socket.waitForBytesWritten(
                round(timeout_s * MILLISECONDS_PER_SECOND)
            )

    def close(self) -> None:
        """Close the socket without signalling anything more."""
        self._closed = True
        self._socket.blockSignals(True)
        self._socket.abort()

    def _on_ready_read(self) -> None:
        # Report every complete line; a partial one waits for the rest.
        data = bytes(self._socket.readAll().data())
        for line in self._buffer.feed(data):
            if self._closed:
                # Refused part-way through; the rest is not read.
                return
            try:
                if isinstance(line, ProtocolError):
                    raise line
                message = decode(line)
            except ProtocolError as error:
                self.protocolError.emit(self, f"line ignored: {error}")
                continue
            self.messageReceived.emit(self, message)


class ModuleSupervisor(QObject):
    """Run one process per module and route their messages."""

    #: A module process started: its name and process ID.
    moduleStarted = Signal(str, int)
    #: A module said ``READY``.
    moduleReady = Signal(str)
    #: Every module has said ``READY``.
    allReady = Signal()
    #: A ready module sent a message: its name and the message.
    messageReceived = Signal(str, object)
    #: Something broke the protocol: who, and what.
    protocolError = Signal(str, str)
    #: A ready module's connection closed.
    moduleDisconnected = Signal(str)
    #: A module process ended, or never started: its name, and how.
    moduleExited = Signal(str, str)
    #: A module did not quit in time and was killed.
    moduleKilled = Signal(str)
    #: Modules still not ready when the startup timeout ran out.
    startupTimedOut = Signal(object)

    def __init__(
        self,
        specs: Sequence[ModuleSpec],
        *,
        startup_timeout_s: float = STARTUP_TIMEOUT_S,
        parent: QObject | None = None,
    ) -> None:
        """Prepare to run ``specs``; ``start`` launches them.

        Args:
            specs: One per module, names unique.
            startup_timeout_s: Real seconds before modules that are
                still not ready are reported.
            parent: Optional Qt parent.

        Raises:
            ValueError: If two specs share a name.
        """
        super().__init__(parent)
        names = [spec.name for spec in specs]
        if len(set(names)) != len(names):
            raise ValueError(f"module names must be unique: {names}")
        self._specs = tuple(specs)
        self._server_name = (
            f"track-overflow-{os.getpid()}-{uuid.uuid4().hex[:12]}"
        )
        self._server = QLocalServer(self)
        # Only this user's processes may connect.
        self._server.setSocketOptions(
            QLocalServer.SocketOption.UserAccessOption
        )
        self._server.newConnection.connect(self._on_new_connection)
        self._processes: dict[str, QProcess] = {}
        # Exit code of each ended module; None if it crashed, was
        # killed or never started.
        self._exit_codes: dict[str, int | None] = {}
        self._ready: dict[str, _Connection] = {}
        self._unidentified: list[_Connection] = []
        self._stopping = False
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.setInterval(
            round(startup_timeout_s * MILLISECONDS_PER_SECOND)
        )
        self._startup_timer.timeout.connect(self._on_startup_timeout)

    @property
    def server_name(self) -> str:
        """The local server modules connect to."""
        return self._server_name

    @property
    def module_names(self) -> tuple[str, ...]:
        """Every module, in start order."""
        return tuple(spec.name for spec in self._specs)

    @property
    def ready_modules(self) -> tuple[str, ...]:
        """Modules that said ``READY`` and are still connected."""
        return tuple(name for name in self.module_names if name in self._ready)

    @property
    def all_ready(self) -> bool:
        """Whether every module is ready and connected."""
        return len(self._ready) == len(self._specs)

    def start(self) -> None:
        """Open the server and start every module process at once.

        Raises:
            HarnessStartError: If the server cannot listen.
        """
        if not self._server.listen(self._server_name):
            raise HarnessStartError(
                f"cannot listen on {self._server_name}: "
                f"{self._server.errorString()}"
            )
        for spec in self._specs:
            self._launch(spec)
        self._startup_timer.start()

    def send(self, module: str, message: Mapping[str, Any]) -> bool:
        """Send ``message`` to a ready module.

        Returns:
            False if the module is not connected.
        """
        connection = self._ready.get(module)
        return connection is not None and connection.send(message)

    def stop(
        self, tick: int, timeout_s: float = QUIT_TIMEOUT_S
    ) -> dict[str, int | None]:
        """Send ``QUIT`` to every module, then end any still running.

        Blocks for up to ``timeout_s`` while modules quit, plus
        ``KILL_WAIT_S`` for each one killed.

        Args:
            tick: The tick the ``QUIT`` belongs to.
            timeout_s: Real seconds modules have to end on their own.

        Returns:
            Each module's exit code; None for one that crashed, was
            killed or never started.
        """
        self._stopping = True
        self._startup_timer.stop()
        # A module still starting finds no server, and ends itself.
        self._server.close()
        deadline_s = time.monotonic() + timeout_s
        # A module that has not said READY yet is told to quit too.
        # Copies throughout: waiting can deliver a disconnect, which
        # changes the collections.
        connections = [*self._ready.values(), *self._unidentified]
        for connection in connections:
            connection.send(quit_message(tick))
        for connection in connections:
            connection.wait_until_written(
                max(0.0, deadline_s - time.monotonic())
            )
        for name, process in list(self._processes.items()):
            if process.state() == QProcess.ProcessState.NotRunning:
                continue
            remaining_s = max(0.0, deadline_s - time.monotonic())
            if not process.waitForFinished(
                round(remaining_s * MILLISECONDS_PER_SECOND)
            ):
                self.moduleKilled.emit(name)
                process.kill()
                process.waitForFinished(
                    round(KILL_WAIT_S * MILLISECONDS_PER_SECOND)
                )
                self._exit_codes[name] = None
        for connection in [*self._ready.values(), *self._unidentified]:
            connection.close()
            connection.deleteLater()
        self._ready.clear()
        self._unidentified.clear()
        return {name: self._exit_codes.get(name) for name in self.module_names}

    def _launch(self, spec: ModuleSpec) -> None:
        # Start one module process. Its console output goes to the
        # harness's console.
        name = spec.name
        program, args = module_command(
            [*spec.args, "--harness", self._server_name]
        )
        process = QProcess(self)
        process.setProgram(program)
        process.setArguments(args)
        process.setWorkingDirectory(str(working_directory()))
        process.setProcessChannelMode(
            QProcess.ProcessChannelMode.ForwardedChannels
        )
        process.started.connect(
            lambda: self.moduleStarted.emit(name, process.processId())
        )
        process.finished.connect(
            lambda code, status: self._on_finished(name, code, status)
        )
        process.errorOccurred.connect(
            lambda error: self._on_process_error(name, process, error)
        )
        self._processes[name] = process
        process.start()

    def _on_finished(
        self, name: str, code: int, status: QProcess.ExitStatus
    ) -> None:
        # A module process ended, by itself or by a crash.
        if status == QProcess.ExitStatus.NormalExit:
            self._exit_codes[name] = code
            how = f"exit code {code}"
        else:
            self._exit_codes[name] = None
            how = "crashed"
        self.moduleExited.emit(name, how)

    def _on_process_error(
        self, name: str, process: QProcess, error: QProcess.ProcessError
    ) -> None:
        # Only a failure to start goes unreported by ``finished``.
        if error == QProcess.ProcessError.FailedToStart:
            self._exit_codes[name] = None
            self.moduleExited.emit(
                name, f"failed to start: {process.errorString()}"
            )

    def _on_new_connection(self) -> None:
        # A connection is anonymous until its READY names it.
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            connection = _Connection(socket, self)
            if self._stopping:
                connection.close()
                connection.deleteLater()
                continue
            connection.messageReceived.connect(self._on_message)
            connection.protocolError.connect(self._on_connection_error)
            connection.disconnected.connect(self._on_disconnected)
            self._unidentified.append(connection)

    def _on_message(
        self, connection: _Connection, message: Mapping[str, Any]
    ) -> None:
        # A connection's first message must be READY; after that,
        # anything a module may send goes up.
        op = message["op"]
        if connection.module is None:
            if op == READY:
                self._identify(connection, message)
            else:
                self._refuse(connection, f"{op} came before READY")
            return
        if op == READY or op not in MODULE_TO_HARNESS:
            self.protocolError.emit(
                connection.module, f"unexpected {op} ignored"
            )
            return
        self.messageReceived.emit(connection.module, message)

    def _identify(
        self, connection: _Connection, message: Mapping[str, Any]
    ) -> None:
        # Accept a READY from an expected module not yet connected.
        name = message["module"]
        if message["protocol"] != PROTOCOL_VERSION:
            self._refuse(
                connection,
                f"{name} speaks protocol {message['protocol']}, "
                f"the harness {PROTOCOL_VERSION}",
            )
        elif name not in self.module_names:
            self._refuse(connection, f"no module {name!r} is expected")
        elif name in self._ready:
            self._refuse(connection, f"{name} is already connected")
        else:
            connection.module = name
            self._unidentified.remove(connection)
            self._ready[name] = connection
            self.moduleReady.emit(name)
            if self.all_ready:
                self._startup_timer.stop()
                self.allReady.emit()

    def _refuse(self, connection: _Connection, reason: str) -> None:
        # Report and drop a connection that cannot be a module of ours.
        self.protocolError.emit(
            "harness", f"refused a connection: {reason}"
        )
        if connection in self._unidentified:
            self._unidentified.remove(connection)
        connection.close()
        connection.deleteLater()

    def _on_connection_error(
        self, connection: _Connection, text: str
    ) -> None:
        # Name the module if the connection said who it is.
        self.protocolError.emit(connection.module or "harness", text)

    def _on_disconnected(self, connection: _Connection) -> None:
        # A ready module's link closed: it is no longer ready.
        name = connection.module
        if name is not None and self._ready.get(name) is connection:
            del self._ready[name]
            self.moduleDisconnected.emit(name)
        elif connection in self._unidentified:
            self._unidentified.remove(connection)
        connection.deleteLater()

    def _on_startup_timeout(self) -> None:
        # Name the modules still not ready; the harness keeps waiting.
        missing = [
            name for name in self.module_names if name not in self._ready
        ]
        if missing:
            self.startupTimedOut.emit(missing)
