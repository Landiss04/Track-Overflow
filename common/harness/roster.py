"""The trains in service, as the CTC Office releases and retires them.

The CTC Office creates each train when it releases it from the yard,
and retires it at the yard entry block (D022). It reports both as
one-time events in its outputs, and the harness applies each tick's
events exactly once:

- ``new_trains``: a list of ``{"train_id": ..., "line": ...}``, one per
  train released on that tick;
- ``retired_trains``: a list of ``{"train_id": ...}``, one per train
  retired on that tick.

A released train joins the Train Model and its line's Train Controller
from the next tick; a retired train leaves them. Train IDs are the CTC
Office's, used unchanged (``conventions/identifiers.md``).
"""

from __future__ import annotations

__all__ = ["LINES", "Roster", "TrainEntry"]

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

#: The lines in scope; the Blue Line is not (D023).
LINES = ("Green", "Red")

#: The longest train ID (``conventions/identifiers.md``).
MAX_TRAIN_ID_LENGTH = 32

# (source, event, detail), as the harness logs it.
Event = tuple[str, str, str]


@dataclass(frozen=True)
class TrainEntry:
    """One train in service.

    Attributes:
        train_id: The CTC Office's ID for the train.
        line: ``"Green"`` or ``"Red"``.
        joined_s: Simulation time of the tick it entered service.
    """

    train_id: str
    line: str
    joined_s: float


class Roster:
    """Every train in service, in release order."""

    def __init__(self, source: str) -> None:
        """Start with no trains.

        Args:
            source: The module whose events the roster follows, for
                the log.
        """
        self._source = source
        self._trains: dict[str, TrainEntry] = {}

    def __iter__(self) -> Iterator[TrainEntry]:
        return iter(list(self._trains.values()))

    def __len__(self) -> int:
        return len(self._trains)

    def __contains__(self, train_id: object) -> bool:
        return train_id in self._trains

    def apply(
        self, outputs: Mapping[str, Any], sim_time_s: float
    ) -> list[Event]:
        """Apply one tick's release and retire events.

        Call it once per tick, with the outputs the CTC Office gave on
        that tick, so each event is applied exactly once.

        Args:
            outputs: The CTC Office's outputs for one tick.
            sim_time_s: Simulation time of that tick.

        Returns:
            Events for the log: each train added or removed, and each
            event refused, with the reason.
        """
        events: list[Event] = []
        for item in _items(outputs, "new_trains", events, self._source):
            train_id = item.get("train_id")
            line = item.get("line")
            problem = _id_problem(train_id) or _line_problem(line)
            if problem is None and train_id in self._trains:
                problem = f"{train_id} is already in service"
            if problem is not None:
                events.append(
                    (self._source, "PROTOCOL_ERROR",
                     f"release refused: {problem}")
                )
                continue
            # Both are checked strings by now.
            entry = TrainEntry(str(train_id), str(line), sim_time_s)
            self._trains[entry.train_id] = entry
            events.append(
                ("harness", "TRAIN_ADDED", f"{train_id} on {line}")
            )
        for item in _items(outputs, "retired_trains", events, self._source):
            train_id = item.get("train_id")
            if train_id not in self._trains:
                events.append(
                    (self._source, "PROTOCOL_ERROR",
                     f"retire refused: no train {train_id!r} in service")
                )
                continue
            del self._trains[train_id]
            events.append(("harness", "TRAIN_REMOVED", train_id))
        return events


def _items(
    outputs: Mapping[str, Any],
    key: str,
    events: list[Event],
    source: str,
) -> list[Mapping[str, Any]]:
    # One event list from the outputs; a missing key is no events, and
    # anything that is not a list of objects is refused whole.
    value = outputs.get(key, [])
    if isinstance(value, list) and all(
        isinstance(item, Mapping) for item in value
    ):
        return value
    events.append(
        (source, "PROTOCOL_ERROR", f"{key} must be a list of objects")
    )
    return []


def _id_problem(train_id: Any) -> str | None:
    # A train ID is a plain string, trimmed and printable, at most 32
    # characters (conventions/identifiers.md).
    if not isinstance(train_id, str) or not train_id:
        return f"train ID must be a non-empty string, got {train_id!r}"
    if train_id != train_id.strip() or not train_id.isprintable():
        return f"train ID must be trimmed and printable: {train_id!r}"
    if len(train_id) > MAX_TRAIN_ID_LENGTH:
        return f"train ID longer than {MAX_TRAIN_ID_LENGTH}: {train_id!r}"
    return None


def _line_problem(line: Any) -> str | None:
    # One of the lines in scope, spelled exactly.
    if line not in LINES:
        return f"line must be one of {', '.join(LINES)}, got {line!r}"
    return None
