"""Qt-free Pi core adapters with an allowlist of window actions."""

from __future__ import annotations

import copy
import dataclasses
import sys
from pathlib import Path
from typing import Any

from .codec import pack

ROOT = Path(__file__).resolve().parents[2]
for folder in ("TrackCtrlHw", "Train-Ctrl_HW"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)


class TrackCore:
    """Braden's HwTrackController lives on the Pi."""

    def __init__(self) -> None:
        from track_ctrl_hw.controller import HwTrackController

        self.controller = HwTrackController()

    def step(self, request: dict[str, Any]) -> dict[str, Any]:
        from track_ctrl_hw.wire import inputs_from_wire, outputs_to_wire

        inputs = dict(request["inputs"], time_s=request["sim_time_s"])
        return outputs_to_wire(
            self.controller.step(request["dt"], inputs_from_wire(inputs))
        )

    def action(self, name: str, args: dict[str, Any]) -> Any:
        from track_ctrl_hw.wire import territory_from_wire

        if name == "load_territory":
            return self.controller.load_territory(
                territory_from_wire(args["territory"])
            )
        if name == "load_program":
            return pack(
                self.controller.load_program(
                    args["wayside_id"], args["source"], args["file_name"]
                )
            )
        if name == "reset":
            self.controller.reset()
            return None
        raise ValueError(f"unknown Track action {name!r}")

    def view(self) -> dict[str, Any]:
        return {"snapshot": pack(self.controller.snapshot())}


class TrainCore:
    """One Qt-free fleet for Red; an accepted STEP is transactional."""

    STATE_FIELDS = frozenset(
        {
            "manual",
            "service_request",
            "target_temp_c",
            "announcement",
            "kp",
            "ki",
            "authority_target",
        }
    )
    CORE_FIELDS = frozenset({"armed", "integral"})
    METHODS = frozenset(
        {
            "set_target_mps",
            "engage_emergency",
            "release_emergency",
            "command_door",
            "driver_door",
            "command_lights",
            "repeat_announcement",
            "clear_failure",
        }
    )

    def __init__(self) -> None:
        from train_ctrl.constants import ECHO_TICKS
        from train_ctrl.fleet import TrainControllerFleet

        self.fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.engineer_gains: tuple[float, float] | None = None

    def step(self, request: dict[str, Any]) -> dict[str, Any]:
        trains = request["inputs"].get("trains")
        if not isinstance(trains, dict) or not all(
            isinstance(entry, dict) and isinstance(entry.get("inputs"), dict)
            for entry in trains.values()
        ):
            raise ValueError(
                "inputs must hold a trains object, with inputs per train"
            )
        # Roster updates must roll back too when any input is invalid.
        candidate = copy.deepcopy(self.fleet)
        for train_id in candidate.ids():
            if train_id not in trains:
                candidate.remove(train_id)
        for train_id, entry in trains.items():
            if train_id not in candidate:
                core = candidate.add(train_id, str(entry.get("line", "")))
                if self.engineer_gains is not None:
                    core.state.kp, core.state.ki = self.engineer_gains
                    core.armed = True
        commands = candidate.step_all(
            request["dt"],
            {key: entry["inputs"] for key, entry in trains.items()},
            request["sim_time_s"],
        )
        self.fleet = candidate
        return {
            "trains": {
                key: dataclasses.asdict(value)
                for key, value in commands.items()
            }
        }

    def action(self, name: str, args: dict[str, Any]) -> Any:
        if name == "test_engineer_gains":
            self.engineer_gains = (
                max(0.0, float(args["kp"])),
                max(0.0, float(args["ki"])),
            )
            return None
        if name == "recovery_gains":
            # A reboot while paused must wait for the engineer (K11/D024).
            for core in self.fleet:
                core.armed = False
            for key, gains in args.get("trains", {}).items():
                if key in self.fleet:
                    core = self.fleet.get(key)
                    core.state.kp, core.state.ki = gains
                    core.armed = True
            return None
        core = self.fleet.get(args["train_id"])
        if name == "set_state" and args["field"] in self.STATE_FIELDS:
            setattr(core.state, args["field"], args["value"])
            return None
        if name == "set_core" and args["field"] in self.CORE_FIELDS:
            setattr(core, args["field"], args["value"])
            return None
        if name == "core_method" and args["method"] in self.METHODS:
            return getattr(core, args["method"])(*args.get("values", []))
        raise ValueError(f"unknown Train action {name!r}")

    def view(self) -> dict[str, Any]:
        return {
            "trains": {
                core.state.train_id: {
                    "state": dataclasses.asdict(core.state),
                    "core": {
                        key: value
                        for key, value in vars(core).items()
                        if key != "state"
                        and isinstance(
                            value, (str, bool, int, float, type(None))
                        )
                    },
                }
                for core in self.fleet
            }
        }


def make_core(module: str) -> TrackCore | TrainCore:
    """Create only the requested module's core."""
    if module == "track-controller-hw":
        return TrackCore()
    if module == "train-controller-hw":
        return TrainCore()
    raise ValueError(f"unknown hardware module {module!r}")
