"""A module process's link to the central harness.

The harness starts every module as a process of its own and passes it
the name of the harness's local server, ``--harness <name>``. The
module connects to that server, says ``READY`` once it can step, and
from then on answers each ``STEP`` with its outputs, or with a
rejection that leaves its state unchanged. Only the harness drives a
module (D005), so the module ends when the harness sends ``QUIT`` or
goes away.

Changes a person makes in the module's window between ticks reach the
other modules through the module's next outputs. ``push_state`` is for
the one exception: the CTC Office's ``clock_paused`` and
``clock_speedup``, which the harness must read while the clock is
paused and no step runs.

Messages sent before the link opens wait for it and go in order; once
the link is lost, nothing more is sent.

Messages are defined in ``utils.harness_protocol``.
"""

from __future__ import annotations

__all__ = ["ModuleLink", "StepHandler", "TickRejectedError"]

import sys
from collections.abc import Callable, Mapping
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalSocket

from utils.harness_protocol import (
    QUIT,
    STEP,
    LineBuffer,
    ProtocolError,
    decode,
    encode,
    outputs_message,
    ready_message,
    rejected_message,
    state_message,
)

#: Called for every ``STEP`` with ``(tick, dt, sim_time_s, inputs)``;
#: returns the module's outputs for that tick.
StepHandler = Callable[
    [int, float, float, Mapping[str, Any]], Mapping[str, Any]
]


class TickRejectedError(Exception):
    """Raised by a step handler to refuse a tick.

    The module's state must be unchanged. The message is the reason
    the harness logs.
    """


class ModuleLink(QObject):
    """Connect one module process to the central harness."""

    #: The harness sent ``QUIT``.
    quitRequested = Signal()
    #: The harness could not be reached, or the connection closed.
    harnessLost = Signal()

    def __init__(
        self,
        module: str,
        server_name: str,
        step: StepHandler,
        parent: QObject | None = None,
    ) -> None:
        """Prepare a link; ``connect_to_harness`` opens it.

        Args:
            module: This module's name, as the harness knows it.
            server_name: The harness's local server, from
                ``--harness``.
            step: Steps the module once per ``STEP``.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._module = module
        self._server_name = server_name
        self._step = step
        self._buffer = LineBuffer()
        self._tick = 0
        self._ready_sent = False
        self._lost = False
        self._last_reply: dict[str, Any] | None = None
        # Lines sent before the link opened, in order.
        self._queued: list[bytes] = []
        self._socket = QLocalSocket(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.disconnected.connect(self._on_lost)
        self._socket.errorOccurred.connect(self._on_error)

    @property
    def module(self) -> str:
        """This module's name."""
        return self._module

    @property
    def tick(self) -> int:
        """The last tick the harness sent, 0 before the first."""
        return self._tick

    @property
    def is_connected(self) -> bool:
        """Whether the link to the harness is open."""
        return (
            self._socket.state()
            == QLocalSocket.LocalSocketState.ConnectedState
        )

    @property
    def last_reply(self) -> dict[str, Any] | None:
        """The last ``OUTPUTS`` or ``REJECTED`` sent, if any."""
        return self._last_reply

    def connect_to_harness(self) -> None:
        """Open the link. ``harnessLost`` fires if it cannot."""
        self._socket.connectToServer(self._server_name)

    def announce_ready(self) -> None:
        """Tell the harness the module can step.

        Only the first call sends anything.
        """
        if not self._ready_sent:
            self._ready_sent = True
            self.send(ready_message(self._module))

    def push_state(self, state: Mapping[str, Any]) -> None:
        """Send a change made between ticks.

        Args:
            state: The changed values, such as
                ``{"clock_paused": False}``.
        """
        self.send(state_message(self._tick, state))

    def send(self, message: Mapping[str, Any]) -> None:
        """Send one protocol message.

        It waits if the link has not opened yet, and is dropped if the
        link was lost.

        Raises:
            ProtocolError: If the message is not valid.
        """
        line = encode(message)
        if self._lost:
            return
        if self.is_connected:
            self._write(line)
        else:
            self._queued.append(line)

    def close(self) -> None:
        """Close the link without signalling ``harnessLost``."""
        self._lost = True
        self._queued.clear()
        self._socket.abort()

    def _on_connected(self) -> None:
        # Messages sent before the link opened go now, in order.
        queued, self._queued = self._queued, []
        for line in queued:
            self._write(line)

    def _write(self, line: bytes) -> None:
        # Hand the line to the socket at once; Qt sends the rest of a
        # long line from the event loop.
        if self.is_connected:
            self._socket.write(line)
            self._socket.flush()

    def _on_ready_read(self) -> None:
        # Handle every complete line; a partial one waits for the rest.
        data = bytes(self._socket.readAll().data())
        try:
            lines = self._buffer.feed(data)
        except ProtocolError as error:
            self._complain(f"harness stream broken: {error}")
            self._on_lost()
            return
        for line in lines:
            try:
                message = decode(line)
            except ProtocolError as error:
                self._complain(f"ignored a line from the harness: {error}")
                continue
            self._handle(message)

    def _handle(self, message: Mapping[str, Any]) -> None:
        # STEP and QUIT are the only messages a module receives.
        op = message["op"]
        if op == STEP:
            self._answer_step(message)
        elif op == QUIT:
            self.quitRequested.emit()
        else:
            self._complain(f"ignored an unexpected {op} from the harness")

    def _answer_step(self, message: Mapping[str, Any]) -> None:
        # Step once and reply. A handler that raises refuses the tick,
        # whatever the error, so one bad tick never kills the module.
        request_id = message["id"]
        tick = message["tick"]
        self._tick = tick
        try:
            outputs = self._step(
                tick, message["dt"], message["sim_time_s"], message["inputs"]
            )
            reply = outputs_message(request_id, tick, outputs)
            line = encode(reply)
        except TickRejectedError as error:
            reply = rejected_message(request_id, tick, str(error) or "refused")
            line = encode(reply)
        except Exception as error:  # noqa: BLE001 - reported, not hidden
            reason = f"{type(error).__name__}: {error}"
            reply = rejected_message(request_id, tick, reason)
            line = encode(reply)
        self._last_reply = reply
        self._write(line)

    def _on_error(self, _error: QLocalSocket.LocalSocketError) -> None:
        # Unreachable or broken: either way the harness is gone.
        if not self.is_connected:
            self._on_lost()

    def _on_lost(self) -> None:
        # Signal once, however the link was lost.
        if not self._lost:
            self._lost = True
            self._queued.clear()
            self.harnessLost.emit()

    def _complain(self, text: str) -> None:
        # Module processes have no log of their own; the console keeps
        # the trail. The harness logs what reaches it.
        print(f"[{self._module}] {text}", file=sys.stderr, flush=True)
