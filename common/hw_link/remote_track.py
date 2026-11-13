"""TrackController adapter injected into the existing window state."""

from __future__ import annotations

from typing import Any
from .codec import unpack
from .relay import HardwareRelay


class RemoteTrackController:
    """Cached display snapshots; all mutable control state lives on the Pi."""

    def __init__(self, relay: HardwareRelay) -> None:
        from track_ctrl_hw.interface import TrackControllerSnapshot

        self.relay = relay
        self._snapshot = TrackControllerSnapshot(None, (), None, 0, False, ())
        relay.viewChanged.connect(self._view)

    def _view(self, view: dict[str, Any]) -> None:
        if "snapshot" in view:
            self._snapshot = unpack(view["snapshot"])

    @property
    def wayside_ids(self) -> tuple[str, ...]:
        return tuple(w.territory.wayside_id for w in self._snapshot.waysides)

    @property
    def ticks(self) -> int:
        return self._snapshot.ticks

    @property
    def line(self) -> str | None:
        return self._snapshot.line

    def snapshot(self) -> Any:
        return self._snapshot

    def load_territory(self, territory: Any) -> Any:
        from track_ctrl_hw.errors import TerritoryError
        from track_ctrl_hw.wire import territory_to_wire

        try:
            return (
                self.relay.call_action(
                    "load_territory",
                    {"territory": territory_to_wire(territory)},
                )
                or ()
            )
        except (ValueError, ConnectionError) as error:
            raise TerritoryError(str(error)) from error

    def load_program(
        self, wayside_id: str, source: str, file_name: str
    ) -> Any:
        from track_ctrl_hw.errors import PlcError

        try:
            return unpack(
                self.relay.call_action(
                    "load_program",
                    {
                        "wayside_id": wayside_id,
                        "source": source,
                        "file_name": file_name,
                    },
                )
            )
        except (ValueError, ConnectionError) as error:
            raise PlcError(
                str(error), getattr(error, "diagnostics", ())
            ) from error

    def reset(self) -> None:
        self.relay.call_action("reset", {})

    def step(self, dt: float, inputs: Any) -> Any:
        # The standalone test-link must never become a second driver.
        from track_ctrl_hw.errors import InvalidInputError

        raise InvalidInputError(
            "The central harness is the sole Pi clock driver."
        )
