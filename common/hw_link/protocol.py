"""Additive D027 messages, confined to the host-to-Pi connection."""

from __future__ import annotations

import zlib
from collections.abc import Mapping
from typing import Any

from utils import harness_protocol as hp

VERSION = hp.PROTOCOL_VERSION
MODULES = ("track-controller-hw", "train-controller-hw")
HELLO, ACTION, ACK, VIEW = "HELLO", "ACTION", "ACK", "VIEW"


def matches_hello(
    reply: Mapping[str, Any],
    *,
    module: str,
    session: str,
    agent_version: str,
    agent_hash: str,
) -> bool:
    """Match a decoded HELLO to the host's expected peer and session.

    Framing and field types are checked by decode. Boot/recovery policy belongs
    to the caller; a bringup probe does not require a boot identifier.
    """
    return (
        reply.get("op") == HELLO
        and reply.get("module") == module
        and reply.get("protocol") == VERSION
        and reply.get("session") == session
        and reply.get("agent_version") == agent_version
        and reply.get("agent_hash") == agent_hash
    )


def validate(message: Mapping[str, Any]) -> None:
    """Check framing fields and operation-specific payloads."""
    op = message.get("op")
    if op in hp.HARNESS_TO_MODULE | hp.MODULE_TO_HARNESS:
        hp.validate(message)
        return
    if op not in (HELLO, ACTION, ACK, VIEW):
        raise hp.ProtocolError(f"unknown Pi op {op!r}")
    # Reuse the shared strict integer checks, without extending its op set.
    hp.validate(dict(message, op=hp.QUIT))
    fields = {
        HELLO: ("module", "session", "agent_version", "agent_hash"),
        ACTION: ("action",),
        ACK: (),
        VIEW: (),
    }[op]
    for field in fields:
        if not isinstance(message.get(field), str) or not message[field]:
            raise hp.ProtocolError(f"{op} needs nonempty {field}")
    if op == HELLO:
        if message["module"] not in MODULES:
            raise hp.ProtocolError("unknown hardware module")
        if type(message.get("protocol")) is not int:
            raise hp.ProtocolError("HELLO needs protocol integer")
    if op == ACTION and not isinstance(message.get("args", {}), dict):
        raise hp.ProtocolError("ACTION args must be an object")
    if op == VIEW and not isinstance(message.get("view"), dict):
        raise hp.ProtocolError("VIEW needs view object")


def encode(message: Mapping[str, Any]) -> bytes:
    """Encode with the harness's finite-number and Unicode checks."""
    validate(message)
    # One strict pass; the receiver reads the same values that the old
    # encode-parse-encode normalisation produced.
    return hp._dump(dict(message))


def decode(line: bytes) -> dict[str, Any]:
    """Decode strictly while keeping Pi-only ops out of the harness codec."""
    # The shared parser catches overflow, NaN, invalid surrogates and
    # non-objects; Pi validation then checks IDs and the op's fields.
    raw = hp._parse(line)
    validate(raw)
    return raw


def frame(line: bytes) -> bytes:
    """Prefix an encoded line with its CRC-32 for the USB link."""
    # The link has been seen to drop chunks mid-line; some damaged lines
    # still parse as JSON, so only a checksum can tell.
    return b"%08x " % zlib.crc32(line.rstrip(b"\n")) + line


def unframe(line: bytes) -> bytes:
    """Return a link line's JSON, refusing it unless its CRC-32 matches."""
    body = line[9:]
    try:
        expected = int(line[:8], 16) if line[8:9] == b" " else None
    except ValueError:
        expected = None
    if expected is None:
        raise hp.ProtocolError("line has no checksum")
    if zlib.crc32(body) != expected:
        raise hp.ProtocolError("line checksum does not match")
    return body


def message(
    op: str, request_id: int = 0, tick: int = 0, **fields: Any
) -> dict[str, Any]:
    """Build one Pi envelope."""
    return dict(op=op, id=request_id, tick=tick, **fields)
