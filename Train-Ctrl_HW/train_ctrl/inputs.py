"""Read and check Train Model signals before any state is touched."""

from __future__ import annotations

from typing import Any

from .constants import ASPECTS, BEACON_SIDES
from .errors import InvalidInputError


# What the Train Model sends every tick (module-interface.md on
# development). A harness tick missing one would leave the last value
# standing, and a stale Brake State reads as a brake failure, so the
# fleet refuses it. Beacon and aspect are not here: a beacon is only
# heard near a station (truth beacon.md).
EVERY_TICK = ("actual_speed", "commanded_speed", "authority_blocks",
              "emergency_brake_state", "service_brake_state",
              "door_state", "light_state", "cabin_temperature")


def _read_flags(values: dict, key: str, count: int) -> list[bool]:
    # A bool[N] signal arrives as a list; anything else, or a list of
    # the wrong length, is a caller error.
    flags = values[key]
    if not isinstance(flags, (list, tuple)) or len(flags) != count:
        raise InvalidInputError(
            f"{key} must be {count} flags, not {flags!r}")
    return [bool(flag) for flag in flags]


def _read_number(values: dict, key: str) -> float:
    # Bench values arrive from QML untyped; a value that is not a
    # number is a caller error, raised in this module's own terms.
    try:
        return float(values[key])
    except (TypeError, ValueError) as error:
        raise InvalidInputError(
            f"{key} must be a number, not {values[key]!r}"
        ) from error


def read_inputs(values: dict) -> dict[str, Any]:
    """Read and check a set of Train Model signals, touching no state.

    Keys and shapes follow truth signals/: commanded_speed and
    actual_speed (m/s, actual signed),
    cabin_temperature (C), authority_blocks, signal_light_ahead,
    beacon_station / beacon_side / beacon_underground,
    emergency_brake_state and service_brake_state (bool each, what is
    engaged; REQUIREMENTS.md M18), door_state bool[2] (left, right)
    and light_state bool[2] (interior, exterior). There is no
    failure status: the Train Model no longer sends one (truth
    modules/train-model.md); detect_failures() infers failures
    instead. Unknown keys are ignored.

    The whole set is read before any of it is applied, so a caller
    can refuse it outright. Raises InvalidInputError for a value
    that cannot be read as its type.
    """
    staged: dict[str, Any] = {}
    # A null commanded speed or authority is a Track Signal the Train
    # Model could not read: a signal pickup failure (Kevin Schillinger
    # 2026-10-28). The last values received are kept, unused.
    signal = [key for key in ("commanded_speed", "authority_blocks")
              if key in values]
    if signal:
        staged["signal_lost"] = any(values[key] is None for key in signal)
    # Commanded speed is the speed limit; a separate speed_limit is
    # ignored like any unknown key (REQUIREMENTS.md M1).
    if values.get("commanded_speed") is not None:
        staged["commanded_mps"] = max(
            0.0, _read_number(values, "commanded_speed"))
    if "actual_speed" in values:
        staged["actual_mps"] = _read_number(values, "actual_speed")
    if "cabin_temperature" in values:
        staged["cabin_temp_c"] = _read_number(
            values, "cabin_temperature")
    if values.get("authority_blocks") is not None:
        staged["authority_blocks"] = max(
            0, int(_read_number(values, "authority_blocks")))
    if "beacon_station" in values:
        staged["beacon_station"] = str(values["beacon_station"])
    if values.get("beacon_side") in BEACON_SIDES:
        staged["beacon_side"] = values["beacon_side"]
    if "beacon_underground" in values:
        staged["beacon_underground"] = bool(
            values["beacon_underground"])
    if values.get("signal_light_ahead") in ASPECTS:
        staged["next_signal"] = values["signal_light_ahead"]
    for key in ("emergency_brake_state", "service_brake_state"):
        if key in values:
            staged[key] = bool(values[key])
    if "door_state" in values:
        staged["fb_doors_left"], staged["fb_doors_right"] = (
            _read_flags(values, "door_state", 2))
    if "light_state" in values:
        (staged["fb_interior_lights"],
         staged["fb_exterior_lights"]) = _read_flags(
            values, "light_state", 2)
    return staged
