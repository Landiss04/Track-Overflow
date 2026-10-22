"""Lossless display snapshots with a fixed dataclass allowlist; no pickle."""

from __future__ import annotations

import dataclasses
from typing import Any


def pack(value: Any) -> Any:
    """Encode frozen Track boundary values, including dataclass map keys."""
    if dataclasses.is_dataclass(value):
        return {
            "$type": type(value).__name__,
            "fields": {
                f.name: pack(getattr(value, f.name))
                for f in dataclasses.fields(value)
            },
        }
    if isinstance(value, dict) or hasattr(value, "items"):
        return {"$map": [[pack(k), pack(v)] for k, v in value.items()]}
    if isinstance(value, (tuple, list, set, frozenset)):
        return {
            "$sequence": type(value).__name__,
            "items": [pack(v) for v in value],
        }
    return value


def unpack(value: Any) -> Any:
    """Decode only known Track boundary dataclasses."""
    if not isinstance(value, dict):
        return value
    if "$type" in value:
        from track_ctrl_hw import interface

        allowed = {
            name: cls
            for name, cls in vars(interface).items()
            if isinstance(cls, type) and dataclasses.is_dataclass(cls)
        }
        cls = allowed.get(value["$type"])
        if cls is None:
            raise ValueError("unknown display type")
        return cls(**{k: unpack(v) for k, v in value["fields"].items()})
    if "$map" in value:
        return {unpack(k): unpack(v) for k, v in value["$map"]}
    if "$sequence" in value:
        sequence_type = {
            "tuple": tuple,
            "list": list,
            "set": set,
            "frozenset": frozenset,
        }[value["$sequence"]]
        return sequence_type(unpack(v) for v in value["items"])
    return {k: unpack(v) for k, v in value.items()}
