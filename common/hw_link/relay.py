"""Host-side ordered Pi relay and reconnect state machine."""

from __future__ import annotations

import uuid
from collections import deque
from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from utils.harness_protocol import LineBuffer, ProtocolError
from . import protocol as p
from .transport import ByteTransport
from .manifest import AGENT_VERSION, expected_hash

# Configuration a reconnected or replaced Pi is given again. Runtime state
# (locks, faults, integrals, gains) is not replayed; a replaced Pi starts
# from these and the gain policy below.
REPLAYED_ACTIONS = frozenset(
    {"load_territory", "load_program", "test_engineer_gains"}
)


def _key(frame: Mapping[str, Any]) -> list[Any]:
    return [frame["op"], frame["id"], frame["tick"]]


class RemoteActionError(ValueError):
    """A refused Pi action, including the original module diagnostic."""

    kind: str = ""
    diagnostics: tuple[str, ...] = ()


class HardwareRelay(QObject):
    """Hold harness replies during USB loss; never substitute a local core."""

    # Messages pass as Python objects: a dict signal argument would be
    # converted to a QVariantMap and back on every emit, which for the
    # Track Controller's per-tick outputs costs more than the relay.
    # Each message is freshly decoded, and receivers only read it.
    ready = Signal()
    reply = Signal(object)
    viewChanged = Signal(object)
    diagnosticEvent = Signal(str)
    completed = Signal(int, object)
    closing = Signal()

    # The Pi discards bytes that arrive while its agent has no tty open.
    HELLO_RETRY_MS = 1000
    # A repeat is answered from the Pi's cache, so asking again is safe.
    REPLY_TIMEOUT_MS = 1000

    def __init__(
        self,
        module: str,
        transport: ByteTransport,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.module, self.transport = module, transport
        self.session = uuid.uuid4().hex
        self.expected_agent_hash = expected_hash()
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
        # Answered requests the Pi has not yet reported on its disk, with
        # how it answered; a power cut can take them back.
        self._unsaved: list[tuple[dict[str, Any], str]] = []
        self._expect_rejected: set[tuple[Any, ...]] = set()
        self._recovery: deque[dict[str, Any]] = deque()
        self._recovering = False
        self._inflight: dict[str, Any] | None = None
        self._saved_inflight: dict[str, Any] | None = None
        self._queue: deque[dict[str, Any]] = deque()
        self._last_view: dict[str, Any] = {}
        self._gains: dict[str, list[float]] = {}
        self._hello: bytes | None = None
        self._hello_answered = False
        self._hello_timer = QTimer(self)
        self._hello_timer.setInterval(self.HELLO_RETRY_MS)
        self._hello_timer.timeout.connect(self._send_hello)
        self._reply_timer = QTimer(self)
        self._reply_timer.setSingleShot(True)
        self._reply_timer.setInterval(self.REPLY_TIMEOUT_MS)
        self._reply_timer.timeout.connect(self._resend)
        self.transport.connected.connect(self._connected)
        self.transport.disconnected.connect(self._disconnected)
        self.transport.received.connect(self._received)
        self.transport.diagnostic.connect(
            lambda value: self.diagnosticEvent.emit(
                value
                if value.startswith("PI_SEARCH ")
                else "TRANSPORT " + value
            )
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
        self.diagnosticEvent.emit("PI_CONNECTED " + self.module)
        self._hello_answered = False
        # A host that closed mid-write leaves a partial line on the Pi; end it.
        hello = p.message(
            p.HELLO,
            self._next_id(),
            protocol=p.VERSION,
            module=self.module,
            session=self.session,
            agent_version="host-1",
            agent_hash="host",
        )
        self._hello = b"\n" + p.frame(p.encode(hello))
        self._send_hello()
        self._hello_timer.start()

    def _send_hello(self) -> None:
        if self._hello is not None and self._online and not self._closed:
            self.transport.write(self._hello)

    def _disconnected(self) -> None:
        if self._closed:
            return
        self._hello = None
        self._hello_timer.stop()
        self._reply_timer.stop()
        self._online = self._ready = False
        if not self._recovering:
            self._lost_running = self._clock_running
        self.diagnosticEvent.emit(
            f"PI_LOST {self.module} running={self._lost_running}"
        )
        # The process transport needs an explicit restart. SerialTransport also
        # keeps scanning, and start() is idempotent for both.
        QTimer.singleShot(1100, self.transport.start)

    def _received(self, data: bytes) -> None:
        for line in self.buffer.feed(data):
            try:
                if isinstance(line, ProtocolError):
                    raise line
                incoming = p.decode(p.unframe(line))
            except ProtocolError as error:
                self.diagnosticEvent.emit(f"PI_SKIPPED_LINE {error}")
                # Lines lose bytes mid-way, so a cut VIEW still starts as one;
                # anything else may have been the awaited reply.
                if line[9:21] != b'{"op":"VIEW"':
                    self._resend()
                continue
            self._handle(incoming)

    def _send_inflight(self) -> None:
        assert self._inflight is not None
        self.transport.write(p.frame(p.encode(self._inflight)))
        self._reply_timer.start()

    def _resend(self) -> None:
        if self._inflight is None or not self._online or self._closed:
            return
        self.diagnosticEvent.emit(
            f"PI_RESENT {self._inflight['op']} id={self._inflight['id']} "
            f"tick={self._inflight['tick']}"
        )
        self._send_inflight()

    def _handle(self, incoming: dict[str, Any]) -> None:
        if self._closed:
            return
        op = incoming["op"]
        if op == p.HELLO:
            if not p.matches_hello(
                incoming,
                module=self.module,
                session=self.session,
                agent_version=AGENT_VERSION,
                agent_hash=self.expected_agent_hash,
            ) or not incoming.get("boot"):
                self.diagnosticEvent.emit(
                    "PI_HELLO_REJECTED "
                    "identity, version or bundle hash mismatch"
                )
                return
            if self._hello_answered:
                return  # A retried HELLO answered again; this link is up.
            self._hello_answered = True
            self._hello = None
            self._hello_timer.stop()
            rebooted = self._boot is not None and self._boot != incoming.get(
                "boot"
            )
            self._boot = incoming.get("boot")
            self.diagnosticEvent.emit(
                f"PI_HELLO {self.module} "
                f"version={incoming['agent_version']} "
                f"hash={incoming['agent_hash']}"
            )
            if self._ever_ready:
                if not self._recovering:
                    self._saved_inflight = self._inflight
                self._inflight = None
                self._reply_timer.stop()
                lost = self._lost_requests(incoming)
                # A resumed agent answers these from its cache; a replaced
                # one runs them again.
                self._recovery = deque(
                    frame
                    for frame in self._history
                    if all(frame is not other for other in lost)
                )
                self._recovery.extend(lost)
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
                    self.diagnosticEvent.emit(
                        "GAINS_RESENT"
                        if self._lost_running
                        else "GAINS_WAIT_ENGINEER"
                    )
                elif self.module == "train-controller-hw":
                    self.diagnosticEvent.emit("GAINS_NOT_RESENT paused unplug")
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
            self.diagnosticEvent.emit(
                f"PI_UNMATCHED_REPLY id={incoming['id']} "
                f"tick={incoming['tick']}"
            )
            return
        if op not in (p.ACK, "OUTPUTS", "REJECTED"):
            return
        self._inflight = None
        self._reply_timer.stop()
        if "view" in incoming:
            self._take_view(incoming["view"])
        if self._recovering:
            if (
                op == "REJECTED"
                and tuple(_key(current)) not in self._expect_rejected
            ):
                self.diagnosticEvent.emit(
                    "PI_RECOVERY_REJECTED " + incoming["reason"]
                )
                return  # Hold the clock: recovery has not succeeded.
            self._keep_until_durable(current, op, incoming.get("durable"))
            self.diagnosticEvent.emit(
                f"PI_REPLAYED {current['op']} id={current['id']} "
                f"tick={current['tick']}"
            )
            self._pump_recovery()
            return
        self._keep_until_durable(current, op, incoming.get("durable"))
        if op != "REJECTED" and current.get("action") in REPLAYED_ACTIONS:
            self._history.append(current)
        if current["op"] == "STEP":
            trains = incoming.get("outputs", {}).get("trains")
            if isinstance(trains, dict):
                self._gains = {
                    key: value
                    for key, value in self._gains.items()
                    if key in trains
                }
            self.reply.emit(incoming)
        else:
            self.completed.emit(current["id"], incoming)
        self._pump()

    def _keep_until_durable(
        self, frame: dict[str, Any], op: str, durable: Any
    ) -> None:
        key = _key(frame)
        if all(_key(kept) != key for kept, _ in self._unsaved):
            self._unsaved.append((frame, op))
        if durable is not None:
            for index, (kept, _) in enumerate(self._unsaved):
                if _key(kept) == list(durable):
                    del self._unsaved[: index + 1]
                    break

    def _lost_requests(self, hello: Mapping[str, Any]) -> list[dict[str, Any]]:
        """What a resumed Pi lost with its power, oldest first."""
        self._expect_rejected = set()
        if not hello.get("resumed"):
            self._unsaved.clear()
            return []
        applied = hello.get("applied")
        pending = self._saved_inflight
        if pending is not None and applied == _key(pending):
            return []
        keys = [_key(frame) for frame, _ in self._unsaved]
        if applied in keys:
            lost = self._unsaved[keys.index(applied) + 1 :]
        else:
            # The Pi stopped exactly where the host last trimmed.
            lost = self._unsaved
        self._expect_rejected = {
            tuple(_key(frame)) for frame, op in lost if op == "REJECTED"
        }
        if lost:
            self.diagnosticEvent.emit(
                f"PI_RESENDING_UNSAVED count={len(lost)} "
                f"from_tick={lost[0][0]['tick']}"
            )
        return [frame for frame, _ in lost]

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
            self._send_inflight()
            return
        self._recovering = False
        self._inflight, self._saved_inflight = self._saved_inflight, None
        self._ready = True
        if self._inflight:
            self.diagnosticEvent.emit(
                f"PI_RESEND_PENDING tick={self._inflight['tick']}"
            )
            self._send_inflight()
        else:
            self._pump()
        self.diagnosticEvent.emit("PI_RECOVERED " + self.module)

    def _become_ready(self) -> None:
        self._ready = self._ever_ready = True
        self.ready.emit()
        self._pump()

    def submit_step(self, request: Mapping[str, Any]) -> None:
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
            self._send_inflight()

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
        self._hello_timer.stop()
        self._reply_timer.stop()
        self.closing.emit()
        self._queue.clear()
        self._inflight = None
        if self._online:
            self.transport.write(p.frame(p.encode(p.message("QUIT"))))
        self.transport.close()
