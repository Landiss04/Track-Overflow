"""Link between the CTC Office and its test UI for the simulation clock.

The CTC Office process owns the one simulation clock. The test UI runs
in its own process and controls that clock over this link: pause,
resume, and set speed. Both windows show the same clock state.

The link is a Qt local socket: ``QLocalServer`` in the CTC process,
``QLocalSocket`` in the test UI. That is a named pipe on Windows and a
Unix socket elsewhere, never a network connection. Each message is one
JSON object on its own line:

- CTC to test UI: ``{"type": "clock", "time": "05:00:03",
  "paused": false, "speed": 1}``, sent on connect and whenever the shown
  time, pause state, or speed changes.
- Test UI to CTC: ``{"type": "pause"}``, ``{"type": "resume"}``, or
  ``{"type": "set_speed", "speed": 10}``.

Messages from the other process are untrusted: anything malformed or
unsupported is ignored.
"""

from __future__ import annotations

__all__ = ["ClockLinkClient", "ClockLinkServer", "SERVER_NAME"]

import json
import sys
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ctc_ui.sim_clock import SimulationClockBridge
from utils.system_clock import ALLOWED_SPEEDS

SERVER_NAME = "TrackOverflow.CTCOffice.clock"
NO_TIME_TEXT = "--:--:--"
RECONNECT_INTERVAL_MS = 1000


def _encode(message: dict[str, Any]) -> bytes:
    # One JSON object per line.
    return (json.dumps(message) + "\n").encode("utf-8")


def _decode(line: bytes) -> dict[str, Any] | None:
    # Parse one line; None if it is not a JSON object.
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return message if isinstance(message, dict) else None


def _read_messages(socket: QLocalSocket) -> list[dict[str, Any]]:
    # Every complete line waiting on the socket, decoded.
    messages = []
    while socket.canReadLine():
        message = _decode(bytes(socket.readLine().data()).strip())
        if message is not None:
            messages.append(message)
    return messages


class ClockLinkServer(QObject):
    """Serve the CTC Office's simulation clock to test UIs."""

    def __init__(
        self,
        clock: SimulationClockBridge,
        parent: QObject | None = None,
    ) -> None:
        """Serve ``clock`` once ``listen()`` is called.

        Args:
            clock: The CTC Office's simulation clock.
            parent: Optional Qt parent that owns this server.
        """
        super().__init__(parent)
        self._clock = clock
        self._clients: list[QLocalSocket] = []
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        clock.timeTextChanged.connect(self._broadcast)
        clock.pausedChanged.connect(self._broadcast)
        clock.speedChanged.connect(self._broadcast)

    @property
    def client_count(self) -> int:
        """Number of connected test UIs."""
        return len(self._clients)

    def listen(self, name: str = SERVER_NAME) -> bool:
        """Start accepting test UIs. Return False if that failed."""
        # A crashed CTC can leave a stale Unix socket file behind.
        QLocalServer.removeServer(name)
        if self._server.listen(name):
            return True
        print(
            f"Clock link unavailable: {self._server.errorString()}",
            file=sys.stderr,
        )
        return False

    def close(self) -> None:
        """Stop listening and drop every test UI."""
        self._server.close()
        clients, self._clients = self._clients, []
        for socket in clients:
            # Detach first so no handler runs on a socket being freed.
            socket.readyRead.disconnect(self._on_ready_read)
            socket.disconnected.disconnect(self._on_disconnected)
            socket.abort()
            socket.deleteLater()

    def _state(self) -> dict[str, Any]:
        # The clock's state as a message.
        return {
            "type": "clock",
            "time": self._clock.timeText,
            "paused": self._clock.paused,
            "speed": self._clock.speed,
        }

    def _broadcast(self) -> None:
        # Send the current state to every connected test UI.
        data = _encode(self._state())
        for socket in self._clients:
            socket.write(data)
            socket.flush()

    def _on_new_connection(self) -> None:
        # Accept each waiting test UI and send it the current state.
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._clients.append(socket)
            socket.readyRead.connect(self._on_ready_read)
            socket.disconnected.connect(self._on_disconnected)
            socket.write(_encode(self._state()))
            socket.flush()

    def _sending_client(self) -> QLocalSocket | None:
        # The connected socket whose signal is being handled, if any.
        # Looked up through sender() rather than captured, so a handler
        # never holds a socket Qt may already have freed.
        socket = self.sender()
        if isinstance(socket, QLocalSocket) and socket in self._clients:
            return socket
        return None

    def _on_ready_read(self) -> None:
        # Apply each command from a test UI.
        socket = self._sending_client()
        if socket is None:
            return
        for message in _read_messages(socket):
            kind = message.get("type")
            if kind == "pause":
                self._clock.pause()
            elif kind == "resume":
                self._clock.resume()
            elif kind == "set_speed":
                speed = message.get("speed")
                # bool is an int subclass; accept only a real 1 or 10.
                if type(speed) is int and speed in ALLOWED_SPEEDS:
                    self._clock.setSpeed(speed)

    def _on_disconnected(self) -> None:
        # Forget a test UI that went away.
        socket = self._sending_client()
        if socket is not None:
            self._clients.remove(socket)
            socket.deleteLater()


class ClockLinkClient(QObject):
    """The test UI's view of, and control over, the CTC Office clock.

    Connects to a running CTC Office and keeps retrying while none is
    running. QML reads ``connected``, ``timeText``, ``paused`` and
    ``speed`` and calls ``pause()``, ``resume()`` and ``setSpeed()``.
    """

    connectedChanged = Signal()
    stateChanged = Signal()

    def __init__(
        self,
        name: str = SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        """Start connecting to the CTC Office's clock.

        Args:
            name: Local server name the CTC Office listens on.
            parent: Optional Qt parent that owns this client.
        """
        super().__init__(parent)
        self._name = name
        self._connected = False
        self._time_text = NO_TIME_TEXT
        self._paused = True
        self._speed = 1
        self._socket = QLocalSocket(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.errorOccurred.connect(self._on_error)
        self._socket.readyRead.connect(self._on_ready_read)
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.setInterval(RECONNECT_INTERVAL_MS)
        self._retry.timeout.connect(self._connect)
        self._connect()

    def _get_connected(self) -> bool:
        # Whether a CTC Office is on the other end.
        return self._connected

    def _get_time_text(self) -> str:
        # CTC simulation time of day, or dashes when not connected.
        return self._time_text

    def _get_paused(self) -> bool:
        # Whether the CTC clock is held.
        return self._paused

    def _get_speed(self) -> int:
        # CTC clock speed multiplier.
        return self._speed

    connected = Property(bool, _get_connected, notify=connectedChanged)
    timeText = Property(str, _get_time_text, notify=stateChanged)
    paused = Property(bool, _get_paused, notify=stateChanged)
    speed = Property(int, _get_speed, notify=stateChanged)

    def close(self) -> None:
        """Disconnect and stop trying to reconnect."""
        self._retry.stop()
        self._socket.disconnected.disconnect(self._on_disconnected)
        self._socket.errorOccurred.disconnect(self._on_error)
        self._socket.abort()
        if self._connected:
            self._connected = False
            self._time_text = NO_TIME_TEXT
            self.connectedChanged.emit()
            self.stateChanged.emit()

    @Slot()
    def pause(self) -> None:
        """Ask the CTC Office to hold its clock."""
        self._send({"type": "pause"})

    @Slot()
    def resume(self) -> None:
        """Ask the CTC Office to run its clock."""
        self._send({"type": "resume"})

    @Slot(int)
    def setSpeed(self, speed: int) -> None:  # noqa: N802
        """Ask the CTC Office to run its clock at 1x or 10x."""
        self._send({"type": "set_speed", "speed": speed})

    def _send(self, message: dict[str, Any]) -> None:
        # Commands are dropped while no CTC Office is connected.
        if self._connected:
            self._socket.write(_encode(message))
            self._socket.flush()

    def _connect(self) -> None:
        # Try the CTC Office's server; on failure _on_error retries.
        unconnected = QLocalSocket.LocalSocketState.UnconnectedState
        if self._socket.state() == unconnected:
            self._socket.connectToServer(self._name)

    def _on_connected(self) -> None:
        # The CTC sends its clock state as soon as it accepts us.
        self._connected = True
        self.connectedChanged.emit()

    def _on_disconnected(self) -> None:
        # The CTC Office closed; show no time and keep trying.
        if self._connected:
            self._connected = False
            self._time_text = NO_TIME_TEXT
            self.connectedChanged.emit()
            self.stateChanged.emit()
        self._retry.start()

    def _on_error(self, error: QLocalSocket.LocalSocketError) -> None:
        # No CTC Office yet, or it went away: retry shortly.
        if not self._connected:
            self._retry.start()

    def _on_ready_read(self) -> None:
        # Take the newest well-formed clock state from the CTC.
        for message in _read_messages(self._socket):
            if message.get("type") != "clock":
                continue
            time_text = message.get("time")
            paused = message.get("paused")
            speed = message.get("speed")
            if (
                isinstance(time_text, str)
                and isinstance(paused, bool)
                and type(speed) is int
                and speed in ALLOWED_SPEEDS
            ):
                self._time_text = time_text
                self._paused = paused
                self._speed = speed
                self.stateChanged.emit()
