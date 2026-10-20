"""Phase 0 edges: each module reads its producers' outputs whole.

In Phase 0 every module is a stub, so the harness hands each module the
last outputs of every producer in ``PRODUCERS``, untranslated and keyed
by producer. From Phase 1 the real modules replace this, edge by edge,
with mapping functions between their types (D005).
"""

from __future__ import annotations

__all__ = ["stub_inputs"]

from collections.abc import Mapping
from typing import Any

from common.harness.modules import PRODUCERS


def stub_inputs(
    consumer: str, outputs: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Return ``consumer``'s inputs: its producers' outputs, whole.

    Args:
        consumer: The module about to step.
        outputs: Every module's last outputs, by module. A producer
            with none yet is left out.
    """
    return {
        producer: outputs[producer]
        for producer in PRODUCERS[consumer]
        if producer in outputs
    }
