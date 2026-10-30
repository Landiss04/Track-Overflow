"""The vital block: PLC code the wayside scans after every user program.

The user's program is written by a person and is not trusted to be
safe. The vital block is generated from the wayside's own territory, is
read-only, and runs on the same PLC engine and both channels. It reads
the wayside's inputs and the user program's outputs under their own
names (``AUTH_n``, ``CMD_n_b``, ``SW_s``, ``SIG_s_*``, ``XING_c``) and
writes the outputs that reach the track, each prefixed ``OUT_``.

Every rule can only make an output more restrictive, so a wrong program
gives a stopped railway, not a collision:

- no authority in a closed block, or while a block a train in it could
  move into is occupied, or while a switch on it is moving;
- no speed above the block's limit, and none without authority;
- the CTC Office's switch command wins over the program; a switch with
  a train on its point or listed block stays where it reports;
- a signal with no aspect or several lit, or whose point block is
  occupied, closed or under a moving switch, shows red;
- a crossing is active while a train is on it or beside it.

Speed limits and switch geometry come from the wayside database. The
vital block is regenerated whenever a database is loaded.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable, Mapping

from track_ctrl_hw.interface import Block, Switch, Territory

#: Prefix of the outputs the vital block writes and the wayside drives.
OUT = "OUT_"

_SPEED_BITS = 5
_YARD = "yard"
_ASPECTS = ("R", "Y", "G", "SG")
_LIMIT_TOLERANCE = 1e-9


def speed_limit_whole_mps(limit_mps: float) -> int:
    """The highest whole m/s that does not exceed a speed limit."""
    return int(math.floor(limit_mps + _LIMIT_TOLERANCE))


@lru_cache(maxsize=16)
def vital_source(territory: Territory) -> str:
    """Write the vital block for one wayside, from its territory."""
    writer = _Writer(territory)
    return writer.source()


def overrides(
    program: Mapping[str, bool], final: Mapping[str, bool]
) -> tuple[str, ...]:
    """Outputs the vital block changed this scan, as ``NAME 1->0``."""
    return tuple(
        f"{name} {int(program[name])}->{int(value)}"
        for name, value in sorted(final.items())
        if program[name] != value
    )


def _any(terms: Iterable[str]) -> str:
    terms = list(terms)
    return " OR ".join(terms) if terms else "0"


def _declare(keyword: str, names: list[str]) -> list[str]:
    return [
        f"{keyword} " + " ".join(names[at:at + 8])
        for at in range(0, len(names), 8)
    ]


class _Writer:
    def __init__(self, territory: Territory) -> None:
        self._territory = territory
        self._own = {block.key.block_id for block in territory.blocks}
        self._reads: set[str] = set()
        self._outputs: list[str] = []
        self._lines: list[str] = []

    def source(self) -> str:
        territory = self._territory
        moving: dict[str, list[str]] = {}
        for switch in territory.switches:
            self._switch(switch)
            name = f"V_MOV_{switch.switch_id}"
            for block in {switch.point, switch.switch_id}:
                moving.setdefault(block, []).append(name)
        for switch in territory.switches:
            self._signal(switch)
        for crossing in territory.crossings:
            self._crossing(crossing.block_id)
        points = {switch.point: switch for switch in territory.switches}
        self._emit("", "// Authority, then speed, block by block.")
        for block in territory.blocks:
            self._authority(block, points.get(block.key.block_id),
                            moving.get(block.key.block_id, []))
            self._speed(block)

        header = [
            f"// Vital block for {territory.line} wayside "
            f"{territory.wayside_id}. Generated; read-only.",
            "// Reads the program's outputs, writes OUT_*.",
        ]
        header += _declare("VAR_IN ", sorted(self._reads, key=_natural))
        header += _declare("VAR_OUT", self._outputs)
        return "\n".join(header + self._lines) + "\n"

    # -- rules ------------------------------------------------------

    def _switch(self, switch: Switch) -> None:
        s = switch.switch_id
        lock = _any(
            self._read(f"OCC_{b}")
            for b in sorted({switch.point, s}, key=int)
        )
        self._emit(
            "",
            f"// Switch {s}: the CTC Office's command, else the program;",
            "// a train on its point or listed block locks it.",
            f"V_LOCK_{s} := {lock}",
            f"V_REQ_{s} := ({self._read(f'CTCSW_{s}')} AND "
            f"{self._read(f'CTCREV_{s}')}) OR "
            f"(NOT CTCSW_{s} AND {self._read(f'SW_{s}')})",
            f"{self._out(f'SW_{s}')} := (V_LOCK_{s} AND "
            f"{self._read(f'SWREV_{s}')}) OR (NOT V_LOCK_{s} AND V_REQ_{s})",
            f"V_MOV_{s} := OUT_SW_{s} XOR SWREV_{s}",
        )

    def _signal(self, switch: Switch) -> None:
        s, p = switch.switch_id, switch.point
        lit = [self._read(f"SIG_{s}_{a}") for a in _ASPECTS]
        pairs = " OR ".join(
            f"({a} AND {b})"
            for i, a in enumerate(lit) for b in lit[i + 1:]
        )
        self._emit(
            "",
            f"// Signal {s}: exactly one aspect, red over a busy point {p}.",
            f"V_ONE_{s} := ({' XOR '.join(lit)}) AND NOT ({pairs})",
            f"V_OK_{s} := V_ONE_{s} AND NOT {self._read(f'OCC_{p}')} AND "
            f"NOT {self._read(f'CLOSED_{p}')} AND NOT V_MOV_{s}",
            f"{self._out(lit[0])} := NOT V_OK_{s} OR {lit[0]}",
        )
        for name in lit[1:]:
            self._emit(f"{self._out(name)} := V_OK_{s} AND {name}")

    def _crossing(self, c: str) -> None:
        near = sorted({c} | self._adjacent(c), key=int)
        self._emit(
            "",
            f"// Crossing {c}: active for a train on {', '.join(near)}.",
            f"{self._out(f'XING_{c}')} := {self._read(f'XING_{c}')} OR "
            + _any(self._read(f"OCC_{b}") for b in near),
        )

    def _authority(
        self, block: Block, point_of: Switch | None, moving: list[str]
    ) -> None:
        n = block.key.block_id
        near = []
        for m in block.next_blocks:
            if m == _YARD:
                continue
            occ = self._read(f"OCC_{m}")
            if point_of is not None and m == point_of.normal_end:
                near.append(f"(NOT SWREV_{point_of.switch_id} AND {occ})")
            elif point_of is not None and m == point_of.reverse_end:
                near.append(f"(SWREV_{point_of.switch_id} AND {occ})")
            else:
                near.append(occ)
        held = [self._read(f"CLOSED_{n}")]
        if near:
            held.append(f"({self._read(f'OCC_{n}')} AND ({_any(near)}))")
        held.extend(moving)
        self._emit(
            f"{self._out(f'AUTH_{n}')} := {self._read(f'AUTH_{n}')} AND "
            f"NOT ({' OR '.join(held)})"
        )

    def _speed(self, block: Block) -> None:
        n = block.key.block_id
        limit = min(speed_limit_whole_mps(block.speed_limit_mps),
                    (1 << _SPEED_BITS) - 1)
        bits = [self._read(f"CMD_{n}_{b}") for b in range(_SPEED_BITS)]
        # Above the limit when a 1 sits where the limit has a 0 and every
        # higher 1 of the limit is matched.
        terms = []
        for b in range(_SPEED_BITS - 1, -1, -1):
            if limit >> b & 1:
                continue
            higher = [bits[h] for h in range(b + 1, _SPEED_BITS)
                      if limit >> h & 1]
            terms.append(" AND ".join(higher + [bits[b]]))
        over = _any(f"({t})" if " AND " in t else t for t in terms)
        self._emit(f"V_OVER_{n} := {over}  // limit {limit} m/s")
        for b, name in enumerate(bits):
            out = self._out(name)
            if limit >> b & 1:
                self._emit(f"{out} := OUT_AUTH_{n} AND (V_OVER_{n} OR {name})")
            else:
                self._emit(
                    f"{out} := OUT_AUTH_{n} AND NOT V_OVER_{n} AND {name}"
                )

    # -- helpers ------------------------------------------------------

    def _adjacent(self, number: str) -> set[str]:
        # Both directions: a one-way block lists only where trains go.
        found = set()
        for block in self._territory.blocks:
            if block.key.block_id == number:
                found.update(block.next_blocks)
            elif number in block.next_blocks:
                found.add(block.key.block_id)
        found.discard(_YARD)
        return found

    def _read(self, name: str) -> str:
        self._reads.add(name)
        return name

    def _out(self, name: str) -> str:
        self._outputs.append(OUT + name)
        return OUT + name

    def _emit(self, *lines: str) -> None:
        self._lines.extend(lines)


def _natural(name: str) -> tuple[str, int, str]:
    prefix, _, rest = name.partition("_")
    number, _, tail = rest.partition("_")
    return (prefix, int(number) if number.isdigit() else -1, tail)
