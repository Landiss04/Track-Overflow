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
    if not isinstance(arrival_s, int) or arrival_s < 0:
        raise ScheduleError(f"{where}: arrival_s must be whole seconds >= 0")
    return ScheduledStop(block_id, station or None, arrival_s)


def parse_schedule(data: Any, source: str = "") -> Schedule:
    """Build a ``Schedule`` from loaded JSON, or raise an error."""
    if not isinstance(data, dict) or data.get("time_unit") != "s":
        raise ScheduleError(
            "not a schedule file: expected the schedule_v4.json format")
    trains = []
    for line in data.get("lines", []):
        name = line.get("line")
        for train in line.get("trains", []):
            train_id = str(train.get("train_id", ""))
            where = f"{name} train {train_id}"
            stops = tuple(_stop(raw, f"{where} stop {i + 1}")
                          for i, raw in enumerate(train.get("stops", [])))
            if not stops:
                raise ScheduleError(f"{where}: no stops")
            trains.append(ScheduledTrain(str(name), train_id, stops))
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
