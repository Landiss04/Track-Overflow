"""Pure edges for the HW Track Controller's own JSON boundary.

The SW mapping owns the common signal semantics; these functions adapt
its representation to the distinct HW codec without importing Qt or a
module implementation. Time is the harness STEP's simulation time.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from common.harness import wayside_edges as sw
from common.harness.track_devices import TrackDevices
from common.harness.track_edges import BlockNames


def ctc_to_track_controller(
    outputs: Mapping[str, Any], line: str,
) -> dict[str, Any]:
    """Translate one line's CTC suggestions and dispatcher commands."""
    mapped = sw.ctc_to_track_controller(outputs, line)
    return {
        "closed_blocks": mapped["closed_blocks"],
        "suggestions": [
            {**entry["block"], **entry["value"]}
            for entry in mapped["suggestions"]
        ],
        "switch_commands": [
            {"line": entry["block"]["line"],
             "switch_id": entry["block"]["block_id"],
             "position": entry["value"]}
            for entry in mapped["switch_commands"]
        ],
    }


def track_model_to_track_controller(
    outputs: Mapping[str, Any], line: str, names: BlockNames,
    devices: TrackDevices,
) -> dict[str, Any]:
    """Include the section in every HW Track Model block key."""
    mapped = sw.track_model_to_track_controller(outputs, line, names, devices)

    def key(block: Mapping[str, Any]) -> dict[str, str]:
        return {
            **block,
            "section": names.section(block["line"], block["block_id"]),
        }
    fields = {"switch_positions": "position", "crossings_active": "active",
              "signal_aspects": "aspect"}
    result: dict[str, Any] = {
        "occupied_blocks": [key(block) for block in mapped["occupied_blocks"]],
        # Every block reported, so HW reads a missing one as occupied
        # (INPUT-1).
        "reported_blocks": [
            key({"line": line, "block_id": number})
            for number, _ in sw._on_line(
                outputs["controller"]["block_occupancy"], line, names
            )
        ],
    }
    for field, value_name in fields.items():
        result[field] = [
            {"block": key(entry["block"]), value_name: entry["value"]}
            for entry in mapped[field]
        ]
    return result


def _sw_outputs(outputs: Mapping[str, Any]) -> dict[str, Any]:
    fields = {"track_circuits": None, "switch_commands": "position",
              "crossing_commands": "active", "signal_commands": "aspect"}
    model = {}
    for field, value_name in fields.items():
        model[field] = [
            {"block": entry["block"], "value": (
                {"speed_mps": entry["speed_mps"],
                 "authority_blocks": entry["authority_blocks"]}
                if value_name is None else entry[value_name]
            )}
            for entry in outputs["track_model"][field]
        ]
    return {"track_model": model, "ctc_reports": [
        {**report, "blocks": [
            {"block": entry["block"], "value": {
                name: value for name, value in entry.items() if name != "block"
            }} for entry in report["blocks"]
        ]} for report in outputs["ctc_reports"]
    ]}


def track_controller_to_track_model(
    outputs: Mapping[str, Any], names: BlockNames, devices: TrackDevices,
) -> dict[str, Any]:
    """Translate encoded HW outputs into the Track Model's commands."""
    return sw.track_controller_to_track_model(
        _sw_outputs(outputs), names, devices
    )


def track_controller_to_ctc(outputs: Mapping[str, Any]) -> dict[str, Any]:
    """Translate HW reports, preserving line, readiness and reason."""
    return sw.track_controller_to_ctc(_sw_outputs(outputs))
