"""The fail-safe supervisor applied to every PLC result.

The PLC program is written by a programmer and is therefore not trusted
to be safe. This module sits between the program's outputs and the
output card and can only ever make an output *more* restrictive: it
lowers speed, shortens authority, drops a signal to red and arms a
crossing. It never raises a speed, extends an authority or clears a
crossing the program left armed.

That one-way property is what "vital" means here, and it is the reason
a wrong program produces a stopped railway rather than a collision.

Every override is reported as a :class:`VitalOverride` so the Program
tab can show the programmer exactly which rule fired and why, rather
than silently disagreeing with the code on screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from track_ctrl.layout import Block, ControllerConfig

#: Aspect order, most restrictive first. A signal always falls back to
#: the first entry.
ASPECTS: tuple[str, ...] = ("RED", "ORANGE", "GREEN", "SUPER GREEN")

#: Speed ceiling each aspect permits, as a fraction of the posted limit.
_ASPECT_SPEED_FACTOR: dict[str, float] = {
    "RED": 0.0,
    "ORANGE": 0.5,
    "GREEN": 1.0,
    "SUPER GREEN": 1.0,
}


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

    commanded_speed_mph: float = 0.0
    commanded_authority_blocks: int = 0
    switches: dict[str, bool] = field(default_factory=dict)
    aspects: dict[str, str] = field(default_factory=dict)
    crossings: dict[str, bool] = field(default_factory=dict)
    overrides: tuple[VitalOverride, ...] = ()


def restrictive_outputs(
    config: ControllerConfig, reason: str
) -> ControllerOutputs:
    """Return the state the wayside falls back to when it cannot trust
    its own program: stop, no authority, all red, all crossings armed.

    This is the output of a failed compile, a failed scan, or a
    controller that has lost its inputs.
    """
    override = VitalOverride("fail_safe", "ALL", reason)
    return ControllerOutputs(
        commanded_speed_mph=0.0,
        commanded_authority_blocks=0,
        switches={switch.switch_id: False for switch in config.switches},
        aspects={signal.signal_id: "RED" for signal in config.signals},
        crossings={crossing.crossing_id: True for crossing in config.crossings},
        overrides=(override,),
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


def supervise(
    config: ControllerConfig,
    blocks: Sequence[Block],
    values: Mapping[str, bool],
    commanded_speed_mph: float,
    commanded_authority_blocks: int,
    occupancy: Mapping[str, bool],
    closed: Mapping[str, bool],
    manual_switches: Mapping[str, bool],
    maintenance: bool,
    current_switches: Mapping[str, bool],
) -> ControllerOutputs:
    """Clamp one scan's raw outputs down to something safe to drive.

    ``commanded_speed_mph`` and ``commanded_authority_blocks`` are what
    the program asked for, already decoded from its output bits.
    ``current_switches`` is where the switches are standing now, which
    a switch locked under a train is held at.
    """
    overrides: list[VitalOverride] = []
    by_id = {block.block_id: block for block in blocks}

    # --- switches ----------------------------------------------------
    switches: dict[str, bool] = {}
    manual_active = False
    for switch in config.switches:
        requested = values.get(switch.output_signal, False)
        if maintenance and switch.switch_id in manual_switches:
            switches[switch.switch_id] = manual_switches[switch.switch_id]
            manual_active = True
            overrides.append(
                VitalOverride(
                    "manual_switch",
                    switch.switch_id,
                    "held by maintenance override, program output ignored",
                )
            )
        else:
            switches[switch.switch_id] = requested

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
                    switch.switch_id,
                    f"block {switch.block_id} is occupied; "
                    "the switch is locked and will not move",
                )
            )
        switches[switch.switch_id] = held

    # --- signals -----------------------------------------------------
    aspects: dict[str, str] = {}
    for signal in config.signals:
        aspect, problem = _decode_aspect(values, signal.aspect_signals)
        block = by_id.get(signal.block_id)
        if problem is not None:
            overrides.append(
                VitalOverride("signal_aspect", signal.signal_id, problem)
            )
        # A signal protecting an occupied or closed block is red no
        # matter what the program computed.
        if block is not None and (
            occupancy.get(signal.block_id, False)
            or closed.get(signal.block_id, False)
        ):
            if aspect != "RED":
                overrides.append(
                    VitalOverride(
                        "signal_protects_block",
                        signal.signal_id,
                        f"block {signal.block_id} is occupied or closed; "
                        f"{aspect} dropped to RED",
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
                    crossing.crossing_id,
                    "a train is on the approach; gates forced down",
                )
            )

    # --- authority ---------------------------------------------------
    authority = max(0, commanded_authority_blocks)
    ordered = [block.block_id for block in blocks]

    # Authority may not reach into an occupied or closed block. The
    # count is truncated at the first one ahead.
    blocked_at: str | None = None
    for offset, block_id in enumerate(ordered[:authority]):
        if occupancy.get(block_id, False) or closed.get(block_id, False):
            blocked_at = block_id
            authority = offset
            break
    if blocked_at is not None:
        overrides.append(
            VitalOverride(
                "authority_truncated",
                "CMD_AUTH",
                f"{blocked_at} is occupied or closed; authority cut to "
                f"{authority} block(s)",
            )
        )

    if maintenance:
        if authority != 0:
            overrides.append(
                VitalOverride(
                    "maintenance_hold",
                    "CMD_AUTH",
                    "controller is in maintenance; authority held at 0",
                )
            )
        authority = 0
    elif manual_active:
        if authority != 0:
            overrides.append(
                VitalOverride(
                    "manual_switch_hold",
                    "CMD_AUTH",
                    "a switch is under manual control; authority held at 0",
                )
            )
        authority = 0

    # --- speed -------------------------------------------------------
    speed = max(0.0, commanded_speed_mph)

    # The posted limit of the slowest block inside the authority is the
    # ceiling; with no authority there is nothing to move over.
    covered = ordered[:authority] if authority else []
    if covered:
        limit = min(by_id[block_id].speed_limit_mph for block_id in covered)
        if speed > limit:
            overrides.append(
                VitalOverride(
                    "speed_limit",
                    "CMD_SPEED",
                    f"{speed:.0f} mph exceeds the {limit} mph posted limit; "
                    "clamped",
                )
            )
            speed = float(limit)

    # The most restrictive aspect the train will pass caps it further.
    if aspects and authority:
        worst = min(
            (aspect for aspect in aspects.values()),
            key=lambda aspect: _ASPECT_SPEED_FACTOR.get(aspect, 0.0),
        )
        factor = _ASPECT_SPEED_FACTOR.get(worst, 0.0)
        capped = speed * factor
        if capped < speed:
            overrides.append(
                VitalOverride(
                    "aspect_speed_cap",
                    "CMD_SPEED",
                    f"a {worst} aspect is displayed; "
                    f"{speed:.0f} mph capped to {capped:.0f} mph",
                )
            )
            speed = capped

    if authority == 0 and speed != 0.0:
        overrides.append(
            VitalOverride(
                "no_authority",
                "CMD_SPEED",
                "no authority is in force; commanded speed zeroed",
            )
        )
        speed = 0.0

    return ControllerOutputs(
        commanded_speed_mph=speed,
        commanded_authority_blocks=authority,
        switches=switches,
        aspects=aspects,
        crossings=crossings,
        overrides=tuple(overrides),
    )
