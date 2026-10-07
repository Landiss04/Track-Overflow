"""View model for the Track Controller window.

Pure functions from module snapshots to the plain lists and maps QML
binds to. They hold no Qt state, so they are tested directly.
"""

from __future__ import annotations

from typing import Any

from track_ctrl_hw import display
from track_ctrl_hw.interface import (
    BlockKey,
    Override,
    TrackControllerSnapshot,
    WaysideSnapshot,
)
from track_ctrl_hw.schematic import layout

#: How the vital layer's rules read in the PLC details, in order.
VITAL_RULES: tuple[tuple[str, str], ...] = (
    ("Speed above the block's limit", "Clamped to the limit"),
    ("Speed or authority on a closed or failed block", "Held at zero"),
    ("Route over a switch that does not agree",
     "Authority zero, signal red"),
    ("Switch with its block or point occupied", "Never moves"),
    ("Signal lit with no aspect, or several", "Shown red"),
    ("Train at or beside a crossing", "Lights on, gates down"),
    ("No program, or channels A and B disagree",
     "All signals red, authority zero"),
)


def block_state(snapshot: WaysideSnapshot, key: BlockKey) -> tuple[str, str]:
    """A block's most severe state and its label.

    Returns:
        ``(state, label)``; state is ``failure``, ``closed``,
        ``occupied`` or ``free``.
    """
    failure = snapshot.failures.get(key)
    if failure is not None:
        return "failure", display.failure_name(failure)
    if key in snapshot.closed_blocks:
        return "closed", "Closed"
    if key in snapshot.occupied_blocks:
        return "occupied", "Occupied"
    return "free", "Clear"


_BADGES = {
    "failure": "fault",
    "closed": "warning",
    "occupied": "info",
    "free": "ok",
}


def block_rows(snapshot: WaysideSnapshot) -> list[dict[str, Any]]:
    """Rows of the block occupancy table."""
    rows = []
    for block in snapshot.territory.blocks:
        key = block.key
        state, label = block_state(snapshot, key)
        circuit = snapshot.track_circuits.get(key)
        rows.append({
            "section": key.section,
            "block": key.block_id,
            "length": display.feet(block.length_m),
            "limit": display.mph(block.speed_limit_mps),
            "state": state,
            "badge": _BADGES[state],
            "stateText": label,
            "circuit": (
                display.EM_DASH
                if circuit is None
                else f"{display.mph(circuit.speed_mps)} \u00b7 "
                f"{display.blocks(circuit.authority_blocks)}"
            ),
            "sending": circuit is not None,
        })
    return rows


def office_rows(snapshot: WaysideSnapshot) -> list[dict[str, Any]]:
    """Suggestions received from the CTC Office, in block order."""
    return [
        {
            "block": key.label,
            "speed": display.mph(suggestion.speed_mps),
            "authority": display.blocks(suggestion.authority_blocks),
        }
        for key in snapshot.territory.keys
        if (suggestion := snapshot.suggestions.get(key)) is not None
    ]


def _held(snapshot: WaysideSnapshot) -> bool:
    return any(override.target == "ALL" for override in snapshot.overrides)


def _route_order(end: str) -> tuple[bool, int]:
    # Block numbers in ascending order, then the yard.
    return (not end.isdigit(), int(end) if end.isdigit() else 0)


def _set_by(snapshot: WaysideSnapshot, target: str) -> str:
    if _held(snapshot):
        return "Held"
    if any(override.target == target for override in snapshot.overrides):
        return "Vital"
    return "PLC"


def switch_rows(
    snapshot: WaysideSnapshot, maintenance: bool
) -> list[dict[str, Any]]:
    """Rows of the switch table."""
    rows = []
    for state in snapshot.switches:
        switch = state.switch
        name = f"SW-{switch.switch_id}"
        ends = (
            switch.normal_end
            if state.commanded == "normal"
            else switch.reverse_end
        )
        joined = sorted((switch.point, ends), key=_route_order)
        route = "\u2013".join(joined)
        request = snapshot.switch_requests.get(switch.key)
        if maintenance:
            set_by = "CTC"
            if request is not None and request != state.commanded:
                set_by = "CTC \u00b7 held"
        elif any(o.target == name for o in snapshot.overrides):
            set_by = "PLC \u00b7 held"
        else:
            set_by = "PLC"
        if state.reported is None:
            agree_text, agree_badge = "No report", "idle"
        elif state.agreeing:
            agree_text, agree_badge = "Agreeing", "ok"
        else:
            agree_text, agree_badge = "Not agreeing", "fault"
        rows.append({
            "name": name,
            "commanded": f"{display.position_name(state.commanded)} "
            f"\u00b7 {route}",
            "reported": display.position_name(state.reported),
            "setBy": set_by,
            "agreeing": state.agreeing,
            "agreeText": agree_text,
            "agreeBadge": agree_badge,
        })
    return rows


def device_rows(snapshot: WaysideSnapshot) -> list[dict[str, Any]]:
    """Rows of the signals and crossings table."""
    rows = []
    for state in snapshot.switches:
        key = state.switch.key
        name = f"SIG-{key.block_id}"
        rows.append({
            "name": name,
            "location": key.label,
            "commanded": display.aspect_name(
                snapshot.signal_commands.get(key)
            ),
            "reported": display.aspect_name(snapshot.signal_reports.get(key)),
            "setBy": _set_by(snapshot, name),
        })
    for key in snapshot.territory.crossings:
        name = f"XING-{key.block_id}"
        rows.append({
            "name": name,
            "location": key.label,
            "commanded": display.crossing_name(
                snapshot.crossing_commands.get(key)
            ),
            "reported": display.crossing_name(
                snapshot.crossing_reports.get(key)
            ),
            "setBy": _set_by(snapshot, name),
        })
    return rows


def report_rows(snapshot: WaysideSnapshot) -> list[dict[str, Any]]:
    """The last report to the CTC Office, one row per block."""
    report = snapshot.report
    if report is None:
        return []
    rows = []
    for key, entry in report.blocks.items():
        rows.append({
            "key": f"{key.line} \u00b7 {key.section} \u00b7 {key.block_id}",
            "block": key.label,
            "occupied": "Occupied" if entry.occupied else "Clear",
            "switch": (
                display.EM_DASH
                if key not in {s.switch.key for s in snapshot.switches}
                else display.position_name(entry.switch_position)
            ),
            "crossing": (
                display.EM_DASH
                if key not in snapshot.territory.crossings
                else display.crossing_name(entry.crossing_active)
            ),
            "failure": display.failure_name(entry.failure),
        })
    return rows


def program_details(snapshot: WaysideSnapshot) -> dict[str, Any]:
    """Everything the PLC details window shows."""
    program = snapshot.program
    scan = snapshot.scan
    interventions = [
        f"{override.target}: {override.message}"
        for override in snapshot.overrides
        if override.rule not in ("holding",)
    ]
    loaded = (
        display.EM_DASH
        if program is None
        else "before the clock started"
        if program.loaded_at_s is None
        else display.clock(program.loaded_at_s)
    )
    return {
        "loaded": program is not None,
        "file": display.EM_DASH if program is None else program.file_name,
        "loadedAt": loaded,
        "checksum": display.EM_DASH if program is None else program.checksum,
        "booleans": (
            display.EM_DASH if program is None else str(program.boolean_count)
        ),
        "statements": (
            display.EM_DASH
            if program is None
            else str(program.statement_count)
        ),
        "warnings": [] if program is None else list(program.warnings),
        "scanInterval": (
            display.EM_DASH
            if scan.interval_s is None
            else f"{round(scan.interval_s * 1000)} ms"
        ),
        "lastScan": display.clock(scan.last_scan_s),
        "scanTime": (
            display.EM_DASH
            if scan.last_scan_s is None
            else f"{scan.last_duration_s * 1000:.2f} ms"
        ),
        "overruns": str(scan.overruns),
        "channels": "Agree" if scan.channels_agree else "Disagree",
        "vitalFault": scan.vital_fault or "None",
        "rules": [
            {"rule": rule, "action": action} for rule, action in VITAL_RULES
        ],
        "interventions": interventions,
        "running": program is not None and not scan.vital_fault,
    }


def diagram(
    snapshot: WaysideSnapshot, geometry: dict[str, Any]
) -> dict[str, Any]:
    """Schematic geometry with this scan's state laid over it."""
    keys = {key.block_id: key for key in snapshot.territory.keys}
    blocks = []
    for block in geometry["blocks"]:
        state, label = block_state(snapshot, keys[block["number"]])
        blocks.append(dict(block, state=state, stateText=label))
    by_number = {s.switch.switch_id: s for s in snapshot.switches}
    switches = []
    for switch in geometry["switches"]:
        state = by_number[switch["number"]]
        aspect = snapshot.signal_commands.get(state.switch.key)
        switches.append(dict(
            switch,
            position=state.commanded,
            agreeing=state.agreeing,
            aspect=aspect or "red",
            aspectLetter=display.aspect_letter(aspect),
        ))
    crossings = [
        dict(crossing, active=bool(
            snapshot.crossing_commands.get(keys[crossing["number"]])
        ))
        for crossing in geometry["crossings"]
    ]
    return dict(geometry, blocks=blocks, switches=switches,
                crossings=crossings)


def territory_summary(snapshot: WaysideSnapshot) -> str:
    """``Sections A\u2013E \u00b7 Blocks 1\u201320``."""
    keys = snapshot.territory.keys
    sections = []
    for key in keys:
        if key.section not in sections:
            sections.append(key.section)
    numbers = sorted(int(key.block_id) for key in keys)
    section_text = (
        f"Section {sections[0]}"
        if len(sections) == 1
        else f"Sections {sections[0]}\u2013{sections[-1]}"
    )
    return f"{section_text} \u00b7 Blocks {numbers[0]}\u2013{numbers[-1]}"


def wayside(
    snapshot: TrackControllerSnapshot, wayside_id: str
) -> WaysideSnapshot | None:
    """One wayside's snapshot, by ID."""
    for item in snapshot.waysides:
        if item.territory.wayside_id == wayside_id:
            return item
    return None


def geometry_for(snapshot: WaysideSnapshot) -> dict[str, Any]:
    """Schematic geometry for a wayside's territory."""
    return layout(snapshot.territory)


def interventions(overrides: tuple[Override, ...]) -> list[str]:
    """Vital interventions from one scan, as readable lines."""
    return [f"{o.target}: {o.message}" for o in overrides]
