"""Fleet/core/state display proxies for the unchanged Train console backend."""

from __future__ import annotations

from typing import Any, Iterator
from .cores import TrainCore
from .relay import HardwareRelay


class RemoteState:
    """Intercept the console's direct state assignments as ordered ACTIONs."""

    def __init__(self, core: RemoteTrainCore) -> None:
        object.__setattr__(self, "_core", core)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._core._mirror.state, name)

    def __setattr__(self, name: str, value: Any) -> None:
        self._core._relay.call_action(
            "set_state",
            {"train_id": self._core.train_id, "field": name, "value": value},
        )


class RemoteTrainCore:
    """An unstepped display mirror; control methods run only on the Pi."""

    def __init__(self, train_id: str, relay: HardwareRelay) -> None:
        from train_ctrl.control import ControllerCore

        object.__setattr__(self, "train_id", train_id)
        object.__setattr__(self, "_relay", relay)
        object.__setattr__(self, "_mirror", ControllerCore())
        object.__setattr__(self, "state", RemoteState(self))

    def __getattr__(self, name: str) -> Any:
        if name in TrainCore.METHODS:

            def call(*values: Any) -> Any:
                return self._relay.call_action(
                    "core_method",
                    {
                        "train_id": self.train_id,
                        "method": name,
                        "values": list(values),
                    },
                )

            return call
        return getattr(self._mirror, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in TrainCore.CORE_FIELDS:
            raise AttributeError(f"not a remote console field: {name}")
        self._relay.call_action(
            "set_core",
            {"train_id": self.train_id, "field": name, "value": value},
        )

    def update(self, entry: dict[str, Any]) -> None:
        for key, value in entry["state"].items():
            setattr(self._mirror.state, key, value)
        for key, value in entry["core"].items():
            setattr(self._mirror, key, value)


class RemoteTrainFleet:
    """Roster and display cores for ConsoleBackend(fleet=...)."""

    def __init__(self, relay: HardwareRelay) -> None:
        self.relay = relay
        self._cores: dict[str, RemoteTrainCore] = {}
        relay.viewChanged.connect(self._view)

    def _view(self, view: dict[str, Any]) -> None:
        if "trains" not in view:
            return
        trains = view["trains"]
        for key in list(self._cores):
            if key not in trains:
                del self._cores[key]
        for key, entry in trains.items():
            if key not in self._cores:
                self._cores[key] = RemoteTrainCore(key, self.relay)
            self._cores[key].update(entry)

    def ids(self) -> list[str]:
        return list(self._cores)

    def get(self, train_id: str) -> RemoteTrainCore:
        return self._cores[train_id]

    def __contains__(self, train_id: object) -> bool:
        return train_id in self._cores

    def __len__(self) -> int:
        return len(self._cores)

    def __iter__(self) -> Iterator[RemoteTrainCore]:
        return iter(list(self._cores.values()))
