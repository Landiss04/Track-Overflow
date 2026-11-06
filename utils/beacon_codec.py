"""Pure encoding of the bounded logical beacon, independent of wire types."""

from __future__ import annotations

import json

MAX_BEACON_CHARS = 128


def encode_beacon(name: object, side: object, underground: object) -> str:
    """Validate and encode the complete payload; never truncate a name.

    Module-owned Beacon objects and outer transport envelopes stay intact.
    ASCII escaping makes this character limit also a UTF-8 byte limit.
    """
    if not isinstance(name, str):
        raise ValueError("beacon station_name must be text")
    if not isinstance(side, str) or side not in ("L", "R", "LR"):
        raise ValueError("beacon platform_side must be L, R or LR")
    if not isinstance(underground, bool):
        raise ValueError("beacon underground must be True or False")
    payload = json.dumps(
        [name, side, underground],
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(payload) > MAX_BEACON_CHARS:
        raise ValueError(
            f"beacon payload must be at most {MAX_BEACON_CHARS} "
            f"characters, got {len(payload)}"
        )
    return payload
