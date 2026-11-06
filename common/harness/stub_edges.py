"""Edges into stub modules: each reads its producers' outputs whole.

A stub (``stub_module``) takes the last outputs of every producer in
``PRODUCERS``, untranslated and keyed by producer. In Phase 0 every
module was a stub, and ``StubEdges`` serves that whole system. Once a
module is wired in, ``edges.SystemEdges`` gives it real mapping
functions (D005) and keeps these for the stubs left.
"""

from __future__ import annotations

__all__ = ["StubEdges", "stub_inputs"]

from collections.abc import Mapping, Sequence
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


class StubEdges:
    """The harness's edges when every module is a stub."""

    def tick_completed(
        self,
        tick: int,
        sim_time_s: float,
        fresh: Mapping[str, Mapping[str, Any]],
    ) -> Sequence[tuple[str, str, str]]:
        """Stubs report nothing for the harness to act on."""
        return ()

    def inputs_for(
        self,
        consumer: str,
        tick: int,
        sim_time_s: float,
        outputs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Return ``consumer``'s producers' outputs, whole."""
        return stub_inputs(consumer, outputs)
