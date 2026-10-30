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
- a yellow signal halves its block's speed (``OUT_HALF_n = 1``);
- a suggested speed over the block's posted limit is clamped to it.

A user program never sees a speed or an authority: it decides only
``AUTH_n``. The suggested speed does enter the vital code, as bits the
program cannot declare (``SUGSPD_n_b``, the whole m/s speed, least
significant bit first), and the clamped speed leaves it as
``OUT_SPD_n_b``. The clamp is a comparison against the block's posted
limit, written out in Boolean code for each block, so a program can
only pass the suggestion or stop. The OS then passes that speed (halved
where ``OUT_HALF_n`` is set) and the CTC Office's authority, or 0.
Zero speed for zero authority is still the CTC Office's (truth
``suggested-speed-stops-within-authority``).

This module also turns a scan into the overrides the Program tab shows,
by comparing the program's outputs with the vital code's. That is for
display only and decides nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from track_ctrl.layout import Block, ControllerConfig

#: Aspect order, most restrictive first.
ASPECTS: tuple[str, ...] = ("RED", "YELLOW", "GREEN", "SUPER GREEN")

#: Prefix of the final outputs the vital code writes.
OUT = "OUT_"

#: Blocks named in one override message before the rest are counted.
_NAMED_BLOCKS = 6


def speed_width(blocks: Sequence[Block]) -> int:
    """How many bits carry a speed: enough for the fastest posted limit.

    A suggestion above what the bits can hold is saturated to it before
    it is decoded, which is still at or over every limit, so the clamp
    gives the same answer as it would on the full number.
    """
    return max(1, max(b.whole_speed_limit_mps for b in blocks).bit_length())


def speed_bit(block_id: str, bit: int) -> str:
    """Name of one bit of a block's suggested speed, as the vital code
    reads it."""
    return f"SUGSPD_{block_id}_{bit}"


def _greater_than(n: str, limit: int, width: int) -> str:
    """PLC expression: the suggested speed of block ``n`` exceeds ``limit``.

    Compares from the most significant bit down: the speed is greater at
    the first bit where it is 1 and the limit is 0, provided every bit
    above it matches.
    """
    terms: list[str] = []
    for i in range(width - 1, -1, -1):
        if (limit >> i) & 1:
            continue
        factors = [speed_bit(n, i)]
        for j in range(width - 1, i, -1):
            bit = speed_bit(n, j)
            factors.append(bit if (limit >> j) & 1 else f"NOT {bit}")
        terms.append("(" + " AND ".join(factors) + ")")
    return " OR ".join(terms) if terms else "0"


@dataclass(frozen=True)
class VitalOverride:
    """One place the vital code changed the program's output."""

    rule: str
    signal: str
    message: str

    def format(self) -> str:
        """Render as a single terminal line."""
        return f"VITAL  {self.rule}  {self.signal}: {self.message}"


# --- the vital code -----------------------------------------------------

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
    width = speed_width(blocks)
    for n in numbers:
        lines.append("VAR_IN   " + " ".join(
            speed_bit(n, b) for b in range(width)))
        lines.append("VAR_OUT  " + " ".join(
            f"{OUT}SPD_{n}_{b}" for b in range(width)))
    for s in config.switches:
        lines.append(
            f"VAR_IN   SW_{s} SWREV_{s} CTCCMD_{s} CTCREV_{s} "
            f"HAND_{s} HANDREV_{s}"
        )
        lines.append(f"VAR_OUT  {OUT}SW_{s}")
    for s in config.signals:
        aspects = config.aspect_outputs(s)
        lines.append("VAR_IN   " + " ".join(aspects))
        lines.append("VAR_OUT  " + " ".join(OUT + name for name in aspects))
        lines.append(f"VAR_OUT  {OUT}HALF_{s}")
    for c in config.crossings:
        lines.append(f"VAR_IN   {config.crossing_output(c)}")
        lines.append(f"VAR_OUT  {OUT}{config.crossing_output(c)}")

    # A switch, its signal and a crossing are each named by the block
    # they stand on, so an id is also that block.
    moving: dict[str, str] = {}
    for s in config.switches:
        b = s
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

    for s in config.signals:
        b = s
        r, y, g, sg = config.aspect_outputs(s)
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

    for c in config.crossings:
        near = config.crossing_approach(c)
        out = config.crossing_output(c)
        lines += [
            "",
            f"// Crossing {c}: armed while a train is on its approach.",
            f"{OUT}{out} := {out} OR "
            + _any([f"OCC_{n}" for n in near]),
        ]

    lines += ["", "// Authority: none into a closed block or a moving switch."]
    for n in numbers:
        body = f"AUTH_{n} AND NOT CLOSED_{n}"
        if n in moving:
            body += f" AND NOT {moving[n]}"
        lines.append(f"{OUT}AUTH_{n} := {body}")

    lines += ["", "// Speed: the suggestion, clamped to the block's posted limit."]
    for block in blocks:
        n, limit = block.block_id, block.whole_speed_limit_mps
        lines.append(f"V_GT_{n} := {_greater_than(n, limit, width)}")
        for k in range(width):
            bit = speed_bit(n, k)
            if (limit >> k) & 1:
                lines.append(f"{OUT}SPD_{n}_{k} := V_GT_{n} OR {bit}")
            else:
                lines.append(f"{OUT}SPD_{n}_{k} := NOT V_GT_{n} AND {bit}")
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

    for s in config.switches:
        b = s
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

    for s in config.signals:
        b = s
        aspects = config.aspect_outputs(s)
        if not on(f"V_ONE_{s}"):
            lit = [a for a, name in zip(ASPECTS, aspects) if on(name)]
            found.append(VitalOverride(
                "signal_aspect", f"SIG_{s}",
                "no aspect lit; signal would be dark" if not lit
                else f"{len(lit)} aspects lit at once ({', '.join(lit)})"))
        elif not on(f"V_OK_{s}") and not on(aspects[0]):
            found.append(VitalOverride(
                "signal_protects_block", f"SIG_{s}",
                f"block {b} is occupied or closed; dropped to RED"))

    for c in config.crossings:
        out = config.crossing_output(c)
        if on(f"{OUT}{out}") and not on(out):
            found.append(VitalOverride(
                "crossing_armed", f"XING_{c}",
                "a train is on the approach; gates forced down"))

    moving_blocks = {s for s in config.switches if on(f"V_MOV_{s}")}
    for block in blocks:
        n = block.block_id
        if n not in suggested:
            continue
        if on(f"AUTH_{n}") and not on(f"{OUT}AUTH_{n}"):
            rule = "closed_block" if on(f"CLOSED_{n}") else "switch_moving"
            if rule == "switch_moving" and n not in moving_blocks:
                continue
            by_rule.setdefault(rule, []).append(n)
        if on(f"{OUT}AUTH_{n}") and on(f"V_GT_{n}"):
            by_rule.setdefault("speed_clamped", []).append(n)
        if on(f"{OUT}AUTH_{n}") and on(f"{OUT}HALF_{n}"):
            by_rule.setdefault("aspect_speed_cap", []).append(n)

    text = {
        "closed_block": "closed by the CTC Office; speed and authority "
                        "zeroed",
        "switch_moving": "hold a switch that is not where it was "
                         "commanded; speed and authority zeroed",
        "aspect_speed_cap": "show yellow; speed halved (rounded down)",
        "speed_clamped": "suggested over the posted limit; speed clamped "
                         "to it",
    }
    for rule, names in by_rule.items():
        found.append(VitalOverride(
            rule, "TRACK_CIRCUIT",
            f"block(s) {_blocks_text(names)} {text[rule]}"))
    return tuple(found)
