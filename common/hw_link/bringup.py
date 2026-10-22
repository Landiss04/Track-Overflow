"""Owner link probe: shared production transports, framing and Pi agent."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtSerialPort import QSerialPortInfo
from utils.harness_protocol import LineBuffer, ProtocolError
from . import protocol as p
from .manifest import AGENT_VERSION, expected_hash
from .transport import (
    IDENTITIES,
    ProcessTransport,
    SerialTransport,
    matches_identity,
)


def summary(values: list[float]) -> dict[str, float | None]:
    """Nearest-rank p95; empty samples are unavailable, never zero latency."""
    if not values:
        return dict(mean=None, p95=None, maximum=None)
    return dict(
        mean=statistics.mean(values),
        p95=sorted(values)[math.ceil(0.95 * len(values)) - 1],
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
    parser.add_argument("--output", type=Path)
    opts = parser.parse_args(argv)
    if opts.count < 1 or opts.hz <= 0 or opts.timeout <= 0:
        parser.error("count, hz and timeout must be positive")
    if opts.echo_bytes and opts.recording:
        parser.error("choose echo or recorded core workload")
    if opts.list:
        print(
            json.dumps(inventory(QSerialPortInfo.availablePorts()), indent=2)
        )
        return 0
    if opts.module is None:
        parser.error("--module is required unless --list is used")
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
                core_step_ms=summary(core),
                request_bytes=request_bytes,
                reply_bytes=reply_bytes,
                error=error,
                hardware_test=opts.transport == "serial",
            )
            rendered = json.dumps(result, indent=2)
            print(rendered)
            if opts.output:
                opts.output.write_text(rendered + "\n")
            app.quit()

        def write(frame: dict[str, Any]) -> None:
            nonlocal sent, request_bytes
            data = p.encode(frame)
            request_bytes += len(data)
            sent = time.monotonic()
            transport.write(data)

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
            nonlocal hello_s, reply_bytes
            for line in buffer.feed(data):
                if isinstance(line, ProtocolError):
                    finish(str(line))
                    return
                if done:
                    return
                try:
                    reply = p.decode(line)
                except ProtocolError as error:
                    finish(str(error))
                    return
                reply_bytes += len(line) + 1
                if index == -1:
                    if (
                        reply["op"] != p.HELLO
                        or reply.get("module") != opts.module
                        or reply.get("protocol") != p.VERSION
                        or reply.get("session") != session
                        or reply.get("agent_version") != AGENT_VERSION
                        or reply.get("agent_hash") != bundle_hash
                    ):
                        finish(
                            "HELLO identity/version/session/"
                            "bundle hash mismatch"
                        )
                        return
                    hello_s = time.monotonic() - started
                    next_frame()
                elif reply["op"] != p.VIEW:
                    request = frames[index]
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
                    rtts.append((time.monotonic() - sent) * 1000)
                    if "core_step_s" in reply.get("metrics", {}):
                        core.append(reply["metrics"]["core_step_s"] * 1000)
                    QTimer.singleShot(
                        max(0, math.ceil((due - time.monotonic()) * 1000)),
                        next_frame,
                    )

        transport.connected.connect(lambda: write(hello))
        transport.received.connect(receive)
        transport.diagnostic.connect(
            lambda message: print(message, file=sys.stderr)
        )
        transport.disconnected.connect(
            lambda: finish("transport disconnected")
        )
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
        transport.start()
        app.exec()
        watchdog.stop()
        transport.close()
        return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
