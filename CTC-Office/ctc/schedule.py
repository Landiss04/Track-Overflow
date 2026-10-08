"""Train schedules for the CTC Office, read from JSON.

The format is the one ``tools/schedule_to_json.py`` writes
(``utils/schedule_v4.json``): per line, per train, the ordered timed
stops, each with a block ID, an optional station name and an arrival
time in seconds after the schedule start. IDs are strings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ctc.model import CtcError


class ScheduleError(CtcError):
    """A schedule file could not be read or is malformed."""


@dataclass(frozen=True, slots=True)
class ScheduledStop:
    block_id: str
    station: str | None
    arrival_s: int


@dataclass(frozen=True, slots=True)
class ScheduledTrain:
    """One scheduled run on one line."""

    line: str
    train_id: str
    stops: tuple[ScheduledStop, ...]

    @property
    def departure_s(self) -> int:
        """When the run is due at its first stop."""
        return self.stops[0].arrival_s


@dataclass(frozen=True, slots=True)
class Schedule:
    source: str
    trains: tuple[ScheduledTrain, ...]


def _stop(raw: Any, where: str) -> ScheduledStop:
    try:
        block_id, arrival_s = raw["block_id"], raw["arrival_s"]
        station = raw.get("station")
    except (TypeError, KeyError) as error:
        raise ScheduleError(f"{where}: missing {error}") from None
    if not isinstance(block_id, str) or not block_id:
        raise ScheduleError(f"{where}: block_id must be a string ID")
    if (isinstance(arrival_s, bool) or not isinstance(arrival_s, int)
            or arrival_s < 0):
        raise ScheduleError(f"{where}: arrival_s must be whole seconds >= 0")
    if station is not None and not isinstance(station, str):
        raise ScheduleError(f"{where}: station must be a name")
    return ScheduledStop(block_id, station or None, arrival_s)


def _list(value: Any, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise ScheduleError(f"{what} must be a list")
    return value


def parse_schedule(data: Any, source: str = "") -> Schedule:
    """Build a ``Schedule`` from loaded JSON, or raise an error."""
    if not isinstance(data, dict) or data.get("time_unit") != "s":
        raise ScheduleError(
            "not a schedule file: expected the schedule_v4.json format")
    trains = []
    runs: set[tuple[str, str]] = set()
    for number, line in enumerate(_list(data.get("lines", []), "lines"), 1):
        if not isinstance(line, dict):
            raise ScheduleError(f"line {number} must be an object")
        name = line.get("line")
        if not isinstance(name, str) or not name:
            raise ScheduleError(f"line {number}: line must be a name")
        for train in _list(line.get("trains", []), f"{name} trains"):
            if not isinstance(train, dict):
                raise ScheduleError(f"{name}: every train must be an object")
            train_id = str(train.get("train_id", ""))
            where = f"{name} train {train_id}"
            if not train_id:
                raise ScheduleError(f"{name}: a train has no train_id")
            if (name, train_id) in runs:
                raise ScheduleError(f"{where} is listed twice")
            runs.add((name, train_id))
            stops = tuple(_stop(raw, f"{where} stop {i + 1}")
                          for i, raw in enumerate(
                              _list(train.get("stops", []),
                                    f"{where} stops")))
            if not stops:
                raise ScheduleError(f"{where}: no stops")
            for i, (before, after) in enumerate(zip(stops, stops[1:]), 2):
                if after.arrival_s < before.arrival_s:
                    raise ScheduleError(
                        f"{where} stop {i}: arrives before the stop "
                        "before it")
            trains.append(ScheduledTrain(name, train_id, stops))
    if not trains:
        raise ScheduleError("the schedule has no trains")
    return Schedule(source=source, trains=tuple(trains))


def load_schedule(path: Path) -> Schedule:
    """Read a schedule JSON file, or raise ``ScheduleError``."""
    try:
        with open(path, encoding="utf-8") as schedule_file:
            data = json.load(schedule_file)
    except (OSError, ValueError) as error:
        raise ScheduleError(f"could not read {path.name}: {error}") from None
    return parse_schedule(data, source=path.name)
