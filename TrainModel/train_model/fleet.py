"""Every running train's Train Model, held by train ID.

The module is one train per :class:`TrainModelState`; the fleet is the
set of them in the system process. Whoever owns dispatch (the central
harness once integrated) adds a train when it enters service, removes
it when it leaves, and steps the fleet once per shared-clock tick. The
Train Model window shows whichever train is selected.

Train IDs are opaque strings (``conventions/identifiers.md``).
"""

from __future__ import annotations

import zlib
from typing import Any, Iterator, Mapping

from PySide6.QtCore import Property, QObject, Signal, Slot

from train_model.interface import (
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
)
from train_model.model import TrainModelError
from train_model.state import TrainModelState


class TrainModelFleetError(TrainModelError):
    """Base class for errors in managing the set of trains."""


class DuplicateTrainError(TrainModelFleetError):
    """A train with that ID is already in the fleet."""


class UnknownTrainError(TrainModelFleetError, KeyError):
    """No train with that ID is in the fleet."""


class TrainModelFleet(QObject):
    """Holds one :class:`TrainModelState` per running train."""

    rosterChanged = Signal()
    currentChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Insertion order is the roster order.
        self._trains: dict[str, TrainModelState] = {}
        self._selected = ""
        # Shown while no train is selected, so the window always has a
        # train to bind to. It is never stepped.
        self._idle = TrainModelState(parent=self)

    # ------------------------------------------------------------------ #
    # Driven by whoever owns dispatch
    # ------------------------------------------------------------------ #

    def add(
        self,
        train_id: str,
        line: str = "",
        config: TrainConfig | None = None,
    ) -> TrainModelState:
        """Put a new train in service and return its Train Model.

        Without ``config`` the seed is derived from the train ID, so
        each train draws its own disembark counts and a run repeats.
        """
        if train_id in self._trains:
            raise DuplicateTrainError(f"train {train_id!r} already exists")
        if config is None:
            config = TrainConfig(seed=zlib.crc32(train_id.encode()))
        state = TrainModelState(
            config, parent=self, train_id=train_id, line=line,
        )
        self._trains[train_id] = state
        if not self._selected:
            self._selected = train_id
            self.currentChanged.emit()
        self.rosterChanged.emit()
        return state

    def remove(self, train_id: str) -> None:
        """Take a train out of service and drop its Train Model."""
        state = self.get(train_id)
        ids = list(self._trains)
        index = ids.index(train_id)
        del self._trains[train_id]
        if self._selected == train_id:
            # The next train in the roster, else the one before it.
            rest = ids[:index] + ids[index + 1:]
            self._selected = rest[min(index, len(rest) - 1)] if rest else ""
            self.currentChanged.emit()
        self.rosterChanged.emit()
        # Only now nothing binds to it any more.
        state.deleteLater()

    def get(self, train_id: str) -> TrainModelState:
        """Return one train's Train Model."""
        try:
            return self._trains[train_id]
        except KeyError:
            raise UnknownTrainError(f"no train {train_id!r}") from None

    def ids(self) -> list[str]:
        """Every train's ID, in the order the trains were added."""
        return list(self._trains)

    def __contains__(self, train_id: object) -> bool:
        return train_id in self._trains

    def __len__(self) -> int:
        return len(self._trains)

    def __iter__(self) -> Iterator[TrainModelState]:
        return iter(list(self._trains.values()))

    def step_all(
        self, dt: float, inputs_by_id: Mapping[str, TrainModelInputs],
    ) -> dict[str, TrainModelOutputs]:
        """Step every train one tick, or none of them.

        Every train's inputs are validated before any train steps, so
        input one train would reject leaves the whole fleet unchanged.
        ``inputs_by_id`` must hold exactly one entry per train.
        """
        unknown = sorted(set(inputs_by_id) - set(self._trains))
        if unknown:
            raise UnknownTrainError(f"inputs for unknown trains: {unknown}")
        missing = [i for i in self._trains if i not in inputs_by_id]
        if missing:
            raise TrainModelFleetError(f"no inputs for trains: {missing}")
        for train_id, state in self._trains.items():
            state.validate_inputs(dt, inputs_by_id[train_id])
        return {
            train_id: state.step(dt, inputs_by_id[train_id])
            for train_id, state in self._trains.items()
        }

    # ------------------------------------------------------------------ #
    # Read by the window
    # ------------------------------------------------------------------ #

    @Property(QObject, notify=currentChanged)
    def current(self) -> TrainModelState:
        """The selected train, or an idle stand-in if there is none."""
        return self._trains.get(self._selected, self._idle)

    @Property("QVariantList", notify=rosterChanged)  # type: ignore[arg-type]
    def trains(self) -> list[dict[str, Any]]:
        """The roster the train selector shows."""
        return [
            {
                "id": train_id,
                "line": state.line,
                "label": (
                    f"{train_id} · {state.line}" if state.line
                    else train_id
                ),
            }
            for train_id, state in self._trains.items()
        ]

    @Property(int, notify=rosterChanged)
    def selectedIndex(self) -> int:
        """The selected train's place in the roster, or -1."""
        ids = list(self._trains)
        return ids.index(self._selected) if self._selected in ids else -1

    @Property(int, notify=rosterChanged)
    def count(self) -> int:
        """How many trains are in service."""
        return len(self._trains)

    @Slot(str)
    def selectTrain(self, train_id: str) -> None:
        """Point the window at one train; an unknown ID is ignored."""
        if train_id not in self._trains or train_id == self._selected:
            return
        self._selected = train_id
        self.currentChanged.emit()
        self.rosterChanged.emit()
