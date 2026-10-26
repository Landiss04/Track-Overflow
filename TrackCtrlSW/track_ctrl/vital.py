"""The vital code attached to the end of every PLC program.

The PLC program is written by a programmer and is therefore not trusted
to be safe. Every decision the wayside makes is PLC code, so the vital
supervision is PLC code too: generated for each wayside from its own
territory and attached to the end of whatever program is committed. The
programmer's program runs first and writes its outputs (``AUTH_n``,
``SW_s``, ``SIG_s_*``, ``XING_c``). The vital code then reads those and
the inputs, and writes the final outputs, each prefixed ``OUT_``. Only
the final outputs leave the wayside.

The vital code can only make an output *more* restrictive: it drops an
``AUTH`` to 0, a signal to red and arms a crossing. It never does the
reverse, which is what "vital" means here, and why a wrong program
produces a stopped railway rather than a collision.

The rules, as PLC code:

- a block the CTC closed gets no authority (``OUT_AUTH_n = 0``);
- a block whose switch is not where it was commanded gets none;
- in maintenance mode a switch follows the CTC's command, else the
  programmer's hand-set position, else the program;
- a switch on an occupied block stays where it actually is;
- a signal showing no aspect or several, or on an occupied or closed
  block, is red;
- a train on a crossing's approach arms it;
- a yellow signal halves its block's speed (``OUT_HALF_n = 1``).

Speeds and authorities never enter the program: the OS passes a block's
suggestion, or half its speed, or 0, as the bits say. Keeping a speed
under the posted limit, and zero speed for zero authority, are the CTC
Office's (truth ``suggested-speed-under-block-limit``,
``suggested-speed-stops-within-authority``).

This module also turns a scan into the overrides the Program tab shows,
by comparing the program's outputs with the vital code's. That is for
display only and decides nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from track_ctrl.layout import Block, ControllerConfig

#: Aspect order, most restrictive first.
ASPECTS: tuple[str, ...] = ("RED", "YELLOW", "GREEN", "SUPER GREEN")

#: Prefix of the final outputs the vital code writes.
OUT = "OUT_"

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
    """One place the vital code changed the program's output."""

    rule: str
    signal: str
    message: str

    def format(self) -> str:
        """Render as a single terminal line."""
        return f"VITAL  {self.rule}  {self.signal}: {self.message}"


@dataclass
class ControllerOutputs:
    """What the OS encodes from the vital code's final outputs.

    Every mapping can be empty: a wayside running no program transmits
    nothing at all, because without a program it has nothing to send.
    """

    #: Only for blocks the CTC Office sent a suggestion for.
    track_circuits: dict[str, TrackCircuit] = field(default_factory=dict)
    switches: dict[str, bool] = field(default_factory=dict)
    aspects: dict[str, str] = field(default_factory=dict)
    crossings: dict[str, bool] = field(default_factory=dict)
    overrides: tuple[VitalOverride, ...] = ()


def idle_outputs(reason: str) -> ControllerOutputs:
    """A wayside that runs no program: it transmits nothing."""
    return ControllerOutputs(
        overrides=(VitalOverride("not_running", "ALL", reason),)
    )


# --- the vital code -----------------------------------------------------

def _owned(config: ControllerConfig, block_ids: Sequence[str]) -> list[str]:
    return [b for b in block_ids if config.owns(b)]


def _any(names: Sequence[str]) -> str:
    return " OR ".join(names) if names else "0"


def vital_source(config: ControllerConfig, blocks: Sequence[Block]) -> str:
    """Write the vital code for one wayside, from its own territory."""
    numbers = [block.block_id for block in blocks]
    lines = [
        f"// Vital code for {config.controller_id}: attached to the end of",
        "// every program. Reads the program's outputs, writes OUT_*.",
        "",
        "VAR_IN   " + " ".join(f"OCC_{n}" for n in numbers),
        "VAR_IN   " + " ".join(f"CLOSED_{n}" for n in numbers),
        "VAR_IN   " + " ".join(f"AUTH_{n}" for n in numbers),
        "VAR_OUT  " + " ".join(f"{OUT}AUTH_{n}" for n in numbers),
    ]
    for switch in config.switches:
        s = switch.switch_id
        lines.append(
            f"VAR_IN   SW_{s} SWREV_{s} CTCCMD_{s} CTCREV_{s} "
            f"HAND_{s} HANDREV_{s}"
        )
        lines.append(f"VAR_OUT  {OUT}SW_{s}")
    for signal in config.signals:
        lines.append("VAR_IN   " + " ".join(signal.aspect_signals))
        lines.append("VAR_OUT  " + " ".join(
            OUT + name for name in signal.aspect_signals))
        lines.append(f"VAR_OUT  {OUT}HALF_{signal.block_id}")
    for crossing in config.crossings:
        lines.append(f"VAR_IN   {crossing.output_signal}")
        lines.append(f"VAR_OUT  {OUT}{crossing.output_signal}")

    moving: dict[str, str] = {}
    for switch in config.switches:
        s, b = switch.switch_id, switch.block_id
        lines += [
            "",
            f"// Switch {s}: the CTC's command, else the hand-set position,",
            "// else the program. Under a train it stays where it is.",
            f"V_REQ_{s} := (CTCCMD_{s} AND CTCREV_{s}) OR "
            f"(NOT CTCCMD_{s} AND HAND_{s} AND HANDREV_{s}) OR "
            f"(NOT CTCCMD_{s} AND NOT HAND_{s} AND SW_{s})",
            f"{OUT}SW_{s} := (OCC_{b} AND SWREV_{s}) OR "
            f"(NOT OCC_{b} AND V_REQ_{s})",
            f"V_MOV_{s} := {OUT}SW_{s} XOR SWREV_{s}",
        ]
        moving[b] = f"V_MOV_{s}"

    for signal in config.signals:
        s, b = signal.signal_id, signal.block_id
        r, y, g, sg = signal.aspect_signals
        pairs = " OR ".join(
            f"({p} AND {q})"
            for i, p in enumerate((r, y, g, sg))
            for q in (r, y, g, sg)[i + 1:]
        )
        lines += [
            "",
            f"// Signal {s}: exactly one aspect, and red on a busy block.",
            f"V_ONE_{s} := ({r} XOR {y} XOR {g} XOR {sg}) AND NOT ({pairs})",
            f"V_OK_{s} := V_ONE_{s} AND NOT OCC_{b} AND NOT CLOSED_{b}",
            f"{OUT}{r} := NOT V_OK_{s} OR {r}",
            f"{OUT}{y} := V_OK_{s} AND {y}",
            f"{OUT}{g} := V_OK_{s} AND {g}",
            f"{OUT}{sg} := V_OK_{s} AND {sg}",
            f"{OUT}HALF_{b} := {OUT}{y}",
        ]

    for crossing in config.crossings:
        near = _owned(config, crossing.approach_block_ids)
        lines += [
            "",
            f"// Crossing {crossing.crossing_id}: armed while a train is "
            "on its approach.",
            f"{OUT}{crossing.output_signal} := {crossing.output_signal} OR "
            + _any([f"OCC_{n}" for n in near]),
        ]

    lines += ["", "// Authority: none into a closed block or a moving switch."]
    for n in numbers:
        body = f"AUTH_{n} AND NOT CLOSED_{n}"
        if n in moving:
            body += f" AND NOT {moving[n]}"
        lines.append(f"{OUT}AUTH_{n} := {body}")
    return "\n".join(lines) + "\n"


# --- what the vital code changed, for display ------------------------------

def _blocks_text(names: Sequence[str]) -> str:
    """Name a few and count the rest, for one-line messages."""
    shown = ", ".join(names[:_NAMED_BLOCKS])
    extra = len(names) - _NAMED_BLOCKS
    return f"{shown} and {extra} more" if extra > 0 else shown


def report_overrides(
    config: ControllerConfig,
    blocks: Sequence[Block],
    values: Mapping[str, bool],
    suggested: Sequence[str],
) -> tuple[VitalOverride, ...]:
    """Say where the vital code's outputs differ from the program's.

    ``values`` is everything the vital code's scan saw and wrote: the
    inputs, the program's outputs and the final ``OUT_`` values.
    ``suggested`` lists the blocks the CTC suggested something for.
    """
    def on(name: str) -> bool:
        return bool(values.get(name, False))

    found: list[VitalOverride] = []
    by_rule: dict[str, list[str]] = {}

    for switch in config.switches:
        s, b = switch.switch_id, switch.block_id
        if on(f"CTCCMD_{s}"):
            found.append(VitalOverride(
                "ctc_switch_command", f"SW_{s}",
                "maintenance mode: the CTC Office's command is obeyed, "
                "the program's output ignored"))
        elif on(f"HAND_{s}"):
            found.append(VitalOverride(
                "manual_switch", f"SW_{s}",
                "held by the programmer in maintenance mode, program "
                "output ignored"))
        if on(f"OCC_{b}") and on(f"V_REQ_{s}") != on(f"{OUT}SW_{s}"):
            found.append(VitalOverride(
                "switch_locked_under_train", f"SW_{s}",
                f"block {b} is occupied; the switch is locked and will "
                "not move"))

    for signal in config.signals:
        s, b = signal.signal_id, signal.block_id
        if not on(f"V_ONE_{s}"):
            lit = [a for a, name in zip(ASPECTS, signal.aspect_signals)
                   if on(name)]
            found.append(VitalOverride(
                "signal_aspect", f"SIG_{s}",
                "no aspect lit; signal would be dark" if not lit
                else f"{len(lit)} aspects lit at once ({', '.join(lit)})"))
        elif not on(f"V_OK_{s}") and not on(signal.aspect_signals[0]):
            found.append(VitalOverride(
                "signal_protects_block", f"SIG_{s}",
                f"block {b} is occupied or closed; dropped to RED"))

    for crossing in config.crossings:
        if on(f"{OUT}{crossing.output_signal}") and not on(
            crossing.output_signal
        ):
            found.append(VitalOverride(
                "crossing_armed", f"XING_{crossing.crossing_id}",
                "a train is on the approach; gates forced down"))

    moving_blocks = {
        switch.block_id for switch in config.switches
        if on(f"V_MOV_{switch.switch_id}")
    }
    for block in blocks:
        n = block.block_id
        if n not in suggested:
            continue
        if on(f"AUTH_{n}") and not on(f"{OUT}AUTH_{n}"):
            rule = "closed_block" if on(f"CLOSED_{n}") else "switch_moving"
            if rule == "switch_moving" and n not in moving_blocks:
                continue
            by_rule.setdefault(rule, []).append(n)
        if on(f"{OUT}AUTH_{n}") and on(f"{OUT}HALF_{n}"):
            by_rule.setdefault("aspect_speed_cap", []).append(n)

    text = {
        "closed_block": "closed by the CTC Office; speed and authority "
                        "zeroed",
        "switch_moving": "hold a switch that is not where it was "
                         "commanded; speed and authority zeroed",
        "aspect_speed_cap": "show yellow; speed halved (rounded down)",
    }
    for rule, names in by_rule.items():
        found.append(VitalOverride(
            rule, "TRACK_CIRCUIT",
            f"block(s) {_blocks_text(names)} {text[rule]}"))
    return tuple(found)
