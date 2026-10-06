"""Observable state for the Train Model module.

Wraps one ``TrainModel`` and republishes its state as a flat snapshot the
views bind to. Whoever drives the module (the test UI over its link
today, the central harness once integrated) calls :meth:`step`; this
class steps the model and refreshes the snapshot after each tick.

Every value in the snapshot is in its backend unit, per D002; the views
convert for display. Unavailable identity, line and arrival metadata is
shown as unknown. The simulation clock comes from the model's elapsed time.

Signal names, units and directions follow the Train Model interface
dictionary (v0.2). Deviations from the wireframes are recorded in
``TrainModel/README.md``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QObject,
    QTimer,
    Signal,
    Slot,
)

from train_model.interface import (
    FailureState,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
)
from train_model.model import TrainModel

#: The three failure modes injected by Murphy, in ``Failure Status``
#: (``bool[3]``) element order: engine, signal pickup, brake.
FAILURE_MODES: tuple[str, ...] = (
    "engine_failure",
    "signal_pickup_failure",
    "brake_failure",
)

_FAILURE_LABELS: dict[str, str] = {
    "engine_failure": "Engine",
    "brake_failure": "Brake",
    "signal_pickup_failure": "Signal pickup",
}

# Shown where the model has not reported a value yet.
_NONE_SHOWN = "—"

# The window reads "Paused" once no step has arrived for this long.
_IDLE_MS = 500


class TrainModelState(QObject):
    """Holds everything the Train Model views display."""

    snapshotChanged = Signal()
    failuresChanged = Signal()
    runningChanged = Signal()

    def __init__(
        self,
        config: TrainConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config if config is not None else TrainConfig()
        self._model = TrainModel(self._config)
        self._failures: dict[str, bool] = dict.fromkeys(FAILURE_MODES, False)
        # The last beacon's station and platform side, kept until the
        # train is at that station: a beacon is sent only near it.
        self._next_station: tuple[str, str] | None = None
        self._snapshot: dict[str, Any] = self._initial_snapshot()
        self._running = False
        self._idle: QTimer | None = None
        self._refresh()

    def _initial_snapshot(self) -> dict[str, Any]:
        # Unknown metadata and config; live values come from _refresh.
        cfg = self._config
        return {
            "train_id": _NONE_SHOWN,
            "line": _NONE_SHOWN,
            "clock": "00:00:00",
            "arrival": _NONE_SHOWN,
            "grade": 0.0,
            "elevation": 0.0,
            "announcement": "",
            "station": _NONE_SHOWN,
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
            "power_command": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Driven from outside the module
    # ------------------------------------------------------------------ #

    def step(
        self, dt: float, inputs: TrainModelInputs, *,
        override_passenger_brake: bool = False,
    ) -> TrainModelOutputs:
        """Validate before a test override; publish only the accepted step."""
        if override_passenger_brake:
            self._model.validate_inputs(dt, inputs)
            self._model.clear_passenger_brake_for_test()
        outputs = self._model.step(dt, inputs)
        self._refresh()
        self._mark_running()
        return outputs

    def outputs(self) -> TrainModelOutputs:
        """The module's current cross-module outputs."""
        return self._model.snapshot().outputs

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        """Whether steps are arriving, whoever is sending them."""
        return self._running

    def _mark_running(self) -> None:
        # Needs an event loop; without one the flag is never shown.
        if QCoreApplication.instance() is None:
            return
        if self._idle is None:
            self._idle = QTimer(self)
            self._idle.setSingleShot(True)
            self._idle.setInterval(_IDLE_MS)
            self._idle.timeout.connect(lambda: self._set_running(False))
        self._idle.start()
        self._set_running(True)

    def _set_running(self, running: bool) -> None:
        if running != self._running:
            self._running = running
            self.runningChanged.emit()

    def command_values(self) -> dict[str, Any]:
        """Current producer inputs; consumed boarding is not replayed."""
        inputs = self._model.snapshot().inputs
        if inputs is None:
            return {
                "power_command": 0.0, "service_brake_command": False,
                "emergency_brake_command": False,
                "interior_light_command": False,
                "exterior_light_command": False,
                "left_door_command": False, "right_door_command": False,
                "commanded_speed": 0.0, "authority": 0,
                "beacon_station": "", "beacon_platform_side": "L",
                "beacon_underground": False, "block": "", "grade": 0.0,
                "elevation": 0.0, "speed_limit": 0.0, "polarity": False,
                "station": "", "passengers_boarded": 0,
                "temperature_setpoint": 20.0, "announcement": "",
            }
        cmd, track = inputs.controller, inputs.track
        beacon = track.beacon
        return {
            "power_command": cmd.power_cmd_w,
            "service_brake_command": cmd.service_brake,
            "emergency_brake_command": cmd.emergency_brake,
            "interior_light_command": cmd.interior_lights,
            "exterior_light_command": cmd.exterior_lights,
            "left_door_command": cmd.door_left_open,
            "right_door_command": cmd.door_right_open,
            "commanded_speed": track.track_signal.commanded_speed_mps,
            "authority": track.track_signal.authority_blocks,
            "beacon_station": beacon.station_name if beacon else "",
            "beacon_platform_side": beacon.platform_side if beacon else "L",
            "beacon_underground": beacon.underground if beacon else False,
            "block": track.track_info.block_id,
            "grade": track.track_info.grade_deg,
            "elevation": track.track_info.elevation_m,
            "speed_limit": track.track_info.speed_limit_mps,
            "polarity": track.track_info.polarity,
            "station": track.track_info.station_name or "",
            "passengers_boarded": 0,
            "temperature_setpoint": cmd.temp_setpoint_c,
            "announcement": cmd.announcement,
        }

    def reset(self) -> None:
        """Replace the model with a fresh one and clear every failure."""
        self._model = TrainModel(self._config)
        self._failures = dict.fromkeys(FAILURE_MODES, False)
        self._next_station = None
        self._snapshot = self._initial_snapshot()
        self._refresh()
        self.failuresChanged.emit()

    # ------------------------------------------------------------------ #
    # Read by the views
    # ------------------------------------------------------------------ #

    @Property("QVariantMap", notify=snapshotChanged)  # type: ignore[arg-type]
    def snapshot(self) -> dict[str, Any]:
        """Every scalar the views read, refreshed on model state changes."""
        return dict(self._snapshot)

    @Property("QVariantList", notify=snapshotChanged)  # type: ignore[arg-type]
    def doors(self) -> list[dict[str, Any]]:
        """Door state as ``bool[2]``: left, right."""
        return [
            {"side": "Left", "open": self._snapshot["left_door"]},
            {"side": "Right", "open": self._snapshot["right_door"]},
        ]

    @Property("QVariantList", notify=failuresChanged)  # type: ignore[arg-type]
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
        """Report faults immediately; their force acts on the next tick."""
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
        self._refresh()
        self.failuresChanged.emit()

    @Slot(str, result=bool)
    def isFailed(self, name: str) -> bool:
        """Return whether one failure mode is set."""
        return self._failures.get(name, False)

    @Slot()
    def applyEmergencyBrake(self) -> None:
        """Report the passenger pull now; apply its force next tick."""
        self._model.pull_passenger_emergency_brake()
        self._refresh()

    @Slot()
    def releaseEmergencyBrake(self) -> None:
        """Do nothing: normal UI release policy is still undecided."""

    def clear_passenger_brake_for_test(self) -> None:
        """Clear the passenger latch for an explicit harness override."""
        self._model.clear_passenger_brake_for_test()
        self._refresh()

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        # Republish the model's state. Before the first tick there are
        # no inputs, so only the model's own state is shown.
        snap = self._model.snapshot()
        inputs = snap.inputs
        outputs: TrainModelOutputs = snap.outputs
        ctl = outputs.controller
        trk = outputs.track

        block = trk.block_id or _NONE_SHOWN
        updates: dict[str, Any] = {
            "clock": (
                f"{int(snap.elapsed_s + 1e-9) // 3600:02d}:"
                f"{int(snap.elapsed_s + 1e-9) // 60 % 60:02d}:"
                f"{int(snap.elapsed_s + 1e-9) % 60:02d}"
            ),
            "actual_speed": ctl.actual_speed_mps,
            "commanded_speed": ctl.commanded_speed_mps,
            "speed_limit": ctl.speed_limit_mps,
            "authority": ctl.authority_blocks,
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
            "beacon_station": ctl.beacon.station_name if ctl.beacon else "",
            "beacon_platform_side": (
                ctl.beacon.platform_side if ctl.beacon else ""
            ),
            "beacon_underground": (
                ctl.beacon.underground if ctl.beacon else False
            ),
            "passenger_capacity": trk.passenger_capacity,
            "block_changed": trk.block_changed,
        }
        if block != self._snapshot["current_block"]:
            updates["previous_block"] = self._snapshot["current_block"]
        # The station in the current block, from Track Info.
        station = (
            inputs.track.track_info.station_name if inputs is not None
            else None
        ) or ""
        if ctl.beacon is not None:
            self._next_station = (
                ctl.beacon.station_name, ctl.beacon.platform_side
            )
        if (self._next_station is not None
                and station == self._next_station[0]):
            # Arrived: the station is now the current one.
            self._next_station = None
        updates["station"] = station or _NONE_SHOWN
        next_name, side = self._next_station or (_NONE_SHOWN, _NONE_SHOWN)
        updates["next_station"] = next_name
        updates["platform_side"] = side
        if inputs is not None:
            updates["announcement"] = inputs.controller.announcement
            updates["grade"] = inputs.track.track_info.grade_deg
            updates["elevation"] = inputs.track.track_info.elevation_m
            # The model does not report power; show the command, capped
            # at P_max, and nothing while the engine has failed.
            power_w = min(max(inputs.controller.power_cmd_w, 0.0),
                          self._config.p_max_w)
            if self._failures["engine_failure"]:
                power_w = 0.0
            updates["power_command"] = power_w

        if any(self._snapshot.get(key) != value
               for key, value in updates.items()):
            self._snapshot.update(updates)
            self.snapshotChanged.emit()
