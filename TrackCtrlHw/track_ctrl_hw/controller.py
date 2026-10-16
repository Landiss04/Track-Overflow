"""The hardware Track Controller: every wayside of one line.

``HwTrackController`` implements the ``TrackController`` protocol in
``track_ctrl_hw.interface``. It holds one ``Wayside`` per loaded
database, all on the same line, and scans each of them once per step.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from track_ctrl_hw.errors import (
    InvalidInputError,
    InvalidTimeStepError,
    PlcError,
    TerritoryError,
)
from track_ctrl_hw.interface import (
    FAILURE_KINDS,
    SIGNAL_ASPECTS,
    SWITCH_POSITIONS,
    BlockKey,
    ProgramInfo,
    Suggestion,
    Territory,
    TrackCircuitCommand,
    TrackControllerInputs,
    TrackControllerOutputs,
    TrackControllerSnapshot,
    TrackModelOutputs,
)
from track_ctrl_hw.wayside import Wayside


class HwTrackController:
    """One line's wayside controllers. See ``TrackController``."""

    def __init__(self) -> None:
        self._waysides: dict[str, Wayside] = {}
        self._time_s: float | None = None
        self._ticks = 0
        self._maintenance = False

    # -- configuration, from the Track Controller UI -----------------

    @property
    def line(self) -> str | None:
        """The line this controller runs, once a wayside is loaded."""
        for wayside in self._waysides.values():
            return wayside.territory.line
        return None

    @property
    def wayside_ids(self) -> tuple[str, ...]:
        """Loaded waysides, in load order."""
        return tuple(self._waysides)

    @property
    def ticks(self) -> int:
        """Steps taken since the last reset."""
        return self._ticks

    def load_territory(self, territory: Territory) -> tuple[str, ...]:
        """Add a wayside, or replace the one with the same ID.

        Returns:
            Notices for the user, such as a program that no longer fits
            the replaced territory and was unloaded.

        Raises:
            TerritoryError: If the territory is on another line or
                claims a block another wayside governs.
        """
        line = self.line
        if line is not None and territory.line != line:
            raise TerritoryError(
                f"This controller runs the {line} line, and the database "
                f"is for the {territory.line} line. A Track Controller runs "
                "one line; restart it to change lines."
            )
        for other_id, other in self._waysides.items():
            if other_id == territory.wayside_id:
                continue
            shared = sorted(
                (key for key in territory.keys if other.owns(key)),
                key=lambda key: int(key.block_id),
            )
            if shared:
                raise TerritoryError(
                    f"Wayside {other_id} already governs block "
                    f"{shared[0].label}; a block belongs to one wayside."
                )
        wayside = Wayside(territory)
        notices: list[str] = []
        previous = self._waysides.get(territory.wayside_id)
        if previous is not None and previous.program is not None:
            if not wayside.adopt_program(previous):
                notices.append(
                    f"Wayside {territory.wayside_id}'s PLC program does not "
                    "fit the new database and was unloaded. Load a program "
                    "written for it."
                )
        self._waysides[territory.wayside_id] = wayside
        return tuple(notices)

    def load_program(
        self, wayside_id: str, source: str, file_name: str
    ) -> ProgramInfo:
        """Replace a wayside's PLC program; see ``TrackController``.

        Raises:
            PlcError: If the program has errors or does not fit, or no
                such wayside is loaded.
        """
        wayside = self._waysides.get(wayside_id)
        if wayside is None:
            raise PlcError(f"No wayside {wayside_id} is loaded.")
        return wayside.load_program(source, file_name, self._time_s)

    def reset(self) -> None:
        """Forget every scan; keep territories and programs."""
        for wayside in self._waysides.values():
            wayside.reset()
        self._time_s = None
        self._ticks = 0
        self._maintenance = False

    # -- the module boundary -----------------------------------------

    def step(
        self, dt: float, inputs: TrackControllerInputs
    ) -> TrackControllerOutputs:
        """Scan every wayside once; see ``TrackController.step``."""
        if (
            isinstance(dt, bool)
            or not isinstance(dt, (int, float))
            or not math.isfinite(dt)
            or dt <= 0
        ):
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {dt!r}"
            )
        _validate(inputs)
        circuits: dict[BlockKey, TrackCircuitCommand] = {}
        switches = {}
        crossings = {}
        signals = {}
        reports = []
        for wayside in self._waysides.values():
            result = wayside.scan(
                float(dt), inputs.time_s, inputs.ctc, inputs.track_model
            )
            circuits.update(result.track_circuits)
            switches.update(result.switch_commands)
            crossings.update(result.crossing_commands)
            signals.update(result.signal_commands)
            reports.append(result.report)
        self._time_s = inputs.time_s
        self._ticks += 1
        self._maintenance = inputs.ctc.maintenance_mode
        return TrackControllerOutputs(
            track_model=TrackModelOutputs(
                track_circuits=circuits,
                switch_commands=switches,
                crossing_commands=crossings,
                signal_commands=signals,
            ),
            ctc_reports=tuple(reports),
        )

    def snapshot(self) -> TrackControllerSnapshot:
        """Current state for display. No side effects."""
        return TrackControllerSnapshot(
            line=self.line,
            waysides=tuple(
                wayside.snapshot() for wayside in self._waysides.values()
            ),
            maintenance_mode=self._maintenance,
            time_s=self._time_s,
            ticks=self._ticks,
        )


def _validate(inputs: Any) -> None:
    # Reject anything step must not act on, before any state changes.
    if not isinstance(inputs, TrackControllerInputs):
        raise InvalidInputError("inputs must be TrackControllerInputs")
    if (
        isinstance(inputs.time_s, bool)
        or not isinstance(inputs.time_s, (int, float))
        or not math.isfinite(inputs.time_s)
        or inputs.time_s < 0
    ):
        raise InvalidInputError(
            f"time_s must be a finite, non-negative number, got "
            f"{inputs.time_s!r}"
        )
    ctc = inputs.ctc
    model = inputs.track_model
    if not isinstance(ctc.maintenance_mode, bool):
        raise InvalidInputError("maintenance_mode must be true or false")
    _keys(ctc.closed_blocks, "closed_blocks")
    _keys(model.occupied_blocks, "occupied_blocks")
    _choices(ctc.switch_commands, SWITCH_POSITIONS, "switch_commands")
    _choices(model.switch_positions, SWITCH_POSITIONS, "switch_positions")
    _choices(model.signal_aspects, SIGNAL_ASPECTS, "signal_aspects")
    _choices(model.failures, FAILURE_KINDS, "failures")
    _keys(model.crossings_active, "crossings_active")
    for key, active in model.crossings_active.items():
        if not isinstance(active, bool):
            raise InvalidInputError(
                f"crossings_active[{key.label}] must be true or false"
            )
    _keys(ctc.suggestions, "suggestions")
    for key, suggestion in ctc.suggestions.items():
        if not isinstance(suggestion, Suggestion):
            raise InvalidInputError(
                f"suggestions[{key.label}] must be a Suggestion"
            )
        for name in ("speed_mps", "authority_blocks"):
            value = getattr(suggestion, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidInputError(
                    f"suggestions[{key.label}].{name} must be a whole "
                    f"number, got {value!r}"
                )
            if value < 0:
                raise InvalidInputError(
                    f"suggestions[{key.label}].{name} must not be "
                    f"negative, got {value}"
                )


def _keys(keys: Iterable[Any], name: str) -> None:
    for key in keys:
        if not isinstance(key, BlockKey):
            raise InvalidInputError(f"{name} must be keyed by BlockKey")


def _choices(
    values: Mapping[Any, Any], allowed: tuple[str, ...], name: str
) -> None:
    _keys(values, name)
    for key, value in values.items():
        if value not in allowed:
            raise InvalidInputError(
                f"{name}[{key.label}] must be one of {', '.join(allowed)}, "
                f"got {value!r}"
            )
