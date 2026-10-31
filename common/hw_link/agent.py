"""PiLinkServer: standard-library newline JSON over stdio or a raw tty.

No clock runs here. A durable request journal reconstructs the core and reply
cache after a process/Pi restart. It records accepted and rejected transactions
before replying; replay is internal reconstruction, never a new harness tick.

Every ``CHECKPOINT_TICKS`` steps the agent pickles its core and reply cache and
starts a new journal on top of that checkpoint, so a restart replays at most
that many steps and the journal never grows past them. The checkpoint is only
ever read back from the agent's own disk; nothing pickled crosses the link.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from utils.harness_protocol import LineBuffer, ProtocolError
from . import protocol as p
from .cores import make_core
from .manifest import AGENT_VERSION, expected_hash

# K6 permits display snapshots every 100–200 ms. Use the 200 ms bound
# to halve measured snapshot packing/unpacking and window refresh overhead.
# STEP replies and ACTION acknowledgement views are still immediate.
VIEW_INTERVAL_S = 0.2

# Steps between checkpoints: one minute at 10x, ten at 1x.
CHECKPOINT_TICKS = 600

AGENT_HASH = expected_hash()


class PiLinkServer:
    """Pure dispatcher plus optional durable journal; feed any byte stream."""

    def __init__(
        self,
        module: str,
        journal: Path | None = None,
        log: Callable[[str], None] | None = None,
        *,
        echo_test: bool = False,
    ) -> None:
        self.module = module
        self.echo_test = echo_test
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
        # The reply just executed and its encoded line, sent as is.
        self._fresh: tuple[dict[str, Any], bytes] | None = None
        self._checkpoint_seq = 0
        self._steps_since_checkpoint = 0
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
                # Kept even when stale, so the next HELLO deletes it.
                self._checkpoint_seq = entry.get("checkpoint") or 0
                if entry.get("agent_hash") != AGENT_HASH:
                    # Written by other agent code: start fresh, as a wiped
                    # Pi does, rather than unpickle or replay into this one.
                    self.log("JOURNAL_STALE agent hash differs; starting fresh")
                    return
                if self._checkpoint_seq:
                    path = self._checkpoint_path(self._checkpoint_seq)
                    with path.open("rb") as stream:
                        self.core, self.cache = pickle.load(stream)
                self.session = entry["session"]
            else:
                request = entry["request"]
                self._execute(request)
                self._remember(request, p.encode(request), entry["reply"])
                if request["op"] == "STEP":
                    self._steps_since_checkpoint += 1
            complete.extend(line)
        if len(complete) != self.journal.stat().st_size:
            self.journal.write_bytes(complete)
        self.log(f"JOURNAL_RESTORED transactions={len(self.cache)}")

    @staticmethod
    def _key(request: dict[str, Any]) -> tuple[str, int, int]:
        return request["op"], request["id"], request["tick"]

    def _checkpoint_path(self, seq: int) -> Path:
        assert self.journal is not None
        return self.journal.with_name(f"{self.journal.name}.ckpt{seq}")

    def _start(self, session: str) -> None:
        self.session = session
        self.core = make_core(self.module)
        self.cache.clear()
        if self.journal is not None:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            self._new_journal(0)

    def _new_journal(self, seq: int) -> None:
        # Swap in a journal holding only its header, then drop the
        # checkpoint the old one stood on. A crash in between leaves the
        # old journal and its checkpoint, still consistent.
        assert self.journal is not None
        header = {
            "module": self.module,
            "session": self.session,
            "agent_hash": AGENT_HASH,
            "checkpoint": seq or None,
        }
        _write_durably(self.journal, (json.dumps(header) + "\n").encode())
        if self._checkpoint_seq and self._checkpoint_seq != seq:
            self._checkpoint_path(self._checkpoint_seq).unlink(missing_ok=True)
        self._checkpoint_seq = seq
        self._steps_since_checkpoint = 0

    def _checkpoint(self) -> None:
        seq = self._checkpoint_seq + 1
        _write_durably(
            self._checkpoint_path(seq),
            pickle.dumps(
                (self.core, self.cache), protocol=pickle.HIGHEST_PROTOCOL
            ),
        )
        self._new_journal(seq)
        self.log(f"CHECKPOINT {seq}")

    def _record(self, request: bytes, reply: bytes) -> None:
        if self.journal is None:
            return
        # Both are already compact JSON lines; splice, do not re-encode.
        line = b'{"request":' + request[:-1] + b',"reply":' + reply[:-1]
        with self.journal.open("ab") as stream:
            stream.write(line + b"}\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _remember(
        self, request: dict[str, Any], request_bytes: bytes, reply: Any
    ) -> None:
        # Every ACTION stays, since a reconnect replays the loads; of the
        # steps only the latest can be resent, so only it stays.
        key = self._key(request)
        if key[0] == "STEP":
            for old in [k for k in self.cache if k[0] == "STEP"]:
                del self.cache[old]
        self.cache[key] = (request_bytes, reply)

    def _execute(
        self, request: dict[str, Any]
    ) -> tuple[dict[str, Any], bytes]:
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
        return reply, p.encode(reply)

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
                    **(
                        {"echo": request.get("echo", "")}
                        if self.echo_test
                        else {}
                    ),
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
        request_bytes = p.encode(request)
        previous = self.cache.get(key)
        if previous is not None:
            if previous[0] != request_bytes:
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
        reply, reply_bytes = self._execute(request)
        self._record(request_bytes, reply_bytes)
        self._remember(request, request_bytes, reply)
        self._fresh = (reply, reply_bytes)
        if op == "STEP":
            self._steps_since_checkpoint += 1
            if (
                self.journal is not None
                and self._steps_since_checkpoint >= CHECKPOINT_TICKS
            ):
                self._checkpoint()
        replies = [reply]
        now = time.monotonic()
        if now - self.last_view >= VIEW_INTERVAL_S:
            self.last_view = now
            replies.append(
                p.message(p.VIEW, tick=request["tick"], view=self.core.view())
            )
        return replies

    def feed(self, data: bytes) -> list[bytes]:
        """Parse chunks; log and skip modem probes and malformed lines."""
        return [line for _, line in self._feed(data)]

    def _feed(self, data: bytes) -> list[tuple[dict[str, Any], bytes]]:
        # Each reply with its line; a fresh reply's line is the one
        # encoded when it was checked.
        outgoing: list[tuple[dict[str, Any], bytes]] = []
        for line in self.buffer.feed(data):
            try:
                if isinstance(line, ProtocolError):
                    raise line
                self._fresh = None
                for reply in self.handle(p.decode(line)):
                    fresh = self._fresh
                    if fresh is not None and reply is fresh[0]:
                        outgoing.append(fresh)
                    else:
                        outgoing.append((reply, p.encode(reply)))
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
    parser.add_argument(
        "--echo-test",
        action="store_true",
        help="reflect HELLO echo payload for isolated link tests",
    )
    options = parser.parse_args(argv)

    def log(text: str) -> None:
        if options.log:
            with options.log.open("a") as stream:
                stream.write(text + "\n")

    server = PiLinkServer(
        options.module, options.journal, log, echo_test=options.echo_test
    )
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
                for decoded, reply in server._feed(data):
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


def _write_durably(path: Path, data: bytes) -> None:
    # Write beside, fsync, then rename over: a power loss leaves the old
    # file or the new one, never half of either.
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if hasattr(os, "O_DIRECTORY"):
        # The rename is durable only once its directory is.
        folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)


if __name__ == "__main__":
    raise SystemExit(main())
