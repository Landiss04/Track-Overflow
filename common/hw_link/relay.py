"""Host-side ordered Pi relay and reconnect state machine."""

from __future__ import annotations

import uuid
from collections import deque
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from utils.harness_protocol import LineBuffer, ProtocolError
from . import protocol as p
from .transport import ByteTransport


class RemoteActionError(ValueError):
    """A refused Pi action, including the original module diagnostic."""

    kind: str = ""
    diagnostics: tuple[str, ...] = ()


class HardwareRelay(QObject):
    """Hold harness replies during USB loss; never substitute a local core."""

    ready = Signal()
    reply = Signal(dict)
    viewChanged = Signal(dict)
    event = Signal(str)
    completed = Signal(int, dict)
    closing = Signal()

    def __init__(
        self,
        module: str,
        transport: ByteTransport,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.module, self.transport = module, transport
        self.session = uuid.uuid4().hex
        self.buffer = LineBuffer()
        self._id = 1_000_000_000
        self._action_depth = 0
        self._ready = False
        self._ever_ready = False
        self._online = False
        self._closed = False
        self._boot: str | None = None
        self._clock_running = False
        self._lost_running = False
        self._history: list[dict[str, Any]] = []
        self._recovery: deque[dict[str, Any]] = deque()
        self._recovering = False
        self._inflight: dict[str, Any] | None = None
        self._saved_inflight: dict[str, Any] | None = None
        self._queue: deque[dict[str, Any]] = deque()
        self._last_view: dict[str, Any] = {}
        self._gains: dict[str, list[float]] = {}
        self.metrics: list[dict[str, Any]] = []
        self.transport.connected.connect(self._connected)
        self.transport.disconnected.connect(self._disconnected)
        self.transport.received.connect(self._received)
        self.transport.diagnostic.connect(
            lambda value: self.event.emit("TRANSPORT " + value)
        )

    def start(self) -> None:
        self.transport.start()

    def set_clock_state(self, state: dict[str, Any]) -> None:
        """Record clock state; disconnect latches its prior value."""
        self._clock_running = not bool(state.get("clock_paused", True))

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _connected(self) -> None:
        if self._closed:
            return
        self._online = True
        self.buffer = LineBuffer()
        self.event.emit("PI_CONNECTED " + self.module)
        self.transport.write(
            p.encode(
                p.message(
                    p.HELLO,
                    self._next_id(),
                    protocol=p.VERSION,
                    module=self.module,
                    session=self.session,
                    agent_version="host-1",
                    agent_hash="host",
                )
            )
        )

    def _disconnected(self) -> None:
        if self._closed:
            return
        self._online = self._ready = False
        if not self._recovering:
            self._lost_running = self._clock_running
        self.event.emit(f"PI_LOST {self.module} running={self._lost_running}")
        # The process transport needs an explicit restart. SerialTransport also
        # keeps scanning, and start() is idempotent for both.
        QTimer.singleShot(1100, self.transport.start)

    def _received(self, data: bytes) -> None:
        for line in self.buffer.feed(data):
            try:
                if isinstance(line, ProtocolError):
                    raise line
                incoming = p.decode(line)
            except ProtocolError as error:
                self.event.emit(f"PI_SKIPPED_LINE {error}")
                continue
            self._handle(incoming)

    def _handle(self, incoming: dict[str, Any]) -> None:
        if self._closed:
            return
        op = incoming["op"]
        if op == p.HELLO:
            if (
                incoming["module"] != self.module
                or incoming["protocol"] != p.VERSION
                or incoming["session"] != self.session
                or not incoming.get("agent_version")
                or not incoming.get("agent_hash")
                or not incoming.get("boot")
            ):
                self.event.emit(
                    "PI_HELLO_REJECTED identity or version mismatch"
                )
                return
            rebooted = self._boot is not None and self._boot != incoming.get(
                "boot"
            )
            self._boot = incoming.get("boot")
            self.event.emit(
                f"PI_HELLO {self.module} "
                f"version={incoming['agent_version']} "
                f"hash={incoming['agent_hash']}"
            )
            if self._ever_ready:
                if not self._recovering:
                    self._saved_inflight = self._inflight
                self._inflight = None
                # If the durable agent resumed, load requests are cache hits.
                # A replaced journal/device needs every accepted transaction.
                history = (
                    self._history
                    if not incoming.get("resumed")
                    else [
                        r
                        for r in self._history
                        if r.get("action")
                        in ("load_territory", "load_program")
                    ]
                )
                self._recovery = deque(history)
                if self.module == "train-controller-hw" and (
                    rebooted or self._lost_running
                ):
                    gains = self._gains if self._lost_running else {}
                    self._recovery.append(
                        p.message(
                            p.ACTION,
                            self._next_id(),
                            action="recovery_gains",
                            args={"trains": gains},
                        )
                    )
                    self.event.emit(
                        "GAINS_RESENT"
                        if self._lost_running
                        else "GAINS_WAIT_ENGINEER"
                    )
                elif self.module == "train-controller-hw":
                    self.event.emit("GAINS_NOT_RESENT paused unplug")
                self._recovering = True
                self._pump_recovery()
            else:
                self._become_ready()
            return
        if op == p.VIEW:
            self._take_view(incoming["view"])
            return
        current = self._inflight
        if current is None or (incoming["id"], incoming["tick"]) != (
            current["id"],
            current["tick"],
        ):
            self.event.emit(
                f"PI_UNMATCHED_REPLY id={incoming['id']} "
                f"tick={incoming['tick']}"
            )
            return
        if op not in (p.ACK, "OUTPUTS", "REJECTED"):
            return
        self._inflight = None
        if "view" in incoming:
            self._take_view(incoming["view"])
        if self._recovering:
            if op == "REJECTED":
                self.event.emit("PI_RECOVERY_REJECTED " + incoming["reason"])
                return  # Hold the clock: recovery has not succeeded.
            self.event.emit(
                f"PI_REPLAYED {current['op']} id={current['id']} "
                f"tick={current['tick']}"
            )
            # A recovery policy action is itself part of future reconstruction.
            if current.get("action") == "recovery_gains":
                self._history.append(current)
            self._pump_recovery()
            return
        if op != "REJECTED":
            self._history.append(current)
        if current["op"] == "STEP":
            trains = incoming.get("outputs", {}).get("trains")
            if isinstance(trains, dict):
                self._gains = {
                    key: value
                    for key, value in self._gains.items()
                    if key in trains
                }
            metric = dict(
                incoming.get("metrics", {}),
                tick=current["tick"],
                request_bytes=len(p.encode(current)),
                reply_bytes=len(p.encode(incoming)),
            )
            self.metrics.append(metric)
            self.reply.emit(incoming)
        else:
            self.completed.emit(current["id"], incoming)
        self._pump()

    def _take_view(self, view: dict[str, Any]) -> None:
        self._last_view = view
        if "trains" in view:
            self._gains = {
                key: [entry["state"]["kp"], entry["state"]["ki"]]
                for key, entry in view["trains"].items()
                if entry["core"].get("armed")
            }
        self.viewChanged.emit(view)

    def _pump_recovery(self) -> None:
        if self._recovery:
            self._inflight = self._recovery.popleft()
            self.transport.write(p.encode(self._inflight))
            return
        self._recovering = False
        self._inflight, self._saved_inflight = self._saved_inflight, None
        self._ready = True
        if self._inflight:
            self.event.emit(f"PI_RESEND_PENDING tick={self._inflight['tick']}")
            self.transport.write(p.encode(self._inflight))
        else:
            self._pump()
        self.event.emit("PI_RECOVERED " + self.module)

    def _become_ready(self) -> None:
        self._ready = self._ever_ready = True
        self.ready.emit()
        self._pump()

    def submit_step(self, request: dict[str, Any]) -> None:
        """Queue the exact harness envelope; completion is asynchronous."""
        self._queue.append(dict(request))
        self._pump()

    def _pump(self) -> None:
        if (
            not self._closed
            and self._ready
            and self._online
            and self._inflight is None
            and self._queue
        ):
            if self._action_depth and self._queue[0]["op"] == "STEP":
                return
            self._inflight = self._queue.popleft()
            self.transport.write(p.encode(self._inflight))

    def call_action(
        self, name: str, args: dict[str, Any], timeout_ms: int = 5000
    ) -> Any:
        """Apply a window action in stream order; wait within its UI slot."""
        if self._closed:
            return None  # Delayed window timers can outlive QML teardown.
        request = p.message(p.ACTION, self._next_id(), action=name, args=args)
        result: list[dict[str, Any]] = []
        loop = QEventLoop()

        def done(request_id: int, reply: dict[str, Any]) -> None:
            if request_id == request["id"]:
                result.append(reply)
                loop.quit()

        self.completed.connect(done)
        self.closing.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        self._action_depth += 1
        self._queue.appendleft(request)
        self._pump()
        if not result and not self._closed:
            timer.start(timeout_ms)
            loop.exec()
        self.completed.disconnect(done)
        self.closing.disconnect(loop.quit)
        timer.stop()
        self._action_depth -= 1
        QTimer.singleShot(0, self._pump)
        if not result and self._closed:
            return None
        if not result:
            raise ConnectionError(
                "The Pi did not acknowledge the action; it remains queued."
            )
        reply = result[0]
        if reply["op"] == "REJECTED":
            error = RemoteActionError(reply["reason"])
            error.kind = reply.get("error", "")
            error.diagnostics = tuple(reply.get("diagnostics", ()))
            raise error
        return reply.get("result")

    def close(self) -> None:
        self._closed = True
        self.closing.emit()
        self._queue.clear()
        self._inflight = None
        if self._online:
            self.transport.write(p.encode(p.message("QUIT")))
        self.transport.close()
