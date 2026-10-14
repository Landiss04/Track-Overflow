"""The fail-safe supervisor applied to every PLC result.

The PLC program is written by a programmer and is therefore not trusted
to be safe. This module sits between the program's outputs and the
output card and can only ever make an output *more* restrictive: it
lowers a speed, cuts an authority to zero, drops a signal to red and
arms a crossing. It never raises a speed, extends an authority or
clears a crossing the program left armed.

That one-way property is what "vital" means here, and it is the reason
a wrong program produces a stopped railway rather than a collision.

Speed and authority are per block (D015). The controller receives a
suggestion for each block from the CTC Office, the program decides per
block whether to pass it on (the ``AUTH_n`` outputs), and a train gets
the values of the block it is in down that block's track circuit. Speeds
are whole m/s and authorities are block counts (D013), so nothing in
this module converts a unit; the display layer does that.

Every override is reported as a :class:`VitalOverride` so the Program
tab can show the programmer exactly which rule fired and why, rather
than silently disagreeing with the code on screen. Overrides that apply
to many blocks are reported once, naming the blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from track_ctrl.layout import Block, ControllerConfig

#: Aspect order, most restrictive first. A signal always falls back to
#: the first entry.
ASPECTS: tuple[str, ...] = ("RED", "YELLOW", "GREEN", "SUPER GREEN")

#: Blocks named in one override message before the rest are counted.
_NAMED_BLOCKS = 6


@dataclass(frozen=True)
class Suggestion:
    """What the CTC Office suggests for one block."""

    speed_mps: int
    authority_blocks: int


@dataclass(frozen=True)
class TrackCircuit:
    """What is sent down one block's track circuit to the train in it."""

    speed_mps: int
    authority_blocks: int


@dataclass(frozen=True)
class VitalOverride:
    """One restriction the supervisor imposed on the program's output."""

    rule: str
    signal: str
    message: str

    def format(self) -> str:
        """Render as a single terminal line."""
        return f"VITAL  {self.rule}  {self.signal}: {self.message}"


@dataclass
class ControllerOutputs:
    """What the controller actually drives onto the output card."""

    #: Only for blocks the CTC Office sent a suggestion for.
    track_circuits: dict[str, TrackCircuit] = field(default_factory=dict)
    switches: dict[str, bool] = field(default_factory=dict)
    aspects: dict[str, str] = field(default_factory=dict)
    crossings: dict[str, bool] = field(default_factory=dict)
    overrides: tuple[VitalOverride, ...] = ()


def restrictive_outputs(
    config: ControllerConfig,
    reason: str,
    suggestions: Mapping[str, Suggestion] | None = None,
    held_switches: Mapping[str, bool] | None = None,
) -> ControllerOutputs:
    """Return the state the wayside falls back to when it cannot trust
    its own program: stop everywhere, all red, every crossing armed.

    This is the output of a missing program or a failed scan. Switches
    are held where they stand rather than thrown, since moving a switch
    is not a safe way to fail.
    """
    held = held_switches or {}
    return ControllerOutputs(
        track_circuits={
            block_id: TrackCircuit(0, 0)
            for block_id in (suggestions or {})
        },
        switches={
            switch.switch_id: held.get(switch.switch_id, False)
            for switch in config.switches
        },
        aspects={signal.signal_id: "RED" for signal in config.signals},
        crossings={crossing.crossing_id: True for crossing in config.crossings},
        overrides=(VitalOverride("fail_safe", "ALL", reason),),
    )


def _decode_aspect(
    values: Mapping[str, bool], signal_names: tuple[str, str, str, str]
) -> tuple[str, str | None]:
    """Turn four aspect bits into one aspect, failing safe to red.

    A signal showing no aspect is dark and a signal showing more than
    one is ambiguous; both are wrong-side failures if read
    permissively, so both resolve to RED.
    """
    lit = [
        aspect
        for aspect, name in zip(ASPECTS, signal_names)
        if values.get(name, False)
    ]
    if len(lit) == 1:
        return lit[0], None
    if not lit:
        return "RED", "no aspect lit; signal would be dark"
    return "RED", f"{len(lit)} aspects lit at once ({', '.join(lit)})"


def _blocks_text(block_ids: Sequence[str]) -> str:
    """Name a few blocks and count the rest, for one-line messages."""
    named = ", ".join(block_ids[:_NAMED_BLOCKS])
    extra = len(block_ids) - _NAMED_BLOCKS
    return f"{named} and {extra} more" if extra > 0 else named


def supervise(
    config: ControllerConfig,
    blocks: Sequence[Block],
    values: Mapping[str, bool],
    suggestions: Mapping[str, Suggestion],
    occupancy: Mapping[str, bool],
    closed: Mapping[str, bool],
    maintenance: bool,
    ctc_switch_commands: Mapping[str, bool],
    manual_switches: Mapping[str, bool],
    current_switches: Mapping[str, bool],
    faulted_switches: Mapping[str, bool] | None = None,
    moving_switches: Mapping[str, bool] | None = None,
    speed_limit_override_mps: int | None = None,
) -> ControllerOutputs:
    """Clamp one scan's raw outputs down to something safe to drive.

    ``values`` is everything the PLC program produced. ``suggestions``
    holds the CTC Office's suggestion for each block it sent one for.
    ``current_switches`` is where the switches stand now, which a switch
    locked under a train is held at. ``faulted_switches`` and
    ``moving_switches`` are the Track Model's physical switch flags, and
    ``speed_limit_override_mps`` replaces the per-block posted limits
    when the configuration supplies one.

    In maintenance mode a switch follows the CTC Office's command if it
    has sent one, else the programmer's hand-set position, else the
    program. Outside maintenance only the program drives a switch.
    """
    overrides: list[VitalOverride] = []
    faulted = faulted_switches or {}
    moving = moving_switches or {}

    # A switch machine that reports a fault cannot be trusted to be in
    # the position it was commanded to, so the block it sits on is
    # treated like an unusable one for signals and track circuits.
    fault_blocks = {
        switch.block_id
        for switch in config.switches
        if faulted.get(switch.switch_id, False)
    }
    moving_blocks = {
        switch.block_id
        for switch in config.switches
        if moving.get(switch.switch_id, False)
    }

    # --- switches ----------------------------------------------------
    switches: dict[str, bool] = {}
    for switch in config.switches:
        switch_id = switch.switch_id
        requested = values.get(switch.output_signal, False)
        if maintenance and switch_id in ctc_switch_commands:
            switches[switch_id] = ctc_switch_commands[switch_id]
            overrides.append(
                VitalOverride(
                    "ctc_switch_command",
                    f"SW_{switch_id}",
                    "maintenance mode: the CTC Office's command is obeyed, "
                    "the program's output ignored",
                )
            )
        elif maintenance and switch_id in manual_switches:
            switches[switch_id] = manual_switches[switch_id]
            overrides.append(
                VitalOverride(
                    "manual_switch",
                    f"SW_{switch_id}",
                    "held by the programmer in maintenance mode, program "
                    "output ignored",
                )
            )
        else:
            switches[switch_id] = requested

    # A switch under a train must not move. The requested position is
    # refused and the switch is held where it already stands.
    for switch in config.switches:
        if not occupancy.get(switch.block_id, False):
            continue
        held = current_switches.get(switch.switch_id, False)
        if switches[switch.switch_id] != held:
            overrides.append(
                VitalOverride(
                    "switch_locked_under_train",
                    f"SW_{switch.switch_id}",
                    f"block {switch.block_id} is occupied; the switch is "
                    "locked and will not move",
                )
            )
        switches[switch.switch_id] = held

    # --- signals -----------------------------------------------------
    aspects: dict[str, str] = {}
    for signal in config.signals:
        aspect, problem = _decode_aspect(values, signal.aspect_signals)
        if problem is not None:
            overrides.append(
                VitalOverride("signal_aspect", f"SIG_{signal.signal_id}",
                              problem)
            )
        # A signal protecting an occupied, closed or faulted block is
        # red no matter what the program computed.
        if (
            occupancy.get(signal.block_id, False)
            or closed.get(signal.block_id, False)
            or signal.block_id in fault_blocks
        ):
            if aspect != "RED":
                overrides.append(
                    VitalOverride(
                        "signal_protects_block",
                        f"SIG_{signal.signal_id}",
                        f"block {signal.block_id} is occupied, closed or "
                        f"holds a faulted switch; {aspect} dropped to RED",
                    )
                )
            aspect = "RED"
        aspects[signal.signal_id] = aspect

    # --- crossings ---------------------------------------------------
    crossings: dict[str, bool] = {}
    for crossing in config.crossings:
        requested = values.get(crossing.output_signal, False)
        must_arm = any(
            occupancy.get(block_id, False)
            for block_id in crossing.approach_block_ids
        )
        crossings[crossing.crossing_id] = requested or must_arm
        if must_arm and not requested:
            overrides.append(
                VitalOverride(
                    "crossing_armed",
                    f"XING_{crossing.crossing_id}",
                    "a train is on the approach; gates forced down",
                )
            )

    # --- track circuits, one per block that has a suggestion -----------
    circuits: dict[str, TrackCircuit] = {}
    closed_hit: list[str] = []
    fault_hit: list[str] = []
    limit_hit: list[str] = []
    moving_hit: list[str] = []
    no_authority_hit: list[str] = []
    yellow_hit: list[str] = []
    yellow_blocks = {
        signal.block_id for signal in config.signals
        if aspects[signal.signal_id] == "YELLOW"
    }
    for block in blocks:
        block_id = block.block_id
        suggestion = suggestions.get(block_id)
        if suggestion is None:
            continue

        speed = max(0, int(suggestion.speed_mps))
        authority = max(0, int(suggestion.authority_blocks))

        # The program decides per block whether to pass the suggestion
        # on. A block it does not address withholds it: fail safe.
        if not values.get(f"AUTH_{block_id}", False):
            circuits[block_id] = TrackCircuit(0, 0)
            continue

        if closed.get(block_id, False):
            closed_hit.append(block_id)
            circuits[block_id] = TrackCircuit(0, 0)
            continue
        if block_id in fault_blocks:
            fault_hit.append(block_id)
            circuits[block_id] = TrackCircuit(0, 0)
            continue

        limit = (
            speed_limit_override_mps
            if speed_limit_override_mps is not None
            else block.whole_speed_limit_mps
        )
        if speed > limit:
            limit_hit.append(block_id)
            speed = limit

        if block_id in yellow_blocks and speed > 0:
            yellow_hit.append(block_id)
            speed //= 2

        if block_id in moving_blocks and speed > 0:
            moving_hit.append(block_id)
            speed = 0

        # Zero authority means the train must stop, so it gets no speed.
        if authority == 0 and speed > 0:
            no_authority_hit.append(block_id)
            speed = 0

        circuits[block_id] = TrackCircuit(speed, authority)

    if yellow_hit:
        overrides.append(VitalOverride(
            "aspect_speed_cap", "TRACK_CIRCUIT",
            f"Yellow signal; speed halved (rounded down) for block(s) "
            f"{_blocks_text(yellow_hit)}",
        ))
    if closed_hit:
        overrides.append(
            VitalOverride(
                "closed_block",
                "TRACK_CIRCUIT",
                f"block(s) {_blocks_text(closed_hit)} closed by the CTC "
                "Office; speed and authority zeroed",
            )
        )
    if fault_hit:
        overrides.append(
            VitalOverride(
                "switch_fault",
                "TRACK_CIRCUIT",
                f"block(s) {_blocks_text(fault_hit)} hold a faulted "
                "switch; speed and authority zeroed",
            )
        )
    if limit_hit:
        overrides.append(
            VitalOverride(
                "speed_limit",
                "TRACK_CIRCUIT",
                f"block(s) {_blocks_text(limit_hit)} were suggested a "
                "speed above the posted limit; clamped",
            )
        )
    if moving_hit:
        overrides.append(
            VitalOverride(
                "switch_moving",
                "TRACK_CIRCUIT",
                f"block(s) {_blocks_text(moving_hit)} hold a switch that "
                "is mid-throw; speed zeroed",
            )
        )
    if no_authority_hit:
        overrides.append(
            VitalOverride(
                "no_authority",
                "TRACK_CIRCUIT",
                f"block(s) {_blocks_text(no_authority_hit)} have no "
                "authority; speed zeroed",
            )
        )

    return ControllerOutputs(
        track_circuits=circuits,
        switches=switches,
        aspects=aspects,
        crossings=crossings,
        overrides=tuple(overrides),
    )
