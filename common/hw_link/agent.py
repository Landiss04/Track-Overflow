"""PiLinkServer: standard-library newline JSON over stdio or a raw tty.

No clock runs here. A durable request journal reconstructs the core and reply
cache after a process/Pi restart. It records accepted and rejected transactions
before replying; replay is internal reconstruction, never a new harness tick.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from utils.harness_protocol import LineBuffer, ProtocolError
from . import protocol as p
from .cores import make_core

AGENT_VERSION = "1"
AGENT_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


class PiLinkServer:
    """Pure dispatcher plus optional durable journal; feed any byte stream."""

    def __init__(
        self,
        module: str,
        journal: Path | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.module = module
        self.journal = journal
        self.log = log or (lambda text: None)
        self.boot = uuid.uuid4().hex
        self.session: str | None = None
        self._hello_seen = False
        self.core = make_core(module)
        self.cache: dict[
            tuple[str, int, int], tuple[bytes, dict[str, Any]]
        ] = {}
        self.buffer = LineBuffer()
        self.last_view = 0.0
        self._restore()

    def _restore(self) -> None:
        if self.journal is None or not self.journal.exists():
            return
        lines = self.journal.read_bytes().splitlines(keepends=True)
        complete = bytearray()
        for index, line in enumerate(lines):
            # A power loss can leave only the final append incomplete.
            if not line.endswith(b"\n"):
                self.log("JOURNAL_INCOMPLETE_TAIL")
                break
            entry = json.loads(line)
            if index == 0:
                if entry["module"] != self.module:
                    raise ValueError("journal module mismatch")
                self.session = entry["session"]
            else:
                request = entry["request"]
                self._execute(request)
                self.cache[self._key(request)] = (
                    p.encode(request),
                    entry["reply"],
                )
            complete.extend(line)
        if len(complete) != self.journal.stat().st_size:
            self.journal.write_bytes(complete)
        self.log(f"JOURNAL_RESTORED transactions={len(self.cache)}")

    @staticmethod
    def _key(request: dict[str, Any]) -> tuple[str, int, int]:
        return request["op"], request["id"], request["tick"]

    def _start(self, session: str) -> None:
        self.session = session
        self.core = make_core(self.module)
        self.cache.clear()
        if self.journal is not None:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open("wb") as stream:
                stream.write(
                    (
                        json.dumps({"module": self.module, "session": session})
                        + "\n"
                    ).encode()
                )
                stream.flush()
                os.fsync(stream.fileno())

    def _record(self, request: dict[str, Any], reply: dict[str, Any]) -> None:
        if self.journal is not None:
            with self.journal.open("ab") as stream:
                stream.write(
                    (
                        json.dumps(
                            {"request": request, "reply": reply},
                            allow_nan=False,
                        )
                        + "\n"
                    ).encode()
                )
                stream.flush()
                os.fsync(stream.fileno())

    def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            if request["op"] == "STEP":
                result = self.core.step(request)
                reply = p.message(
                    "OUTPUTS", request["id"], request["tick"], outputs=result
                )
                reply["metrics"] = {
                    "core_step_s": time.perf_counter() - started
                }
            else:
                result = self.core.action(
                    request["action"], request.get("args", {})
                )
                reply = p.message(
                    p.ACK,
                    request["id"],
                    request["tick"],
                    result=result,
                    view=self.core.view(),
                )
        except (
            Exception
        ) as error:  # noqa: BLE001 - a rejected request is a wire result
            reply = p.message(
                "REJECTED",
                request["id"],
                request["tick"],
                reason=str(error) or type(error).__name__,
                error=type(error).__name__,
                diagnostics=list(getattr(error, "diagnostics", ())),
            )
        # Fail before journalling if a core returned something un-sendable.
        p.encode(reply)
        return reply

    def handle(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        """Handle a checked request once, preserving IDs on replay."""
        p.validate(request)
        op = request["op"]
        if op == p.HELLO:
            if (
                request["protocol"] != p.VERSION
                or request["module"] != self.module
            ):
                return [
                    p.message(
                        "REJECTED",
                        request["id"],
                        request["tick"],
                        reason="HELLO protocol or module mismatch",
                    )
                ]
            resumed = self.session == request["session"]
            if not resumed:
                self._start(request["session"])
            self._hello_seen = True
            return [
                p.message(
                    p.HELLO,
                    request["id"],
                    request["tick"],
                    protocol=p.VERSION,
                    module=self.module,
                    session=self.session,
                    agent_version=AGENT_VERSION,
                    agent_hash=AGENT_HASH,
                    boot=self.boot,
                    resumed=resumed,
                )
            ]
        if op == "QUIT":
            self._start("")
            self.session = None
            self._hello_seen = False
            self.buffer = LineBuffer()
            return []
        if not self.session or not self._hello_seen:
            return [
                p.message(
                    "REJECTED",
                    request["id"],
                    request["tick"],
                    reason="HELLO required",
                )
            ]
        if op not in ("STEP", p.ACTION):
            return []
        key = self._key(request)
        previous = self.cache.get(key)
        if previous is not None:
            if previous[0] != p.encode(request):
                return [
                    p.message(
                        "REJECTED",
                        request["id"],
                        request["tick"],
                        reason=(
                            "request identity reused " "with different payload"
                        ),
                    )
                ]
            self.log(f"CACHE_HIT {key}")
            return [previous[1]]
        reply = self._execute(request)
        self._record(request, reply)
        self.cache[key] = (p.encode(request), reply)
        replies = [reply]
        now = time.monotonic()
        if now - self.last_view >= 0.1:
            self.last_view = now
            replies.append(
                p.message(p.VIEW, tick=request["tick"], view=self.core.view())
            )
        return replies

    def feed(self, data: bytes) -> list[bytes]:
        """Parse chunks; log and skip modem probes and malformed lines."""
        outgoing: list[bytes] = []
        for line in self.buffer.feed(data):
            try:
                if isinstance(line, ProtocolError):
                    raise line
                request = p.decode(line)
                outgoing.extend(
                    p.encode(reply) for reply in self.handle(request)
                )
            except ProtocolError as error:
                self.log(f"SKIPPED_LINE {error}")
        return outgoing


def main(argv: list[str] | None = None) -> int:
    """Run the Pi agent; fault options are explicit development tools."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=p.MODULES, required=True)
    parser.add_argument(
        "--device", help="gadget tty, normally /dev/ttyGS0; otherwise stdio"
    )
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--delay-ms", type=float, default=0)
    parser.add_argument("--jitter-ms", type=float, default=0)
    parser.add_argument("--drop-after", type=int)
    parser.add_argument("--reboot-at-tick", type=int)
    options = parser.parse_args(argv)

    def log(text: str) -> None:
        if options.log:
            with options.log.open("a") as stream:
                stream.write(text + "\n")

    server = PiLinkServer(options.module, options.journal, log)
    count = 0
    fault_marker = options.journal.with_suffix(".fault-used")
    while True:
        if options.device:
            import tty
            import termios

            try:
                reader = writer = os.open(
                    options.device, os.O_RDWR | os.O_NOCTTY
                )
                tty.setraw(reader, when=termios.TCSANOW)
            except OSError as error:
                log(f"DEVICE_OPEN_RETRY {error}")
                time.sleep(0.3)
                continue
        else:
            reader, writer = sys.stdin.fileno(), sys.stdout.fileno()
        try:
            while True:
                data = os.read(reader, 65536)
                if not data:
                    if not options.device:
                        return 0
                    break
                for reply in server.feed(data):
                    decoded = p.decode(reply)
                    if decoded["op"] == "OUTPUTS":
                        count += 1
                        fault = (
                            options.drop_after is not None
                            and count >= options.drop_after
                        ) or decoded["tick"] == options.reboot_at_tick
                        if fault and not fault_marker.exists():
                            fault_marker.write_text("injected\n")
                            log(f"INJECTED_LOSS tick={decoded['tick']}")
                            return 0
                        delay = max(
                            0.0,
                            options.delay_ms
                            + random.uniform(
                                -options.jitter_ms, options.jitter_ms
                            ),
                        )
                        if delay:
                            time.sleep(delay / 1000)
                    pending = memoryview(reply)
                    while pending:
                        sent = os.write(writer, pending)
                        pending = pending[sent:]
        except OSError as error:
            if not options.device:
                return 0  # The subprocess parent closed its pipe.
            log(f"DEVICE_IO_RETRY {error}")
        finally:
            if options.device:
                os.close(reader)
        # A gadget unplug is a lost transport, not a fresh core/session.
        server.buffer = LineBuffer()
        server._hello_seen = False
        log("DEVICE_RECONNECT_WAIT")
        time.sleep(0.3)


if __name__ == "__main__":
    raise SystemExit(main())
