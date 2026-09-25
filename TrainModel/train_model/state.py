"""Stub state for the Train Model main page (page 3a).

Holds every displayed value on the operational view as a ``pyqtProperty`` so
the QML layer binds to it. Values are seeded to exactly what the mockup shows
(``refrence-docs/main_page.png``); there is no physics or simulation here.

The three failure-mode rows and the passenger e-brake row are interactive:
their slots flip the stub state between its two designed labels. Everything
else is read-only display.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot


class TrainModelState(QObject):
    """Backs the page-3a view with seeded, bindable display values."""

    # -- Change signals -------------------------------------------------
    train_selector_changed = pyqtSignal()
    clock_changed = pyqtSignal()
    mode_label_changed = pyqtSignal()

    speed_auth_badge_changed = pyqtSignal()
    actual_speed_changed = pyqtSignal()
    commanded_display_changed = pyqtSignal()
    speed_limit_changed = pyqtSignal()
    authority_changed = pyqtSignal()
    distance_to_eoa_changed = pyqtSignal()
    acceleration_changed = pyqtSignal()
    grade_changed = pyqtSignal()

    cabin_badge_changed = pyqtSignal()
    passengers_changed = pyqtSignal()
    loaded_mass_changed = pyqtSignal()
    cabin_temp_changed = pyqtSignal()
    crew_changed = pyqtSignal()
    cars_changed = pyqtSignal()
    train_size_changed = pyqtSignal()
    empty_mass_changed = pyqtSignal()
    power_consumption_changed = pyqtSignal()
    power_fill_changed = pyqtSignal()
    interior_light_state_changed = pyqtSignal()
    exterior_light_state_changed = pyqtSignal()

    position_badge_changed = pyqtSignal()
    direction_of_travel_changed = pyqtSignal()
    current_block_changed = pyqtSignal()
    distance_into_block_changed = pyqtSignal()
    next_station_changed = pyqtSignal()

    brakes_badge_changed = pyqtSignal()
    passenger_ebrake_state_changed = pyqtSignal()

    failure_badge_changed = pyqtSignal()
    engine_failure_state_changed = pyqtSignal()
    brake_failure_state_changed = pyqtSignal()
    signal_pickup_state_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        # Top bar.
        self._train_selector = "T-114 · GREEN LINE"
        self._clock = "19:00:05"

        # Mode banner.
        self._mode_label = "AUTOMATIC — TRACK CONTROLLER IN COMMAND"

        # Speed & Authority. Tile values carry no unit; the QML readout
        # renders the unit per Style Guide §6.5 (muted, smaller than value).
        self._speed_auth_badge = "GREEN I · 14:12"
        self._actual_speed = "32"
        self._commanded_display = "35"
        self._speed_limit = "40"
        self._authority = "→ GREEN M"
        self._distance_to_eoa = "1,340 FT"
        self._acceleration = "+0.4 FT/S²"
        self._grade = "+1.2 %"

        # Cabin & Load.
        self._cabin_badge = "3 CARS"
        self._passengers = "84 / 148"
        self._loaded_mass = "56.7"
        self._cabin_temp = "68"
        self._crew = "2"
        self._cars = "3"
        self._train_size = "105.64 FT | 8.69 FT | 11.22 FT"
        self._empty_mass = "40.9 T"
        self._power_consumption = "350 kW / 480 kW"
        self._power_fill = 0.78
        # Lights are controller-driven; the model only displays their state.
        self._interior_light_state = "ON"
        self._exterior_light_state = "ON"

        # Position.
        self._position_badge = "GREEN LINE"
        self._direction_of_travel = "FORWARD · GREEN H → GREEN I"
        self._current_block = "GREEN I"
        self._distance_into_block = "620 FT"
        self._next_station = "[STATION] 14:19"

        # Brakes & Doors.
        self._brakes_badge = "E-BRAKE RELEASED · DOORS CLOSED"
        self._passenger_ebrake_state = "RELEASED"
        self._door_states = [
            {"car": "T-114-A", "side": "Left", "state": "Closed"},
            {"car": "T-114-A", "side": "Right", "state": "Closed"},
            {"car": "T-114-B", "side": "Left", "state": "Closed"},
            {"car": "T-114-B", "side": "Right", "state": "Closed"},
            {"car": "T-114-C", "side": "Left", "state": "Closed"},
            {"car": "T-114-C", "side": "Right", "state": "Closed"},
            {"car": "T-114-D", "side": "Left", "state": "Closed"},
            {"car": "T-114-D", "side": "Right", "state": "Closed"},
        ]

        # Failure modes (each has a normal and a failed label).
        self._failure_badge = "1 FAILED"
        self._engine_normal = "ENGINE · NORMAL"
        self._engine_failed = "ENGINE · FAILED 14:12"
        self._engine_failure_state = self._engine_normal
        self._brake_normal = "BRAKE · NORMAL"
        self._brake_failed = "BRAKE · FAILED 14:12"
        self._brake_failure_state = self._brake_normal
        self._signal_normal = "SIGNAL PICKUP · NORMAL"
        self._signal_failed = "SIGNAL PICKUP · FAILED 14:07"
        # Seeded failed to match the mockup.
        self._signal_pickup_state = self._signal_failed

    # -- Top bar --------------------------------------------------------
    def _get_train_selector(self) -> str:
        return self._train_selector

    train_selector = pyqtProperty(
        str, _get_train_selector, notify=train_selector_changed
    )

    def _get_clock(self) -> str:
        return self._clock

    clock = pyqtProperty(str, _get_clock, notify=clock_changed)

    # -- Mode banner ----------------------------------------------------
    def _get_mode_label(self) -> str:
        return self._mode_label

    mode_label = pyqtProperty(str, _get_mode_label, notify=mode_label_changed)

    # -- Speed & Authority ----------------------------------------------
    def _get_speed_auth_badge(self) -> str:
        return self._speed_auth_badge

    speed_auth_badge = pyqtProperty(
        str, _get_speed_auth_badge, notify=speed_auth_badge_changed
    )

    def _get_actual_speed(self) -> str:
        return self._actual_speed

    actual_speed = pyqtProperty(
        str, _get_actual_speed, notify=actual_speed_changed
    )

    def _get_commanded_display(self) -> str:
        return self._commanded_display

    commanded_display = pyqtProperty(
        str, _get_commanded_display, notify=commanded_display_changed
    )

    def _get_speed_limit(self) -> str:
        return self._speed_limit

    speed_limit = pyqtProperty(str, _get_speed_limit, notify=speed_limit_changed)

    def _get_authority(self) -> str:
        return self._authority

    authority = pyqtProperty(str, _get_authority, notify=authority_changed)

    def _get_distance_to_eoa(self) -> str:
        return self._distance_to_eoa

    distance_to_eoa = pyqtProperty(
        str, _get_distance_to_eoa, notify=distance_to_eoa_changed
    )

    def _get_acceleration(self) -> str:
        return self._acceleration

    acceleration = pyqtProperty(
        str, _get_acceleration, notify=acceleration_changed
    )

    def _get_grade(self) -> str:
        return self._grade

    grade = pyqtProperty(str, _get_grade, notify=grade_changed)

    # -- Cabin & Load ---------------------------------------------------
    def _get_cabin_badge(self) -> str:
        return self._cabin_badge

    cabin_badge = pyqtProperty(str, _get_cabin_badge, notify=cabin_badge_changed)

    def _get_passengers(self) -> str:
        return self._passengers

    passengers = pyqtProperty(str, _get_passengers, notify=passengers_changed)

    def _get_loaded_mass(self) -> str:
        return self._loaded_mass

    loaded_mass = pyqtProperty(
        str, _get_loaded_mass, notify=loaded_mass_changed
    )

    def _get_cabin_temp(self) -> str:
        return self._cabin_temp

    cabin_temp = pyqtProperty(str, _get_cabin_temp, notify=cabin_temp_changed)

    def _get_crew(self) -> str:
        return self._crew

    crew = pyqtProperty(str, _get_crew, notify=crew_changed)

    def _get_cars(self) -> str:
        return self._cars

    cars = pyqtProperty(str, _get_cars, notify=cars_changed)

    def _get_train_size(self) -> str:
        return self._train_size

    train_size = pyqtProperty(str, _get_train_size, notify=train_size_changed)

    def _get_empty_mass(self) -> str:
        return self._empty_mass

    empty_mass = pyqtProperty(str, _get_empty_mass, notify=empty_mass_changed)

    def _get_power_consumption(self) -> str:
        return self._power_consumption

    power_consumption = pyqtProperty(
        str, _get_power_consumption, notify=power_consumption_changed
    )

    def _get_power_fill(self) -> float:
        return self._power_fill

    power_fill = pyqtProperty(float, _get_power_fill, notify=power_fill_changed)

    def _get_interior_light_state(self) -> str:
        return self._interior_light_state

    interior_light_state = pyqtProperty(
        str, _get_interior_light_state, notify=interior_light_state_changed
    )

    def _get_exterior_light_state(self) -> str:
        return self._exterior_light_state

    exterior_light_state = pyqtProperty(
        str, _get_exterior_light_state, notify=exterior_light_state_changed
    )

    # -- Position -------------------------------------------------------
    def _get_position_badge(self) -> str:
        return self._position_badge

    position_badge = pyqtProperty(
        str, _get_position_badge, notify=position_badge_changed
    )

    def _get_direction_of_travel(self) -> str:
        return self._direction_of_travel

    direction_of_travel = pyqtProperty(
        str, _get_direction_of_travel, notify=direction_of_travel_changed
    )

    def _get_current_block(self) -> str:
        return self._current_block

    current_block = pyqtProperty(
        str, _get_current_block, notify=current_block_changed
    )

    def _get_distance_into_block(self) -> str:
        return self._distance_into_block

    distance_into_block = pyqtProperty(
        str, _get_distance_into_block, notify=distance_into_block_changed
    )

    def _get_next_station(self) -> str:
        return self._next_station

    next_station = pyqtProperty(str, _get_next_station, notify=next_station_changed)

    # -- Brakes & Doors -------------------------------------------------
    def _get_brakes_badge(self) -> str:
        return self._brakes_badge

    brakes_badge = pyqtProperty(
        str, _get_brakes_badge, notify=brakes_badge_changed
    )

    def _get_passenger_ebrake_state(self) -> str:
        return self._passenger_ebrake_state

    def _set_passenger_ebrake_state(self, value: str) -> None:
        self._passenger_ebrake_state = value
        self.passenger_ebrake_state_changed.emit()

    passenger_ebrake_state = pyqtProperty(
        str,
        _get_passenger_ebrake_state,
        _set_passenger_ebrake_state,
        notify=passenger_ebrake_state_changed,
    )

    def _get_door_states(self) -> list[dict[str, str]]:
        return self._door_states

    door_states = pyqtProperty("QVariantList", _get_door_states, constant=True)

    # -- Failure modes --------------------------------------------------
    def _get_failure_badge(self) -> str:
        return self._failure_badge

    failure_badge = pyqtProperty(
        str, _get_failure_badge, notify=failure_badge_changed
    )

    def _get_engine_failure_state(self) -> str:
        return self._engine_failure_state

    def _set_engine_failure_state(self, value: str) -> None:
        self._engine_failure_state = value
        self.engine_failure_state_changed.emit()

    engine_failure_state = pyqtProperty(
        str,
        _get_engine_failure_state,
        _set_engine_failure_state,
        notify=engine_failure_state_changed,
    )

    def _get_brake_failure_state(self) -> str:
        return self._brake_failure_state

    def _set_brake_failure_state(self, value: str) -> None:
        self._brake_failure_state = value
        self.brake_failure_state_changed.emit()

    brake_failure_state = pyqtProperty(
        str,
        _get_brake_failure_state,
        _set_brake_failure_state,
        notify=brake_failure_state_changed,
    )

    def _get_signal_pickup_state(self) -> str:
        return self._signal_pickup_state

    def _set_signal_pickup_state(self, value: str) -> None:
        self._signal_pickup_state = value
        self.signal_pickup_state_changed.emit()

    signal_pickup_state = pyqtProperty(
        str,
        _get_signal_pickup_state,
        _set_signal_pickup_state,
        notify=signal_pickup_state_changed,
    )

    # -- Slots (stub behaviour only) ------------------------------------
    @pyqtSlot()
    def apply_emergency_brake(self) -> None:
        """Toggle the passenger e-brake between released and applied."""
        applied = "APPLIED"
        self.passenger_ebrake_state = (
            "RELEASED" if self._passenger_ebrake_state == applied else applied
        )

    @pyqtSlot()
    def toggle_engine_failure(self) -> None:
        """Flip the engine failure state between normal and failed."""
        self.engine_failure_state = (
            self._engine_normal
            if self._engine_failure_state == self._engine_failed
            else self._engine_failed
        )

    @pyqtSlot()
    def toggle_brake_failure(self) -> None:
        """Flip the brake failure state between normal and failed."""
        self.brake_failure_state = (
            self._brake_normal
            if self._brake_failure_state == self._brake_failed
            else self._brake_failed
        )

    @pyqtSlot()
    def toggle_signal_pickup(self) -> None:
        """Flip the signal-pickup failure between cleared and failed."""
        self.signal_pickup_state = (
            self._signal_normal
            if self._signal_pickup_state == self._signal_failed
            else self._signal_failed
        )
