"""Owner link probe: shared production transports, framing and Pi agent."""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QTimer, Qt
from PySide6.QtSerialPort import QSerialPortInfo
from utils.harness_protocol import LineBuffer, ProtocolError
from utils.process_speed import keep_full_speed
from . import protocol as p
from .manifest import AGENT_VERSION, expected_hash
from .transport import (
    IDENTITIES,
    ProcessTransport,
    SerialTransport,
    matches_identity,
)


SLOW_RTT_MS = 10.0
# The host relay waits this long for a reply before it sends the request again.
RESEND_MS = 1000.0
# A damaged line that still starts like a VIEW is display data, so the relay
# lets the next one replace it instead of resending anything.
VIEW_PREFIX = b'{"op":"VIEW"'


def count_over(values: list[float], limit: float = SLOW_RTT_MS) -> int:
    """Round trips strictly over `limit` ms: the tick budget at 100 Hz."""
    return sum(1 for value in values if value > limit)


def summary(values: list[float]) -> dict[str, float | None]:
    """Nearest-rank p95 and p99; empty samples are unavailable, never zero."""
    if not values:
        return dict(mean=None, p95=None, p99=None, maximum=None)
    ordered = sorted(values)
    return dict(
        mean=statistics.mean(values),
        p95=ordered[math.ceil(0.95 * len(values)) - 1],
        p99=ordered[math.ceil(0.99 * len(values)) - 1],
        maximum=max(values),
    )


def recording(path: Path) -> list[dict[str, Any]]:
    """Read ordered ACTION/STEP requests from an agent's durable journal."""
    frames = []
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        request = entry.get("request", entry)
        if request.get("op") in (p.ACTION, "STEP"):
            p.validate(request)
            frames.append(request)
    if not any(frame["op"] == "STEP" for frame in frames):
        raise ValueError("recording needs at least one STEP")
    return frames


def inventory(ports: list[Any]) -> dict[str, Any]:
    """Report both assigned identities, including absent/ambiguous devices."""
    modules = {}
    for module, identity in IDENTITIES.items():
        matches = [
            port.systemLocation()
            for port in ports
            if matches_identity(port, module)
        ]
        modules[module] = dict(
            identity=identity,
            ports=matches,
            matches=len(matches),
            status=(
                "found"
                if len(matches) == 1
                else "missing" if not matches else "ambiguous"
            ),
        )
    return dict(
        modules=modules,
        ports=[
            dict(
                port=port.systemLocation(),
                manufacturer=port.manufacturer(),
                product=port.description(),
                serial=port.serialNumber(),
            )
            for port in ports
        ],
    )


def _announce(module: str, transport: Any, hello_s: float) -> None:
    """Say which board answered and on what port, once HELLO is accepted."""
    port = getattr(getattr(transport, "port", None), "portName", None)
    print(
        f"CONNECTED {module} serial={IDENTITIES[module]['serial']}"
        f" port={port() if port else 'unknown'}"
        f" hello={hello_s:.3f} s agent_hash={expected_hash()[:8]}",
        file=sys.stderr,
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=p.MODULES)
    parser.add_argument(
        "--transport", choices=("serial", "process", "pty"), default="serial"
    )
    parser.add_argument(
        "--list", action="store_true", help="inspect USB identities only"
    )
    parser.add_argument("--echo-bytes", type=int, choices=(1024, 10240, 20480))
    parser.add_argument("--recording", type=Path)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--hz", type=float, default=100)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument(
        "--progress-s",
        type=float,
        default=60,
        help="seconds between progress lines on stderr; 0 for none",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="stop on the first damaged line, as link tests need; "
        "otherwise act as the host relay does",
    )
    parser.add_argument(
        "--resend-ms",
        type=float,
        default=RESEND_MS,
        help="wait for a reply this long before sending the request again",
    )
    parser.add_argument("--output", type=Path)
    opts = parser.parse_args(argv)
    if opts.count < 1 or opts.hz <= 0 or opts.timeout <= 0:
        parser.error("count, hz and timeout must be positive")
    if opts.resend_ms <= 0:
        parser.error("resend-ms must be positive")
    if opts.echo_bytes and opts.recording:
        parser.error("choose echo or recorded core workload")
    if opts.list:
        print(
            json.dumps(inventory(QSerialPortInfo.availablePorts()), indent=2)
        )
        return 0
    if opts.module is None:
        parser.error("--module is required unless --list is used")
    # As the harness and the agent do: Windows may otherwise throttle this
    # process, which lowers the rate it can hold below the one asked for.
    keep_full_speed()
    app = QCoreApplication.instance() or QCoreApplication([])
    session = uuid.uuid4().hex
    bundle_hash = expected_hash()
    hello = p.message(
        p.HELLO,
        protocol=p.VERSION,
        module=opts.module,
        session=session,
        agent_version="bringup-1",
        agent_hash="probe",
    )
    frames = recording(opts.recording) if opts.recording else []
    if opts.echo_bytes:
        # Payload sizes exclude JSON; actual wire bytes are reported too.
        frames = [
            dict(hello, id=i + 1, echo="x" * opts.echo_bytes)
            for i in range(opts.count)
        ]
    with tempfile.TemporaryDirectory(prefix="pi-bringup-") as scratch:
        transport = (
            SerialTransport(opts.module)
            if opts.transport == "serial"
            else ProcessTransport(
                opts.module,
                Path(scratch) / "journal",
                raw_pty=opts.transport == "pty",
                fault_args=["--echo-test"] if opts.echo_bytes else [],
            )
        )
        buffer = LineBuffer()
        started = time.monotonic()
        sent = 0.0
        due = 0.0
        index = -1
        done = False
        failed = False
        rtts: list[float] = []
        core: list[float] = []
        request_bytes = reply_bytes = missed = 0
        hello_s: float | None = None
        # Damaged lines are counted, never hidden: lost is every line whose
        # checksum or shape failed, views_lost the part of those that were
        # VIEWs (not resent), resends the requests sent again.
        lines_lost = views_lost = resends = duplicates = 0
        inflight: dict[str, Any] | None = None
        answered: collections.deque[tuple[int, int]] = collections.deque(
            maxlen=64
        )

        def finish(error: str | None = None) -> None:
            nonlocal done, failed
            if done:
                return
            done, failed = True, bool(error)
            result = dict(
                module=opts.module,
                transport=opts.transport,
                identity=IDENTITIES[opts.module],
                hello_s=hello_s,
                agent_hash=bundle_hash,
                agent_version=AGENT_VERSION,
                samples=len(rtts),
                target_hz=opts.hz,
                late_sends=missed,
                elapsed_s=time.monotonic() - started,
                rtt_ms=summary(rtts),
                rtt_over_10ms=count_over(rtts),
                core_step_ms=summary(core),
                request_bytes=request_bytes,
                reply_bytes=reply_bytes,
                lines_lost=lines_lost,
                views_lost=views_lost,
                resends=resends,
                duplicate_replies=duplicates,
                strict=opts.strict,
                error=error,
                hardware_test=opts.transport == "serial",
            )
            rendered = json.dumps(result, indent=2)
            print(rendered)
            if opts.output:
                # A failed write must not skip app.quit() and hold the port.
                opts.output.parent.mkdir(parents=True, exist_ok=True)
                opts.output.write_text(rendered + "\n")
            app.quit()

        def write(frame: dict[str, Any]) -> None:
            nonlocal sent, request_bytes, inflight
            data = p.frame(p.encode(frame))
            request_bytes += len(data)
            sent = time.monotonic()
            inflight = frame
            if not opts.strict:
                reply_timer.start()
            transport.write(data)

        def resend() -> None:
            # `sent` stays at the first attempt, so the round trip that
            # lost a line is measured whole, not from the second try.
            nonlocal request_bytes, resends
            if done or inflight is None:
                return
            resends += 1
            data = p.frame(p.encode(inflight))
            request_bytes += len(data)
            print(
                f"PI_RESENT {inflight['op']} id={inflight['id']}"
                f" tick={inflight['tick']}",
                file=sys.stderr,
            )
            reply_timer.start()
            transport.write(data)

        def answered_by(reply: dict[str, Any]) -> None:
            nonlocal inflight
            inflight = None
            reply_timer.stop()
            answered.append((reply["id"], reply["tick"]))

        def next_frame() -> None:
            nonlocal index, due, missed
            if done:
                return
            index += 1
            if index == len(frames):
                finish()
                return
            now = time.monotonic()
            if due and now - due > 0.001:
                missed += 1
            due = max(due, now) + 1 / opts.hz
            write(frames[index])

        def receive(data: bytes) -> None:
            nonlocal hello_s, reply_bytes, lines_lost, views_lost, duplicates
            for line in buffer.feed(data):
                if done:
                    return
                try:
                    if isinstance(line, ProtocolError):
                        raise line
                    reply = p.decode(p.unframe(line))
                except ProtocolError as error:
                    if opts.strict:
                        finish(str(error))
                        return
                    # As the relay does: a damaged VIEW is skipped, and
                    # anything else may have been the awaited reply.
                    lines_lost += 1
                    is_view = (
                        isinstance(line, bytes)
                        and line[9:21] == VIEW_PREFIX
                    )
                    views_lost += is_view
                    print(f"PI_SKIPPED_LINE {error}", file=sys.stderr)
                    if not is_view:
                        resend()
                    continue
                reply_bytes += len(line) + 1
                if index == -1:
                    if not p.matches_hello(
                        reply,
                        module=opts.module,
                        session=session,
                        agent_version=AGENT_VERSION,
                        agent_hash=bundle_hash,
                    ):
                        finish(
                            "HELLO identity/version/session/"
                            "bundle hash mismatch"
                        )
                        return
                    answered_by(reply)
                    hello_s = time.monotonic() - started
                    if opts.transport == "serial":
                        _announce(opts.module, transport, hello_s)
                    if opts.progress_s > 0:
                        progress.start(int(opts.progress_s * 1000))
                    next_frame()
                elif reply["op"] != p.VIEW:
                    request = frames[index]
                    if (reply["id"], reply["tick"]) in answered:
                        # A resend whose first answer was only late.
                        duplicates += 1
                        continue
                    if (reply["id"], reply["tick"]) != (
                        request["id"],
                        request["tick"],
                    ):
                        finish("reply identity mismatch")
                        return
                    if reply["op"] == "REJECTED":
                        finish("recorded request rejected: " + reply["reason"])
                        return
                    if (
                        opts.echo_bytes
                        and reply.get("echo") != request["echo"]
                    ):
                        finish(
                            "echo payload mismatch; "
                            "start agent with --echo-test"
                        )
                        return
                    answered_by(reply)
                    rtts.append((time.monotonic() - sent) * 1000)
                    if "core_step_s" in reply.get("metrics", {}):
                        core.append(reply["metrics"]["core_step_s"] * 1000)
                    pacer.start(
                        max(0, math.ceil((due - time.monotonic()) * 1000))
                    )

        transport.connected.connect(lambda: write(hello))
        transport.received.connect(receive)
        transport.diagnostic.connect(
            lambda message: print(message, file=sys.stderr)
        )
        transport.disconnected.connect(
            lambda: finish("transport disconnected")
        )
        minute = {"count": 0, "mark": 0.0}

        def report_progress() -> None:
            now = time.monotonic()
            fresh = rtts[minute["count"] :]
            span = now - (minute["mark"] or started)
            print(
                f"[+{now - started:6.0f} s] {len(rtts):,} of {len(frames):,}"
                f" requests, {len(fresh) / span:.1f} Hz and worst round trip"
                f" {max(fresh, default=0.0):.1f} ms in the last {span:.0f} s",
                file=sys.stderr,
                flush=True,
            )
            minute["count"], minute["mark"] = len(rtts), now

        progress = QTimer()
        progress.timeout.connect(report_progress)
        watchdog = QTimer()
        watchdog.setInterval(50)
        watchdog.timeout.connect(
            lambda: (
                finish("HELLO/reply timeout")
                if time.monotonic() - (sent or started) > opts.timeout
                else None
            )
        )
        watchdog.start()
        reply_timer = QTimer()
        reply_timer.setSingleShot(True)
        reply_timer.setInterval(int(opts.resend_ms))
        reply_timer.timeout.connect(resend)
        # Qt's default coarse timers can fire several ms late on Windows,
        # which lowers the achieved rate independently of the link.
        pacer = QTimer()
        pacer.setSingleShot(True)
        pacer.setTimerType(Qt.TimerType.PreciseTimer)
        pacer.timeout.connect(next_frame)
        transport.start()
        app.exec()
        watchdog.stop()
        pacer.stop()
        progress.stop()
        reply_timer.stop()
        transport.close()
        return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())