"""Observable state for the Train Model module.

Wraps one ``TrainModel`` and republishes its state as a flat snapshot the
views bind to. The test harness supplies the inputs and drives the clock;
this class steps the model and refreshes the snapshot after each tick.

Every value in the snapshot is in its backend unit, per D002; the views
convert for display. A few fields are display-only placeholders that the
Train Model does not produce (train ID, line, mode, clock, arrival).

Signal names, units and directions follow the Train Model interface
dictionary (v0.2). Deviations from the wireframes are recorded in
``TrainModel/README.md``.
"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Property, QObject, Signal, Slot

from train_model.interface import (
    FailureState,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
)
from train_model.model import TrainModel

#: The three failure modes injected by Murphy, in interface-dictionary
#: order (``Failure Status`` is ``bool[3]``).
FAILURE_MODES: tuple[str, ...] = (
    "engine_failure",
    "brake_failure",
    "signal_pickup_failure",
)

_FAILURE_LABELS: dict[str, str] = {
    "engine_failure": "Engine",
    "brake_failure": "Brake",
    "signal_pickup_failure": "Signal pickup",
}

# Shown where the model has not reported a block or an authority yet.
_NONE_SHOWN = "—"


class TrainModelState(QObject):
    """Holds everything the Train Model views display."""

    snapshotChanged = Signal()
    failuresChanged = Signal()

    def __init__(
        self,
        config: TrainConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config if config is not None else TrainConfig()
        self._model = TrainModel(self._config)
        self._failures: dict[str, bool] = dict.fromkeys(FAILURE_MODES, False)
        self._snapshot: dict[str, Any] = self._initial_snapshot()
        self._refresh(inputs=None)

    def _initial_snapshot(self) -> dict[str, Any]:
        # Display-only fields, and the harness pass-throughs the model
        # does not use. Everything else is filled in by _refresh.
        cfg = self._config
        return {
            "train_id": "T-114",
            "line": "Green Line",
            "mode": "Automatic",
            "clock": "19:00:05",
            "arrival": "14:19",
            "grade": 0.0,
            "elevation": 0.0,
            "next_station": _NONE_SHOWN,
            "platform_side": _NONE_SHOWN,
            "previous_block": _NONE_SHOWN,
            "current_block": _NONE_SHOWN,
            "capacity": cfg.capacity,
            "empty_mass": cfg.m_empty_kg,
            "crew": cfg.n_crew,
            "length": cfg.length_m,
            "width": cfg.width_m,
            "height": cfg.height_m,
            "power_limit": cfg.p_max_w,
            "power_consumption": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Driven by the test harness
    # ------------------------------------------------------------------ #

    def step(self, dt: float, inputs: TrainModelInputs) -> None:
        """Advance the model one tick and refresh the snapshot."""
        self._model.step(dt, inputs)
        self._refresh(inputs)

    def reset(self) -> None:
        """Replace the model with a fresh one and clear every failure."""
        self._model = TrainModel(self._config)
        self._failures = dict.fromkeys(FAILURE_MODES, False)
        self._snapshot = self._initial_snapshot()
        self._refresh(inputs=None)
        self.failuresChanged.emit()

    def update_many(self, updates: Mapping[str, Any]) -> None:
        """Apply a snapshot batch; notify QML once if it changed."""
        unknown_keys = updates.keys() - self._snapshot.keys()
        if unknown_keys:
            raise KeyError(f"unknown snapshot fields: {sorted(unknown_keys)}")
        if all(self._snapshot[key] == value for key, value in updates.items()):
            return
        self._snapshot.update(updates)
        self.snapshotChanged.emit()

    # ------------------------------------------------------------------ #
    # Read by the views
    # ------------------------------------------------------------------ #

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Every scalar the views read, refreshed once per tick."""
        return dict(self._snapshot)

    @Property("QVariantList", notify=snapshotChanged)
    def doors(self) -> list[dict[str, Any]]:
        """Door state as ``bool[2]``: left, right."""
        return [
            {"side": "Left", "open": self._snapshot["left_door"]},
            {"side": "Right", "open": self._snapshot["right_door"]},
        ]

    @Property("QVariantList", notify=failuresChanged)
    def failures(self) -> list[dict[str, Any]]:
        """The three Murphy failure flags, with display labels."""
        return [
            {
                "name": name,
                "label": _FAILURE_LABELS[name],
                "active": self._failures[name],
            }
            for name in FAILURE_MODES
        ]

    @Property(int, notify=failuresChanged)
    def activeFailureCount(self) -> int:
        """How many failure modes are currently set."""
        return sum(1 for active in self._failures.values() if active)

    # ------------------------------------------------------------------ #
    # Train Model UI actions
    # ------------------------------------------------------------------ #

    @Slot(str, bool)
    def setFailure(self, name: str, active: bool) -> None:
        """Set or clear one failure mode; it applies from the next tick."""
        if name not in self._failures:
            raise KeyError(f"unknown failure mode: {name}")
        if self._failures[name] == active:
            return
        self._failures[name] = active
        self._model.set_failures(
            FailureState(
                engine=self._failures["engine_failure"],
                signal_pickup=self._failures["signal_pickup_failure"],
                brake=self._failures["brake_failure"],
            )
        )
        self.failuresChanged.emit()

    @Slot(str, result=bool)
    def isFailed(self, name: str) -> bool:
        """Return whether one failure mode is set."""
        return self._failures.get(name, False)

    @Slot()
    def applyEmergencyBrake(self) -> None:
        """Pull the passenger emergency brake; it applies next tick."""
        self._model.pull_passenger_emergency_brake()
        self.update_many({"passenger_ebrake_pulled": True})

    @Slot()
    def releaseEmergencyBrake(self) -> None:
        """Do nothing: the model latches the pull until Reset module."""
        # OPEN(5.8): the design does not say who releases the brake.

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def _refresh(self, inputs: TrainModelInputs | None) -> None:
        # Republish the model's state. Before the first tick there are
        # no inputs, so only the model's own state is shown.
        snap = self._model.snapshot()
        outputs: TrainModelOutputs = snap.outputs
        ctl = outputs.controller
        trk = outputs.track

        block = trk.block_id or _NONE_SHOWN
        updates: dict[str, Any] = {
            "actual_speed": ctl.actual_speed_mps,
            "commanded_speed": ctl.commanded_speed_mps,
            "speed_limit": ctl.speed_limit_mps,
            "authority_block": ctl.authority_block_id or _NONE_SHOWN,
            "acceleration": snap.acceleration_mps2,
            "passengers": snap.n_passengers,
            "loaded_mass": snap.mass_kg,
            "cabin_temp": ctl.cabin_temp_c,
            "interior_light": ctl.interior_lights_on,
            "exterior_light": ctl.exterior_lights_on,
            "left_door": ctl.door_left_open,
            "right_door": ctl.door_right_open,
            "emergency_brake": ctl.emergency_brake_active,
            "service_brake": ctl.service_brake_active,
            "passenger_ebrake_pulled": snap.passenger_ebrake_pulled,
            "direction": (
                "Reverse" if ctl.actual_speed_mps < 0.0 else "Forward"
            ),
            "current_block": block,
            "position_offset": trk.offset_m,
        }
        if block != self._snapshot["current_block"]:
            updates["previous_block"] = self._snapshot["current_block"]
        # A beacon is only received near a station; keep the last one.
        if ctl.beacon is not None:
            updates["next_station"] = ctl.beacon.station_name
            updates["platform_side"] = ctl.beacon.platform_side
        if inputs is not None:
            # The model does not report power; show the command, capped
            # at P_max, and nothing while the engine has failed.
            power_w = min(max(inputs.controller.power_cmd_w, 0.0),
                          self._config.p_max_w)
            if self._failures["engine_failure"]:
                power_w = 0.0
            updates["power_consumption"] = power_w

        if any(self._snapshot.get(key) != value
               for key, value in updates.items()):
            self._snapshot.update(updates)
            self.snapshotChanged.emit()
