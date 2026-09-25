"""Observable state for the Train Model module.

Values are placeholders. No physics is implemented: the class exists so the
views bind to a single source of truth and so the simulation can be dropped
in behind these properties without touching QML.

Signal names, units and directions follow the Train Model interface
dictionary (v0.2). Deviations from the wireframes are recorded in
``TrainModel/README.md``.
"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Property, QObject, Signal, Slot

#: The three failure modes injected by Murphy, in interface-dictionary order
#: (``Failure Status`` is ``bool[3]``).
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


class TrainModelState(QObject):
    """Holds everything the Train Model views display."""

    snapshotChanged = Signal()
    failuresChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._snapshot: dict[str, Any] = {
            "train_id": "T-114",
            "line": "Green Line",
            "mode": "Automatic",
            "clock": "19:00:05",
            # Speed and authority. Track Signal arrives from the Track Model.
            "actual_speed": 14.5,
            "commanded_speed": 16.0,
            "speed_limit": 18.0,
            "authority_block": "GREEN M",
            "authority_distance": 410.0,
            "acceleration": 0.12,
            "grade": 0.7,
            "elevation": 0.0,
            # Cabin and load.
            "passengers": 84,
            "capacity": 148,
            "loaded_mass": 51.4,
            "empty_mass": 37.1,
            "cabin_temp": 68,
            "crew": 2,
            "cars": 3,
            "length": 32.2,
            "width": 2.65,
            "height": 3.42,
            "power_consumption": 350.0,
            "power_limit": 480.0,
            # Light State is bool[2]: cabin and headlight. Commanded by the
            # Train Controller, displayed read-only here.
            "cabin_light": True,
            "headlight": True,
            # Position.
            "direction": "Forward",
            "previous_block": "GREEN H",
            "current_block": "GREEN I",
            "position_offset": 189.0,
            "next_station": "Dormont",
            "platform_side": "L",
            "left_door": False,
            "right_door": False,
            "arrival": "14:19",
            "emergency_brake": False,
        }
        self._failures: dict[str, bool] = {
            "engine_failure": False,
            "brake_failure": False,
            "signal_pickup_failure": True,
        }

    @Property("QVariantMap", notify=snapshotChanged)
    def snapshot(self) -> dict[str, Any]:
        """Every scalar the views read, refreshed as one block per tick."""
        return dict(self._snapshot)

    @Property("QVariantList", notify=snapshotChanged)
    def doors(self) -> list[dict[str, Any]]:
        """Door state as ``bool[2]``, left and right, per the dictionary."""
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

    @Slot(str, bool)
    def setFailure(self, name: str, active: bool) -> None:
        """Set or clear one failure mode."""
        if name not in self._failures:
            raise KeyError(f"unknown failure mode: {name}")
        if self._failures[name] == active:
            return
        self._failures[name] = active
        self.failuresChanged.emit()

    @Slot(str, result=bool)
    def isFailed(self, name: str) -> bool:
        """Return whether one failure mode is set."""
        return self._failures.get(name, False)

    @Slot()
    def applyEmergencyBrake(self) -> None:
        """Latch the passenger emergency brake."""
        self._set("emergency_brake", True)

    @Slot()
    def releaseEmergencyBrake(self) -> None:
        """Release the passenger emergency brake."""
        self._set("emergency_brake", False)

    @Slot(str, "QVariant")
    def update(self, key: str, value: Any) -> None:
        """Write one snapshot field. Used by the test harness."""
        if key not in self._snapshot:
            raise KeyError(f"unknown snapshot field: {key}")
        self._set(key, value)

    def update_many(self, updates: Mapping[str, Any]) -> None:
        """Apply a snapshot batch and notify QML once when it changes."""
        unknown_keys = updates.keys() - self._snapshot.keys()
        if unknown_keys:
            raise KeyError(f"unknown snapshot fields: {sorted(unknown_keys)}")
        if all(self._snapshot[key] == value for key, value in updates.items()):
            return
        self._snapshot.update(updates)
        self.snapshotChanged.emit()

    def _set(self, key: str, value: Any) -> None:
        if self._snapshot.get(key) == value:
            return
        self._snapshot[key] = value
        self.snapshotChanged.emit()
