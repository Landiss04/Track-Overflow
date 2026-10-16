"""Edge mapping from the CTC Office to the Track Controller (software).

One pure function that translates the CTC Office's output types into the
Track Controller's input types (D005). It touches no module state and
imports both modules' boundary types, which no module does of the other.
Units do not change across the edge: speeds are whole m/s and
authorities are block counts.

The CTC Office addresses a suggestion to a train and names the block the
train is in. A wayside sends down a track circuit and cannot address a
train, so the block is all the Track Controller needs and the train ID
stops here. The Track Controller reads the suggestion as that block's.

Not mapped through ``common/interfaces.py``: the catalog has no type for
this edge yet (its ``ISwTrackController`` predates D013 and block
addressing), so the mapping goes straight between the two modules'
types until it does.
"""

from __future__ import annotations

from ctc.interface import (
    TrackControllerOutputs as CtcToTrackController,
    TrainSuggestion,
)
from track_ctrl.interface import (
    BlockKey,
    CtcInputs,
    Suggestion,
)


def ctc_to_track_controller(
    outputs: CtcToTrackController,
) -> CtcInputs:
    """Map the CTC Office's output for the Track Controller to its input.

    If two suggestions name the same block, which the CTC Office's
    one-train-per-block rule should prevent, the more restrictive speed
    and authority win, each taken on its own: a vital controller never
    takes the more permissive of two conflicting commands.
    """
    return CtcInputs(
        closed_blocks=frozenset(
            BlockKey(ref.line, ref.block_id) for ref in outputs.closed_blocks
        ),
        switch_commands={
            BlockKey(command.line, command.switch_id): command.position
            for command in outputs.switch_commands
        },
        suggestions=_by_block(outputs.suggestions),
    )


def _by_block(
    suggestions: tuple[TrainSuggestion, ...],
) -> dict[BlockKey, Suggestion]:
    found: dict[BlockKey, Suggestion] = {}
    for each in suggestions:
        key = BlockKey(each.line, each.block_id)
        wanted = Suggestion(each.suggested_speed_mps, each.authority_blocks)
        held = found.get(key)
        found[key] = wanted if held is None else Suggestion(
            min(held.speed_mps, wanted.speed_mps),
            min(held.authority_blocks, wanted.authority_blocks),
        )
    return found
