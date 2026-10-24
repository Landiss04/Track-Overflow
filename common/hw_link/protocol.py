"""Additive D027 messages, confined to the host-to-Pi connection."""

from __future__ import annotations

import json
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
    # Shared encoder recursively checks JSON types, finite numbers and Unicode.
    line = hp.encode(
        {"op": hp.STATE, "id": 0, "tick": 0, "state": dict(message)}
    )
    result = json.loads(line)["state"]
    return (
        json.dumps(
            result, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")


def decode(line: bytes) -> dict[str, Any]:
    """Decode strictly while keeping Pi-only ops out of the harness codec."""
    try:
        raw = json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise hp.ProtocolError(f"not a Pi JSON object: {error}") from error
    if not isinstance(raw, dict):
        raise hp.ProtocolError("not a Pi JSON object")
    # The shared decoder catches overflow, NaN, invalid surrogates and IDs.
    checked = {"op": hp.STATE, "id": 0, "tick": 0, "state": raw}
    hp.decode(json.dumps(checked, ensure_ascii=True).encode("utf-8"))
    validate(raw)
    return raw


def message(
    op: str, request_id: int = 0, tick: int = 0, **fields: Any
) -> dict[str, Any]:
    """Build one Pi envelope."""
    return dict(op=op, id=request_id, tick=tick, **fields)
